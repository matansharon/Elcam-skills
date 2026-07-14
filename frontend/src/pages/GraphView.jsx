import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import {
  buildStylesheet,
  GRAPH_LAYOUT,
  CATEGORY_PALETTE,
  EDGE_COLORS,
  RELATIONSHIP_TYPES,
  UNCATEGORIZED_COLOR,
} from '../graph/cyStyles'

cytoscape.use(fcose)

export default function GraphView() {
  const navigate = useNavigate()
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const pinnedRef = useRef(false)
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)
  const [hiddenCats, setHiddenCats] = useState(new Set())
  const [hiddenTypes, setHiddenTypes] = useState(new Set())
  const [tagFilter, setTagFilter] = useState('')

  useEffect(() => {
    api.get('/api/graph').then(setGraph).catch((e) => setError(e.message))
  }, [])

  const categories = useMemo(
    () =>
      [...new Set((graph?.nodes || []).map((n) => n.category).filter(Boolean))].sort(),
    [graph],
  )
  const tags = useMemo(
    () => [...new Set((graph?.nodes || []).flatMap((n) => n.tags || []))].sort(),
    [graph],
  )

  const colorFor = (category) => {
    const idx = categories.indexOf(category)
    return idx === -1 ? UNCATEGORIZED_COLOR : CATEGORY_PALETTE[idx % CATEGORY_PALETTE.length]
  }

  const visibleNodeList = useMemo(() => {
    if (!graph) return []
    return graph.nodes.filter(
      (n) =>
        !hiddenCats.has(n.category || '') &&
        (!tagFilter || (n.tags || []).includes(tagFilter)),
    )
  }, [graph, hiddenCats, tagFilter])
  const visibleCount = visibleNodeList.length

  useEffect(() => {
    if (!graph || !containerRef.current) return

    const visibleNodes = graph.nodes.filter(
      (n) =>
        !hiddenCats.has(n.category || '') &&
        (!tagFilter || (n.tags || []).includes(tagFilter)),
    )
    const visibleIds = new Set(visibleNodes.map((n) => n.id))

    const visibleEdges = graph.edges.filter(
      (e) =>
        !hiddenTypes.has(e.type) &&
        visibleIds.has(e.source) &&
        visibleIds.has(e.target),
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

    // Fresh render: drop any stale pin/preview so hover works again.
    pinnedRef.current = false
    setSelected(null)
    setHovered(null)

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: buildStylesheet(),
      layout: GRAPH_LAYOUT,
      wheelSensitivity: 0.3,
    })
    cyRef.current = cy

    const highlightNeighborhood = (node) => {
      cy.edges().removeClass('show-label')
      cy.elements().addClass('faded')
      const hood = node.closedNeighborhood()
      hood.removeClass('faded')
      hood.edges().addClass('show-label')
    }
    const resetHighlight = () => {
      cy.elements().removeClass('faded')
      cy.edges().removeClass('show-label')
    }

    cy.on('mouseover', 'node', (evt) => {
      if (!pinnedRef.current) setHovered(evt.target.data())
      if (containerRef.current) containerRef.current.style.cursor = 'pointer'
    })
    cy.on('mouseout', 'node', () => {
      if (!pinnedRef.current) setHovered(null)
      if (containerRef.current) containerRef.current.style.cursor = 'default'
    })
    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      pinnedRef.current = true
      setSelected(node.data())
      setHovered(null)
      highlightNeighborhood(node)
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        pinnedRef.current = false
        setSelected(null)
        setHovered(null)
        resetHighlight()
      }
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, hiddenCats, hiddenTypes, tagFilter])

  const toggle = (set, setter) => (value) => {
    const next = new Set(set)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    setter(next)
  }
  const toggleCat = toggle(hiddenCats, setHiddenCats)
  const toggleType = toggle(hiddenTypes, setHiddenTypes)

  const zoomBy = (factor) => {
    const cy = cyRef.current
    if (!cy) return
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    })
  }
  const fitView = () => cyRef.current && cyRef.current.fit(undefined, 45)
  const respread = () => {
    const cy = cyRef.current
    if (!cy || cy.elements().length === 0) return
    cy.elements().removeClass('faded')
    cy.edges().removeClass('show-label')
    pinnedRef.current = false
    setSelected(null)
    setHovered(null)
    cy.layout(GRAPH_LAYOUT).run()
  }

  const focusNode = (id) => {
    const cy = cyRef.current
    if (!cy) return
    const node = cy.getElementById(String(id))
    if (node.empty()) return
    pinnedRef.current = true
    setSelected(node.data())
    setHovered(null)
    cy.edges().removeClass('show-label')
    cy.elements().addClass('faded')
    const hood = node.closedNeighborhood()
    hood.removeClass('faded')
    hood.edges().addClass('show-label')
    cy.animate({ center: { eles: node }, zoom: 1.4 }, { duration: 200 })
  }

  const card = selected || hovered

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Skill Graph</h1>
          <div className="subtitle">
            Hover to preview a skill; click a node to focus its neighbors. Click the
            background to reset.
          </div>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="graph-layout">
        <div className="card panel graph-sidebar">
          <h3>Find a skill</h3>
          <input
            className="graph-search"
            aria-label="Search skills by name"
            list="graph-node-names"
            placeholder="Search by name…"
            onChange={(e) => {
              const match = visibleNodeList.find((n) => n.name === e.target.value)
              if (match) focusNode(match.id)
            }}
          />
          <datalist id="graph-node-names">
            {visibleNodeList.map((n) => (
              <option key={n.id} value={n.name} />
            ))}
          </datalist>

          <h3>Categories</h3>
          {categories.map((c) => (
            <label className="check" key={c}>
              <input
                type="checkbox"
                checked={!hiddenCats.has(c)}
                onChange={() => toggleCat(c)}
              />
              <span
                style={{
                  width: 10,
                  height: 10,
                  background: colorFor(c),
                  display: 'inline-block',
                  borderRadius: 2,
                }}
              />
              {c}
            </label>
          ))}

          <h3>Relationships</h3>
          {RELATIONSHIP_TYPES.map((t) => (
            <label className="check" key={t}>
              <input
                type="checkbox"
                checked={!hiddenTypes.has(t)}
                onChange={() => toggleType(t)}
              />
              <span className={`rel-type rel-${t}`}>{t}</span>
            </label>
          ))}

          <h3>Tag</h3>
          <select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
            <option value="">All tags</option>
            {tags.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          <h3>Legend</h3>
          <div className="graph-legend-note">
            Node color = category. Larger node = more connections. Octagon =
            deprecated. Arrows point from source to target. Edge type = color +
            line style: <b>solid</b> depends_on, <b>dashed</b> extends,{' '}
            <b>dotted</b> used_with, <b>dash-dot</b> replaces. Click a node to
            focus its neighbors.
          </div>
        </div>

        <div className="card graph-canvas">
          <div className="graph-controls">
            <button
              className="btn btn-small"
              title="Zoom in"
              aria-label="Zoom in"
              onClick={() => zoomBy(1.3)}
            >
              ＋
            </button>
            <button
              className="btn btn-small"
              title="Zoom out"
              aria-label="Zoom out"
              onClick={() => zoomBy(1 / 1.3)}
            >
              −
            </button>
            <button
              className="btn btn-small"
              title="Fit to view"
              aria-label="Fit to view"
              onClick={fitView}
            >
              ⤢
            </button>
            <button
              className="btn btn-small"
              title="Re-spread layout"
              aria-label="Re-spread layout"
              onClick={respread}
            >
              ↻
            </button>
          </div>

          <div className="graph-cy" ref={containerRef} />

          {!graph && !error && <div className="graph-state">Loading graph…</div>}
          {graph && visibleCount === 0 && (
            <div className="graph-state">No skills match these filters.</div>
          )}

          {card && (
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
          )}
        </div>
      </div>
    </div>
  )
}
