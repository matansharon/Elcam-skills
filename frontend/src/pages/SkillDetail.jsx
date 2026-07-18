import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import StatusBadge from '../components/StatusBadge'
import TagChips from '../components/TagChips'
import FavoriteStar from '../components/FavoriteStar'
import SkillFormModal from '../components/SkillFormModal'
import VersionHistory from '../components/VersionHistory'
import LinksPanel from '../components/LinksPanel'
import RelationshipEditor from '../components/RelationshipEditor'
import AuditPanel from '../components/AuditPanel'

const TABS = ['Content', 'Links', 'History', 'Audit']

export default function SkillDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [skill, setSkill] = useState(null)
  const [content, setContent] = useState('')
  const [latestVersion, setLatestVersion] = useState(null)
  const [versions, setVersions] = useState([])
  const [links, setLinks] = useState({ outgoing: [], incoming: [] })
  const [audit, setAudit] = useState([])
  const [tab, setTab] = useState('Content')
  const [error, setError] = useState(null)
  const [showEdit, setShowEdit] = useState(false)

  const load = useCallback(async () => {
    try {
      const s = await api.get(`/api/skills/${id}`)
      setSkill(s)
      const [vs, ls, au] = await Promise.all([
        api.get(`/api/skills/${id}/versions`),
        api.get(`/api/skills/${id}/links`),
        api.get(`/api/skills/${id}/audit`),
      ])
      setVersions(vs)
      setLinks(ls)
      setAudit(au)
      if (vs.length) {
        const latest = await api.get(`/api/skills/${id}/versions/${vs[0].version_number}`)
        setContent(latest.content)
        setLatestVersion(latest)
      }
      setError(null)
    } catch (e) {
      setError(e.message)
      if (e.status === 404) setSkill(null)
    }
  }, [id])

  useEffect(() => {
    setTab('Content')
    load()
  }, [load])

  if (error && !skill) {
    return <div className="empty-state">Skill not found (or you have no access to it).</div>
  }
  if (!skill) return <div className="page-loading">Loading…</div>

  const canEdit = skill.my_permission === 'edit'

  const saveEdit = async (payload) => {
    await api.put(`/api/skills/${id}`, payload)
    setShowEdit(false)
    await load()
  }

  const restoreVersion = async (n) => {
    try {
      await api.post(`/api/skills/${id}/versions/${n}/restore`)
      await load()
      setTab('Content')
    } catch (e) {
      setError(e.message)
    }
  }

  const deleteLink = async (relId) => {
    try {
      await api.del(`/api/relationships/${relId}`)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const deleteSkill = async () => {
    if (!window.confirm(`Delete "${skill.name}" and its entire history? This cannot be undone.`)) return
    try {
      await api.del(`/api/skills/${id}`)
      navigate('/')
    } catch (e) {
      setError(e.message)
    }
  }

  const isOwner = user?.role === 'admin' || user?.id === skill.owner.id

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="detail-title-row">
            <h1>{skill.name}</h1>
            <FavoriteStar skillId={skill.id} favorited={skill.favorited} />
          </div>
          <div className="subtitle">
            <StatusBadge status={skill.status} />{' '}
            <span className="mono">v{skill.current_version}</span>
            {' · '}
            {skill.category || 'uncategorized'}
            {' · owned by '}
            <Link to={`/users/${skill.owner.id}`}>{skill.owner.display_name}</Link>
            {' · updated '}
            {new Date(skill.updated_at).toLocaleString()}
          </div>
          <div style={{ marginTop: 8 }}>
            <TagChips tags={skill.tags} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {latestVersion?.has_package && (
            <a
              className="btn btn-ghost"
              href={`/api/skills/${id}/versions/${latestVersion.version_number}/package`}
            >
              ⬇ Download .skill
            </a>
          )}
          {canEdit && (
            <button className="btn btn-primary" onClick={() => setShowEdit(true)}>
              Edit
            </button>
          )}
          {isOwner && (
            <button className="btn btn-danger" onClick={deleteSkill}>
              Delete
            </button>
          )}
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="card">
        <div className="tabs">
          {TABS.map((t) => (
            <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
              {t}
              {t === 'Links' && ` (${links.outgoing.length + links.incoming.length})`}
              {t === 'History' && ` (${versions.length})`}
            </button>
          ))}
        </div>
        <div className="panel">
          {tab === 'Content' && (
            <div>
              <div className="md-body">
                {content ? <ReactMarkdown>{content}</ReactMarkdown> : (
                  <div className="cell-muted">No content yet.</div>
                )}
              </div>
              {latestVersion?.bundled_files?.length > 0 && (
                <div className="bundled-files">
                  <h3 style={{ fontSize: 14, marginBottom: 8 }}>Bundled files</h3>
                  <div className="upload-preview-files">
                    {latestVersion.bundled_files.map((f) => (
                      <span key={f} className="chip mono">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'Links' && (
            <div>
              <LinksPanel links={links} canEdit={canEdit} onDelete={deleteLink} />
              {canEdit && (
                <>
                  <h3 style={{ marginTop: 20, fontSize: 15 }}>Add a link</h3>
                  <RelationshipEditor skillId={id} onAdded={load} />
                </>
              )}
            </div>
          )}

          {tab === 'History' && (
            <VersionHistory
              skillId={id}
              skillName={skill.name}
              versions={versions}
              canEdit={canEdit}
              onRestore={restoreVersion}
              onUploaded={load}
            />
          )}

          {tab === 'Audit' && <AuditPanel entries={audit} />}
        </div>
      </div>

      {showEdit && (
        <SkillFormModal
          title={`Edit — ${skill.name}`}
          submitLabel="Save new version"
          showChangeNote
          initial={{
            name: skill.name,
            description: skill.description,
            category: skill.category,
            tags: skill.tags,
            status: skill.status,
            content,
          }}
          onSubmit={saveEdit}
          onClose={() => setShowEdit(false)}
        />
      )}
    </div>
  )
}
