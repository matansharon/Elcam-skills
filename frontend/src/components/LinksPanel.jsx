import { Link } from 'react-router-dom'

function LinkList({ title, items, arrow, canDelete, onDelete }) {
  return (
    <div className="link-group">
      <h3>{title}</h3>
      {items.length === 0 && <div className="cell-muted">None</div>}
      {items.map((l) => (
        <div className="link-item" key={l.id}>
          <span className={`rel-type rel-${l.type}`}>
            {arrow === 'out' ? `${l.type} →` : `← ${l.type}`}
          </span>
          <Link to={`/skills/${l.skill.id}`}>{l.skill.name}</Link>
          <span className={`badge badge-${l.skill.status}`}>{l.skill.status}</span>
          {canDelete && (
            <button
              className="btn btn-danger btn-small"
              style={{ marginLeft: 'auto' }}
              onClick={() => onDelete(l.id)}
            >
              Remove
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

export default function LinksPanel({ links, canEdit, onDelete }) {
  return (
    <div>
      <LinkList
        title="Outgoing — this skill points to"
        items={links.outgoing}
        arrow="out"
        canDelete={canEdit}
        onDelete={onDelete}
      />
      <LinkList
        title="Incoming — other skills point here"
        items={links.incoming}
        arrow="in"
        canDelete={false}
      />
    </div>
  )
}
