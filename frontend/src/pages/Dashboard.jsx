import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import TagChips from '../components/TagChips'
import SkillFormModal from '../components/SkillFormModal'
import UploadSkillModal from '../components/UploadSkillModal'

export default function Dashboard() {
  const navigate = useNavigate()
  const [allSkills, setAllSkills] = useState(null) // unfiltered, for options
  const [skills, setSkills] = useState(null)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showUpload, setShowUpload] = useState(false)

  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [owner, setOwner] = useState('')
  const [tag, setTag] = useState('')

  useEffect(() => {
    api.get('/api/skills').then(setAllSkills).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setQ(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    if (category) params.set('category', category)
    if (owner) params.set('owner', owner)
    if (tag) params.set('tag', tag)
    api
      .get(`/api/skills?${params.toString()}`)
      .then(setSkills)
      .catch((e) => setError(e.message))
  }, [q, status, category, owner, tag])

  const options = useMemo(() => {
    const categories = new Set()
    const owners = new Set()
    for (const s of allSkills || []) {
      if (s.category) categories.add(s.category)
      owners.add(s.owner.display_name)
    }
    return {
      categories: [...categories].sort(),
      owners: [...owners].sort(),
    }
  }, [allSkills])

  const createSkill = async (payload) => {
    const skill = await api.post('/api/skills', payload)
    navigate(`/skills/${skill.id}`)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Skills</h1>
          <div className="subtitle">
            {skills ? `${skills.length} skill${skills.length === 1 ? '' : 's'} visible to you` : ' '}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => setShowUpload(true)}>
            ⬆ Upload .skill
          </button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New Skill
          </button>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="card">
        <div className="toolbar">
          <input
            type="search"
            placeholder="Search name or description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="deprecated">deprecated</option>
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {options.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select value={owner} onChange={(e) => setOwner(e.target.value)}>
            <option value="">All owners</option>
            {options.owners.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          {tag && (
            <span className="chip selected clickable" onClick={() => setTag('')}>
              tag: {tag} ✕
            </span>
          )}
        </div>

        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Category</th>
                <th>Tags</th>
                <th>Owner</th>
                <th>Status</th>
                <th>Ver</th>
                <th>Access</th>
              </tr>
            </thead>
            <tbody>
              {(skills || []).map((s) => (
                <tr key={s.id}>
                  <td className="cell-name">
                    <Link to={`/skills/${s.id}`}>{s.name}</Link>
                  </td>
                  <td className="cell-muted">
                    {s.description.length > 70
                      ? s.description.slice(0, 70) + '…'
                      : s.description}
                  </td>
                  <td className="cell-muted">{s.category}</td>
                  <td>
                    <TagChips tags={s.tags} selected={tag} onTagClick={setTag} />
                  </td>
                  <td className="cell-muted">{s.owner.display_name}</td>
                  <td>
                    <StatusBadge status={s.status} />
                  </td>
                  <td>
                    <span className="mono">v{s.current_version}</span>
                  </td>
                  <td>
                    <span className="badge badge-perm">{s.my_permission}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {skills && skills.length === 0 && (
            <div className="empty-state">No skills match the current filters.</div>
          )}
        </div>
      </div>

      {showCreate && (
        <SkillFormModal
          title="New Skill"
          submitLabel="Create"
          onSubmit={createSkill}
          onClose={() => setShowCreate(false)}
        />
      )}

      {showUpload && (
        <UploadSkillModal
          onCreated={(skill) => navigate(`/skills/${skill.id}`)}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  )
}
