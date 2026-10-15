// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../App'
import type { Membership, User } from '../../auth/auth-context'
import type { AdminOrganizationDetail, Organization } from '../../lib/organizations'

// Mirror backend/app/schemas/organizations.py.
function organization(overrides: Partial<Organization> = {}): Organization {
  return {
    id: 'org-1', name: 'Corniche Tyre Centre', kind: 'workshop', registration_number: 'DXB-778899', emirate: 'Dubai',
    status: 'pending', rejection_reason: null, approved_at: null, reviewed_at: null,
    created_at: '2026-04-11T08:00:00Z', updated_at: '2026-04-11T08:00:00Z', ...overrides,
  }
}

function adminDetail(overrides: Partial<AdminOrganizationDetail> = {}): AdminOrganizationDetail {
  return { ...organization(), member_count: 1, record_count: 3, members: [
    { membership_id: 'm1', user_id: 'u1', full_name: 'Mariam Al Mansoori', email: 'owner@example.ae', role: 'entity_admin', status: 'active' },
  ], ...overrides }
}

function membership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'm1', organization_id: 'org-1', organization_name: 'Corniche Tyre Centre', organization_status: 'pending',
    role: 'entity_admin', status: 'active', ...overrides,
  }
}

function account(overrides: Partial<User> = {}): User {
  return {
    id: 'u1', email: 'owner@example.ae', full_name: 'Mariam Al Mansoori', role: 'consumer', effective_role: 'consumer',
    must_change_password: false, created_at: '2026-04-01T08:00:00Z', memberships: [], ...overrides,
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

type Handler = (body: unknown) => Response
interface Call { method: string; path: string; body: unknown }

/** Network stub: `routes` maps "METHOD /path" to a handler. Unknown requests fail the test. */
function stubApi(user: User, routes: Record<string, Handler>) {
  const calls: Call[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    if (url.pathname === '/api/v1/auth/session') return json({ user })
    if (url.pathname === '/api/v1/auth/csrf') return json({ csrf_token: 'token' })
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path: url.pathname + url.search, body })
    const handler = routes[`${method} ${url.pathname}`]
    if (!handler) throw new Error(`unexpected request ${method} ${url.pathname}`)
    return handler(body)
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

describe('register a business', () => {
  it('submits the registration and lands on the pending organisation', async () => {
    const registered = account({ memberships: [membership()] })
    const calls = stubApi(account(), {
      'POST /api/v1/organizations': () => json(organization(), 201),
      'GET /api/v1/me': () => json(registered),
      'GET /api/v1/organizations/org-1': () => json(organization()),
    })
    open('/organizations/register')

    fireEvent.change(await screen.findByLabelText(/^Business name/), { target: { value: 'Corniche Tyre Centre' } })
    fireEvent.change(screen.getByLabelText(/^Type of business/), { target: { value: 'workshop' } })
    fireEvent.change(screen.getByLabelText(/^Trade licence number/), { target: { value: 'dxb-778899' } })
    fireEvent.change(screen.getByLabelText(/^Emirate/), { target: { value: 'Dubai' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit for review' }))

    expect(await screen.findByText('Awaiting review', { selector: 'p' })).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      name: 'Corniche Tyre Centre', kind: 'workshop', registration_number: 'DXB-778899', emirate: 'Dubai',
    })
    // The nav now links to the organisation instead of inviting a registration.
    expect(screen.getAllByRole('link', { name: 'Organisation' })[0]).toHaveAttribute('href', '/organizations/org-1')
  })

  it('checks the form before calling the API', async () => {
    const calls = stubApi(account(), {})
    open('/organizations/register')
    fireEvent.click(await screen.findByRole('button', { name: 'Submit for review' }))
    expect(await screen.findByText('Enter the business name.')).toBeInTheDocument()
    expect(screen.getByText('Choose the emirate.')).toBeInTheDocument()
    expect(calls).toEqual([])
  })

  it('shows the server answer for a taken licence number', async () => {
    stubApi(account(), {
      'POST /api/v1/organizations': () => json({ error: {
        code: 'registration_number_taken', message: 'An organization with this trade licence number is already registered.',
      } }, 409),
    })
    open('/organizations/register')
    fireEvent.change(await screen.findByLabelText(/^Business name/), { target: { value: 'Corniche Tyre Centre' } })
    fireEvent.change(screen.getByLabelText(/^Type of business/), { target: { value: 'workshop' } })
    fireEvent.change(screen.getByLabelText(/^Trade licence number/), { target: { value: 'DXB-1' } })
    fireEvent.change(screen.getByLabelText(/^Emirate/), { target: { value: 'Dubai' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit for review' }))
    expect(await screen.findByText(/already registered/)).toBeInTheDocument()
  })
})

describe('your organisation', () => {
  it('shows the rejection reason and resubmits after a fix', async () => {
    const rejected = organization({ status: 'rejected', rejection_reason: 'Licence number does not match the document.' })
    const member = account({ memberships: [membership({ organization_status: 'rejected' })] })
    const calls = stubApi(member, {
      'GET /api/v1/organizations/org-1': () => json(rejected),
      'PATCH /api/v1/organizations/org-1': () => json({ ...rejected, registration_number: 'DXB-778900' }),
      'POST /api/v1/organizations/org-1/resubmit': () => json(organization({ registration_number: 'DXB-778900' })),
      'GET /api/v1/me': () => json(account({ memberships: [membership()] })),
    })
    open('/organizations/org-1')

    expect(await screen.findByText('Licence number does not match the document.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/^Trade licence number/), { target: { value: 'DXB-778900' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save and resubmit' }))

    expect(await screen.findByText('Resubmitted for review.')).toBeInTheDocument()
    const writes = calls.filter((c) => c.method !== 'GET').map((c) => [c.method, c.path, c.body])
    expect(writes).toEqual([
      ['PATCH', '/api/v1/organizations/org-1', { registration_number: 'DXB-778900' }],
      ['POST', '/api/v1/organizations/org-1/resubmit', undefined],
    ])
  })

  it('is read-only for staff, and the licence is locked once approved', async () => {
    const approved = organization({ status: 'approved', approved_at: '2026-04-12T08:00:00Z' })
    stubApi(account({ effective_role: 'entity_staff', memberships: [membership({ role: 'entity_staff', organization_status: 'approved' })] }), {
      'GET /api/v1/organizations/org-1': () => json(approved),
    })
    open('/organizations/org-1')
    expect(await screen.findByText('12 Apr 2026')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save/ })).not.toBeInTheDocument()
    cleanup()

    stubApi(account({ effective_role: 'entity_admin', memberships: [membership({ organization_status: 'approved' })] }), {
      'GET /api/v1/organizations/org-1': () => json(approved),
    })
    open('/organizations/org-1')
    expect(await screen.findByLabelText(/^Trade licence number/)).toBeDisabled()
  })

  it('tells non-members the organisation is not theirs', async () => {
    stubApi(account(), {
      'GET /api/v1/organizations/org-9': () => json({ error: { code: 'forbidden', message: 'No.' } }, 403),
    })
    open('/organizations/org-9')
    expect(await screen.findByText(/not a member of it/)).toBeInTheDocument()
  })
})

describe('admin: organisations', () => {
  const admin = account({ id: 'admin', role: 'platform_admin', effective_role: 'platform_admin', email: 'admin@sijil.demo' })
  const page = (items: AdminOrganizationDetail[]) => json({ items, total: items.length, page: 1, page_size: 20 })

  it('approves a pending registration from the review queue', async () => {
    const pending = adminDetail()
    const calls = stubApi(admin, {
      'GET /api/v1/admin/organizations': () => page([pending]),
      'GET /api/v1/admin/organizations/org-1': () => json(pending),
      'POST /api/v1/admin/organizations/org-1/approve': () => json(adminDetail({ status: 'approved', approved_at: '2026-04-12T08:00:00Z' })),
    })
    open('/admin/organizations')

    expect(await screen.findByText('1 registration awaiting review.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Review Corniche Tyre Centre' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    expect(await screen.findByRole('button', { name: 'Withdraw approval' })).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/admin/organizations/org-1/approve')).toBe(true)
  })

  it('needs a reason to reject', async () => {
    const pending = adminDetail()
    const calls = stubApi(admin, {
      'GET /api/v1/admin/organizations': () => page([pending]),
      'GET /api/v1/admin/organizations/org-1': () => json(pending),
      'POST /api/v1/admin/organizations/org-1/reject': (body) => json(adminDetail({
        status: 'rejected', rejection_reason: (body as { reason: string }).reason,
      })),
    })
    open('/admin/organizations')
    fireEvent.click(await screen.findByRole('button', { name: 'Review Corniche Tyre Centre' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))

    const dialog = await screen.findByRole('dialog', { name: 'Reject Corniche Tyre Centre' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }))
    expect(await within(dialog).findByText(/at least 5 characters/)).toBeInTheDocument()
    expect(calls.some((c) => c.path.endsWith('/reject'))).toBe(false)

    fireEvent.change(within(dialog).getByLabelText(/^Reason shown to the business/), { target: { value: 'Licence has expired.' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reject' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Rejection reasonLicence has expired.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/reject'))?.body).toEqual({ reason: 'Licence has expired.' })
  })

  it('deletes after confirming, explaining that history stays', async () => {
    const approved = adminDetail({ status: 'approved' })
    const calls = stubApi(admin, {
      'GET /api/v1/admin/organizations': () => page([approved]),
      'GET /api/v1/admin/organizations/org-1': () => json(approved),
      'DELETE /api/v1/admin/organizations/org-1': () => new Response(null, { status: 204 }),
    })
    open('/admin/organizations')
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Corniche Tyre Centre' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete organisation' }))

    const dialog = await screen.findByRole('dialog', { name: 'Delete Corniche Tyre Centre?' })
    expect(within(dialog).getByText(/3 service records stay/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete permanently' }))

    await vi.waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    expect(await screen.findByRole('button', { name: 'Add organisation' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Manage/ })).not.toBeInTheDocument()
  })

  it('is closed to everyone else', async () => {
    stubApi(account({ effective_role: 'entity_admin', memberships: [membership({ organization_status: 'approved' })] }), {})
    open('/admin/organizations')
    expect(await screen.findByText('Access denied')).toBeInTheDocument()
  })
})
