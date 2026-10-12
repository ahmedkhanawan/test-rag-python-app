import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'
import { getHealth } from './services/health.js'

vi.mock('./services/health.js', () => ({ getHealth: vi.fn() }))

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  beforeEach(() => {
    getHealth.mockReset()
  })

  it('renders home and shows backend online', async () => {
    getHealth.mockResolvedValue({ status: 'ok' })
    renderAt('/')
    expect(screen.getByRole('heading', { name: 'Company Knowledge Assistant' })).toBeInTheDocument()
    expect(await screen.findByText('Backend online')).toBeInTheDocument()
  })

  it('shows backend offline when the health check fails', async () => {
    getHealth.mockRejectedValue(new Error('network'))
    renderAt('/')
    expect(await screen.findByText('Backend offline')).toBeInTheDocument()
  })

  it('routes to the chat placeholder', async () => {
    getHealth.mockResolvedValue({ status: 'ok' })
    renderAt('/chat')
    expect(screen.getByRole('heading', { name: 'Ask Assistant' })).toBeInTheDocument()
    await screen.findByText('Backend online')
  })

  it('renders a not-found page for unknown routes', async () => {
    getHealth.mockResolvedValue({ status: 'ok' })
    renderAt('/nope')
    expect(screen.getByText('Page not found')).toBeInTheDocument()
    await screen.findByText('Backend online')
  })
})
