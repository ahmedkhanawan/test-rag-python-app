import { NavLink } from 'react-router-dom'

export default function AdminNav() {
  return (
    <ul className="nav nav-pills mb-4">
      <li className="nav-item">
        <NavLink to="/admin" end className="nav-link">
          <i className="bi bi-speedometer2 me-1" />
          Dashboard
        </NavLink>
      </li>
      <li className="nav-item">
        <NavLink to="/admin/documents" className="nav-link">
          <i className="bi bi-files me-1" />
          Documents
        </NavLink>
      </li>
      <li className="nav-item">
        <NavLink to="/admin/retrieval" className="nav-link">
          <i className="bi bi-search me-1" />
          Retrieval playground
        </NavLink>
      </li>
      <li className="nav-item">
        <NavLink to="/admin/evaluation" className="nav-link">
          <i className="bi bi-clipboard-data me-1" />
          Evaluation
        </NavLink>
      </li>
    </ul>
  )
}
