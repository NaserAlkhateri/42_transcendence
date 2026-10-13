// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { User } from './auth-context'

const ADMIN: User = {
  id: '0b6f8a52-0000-4000-8000-000000000001',
  email: 'admin@sijil.demo',
  full_name: 'Platform Admin',
  role: 'platform_admin',
  effective_role: 'platform_admin',
  must_change_password: false,
  created_at: '2026-10-12T08:00:00Z',
  memberships: [],
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

type Route = (url: URL, init?: RequestInit) => Response | Promise<Response>

/** Stub the network only. Unknown requests fail the test loudly. */
function stubApi(routes: Record<string, Route>) {
  const requested: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    requested.push(`${init?.method ?? 'GET'} ${url.pathname}`)
    const route = routes[url.pathname]
    if (!route) throw new Error(`unexpected request ${url.pathname}`)
    return route(url, init)
  }))
  return requested
}

const EMPTY_USER_PAGE = { items: [], total: 0, page: 1, page_size: 20 }

function open(path: string) {
  window.history.replaceState(null, '', path)
  render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('session start-up', () => {
  it('restores the signed-in user from the session probe, which never answers 401', async () => {
    const requested = stubApi({ '/api/v1/auth/session': () => json({ user: ADMIN }) })
    open('/')

    expect(await screen.findByRole('link', { name: 'Go to your account' })).toBeInTheDocument()
    expect(requested).not.toContain('GET /api/v1/me')
  })
})

describe('logout', () => {
  it('lands on the home page, so the next person to log in does not inherit the previous page', async () => {
    stubApi({
      '/api/v1/auth/session': () => json({ user: ADMIN }),
      '/api/v1/admin/users': () => json(EMPTY_USER_PAGE),
      '/api/v1/auth/csrf': () => json({ csrf_token: 'token' }),
      '/api/v1/auth/logout': () => new Response(null, { status: 204 }),
    })
    open('/admin/users')
    fireEvent.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Trusted vehicle service history' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(screen.queryByRole('button', { name: 'Log out' })).toBeNull()
  })

  it('keeps the user signed in and says why when the server cannot be reached', async () => {
    stubApi({
      '/api/v1/auth/session': () => json({ user: ADMIN }),
      '/api/v1/admin/users': () => json(EMPTY_USER_PAGE),
      '/api/v1/auth/csrf': () => json({ csrf_token: 'token' }),
      '/api/v1/auth/logout': () => Promise.reject(new TypeError('Failed to fetch')),
    })
    open('/admin/users')
    fireEvent.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/admin/users')
  })
})

describe('admin users page', () => {
  it('shows why the list failed to load instead of a loading row that never ends', async () => {
    stubApi({
      '/api/v1/auth/session': () => json({ user: ADMIN }),
      '/api/v1/admin/users': () => json({ error: { code: 'internal_error', message: 'The user list is unavailable.' } }, 500),
    })
    open('/admin/users')

    expect(await screen.findByRole('alert')).toHaveTextContent('The user list is unavailable.')
    await waitFor(() => expect(screen.queryByText('Loading users…')).toBeNull())
  })
})
