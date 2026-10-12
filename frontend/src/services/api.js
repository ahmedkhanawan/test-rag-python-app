import axios from 'axios'

// Base URL comes from the environment; "/api" works with the Vite dev proxy.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

export default api
