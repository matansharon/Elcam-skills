import { useEffect, useState } from 'react'
import { api } from '../api/client'

const TYPES = ['depends_on', 'extends', 'used_with', 'replaces']

// Controlled picker: value is [{ target_skill_id, type }]. Options come from
// the skills the current user can see.
export default function RelatedSkillsPicker({ value, onChange }) {
  const [skills, setSkills] = useState([])

  useEffect(() => {
    api.get('/api/skills').then(setSkills).catch(() => setSkills([]))
  }, [])

  const picked = new Set(value.map((r) => r.target_skill_id))

  const addRow = () => onChange([...value, { target_skill_id: null, type: 'used_with' }])
  const removeRow = (i) => onChange(value.filter((_, idx) => idx !== i))
  const setRow = (i, patch) =>
    onChange(value.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  return (
    <div className="related-picker">
      <div className="related-picker-label">Related skills</div>
      {value.map((row, i) => (
        <div className="related-row" key={i}>
          <select
            value={row.target_skill_id ?? ''}
            onChange={(e) => setRow(i, { target_skill_id: Number(e.target.value) })}
          >
            <option value="" disabled>
              Select a skill…
            </option>
            {skills
              .filter((s) => s.id === row.target_skill_id || !picked.has(s.id))
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
          <select value={row.type} onChange={(e) => setRow(i, { type: e.target.value })}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-ghost btn-small" onClick={() => removeRow(i)}>
            ✕
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-ghost btn-small" onClick={addRow}>
        ＋ Add related skill
      </button>
    </div>
  )
}
