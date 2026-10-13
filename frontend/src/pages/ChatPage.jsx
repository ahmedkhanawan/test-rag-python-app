import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ChatInput from '../components/ChatInput.jsx'
import ConversationList from '../components/ConversationList.jsx'
import MessageBubble from '../components/MessageBubble.jsx'
import useConversations from '../hooks/useConversations.js'
import { sendChatMessage } from '../services/chat.js'
import { describeChatError } from '../utils/errors.js'

export default function ChatPage() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const { conversations, recordExchange } = useConversations()
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState(null) // question awaiting an answer
  const [errorState, setErrorState] = useState(null) // { conversationId, message }
  const bottomRef = useRef(null)

  const active = conversations.find((c) => c.id === conversationId)
  const missing = Boolean(conversationId) && !active
  const messages = active?.messages ?? []
  // An error is only shown for the conversation it happened in.
  const error = errorState?.conversationId === (conversationId ?? null) ? errorState.message : null

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages.length, pending])

  async function handleSubmit() {
    const text = question.trim()
    if (!text || pending) return
    setPending(text)
    setErrorState(null)
    try {
      const response = await sendChatMessage(text, conversationId ?? null)
      recordExchange(response)
      setQuestion('')
      if (!conversationId) navigate(`/chat/${response.conversation_id}`)
    } catch (e) {
      // the question stays in the input for a retry
      setErrorState({ conversationId: conversationId ?? null, message: describeChatError(e) })
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="row g-4">
      <div className="col-md-3">
        <ConversationList conversations={conversations} activeId={conversationId} />
      </div>
      <div className="col-md-9">
        <h1 className="h4 mb-3">Ask Assistant</h1>
        {missing ? (
          <div className="alert alert-warning">
            This conversation was not found in this browser. <Link to="/chat">Start a new conversation</Link>.
          </div>
        ) : (
          <>
            <div className="border rounded-3 bg-light p-3" style={{ height: '60vh', overflowY: 'auto' }}>
              {messages.length === 0 && !pending && (
                <div className="text-center text-muted mt-5">
                  <i className="bi bi-chat-dots fs-1" />
                  <p className="mt-2">Ask a question about the company documents to get started.</p>
                </div>
              )}
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {pending && (
                <>
                  <MessageBubble message={{ role: 'user', content: pending }} />
                  <div className="d-flex align-items-center text-muted" role="status">
                    <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
                    Thinking…
                  </div>
                </>
              )}
              <div ref={bottomRef} />
            </div>
            {error && (
              <div className="alert alert-danger mt-3 mb-0" role="alert">
                {error}
              </div>
            )}
            <ChatInput
              value={question}
              onChange={setQuestion}
              onSubmit={handleSubmit}
              sending={Boolean(pending)}
            />
          </>
        )}
      </div>
    </div>
  )
}
