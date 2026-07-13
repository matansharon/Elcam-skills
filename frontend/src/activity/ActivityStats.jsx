import { useEffect, useState } from 'react'
import { activityApi } from './activityApi'

function statsQuery(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v)
  })
  return params.toString()
}

function TimelineChart({ timeline }) {
  if (!timeline || timeline.length === 0) return <div className="cell-muted">No data yet.</div>
  const max = Math.max(...timeline.map((t) => t.count), 1)
  const barW = 22
  const gap = 8
  const height = 90
  const width = timeline.length * (barW + gap)
  return (
    <svg className="activity-chart" viewBox={`0 0 ${width} ${height + 20}`} width="100%" height={height + 20}>
      {timeline.map((t, i) => {
        const h = Math.round((t.count / max) * height)
        const x = i * (barW + gap)
        return (
          <g key={t.bucket}>
            <rect x={x} y={height - h} width={barW} height={h} rx="3" className="activity-bar" />
            <text x={x + barW / 2} y={height + 14} textAnchor="middle" className="activity-bar-label">
              {t.bucket.slice(5)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function ActivityStats({ filters, refreshKey }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    activityApi
      .get(`/api/activity/stats?${statsQuery(filters)}`)
      .then(setStats)
      .catch(() => setStats(null))
  }, [filters, refreshKey])

  if (!stats) return null
  const topCategory = [...stats.by_category].sort((a, b) => b.count - a.count)[0]

  return (
    <div className="activity-stats">
      <div className="stat-cards">
        <div className="card stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total events</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{stats.active_users}</div>
          <div className="stat-label">Active actors</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{topCategory ? topCategory.category : '—'}</div>
          <div className="stat-label">Top category</div>
        </div>
      </div>
      <div className="card panel">
        <h3 style={{ fontSize: 14, marginTop: 0 }}>Activity over time</h3>
        <TimelineChart timeline={stats.timeline} />
      </div>
    </div>
  )
}
