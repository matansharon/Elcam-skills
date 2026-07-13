import pytest

from analysis import analyze_skill, AnalysisError, MAX_TAGS, MAX_RELATED


class _Block:
    def __init__(self, type, input=None):
        self.type = type
        self.input = input


class _Resp:
    def __init__(self, blocks):
        self.content = blocks


class _FakeMessages:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._resp


class FakeClient:
    """Stand-in for anthropic.Anthropic; returns a canned tool_use response."""
    def __init__(self, tool_input=None, blocks=None):
        if blocks is None:
            blocks = [_Block("text"), _Block("tool_use", input=tool_input)]
        self.messages = _FakeMessages(_Resp(blocks))


CANDIDATES = [
    {"id": 1, "name": "PDF Extractor", "description": "d", "category": "data"},
    {"id": 2, "name": "Table Parser", "description": "d", "category": "data"},
]


def _analyze(tool_input, candidates=CANDIDATES):
    client = FakeClient(tool_input=tool_input)
    return analyze_skill(client, "claude-sonnet-5", "N", "desc", "body", candidates)


def test_happy_path():
    out = _analyze({
        "category": " data ",
        "status": "active",
        "tags": ["pdf", "tables"],
        "related": [{"skill_id": 1, "type": "depends_on", "reason": "x"}],
    })
    assert out == {
        "category": "data",
        "status": "active",
        "tags": ["pdf", "tables"],
        "related": [{"skill_id": 1, "type": "depends_on"}],
    }


def test_invalid_status_clamped_to_draft():
    out = _analyze({"category": "c", "status": "shipped", "tags": [], "related": []})
    assert out["status"] == "draft"


def test_invalid_relationship_type_dropped():
    out = _analyze({
        "category": "c", "status": "draft", "tags": [],
        "related": [{"skill_id": 1, "type": "bogus"}],
    })
    assert out["related"] == []


def test_unknown_skill_id_dropped():
    out = _analyze({
        "category": "c", "status": "draft", "tags": [],
        "related": [{"skill_id": 999, "type": "used_with"}],
    })
    assert out["related"] == []


def test_related_deduped():
    out = _analyze({
        "category": "c", "status": "draft", "tags": [],
        "related": [
            {"skill_id": 1, "type": "used_with"},
            {"skill_id": 1, "type": "used_with"},
        ],
    })
    assert out["related"] == [{"skill_id": 1, "type": "used_with"}]


def test_tags_deduped_and_capped():
    out = _analyze({
        "category": "c", "status": "draft",
        "tags": ["A", "a", " b "] + [f"t{i}" for i in range(20)],
        "related": [],
    })
    assert len(out["tags"]) == MAX_TAGS
    assert out["tags"][0] == "A"          # first-wins, original casing kept
    assert "a" not in out["tags"][1:]     # case-insensitive dupe removed
    assert out["tags"][1] == "b"          # stripped


def test_missing_tool_use_raises():
    client = FakeClient(blocks=[_Block("text")])
    with pytest.raises(AnalysisError):
        analyze_skill(client, "m", "N", "d", "b", CANDIDATES)
