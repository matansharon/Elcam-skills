import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import StatusBadge from '../components/StatusBadge'
import TagChips from '../components/TagChips'
import SkillFormModal from '../components/SkillFormModal'
import FavoriteStar from '../components/FavoriteStar'
import FolderTree from '../components/FolderTree'
import FolderMenu from '../components/FolderMenu'

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [allSkills, setAllSkills] = useState(null) // unfiltered, for options
  const [skills, setSkills] = useState(null)
  const [folders, setFolders] = useState([])
  const [selectedFolder, setSelectedFolder] = useState(null) // null | 'unfiled' | id
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [owner, setOwner] = useState('')
  const [tag, setTag] = useState('')
  const [selectedIds, setSelectedIds] = useState(new Set()) // bulk-select skill ids
  const [menuFor, setMenuFor] = useState(null)              // skillId with open FolderMenu
  const [menuAnchor, setMenuAnchor] = useState(null)        // trigger rect for popover positioning
  const [skillFolderIds, setSkillFolderIds] = useState({})  // skillId -> [folderId] cache

  const loadFolders = () =>
    api.get('/api/folders').then((f) => { setFolders(f); return f }).catch(() => { setFolders([]); return [] })

  useEffect(() => {
    api.get('/api/skills').then(setAllSkills).catch((e) => setError(e.message))
    loadFolders()
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setQ(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    setSelectedIds(new Set())
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    if (category) params.set('category', category)
    if (owner) params.set('owner', owner)
    if (tag) params.set('tag', tag)
    if (selectedFolder === 'unfiled') params.set('folder', 'unfiled')
    else if (selectedFolder != null) params.set('folder', String(selectedFolder))
    api
      .get(`/api/skills?${params.toString()}`)
      .then(setSkills)
      .catch((e) => setError(e.message))
  }, [q, status, category, owner, tag, selectedFolder])

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

  const reload = () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    if (category) params.set('category', category)
    if (owner) params.set('owner', owner)
    if (tag) params.set('tag', tag)
    if (selectedFolder === 'unfiled') params.set('folder', 'unfiled')
    else if (selectedFolder != null) params.set('folder', String(selectedFolder))
    api.get(`/api/skills?${params.toString()}`).then(setSkills).catch((e) => setError(e.message))
  }

  const createFolder = async (parentId) => {
    const name = window.prompt('New folder name:')
    if (!name || !name.trim()) return
    try {
      await api.post('/api/folders', { name: name.trim(), parent_id: parentId })
      loadFolders()
    } catch (e) { setError(e.message) }
  }

  const renameFolder = async (folder) => {
    const name = window.prompt('Rename folder:', folder.name)
    if (!name || !name.trim() || name.trim() === folder.name) return
    try {
      await api.put(`/api/folders/${folder.id}`, { name: name.trim() })
      loadFolders()
    } catch (e) { setError(e.message) }
  }

  const deleteFolder = async (folder) => {
    if (!window.confirm(
      `Delete "${folder.name}"? Subfolders are deleted and their skills become unfiled. Skills are not deleted.`
    )) return
    try {
      await api.del(`/api/folders/${folder.id}`)
      if (selectedFolder === folder.id) setSelectedFolder(null)
      const fresh = await loadFolders()
      if (typeof selectedFolder === 'number' && !fresh.some((f) => f.id === selectedFolder)) {
        setSelectedFolder(null)
      }
      reload()
    } catch (e) { setError(e.message) }
  }

  const dropSkillOnFolder = async (skillId, folderId) => {
    try {
      // drag = move: membership becomes exactly [folderId]
      await api.put(`/api/skills/${skillId}/folders`, { folder_ids: [folderId] })
      loadFolders()
      reload()
    } catch (e) { setError(e.message) }
  }

  const toggleSelected = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const bulkMoveTo = async (folderId) => {
    if (!selectedIds.size) return
    try {
      await api.post(`/api/folders/${folderId}/skills`, {
        skill_ids: [...selectedIds], mode: 'move',
      })
      setSelectedIds(new Set())
      loadFolders()
      reload()
    } catch (e) { setError(e.message) }
  }

  const openFolderMenu = async (skillId, el) => {
    if (menuFor === skillId) { setMenuFor(null); setMenuAnchor(null); return }
    const rect = el.getBoundingClientRect()
    try {
      const detail = await api.get(`/api/skills/${skillId}`)
      setSkillFolderIds((m) => ({ ...m, [skillId]: (detail.folders || []).map((f) => f.id) }))
      setMenuAnchor(rect)
      setMenuFor(skillId)
    } catch (e) { setError(e.message) }
  }

  return (
    <div className="dashboard-layout">
      <FolderTree
        folders={folders}
        selected={selectedFolder}
        onSelect={setSelectedFolder}
        isAdmin={isAdmin}
        onCreate={createFolder}
        onRename={renameFolder}
        onDelete={deleteFolder}
        onDropSkill={dropSkillOnFolder}
      />

      <div className="dashboard-main">
        <div className="page-header">
          <div>
            <h1>Skills</h1>
            <div className="subtitle">
              {skills ? `${skills.length} skill${skills.length === 1 ? '' : 's'} visible to you` : ' '}
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New Skill
          </button>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        {isAdmin && selectedIds.size > 0 && (
          <div className="bulk-bar">
            <span>{selectedIds.size} selected</span>
            <label>
              Move to:
              <select
                defaultValue=""
                onChange={(e) => { if (e.target.value) bulkMoveTo(Number(e.target.value)) }}
              >
                <option value="" disabled>Choose folder…</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </label>
            <button className="btn btn-ghost btn-sm" onClick={() => setSelectedIds(new Set())}>
              Clear
            </button>
          </div>
        )}

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
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select value={owner} onChange={(e) => setOwner(e.target.value)}>
              <option value="">All owners</option>
              {options.owners.map((o) => (
                <option key={o} value={o}>{o}</option>
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
                  <th aria-label="Select">
                    {isAdmin ? <span className="cell-muted">☑</span> : ''}
                  </th>
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
                  <tr
                    key={s.id}
                    draggable={isAdmin}
                    onDragStart={(e) => e.dataTransfer.setData('text/skill-id', String(s.id))}
                  >
                    <td className="cell-select">
                      {isAdmin && (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(s.id)}
                          onChange={() => toggleSelected(s.id)}
                        />
                      )}
                      <FavoriteStar skillId={s.id} favorited={s.favorited} />
                    </td>
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
                    <td className="cell-muted">
                      <Link to={`/users/${s.owner.id}`}>{s.owner.display_name}</Link>
                    </td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td>
                      <span className="mono">v{s.current_version}</span>
                    </td>
                    <td className="cell-access">
                      <span className="badge badge-perm">{s.my_permission}</span>
                      {isAdmin && (
                        <span className="folder-menu-anchor">
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={(e) => openFolderMenu(s.id, e.currentTarget)}
                          >
                            Folders…
                          </button>
                          {menuFor === s.id && (
                            <FolderMenu
                              skillId={s.id}
                              currentFolderIds={skillFolderIds[s.id] || []}
                              folders={folders}
                              anchorRect={menuAnchor}
                              onClose={() => { setMenuFor(null); setMenuAnchor(null) }}
                              onApply={() => { loadFolders(); reload() }}
                            />
                          )}
                        </span>
                      )}
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
      </div>

      {showCreate && (
        <SkillFormModal
          title="New Skill"
          submitLabel="Create"
          uploadOption
          onUploaded={(skill) => navigate(`/skills/${skill.id}`)}
          onSubmit={createSkill}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}
