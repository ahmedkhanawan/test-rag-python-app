import { afterEach, describe, expect, it } from 'vitest'
import api from './api.js'
import { sendChatMessage } from './chat.js'
import { getHealth } from './health.js'

const original = api.defaults.adapter

function fakeAdapter(data, seen) {
  return async (config) => {
    seen.push(config)
    return { data, status: 200, statusText: 'OK', headers: {}, config }
  }
}

afterEach(() => {
  api.defaults.adapter = original
})

describe('api client', () => {
  it('uses the configured base URL', () => {
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('getHealth calls GET /health', async () => {
    const seen = []
    api.defaults.adapter = fakeAdapter({ status: 'ok' }, seen)
    expect(await getHealth()).toEqual({ status: 'ok' })
    expect(seen[0].method).toBe('get')
    expect(seen[0].url).toBe('/health')
  })

  it('sendChatMessage posts question and conversation_id', async () => {
    const seen = []
    api.defaults.adapter = fakeAdapter({ conversation_id: 'c1' }, seen)
    await sendChatMessage('hi', 'c1')
    expect(seen[0].method).toBe('post')
    expect(seen[0].url).toBe('/chat')
    expect(JSON.parse(seen[0].data)).toEqual({ question: 'hi', conversation_id: 'c1' })
  })
})
