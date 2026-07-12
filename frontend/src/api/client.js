// Single transport module — swap the fetch implementation here without
// touching any page or component.

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

let onUnauthorized = null
export function setOnUnauthorized(fn) {
  onUnauthorized = fn
}

async function request(method, path, body) {
  const opts = { method, credentials: 'include', headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(path, opts)
  let data = null
  try {
    data = await resp.json()
  } catch {
    data = null
  }
  if (!resp.ok) {
    if (resp.status === 401 && onUnauthorized) onUnauthorized()
    throw new ApiError(resp.status, data?.error || `Request failed (${resp.status})`)
  }
  return data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
}
