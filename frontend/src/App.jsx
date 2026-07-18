import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import LoginPage from './auth/LoginPage'
import Dashboard from './pages/Dashboard'
import SkillDetail from './pages/SkillDetail'
import UserPage from './pages/UserPage'
import GraphView from './pages/GraphView'
import AdminPanel from './pages/AdminPanel'
import ActivityPage from './activity/ActivityPage'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-loading">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RequireAdmin({ children }) {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return children
}

function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="app-shell">
      <header className="top-nav">
        <div className="wordmark">
          <span className="wordmark-block" />
          <span className="wordmark-text">
            ELCAM <em>/</em> SKILL REGISTRY
          </span>
        </div>
        <nav className="nav-links">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/graph">Graph</NavLink>
          <NavLink to={`/users/${user?.id}`}>My Page</NavLink>
          {user?.role === 'admin' && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <div className="nav-user">
          <span className="user-chip">
            {user?.display_name}
            <em>{user?.role}</em>
          </span>
          <button className="btn btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="skills/:id" element={<SkillDetail />} />
        <Route path="users/:id" element={<UserPage />} />
        <Route path="graph" element={<GraphView />} />
        <Route
          path="admin"
          element={
            <RequireAdmin>
              <AdminPanel />
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="/activity" element={<ActivityPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
