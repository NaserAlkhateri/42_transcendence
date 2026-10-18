// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { User } from '../auth/auth-context'
import { ApiError, errorMessage } from '../lib/api'

const ADMIN: User = {
  id: 'admin', email: 'admin@sijil.demo', full_name: 'Platform Admin', role: 'platform_admin',
  effective_role: 'platform_admin', must_change_password: false, created_at: '2026-04-01T08:00:00Z', memberships: [],
}

function adminRow(id: string, name: string) {
  return {
    id, email: `${id}@example.ae`, full_name: name, role: 'consumer', effective_role: 'consumer', must_change_password: false,
    created_at: '2026-04-01T08:00:00Z', updated_at: '2026-04-01T08:00:00Z', status: 'active', memberships: [],
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

type Handler = (url: URL, body: unknown) => Response

function stubApi(session: () => User | null, routes: Record<string, Handler>) {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    calls.push(`${method} ${url.pathname}${url.search}`)
    if (url.pathname === '/api/v1/auth/session') return json({ user: session() })
    if (url.pathname === '/api/v1/auth/csrf') return json({ csrf_token: 'token' })
    const handler = routes[`${method} ${url.pathname}`]
    if (!handler) throw new Error(`unexpected request ${method} ${url.pathname}`)
    return handler(url, init?.body ? JSON.parse(String(init.body)) : undefined)
  }))
  return calls
}

function open(path: string) {
  window.history.replaceState(null, '', path)
  render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('readable validation errors', () => {
  it('turns a 422 into a sentence instead of "Request validation failed"', () => {
    const error = new ApiError(422, 'validation_error', 'Request validation failed', [
      { loc: ['body', 'email'], message: 'value is not a valid email address' },
    ])
    expect(errorMessage(error)).toBe('Please check your details: value is not a valid email address')
    expect(errorMessage(new ApiError(429, 'rate_limited', 'Too many attempts.'))).toBe('Too many attempts.')
  })

  it('shows the email problem next to the field on the login page', async () => {
    stubApi(() => null, {
      'POST /api/v1/auth/login': () => json({ error: {
        code: 'validation_error', message: 'Request validation failed',
        details: [{ loc: ['body', 'email'], message: 'The part after the @-sign is a special-use or reserved name.' }],
      } }, 422),
    })
    open('/login')
    fireEvent.change(await screen.findByLabelText(/^Email/), { target: { value: 'me@garage.local' } })
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: 'whatever-pass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText(/^Please check your details:/)).toBeInTheDocument()
    expect(screen.queryByText('Request validation failed')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/^Email/)).toHaveAttribute('aria-invalid', 'true')
  })

  it('explains a login lockout', async () => {
    stubApi(() => null, {
      'POST /api/v1/auth/login': () => json({ error: { code: 'rate_limited', message: 'Too many attempts. Wait a few minutes and try again.' } }, 429),
    })
    open('/login')
    fireEvent.change(await screen.findByLabelText(/^Email/), { target: { value: 'me@example.ae' } })
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: 'whatever-pass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Too many attempts. Wait a few minutes and try again.')).toBeInTheDocument()
  })
})

describe('role changes made elsewhere', () => {
  it('re-reads the session after a 403, so a demoted admin loses the admin links', async () => {
    let current: User = ADMIN
    stubApi(() => current, {
      'GET /api/v1/admin/users': () => {
        current = { ...ADMIN, role: 'consumer', effective_role: 'consumer' }  // demoted in another tab
        return json({ error: { code: 'forbidden', message: 'Platform admin access required.' } }, 403)
      },
    })
    open('/admin/users')

    expect(await screen.findByText('Access denied')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })
})

describe('admin: users', () => {
  it('resets a forgotten password and shows it once', async () => {
    const calls = stubApi(() => ADMIN, {
      'GET /api/v1/admin/users': () => json({ items: [adminRow('u1', 'Arjun Nair')], total: 1, page: 1, page_size: 20 }),
      'POST /api/v1/admin/users/u1/reset-password': () => json({ temporary_password: 'Tmp-q81xZp0w9f2k' }),
    })
    open('/admin/users')
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Arjun Nair' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Reset password' }))
    const dialog = await screen.findByRole('dialog', { name: 'Reset the password of Arjun Nair?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reset password' }))

    expect(await screen.findByTestId('reset-temporary-password')).toHaveTextContent('Tmp-q81xZp0w9f2k')
    expect(calls).toContain('POST /api/v1/admin/users/u1/reset-password')
  })

  it('moves back a page when the last user on the last page is deleted', async () => {
    let total = 21
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const calls = stubApi(() => ADMIN, {
      'GET /api/v1/admin/users': (url) => {
        const page = Number(url.searchParams.get('page'))
        const items = page === 2 && total === 21 ? [adminRow('u21', 'Last Person')] : page === 1 ? [adminRow('u1', 'First Person')] : []
        return json({ items, total, page, page_size: 20 })
      },
      'DELETE /api/v1/admin/users/u21': () => { total = 20; return new Response(null, { status: 204 }) },
    })
    open('/admin/users')
    fireEvent.click(await screen.findByRole('button', { name: /Next/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Last Person' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete user' }))

    expect(await screen.findByText('First Person')).toBeInTheDocument()
    const lists = calls.filter((c) => c.startsWith('GET /api/v1/admin/users'))
    expect(lists[lists.length - 1]).toContain('page=1')
  })
})
