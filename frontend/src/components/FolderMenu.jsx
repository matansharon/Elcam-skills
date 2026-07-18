import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

// A checkbox popover: check/uncheck folders to set a skill's exact membership.
export default function FolderMenu({ skillId, currentFolderIds, folders, onApply, onClose }) {
  const [checked, setChecked] = useState(new Set(currentFolderIds || []))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const ref = useRef(null)

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose?.() }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [onClose])

  const toggle = (id) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const apply = async () => {
    setBusy(true)
    setErr(null)
    try {
      const folderIds = [...checked]
      await api.put(`/api/skills/${skillId}/folders`, { folder_ids: folderIds })
      onApply?.(folderIds)
      onClose?.()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="folder-menu" ref={ref}>
      <div className="folder-menu-title">Folders</div>
      <div className="folder-menu-list">
        {folders.length === 0 && <div className="cell-muted">No folders yet.</div>}
        {folders.map((f) => (
          <label key={f.id} className="folder-menu-item">
            <input type="checkbox" checked={checked.has(f.id)} onChange={() => toggle(f.id)} />
            {f.name}
          </label>
        ))}
      </div>
      {err && <div className="folder-menu-error">{err}</div>}
      <div className="folder-menu-actions">
        <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="btn btn-primary btn-sm" onClick={apply} disabled={busy}>Apply</button>
      </div>
    </div>
  )
}
