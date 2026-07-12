import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import cytoscape from 'cytoscape'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import {
  buildStylesheet,
  CATEGORY_PALETTE,
  EDGE_COLORS,
  RELATIONSHIP_TYPES,
  UNCATEGORIZED_COLOR,
} from '../graph/cyStyles'

export default function GraphView() {
  const navigate = useNavigate()
  const containerRef = useRef(null)
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
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

  useEffect(() => {
    if (!graph || !containerRef.current) return

    const visibleNodes = graph.nodes.filter(
      (n) =>
        !hiddenCats.has(n.category || '') &&
        (!tagFilter || (n.tags || []).includes(tagFilter)),
    )
    const visibleIds = new Set(visibleNodes.map((n) => n.id))

    const elements = [
      ...visibleNodes.map((n) => ({
        data: {
          id: String(n.id),
          name: n.name,
          status: n.status,
          category: n.category,
          color: colorFor(n.category),
        },
      })),
      ...graph.edges
        .filter(
          (e) =>
            !hiddenTypes.has(e.type) &&
            visibleIds.has(e.source) &&
            visibleIds.has(e.target),
        )
        .map((e) => ({
          data: {
            id: `e${e.id}`,
            source: String(e.source),
            target: String(e.target),
            type: e.type,
            color: EDGE_COLORS[e.type],
          },
        })),
    ]

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: buildStylesheet(),
      layout: { name: 'cose', animate: false, padding: 40 },
      wheelSensitivity: 0.3,
    })

    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      setSelected(node.data())
      cy.elements().addClass('faded')
      node.closedNeighborhood().removeClass('faded')
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelected(null)
        cy.elements().removeClass('faded')
      }
    })

    return () => cy.destroy()
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

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Skill Graph</h1>
          <div className="subtitle">
            Click a node to highlight its direct neighbors. Click the background to reset.
          </div>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="graph-layout">
        <div className="card panel graph-sidebar">
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
        </div>

        <div className="card graph-canvas">
          <div ref={containerRef} />
          {selected && (
            <div className="graph-hovercard">
              <h4>{selected.name}</h4>
              <div className="cell-muted" style={{ marginBottom: 8 }}>
                {selected.category || 'uncategorized'}{' '}
                <StatusBadge status={selected.status} />
              </div>
              <button
                className="btn btn-primary btn-small"
                onClick={() => navigate(`/skills/${selected.id}`)}
              >
                Open skill
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
