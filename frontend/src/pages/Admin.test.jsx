import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'
import { getAdminStats, getDocuments } from '../services/admin.js'
import * as auth from '../services/auth.js'
import { getHealth } from '../services/health.js'

vi.mock('../services/health.js', () => ({ getHealth: vi.fn() }))
vi.mock('../services/admin.js', () => ({ getAdminStats: vi.fn(), getDocuments: vi.fn() }))
vi.mock('../services/auth.js', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, login: vi.fn() }
})

const STATS = {
  documents: 3,
  documents_by_status: { PENDING: 0, PROCESSING: 0, READY: 2, FAILED: 1 },
  chunks: 17,
  conversations: 4,
  messages: 9,
}
const DOCS = [
  { id: 'd1', name: 'Handbook', filename: 'handbook.pdf', status: 'READY', chunk_count: 12, created_at: '2026-01-02T10:00:00Z', updated_at: '2026-01-02T10:00:00Z' },
  { id: 'd2', name: 'Broken', filename: 'broken.pdf', status: 'FAILED', chunk_count: 0, created_at: '2026-01-03T10:00:00Z', updated_at: '2026-01-03T10:00:00Z' },
]

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

function signIn() {
  auth.setToken('test-token')
}

describe('admin panel', () => {
  beforeEach(() => {
    auth.logout()
    sessionStorage.clear()
    getHealth.mockResolvedValue({ status: 'ok' })
    getAdminStats.mockReset().mockResolvedValue(STATS)
    getDocuments.mockReset().mockResolvedValue(DOCS)
    auth.login.mockReset()
  })

  it('redirects unauthenticated visitors from /admin to the login page', async () => {
    renderAt('/admin')
    expect(await screen.findByRole('heading', { name: 'Admin login' })).toBeInTheDocument()
    expect(getAdminStats).not.toHaveBeenCalled()
  })

  it('logs in and lands on the dashboard with statistics', async () => {
    auth.login.mockImplementation(async () => auth.setToken('test-token'))
    const user = userEvent.setup()
    renderAt('/admin')
    await user.type(await screen.findByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(auth.login).toHaveBeenCalledWith('admin', 'secret')
    expect(await screen.findByRole('heading', { name: 'Admin dashboard' })).toBeInTheDocument()
    expect(await screen.findByText('17')).toBeInTheDocument() // chunks
    expect(screen.getByText('Documents by status')).toBeInTheDocument()
  })

  it('shows an error for invalid credentials and stays on the login page', async () => {
    auth.login.mockRejectedValue({ response: { status: 401 } })
    const user = userEvent.setup()
    renderAt('/login')
    await user.type(await screen.findByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'nope')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password')
    expect(screen.getByRole('heading', { name: 'Admin login' })).toBeInTheDocument()
  })

  it('lists documents with status badges and chunk counts', async () => {
    signIn()
    renderAt('/admin/documents')
    expect(await screen.findByText('Handbook')).toBeInTheDocument()
    expect(screen.getByText('READY')).toHaveClass('text-bg-success')
    expect(screen.getByText('FAILED')).toHaveClass('text-bg-danger')
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('shows empty and error states for documents', async () => {
    signIn()
    getDocuments.mockResolvedValueOnce([])
    const { unmount } = renderAt('/admin/documents')
    expect(await screen.findByText('No documents have been ingested yet.')).toBeInTheDocument()
    unmount()

    getDocuments.mockRejectedValueOnce({ response: { status: 500 } })
    renderAt('/admin/documents')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load documents.')
  })

  it('shows an error state for the dashboard', async () => {
    signIn()
    getAdminStats.mockRejectedValue({ response: { status: 500 } })
    renderAt('/admin')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load statistics.')
  })

  it('log out returns to the login page', async () => {
    signIn()
    const user = userEvent.setup()
    renderAt('/admin')
    await screen.findByRole('heading', { name: 'Admin dashboard' })
    await user.click(screen.getByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Admin login' })).toBeInTheDocument()
    expect(auth.getToken()).toBeNull()
  })

  it('sends the user to login when the API reports an expired token', async () => {
    signIn()
    renderAt('/admin')
    await screen.findByRole('heading', { name: 'Admin dashboard' })
    const { UNAUTHORIZED_EVENT } = await import('../services/api.js')
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Admin login' })).toBeInTheDocument(),
    )
  })
})
