import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'
import {
  deleteDocument,
  getAdminStats,
  getDocuments,
  getEvaluationRun,
  getEvaluationRuns,
  reindexDocument,
  searchRetrieval,
  uploadDocument,
} from '../services/admin.js'
import * as auth from '../services/auth.js'
import { getHealth } from '../services/health.js'

vi.mock('../services/health.js', () => ({ getHealth: vi.fn() }))
vi.mock('../services/admin.js', () => ({
  getAdminStats: vi.fn(),
  getDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  reindexDocument: vi.fn(),
  deleteDocument: vi.fn(),
  searchRetrieval: vi.fn(),
  getEvaluationRuns: vi.fn(),
  getEvaluationRun: vi.fn(),
}))
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
    uploadDocument.mockReset()
    reindexDocument.mockReset()
    deleteDocument.mockReset()
    searchRetrieval.mockReset()
    getEvaluationRuns.mockReset()
    getEvaluationRun.mockReset()
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

  describe('document management', () => {
    const pdf = () => new File(['%PDF-1.4'], 'policy.pdf', { type: 'application/pdf' })

    it('uploads a PDF with an optional name and refreshes the list', async () => {
      signIn()
      uploadDocument.mockResolvedValue({ name: 'Policy', chunk_count: 2 })
      const user = userEvent.setup()
      renderAt('/admin/documents')
      await screen.findByText('Handbook')
      expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled()

      await user.upload(screen.getByLabelText('PDF file'), pdf())
      await user.type(screen.getByLabelText('Display name (optional)'), 'Policy')
      await user.click(screen.getByRole('button', { name: 'Upload' }))

      expect(uploadDocument).toHaveBeenCalledWith(expect.objectContaining({ name: 'policy.pdf' }), 'Policy')
      expect(await screen.findByText('Uploaded "Policy" (2 chunks).')).toBeInTheDocument()
      expect(getDocuments).toHaveBeenCalledTimes(2)
    })

    it('shows the server error when an upload fails and still refreshes', async () => {
      signIn()
      uploadDocument.mockRejectedValue({
        response: { status: 422, data: { detail: 'The file is not a valid PDF' } },
      })
      const user = userEvent.setup()
      renderAt('/admin/documents')
      await screen.findByText('Handbook')
      await user.upload(screen.getByLabelText('PDF file'), pdf())
      await user.click(screen.getByRole('button', { name: 'Upload' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('The file is not a valid PDF')
      await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(2))
    })

    it('re-indexes a document', async () => {
      signIn()
      reindexDocument.mockResolvedValue({})
      const user = userEvent.setup()
      renderAt('/admin/documents')
      await user.click(await screen.findByRole('button', { name: 'Re-index Handbook' }))
      expect(reindexDocument).toHaveBeenCalledWith('d1')
      expect(await screen.findByText('Re-indexed "Handbook".')).toBeInTheDocument()
      // a document with no chunks cannot be re-indexed
      expect(screen.getByRole('button', { name: 'Re-index Broken' })).toBeDisabled()
    })

    it('shows an error when re-indexing fails', async () => {
      signIn()
      reindexDocument.mockRejectedValue({
        response: { status: 502, data: { detail: 'Embedding service failed' } },
      })
      const user = userEvent.setup()
      renderAt('/admin/documents')
      await user.click(await screen.findByRole('button', { name: 'Re-index Handbook' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Embedding service failed')
    })

    it('deletes only after confirmation', async () => {
      signIn()
      deleteDocument.mockResolvedValue()
      const confirm = vi.spyOn(window, 'confirm')
      const user = userEvent.setup()
      renderAt('/admin/documents')
      const button = await screen.findByRole('button', { name: 'Delete Handbook' })

      confirm.mockReturnValueOnce(false)
      await user.click(button)
      expect(deleteDocument).not.toHaveBeenCalled()

      confirm.mockReturnValueOnce(true)
      await user.click(button)
      expect(deleteDocument).toHaveBeenCalledWith('d1')
      expect(await screen.findByText('Deleted "Handbook".')).toBeInTheDocument()
      confirm.mockRestore()
    })
  })

  describe('retrieval playground', () => {
    const RESULT = {
      question: 'leave?',
      results: [
        { rank: 1, score: 0.8123, document_id: 'd1', document_name: 'Leave Policy', chunk_id: 'c1', chunk_index: 0, page_number: 2, section: 'Leave', text: '25 days of leave' },
        { rank: 2, score: 0.4, document_id: 'd2', document_name: 'Remote Policy', chunk_id: 'c2', chunk_index: 3, page_number: null, section: null, text: 'work from home' },
      ],
    }

    it('shows retrieved chunks with ranks and scores', async () => {
      signIn()
      searchRetrieval.mockResolvedValue(RESULT)
      const user = userEvent.setup()
      renderAt('/admin/retrieval')
      expect(screen.getByRole('button', { name: 'Search' })).toBeDisabled()
      await user.type(await screen.findByLabelText('Question'), 'leave?')
      await user.selectOptions(screen.getByLabelText('Top K'), '3')
      await user.click(screen.getByRole('button', { name: 'Search' }))

      expect(searchRetrieval).toHaveBeenCalledWith('leave?', 3)
      const chunks = await screen.findAllByTestId('retrieved-chunk')
      expect(chunks).toHaveLength(2)
      expect(chunks[0]).toHaveTextContent('Leave Policy')
      expect(chunks[0]).toHaveTextContent('Page 2')
      expect(chunks[0]).toHaveTextContent('score 0.812')
      expect(chunks[0]).toHaveTextContent('25 days of leave')
    })

    it('shows an empty state and an error state', async () => {
      signIn()
      searchRetrieval.mockResolvedValueOnce({ question: 'x', results: [] })
      const user = userEvent.setup()
      renderAt('/admin/retrieval')
      await user.type(await screen.findByLabelText('Question'), 'x')
      await user.click(screen.getByRole('button', { name: 'Search' }))
      expect(await screen.findByText(/No chunks were retrieved/)).toBeInTheDocument()

      searchRetrieval.mockRejectedValueOnce({ response: { status: 503, data: { detail: 'Document search is unavailable' } } })
      await user.click(screen.getByRole('button', { name: 'Search' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Document search is unavailable')
    })
  })

  describe('evaluation page', () => {
    const chunk = (over) => ({ rank: 1, score: 0.61, chunk_id: 'c1', document_name: 'Handbook', page_number: 1, chunk_index: 0, text: 'chunk text', relevant: true, facts: ['f'], ...over })
    const RUNS = [
      { id: 'r-ret', started_at: '2026-01-02T00:00:00Z', mode: 'retrieval', aborted: false },
      { id: 'r-full', started_at: '2026-01-01T00:00:00Z', mode: 'full', aborted: false },
    ]
    const FULL = {
      id: 'r-full', mode: 'full', aborted: false,
      config: { embedding_model: 'text-embedding-3-small', chat_model: 'gpt-5.4-mini', k: 5 },
      usage: { embedding_tokens: 425, chat_prompt_tokens: 30269, chat_completion_tokens: 1017 },
      aggregate: {
        questions: 2, evaluated: 2, passed: 1, mean_latency_ms: 1455,
        retrieval: { k: 5, recall_at_k: 1, hit_rate_at_k: 1, mrr: 0.951, mean_top_score_answerable: 0.6, mean_top_score_unsupported: 0.39 },
        answers: { correct_rate: 0.9, correct_refusal_rate: 1, false_refusal_rate: 0, citation_supported_rate: 1, numbers_grounded_rate: 1 },
        by_category: { direct: { questions: 1, evaluated: 1, passed: 1 }, unsupported: { questions: 1, evaluated: 1, passed: 0 } },
      },
      results: [
        { id: 'q01', category: 'direct', question: 'How many leave days?', expected_answer: '20 days', answer: '20 days [Source 1]', passed: true, failures: [], failure_stage: null, retrieval: { retrieved: [chunk()] } },
        { id: 'q02', category: 'unsupported', question: 'Dress code?', expected_answer: 'Not in documents', answer: 'Business casual [Source 1]', passed: false, failures: ['did not refuse an unsupported question'], failure_stage: 'generation', retrieval: { retrieved: [chunk({ relevant: false, text: 'unrelated' })] } },
      ],
    }

    it('shows aggregate metrics and per-question details for the newest full run', async () => {
      signIn()
      getEvaluationRuns.mockResolvedValue(RUNS)
      getEvaluationRun.mockResolvedValue(FULL)
      renderAt('/admin/evaluation')
      expect(await screen.findByTestId('metric-MRR')).toHaveTextContent('0.951')
      expect(getEvaluationRun).toHaveBeenCalledWith('r-full')
      expect(screen.getByTestId('metric-Recall@5')).toHaveTextContent('100.0%')
      expect(screen.getByTestId('metric-Correct answers')).toHaveTextContent('90.0%')
      expect(screen.getByText(/30269 prompt/)).toBeInTheDocument()
      const items = screen.getAllByTestId('eval-question')
      expect(items).toHaveLength(2)
      expect(items[1]).toHaveTextContent('did not refuse an unsupported question')
      expect(items[1]).toHaveTextContent('generation failure')
      expect(items[0]).toHaveTextContent('0.610')
    })

    it('filters to failures only', async () => {
      signIn()
      getEvaluationRuns.mockResolvedValue(RUNS)
      getEvaluationRun.mockResolvedValue(FULL)
      const user = userEvent.setup()
      renderAt('/admin/evaluation')
      await screen.findAllByTestId('eval-question')
      await user.click(screen.getByLabelText('Failures only'))
      const items = screen.getAllByTestId('eval-question')
      expect(items).toHaveLength(1)
      expect(items[0]).toHaveTextContent('Dress code?')
    })

    it('shows an empty state when no runs exist and an error state on failure', async () => {
      signIn()
      getEvaluationRuns.mockResolvedValueOnce([])
      const { unmount } = renderAt('/admin/evaluation')
      expect(await screen.findByText('No evaluation runs have been saved yet.')).toBeInTheDocument()
      unmount()

      getEvaluationRuns.mockRejectedValueOnce({ response: { status: 500 } })
      renderAt('/admin/evaluation')
      expect(await screen.findByRole('alert')).toHaveTextContent('Could not load evaluation runs.')
    })

    it('labels retrieval-only runs without answer metrics', async () => {
      signIn()
      const retrievalOnly = { ...FULL, id: 'r-ret', mode: 'retrieval', usage: null, config: { ...FULL.config, chat_model: null }, aggregate: { ...FULL.aggregate, answers: undefined } }
      getEvaluationRuns.mockResolvedValue([RUNS[0]])
      getEvaluationRun.mockResolvedValue(retrievalOnly)
      renderAt('/admin/evaluation')
      expect(await screen.findByTestId('metric-MRR')).toBeInTheDocument()
      expect(screen.queryByTestId('metric-Correct answers')).not.toBeInTheDocument()
    })
  })
})
