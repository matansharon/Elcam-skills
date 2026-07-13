import { useState } from 'react'
import { api } from '../api/client'

// Asks Claude to analyze the current form input and hands the sanitized
// suggestions back via onSuggestions. Never blocks manual entry.
export default function SuggestButton({ getInput, onSuggestions, disabled }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    setError(null)
    setBusy(true)
    try {
      const suggestions = await api.post('/api/skills/analyze', getInput())
      onSuggestions(suggestions)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="suggest-wrap">
      <button
        type="button"
        className="btn suggest-btn"
        onClick={run}
        disabled={busy || disabled}
      >
        {busy ? 'Analyzing…' : '✨ Suggest with AI'}
      </button>
      {error && <div className="banner banner-error suggest-error">{error}</div>}
    </div>
  )
}
