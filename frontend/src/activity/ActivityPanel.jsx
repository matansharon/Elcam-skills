import { useCallback, useEffect, useRef, useState } from 'react'
import { activityApi } from './activityApi'
import ActivityStats from './ActivityStats'

const EMPTY_FILTERS = { actor: '', category: '', method: '', status: '', q: '' }
const PAGE_SIZE = 50

function buildQuery({ view, page, filters }) {
  const params = new URLSearchParams({ view, page: String(page), page_size: String(PAGE_SIZE) })
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v)
  })
  return params.toString()
}

export default function ActivityPanel({ onLogout }) {
  const [view, setView] = useState('raw')
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE })
  const [error, setError] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)
  const timerRef = useRef(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const q = buildQuery({ view, page, filters })
      setData(await activityApi.get(`/api/activity/logs?${q}`))
    } catch (err) {
      setError(err.message)
    }
  }, [view, page, filters])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!autoRefresh) return undefined
    timerRef.current = setInterval(() => {
      load()
      setRefreshTick((t) => t + 1)
    }, 5000)
    return () => clearInterval(timerRef.current)
  }, [autoRefresh, load])

  const setFilter = (key) => (e) => {
    setPage(1)
    setFilters((f) => ({ ...f, [key]: e.target.value }))
  }

  const signOut = async () => {
    try {
      await activityApi.post('/api/activity/logout')
    } catch {
      /* already gone */
    }
    onLogout()
  }

  const exportCsv = () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v)
    })
    if (view) params.set('view', view)
    const qs = params.toString()
    const a = document.createElement('a')
    a.href = `/api/activity/export.csv${qs ? `?${qs}` : ''}`
    a.download = 'activity-log.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  const clearLog = async () => {
    if (!window.confirm('Permanently delete all recorded activity? This cannot be undone.')) return
    setError(null)
    try {
      await activityApi.post('/api/activity/clear')
      setRefreshTick((t) => t + 1)
      if (page === 1) {
        await load()
      } else {
        setPage(1)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))

  return (
    <div className="activity-shell">
      <div className="page-header">
        <div>
          <h1>Activity</h1>
          <div className="subtitle">All operations across the app.</div>
        </div>
        <button className="btn btn-ghost" onClick={signOut}>
          Sign out
        </button>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <ActivityStats filters={filters} refreshKey={`${view}-${page}-${refreshTick}`} />

      <div className="card panel">
        <div className="activity-toolbar">
          <div className="activity-toggle">
            <button
              className={`btn btn-small ${view === 'raw' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setView('raw'); setPage(1) }}
            >
              Raw
            </button>
            <button
              className={`btn btn-small ${view === 'readable' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setView('readable'); setPage(1) }}
            >
              Readable
            </button>
            <label className="activity-auto">
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
              Auto-refresh
            </label>
            <button className="btn btn-small btn-ghost" onClick={exportCsv}>Export CSV</button>
            <button className="btn btn-small btn-danger" onClick={clearLog}>Clear log</button>
          </div>
          <div className="activity-filters">
            <input placeholder="Search path/summary" value={filters.q} onChange={setFilter('q')} />
            <input placeholder="Actor" value={filters.actor} onChange={setFilter('actor')} />
            <select value={filters.category} onChange={setFilter('category')}>
              <option value="">All categories</option>
              <option value="auth">auth</option>
              <option value="skill">skill</option>
              <option value="permission">permission</option>
              <option value="relationship">relationship</option>
              <option value="admin">admin</option>
            </select>
            <select value={filters.method} onChange={setFilter('method')}>
              <option value="">All methods</option>
              <option>GET</option>
              <option>POST</option>
              <option>PUT</option>
              <option>DELETE</option>
            </select>
            <input placeholder="Status" value={filters.status} onChange={setFilter('status')} />
          </div>
        </div>

        <div className="table-wrap">
          <table className="data">
            <thead>
              {view === 'raw' ? (
                <tr>
                  <th>Time</th><th>Actor</th><th>Method</th><th>Path</th><th>Status</th><th>ms</th>
                </tr>
              ) : (
                <tr>
                  <th>Time</th><th>Actor</th><th>Category</th><th>Summary</th>
                </tr>
              )}
            </thead>
            <tbody>
              {data.items.map((r) =>
                view === 'raw' ? (
                  <tr key={r.id}>
                    <td className="cell-muted">{new Date(r.timestamp).toLocaleString()}</td>
                    <td>{r.actor}</td>
                    <td><span className="badge">{r.method}</span></td>
                    <td className="mono">{r.path}</td>
                    <td>{r.status_code}</td>
                    <td className="cell-muted">{r.duration_ms}</td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <td className="cell-muted">{new Date(r.timestamp).toLocaleString()}</td>
                    <td>{r.actor}</td>
                    <td>{r.category && <span className="badge badge-perm">{r.category}</span>}</td>
                    <td>{r.summary}</td>
                  </tr>
                )
              )}
              {data.items.length === 0 && (
                <tr><td colSpan={view === 'raw' ? 6 : 4} className="cell-muted">No activity.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="activity-pager">
          <button className="btn btn-small btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Prev
          </button>
          <span className="cell-muted">Page {data.page} of {totalPages} · {data.total} events</span>
          <button className="btn btn-small btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
