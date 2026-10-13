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

const MERCEDES: TimelineBody = {
  vin: 'WDDGF4HB1CA654321',
  vehicle: { vin: 'WDDGF4HB1CA654321', make: 'Mercedes-Benz', model: 'C 200', model_year: 2018 },
  records: [
    {
      id: '6f1c2c1e-0000-4000-8000-000000000003', service_date: '2026-04-11', created_at: '2026-04-11T08:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 58100,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: true, corrects_record_id: null,
    },
    {
      id: '6f1c2c1e-0000-4000-8000-000000000002', service_date: '2025-09-22', created_at: '2025-09-22T08:00:00Z',
      category: 'repair', work_codes: ['AC_SERVICE'], odometer_km: 71300,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: false, corrects_record_id: null,
    },
    {
      id: '6f1c2c1e-0000-4000-8000-000000000001', service_date: '2025-03-01', created_at: '2025-03-01T08:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 62000,
      organization_name: 'Oasis Line Motors', is_mileage_flagged: false, corrects_record_id: null,
    },
  ],
}

const ORIGINAL_ID = '7a2d3d2f-0000-4000-8000-000000000001'
const HYUNDAI: TimelineBody = {
  vin: 'KMHD841CBMU112233',
  vehicle: { vin: 'KMHD841CBMU112233', make: 'Hyundai', model: 'Elantra', model_year: 2021 },
  records: [
    {
      id: '7a2d3d2f-0000-4000-8000-000000000002', service_date: '2025-11-05', created_at: '2025-11-06T09:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 12100,
      organization_name: 'Falcon Auto Workshop', is_mileage_flagged: false, corrects_record_id: ORIGINAL_ID,
    },
    {
      id: ORIGINAL_ID, service_date: '2025-11-05', created_at: '2025-11-05T09:00:00Z',
      category: 'maintenance', work_codes: ['OIL_CHANGE'], odometer_km: 21000,
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
    if (url.pathname === '/api/v1/me') return json({ error: { code: 'not_authenticated', message: 'Sign in.' } }, 401)
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
    const calls = stubApi(() => json(MERCEDES))
    open('/vehicles/WDDGF4HB1CA654321')

    expect(await screen.findByRole('heading', { level: 1, name: '2018 Mercedes-Benz C 200' })).toBeInTheDocument()
    expect(calls[0].pathname).toBe('/api/v1/vehicles/WDDGF4HB1CA654321/timeline')
    expect(calls[0].search).toBe('')

    const items = within(screen.getByRole('list', { name: 'Service history' })).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    for (const text of ['11 Apr 2026', '58,100 km', 'Falcon Auto Workshop', 'Maintenance', 'Oil change', 'Mileage warning']) {
      expect(items[0]).toHaveTextContent(text)
    }
    for (const text of ['22 Sept 2025', '71,300 km', 'Repair', 'A/C service']) expect(items[1]).toHaveTextContent(text)
    expect(items[1]).not.toHaveTextContent('Mileage warning')
    expect(items[2]).toHaveTextContent('Oasis Line Motors')
  })

  it('links a correction to the record it corrects and marks the original as corrected', async () => {
    stubApi(() => json(HYUNDAI))
    open('/vehicles/KMHD841CBMU112233')

    const items = within(await screen.findByRole('list', { name: 'Service history' })).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Correction')
    expect(within(items[0]).getByRole('link', { name: '5 Nov 2025 record' })).toHaveAttribute('href', `#record-${ORIGINAL_ID}`)
    expect(items[1]).toHaveAttribute('id', `record-${ORIGINAL_ID}`)
    expect(items[1]).toHaveTextContent('Corrected')
  })

  it('sends category, mileage-warning, date and order filters to the API and keeps them in the URL', async () => {
    const calls = stubApi(() => json(MERCEDES))
    open('/vehicles/WDDGF4HB1CA654321')
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
    const calls = stubApi(() => json(MERCEDES))
    open('/vehicles/WDDGF4HB1CA654321?from=2026-01-01')
    await screen.findByRole('list', { name: 'Service history' })

    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2025-01-01' } })

    expect(await screen.findByText("'To' must be on or after 'From'.")).toBeInTheDocument()
    expect(calls.some((url) => url.searchParams.get('to') === '2025-01-01')).toBe(false)
  })

  it('offers to watch a valid VIN that has no history yet', async () => {
    stubApi(() => json({ vin: 'JTDBR32E720999999', vehicle: null, records: [] }))
    open('/vehicles/JTDBR32E720999999')

    expect(await screen.findByRole('heading', { name: 'No service history yet' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in to watch this VIN' })).toHaveAttribute('href', '/login')
  })

  it('tells filtered-out results apart from an empty history and clears the filters', async () => {
    const calls = stubApi((url) => json(url.searchParams.has('category') ? { ...MERCEDES, records: [] } : MERCEDES))
    open('/vehicles/WDDGF4HB1CA654321?category=repair')

    expect(await screen.findByRole('heading', { name: 'No records match these filters' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Log in to watch this VIN' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(await screen.findByRole('list', { name: 'Service history' })).toBeInTheDocument()
    expect(calls[calls.length - 1].search).toBe('')
    expect(window.location.search).toBe('')
  })

  it('rejects a malformed VIN in the address without calling the API', async () => {
    const calls = stubApi(() => json(MERCEDES))
    open('/vehicles/NOT-A-VIN')

    expect(await screen.findByText('A VIN has exactly 17 letters or digits and never contains I, O or Q.')).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  })

  it('rewrites a lower-case or dashed VIN in the address to its canonical form', async () => {
    const calls = stubApi(() => json(MERCEDES))
    open('/vehicles/wddgf4hb1ca-654321')

    await screen.findByRole('list', { name: 'Service history' })
    expect(window.location.pathname).toBe('/vehicles/WDDGF4HB1CA654321')
    expect(calls.every((url) => url.pathname === '/api/v1/vehicles/WDDGF4HB1CA654321/timeline')).toBe(true)
  })

  it('shows the server error when the lookup fails', async () => {
    stubApi(() => json({ error: { code: 'internal_error', message: 'Something broke on our side.' } }, 500))
    open('/vehicles/WDDGF4HB1CA654321')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something broke on our side.')
  })
})

describe('VIN search on the home page', () => {
  it('normalizes what the visitor typed and opens that vehicle', async () => {
    const calls = stubApi(() => json(MERCEDES))
    open('/')

    fireEvent.change(await screen.findByLabelText('VIN'), { target: { value: 'wddgf4hb1ca-٦٥٤٣٢١' } })
    fireEvent.click(screen.getByRole('button', { name: 'Look up' }))

    expect(await screen.findByRole('heading', { level: 1, name: '2018 Mercedes-Benz C 200' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/vehicles/WDDGF4HB1CA654321')
    expect(calls[0].pathname).toBe('/api/v1/vehicles/WDDGF4HB1CA654321/timeline')
  })

  it('explains an invalid VIN and stays on the page', async () => {
    const calls = stubApi(() => json(MERCEDES))
    open('/')

    fireEvent.change(await screen.findByLabelText('VIN'), { target: { value: 'ABC123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Look up' }))

    expect(await screen.findByText('A VIN has exactly 17 letters or digits and never contains I, O or Q.')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(calls).toHaveLength(0)
  })
})
