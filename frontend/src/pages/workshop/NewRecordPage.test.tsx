// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../App'
import type { Membership, User } from '../../auth/auth-context'

// Mirror backend/app/schemas: work codes, the signed-in staff user and the created record.
const WORK_CODES = [
  { code: 'OIL_CHANGE', label: 'Oil change', label_ar: 'تغيير الزيت' },
  { code: 'AC_SERVICE', label: 'A/C service', label_ar: 'صيانة المكيف' },
  { code: 'BATTERY_REPLACE', label: 'Battery replacement', label_ar: 'تبديل البطارية' },
]

function member(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'mem-1', organization_id: 'org-falcon', organization_name: 'Falcon Bay Auto Care',
    organization_status: 'approved', role: 'entity_staff', status: 'active', ...overrides,
  }
}

function staff(memberships: Membership[]): User {
  return {
    id: 'user-arjun', email: 'falcon.staff@sijil.demo', full_name: 'Arjun Nair', role: 'consumer',
    effective_role: 'entity_staff', must_change_password: false, created_at: '2026-10-12T08:00:00Z', memberships,
  }
}

function created(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rec-1', vin: 'JN8AY2NY4K9012345', service_date: '2026-03-01', created_at: '2026-03-01T09:00:00Z',
    category: 'maintenance', work_codes: ['OIL_CHANGE', 'AC_SERVICE'], odometer_km: 130000,
    organization_name: 'Falcon Bay Auto Care', is_mileage_flagged: false, corrects_record_id: null,
    correction_reason: null, staff_name: 'Arjun Nair', notes: null, ...overrides,
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Network stub; records each POST body. Unknown requests fail the test. */
function stubApi(user: User, onPost: (body: unknown) => Response = () => json(created(), 201)) {
  const posts: { path: string; body: unknown }[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/auth/session') return json({ user })
    if (url.pathname === '/api/v1/work-codes') return json(WORK_CODES)
    if (url.pathname === '/api/v1/auth/csrf') return json({ csrf_token: 'token' })
    if (init?.method === 'POST' && url.pathname === '/api/v1/organizations/org-falcon/records') {
      const body = JSON.parse(String(init.body))
      posts.push({ path: url.pathname, body })
      return onPost(body)
    }
    throw new Error(`unexpected request ${init?.method ?? 'GET'} ${url.pathname}`)
  }))
  return posts
}

function open(path: string) {
  window.history.replaceState(null, '', path)
  render(<App />)
}

async function fillValidForm() {
  fireEvent.change(await screen.findByLabelText(/^VIN \(chassis number\)/), { target: { value: 'jn8ay2ny4k9-012345' } })
  fireEvent.change(screen.getByLabelText(/^Service date/), { target: { value: '2026-03-01' } })
  fireEvent.change(screen.getByLabelText(/^Category/), { target: { value: 'maintenance' } })
  fireEvent.click(await screen.findByLabelText('Oil change')) // the work-code list loads from the API
  fireEvent.click(screen.getByLabelText('A/C service'))
  fireEvent.change(screen.getByLabelText(/^Odometer reading \(km\)/), { target: { value: '130000' } })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('add a service record', () => {
  it('sends the record for the staff member’s organization and links to the vehicle history', async () => {
    const posts = stubApi(staff([member()]))
    open('/workshop/records/new')

    await fillValidForm()
    fireEvent.change(screen.getByLabelText(/^Private notes/), { target: { value: 'Customer waited' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save record' }))

    expect(await screen.findByText(/Record saved/)).toBeInTheDocument()
    expect(posts).toEqual([{
      path: '/api/v1/organizations/org-falcon/records',
      body: {
        vin: 'JN8AY2NY4K9012345', service_date: '2026-03-01', category: 'maintenance',
        work_codes: ['OIL_CHANGE', 'AC_SERVICE'], odometer_km: 130000, notes: 'Customer waited',
      },
    }])
    expect(screen.getByRole('link', { name: 'View vehicle history' })).toHaveAttribute('href', '/vehicles/JN8AY2NY4K9012345')
    expect(screen.queryByText(/mileage warning/i)).toBeNull()
  })

  it('explains when the saved reading carries a mileage warning', async () => {
    stubApi(staff([member()]), () => json(created({ is_mileage_flagged: true }), 201))
    open('/workshop/records/new')

    await fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Save record' }))

    expect(await screen.findByText(/saved with a mileage warning/i)).toBeInTheDocument()
  })

  it('checks the form before sending anything', async () => {
    const posts = stubApi(staff([member()]))
    open('/workshop/records/new')

    fireEvent.click(await screen.findByRole('button', { name: 'Save record' }))

    expect(await screen.findByText('Enter a VIN.')).toBeInTheDocument()
    expect(screen.getByText('Choose at least one item of work done.')).toBeInTheDocument()
    expect(screen.getByText('Enter the odometer reading in km.')).toBeInTheDocument()
    expect(posts).toEqual([])
  })

  it('shows the server’s field errors next to the fields', async () => {
    stubApi(staff([member()]), () => json({
      error: { code: 'validation_error', message: 'Request validation failed',
        details: [{ loc: ['body', 'service_date'], message: 'Value error, The service date cannot be in the future.' }] },
    }, 422))
    open('/workshop/records/new')

    await fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Save record' }))

    expect(await screen.findByText(/cannot be in the future/)).toBeInTheDocument()
  })

  it('asks which organization when the user works for more than one', async () => {
    const posts = stubApi(staff([
      member({ id: 'mem-oasis', organization_id: 'org-oasis', organization_name: 'Oasis Line Motors' }),
      member(),
    ]))
    open('/workshop/records/new')

    fireEvent.change(await screen.findByLabelText(/^Organisation/), { target: { value: 'org-falcon' } })
    await fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Save record' }))

    await screen.findByText(/Record saved/)
    expect(posts[0].path).toBe('/api/v1/organizations/org-falcon/records')
  })

  it('tells members of an organization awaiting approval why they cannot add records', async () => {
    stubApi(staff([member({ organization_status: 'pending', organization_name: 'Sand Dune Garage' })]))
    open('/workshop/records/new')

    expect(await screen.findByText(/waiting for approval/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save record' })).toBeNull()
  })

  it('offers each predefined work code as a checkbox', async () => {
    stubApi(staff([member()]))
    open('/workshop/records/new')

    const group = await screen.findByRole('group', { name: /Work done/ })
    const boxes = await within(group).findAllByRole('checkbox')
    expect(boxes.map((box) => box.closest('div')?.textContent)).toEqual([
      'Oil change', 'A/C service', 'Battery replacement',
    ])
  })
})
