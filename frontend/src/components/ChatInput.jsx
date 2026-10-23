export default function ChatInput({ value, onChange, onSubmit, disabled, sending }) {
  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit()
  }
  return (
    <form onSubmit={handleSubmit} className="input-group mt-3">
      <input
        type="text"
        className="form-control"
        placeholder="Ask a question about company documents…"
        aria-label="Question"
        maxLength={4000}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || sending}
      />
      <button type="submit" className="btn btn-primary" disabled={disabled || sending || !value.trim()}>
        <i className="bi bi-send me-1" />
        Send
      </button>
    </form>
  )
}
