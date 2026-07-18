import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function FavoriteStar({ skillId, favorited, onChange }) {
  const [on, setOn] = useState(!!favorited)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setOn(!!favorited)
  }, [favorited, skillId])

  const toggle = async (e) => {
    e.stopPropagation()
    e.preventDefault()
    if (busy) return
    setBusy(true)
    const next = !on
    setOn(next) // optimistic
    try {
      if (next) await api.put(`/api/skills/${skillId}/favorite`)
      else await api.del(`/api/skills/${skillId}/favorite`)
      onChange?.(next)
    } catch {
      setOn(!next) // revert on failure
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      className={`fav-star${on ? ' is-on' : ''}`}
      aria-pressed={on}
      aria-label={on ? 'Remove from favorites' : 'Add to favorites'}
      title={on ? 'Remove from favorites' : 'Add to favorites'}
      onClick={toggle}
    >
      {on ? '★' : '☆'}
    </button>
  )
}
