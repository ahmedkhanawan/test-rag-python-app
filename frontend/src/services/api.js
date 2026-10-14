import axios from 'axios'

// Base URL comes from the environment; "/api" works with the Vite dev proxy.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// Window event fired when the server rejects the stored admin token.
export const UNAUTHORIZED_EVENT = 'cka:unauthorized'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// Late-bound token getter (set by services/auth.js) avoids a circular import.
let tokenGetter = () => null
export function setTokenGetter(fn) {
  tokenGetter = fn
}

api.interceptors.request.use((config) => {
  const token = tokenGetter()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // A 401 on anything but the login call means the token is missing/expired.
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    return Promise.reject(error)
  },
)

export default api
