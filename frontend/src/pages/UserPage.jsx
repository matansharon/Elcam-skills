import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import FavoriteStar from '../components/FavoriteStar'

function SkillTable({ rows, emptyText }) {
  if (!rows) return <div className="page-loading">Loading…</div>
  if (rows.length === 0) return <div className="empty-state">{emptyText}</div>
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th aria-label="Favorite"></th>
            <th>Name</th>
            <th>Category</th>
            <th>Status</th>
            <th>Ver</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td><FavoriteStar skillId={s.id} favorited={s.favorited} /></td>
              <td className="cell-name"><Link to={`/skills/${s.id}`}>{s.name}</Link></td>
              <td className="cell-muted">{s.category}</td>
              <td><StatusBadge status={s.status} /></td>
              <td><span className="mono">v{s.current_version}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function UserPage() {
  const { id } = useParams()
  const [profile, setProfile] = useState(null)
  const [owned, setOwned] = useState(null)
  const [favorites, setFavorites] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setProfile(null); setOwned(null); setFavorites(null); setError(null)
    api.get(`/api/users/${id}`).then(setProfile).catch((e) => setError(e.message))
    api.get(`/api/skills?owner=${id}`).then(setOwned).catch(() => setOwned([]))
    api.get(`/api/users/${id}/favorites`).then(setFavorites).catch(() => setFavorites([]))
  }, [id])

  if (error) {
    return <div className="empty-state">User not found (or you have no access).</div>
  }
  if (!profile) return <div className="page-loading">Loading…</div>

  return (
    <div className="user-page">
      <div className="page-header">
        <div>
          <h1>{profile.display_name}</h1>
          <div className="subtitle">
            <span className="badge badge-perm">{profile.role}</span>{' '}
            @{profile.username} · joined {new Date(profile.created_at).toLocaleDateString()} ·{' '}
            {profile.owned_count} owned · {profile.favorite_count} favorites
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="section-title">Skills owned</h2>
        <SkillTable rows={owned} emptyText="No skills owned yet." />
      </div>

      <div className="card">
        <h2 className="section-title">Favorites</h2>
        <SkillTable rows={favorites} emptyText="No favorites yet." />
      </div>
    </div>
  )
}
