import { useEffect, useMemo, useState } from 'react'
import AdminNav from '../components/AdminNav.jsx'
import { getEvaluationRun, getEvaluationRuns } from '../services/admin.js'
import { describeAdminError } from '../utils/errors.js'

const pct = (v) => (v == null ? 'n/a' : `${(v * 100).toFixed(1)}%`)

function Metric({ label, value, hint }) {
  return (
    <div className="col-6 col-md-3 col-lg-2">
      <div className="card h-100 text-center">
        <div className="card-body p-2">
          <div className="fs-5 fw-semibold" data-testid={`metric-${label}`}>{value}</div>
          <div className="text-muted small" title={hint}>{label}</div>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ passed }) {
  if (passed === null || passed === undefined) return <span className="badge text-bg-secondary">not evaluated</span>
  return passed ? (
    <span className="badge text-bg-success">pass</span>
  ) : (
    <span className="badge text-bg-danger">fail</span>
  )
}

function QuestionRow({ r }) {
  return (
    <li className="list-group-item" data-testid="eval-question">
      <details>
        <summary>
          <StatusBadge passed={r.passed} />{' '}
          <span className="badge text-bg-light border">{r.id}</span>{' '}
          <span className="text-muted small">{r.category}</span> {r.question}
          {r.failure_stage && (
            <span className="badge text-bg-warning ms-2">{r.failure_stage} failure</span>
          )}
        </summary>
        <div className="mt-2 small">
          <p className="mb-1"><strong>Expected:</strong> {r.expected_answer}</p>
          {r.answer && (
            <p className="mb-1" style={{ whiteSpace: 'pre-wrap' }}><strong>Answer:</strong> {r.answer}</p>
          )}
          {r.failures?.length > 0 && (
            <ul className="text-danger">
              {r.failures.map((f) => <li key={f}>{f}</li>)}
            </ul>
          )}
          {r.retrieval && (
            <table className="table table-sm mb-0">
              <thead>
                <tr><th>#</th><th>Document</th><th>Page</th><th>Score</th><th>Relevant</th><th>Chunk text</th></tr>
              </thead>
              <tbody>
                {r.retrieval.retrieved.map((c) => (
                  <tr key={c.chunk_id}>
                    <td>{c.rank}</td>
                    <td>{c.document_name}</td>
                    <td>{c.page_number ?? '–'}</td>
                    <td>{c.score.toFixed(3)}</td>
                    <td>{c.relevant ? <span className="badge text-bg-success">yes</span> : <span className="text-muted">no</span>}</td>
                    <td className="text-muted">{c.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </details>
    </li>
  )
}

export default function EvaluationPage() {
  const [runs, setRuns] = useState(null)
  const [runId, setRunId] = useState(null)
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)
  const [failuresOnly, setFailuresOnly] = useState(false)
  const [category, setCategory] = useState('all')

  useEffect(() => {
    let active = true
    getEvaluationRuns()
      .then((data) => {
        if (!active) return
        setRuns(data)
        // Prefer the newest full run (it has answer metrics); otherwise the newest run.
        const preferred = data.find((r) => r.mode === 'full') ?? data[0]
        if (preferred) setRunId(preferred.id)
      })
      .catch((err) => {
        if (active && err?.response?.status !== 401) setError(describeAdminError(err, 'Could not load evaluation runs.'))
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!runId) return undefined
    let active = true
    getEvaluationRun(runId)
      .then((data) => active && setRun(data))
      .catch((err) => {
        if (active && err?.response?.status !== 401) setError(describeAdminError(err, 'Could not load the run.'))
      })
    return () => {
      active = false
    }
  }, [runId])

  const shown = useMemo(() => {
    if (!run) return []
    return run.results.filter(
      (r) => (category === 'all' || r.category === category) && (!failuresOnly || r.passed === false),
    )
  }, [run, failuresOnly, category])

  const agg = run?.aggregate
  const ans = agg?.answers

  return (
    <>
      <AdminNav />
      <h1 className="h3 mb-1">Evaluation</h1>
      <p className="text-muted">
        Results of saved evaluation runs. Runs call the OpenAI APIs, so they are started from the
        command line: <code>uv run python -m scripts.run_evaluation --mode full</code>
      </p>

      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {!runs && !error && <div className="text-muted" role="status">Loading…</div>}
      {runs && runs.length === 0 && (
        <p className="text-muted">No evaluation runs have been saved yet.</p>
      )}

      {runs && runs.length > 0 && (
        <div className="mb-3">
          <label htmlFor="eval-run" className="form-label">Run</label>
          <select
            id="eval-run"
            className="form-select"
            value={runId ?? ''}
            onChange={(e) => {
              setRun(null)
              setRunId(e.target.value)
            }}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {new Date(r.started_at).toLocaleString()} · {r.mode}
                {r.aborted ? ' · aborted' : ''}
              </option>
            ))}
          </select>
        </div>
      )}

      {runId && !run && !error && <div className="text-muted" role="status">Loading run…</div>}
      {run && (
        <>
          {run.aborted && (
            <div className="alert alert-warning">
              This run was stopped early after repeated API errors; results are partial.
            </div>
          )}
          <div className="row g-2 mb-3">
            <Metric label="Questions" value={`${agg.evaluated}/${agg.questions} judged`} />
            <Metric label="Passed" value={`${agg.passed}/${agg.evaluated}`} />
            <Metric label={`Recall@${agg.retrieval.k}`} value={pct(agg.retrieval.recall_at_k)} hint="Share of required facts found in the top-K chunks (answerable questions)" />
            <Metric label={`Hit@${agg.retrieval.k}`} value={pct(agg.retrieval.hit_rate_at_k)} hint="Questions with at least one relevant chunk in the top-K" />
            <Metric label="MRR" value={agg.retrieval.mrr == null ? 'n/a' : agg.retrieval.mrr.toFixed(3)} hint="Mean reciprocal rank of the first relevant chunk" />
            {ans && (
              <>
                <Metric label="Correct answers" value={pct(ans.correct_rate)} hint="Answerable questions whose answer contains every expected fact" />
                <Metric label="Correct refusals" value={pct(ans.correct_refusal_rate)} hint="Unsupported questions the assistant declined to answer" />
                <Metric label="False refusals" value={pct(ans.false_refusal_rate)} hint="Answerable questions wrongly refused" />
                <Metric label="Citations supported" value={pct(ans.citation_supported_rate)} hint="Answers citing at least one chunk that contains the expected evidence" />
                <Metric label="Numbers grounded" value={pct(ans.numbers_grounded_rate)} hint="Answers whose numbers all appear in the retrieved context (heuristic)" />
              </>
            )}
            <Metric label="Mean latency" value={agg.mean_latency_ms == null ? 'n/a' : `${Math.round(agg.mean_latency_ms)} ms`} />
          </div>
          <p className="text-muted small">
            Mean top score: answerable {agg.retrieval.mean_top_score_answerable?.toFixed(3) ?? 'n/a'} ·
            unsupported {agg.retrieval.mean_top_score_unsupported?.toFixed(3) ?? 'n/a'}.
            {' '}Models: {run.config.embedding_model}{run.config.chat_model ? `, ${run.config.chat_model}` : ''}.
            {run.usage && (
              <>
                {' '}Tokens: {run.usage.embedding_tokens} embedding, {run.usage.chat_prompt_tokens} prompt,{' '}
                {run.usage.chat_completion_tokens} completion (cost not computed).
              </>
            )}
          </p>

          <div className="d-flex gap-3 align-items-center mb-2">
            <select
              aria-label="Category"
              className="form-select form-select-sm w-auto"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="all">All categories</option>
              {Object.keys(agg.by_category).map((c) => (
                <option key={c} value={c}>{c} ({agg.by_category[c].passed}/{agg.by_category[c].evaluated})</option>
              ))}
            </select>
            <div className="form-check">
              <input
                id="eval-failures"
                type="checkbox"
                className="form-check-input"
                checked={failuresOnly}
                onChange={(e) => setFailuresOnly(e.target.checked)}
              />
              <label htmlFor="eval-failures" className="form-check-label">Failures only</label>
            </div>
          </div>
          {shown.length === 0 ? (
            <p className="text-muted">No questions match the filter.</p>
          ) : (
            <ul className="list-group">
              {shown.map((r) => <QuestionRow key={r.id} r={r} />)}
            </ul>
          )}
        </>
      )}
    </>
  )
}
