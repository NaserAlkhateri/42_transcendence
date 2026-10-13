import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, http, serverFieldErrors, setUnauthorizedHandler } from './api'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api client', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setUnauthorizedHandler(undefined)
  })

  it('prefixes /api/v1 and sends cookies on GET without a CSRF header', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    await expect(api<{ ok: boolean }>('/me')).resolves.toEqual({ ok: true })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/me')
    expect(init?.credentials).toBe('same-origin')
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined()
  })

  it('fetches a CSRF token before a state-changing call and sends it as a header', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, { csrf_token: 'tok123' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 1 }))
    await http.post('/auth/login', { email: 'a@example.ae', password: 'x' })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/csrf')
    const [, init] = fetchMock.mock.calls[1]
    expect(init?.method).toBe('POST')
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('tok123')
    expect(init?.body).toBe(JSON.stringify({ email: 'a@example.ae', password: 'x' }))
  })

  it('turns the error envelope into an ApiError with field details', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        error: { code: 'validation_error', message: 'Invalid input', details: [{ loc: ['body', 'full_name'], message: 'Too long' }] },
      }),
    )
    const error = await api('/me').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).code).toBe('validation_error')
    expect(serverFieldErrors(error, { full_name: 'fullName' })).toEqual({ fullName: 'Too long' })
  })

  it('returns undefined for 204 responses', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(api('/x')).resolves.toBeUndefined()
  })

  it('maps network failures to ApiError status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const error = (await api('/me').catch((e: unknown) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(0)
    expect(error.code).toBe('network_error')
  })

  it('calls the unauthorized handler on 401 unless silenced', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValue(jsonResponse(401, { error: { code: 'not_authenticated', message: 'Sign in' } }))
    await api('/admin/users').catch(() => undefined)
    expect(handler).toHaveBeenCalledTimes(1)
    await api('/me', { silent401: true }).catch(() => undefined)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('reports a timeout distinctly', async () => {
    fetchMock.mockImplementationOnce(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
        }),
    )
    const error = (await api('/slow', { timeoutMs: 5 }).catch((e: unknown) => e)) as ApiError
    expect(error.code).toBe('timeout')
  })
})
