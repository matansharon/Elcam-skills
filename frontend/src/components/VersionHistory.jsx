import { useEffect, useState } from 'react'
import { api } from '../api/client'
import DiffView from './DiffView'
import UploadVersionModal from './UploadVersionModal'

export default function VersionHistory({ skillId, skillName, versions, canEdit, onRestore, onUploaded }) {
  const [showUpload, setShowUpload] = useState(false)
  const numbers = versions.map((v) => v.version_number)
  const latest = numbers[0]
  const [from, setFrom] = useState(numbers[1] ?? latest)
  const [to, setTo] = useState(latest)
  const [contents, setContents] = useState({}) // version_number -> content
  const [error, setError] = useState(null)

  useEffect(() => {
    for (const n of [from, to]) {
      if (n != null && contents[n] === undefined) {
        api
          .get(`/api/skills/${skillId}/versions/${n}`)
          .then((v) => setContents((c) => ({ ...c, [n]: v.content })))
          .catch((e) => setError(e.message))
      }
    }
  }, [from, to, skillId]) // eslint-disable-line react-hooks/exhaustive-deps

  const restore = (n) => {
    if (window.confirm(`Restore version ${n}? This creates a new version — history is kept.`)) {
      onRestore(n)
    }
  }

  return (
    <div>
      {error && <div className="banner banner-error">{error}</div>}

      {canEdit && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <button className="btn btn-ghost btn-small" onClick={() => setShowUpload(true)}>
            ⬆ Upload new version
          </button>
        </div>
      )}

      {versions.length > 1 && (
        <div className="toolbar" style={{ borderBottom: 'none', paddingLeft: 0 }}>
          <span className="mono">compare</span>
          <select value={from} onChange={(e) => setFrom(Number(e.target.value))} style={{ width: 90 }}>
            {numbers.map((n) => (
              <option key={n} value={n}>
                v{n}
              </option>
            ))}
          </select>
          <span className="mono">→</span>
          <select value={to} onChange={(e) => setTo(Number(e.target.value))} style={{ width: 90 }}>
            {numbers.map((n) => (
              <option key={n} value={n}>
                v{n}
              </option>
            ))}
          </select>
        </div>
      )}

      {versions.length > 1 && contents[from] !== undefined && contents[to] !== undefined && (
        <DiffView oldText={contents[from]} newText={contents[to]} />
      )}

      <div className="card section-gap">
        {versions.map((v) => (
          <div className="version-row" key={v.version_number}>
            <span className="version-num">v{v.version_number}</span>
            <span className="version-meta">
              <strong>{v.change_note || '—'}</strong>
              {' · '}
              {v.created_by} · {new Date(v.created_at).toLocaleString()}
            </span>
            {v.has_package && (
              <a
                className="package-chip"
                href={`/api/skills/${skillId}/versions/${v.version_number}/package`}
                title="Download the original .skill package"
              >
                ⬇ {v.package_filename || 'package.skill'}
              </a>
            )}
            {canEdit && v.version_number !== latest && (
              <button className="btn btn-ghost btn-small" onClick={() => restore(v.version_number)}>
                Restore
              </button>
            )}
          </div>
        ))}
      </div>

      {showUpload && (
        <UploadVersionModal
          skillId={skillId}
          skillName={skillName}
          onUploaded={() => {
            setShowUpload(false)
            onUploaded()
          }}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  )
}
