// Standalone transport for the activity panel. Unlike the app's shared
// client it has no global 401 handler, so a panel 401 never disturbs the
// main app's auth state.
async function send(path, opts) {
  const resp = await fetch(path, opts)
  let data = null
  try {
    data = await resp.json()
  } catch {
    data = null
  }
  if (!resp.ok) {
    const err = new Error(data?.error || `Request failed (${resp.status})`)
    err.status = resp.status
    throw err
  }
  return data
}

function request(method, path, body) {
  const opts = { method, credentials: 'include', headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  return send(path, opts)
}

export const activityApi = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
}
