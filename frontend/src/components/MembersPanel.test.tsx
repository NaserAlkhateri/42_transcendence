// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { User } from '../auth/auth-context'
import type { Organization, OrganizationMember } from '../lib/organizations'

const ORG: Organization = {
  id: 'org-1', name: 'Falcon Bay Auto Care', kind: 'workshop', registration_number: 'DXB-1001', emirate: 'Dubai',
  status: 'approved', rejection_reason: null, approved_at: '2026-04-12T08:00:00Z', reviewed_at: '2026-04-12T08:00:00Z',
  created_at: '2026-04-11T08:00:00Z', updated_at: '2026-04-12T08:00:00Z',
}

const BOSS: OrganizationMember = {
  membership_id: 'm-boss', user_id: 'u-boss', full_name: 'Hamad Al Ketbi', email: 'falcon.admin@sijil.demo',
  role: 'entity_admin', status: 'active',
}
const TECH: OrganizationMember = {
  membership_id: 'm-tech', user_id: 'u-tech', full_name: 'Arjun Nair', email: 'falcon.staff@sijil.demo',
  role: 'entity_staff', status: 'active',
}

function boss(organization_status: Organization['status'] = 'approved'): User {
  return {
    id: 'u-boss', email: BOSS.email, full_name: BOSS.full_name, role: 'consumer',
    effective_role: organization_status === 'approved' ? 'entity_admin' : 'consumer', must_change_password: false,
    created_at: '2026-04-01T08:00:00Z',
    memberships: [{ id: 'm-boss', organization_id: 'org-1', organization_name: ORG.name, organization_status, role: 'entity_admin', status: 'active' }],
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

interface Call { method: string; path: string; body: unknown }

/** `routes` maps "METHOD /path" to a handler; the member list is served from `members` (mutable). */
function stubApi(user: User, organization: Organization, routes: Record<string, (body: unknown) => Response> = {}, members = [BOSS, TECH]) {
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
    if (key === 'GET /api/v1/organizations/org-1') return json(organization)
    if (key === 'GET /api/v1/organizations/org-1/members') return json(members)
    throw new Error(`unexpected request ${key}`)
  }))
  return calls
}

function open() {
  window.history.replaceState(null, '', '/organizations/org-1')
  render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('members panel', () => {
  it('creates a staff account and shows the temporary password once', async () => {
    const members = [BOSS, TECH]
    const calls = stubApi(boss(), ORG, {
      'POST /api/v1/organizations/org-1/members/staff-accounts': (body) => {
        const created = { membership_id: 'm-new', user_id: 'u-new', full_name: 'Fatima Rahman', email: 'fatima@example.ae', role: 'entity_staff', status: 'active' }
        members.push(created as OrganizationMember)
        expect(body).toEqual({ full_name: 'Fatima Rahman', email: 'fatima@example.ae', role: 'entity_staff' })
        return json({ member: created, temporary_password: 'Tmp-9f2kQ81xZp0w' }, 201)
      },
    }, members)
    open()

    expect(await screen.findByText('Arjun Nair')).toBeInTheDocument()
    const form = screen.getByRole('form', { name: 'Create a staff account' })
    fireEvent.change(within(form).getByLabelText(/^Full name/), { target: { value: 'Fatima Rahman' } })
    fireEvent.change(within(form).getByLabelText(/^Work email/), { target: { value: 'fatima@example.ae' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Create account' }))

    expect(await screen.findByTestId('temporary-password')).toHaveTextContent('Tmp-9f2kQ81xZp0w')
    expect(await screen.findByText('Fatima Rahman', { selector: 'td' })).toBeInTheDocument()  // the list reloaded
    expect(within(form).getByLabelText(/^Full name/)).toHaveValue('')
    expect(calls.filter((c) => c.path === '/api/v1/organizations/org-1/members').length).toBeGreaterThan(1)
  })

  it('checks the staff form before calling the API', async () => {
    const calls = stubApi(boss(), ORG)
    open()
    const form = await screen.findByRole('form', { name: 'Create a staff account' })
    fireEvent.click(within(form).getByRole('button', { name: 'Create account' }))
    expect(await within(form).findByText('Name is required.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('adds an existing account and shows why one could not be added', async () => {
    const calls = stubApi(boss(), ORG, {
      'POST /api/v1/organizations/org-1/members': (body) => (body as { email: string }).email === 'nobody@example.ae'
        ? json({ error: { code: 'user_not_found', message: 'No account uses this email. Create a staff account instead.' } }, 404)
        : json({ ...TECH, membership_id: 'm-sara', full_name: 'Sara Haddad' }, 201),
    })
    open()
    const form = await screen.findByRole('form', { name: 'Add someone with an account' })

    fireEvent.change(within(form).getByLabelText(/^Their account email/), { target: { value: 'nobody@example.ae' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Add member' }))
    expect(await within(form).findByText(/Create a staff account instead/)).toBeInTheDocument()

    fireEvent.change(within(form).getByLabelText(/^Their account email/), { target: { value: 'sara@example.ae' } })
    fireEvent.change(within(form).getByLabelText(/^Their role/), { target: { value: 'entity_admin' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Add member' }))
    await vi.waitFor(() => {
      const posts = calls.filter((c) => c.method === 'POST')
      expect(posts[posts.length - 1]?.body).toEqual({ email: 'sara@example.ae', role: 'entity_admin' })
    })
  })

  it('changes a role, deactivates and removes after confirming', async () => {
    const calls = stubApi(boss(), ORG, {
      'PATCH /api/v1/organizations/org-1/members/m-tech': (body) => json({ ...TECH, ...(body as object) }),
      'DELETE /api/v1/organizations/org-1/members/m-tech': () => new Response(null, { status: 204 }),
    })
    open()

    fireEvent.change(await screen.findByLabelText('Role of Arjun Nair'), { target: { value: 'entity_admin' } })
    await vi.waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && (c.body as { role?: string }).role === 'entity_admin')).toBe(true))

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate Arjun Nair' }))
    await vi.waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && (c.body as { status?: string }).status === 'inactive')).toBe(true))

    fireEvent.click(screen.getByRole('button', { name: 'Remove Arjun Nair' }))
    const dialog = await screen.findByRole('dialog', { name: 'Remove Arjun Nair?' })
    expect(within(dialog).getByText(/Their account stays/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove' }))
    await vi.waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.path.endsWith('/m-tech'))).toBe(true))
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('explains why the last entity admin cannot step down', async () => {
    stubApi(boss(), ORG, {
      'PATCH /api/v1/organizations/org-1/members/m-boss': () => json({ error: {
        code: 'last_entity_admin', message: 'Make another member an active entity admin first.',
      } }, 409),
    })
    open()
    fireEvent.click(await screen.findByRole('button', { name: 'Deactivate Hamad Al Ketbi' }))
    expect(await screen.findByText('Make another member an active entity admin first.')).toBeInTheDocument()
  })

  it('waits for approval before a pending organisation can add its team', async () => {
    const calls = stubApi(boss('pending'), { ...ORG, status: 'pending', approved_at: null })
    open()
    expect(await screen.findByText(/add your team once a platform admin approves/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Members' })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path.endsWith('/members'))).toBe(false)
  })
})
