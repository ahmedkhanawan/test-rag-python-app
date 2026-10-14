import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAdminStats } from '../services/admin.js'

function StatCard({ label, value }) {
  return (
    <div className="col-6 col-md-3">
      <div className="card text-center h-100">
        <div className="card-body">
          <div className="display-6">{value}</div>
          <div className="text-muted small">{label}</div>
        </div>
      </div>
    </div>
  )
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    getAdminStats()
      .then((data) => active && setStats(data))
      .catch((err) => {
        // 401 is handled globally (logout + redirect)
        if (active && err?.response?.status !== 401) setError('Could not load statistics.')
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h1 className="h3 mb-0">Admin dashboard</h1>
        <Link to="/admin/documents" className="btn btn-outline-primary btn-sm">
          <i className="bi bi-files me-1" />
          Documents
        </Link>
      </div>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {!stats && !error && (
        <div className="text-muted" role="status">Loading…</div>
      )}
      {stats && (
        <>
          <div className="row g-3 mb-3">
            <StatCard label="Documents" value={stats.documents} />
            <StatCard label="Chunks" value={stats.chunks} />
            <StatCard label="Conversations" value={stats.conversations} />
            <StatCard label="Messages" value={stats.messages} />
          </div>
          <h2 className="h6 text-muted">Documents by status</h2>
          <ul className="list-inline">
            {Object.entries(stats.documents_by_status).map(([status, n]) => (
              <li key={status} className="list-inline-item">
                {status}: <strong>{n}</strong>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}
