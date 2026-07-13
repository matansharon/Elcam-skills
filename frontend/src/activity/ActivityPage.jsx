import { useEffect, useState } from 'react'
import { activityApi } from './activityApi'
import ActivityLogin from './ActivityLogin'
import ActivityPanel from './ActivityPanel'

export default function ActivityPage() {
  const [authed, setAuthed] = useState(null) // null = still checking

  useEffect(() => {
    activityApi
      .get('/api/activity/session')
      .then((d) => setAuthed(!!d.authenticated))
      .catch(() => setAuthed(false))
  }, [])

  if (authed === null) return <div className="page-loading">Loading…</div>
  if (!authed) return <ActivityLogin onSuccess={() => setAuthed(true)} />
  return <ActivityPanel onLogout={() => setAuthed(false)} />
}
