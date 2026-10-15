// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { User } from '../auth/auth-context'
import type { ApiKeyRow } from '../lib/apiKeys'

const ADMIN: User = {
  id: 'admin', email: 'admin@sijil.demo', full_name: 'Platform Admin', role: 'platform_admin',
  effective_role: 'platform_admin', must_change_password: false, created_at: '2026-04-01T08:00:00Z', memberships: [],
}

function row(overrides: Partial<ApiKeyRow> = {}): ApiKeyRow {
  return {
    id: 'k1', partner_name: 'Gulf Shield Insurance', key_prefix: '1a2b3c4d', scopes: ['vehicles:read', 'watches:manage'],
    created_at: '2026-04-11T08:00:00Z', issued_by: 'admin@sijil.demo', last_used_at: null, revoked_at: null, watch_count: 2,
    ...overrides,
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

interface Call { method: string; path: string; body: unknown }

function stubApi(user: User, keys: ApiKeyRow[], routes: Record<string, (body: unknown) => Response> = {}) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    if (url.pathname === '/api/v1/auth/session') return json({ user })
    if (url.pathname === '/api/v1/auth/csrf') return json({ csrf_token: 'token' })
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path: url.pathname, body })
    const key = `${method} ${url.pathname}`
    if (routes[key]) return routes[key](body)
    if (key === 'GET /api/v1/admin/api-keys') return json(keys)
    throw new Error(`unexpected request ${key}`)
  }))
  return calls
}

function open() {
  window.history.replaceState(null, '', '/admin/api-keys')
  render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('admin: partner API keys', () => {
  it('issues a key and shows it once', async () => {
    const keys = [row()]
    const calls = stubApi(ADMIN, keys, {
      'POST /api/v1/admin/api-keys': (body) => {
        const issued = row({ id: 'k2', partner_name: (body as { partner_name: string }).partner_name, key_prefix: '9f8e7d6c', watch_count: 0 })
        keys.unshift(issued)
        return json({ key: issued, api_key: 'sjl_9f8e7d6c_secret-shown-once' }, 201)
      },
    })
    open()

    expect(await screen.findByText('Gulf Shield Insurance')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Issue key' }))
    const dialog = await screen.findByRole('dialog', { name: 'Issue a partner API key' })
    fireEvent.change(within(dialog).getByLabelText(/^Partner name/), { target: { value: '  Desert Cars Marketplace ' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Issue key' }))

    expect(await screen.findByTestId('issued-api-key')).toHaveTextContent('sjl_9f8e7d6c_secret-shown-once')
    expect(await screen.findByText('sjl_9f8e7d6c_…')).toBeInTheDocument()  // the list shows the prefix only
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ partner_name: 'Desert Cars Marketplace' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('checks the partner name before calling the API', async () => {
    const calls = stubApi(ADMIN, [])
    open()
    fireEvent.click(await screen.findByRole('button', { name: 'Issue key' }))
    const dialog = await screen.findByRole('dialog', { name: 'Issue a partner API key' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Issue key' }))
    expect(await within(dialog).findByText('Enter the partner’s name.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('revokes after confirming', async () => {
    const keys = [row()]
    const calls = stubApi(ADMIN, keys, {
      'POST /api/v1/admin/api-keys/k1/revoke': () => {
        keys[0] = row({ revoked_at: '2026-04-12T08:00:00Z' })
        return json(keys[0])
      },
    })
    open()

    fireEvent.click(await screen.findByRole('button', { name: 'Revoke key for Gulf Shield Insurance' }))
    const dialog = await screen.findByRole('dialog', { name: 'Revoke key for Gulf Shield Insurance?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Revoke key' }))

    expect(await screen.findByText('Revoked 12 Apr 2026')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Revoke key for/ })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/api/v1/admin/api-keys/k1/revoke')).toBe(true)
  })

  it('is for platform admins only', async () => {
    stubApi({ ...ADMIN, role: 'consumer', effective_role: 'entity_admin' }, [])
    open()
    expect(await screen.findByText('Access denied')).toBeInTheDocument()
  })
})
