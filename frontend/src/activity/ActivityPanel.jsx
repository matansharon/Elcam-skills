import { activityApi } from './activityApi'

export default function ActivityPanel({ onLogout }) {
  const signOut = async () => {
    try {
      await activityApi.post('/api/activity/logout')
    } catch {
      // already signed out
    }
    onLogout()
  }

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
      <div className="card panel">Panel coming online…</div>
    </div>
  )
}
