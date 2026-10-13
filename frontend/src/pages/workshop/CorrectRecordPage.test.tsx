// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../App'
import type { User } from '../../auth/auth-context'

const WORK_CODES = [
  { code: 'OIL_CHANGE', label: 'Oil change', label_ar: 'تغيير الزيت' },
  { code: 'AC_SERVICE', label: 'A/C service', label_ar: 'صيانة المكيف' },
]

const STAFF: User = {
  id: 'user-arjun', email: 'falcon.staff@sijil.demo', full_name: 'Arjun Nair', role: 'consumer',
  effective_role: 'entity_staff', must_change_password: false, created_at: '2026-10-12T08:00:00Z',
  memberships: [{
    id: 'mem-1', organization_id: 'org-falcon', organization_name: 'Falcon Bay Auto Care',
    organization_status: 'approved', role: 'entity_staff', status: 'active',
  }],
}

// OrgRecordOut from GET /organizations/{id}/records?vin=
function orgRecord(overrides: Record<string, unknown>) {
  return {
    id: 'rec', vin: 'JTNBK3EK6N3012345', service_date: '2025-11-05', created_at: '2025-11-05T09:00:00Z',
    category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 54000, organization_name: 'Falcon Bay Auto Care',
    is_mileage_flagged: false, corrects_record_id: null, correction_reason: null, staff_name: 'Arjun Nair', notes: null,
    corrected_by_id: null, ...overrides,
  }
}

const TYPO = orgRecord({ id: 'rec-typo', service_date: '2026-02-10', odometer_km: 540000 })
const OLDER = orgRecord({ id: 'rec-older', service_date: '2025-11-05', odometer_km: 45000 })

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function stubApi({ list = [TYPO, OLDER], onPost = () => json(orgRecord({ id: 'rec-fix', odometer_km: 54000, corrects_record_id: 'rec-typo', correction_reason: 'odometer' }), 201) }: {
  list?: unknown[] | (() => unknown[]); onPost?: (body: unknown) => Response
} = {}) {
  const calls: string[] = []
  const posts: { path: string; body: unknown }[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    calls.push(`${init?.method ?? 'GET'} ${url.pathname}${url.search}`)
    if (url.pathname === '/api/v1/auth/session') return json({ user: STAFF })
    if (url.pathname === '/api/v1/work-codes') return json(WORK_CODES)
    if (url.pathname === '/api/v1/auth/csrf') return json({ csrf_token: 'token' })
    if (url.pathname === '/api/v1/organizations/org-falcon/records' && (init?.method ?? 'GET') === 'GET') {
      return json(typeof list === 'function' ? list() : list)
    }
    if (init?.method === 'POST' && url.pathname.endsWith('/corrections')) {
      const body = JSON.parse(String(init.body))
      posts.push({ path: url.pathname, body })
      return onPost(body)
    }
    throw new Error(`unexpected request ${init?.method ?? 'GET'} ${url.pathname}`)
  }))
  return { calls, posts }
}

async function findRecords(vin = 'jtnbk3ek6n3-012345') {
  window.history.replaceState(null, '', '/workshop/corrections')
  render(<App />)
  fireEvent.change(await screen.findByLabelText(/^VIN \(chassis number\)/), { target: { value: vin } })
  fireEvent.click(screen.getByRole('button', { name: 'Find records' }))
  return screen.findByRole('table', { name: /records for this VIN/ })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('correct a record', () => {
  it('lists the organisation’s records for the VIN and saves a correction prefilled from the original', async () => {
    const { calls, posts } = stubApi()
    const table = await findRecords()
    expect(calls).toContain('GET /api/v1/organizations/org-falcon/records?vin=JTNBK3EK6N3012345')

    fireEvent.click(within(table).getByRole('button', { name: 'Correct the 10 Feb 2026 record' }))
    const odometer = await screen.findByLabelText(/^Odometer reading \(km\)/)
    expect(odometer).toHaveValue('540000') // prefilled from the original
    fireEvent.change(screen.getByLabelText(/^What does this correction fix/), { target: { value: 'odometer' } })
    fireEvent.change(odometer, { target: { value: '54000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save correction' }))

    expect(await screen.findByText(/Correction saved/)).toBeInTheDocument()
    expect(posts).toEqual([{
      path: '/api/v1/organizations/org-falcon/records/rec-typo/corrections',
      body: {
        correction_reason: 'odometer', service_date: '2026-02-10', category: 'maintenance',
        work_codes: ['OIL_CHANGE'], odometer_km: 54000, notes: null,
      },
    }])
    expect(screen.getByRole('link', { name: 'View vehicle history' })).toHaveAttribute('href', '/vehicles/JTNBK3EK6N3012345')
  })

  it('does not offer to correct a record that already has a correction', async () => {
    stubApi({ list: [orgRecord({ id: 'rec-fix', corrects_record_id: 'rec-typo', correction_reason: 'odometer' }), { ...TYPO, corrected_by_id: 'rec-fix' }] })
    const table = await findRecords()

    const rows = within(table).getAllByRole('row').slice(1)
    expect(within(rows[1]).queryByRole('button')).toBeNull()
    expect(rows[1]).toHaveTextContent('Corrected')
    expect(within(rows[0]).getByRole('button', { name: /^Correct the/ })).toBeInTheDocument()
  })

  it('needs to know what the correction fixes before sending', async () => {
    const { posts } = stubApi()
    const table = await findRecords()
    fireEvent.click(within(table).getByRole('button', { name: 'Correct the 10 Feb 2026 record' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Save correction' }))

    expect(await screen.findByText('Choose what the correction fixes.')).toBeInTheDocument()
    expect(posts).toEqual([])
  })

  it('explains when someone else corrected the record first', async () => {
    stubApi({ onPost: () => json({ error: { code: 'already_corrected', message: 'This record already has a correction. Correct that one instead.' } }, 409) })
    const table = await findRecords()
    fireEvent.click(within(table).getByRole('button', { name: 'Correct the 10 Feb 2026 record' }))
    fireEvent.change(await screen.findByLabelText(/^What does this correction fix/), { target: { value: 'odometer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save correction' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('already has a correction')
  })

  it('says so when the organisation has no records for the VIN', async () => {
    stubApi({ list: [] })
    window.history.replaceState(null, '', '/workshop/corrections')
    render(<App />)
    fireEvent.change(await screen.findByLabelText(/^VIN \(chassis number\)/), { target: { value: 'MDHBN7AD0P0012345' } })
    fireEvent.click(screen.getByRole('button', { name: 'Find records' }))

    expect(await screen.findByText('Your organisation has no records for this VIN.')).toBeInTheDocument()
  })
})
