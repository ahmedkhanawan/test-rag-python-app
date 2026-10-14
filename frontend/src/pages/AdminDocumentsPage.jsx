import { useCallback, useEffect, useRef, useState } from 'react'
import AdminNav from '../components/AdminNav.jsx'
import {
  deleteDocument,
  getDocuments,
  reindexDocument,
  uploadDocument,
} from '../services/admin.js'
import { describeAdminError } from '../utils/errors.js'

const STATUS_CLASS = {
  READY: 'text-bg-success',
  PROCESSING: 'text-bg-info',
  PENDING: 'text-bg-secondary',
  FAILED: 'text-bg-danger',
}

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [file, setFile] = useState(null)
  const [name, setName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [busyId, setBusyId] = useState(null) // document with a re-index/delete in flight
  const fileInput = useRef(null)

  const load = useCallback(async () => {
    try {
      setDocuments(await getDocuments())
    } catch (err) {
      // 401 is handled globally (logout + redirect)
      if (err?.response?.status !== 401) setError(describeAdminError(err, 'Could not load documents.'))
    }
  }, [])

  useEffect(() => {
    // Initial fetch: setState happens after the awaited request resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setError(null)
    setNotice(null)
    try {
      const doc = await uploadDocument(file, name)
      setNotice(`Uploaded "${doc.name}" (${doc.chunk_count} chunks).`)
      setFile(null)
      setName('')
      if (fileInput.current) fileInput.current.value = ''
    } catch (err) {
      setError(describeAdminError(err, 'Upload failed.'))
    } finally {
      setUploading(false)
      await load() // a failed upload may still have left a FAILED document to inspect
    }
  }

  async function runAction(doc, action, successMessage) {
    setBusyId(doc.id)
    setError(null)
    setNotice(null)
    try {
      await action(doc.id)
      setNotice(successMessage)
    } catch (err) {
      setError(describeAdminError(err))
    } finally {
      setBusyId(null)
      await load()
    }
  }

  function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.name}" and its indexed chunks? This cannot be undone.`)) return
    runAction(doc, deleteDocument, `Deleted "${doc.name}".`)
  }

  return (
    <>
      <AdminNav />
      <h1 className="h3 mb-3">Documents</h1>

      <form className="card card-body mb-4" onSubmit={handleUpload}>
        <div className="row g-2 align-items-end">
          <div className="col-md-5">
            <label htmlFor="pdf-file" className="form-label">PDF file</label>
            <input
              id="pdf-file"
              ref={fileInput}
              type="file"
              accept="application/pdf,.pdf"
              className="form-control"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="col-md-4">
            <label htmlFor="doc-name" className="form-label">Display name (optional)</label>
            <input
              id="doc-name"
              className="form-control"
              value={name}
              maxLength={255}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="col-md-3">
            <button type="submit" className="btn btn-primary w-100" disabled={!file || uploading}>
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </div>
        {uploading && (
          <div className="text-muted small mt-2" role="status">
            Extracting text and generating embeddings…
          </div>
        )}
      </form>

      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {notice && <div className="alert alert-success" role="status">{notice}</div>}
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
              <th className="text-end">Actions</th>
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
                <td className="text-end text-nowrap">
                  <button
                    type="button"
                    className="btn btn-outline-secondary btn-sm me-1"
                    disabled={busyId === d.id || d.chunk_count === 0}
                    aria-label={`Re-index ${d.name}`}
                    onClick={() => runAction(d, reindexDocument, `Re-indexed "${d.name}".`)}
                  >
                    <i className="bi bi-arrow-repeat" /> Re-index
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline-danger btn-sm"
                    disabled={busyId === d.id}
                    aria-label={`Delete ${d.name}`}
                    onClick={() => handleDelete(d)}
                  >
                    <i className="bi bi-trash" /> Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
