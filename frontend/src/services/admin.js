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
