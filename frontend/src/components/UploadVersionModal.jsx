import { useState } from 'react'
import { api } from '../api/client'

// Publish a .skill package as the next version of an existing skill.
// Content and description come from the package; identity fields don't change.
export default function UploadVersionModal({ skillId, skillName, onUploaded, onClose }) {
  const [file, setFile] = useState(null)
  const [changeNote, setChangeNote] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return
    setError(null)
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('change_note', changeNote)
      await api.upload(`/api/skills/${skillId}/upload`, fd)
      onUploaded()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" onSubmit={submit}>
        <h2>Upload new version — {skillName}</h2>
        <p className="cell-muted" style={{ marginTop: 0, fontSize: 13 }}>
          The package's SKILL.md becomes the new content and description. The
          skill's name, category, tags, and status are not changed.
        </p>
        {error && <div className="banner banner-error">{error}</div>}
        <label className="field">
          Package file
          <input
            type="file"
            accept=".skill,.zip"
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
        </label>
        <label className="field">
          Change note
          <input
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            placeholder="What changed and why?"
          />
        </label>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy || !file}>
            {busy ? 'Uploading…' : 'Publish version'}
          </button>
        </div>
      </form>
    </div>
  )
}
