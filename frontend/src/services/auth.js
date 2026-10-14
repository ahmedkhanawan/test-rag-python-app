import api, { setTokenGetter } from './api.js'

const TOKEN_KEY = 'cka.admin_token'

// sessionStorage can throw (blocked storage); fall back to an in-memory token.
let memoryToken = null

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? memoryToken
  } catch {
    return memoryToken
  }
}

setTokenGetter(() => getToken())

export function setToken(token) {
  memoryToken = token
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // ignore: in-memory token still works for this page load
  }
}

// POST /api/auth/login -> stores the JWT for the Axios interceptor.
export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password })
  setToken(data.access_token)
  return data
}

export function logout() {
  setToken(null)
}

export function describeLoginError(error) {
  if (!error?.response) return 'Cannot reach the backend. Check that the API is running.'
  if (error.response.status === 401) return 'Invalid username or password.'
  if (error.response.status === 503) return 'Authentication is not configured on the server.'
  return 'Login failed. Please try again.'
}
