import { createContext, useContext, useEffect, useState } from 'react'
import { api, setOnUnauthorized } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setOnUnauthorized(() => setUser(null))
    api
      .get('/api/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    const u = await api.post('/api/auth/login', { username, password })
    setUser(u)
    return u
  }

  const logout = async () => {
    try {
      await api.post('/api/auth/logout')
    } catch {
      // session already gone — nothing to do
    }
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
