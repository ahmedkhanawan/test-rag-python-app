import { useEffect, useState } from 'react'
import { getDocuments } from '../services/admin.js'

const STATUS_CLASS = {
  READY: 'text-bg-success',
  PROCESSING: 'text-bg-info',
  PENDING: 'text-bg-secondary',
  FAILED: 'text-bg-danger',
}

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    getDocuments()
      .then((data) => active && setDocuments(data))
      .catch((err) => {
        if (active && err?.response?.status !== 401) setError('Could not load documents.')
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <>
      <h1 className="h3 mb-3">Documents</h1>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {!documents && !error && <div className="text-muted" role="status">Loading…</div>}
      {documents && documents.length === 0 && (
        <p className="text-muted">No documents have been ingested yet.</p>
      )}
      {documents && documents.length > 0 && (
        <table className="table align-middle">
          <thead>
            <tr>
              <th>Name</th>
              <th>File</th>
              <th>Status</th>
              <th className="text-end">Chunks</th>
              <th>Added</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td className="text-muted">{d.filename}</td>
                <td>
                  <span className={`badge ${STATUS_CLASS[d.status] || 'text-bg-secondary'}`}>
                    {d.status}
                  </span>
                </td>
                <td className="text-end">{d.chunk_count}</td>
                <td className="text-muted small">{new Date(d.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
