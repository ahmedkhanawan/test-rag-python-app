import api from './api.js'

// POST /api/chat. Used by the chat UI in the next milestone.
export async function sendChatMessage(question, conversationId = null) {
  const { data } = await api.post('/chat', {
    question,
    conversation_id: conversationId,
  })
  return data
}
