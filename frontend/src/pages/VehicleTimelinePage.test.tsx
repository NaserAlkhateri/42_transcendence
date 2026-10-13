// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'

// Mirrors backend/app/schemas/vehicle.py (VehicleTimeline). Only fetch is stubbed: router, auth and api client are real.
interface TimelineBody {
  vin: string
  vehicle: { vin: string; make: string | null; model: string | null; model_year: number | null } | null
  records: {
    id: string
    service_date: string
    created_at: string
    category: 'maintenance' | 'repair'
    work_codes: string[]
    odometer_km: number
    organization_name: string
    is_mileage_flagged: boolean
    corrects_record_id: string | null
  }[]
}

// Mirrors the seed (backend/app/seed.py): common UAE cars.
const PATROL: TimelineBody = {
  vin: 'JN8AY2NY4K9012345',
  vehicle: { vin: 'JN8AY2NY4K9012345', make: 'Nissan', model: 'Patrol', model_year: 2019 },
  records: [
    {
      id: '6f1c2c1e-0000-4000-8000-000000000003', service_date: '2026-04-11', created_at: '2026-04-11T08:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 88300,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: true, corrects_record_id: null,
    },
    {
      id: '6f1c2c1e-0000-4000-8000-000000000002', service_date: '2025-07-21', created_at: '2025-07-21T08:00:00Z',
      category: 'repair', work_codes: ['AC_SERVICE', 'BATTERY_REPLACE'], odometer_km: 121500,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: false, corrects_record_id: null,
    },
    {
      id: '6f1c2c1e-0000-4000-8000-000000000001', service_date: '2024-06-03', created_at: '2024-06-03T08:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 96000,
      organization_name: 'Oasis Line Motors', is_mileage_flagged: false, corrects_record_id: null,
    },
  ],
}

const ORIGINAL_ID = '7a2d3d2f-0000-4000-8000-000000000001'
const CAMRY: TimelineBody = {
  vin: 'JTNBK3EK6N3012345',
  vehicle: { vin: 'JTNBK3EK6N3012345', make: 'Toyota', model: 'Camry', model_year: 2022 },
  records: [
    {
      id: '7a2d3d2f-0000-4000-8000-000000000002', service_date: '2025-11-05', created_at: '2025-11-06T09:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 45100,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: false, corrects_record_id: ORIGINAL_ID,
    },
    {
      id: ORIGINAL_ID, service_date: '2025-11-05', created_at: '2025-11-05T09:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 54000,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: false, corrects_record_id: null,
    },
  ],
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Signed-out visitor; every timeline request is recorded and answered by `timeline`. */
function stubApi(timeline: (url: URL) => Response) {
  const calls: URL[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/auth/session') return json({ user: null })
    if (url.pathname.startsWith('/api/v1/vehicles/')) {
      calls.push(url)
      return timeline(url)
    }
    throw new Error(`unexpected request ${url}`)
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

describe('vehicle timeline page', () => {
  it('shows date, mileage, workshop and work done for every record and flags the lower reading', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/vehicles/JN8AY2NY4K9012345')

    expect(await screen.findByRole('heading', { level: 1, name: '2019 Nissan Patrol' })).toBeInTheDocument()
    expect(calls[0].pathname).toBe('/api/v1/vehicles/JN8AY2NY4K9012345/timeline')
    expect(calls[0].search).toBe('')

    const items = within(screen.getByRole('list', { name: 'Service history' })).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    for (const text of ['11 Apr 2026', '88,300 km', 'Falcon Auto Workshop', 'Maintenance', 'Oil change', 'Mileage warning']) {
      expect(items[0]).toHaveTextContent(text)
    }
    for (const text of ['21 Jul 2025', '121,500 km', 'Repair', 'A/C service, Battery replacement']) expect(items[1]).toHaveTextContent(text)
    expect(items[1]).not.toHaveTextContent('Mileage warning')
    expect(items[2]).toHaveTextContent('Oasis Line Motors')
  })

  it('links a correction to the record it corrects and marks the original as corrected', async () => {
    stubApi(() => json(CAMRY))
    open('/vehicles/JTNBK3EK6N3012345')

    const items = within(await screen.findByRole('list', { name: 'Service history' })).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Correction')
    expect(within(items[0]).getByRole('link', { name: '5 Nov 2025 record' })).toHaveAttribute('href', `#record-${ORIGINAL_ID}`)
    expect(items[1]).toHaveAttribute('id', `record-${ORIGINAL_ID}`)
    expect(items[1]).toHaveTextContent('Corrected')
  })

  it('sends category, mileage-warning, date and order filters to the API and keeps them in the URL', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/vehicles/JN8AY2NY4K9012345')
    await screen.findByRole('list', { name: 'Service history' })
    const last = () => calls[calls.length - 1].searchParams

    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'repair' } })
    await waitFor(() => expect(last().get('category')).toBe('repair'))
    fireEvent.click(screen.getByLabelText('Only mileage warnings'))
    await waitFor(() => expect(last().get('flagged')).toBe('true'))
    fireEvent.change(screen.getByLabelText('Order'), { target: { value: 'asc' } })
    await waitFor(() => expect(last().get('order')).toBe('asc'))
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2025-01-01' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2025-12-31' } })
    await waitFor(() => {
      expect(last().get('from')).toBe('2025-01-01')
      expect(last().get('to')).toBe('2025-12-31')
    })

    const pageQuery = new URLSearchParams(window.location.search)
    expect(Object.fromEntries(pageQuery)).toEqual({
      category: 'repair', flagged: 'true', order: 'asc', from: '2025-01-01', to: '2025-12-31',
    })
  })

  it('refuses a date range that ends before it starts without calling the API', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/vehicles/JN8AY2NY4K9012345?from=2026-01-01')
    await screen.findByRole('list', { name: 'Service history' })

    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2025-01-01' } })

    expect(await screen.findByText("'To' must be on or after 'From'.")).toBeInTheDocument()
    expect(calls.some((url) => url.searchParams.get('to') === '2025-01-01')).toBe(false)
  })

  it('offers to watch a valid VIN that has no history yet', async () => {
    stubApi(() => json({ vin: 'MDHBN7AD0P0012345', vehicle: null, records: [] }))
    open('/vehicles/MDHBN7AD0P0012345')

    expect(await screen.findByRole('heading', { name: 'No service history yet' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in to watch this VIN' })).toHaveAttribute('href', '/login')
  })

  it('tells filtered-out results apart from an empty history and clears the filters', async () => {
    const calls = stubApi((url) => json(url.searchParams.has('category') ? { ...PATROL, records: [] } : PATROL))
    open('/vehicles/JN8AY2NY4K9012345?category=repair')

    expect(await screen.findByRole('heading', { name: 'No records match these filters' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Log in to watch this VIN' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(await screen.findByRole('list', { name: 'Service history' })).toBeInTheDocument()
    expect(calls[calls.length - 1].search).toBe('')
    expect(window.location.search).toBe('')
  })

  it('rejects a malformed VIN in the address without calling the API', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/vehicles/NOT-A-VIN')

    expect(await screen.findByText('A VIN has exactly 17 letters or digits and never contains I, O or Q.')).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  })

  it('rewrites a lower-case or dashed VIN in the address to its canonical form', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/vehicles/jn8ay2ny4k9-012345')

    await screen.findByRole('list', { name: 'Service history' })
    expect(window.location.pathname).toBe('/vehicles/JN8AY2NY4K9012345')
    expect(calls.every((url) => url.pathname === '/api/v1/vehicles/JN8AY2NY4K9012345/timeline')).toBe(true)
  })

  it('shows the server error when the lookup fails', async () => {
    stubApi(() => json({ error: { code: 'internal_error', message: 'Something broke on our side.' } }, 500))
    open('/vehicles/JN8AY2NY4K9012345')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something broke on our side.')
  })
})

describe('VIN search on the home page', () => {
  it('normalizes what the visitor typed and opens that vehicle', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/')

    fireEvent.change(await screen.findByLabelText('VIN (chassis number)'), { target: { value: 'jn8ay2ny4k9-٠١٢٣٤٥' } })
    fireEvent.click(screen.getByRole('button', { name: 'Look up' }))

    expect(await screen.findByRole('heading', { level: 1, name: '2019 Nissan Patrol' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/vehicles/JN8AY2NY4K9012345')
    expect(calls[0].pathname).toBe('/api/v1/vehicles/JN8AY2NY4K9012345/timeline')
  })

  it('explains an invalid VIN and stays on the page', async () => {
    const calls = stubApi(() => json(PATROL))
    open('/')

    fireEvent.change(await screen.findByLabelText('VIN (chassis number)'), { target: { value: 'ABC123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Look up' }))

    expect(await screen.findByText('A VIN has exactly 17 letters or digits and never contains I, O or Q.')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(calls).toHaveLength(0)
  })
})
