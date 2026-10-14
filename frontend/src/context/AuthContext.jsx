import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { UNAUTHORIZED_EVENT } from '../services/api.js'
import * as authService from '../services/auth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => authService.getToken())

  const login = useCallback(async (username, password) => {
    await authService.login(username, password)
    setTokenState(authService.getToken())
  }, [])

  const logout = useCallback(() => {
    authService.logout()
    setTokenState(null)
  }, [])

  // The API client signals an expired/invalid token; drop it and re-route to login.
  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, logout)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, logout)
  }, [logout])

  const value = useMemo(
    () => ({ isAuthenticated: Boolean(token), login, logout }),
    [token, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
