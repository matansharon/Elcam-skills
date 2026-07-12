import { useEffect, useState } from 'react'
import { api } from '../api/client'

const LEVELS = [
  { value: null, label: 'None' },
  { value: 'read', label: 'Read' },
  { value: 'edit', label: 'Edit' },
]

export default function PermissionMatrix({ users, skills }) {
  const [userId, setUserId] = useState('')
  const [perms, setPerms] = useState({})
  const [error, setError] = useState(null)

  const selectedUser = users.find((u) => u.id === Number(userId))

  useEffect(() => {
    if (!userId) return
    setPerms({})
    api
      .get(`/api/users/${userId}/permissions`)
      .then((rows) => setPerms(Object.fromEntries(rows.map((r) => [r.skill_id, r.level]))))
      .catch((e) => setError(e.message))
  }, [userId])

  const setLevel = async (skillId, level) => {
    setError(null)
    try {
      await api.put(`/api/users/${userId}/permissions/${skillId}`, { level })
      setPerms((p) => {
        const next = { ...p }
        if (level) next[skillId] = level
        else delete next[skillId]
        return next
      })
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="card panel">
      <h2 style={{ fontSize: 17 }}>Per-skill permissions</h2>
      {error && <div className="banner banner-error">{error}</div>}
      <label className="field" style={{ maxWidth: 280 }}>
        User
        <select value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="">Choose a user…</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name} ({u.username})
            </option>
          ))}
        </select>
      </label>

      {selectedUser?.role === 'admin' && (
        <div className="cell-muted">
          Admins implicitly have full access to every skill — per-skill permissions do
          not apply.
        </div>
      )}

      {selectedUser && selectedUser.role !== 'admin' && (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Skill</th>
                <th>Access</th>
              </tr>
            </thead>
            <tbody>
              {skills.map((s) => {
                const isOwner = s.owner.id === selectedUser.id
                const current = isOwner ? 'edit' : perms[s.id] ?? null
                return (
                  <tr key={s.id}>
                    <td className="cell-name">{s.name}</td>
                    <td>
                      {isOwner ? (
                        <span className="badge badge-perm">owner — implicit edit</span>
                      ) : (
                        <span className="perm-radio">
                          {LEVELS.map((l) => (
                            <button
                              key={l.label}
                              className={current === l.value ? 'on' : ''}
                              onClick={() => setLevel(s.id, l.value)}
                            >
                              {l.label}
                            </button>
                          ))}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
