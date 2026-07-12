export default function AuditPanel({ entries }) {
  if (!entries.length) return <div className="empty-state">No activity recorded.</div>
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>When</th>
            <th>Who</th>
            <th>Action</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td className="cell-muted mono">{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.user || '—'}</td>
              <td>
                <span className="mono">{e.action}</span>
              </td>
              <td className="cell-muted">{e.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
