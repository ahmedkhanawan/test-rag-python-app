/** Turn an Axios error from POST /api/chat into a user-facing message. */
export function describeChatError(error) {
  const status = error?.response?.status
  if (!error?.response) return 'Cannot reach the backend. Check that the API is running.'
  if (status === 404) return 'This conversation no longer exists on the server. Start a new conversation.'
  if (status === 422) return 'Please enter a valid question.'
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  return 'Something went wrong. Please try again.'
}
