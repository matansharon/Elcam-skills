import { useEffect, useState } from 'react'
import { api } from '../api/client'

const TYPES = ['depends_on', 'extends', 'used_with', 'replaces']

export default function RelationshipEditor({ skillId, onAdded }) {
  const [targets, setTargets] = useState([])
  const [type, setType] = useState('depends_on')
  const [target, setTarget] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .get('/api/skills')
      .then((skills) => setTargets(skills.filter((s) => s.id !== Number(skillId))))
      .catch((e) => setError(e.message))
  }, [skillId])

  const add = async () => {
    if (!target) return
    setError(null)
    setBusy(true)
    try {
      await api.post('/api/relationships', {
        source_skill_id: Number(skillId),
        target_skill_id: Number(target),
        type,
      })
      setTarget('')
      onAdded()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {error && <div className="banner banner-error">{error}</div>}
      <div className="toolbar" style={{ borderBottom: 'none', paddingLeft: 0 }}>
        <span className="mono">this skill</span>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={target} onChange={(e) => setTarget(e.target.value)} style={{ minWidth: 200 }}>
          <option value="">Choose a skill…</option>
          {targets.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button className="btn btn-primary btn-small" onClick={add} disabled={busy || !target}>
          Add link
        </button>
      </div>
    </div>
  )
}
