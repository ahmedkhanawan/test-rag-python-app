import { Link, useNavigate } from 'react-router-dom'

export default function ConversationList({ conversations, activeId }) {
  const navigate = useNavigate()
  return (
    <div>
      <button type="button" className="btn btn-primary w-100 mb-3" onClick={() => navigate('/chat')}>
        <i className="bi bi-plus-lg me-1" />
        New conversation
      </button>
      {conversations.length === 0 ? (
        <p className="small text-muted">No conversations yet.</p>
      ) : (
        <div className="list-group" aria-label="Conversations">
          {conversations.map((c) => (
            <Link
              key={c.id}
              to={`/chat/${c.id}`}
              className={`list-group-item list-group-item-action text-truncate ${
                c.id === activeId ? 'active' : ''
              }`}
              aria-current={c.id === activeId ? 'true' : undefined}
            >
              {c.title}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
