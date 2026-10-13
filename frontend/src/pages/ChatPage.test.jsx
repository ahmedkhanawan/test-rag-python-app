import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'
import { sendChatMessage } from '../services/chat.js'
import { getHealth } from '../services/health.js'

vi.mock('../services/chat.js', () => ({ sendChatMessage: vi.fn() }))
vi.mock('../services/health.js', () => ({ getHealth: vi.fn() }))

function response(overrides = {}) {
  return {
    conversation_id: 'c1',
    user_message: { id: 'u1', content: 'How many leave days?', created_at: '2026-01-01T10:00:00Z' },
    assistant_message: { id: 'a1', content: '25 days [Source 1].', created_at: '2026-01-01T10:00:02Z' },
    grounded: true,
    sources: [
      {
        source_number: 1,
        document_id: 'd1',
        document_name: 'Leave Policy',
        chunk_id: 'k1',
        chunk_index: 0,
        page_number: 3,
        section: 'Annual Leave',
        score: 0.8123,
        text: 'Employees receive 25 days.',
      },
    ],
    ...overrides,
  }
}

function renderAt(path = '/chat') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

async function ask(user, text) {
  await user.type(screen.getByLabelText('Question'), text)
  await user.click(screen.getByRole('button', { name: /send/i }))
}

describe('Chat UI', () => {
  beforeEach(() => {
    localStorage.clear()
    sendChatMessage.mockReset()
    getHealth.mockResolvedValue({ status: 'ok' })
  })

  it('shows the empty state and disables send for blank input', async () => {
    renderAt()
    expect(screen.getByText(/ask a question about the company documents/i)).toBeInTheDocument()
    expect(screen.getByText('No conversations yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
    await screen.findByText('Backend online')
  })

  it('sends a question and shows the answer with structured sources', async () => {
    sendChatMessage.mockResolvedValue(response())
    const user = userEvent.setup()
    renderAt()
    await ask(user, 'How many leave days?')

    expect(sendChatMessage).toHaveBeenCalledWith('How many leave days?', null)
    expect(await screen.findByText('25 days [Source 1].')).toBeInTheDocument()
    expect(screen.getByTestId('message-user')).toHaveTextContent('How many leave days?')

    const source = screen.getByTestId('source')
    expect(source).toHaveTextContent('Leave Policy')
    expect(source).toHaveTextContent('Page 3')
    expect(source).toHaveTextContent('Annual Leave')
    expect(source).toHaveTextContent('relevance 0.81')
    expect(source).toHaveTextContent('Employees receive 25 days.')

    // new conversation appears in the list and the input is cleared
    const list = screen.getByLabelText('Conversations')
    expect(within(list).getByText('How many leave days?')).toBeInTheDocument()
    expect(screen.getByLabelText('Question')).toHaveValue('')
  })

  it('shows a loading state while waiting and disables input', async () => {
    let resolve
    sendChatMessage.mockReturnValue(new Promise((r) => (resolve = r)))
    const user = userEvent.setup()
    renderAt()
    await ask(user, 'Slow question')

    expect(await screen.findByText('Thinking…')).toBeInTheDocument()
    expect(screen.getByTestId('message-user')).toHaveTextContent('Slow question')
    expect(screen.getByLabelText('Question')).toBeDisabled()

    resolve(response())
    expect(await screen.findByText('25 days [Source 1].')).toBeInTheDocument()
    expect(screen.queryByText('Thinking…')).not.toBeInTheDocument()
  })

  it('shows the backend error and keeps the question for retry', async () => {
    sendChatMessage.mockRejectedValue({
      response: { status: 503, data: { detail: 'Document search is unavailable' } },
    })
    const user = userEvent.setup()
    renderAt()
    await ask(user, 'Will fail')

    expect(await screen.findByRole('alert')).toHaveTextContent('Document search is unavailable')
    expect(screen.getByLabelText('Question')).toHaveValue('Will fail')
    expect(screen.queryByTestId('message-assistant')).not.toBeInTheDocument()
    expect(screen.queryByText('Thinking…')).not.toBeInTheDocument()
  })

  it('shows a network error when the backend is unreachable', async () => {
    sendChatMessage.mockRejectedValue(new Error('Network Error'))
    const user = userEvent.setup()
    renderAt()
    await ask(user, 'Hello')
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot reach the backend/i)
  })

  it('continues an existing conversation, then starts a new one', async () => {
    sendChatMessage
      .mockResolvedValueOnce(response())
      .mockResolvedValueOnce(
        response({
          user_message: { id: 'u2', content: 'And sick days?', created_at: '2026-01-01T10:05:00Z' },
          assistant_message: { id: 'a2', content: '10 sick days.', created_at: '2026-01-01T10:05:02Z' },
        }),
      )
      .mockResolvedValueOnce(
        response({
          conversation_id: 'c2',
          user_message: { id: 'u3', content: 'Remote work?', created_at: '2026-01-01T11:00:00Z' },
          assistant_message: { id: 'a3', content: 'Three days.', created_at: '2026-01-01T11:00:02Z' },
          sources: [],
        }),
      )
    const user = userEvent.setup()
    renderAt()

    await ask(user, 'How many leave days?')
    await screen.findByText('25 days [Source 1].')
    await ask(user, 'And sick days?')
    await screen.findByText('10 sick days.')
    expect(sendChatMessage).toHaveBeenLastCalledWith('And sick days?', 'c1')
    expect(screen.getAllByTestId('message-user')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: /new conversation/i }))
    expect(screen.queryByText('10 sick days.')).not.toBeInTheDocument()
    expect(screen.getByText(/ask a question about the company documents/i)).toBeInTheDocument()

    await ask(user, 'Remote work?')
    await screen.findByText('Three days.')
    expect(sendChatMessage).toHaveBeenLastCalledWith('Remote work?', null)
    expect(within(screen.getByLabelText('Conversations')).getAllByRole('link')).toHaveLength(2)
  })

  it('selects a saved conversation from the list and shows its sources', async () => {
    sendChatMessage.mockResolvedValue(response())
    const user = userEvent.setup()
    renderAt()
    await ask(user, 'How many leave days?')
    await screen.findByText('25 days [Source 1].')
    await user.click(screen.getByRole('button', { name: /new conversation/i }))
    expect(screen.queryByTestId('source')).not.toBeInTheDocument()

    await user.click(within(screen.getByLabelText('Conversations')).getByText('How many leave days?'))
    expect(await screen.findByText('25 days [Source 1].')).toBeInTheDocument()
    expect(screen.getByTestId('source')).toHaveTextContent('Leave Policy')
  })

  it('restores conversations from localStorage on load', async () => {
    sendChatMessage.mockResolvedValue(response())
    const user = userEvent.setup()
    const first = renderAt()
    await ask(user, 'How many leave days?')
    await screen.findByText('25 days [Source 1].')
    first.unmount()

    renderAt('/chat/c1')
    expect(await screen.findByText('25 days [Source 1].')).toBeInTheDocument()
    expect(screen.getByTestId('source')).toBeInTheDocument()
  })

  it('shows a not-found message for an unknown conversation id', async () => {
    renderAt('/chat/unknown')
    expect(screen.getByText(/was not found in this browser/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByLabelText('Question')).not.toBeInTheDocument())
  })

  it('notes when no documents matched and shows no sources', async () => {
    sendChatMessage.mockResolvedValue(
      response({
        assistant_message: { id: 'a1', content: "I couldn't find information.", created_at: '2026-01-01T10:00:02Z' },
        grounded: false,
        sources: [],
      }),
    )
    const user = userEvent.setup()
    renderAt()
    await ask(user, 'Unknown topic')
    expect(await screen.findByText("I couldn't find information.")).toBeInTheDocument()
    expect(screen.getByText(/no matching company documents/i)).toBeInTheDocument()
    expect(screen.queryByTestId('source')).not.toBeInTheDocument()
  })
})
