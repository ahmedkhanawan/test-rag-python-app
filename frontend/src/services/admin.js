import api from './api.js'

// Admin endpoints; the JWT is attached by the Axios interceptor in api.js.
export async function getAdminStats() {
  const { data } = await api.get('/admin/stats')
  return data
}

export async function getDocuments() {
  const { data } = await api.get('/documents')
  return data
}

// POST /api/documents/upload (multipart). Ingests and indexes the PDF; can take a while.
export async function uploadDocument(file, name) {
  const form = new FormData()
  form.append('file', file)
  if (name?.trim()) form.append('name', name.trim())
  const { data } = await api.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function reindexDocument(id) {
  const { data } = await api.post(`/documents/${id}/reindex`)
  return data
}

export async function deleteDocument(id) {
  await api.delete(`/documents/${id}`)
}

// Retrieval only (no LLM): returns ranked chunks with similarity scores.
export async function searchRetrieval(question, topK) {
  const { data } = await api.post('/retrieval/search', {
    question,
    top_k: topK || null,
  })
  return data
}

// Saved evaluation runs (produced by `python -m scripts.run_evaluation` in backend/).
export async function getEvaluationRuns() {
  const { data } = await api.get('/admin/evaluation/runs')
  return data
}

export async function getEvaluationRun(id) {
  const { data } = await api.get(`/admin/evaluation/runs/${encodeURIComponent(id)}`)
  return data
}
