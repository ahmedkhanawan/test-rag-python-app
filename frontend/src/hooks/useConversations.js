import { useCallback, useEffect, useState } from 'react'
import { loadConversations, saveConversations } from '../utils/conversationStore.js'

const TITLE_LENGTH = 40

function toTitle(question) {
  return question.length > TITLE_LENGTH ? `${question.slice(0, TITLE_LENGTH).trimEnd()}…` : question
}

/** Conversations created in this browser, newest first. */
export default function useConversations() {
  const [conversations, setConversations] = useState(loadConversations)

  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  // Add the user/assistant messages from a POST /api/chat response.
  const recordExchange = useCallback((response) => {
    const { conversation_id: id, user_message: user, assistant_message: assistant } = response
    const messages = [
      { id: user.id, role: 'user', content: user.content, createdAt: user.created_at },
      {
        id: assistant.id,
        role: 'assistant',
        content: assistant.content,
        createdAt: assistant.created_at,
        sources: response.sources ?? [],
        grounded: response.grounded,
      },
    ]
    setConversations((current) => {
      const existing = current.find((c) => c.id === id)
      const updated = {
        id,
        title: existing?.title ?? toTitle(user.content),
        updatedAt: assistant.created_at,
        messages: [...(existing?.messages ?? []), ...messages],
      }
      return [updated, ...current.filter((c) => c.id !== id)]
    })
  }, [])

  return { conversations, recordExchange }
}
