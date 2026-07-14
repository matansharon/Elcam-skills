# Design: Skill Graph UX/UI Overhaul (spread + clarity)

**Date:** 2026-07-14
**Status:** Approved (design), pending implementation plan

## Problem

The Skill Graph (`frontend/src/pages/GraphView.jsx`, Cytoscape.js) renders the
skill dependency network, but reads poorly on load:

- The `cose` layout with `animate: false, padding: 40` packs every node into
  the upper-center-left of the canvas, never centers, and never fits-to-view.
  A large area of the canvas is empty while the connected cluster is cramped.
- Disconnected nodes (e.g. `elcam-regulatory-docs`) float alone in dead space.
- Node labels are long monospace names placed under 34px nodes with **no
  background**, so they collide with each other ("Meeting Prep Assistant" over
  "Legacy Email Classifier"; "Stability Report Analyzer" over "Document
  Summarizer").
- Every edge always shows its type text (`depends_on`, `used_with`, …), which
  overlaps node labels and compounds the clutter.
- There are no zoom / fit / re-layout controls, no way to jump to a skill, no
  hover affordance, and no loading or empty states.

The goal: the graph should be **clear and well-spread by default** — readable
the instant the page loads, with no interaction required — and pleasant to
explore.

## Goals

- **Spread by default:** nodes fill the canvas evenly, no overlaps, centered
  and fit-to-viewport on every render (initial load and filter changes).
- **Readable labels:** names never collide; edge type text never clutters the
  default view.
- **Explorable:** zoom/fit/re-spread controls, search-to-focus, hover preview,
  and structure that reads at a glance (hubs larger).
- **Graceful states:** loading and empty (filtered-to-nothing) states.
- No backend change — `/api/graph` already returns `{id, name, category,
  tags, status}` nodes and `{id, source, target, type}` edges.

## Non-goals

- Changing the graph data model, the `/api/graph` payload, or RBAC/visibility
  rules.
- Replacing Cytoscape with another visualization library.
- Editing relationships from the graph (still done on the skill detail page).
- Persisting layout positions between sessions.

## Chosen approach

**Force-directed `fcose` layout, fit-by-default, decluttered labels, and an
interactive control layer — all in the existing three frontend files.**

### 1. Layout engine → `cytoscape-fcose`

Add the `cytoscape-fcose` dependency and register it once with
`cytoscape.use(fcose)`. fcose gives far better spread than `cose`, avoids node
overlap, and packs disconnected components neatly. Tuned params:

- `name: 'fcose'`, `quality: 'proof'`, `randomize: true`
- `nodeRepulsion: ~9000`, `idealEdgeLength: ~130`, `nodeSeparation: ~90`
- `packComponents: true`, `padding: 40`
- `animate: true`, `animationDuration: ~400` (settle on load / re-spread)
- After layout `stop`, call `cy.fit(undefined, 40)` to center + fit.

### 2. Fit-by-default

Every time the element set changes (initial load and any category/type/tag
filter change) the layout re-runs and fits-to-viewport, so the graph is always
spread and centered without interaction. This is the core of "spread by
default."

### 3. Label de-cluttering (`cyStyles.js`)

- Node labels: rounded **background chip** (`text-background-*`) + padding so
  names read over edges; **wrap** long names (`text-wrap: 'wrap'`,
  `text-max-width: ~100px`) instead of letting them collide.
- **Edge type labels hidden by default.** They render only for edges in the
  highlighted neighborhood (node hover/selection) via a `.show-label` class.
  Type is otherwise conveyed by edge **color + sidebar legend**.
- Keep the octagon = deprecated convention and the white node border.

### 4. Node sizing by connectivity

Compute each node's degree in JS, store it on node `data`, and map size to a
`~30–58px` range so hubs render larger and the network structure reads at a
glance.

### 5. Interactive controls

A small control cluster overlaid at the top-right of the canvas:
`＋` (zoom in), `−` (zoom out), `⤢` (fit), `↻` (re-spread / re-run layout).

### 6. Search-to-focus

A search input in the sidebar (with a datalist of skill names). Selecting /
entering a name centers and selects that node and highlights its neighborhood
(same effect as clicking it). No match → no-op.

### 7. Hover preview + click-to-pin

- `mouseover` a node → show the info card (name, category, status) as a
  lightweight preview; `mouseout` clears it unless a node is pinned.
- `tap` (click) a node → pin it: highlight the closed neighborhood, fade the
  rest, **reveal the neighborhood's edge labels**, and show the "Open skill"
  action. Click background → reset.
- Nodes show a pointer cursor.

### 8. Legend polish

Sidebar keeps category color swatches and relationship-type chips, plus a
compact note explaining node shape (octagon = deprecated), node size
(= connectivity), and edge arrow direction.

### 9. Loading & empty states

- `graph == null && !error` → "Loading graph…" state in the canvas.
- Zero visible nodes after filters → "No skills match these filters" overlay.

## Components / files touched

- `frontend/package.json` — add `cytoscape-fcose`.
- `frontend/src/graph/cyStyles.js` — label chips + wrap, `.show-label` edge
  rule, degree→size mapping, hover/selected/faded styles; export the tuned
  `fcose` layout config (or a factory).
- `frontend/src/pages/GraphView.jsx` — register fcose; build elements with
  degree; run layout + fit on change; controls; search; hover/click handlers;
  loading/empty states.
- `frontend/src/styles.css` — `.graph-*` additions: control cluster, search
  box, legend note, loading/empty overlays; keep responsive (`max-width: 980px`)
  behavior.

## Error handling & edge cases

- Fetch error → existing red banner (unchanged).
- Empty graph or all-filtered → empty overlay, controls still safe (no throw
  on `cy.fit()` with zero elements).
- Disconnected components → handled by `packComponents`.
- Re-layout must not fight React re-renders: create/destroy the `cy` instance
  in the effect cleanup as today; controls call methods on the live instance
  via a ref.
- Single-node / self-referential filters → layout + fit degrade gracefully.

## Testing / verification

- No backend change, so `backend/tests` stay green (run `pytest` as a
  regression guard).
- No frontend unit tests exist; verification is visual via Playwright:
  rebuild, load `/graph` as `admin`, screenshot "after" and compare to the
  captured "before". Confirm: spread fills the canvas, zero label overlap,
  edge labels appear only on hover/selection, controls (zoom/fit/re-spread)
  work, search focuses a node, hover preview + click-to-pin work, hubs render
  larger, disconnected node placed cleanly, loading + empty states render.
- Adversarial review pass over the diff (correctness / Cytoscape API / UX /
  accessibility) before commit.
