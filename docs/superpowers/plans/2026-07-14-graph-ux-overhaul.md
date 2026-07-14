# Skill Graph UX/UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Skill Graph clear and well-spread by default — readable on load with no interaction — and pleasant to explore (controls, search, hover).

**Architecture:** Swap Cytoscape's `cose` layout for force-directed `fcose` (overlap avoidance + component packing) and fit-to-view on every render. Declutter labels (node-name background chips + wrapping; edge type labels shown only for the highlighted neighborhood). Size nodes by connectivity. Add an overlaid control cluster (zoom/fit/re-spread), a sidebar search-to-focus, hover preview + click-to-pin, and loading/empty states. Frontend only — `/api/graph` is unchanged.

**Tech Stack:** React 18 + React Router 6 + Vite, Cytoscape.js 3 + `cytoscape-fcose` (new). No frontend test runner exists — every task is verified by `npm run build` succeeding, plus explicit Playwright smoke steps against a running dev/demo server.

## Global Constraints

- Python interpreter: `C:\Users\Matan\python\Elcam-Skills\.venv\Scripts\python.exe` (machine `python3` is a broken Windows Store alias; use `python`).
- Demo server: `PORT=5100 .venv\Scripts\python.exe backend\app.py` serves the built frontend at http://localhost:5100 (port 5000 is taken by another app). Frontend must be rebuilt (`cd frontend && npm run build`) for changes to show on :5100. Dev alternative: `run_dev.bat` (Vite :5173 proxying `/api` → :5100).
- Demo login for smoke tests: `admin` / `admin123` (sees all 8 skills). Graph route: `/graph`.
- No backend change. `backend/tests` must stay green: from `backend/`, `..\.venv\Scripts\python.exe -m pytest -q`.
- Commit messages: conventional-commit style, **no AI attribution / no `Co-Authored-By` line** (repo convention; clean-commits skill enforces this).
- Reuse existing CSS primitives/tokens in `frontend/src/styles.css`: `--surface`, `--line`, `--accent`, `--muted`, `--radius`, `--shadow`, `--font-mono`, `--slate-soft`, `.card`, `.panel`, `.btn`, `.btn-primary`, `.btn-small`.
- Keep the app's monospace/graph-paper aesthetic (IBM Plex Mono for graph labels).
- The `/api/graph` payload: `{ nodes: [{id:int, name, category, tags:[], status}], edges: [{id:int, source:int, target:int, type}] }`. `type` ∈ `depends_on|extends|used_with|replaces`.

---

## File Structure

**Modified:**
- `frontend/package.json` — add `cytoscape-fcose` dependency.
- `frontend/src/graph/cyStyles.js` — export tuned fcose layout config; node label chips + wrap; edge labels off by default + `.show-label` rule; `data(size)` sizing; hover/selected/faded styles.
- `frontend/src/pages/GraphView.jsx` — register fcose; build elements with per-node `size` (degree); run layout + fit on element changes; canvas control cluster; sidebar search-to-focus; hover preview + click-to-pin (revealing neighborhood edge labels); loading/empty states; legend note.
- `frontend/src/styles.css` — `.graph-controls`, `.graph-search`, `.graph-legend-note`, `.graph-state` (loading/empty overlays); keep responsive `@media (max-width: 980px)` behavior.

Each task ends with a green `npm run build` and a Playwright smoke observation. Commit after each task.

---

## Task 1: fcose layout engine + fit-by-default

**Files:**
- Modify: `frontend/package.json` (add dependency)
- Modify: `frontend/src/graph/cyStyles.js` (add `GRAPH_LAYOUT` export)
- Modify: `frontend/src/pages/GraphView.jsx` (register fcose, use layout, fit)

**Interfaces:**
- Produces: `GRAPH_LAYOUT` (object) — the fcose layout options, imported by `GraphView.jsx` for both initial render and the "re-spread" control (Task 5).

- [ ] **Step 1: Install the dependency**

Run from repo root:
```bash
cd frontend && npm install cytoscape-fcose && cd ..
```
Expected: `cytoscape-fcose` added to `frontend/package.json` `dependencies` and `package-lock.json` updated. Verify:
```bash
grep cytoscape-fcose frontend/package.json
```
Expected: a line like `"cytoscape-fcose": "^2.2.0"`.

- [ ] **Step 2: Add the tuned layout config to `cyStyles.js`**

Append to `frontend/src/graph/cyStyles.js`:
```js
export const GRAPH_LAYOUT = {
  name: 'fcose',
  quality: 'proof',
  randomize: true,
  animate: true,
  animationDuration: 450,
  fit: true,
  padding: 45,
  nodeRepulsion: 9000,
  idealEdgeLength: 130,
  nodeSeparation: 90,
  packComponents: true,
  gravity: 0.25,
}
```

- [ ] **Step 3: Register fcose and use the layout in `GraphView.jsx`**

At the top of `frontend/src/pages/GraphView.jsx`, add the import and one-time registration (module scope, above the component):
```js
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { buildStylesheet, GRAPH_LAYOUT, CATEGORY_PALETTE, EDGE_COLORS, RELATIONSHIP_TYPES, UNCATEGORIZED_COLOR } from '../graph/cyStyles'

cytoscape.use(fcose)
```
(Registering more than once throws; keep this at module scope so it runs once.)

In the cytoscape init inside the render effect, replace the `layout` option:
```js
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: buildStylesheet(),
      layout: GRAPH_LAYOUT,
      wheelSensitivity: 0.3,
    })
```

- [ ] **Step 4: Build**

Run:
```bash
cd frontend && npm run build && cd ..
```
Expected: build succeeds, no unresolved-import errors for `cytoscape-fcose`.

- [ ] **Step 5: Smoke test the spread**

Start the demo server (`PORT=5100 .venv\Scripts\python.exe backend\app.py`), open `/graph` as `admin`, screenshot. Expected: nodes spread across the whole canvas and centered/fit (not clumped in one corner); the disconnected `elcam-regulatory-docs` node placed cleanly rather than isolated in dead space.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/graph/cyStyles.js frontend/src/pages/GraphView.jsx
git commit -m "feat: force-directed fcose graph layout, spread and fit by default"
```

---

## Task 2: Label clarity — name chips + edge labels on demand

**Files:**
- Modify: `frontend/src/graph/cyStyles.js` (node + edge label styles, `.show-label`)
- Modify: `frontend/src/pages/GraphView.jsx` (reveal neighborhood edge labels on select)

**Interfaces:**
- Produces: CSS class contract `edge.show-label` (renders the edge `type` text) consumed by the selection handler in Task 4. In Task 2 the selection handler already exists (current code), so wire it here.

- [ ] **Step 1: Rewrite the `node` and `edge` style rules in `buildStylesheet()`**

In `frontend/src/graph/cyStyles.js`, replace the `node` base rule and the `edge` base rule, and add a `.show-label` edge rule. Node names get a rounded white chip and wrap; edge type text is empty by default and only appears with `.show-label`:
```js
    {
      selector: 'node',
      style: {
        'background-color': 'data(color)',
        label: 'data(name)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 11,
        'text-valign': 'bottom',
        'text-margin-y': 6,
        'text-wrap': 'wrap',
        'text-max-width': '104px',
        color: '#14232b',
        'text-background-color': '#ffffff',
        'text-background-opacity': 0.85,
        'text-background-padding': 3,
        'text-background-shape': 'roundrectangle',
        width: 34,
        height: 34,
        'border-width': 2,
        'border-color': '#ffffff',
      },
    },
```
```js
    {
      selector: 'edge',
      style: {
        width: 2,
        'line-color': 'data(color)',
        'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.1,
        'curve-style': 'bezier',
        label: '',
        color: 'data(color)',
      },
    },
    {
      selector: 'edge.show-label',
      style: {
        label: 'data(type)',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 9,
        'text-rotation': 'autorotate',
        'text-background-color': '#f2f5f4',
        'text-background-opacity': 0.95,
        'text-background-padding': 2,
      },
    },
```
Keep the existing `node[status = "deprecated"]`, `node:selected`, and `.faded` rules as they are.

- [ ] **Step 2: Reveal neighborhood edge labels on node tap in `GraphView.jsx`**

In the existing `cy.on('tap', 'node', …)` handler, add the `show-label` toggle; in the background-tap reset, clear it:
```js
    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      setSelected(node.data())
      cy.elements().addClass('faded')
      const hood = node.closedNeighborhood()
      hood.removeClass('faded')
      hood.edges().addClass('show-label')
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelected(null)
        cy.elements().removeClass('faded')
        cy.edges().removeClass('show-label')
      }
    })
```

- [ ] **Step 3: Build**

```bash
cd frontend && npm run build && cd ..
```
Expected: build succeeds.

- [ ] **Step 4: Smoke test**

Reload `/graph`. Expected: node names sit on white chips and no longer overlap each other; **no** edge type text is visible by default. Click a node → only that node's incident edges show their type text; other nodes fade.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/graph/cyStyles.js frontend/src/pages/GraphView.jsx
git commit -m "feat: readable graph labels — name chips, wrap, edge labels only on selection"
```

---

## Task 3: Node sizing by connectivity

**Files:**
- Modify: `frontend/src/pages/GraphView.jsx` (compute degree → `size` on node data)
- Modify: `frontend/src/graph/cyStyles.js` (drive width/height from `data(size)`)

**Interfaces:**
- Consumes: visible nodes/edges built in the render effect.
- Produces: each node element carries `data.size` (number, px). cyStyles `node` rule reads `data(size)` for `width`/`height`.

- [ ] **Step 1: Compute degree and set `size` when building node elements**

In `GraphView.jsx`, inside the render effect, before mapping nodes, compute degree over the **visible** edges, then set `size` on each node (clamp so hubs don't explode). Replace the node-mapping block:
```js
    const visibleEdges = graph.edges.filter(
      (e) => !hiddenTypes.has(e.type) && visibleIds.has(e.source) && visibleIds.has(e.target),
    )
    const degree = {}
    visibleEdges.forEach((e) => {
      degree[e.source] = (degree[e.source] || 0) + 1
      degree[e.target] = (degree[e.target] || 0) + 1
    })

    const elements = [
      ...visibleNodes.map((n) => ({
        data: {
          id: String(n.id),
          name: n.name,
          status: n.status,
          category: n.category,
          color: colorFor(n.category),
          size: 30 + Math.min(degree[n.id] || 0, 6) * 4.5,
        },
      })),
      ...visibleEdges.map((e) => ({
        data: {
          id: `e${e.id}`,
          source: String(e.source),
          target: String(e.target),
          type: e.type,
          color: EDGE_COLORS[e.type],
        },
      })),
    ]
```
(This also removes the now-duplicate inline `graph.edges.filter(...)` — `visibleEdges` is the single source of truth.)

- [ ] **Step 2: Drive node size from `data(size)` in `cyStyles.js`**

In the `node` rule, change the fixed size to data-driven:
```js
        width: 'data(size)',
        height: 'data(size)',
```
(Replaces `width: 34, height: 34`.)

- [ ] **Step 3: Build + smoke**

```bash
cd frontend && npm run build && cd ..
```
Reload `/graph`. Expected: well-connected skills (e.g. `Document Summarizer`) render as larger discs than leaf skills; the isolated node renders at the smallest size.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/GraphView.jsx frontend/src/graph/cyStyles.js
git commit -m "feat: size graph nodes by connectivity so hubs stand out"
```

---

## Task 4: Hover preview + click-to-pin

**Files:**
- Modify: `frontend/src/pages/GraphView.jsx` (hover/mouseout handlers, pinned ref, pointer cursor, card shows hover-or-pinned)

**Interfaces:**
- Consumes: the `selected` state + tap handlers from Tasks 1–2.
- Produces: card renders for `pinned ?? hovered`; "Open skill" navigates to whichever is shown. Hover never clobbers a pinned selection.

- [ ] **Step 1: Add hover state and a pinned ref, and update handlers**

Add near the other hooks in `GraphView.jsx`:
```js
  const [hovered, setHovered] = useState(null)
  const pinnedRef = useRef(false)
```
In the render effect, after creating `cy`, add hover handlers and keep the tap handlers (from Task 2) but track pinned:
```js
    cy.on('mouseover', 'node', (evt) => {
      if (!pinnedRef.current) setHovered(evt.target.data())
      containerRef.current.style.cursor = 'pointer'
    })
    cy.on('mouseout', 'node', () => {
      if (!pinnedRef.current) setHovered(null)
      containerRef.current.style.cursor = 'default'
    })
    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      pinnedRef.current = true
      setSelected(node.data())
      setHovered(null)
      cy.elements().addClass('faded')
      const hood = node.closedNeighborhood()
      hood.removeClass('faded')
      hood.edges().addClass('show-label')
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        pinnedRef.current = false
        setSelected(null)
        setHovered(null)
        cy.elements().removeClass('faded')
        cy.edges().removeClass('show-label')
      }
    })
```
Reset `pinnedRef` in the effect body when rebuilding (filters change) so a stale pin doesn't block hover after a re-render — set `pinnedRef.current = false` right before `const cy = cytoscape({...})`.

- [ ] **Step 2: Render the card from hover-or-pinned**

Replace the hovercard block. Use `const card = selected || hovered`:
```js
        <div className="card graph-canvas">
          <div ref={containerRef} />
          {(selected || hovered) && (() => {
            const card = selected || hovered
            return (
              <div className="graph-hovercard">
                <h4>{card.name}</h4>
                <div className="cell-muted" style={{ marginBottom: 8 }}>
                  {card.category || 'uncategorized'} <StatusBadge status={card.status} />
                </div>
                {selected && (
                  <button
                    className="btn btn-primary btn-small"
                    onClick={() => navigate(`/skills/${selected.id}`)}
                  >
                    Open skill
                  </button>
                )}
              </div>
            )
          })()}
        </div>
```
(The "Open skill" button shows only when a node is pinned via click — hovering just previews.)

- [ ] **Step 3: Build + smoke**

```bash
cd frontend && npm run build && cd ..
```
Reload `/graph`. Expected: hovering a node shows its info card (no button) and a pointer cursor; clicking pins it (card gains "Open skill", neighbors highlight, incident edge labels appear); clicking the background resets and re-enables hover.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/GraphView.jsx
git commit -m "feat: graph node hover preview and click-to-pin"
```

---

## Task 5: Canvas controls — zoom / fit / re-spread

**Files:**
- Modify: `frontend/src/pages/GraphView.jsx` (cy ref, control cluster + handlers)
- Modify: `frontend/src/styles.css` (`.graph-controls`)

**Interfaces:**
- Consumes: `GRAPH_LAYOUT` (Task 1) for re-spread.
- Produces: a `cyRef` holding the live Cytoscape instance so button handlers can call methods on it.

- [ ] **Step 1: Hold the cy instance in a ref**

Add `const cyRef = useRef(null)` with the other hooks. In the render effect, after `const cy = cytoscape({...})`, set `cyRef.current = cy`; in the cleanup, also null it:
```js
    cyRef.current = cy
    return () => {
      cy.destroy()
      cyRef.current = null
    }
```

- [ ] **Step 2: Add control handlers**

Add these helpers in the component body (guard against a null instance / empty graph):
```js
  const zoomBy = (factor) => {
    const cy = cyRef.current
    if (!cy) return
    cy.animate(
      { zoom: cy.zoom() * factor, center: { eles: cy.elements() } },
      { duration: 150 },
    )
  }
  const fitView = () => cyRef.current && cyRef.current.fit(undefined, 45)
  const respread = () => {
    const cy = cyRef.current
    if (!cy || cy.elements().length === 0) return
    cy.layout(GRAPH_LAYOUT).run()
  }
```

- [ ] **Step 3: Render the control cluster inside `.graph-canvas`**

Add just inside `<div className="card graph-canvas">`, before the container div:
```jsx
          <div className="graph-controls">
            <button className="btn btn-small" title="Zoom in" onClick={() => zoomBy(1.3)}>＋</button>
            <button className="btn btn-small" title="Zoom out" onClick={() => zoomBy(1 / 1.3)}>−</button>
            <button className="btn btn-small" title="Fit to view" onClick={fitView}>⤢</button>
            <button className="btn btn-small" title="Re-spread layout" onClick={respread}>↻</button>
          </div>
```

- [ ] **Step 4: Style the cluster in `styles.css`**

Add in the graph section:
```css
.graph-controls {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.graph-controls .btn {
  width: 34px;
  height: 34px;
  padding: 0;
  font-size: 15px;
  line-height: 1;
  background: var(--surface);
  box-shadow: var(--shadow);
}
```

- [ ] **Step 5: Build + smoke**

```bash
cd frontend && npm run build && cd ..
```
Reload `/graph`. Expected: four stacked buttons top-right of the canvas; `＋`/`−` zoom about the center, `⤢` fits all nodes, `↻` re-runs the spread animation. No console errors when clicking with the graph loaded.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/GraphView.jsx frontend/src/styles.css
git commit -m "feat: graph canvas controls (zoom, fit, re-spread)"
```

---

## Task 6: Search-to-focus

**Files:**
- Modify: `frontend/src/pages/GraphView.jsx` (search input + focus logic)
- Modify: `frontend/src/styles.css` (`.graph-search`)

**Interfaces:**
- Consumes: `cyRef` (Task 5), the tap/highlight logic (Task 4), `graph.nodes`.
- Produces: `focusNode(id)` — centers, pins, and highlights a node's neighborhood programmatically (mirrors a click).

- [ ] **Step 1: Add a `focusNode` helper**

In the component body:
```js
  const focusNode = (id) => {
    const cy = cyRef.current
    if (!cy) return
    const node = cy.getElementById(String(id))
    if (node.empty()) return
    pinnedRef.current = true
    setSelected(node.data())
    setHovered(null)
    cy.elements().addClass('faded')
    const hood = node.closedNeighborhood()
    hood.removeClass('faded')
    hood.edges().addClass('show-label')
    cy.animate({ center: { eles: node }, zoom: 1.4 }, { duration: 200 })
  }
```

- [ ] **Step 2: Add the search input to the sidebar**

Add a new section in the sidebar, above the `<h3>Tag</h3>` block. It uses a datalist of visible skill names and resolves the typed/selected name to an id:
```jsx
          <h3>Find a skill</h3>
          <input
            className="graph-search"
            list="graph-node-names"
            placeholder="Search by name…"
            onChange={(e) => {
              const match = (graph?.nodes || []).find((n) => n.name === e.target.value)
              if (match) focusNode(match.id)
            }}
          />
          <datalist id="graph-node-names">
            {(graph?.nodes || []).map((n) => (
              <option key={n.id} value={n.name} />
            ))}
          </datalist>
```

- [ ] **Step 3: Style the search input**

Add to `styles.css`:
```css
.graph-search {
  width: 100%;
  margin-bottom: 4px;
}
```
(Inherits the app's existing `input` styling; only spacing is added.)

- [ ] **Step 4: Build + smoke**

```bash
cd frontend && npm run build && cd ..
```
Reload `/graph`. Expected: typing/selecting a skill name in "Find a skill" centers and zooms to that node, pins it (neighbors highlighted, edge labels shown). A non-matching string does nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/GraphView.jsx frontend/src/styles.css
git commit -m "feat: search-to-focus a skill in the graph"
```

---

## Task 7: Loading & empty states + legend note

**Files:**
- Modify: `frontend/src/pages/GraphView.jsx` (loading + empty overlays, legend note)
- Modify: `frontend/src/styles.css` (`.graph-state`, `.graph-legend-note`)

**Interfaces:**
- Consumes: `graph`, `error`, and the visible-node computation.
- Produces: `noneVisible` (bool) — true when the graph loaded but filters hide every node.

- [ ] **Step 1: Compute `noneVisible` and gate the render**

The render effect already returns early if `!graph`. Add a memo for whether anything is visible so the JSX can show an overlay. Near the other `useMemo`s:
```js
  const visibleCount = useMemo(() => {
    if (!graph) return 0
    return graph.nodes.filter(
      (n) => !hiddenCats.has(n.category || '') && (!tagFilter || (n.tags || []).includes(tagFilter)),
    ).length
  }, [graph, hiddenCats, tagFilter])
```

- [ ] **Step 2: Render loading / empty overlays inside `.graph-canvas`**

Add after the container `<div ref={containerRef} />`:
```jsx
          {!graph && !error && <div className="graph-state">Loading graph…</div>}
          {graph && visibleCount === 0 && (
            <div className="graph-state">No skills match these filters.</div>
          )}
```

- [ ] **Step 3: Add a compact legend note to the sidebar**

Add at the bottom of the sidebar, after the Tag section:
```jsx
          <h3>Legend</h3>
          <div className="graph-legend-note">
            Node color = category. Larger node = more connections.
            Octagon = deprecated. Arrows point from source to target;
            edge color = relationship type (see above). Click a node to
            focus its neighbors.
          </div>
```

- [ ] **Step 4: Style states + legend note**

Add to `styles.css`:
```css
.graph-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 13px;
  pointer-events: none;
}
.graph-legend-note {
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted);
}
```

- [ ] **Step 5: Build + smoke**

```bash
cd frontend && npm run build && cd ..
```
Reload `/graph`. Expected: the legend note appears in the sidebar. Unchecking every Category shows the "No skills match these filters." overlay over an empty canvas. (Loading state is brief; confirm no crash on first paint.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/GraphView.jsx frontend/src/styles.css
git commit -m "feat: graph loading/empty states and legend note"
```

---

## Task 8: Regression + final verification

**Files:** none (verification only)

- [ ] **Step 1: Backend regression**

From `backend/`:
```bash
..\.venv\Scripts\python.exe -m pytest -q
```
Expected: all tests pass (no backend change, so this is a guard).

- [ ] **Step 2: Full visual verification**

With the rebuilt frontend served on :5100, load `/graph` as `admin` and confirm the full acceptance set:
- Spread fills the canvas and is centered on load (no clumping in one corner).
- No node-label overlaps; names on white chips; long names wrap.
- No edge type text by default; it appears only for a clicked node's neighborhood.
- Hubs render larger than leaves; isolated node smallest and cleanly placed.
- Hover previews; click pins + shows "Open skill" and neighbor highlight.
- Controls: `＋`/`−` zoom, `⤢` fits, `↻` re-spreads.
- Search-to-focus centers + pins a chosen skill.
- Empty-filter overlay shows when all categories are unchecked.
- Screenshot the final graph as `graph-after.png` for the before/after record.

- [ ] **Step 3: Adversarial review of the diff**

Review the full working diff across dimensions (Cytoscape/fcose API correctness; React effect/ref lifecycle & cleanup; filter re-render correctness; accessibility of controls/search; no console errors). Fix any confirmed findings, rebuild, re-verify, and commit fixes.

## Self-Review (plan vs spec)

- **Spec coverage:** fcose + tuned params (T1) · fit-by-default (T1, `fit:true` + re-runs on element change via the existing effect deps) · label chips + wrap (T2) · edge labels on demand (T2, T4) · degree sizing (T3) · hover preview + click-to-pin (T4) · controls (T5) · search-to-focus (T6) · loading/empty states + legend (T7) · no-backend-change regression (T8). All spec sections map to a task.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code.
- **Type consistency:** `GRAPH_LAYOUT` (object) defined T1, reused T5/T6. `data.size` set T3, read by cyStyles T3. `edge.show-label` defined T2, applied T2/T4/T6. `pinnedRef`/`cyRef`/`hovered`/`focusNode` introduced before use (T4→T5→T6). `visibleEdges` replaces the duplicated inline filter in T3.
