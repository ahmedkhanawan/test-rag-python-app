import { NavLink, Outlet } from 'react-router-dom'
import BackendStatus from '../components/BackendStatus.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function MainLayout() {
  const { isAuthenticated, logout } = useAuth()
  return (
    <>
      <nav className="navbar navbar-expand navbar-dark bg-dark">
        <div className="container">
          <span className="navbar-brand">
            <i className="bi bi-journal-text me-2" />
            Company Knowledge Assistant
          </span>
          <ul className="navbar-nav me-auto">
            <li className="nav-item">
              <NavLink to="/" end className="nav-link">
                Home
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/chat" className="nav-link">
                Ask Assistant
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/admin" className="nav-link">
                Admin
              </NavLink>
            </li>
          </ul>
          {isAuthenticated && (
            <button type="button" className="btn btn-outline-light btn-sm me-3" onClick={logout}>
              Log out
            </button>
          )}
          <BackendStatus />
        </div>
      </nav>
      <main className="container py-4">
        <Outlet />
      </main>
    </>
  )
}
