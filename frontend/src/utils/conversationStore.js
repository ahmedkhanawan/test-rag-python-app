// The backend has no conversation-list endpoint yet, so the conversations this
// browser has created (with their sources) are cached in localStorage.
const KEY = 'cka.conversations.v1'

export function loadConversations() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveConversations(conversations) {
  try {
    localStorage.setItem(KEY, JSON.stringify(conversations))
  } catch {
    // Storage may be unavailable or full; the chat still works for this session.
  }
}
