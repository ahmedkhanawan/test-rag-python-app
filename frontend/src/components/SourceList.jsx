export default function SourceList({ sources }) {
  if (!sources?.length) return null
  return (
    <div className="mt-3 pt-2 border-top" aria-label="Sources">
      <div className="small fw-semibold text-muted mb-1">
        <i className="bi bi-file-earmark-text me-1" />
        Sources
      </div>
      <ul className="list-unstyled small mb-0">
        {sources.map((s) => (
          <li key={s.chunk_id} className="mb-1" data-testid="source">
            <details>
              <summary>
                <span className="badge text-bg-light border me-1">{s.source_number}</span>
                <strong>{s.document_name}</strong>
                {s.page_number != null && <span> · Page {s.page_number}</span>}
                {s.section && <span> · {s.section}</span>}
                <span className="text-muted"> · relevance {s.score.toFixed(2)}</span>
              </summary>
              <p className="text-muted fst-italic mt-1 mb-0">{s.text}</p>
            </details>
          </li>
        ))}
      </ul>
    </div>
  )
}
