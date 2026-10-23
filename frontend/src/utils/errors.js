/** Turn an Axios error from POST /api/chat into a user-facing message. */
export function describeChatError(error) {
  const status = error?.response?.status
  if (!error?.response) return 'Cannot reach the backend. Check that the API is running.'
  if (status === 404) return 'This conversation no longer exists on the server. Start a new conversation.'
  if (status === 422) return 'Please enter a valid question.'
  if (status === 429) return 'Too many requests. Please wait a moment and try again.'
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  return 'Something went wrong. Please try again.'
}

/** Turn an Axios error from an admin endpoint into a user-facing message. */
export function describeAdminError(error, fallback = 'Something went wrong. Please try again.') {
  if (!error?.response) return 'Cannot reach the backend. Check that the API is running.'
  const detail = error.response.data?.detail
  // FastAPI validation errors (422) send a list; our own errors send a string.
  if (typeof detail === 'string') return detail
  if (error.response.status === 422) return 'The request was not valid.'
  return fallback
}
