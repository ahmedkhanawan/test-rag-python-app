import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { describeLoginError } from '../services/auth.js'

export default function LoginPage() {
  const { isAuthenticated, login } = useAuth()
  const navigate = useNavigate()
  const from = useLocation().state?.from || '/admin'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)

  if (isAuthenticated) return <Navigate to={from} replace />

  async function handleSubmit(e) {
    e.preventDefault()
    setPending(true)
    setError(null)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(describeLoginError(err))
      setPending(false)
    }
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-5 col-lg-4">
        <h1 className="h3 mb-3">Admin login</h1>
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label htmlFor="username" className="form-label">Username</label>
            <input
              id="username"
              className="form-control"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="mb-3">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              id="password"
              type="password"
              className="form-control"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="alert alert-danger" role="alert">{error}</div>}
          <button type="submit" className="btn btn-primary w-100" disabled={pending}>
            {pending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
