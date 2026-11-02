import { afterEach, describe, expect, it } from 'vitest'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { api, ApiError, errorText } from './api'

const server = setupServer(
  http.get('/ready', () => HttpResponse.json({ status: 'ok', dependencies: { redis: 'ok' } })),
  http.post('/v1/chat/completions', () => HttpResponse.json({ error: 'rate_limit_exceeded', message: 'Too many requests' }, { status: 429, headers: { 'Retry-After': '3' } }))
)
server.listen()
afterEach(() => server.resetHandlers())
describe('API integration', () => {
  it('reads readiness', async () => expect((await api.ready()).dependencies.redis).toBe('ok'))
  it('surfaces retry timing', async () => {
    try { await api.chat('key', 'smart-chat', [{ role: 'user', content: 'hi' }]) } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect(errorText(error)).toContain('Retry in 3s')
    }
  })
})
