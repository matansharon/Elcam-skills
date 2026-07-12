import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import PermissionMatrix from '../components/PermissionMatrix'

const EMPTY_FORM = { username: '', display_name: '', password: '', role: 'user' }

export default function AdminPanel() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [skills, setSkills] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const [us, ss] = await Promise.all([api.get('/api/users'), api.get('/api/skills')])
      setUsers(us)
      setSkills(ss)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const createUser = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api.post('/api/users', form)
      setForm(EMPTY_FORM)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const deleteUser = async (u) => {
    if (!window.confirm(`Delete user "${u.display_name}"? Their skills will be reassigned to you.`))
      return
    setError(null)
    try {
      await api.del(`/api/users/${u.id}`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Administration</h1>
          <div className="subtitle">Manage users and per-skill access.</div>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="admin-grid">
        <div className="card panel">
          <h2 style={{ fontSize: 17 }}>Users</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="cell-name">
                      {u.display_name}
                      <div className="cell-muted mono">{u.username}</div>
                    </td>
                    <td>
                      <span className="badge badge-perm">{u.role}</span>
                    </td>
                    <td className="cell-muted">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      {u.id !== me.id && (
                        <button
                          className="btn btn-danger btn-small"
                          onClick={() => deleteUser(u)}
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 style={{ fontSize: 15, marginTop: 20 }}>Add user</h3>
          <form onSubmit={createUser}>
            <div className="field-row">
              <label className="field">
                Username
                <input value={form.username} onChange={set('username')} required />
              </label>
              <label className="field">
                Display name
                <input value={form.display_name} onChange={set('display_name')} />
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                Password
                <input
                  type="password"
                  value={form.password}
                  onChange={set('password')}
                  required
                />
              </label>
              <label className="field">
                Role
                <select value={form.role} onChange={set('role')}>
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </label>
            </div>
            <button className="btn btn-primary">Create user</button>
          </form>
        </div>

        <PermissionMatrix users={users} skills={skills} />
      </div>
    </div>
  )
}
