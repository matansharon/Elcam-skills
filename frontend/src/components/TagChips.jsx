export default function TagChips({ tags, selected, onTagClick }) {
  if (!tags?.length) return null
  return (
    <span>
      {tags.map((tag) => (
        <span
          key={tag}
          className={`chip ${onTagClick ? 'clickable' : ''} ${selected === tag ? 'selected' : ''}`}
          onClick={onTagClick ? () => onTagClick(tag) : undefined}
        >
          {tag}
        </span>
      ))}
    </span>
  )
}
