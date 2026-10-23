import { useState } from 'react'
import AdminNav from '../components/AdminNav.jsx'
import { searchRetrieval } from '../services/admin.js'
import { describeAdminError } from '../utils/errors.js'

export default function RetrievalPlaygroundPage() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState('5')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const text = question.trim()
    if (!text || pending) return
    setPending(true)
    setError(null)
    try {
      setResult(await searchRetrieval(text, Number(topK)))
    } catch (err) {
      if (err?.response?.status !== 401) setError(describeAdminError(err, 'Search failed.'))
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <AdminNav />
      <h1 className="h3 mb-1">Retrieval playground</h1>
      <p className="text-muted">
        Inspect which chunks are retrieved for a question and how they score. No answer is
        generated.
      </p>

      <form className="row g-2 mb-4" onSubmit={handleSubmit}>
        <div className="col-md-8">
          <label htmlFor="rp-question" className="form-label">Question</label>
          <input
            id="rp-question"
            maxLength={4000}
            className="form-control"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={pending}
          />
        </div>
        <div className="col-6 col-md-2">
          <label htmlFor="rp-topk" className="form-label">Top K</label>
          <select
            id="rp-topk"
            className="form-select"
            value={topK}
            onChange={(e) => setTopK(e.target.value)}
            disabled={pending}
          >
            {[1, 3, 5, 10, 20].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div className="col-6 col-md-2 d-flex align-items-end">
          <button type="submit" className="btn btn-primary w-100" disabled={pending || !question.trim()}>
            {pending ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {result && result.results.length === 0 && (
        <p className="text-muted">No chunks were retrieved. Has any document been indexed?</p>
      )}
      {result && result.results.length > 0 && (
        <ol className="list-unstyled">
          {result.results.map((r) => (
            <li key={r.chunk_id} className="card mb-2" data-testid="retrieved-chunk">
              <div className="card-body py-2">
                <div className="d-flex justify-content-between">
                  <div>
                    <span className="badge text-bg-light border me-2">#{r.rank}</span>
                    <strong>{r.document_name}</strong>
                    <span className="text-muted small">
                      {r.page_number != null && ` · Page ${r.page_number}`}
                      {r.section && ` · ${r.section}`}
                      {` · chunk ${r.chunk_index}`}
                    </span>
                  </div>
                  <span className="badge text-bg-primary" title="Cosine similarity">
                    score {r.score.toFixed(3)}
                  </span>
                </div>
                <p className="small text-muted mb-0 mt-2" style={{ whiteSpace: 'pre-wrap' }}>
                  {r.text}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </>
  )
}
