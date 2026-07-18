import { useMemo, useState } from 'react'

// Build a parent_id -> children[] map and render recursively.
function buildTree(folders) {
  const byParent = new Map()
  for (const f of folders) {
    const key = f.parent_id ?? null
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key).push(f)
  }
  return byParent
}

function FolderNode({ folder, byParent, depth, ctx }) {
  const children = byParent.get(folder.id) || []
  const [open, setOpen] = useState(true)
  const isSelected = ctx.selected === folder.id

  const onDrop = (e) => {
    if (!ctx.isAdmin || !ctx.onDropSkill) return
    e.preventDefault()
    const skillId = e.dataTransfer.getData('text/skill-id')
    if (skillId) ctx.onDropSkill(Number(skillId), folder.id)
  }

  return (
    <li>
      <div
        className={`folder-row${isSelected ? ' is-selected' : ''}`}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        onClick={() => ctx.onSelect(folder.id)}
        onDragOver={(e) => ctx.isAdmin && e.preventDefault()}
        onDrop={onDrop}
      >
        <button
          type="button"
          className="folder-twisty"
          onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
          aria-label={open ? 'Collapse' : 'Expand'}
        >
          {children.length ? (open ? '▾' : '▸') : '·'}
        </button>
        <span className="folder-name">{folder.name}</span>
        <span className="folder-count">{folder.skill_count}</span>
        {ctx.isAdmin && (
          <span className="folder-actions">
            <button type="button" title="New subfolder"
              onClick={(e) => { e.stopPropagation(); ctx.onCreate(folder.id) }}>＋</button>
            <button type="button" title="Rename"
              onClick={(e) => { e.stopPropagation(); ctx.onRename(folder) }}>✎</button>
            <button type="button" title="Delete"
              onClick={(e) => { e.stopPropagation(); ctx.onDelete(folder) }}>🗑</button>
          </span>
        )}
      </div>
      {open && children.length > 0 && (
        <ul className="folder-children">
          {children.map((c) => (
            <FolderNode key={c.id} folder={c} byParent={byParent} depth={depth + 1} ctx={ctx} />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function FolderTree({
  folders, selected, onSelect,
  isAdmin = false, onCreate, onRename, onDelete, onDropSkill,
}) {
  const byParent = useMemo(() => buildTree(folders || []), [folders])
  const roots = byParent.get(null) || []
  const ctx = { selected, onSelect, isAdmin, onCreate, onRename, onDelete, onDropSkill }

  return (
    <aside className="folder-sidebar">
      <div className="folder-sidebar-head">
        <span>Folders</span>
        {isAdmin && (
          <button type="button" className="btn btn-ghost btn-sm"
            onClick={() => onCreate(null)}>+ New</button>
        )}
      </div>
      <ul className="folder-tree">
        <li>
          <div className={`folder-row${selected === null ? ' is-selected' : ''}`}
            style={{ paddingLeft: '8px' }} onClick={() => onSelect(null)}>
            <span className="folder-twisty">★</span>
            <span className="folder-name">All skills</span>
          </div>
        </li>
        <li>
          <div className={`folder-row${selected === 'unfiled' ? ' is-selected' : ''}`}
            style={{ paddingLeft: '8px' }} onClick={() => onSelect('unfiled')}>
            <span className="folder-twisty">⌫</span>
            <span className="folder-name">Unfiled</span>
          </div>
        </li>
        {roots.map((f) => (
          <FolderNode key={f.id} folder={f} byParent={byParent} depth={0} ctx={ctx} />
        ))}
      </ul>
    </aside>
  )
}
