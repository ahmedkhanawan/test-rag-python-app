import { NavLink, Outlet } from 'react-router-dom'
import BackendStatus from '../components/BackendStatus.jsx'

export default function MainLayout() {
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
          </ul>
          <BackendStatus />
        </div>
      </nav>
      <main className="container py-4">
        <Outlet />
      </main>
    </>
  )
}
