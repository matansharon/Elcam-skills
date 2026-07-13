import { useState } from 'react'
import UploadSkillForm from './UploadSkillForm'

const EMPTY = {
  name: '',
  description: '',
  category: '',
  tags: [],
  status: 'draft',
  content: '',
}

// Create/edit a skill. With uploadOption (create flow), the modal offers two
// modes: write the markdown manually, or upload a .skill package.
export default function SkillFormModal({
  title,
  initial,
  submitLabel = 'Save',
  showChangeNote = false,
  uploadOption = false,
  onUploaded,
  onSubmit,
  onClose,
}) {
  const base = { ...EMPTY, ...(initial || {}) }
  const [mode, setMode] = useState('manual')
  const [form, setForm] = useState({
    ...base,
    tags: (base.tags || []).join(', '),
    change_note: '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const payload = {
        name: form.name,
        description: form.description,
        category: form.category,
        tags: form.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        status: form.status,
        content: form.content,
      }
      if (showChangeNote) payload.change_note = form.change_note
      await onSubmit(payload)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2>{title}</h2>

        {uploadOption && (
          <div className="mode-toggle">
            <button
              type="button"
              className={mode === 'manual' ? 'active' : ''}
              onClick={() => setMode('manual')}
            >
              ✎ Write manually
            </button>
            <button
              type="button"
              className={mode === 'upload' ? 'active' : ''}
              onClick={() => setMode('upload')}
            >
              ⬆ Upload .skill
            </button>
          </div>
        )}

        {mode === 'upload' ? (
          <UploadSkillForm onCreated={onUploaded} onClose={onClose} />
        ) : (
          <form onSubmit={submit}>
            {error && <div className="banner banner-error">{error}</div>}
            <div className="field-row">
              <label className="field">
                Name
                <input value={form.name} onChange={set('name')} required autoFocus />
              </label>
              <label className="field">
                Category
                <input
                  value={form.category}
                  onChange={set('category')}
                  placeholder="e.g. data-extraction"
                />
              </label>
            </div>
            <label className="field">
              Description
              <input value={form.description} onChange={set('description')} />
            </label>
            <div className="field-row">
              <label className="field">
                Tags (comma-separated)
                <input value={form.tags} onChange={set('tags')} placeholder="pdf, tables" />
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
              Content (markdown)
              <textarea value={form.content} onChange={set('content')} />
            </label>
            {showChangeNote && (
              <label className="field">
                Change note
                <input
                  value={form.change_note}
                  onChange={set('change_note')}
                  placeholder="What changed and why?"
                />
              </label>
            )}
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={onClose}>
                Cancel
              </button>
              <button className="btn btn-primary" disabled={busy}>
                {busy ? 'Saving…' : submitLabel}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
