import SourceList from './SourceList.jsx'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`d-flex mb-3 ${isUser ? 'justify-content-end' : 'justify-content-start'}`}>
      <div
        className={`p-3 rounded-3 ${isUser ? 'bg-primary text-white' : 'bg-white border'}`}
        style={{ maxWidth: '85%' }}
        data-testid={`message-${message.role}`}
      >
        <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
        {!isUser && message.grounded === false && (
          <div className="small text-muted mt-2">No matching company documents were found.</div>
        )}
        {!isUser && <SourceList sources={message.sources} />}
      </div>
    </div>
  )
}
