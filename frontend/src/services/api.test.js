import { afterEach, describe, expect, it, vi } from 'vitest'
import api, { UNAUTHORIZED_EVENT } from './api.js'
import { getDocuments } from './admin.js'
import { getToken, logout, setToken } from './auth.js'
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

  it('attaches the stored JWT as a Bearer header', async () => {
    const seen = []
    api.defaults.adapter = fakeAdapter([], seen)
    setToken('abc')
    await getDocuments()
    expect(seen[0].headers.Authorization).toBe('Bearer abc')
    logout()
    expect(getToken()).toBeNull()
    await getDocuments()
    expect(seen[1].headers.Authorization).toBeUndefined()
  })

  it('fires the unauthorized event on a 401 (not for login)', async () => {
    const handler = vi.fn()
    window.addEventListener(UNAUTHORIZED_EVENT, handler)
    api.defaults.adapter = async (config) => {
      const err = new Error('401')
      err.config = config
      err.response = { status: 401, config }
      return Promise.reject(err)
    }
    await expect(getDocuments()).rejects.toBeTruthy()
    expect(handler).toHaveBeenCalledTimes(1)
    await expect(api.post('/auth/login', {})).rejects.toBeTruthy()
    expect(handler).toHaveBeenCalledTimes(1)
    window.removeEventListener(UNAUTHORIZED_EVENT, handler)
  })
})
