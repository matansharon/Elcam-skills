import { useState } from 'react'
import { api } from '../api/client'

// Create a skill from a .skill package. Name, description, and content come
// from the package's SKILL.md (shown as a preview via a server-side dry run);
// the user supplies category, tags, and status. Rendered inside the
// New Skill modal as the "Upload .skill" mode.
export default function UploadSkillForm({ onCreated, onClose }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [form, setForm] = useState({ category: '', tags: '', status: 'draft' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const pickFile = async (e) => {
    const f = e.target.files[0] || null
    setFile(f)
    setPreview(null)
    setError(null)
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    fd.append('dry_run', '1')
    try {
      setPreview(await api.upload('/api/skills/upload', fd))
    } catch (err) {
      setError(err.message)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!file || !preview) return
    setError(null)
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('category', form.category)
      fd.append('tags', form.tags)
      fd.append('status', form.status)
      const skill = await api.upload('/api/skills/upload', fd)
      onCreated(skill)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <div className="banner banner-error">{error}</div>}

      <label className="field">
        Package file
        <input type="file" accept=".skill,.zip" onChange={pickFile} />
      </label>

      {preview && (
        <>
          <div className="upload-preview">
            <div className="upload-preview-head">
              <span className="mono upload-preview-name">{preview.name}</span>
            </div>
            {preview.description && (
              <div className="upload-preview-desc">{preview.description}</div>
            )}
            <pre className="upload-preview-content">
              {preview.content.split('\n').slice(0, 10).join('\n')}
              {preview.content.split('\n').length > 10 ? '\n…' : ''}
            </pre>
            {preview.bundled_files.length > 0 && (
              <div className="upload-preview-files">
                {preview.bundled_files.map((f) => (
                  <span key={f} className="chip mono">
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="field-row">
            <label className="field">
              Category
              <input
                value={form.category}
                onChange={set('category')}
                placeholder="e.g. data-extraction"
              />
            </label>
            <label className="field">
              Status
              <select value={form.status} onChange={set('status')}>
                <option value="draft">draft</option>
                <option value="active">active</option>
                <option value="deprecated">deprecated</option>
              </select>
            </label>
          </div>
          <label className="field">
            Tags (comma-separated)
            <input value={form.tags} onChange={set('tags')} placeholder="pdf, tables" />
          </label>
        </>
      )}

      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={busy || !preview}>
          {busy ? 'Uploading…' : 'Create skill'}
        </button>
      </div>
    </form>
  )
}
