def test_config_exposes_analysis_defaults(app):
    # ANALYSIS_MODEL defaults to Sonnet 5 when the env var is unset.
    assert app.config["ANALYSIS_MODEL"] == "claude-sonnet-5"
    # The key is always present in config (value may be None when unset).
    assert "ANTHROPIC_API_KEY" in app.config
