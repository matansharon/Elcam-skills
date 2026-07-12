import { diffLines } from 'diff'

export default function DiffView({ oldText, newText }) {
  const parts = diffLines(oldText ?? '', newText ?? '')
  return (
    <div className="diff-view">
      {parts.flatMap((part, i) => {
        const cls = part.added ? 'diff-add' : part.removed ? 'diff-del' : ''
        return part.value
          .replace(/\n$/, '')
          .split('\n')
          .map((line, j) => (
            <div key={`${i}-${j}`} className={`diff-line ${cls}`}>
              {line || ' '}
            </div>
          ))
      })}
    </div>
  )
}
