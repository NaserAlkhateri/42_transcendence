// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import type { Membership, User } from '../auth/auth-context'
import type { RecordSearchItem } from '../lib/recordSearch'

const WORK_CODES = [
  { code: 'OIL_CHANGE', label: 'Oil change', label_ar: 'تغيير الزيت' },
  { code: 'AC_SERVICE', label: 'A/C service', label_ar: 'صيانة المكيف' },
  { code: 'BRAKE_PADS', label: 'Brake pads', label_ar: 'فحمات الفرامل' },
]

const FALCON: Membership = {
  id: 'mem-1', organization_id: 'org-falcon', organization_name: 'Falcon Bay Auto Care',
  organization_status: 'approved', role: 'entity_staff', status: 'active',
}
const OASIS: Membership = { ...FALCON, id: 'mem-2', organization_id: 'org-oasis', organization_name: 'Oasis Line Motors' }

function account(overrides: Partial<User>): User {
  return {
    id: 'user-arjun', email: 'falcon.staff@sijil.demo', full_name: 'Arjun Nair', role: 'consumer',
    effective_role: 'entity_staff', must_change_password: false, created_at: '2026-10-12T08:00:00Z', memberships: [FALCON],
    ...overrides,
  }
}

const STAFF = account({})
const ADMIN = account({
  id: 'admin', email: 'admin@sijil.demo', full_name: 'Platform Admin', role: 'platform_admin',
  effective_role: 'platform_admin', memberships: [],
})
const CONSUMER = account({ id: 'user-omar', email: 'omar@sijil.demo', full_name: 'Omar Haddad', effective_role: 'consumer', memberships: [] })

// RecordSearchItem from backend/app/schemas/record_search.py.
function item(overrides: Partial<RecordSearchItem>): RecordSearchItem {
  return {
    id: 'rec', vin: 'JN8AY2NY4K9012345', make: 'Nissan', model: 'Patrol', model_year: 2019, service_date: '2026-04-11',
    created_at: '2026-04-11T08:00:00Z', category: 'maintenance', work_codes: ['OIL_CHANGE', 'AC_SERVICE'], odometer_km: 88300,
    organization_id: 'org-falcon', organization_name: 'Falcon Bay Auto Care', staff_name: 'Arjun Nair', notes: null,
    is_mileage_flagged: true, corrects_record_id: null, correction_reason: null, corrected_by_id: null, ...overrides,
  }
}

const PATROL = item({ id: 'rec-patrol' })
const CAMRY_VEHICLE = { vin: 'JTNBK3EK6N3012345', make: 'Toyota', model: 'Camry', model_year: 2022 }
const CAMRY_FIX = item({
  ...CAMRY_VEHICLE, id: 'rec-camry-fix', service_date: '2025-11-05', created_at: '2025-11-06T09:00:00Z', category: 'repair',
  work_codes: ['BRAKE_PADS'], odometer_km: 45100, is_mileage_flagged: false, corrects_record_id: 'rec-camry',
  correction_reason: 'odometer', staff_name: 'Mariam Al Hashimi',
})
const CAMRY = item({
  ...CAMRY_VEHICLE, id: 'rec-camry', service_date: '2025-11-05', created_at: '2025-11-05T09:00:00Z', category: 'repair',
  work_codes: ['BRAKE_PADS'], odometer_km: 451000, is_mileage_flagged: false, corrected_by_id: 'rec-camry-fix',
})

function many(count: number): RecordSearchItem[] {
  return Array.from({ length: count }, (_, index) => item({ id: `rec-${index + 1}`, odometer_km: 1000 * (index + 1) }))
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** The API's paging over `rows`: the page the request asks for, and the total of every row. */
function paged(rows: RecordSearchItem[], url: URL) {
  const page = Number(url.searchParams.get('page'))
  const pageSize = Number(url.searchParams.get('page_size'))
  return json({ items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, page_size: pageSize })
}

function stubApi({ user = STAFF, rows = [PATROL, CAMRY_FIX, CAMRY], search }: {
  user?: User
  rows?: RecordSearchItem[]
  search?: (url: URL) => Response | Promise<Response>
} = {}) {
  const searches: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/auth/session') return json({ user })
    if (url.pathname === '/api/v1/work-codes') return json(WORK_CODES)
    if (url.pathname.endsWith('/records/search') || url.pathname === '/api/v1/admin/records') {
      searches.push(`${url.pathname}${url.search}`)
      return search ? search(url) : paged(rows, url)
    }
    throw new Error(`unexpected request ${url.pathname}`)
  }))
  return searches
}

const last = (searches: string[]) => searches[searches.length - 1]

const ORG_SEARCH = '/api/v1/organizations/org-falcon/records/search'
const DEFAULT_QUERY = 'sort=service_date&order=desc&page=1&page_size=20'

function open(path: string) {
  window.history.replaceState(null, '', path)
  render(<App />)
}

function findResults() {
  return screen.findByRole('table', { name: 'Service records matching the filters' })
}

function dataRows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

function type(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function search() {
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('record search: organisation scope', () => {
  it('lists the organisation’s records with UAE formats, badges and a link to each vehicle', async () => {
    const searches = stubApi()
    open('/workshop/records')
    const table = await findResults()

    expect(searches).toEqual([`${ORG_SEARCH}?${DEFAULT_QUERY}`])
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Search records')
    expect(screen.getByText(/^Organisation:/)).toHaveTextContent('Falcon Bay Auto Care')
    expect(screen.getByText('Showing 1–3 of 3 records')).toBeInTheDocument()

    const [patrol, fix, original] = dataRows(table)
    await waitFor(() => expect(patrol).toHaveTextContent('Oil change, A/C service')) // labels from /work-codes
    expect(patrol).toHaveTextContent('11/04/2026')
    expect(patrol).toHaveTextContent('2019 Nissan Patrol')
    expect(patrol).toHaveTextContent('Maintenance')
    expect(patrol).toHaveTextContent('88,300 km')
    expect(patrol).toHaveTextContent('Arjun Nair')
    expect(within(patrol).getByText('Mileage flagged')).toBeInTheDocument()
    expect(within(patrol).getByRole('link', { name: 'JN8AY2NY4K9012345' })).toHaveAttribute('href', '/vehicles/JN8AY2NY4K9012345')
    expect(within(patrol).getByRole('link', { name: 'JN8AY2NY4K9012345' })).toHaveAttribute('dir', 'ltr')

    expect(fix).toHaveTextContent('05/11/2025')
    expect(fix).toHaveTextContent('06/11/2025') // recorded a day later
    expect(within(fix).getByText('Correction')).toBeInTheDocument()
    expect(within(fix).queryByText('Corrected')).toBeNull()
    expect(within(original).getByText('Corrected')).toBeInTheDocument()
    expect(original).toHaveTextContent('451,000 km')

    // Staff names, not organisations, inside one organisation's search.
    expect(within(table).getByRole('columnheader', { name: 'Staff' })).toBeInTheDocument()
    expect(within(table).queryByRole('columnheader', { name: 'Organisation' })).toBeNull()
    expect(screen.queryByLabelText('Organisation name')).toBeNull()
    expect(within(table).getByRole('columnheader', { name: 'Service date' })).toHaveAttribute('aria-sort', 'descending')
  })

  it('shows a spinner while the first page loads', async () => {
    let answer: (response: Response) => void = () => undefined
    stubApi({ search: () => new Promise<Response>((resolve) => { answer = resolve }) })
    open('/workshop/records')

    expect(await screen.findByText('Loading records')).toBeInTheDocument()
    act(() => answer(json({ items: [PATROL], total: 1, page: 1, page_size: 20 })))
    await findResults()
    expect(screen.getByText('Showing 1 of 1 record')).toBeInTheDocument()
  })

  it('builds the API query from the form and keeps the search in the address', async () => {
    const searches = stubApi()
    open('/workshop/records')
    await findResults()

    type(/^VIN \(chassis number\)/, 'jn8-ay2')
    type('Make', ' Nissan ')
    type('Model', 'Patrol')
    type('Category', 'maintenance')
    type('Service date from', '2026-01-01')
    type('Service date to', '2026-04-30')
    type('Minimum odometer (km)', '٨٠٠٠٠') // Arabic-Indic digits are accepted
    type('Maximum odometer (km)', '120000')
    type('Model year from', '2018')
    type('Model year to', '2020')
    type('Staff name', 'Arjun')
    type('Mileage flag', 'true')
    type('Record type', 'original')
    type('Corrected by a later record', 'false')
    fireEvent.click(screen.getByLabelText('Oil change'))
    fireEvent.click(screen.getByLabelText('A/C service'))
    search()

    const query = 'vin=JN8AY2&make=Nissan&model=Patrol&year_from=2018&year_to=2020&category=maintenance' +
      '&work_code=OIL_CHANGE&work_code=AC_SERVICE&flagged=true&record_type=original&corrected=false' +
      '&date_from=2026-01-01&date_to=2026-04-30&odometer_min=80000&odometer_max=120000&staff=Arjun'
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?${query}&${DEFAULT_QUERY}`))
    expect(window.location.search).toBe(`?${query}`)
    // The form shows the values as they were searched.
    expect(screen.getByLabelText(/^VIN \(chassis number\)/)).toHaveValue('JN8AY2')
    expect(screen.getByLabelText('Minimum odometer (km)')).toHaveValue('80000')
    await findResults()
  })

  it('restores the form, sort and page from a shared link', async () => {
    const searches = stubApi({ rows: many(15) })
    open('/workshop/records?vin=JN8&category=repair&work_code=AC_SERVICE&date_from=2026-01-01&sort=vin&order=asc&page=2&page_size=10')
    const table = await findResults()

    expect(searches).toEqual([
      `${ORG_SEARCH}?vin=JN8&category=repair&work_code=AC_SERVICE&date_from=2026-01-01&sort=vin&order=asc&page=2&page_size=10`,
    ])
    expect(screen.getByLabelText(/^VIN \(chassis number\)/)).toHaveValue('JN8')
    expect(screen.getByLabelText('Category')).toHaveValue('repair')
    expect(screen.getByLabelText('Service date from')).toHaveValue('2026-01-01')
    expect(screen.getByLabelText('Records per page')).toHaveValue('10')
    expect(await screen.findByLabelText('A/C service')).toBeChecked()
    expect(screen.getByLabelText('Oil change')).not.toBeChecked()
    expect(within(table).getByRole('columnheader', { name: 'VIN' })).toHaveAttribute('aria-sort', 'ascending')
    expect(screen.getByText('Showing 11–15 of 15 records')).toBeInTheDocument()
  })

  it('toggles the order from a column heading and starts again at page 1', async () => {
    const searches = stubApi({ rows: many(45) })
    open('/workshop/records?page=2')
    await findResults()

    fireEvent.click(screen.getByRole('button', { name: 'Odometer' }))
    await waitFor(() => expect(window.location.search).toBe('?sort=odometer_km'))
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?sort=odometer_km&order=desc&page=1&page_size=20`))
    expect(screen.getByRole('columnheader', { name: 'Odometer' })).toHaveAttribute('aria-sort', 'descending')
    expect(screen.getByRole('columnheader', { name: 'Service date' })).not.toHaveAttribute('aria-sort')

    fireEvent.click(screen.getByRole('button', { name: 'Odometer' }))
    await waitFor(() => expect(window.location.search).toBe('?sort=odometer_km&order=asc'))
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?sort=odometer_km&order=asc&page=1&page_size=20`))
    expect(screen.getByRole('columnheader', { name: 'Odometer' })).toHaveAttribute('aria-sort', 'ascending')

    // Names and VINs start A to Z.
    fireEvent.click(screen.getByRole('button', { name: 'Vehicle' }))
    await waitFor(() => expect(window.location.search).toBe('?sort=make&order=asc'))
    await findResults()
  })

  it('pages through the results and changes the page size', async () => {
    const searches = stubApi({ rows: many(45) })
    open('/workshop/records')
    await findResults()
    expect(screen.getByText('Showing 1–20 of 45 records')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(window.location.search).toBe('?page=2'))
    expect(await screen.findByText('Showing 21–40 of 45 records')).toBeInTheDocument()
    expect(last(searches)).toBe(`${ORG_SEARCH}?sort=service_date&order=desc&page=2&page_size=20`)

    type('Records per page', '50')
    await waitFor(() => expect(window.location.search).toBe('?page_size=50'))
    expect(await screen.findByText('Showing 1–45 of 45 records')).toBeInTheDocument()
    expect(last(searches)).toBe(`${ORG_SEARCH}?sort=service_date&order=desc&page=1&page_size=50`)
  })

  it('goes back to page 1 when the filters change, keeping the sort', async () => {
    const searches = stubApi({ rows: many(45) })
    open('/workshop/records?page=3&sort=odometer_km')
    await findResults()

    type('Make', 'Toyota')
    search()
    await waitFor(() => expect(window.location.search).toBe('?make=Toyota&sort=odometer_km'))
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?make=Toyota&sort=odometer_km&order=desc&page=1&page_size=20`))
    await findResults()
  })

  it('shows the last page when the address points past it', async () => {
    const searches = stubApi({ rows: many(45) })
    open('/workshop/records?page=9')

    expect(await screen.findByText('Showing 41–45 of 45 records')).toBeInTheDocument()
    expect(window.location.search).toBe('?page=3')
    expect(searches).toEqual([
      `${ORG_SEARCH}?sort=service_date&order=desc&page=9&page_size=20`,
      `${ORG_SEARCH}?sort=service_date&order=desc&page=3&page_size=20`,
    ])
  })

  it('runs the search again when Search is pressed with the same filters', async () => {
    const searches = stubApi()
    open('/workshop/records?make=Nissan')
    await findResults()

    search()
    await waitFor(() => expect(searches).toHaveLength(2))
    expect(searches[1]).toBe(searches[0])
    expect(window.location.search).toBe('?make=Nissan')
    await findResults()
  })

  it('runs the search again on the first press even when the address is tidied', async () => {
    const searches = stubApi()
    open('/workshop/records?page=1&make=nissan&order=desc')
    await findResults()

    search()
    await waitFor(() => expect(searches).toHaveLength(2))
    expect(searches[1]).toBe(searches[0])
    expect(window.location.search).toBe('?make=nissan')
    await findResults()
  })

  it('follows back and forward', async () => {
    const searches = stubApi()
    open('/workshop/records')
    await findResults()
    type('Make', 'Nissan')
    search()
    await waitFor(() => expect(window.location.search).toBe('?make=Nissan'))
    await findResults()

    act(() => window.history.back())
    await waitFor(() => expect(window.location.search).toBe(''))
    await waitFor(() => expect(screen.getByLabelText('Make')).toHaveValue(''))
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?${DEFAULT_QUERY}`))

    act(() => window.history.forward())
    await waitFor(() => expect(screen.getByLabelText('Make')).toHaveValue('Nissan'))
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?make=Nissan&${DEFAULT_QUERY}`))
    await findResults()
  })

  it('offers to clear the filters when nothing matches', async () => {
    const searches = stubApi({ search: (url) => paged(url.searchParams.has('make') ? [] : [PATROL], url) })
    open('/workshop/records?make=Lexus&page_size=50')

    expect(await screen.findByText('No records match these filters')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    await findResults()
    expect(window.location.search).toBe('?page_size=50') // the page size is not a filter
    expect(screen.getByLabelText('Make')).toHaveValue('')
    expect(last(searches)).toBe(`${ORG_SEARCH}?sort=service_date&order=desc&page=1&page_size=50`)
  })

  it('says when the organisation has no records yet', async () => {
    stubApi({ rows: [] })
    open('/workshop/records')

    expect(await screen.findByText('No service records yet')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clear filters' })).toBeNull()
  })

  it('shows the API’s message when the search is refused', async () => {
    stubApi({ search: () => json({ error: { code: 'unknown_work_code', message: 'Unknown work code: WINDOW_TINT.' } }, 422) })
    open('/workshop/records?work_code=WINDOW_TINT')

    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown work code: WINDOW_TINT.')
  })

  it('checks ranges and the VIN before searching', async () => {
    const searches = stubApi()
    open('/workshop/records')
    await findResults()

    type('Service date from', '2026-05-01')
    type('Service date to', '2026-04-11')
    type('Minimum odometer (km)', '120000')
    type('Maximum odometer (km)', '50000')
    type('Model year from', '2022')
    type('Model year to', '2018')
    type(/^VIN \(chassis number\)/, 'JTO')
    search()

    expect(await screen.findByText("Choose a date on or after the 'from' date.")).toBeInTheDocument()
    expect(screen.getByText('Enter a maximum that is at least the minimum.')).toBeInTheDocument()
    expect(screen.getByText("Choose a year on or after the 'from' year.")).toBeInTheDocument()
    expect(screen.getByText(/never contains I, O or Q/)).toBeInTheDocument()
    expect(screen.getByLabelText('Service date to')).toHaveAttribute('aria-invalid', 'true')
    expect(searches).toHaveLength(1)
    expect(window.location.search).toBe('')

    // Clear empties the form and the errors.
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    expect(screen.queryByText("Choose a date on or after the 'from' date.")).toBeNull()
    expect(screen.getByLabelText('Service date from')).toHaveValue('')
  })

  it('clears the filters from the address with the form’s Clear button, keeping the sort', async () => {
    const searches = stubApi()
    open('/workshop/records?make=Nissan&staff=Arjun&page=2&sort=vin&order=asc')
    await findResults()
    expect(screen.getByLabelText('Make')).toHaveValue('Nissan')

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    await waitFor(() => expect(window.location.search).toBe('?sort=vin&order=asc'))
    await waitFor(() => expect(last(searches)).toBe(`${ORG_SEARCH}?sort=vin&order=asc&page=1&page_size=20`))
    expect(screen.getByLabelText('Make')).toHaveValue('')
    expect(screen.getByLabelText('Staff name')).toHaveValue('')
    await findResults()
  })

  it('ignores an impossible date in the address', async () => {
    const searches = stubApi()
    open('/workshop/records?date_from=2026-02-31&make=Nissan')
    await findResults()

    expect(searches).toEqual([`${ORG_SEARCH}?make=Nissan&${DEFAULT_QUERY}`])
    expect(screen.getByLabelText('Service date from')).toHaveValue('')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('does not send a reversed range from the address', async () => {
    const searches = stubApi()
    open('/workshop/records?year_from=2022&year_to=2018')

    expect(await screen.findByText("Choose a year on or after the 'from' year.")).toBeInTheDocument()
    expect(screen.getByText('Correct the highlighted filters, then search again.')).toBeInTheDocument()
    await screen.findByLabelText('Oil change')
    expect(searches).toEqual([])
  })

  it('lets a member of two organisations choose which one to search', async () => {
    const searches = stubApi({ user: account({ memberships: [FALCON, OASIS] }) })
    open('/workshop/records')
    await findResults()
    expect(searches).toEqual([`${ORG_SEARCH}?${DEFAULT_QUERY}`])

    type(/^Organisation/, 'org-oasis')
    await waitFor(() => expect(window.location.search).toBe('?org=org-oasis'))
    await waitFor(() => expect(last(searches)).toBe(`/api/v1/organizations/org-oasis/records/search?${DEFAULT_QUERY}`))
    await findResults()
  })

  it('marks only the current page in the navigation', async () => {
    stubApi()
    open('/workshop/records')
    await findResults()
    expect(screen.getByRole('link', { name: 'Search records' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Add record' })).not.toHaveAttribute('aria-current')
    cleanup()

    open('/workshop/records/new')
    expect(await screen.findByRole('link', { name: 'Add record' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Search records' })).not.toHaveAttribute('aria-current')
    await screen.findByLabelText('Oil change')
  })
})

describe('record search: export (AG-07)', () => {
  const CSV_FILE = () => new Response(`${String.fromCharCode(0xfeff)}record_id,vin\r\n`, {
    status: 200,
    headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="sijil-records-20261020-0815.csv"' },
  })
  let saved: { name: string; url: string }[] = []

  beforeEach(() => {
    saved = []
    // jsdom has no object URLs and cannot follow a download link: record what would be saved.
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:http://localhost/export'), revokeObjectURL: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push({ name: this.download, url: this.href })
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  /** Answers export requests (after stubApi) and logs their paths. */
  function stubExports(respond: (url: URL) => Response | Promise<Response> = CSV_FILE) {
    const searchFetch = globalThis.fetch
    const exports: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.endsWith('/records/export')) {
        exports.push(`${url.pathname}${url.search}`)
        return respond(url)
      }
      return searchFetch(input, init)
    }))
    return exports
  }

  const rowBox = (vin: string, date: string, km: string) =>
    screen.getByRole('checkbox', { name: `Select the record for ${vin}, ${date}, ${km}` })

  it('downloads every page of the current filters and sort as CSV or JSON', async () => {
    stubApi({ rows: many(45) })
    const exports = stubExports()
    open('/workshop/records?make=Nissan&work_code=OIL_CHANGE&sort=odometer_km&order=asc&page=2')
    await findResults()

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    await waitFor(() => expect(saved).toEqual([{ name: 'sijil-records-20261020-0815.csv', url: 'blob:http://localhost/export' }]))
    expect(exports).toEqual([
      '/api/v1/organizations/org-falcon/records/export?make=Nissan&work_code=OIL_CHANGE&sort=odometer_km&order=asc&format=csv',
    ])
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled())

    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    await waitFor(() => expect(exports).toHaveLength(2))
    expect(exports[1]).toBe(
      '/api/v1/organizations/org-falcon/records/export?make=Nissan&work_code=OIL_CHANGE&sort=odometer_km&order=asc&format=json',
    )
    await waitFor(() => expect(saved).toHaveLength(2))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export JSON' })).toBeEnabled())
  })

  it('shows progress and keeps the other export buttons disabled while a file downloads', async () => {
    stubApi()
    let answer: (response: Response) => void = () => undefined
    stubExports(() => new Promise<Response>((resolve) => { answer = resolve }))
    open('/workshop/records')
    await findResults()

    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    const busy = await screen.findByRole('button', { name: /Export JSON/ })
    await waitFor(() => expect(busy).toHaveAttribute('aria-busy', 'true'))
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled()

    act(() => answer(CSV_FILE()))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export JSON' })).not.toHaveAttribute('aria-busy'))
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled()
    expect(saved).toHaveLength(1)
  })

  it('exports only the selected rows, and select-all picks every row on the page', async () => {
    stubApi()
    const exports = stubExports()
    open('/workshop/records')
    await findResults()
    expect(screen.queryByRole('group', { name: /Export selected/ })).toBeNull()

    fireEvent.click(rowBox('JN8AY2NY4K9012345', '11/04/2026', '88,300 km'))
    fireEvent.click(rowBox('JTNBK3EK6N3012345', '05/11/2025', '451,000 km'))
    const selectAll = screen.getByRole('checkbox', { name: 'Select all records on this page' })
    expect(selectAll).not.toBeChecked()
    expect((selectAll as HTMLInputElement).indeterminate).toBe(true)

    const group = screen.getByRole('group', { name: 'Export selected (2)' })
    fireEvent.click(within(group).getByRole('button', { name: 'JSON' }))
    await waitFor(() => expect(exports).toEqual([
      '/api/v1/organizations/org-falcon/records/export?sort=service_date&order=desc&format=json&ids=rec-patrol&ids=rec-camry',
    ]))
    await waitFor(() => expect(within(group).getByRole('button', { name: 'JSON' })).toBeEnabled())

    fireEvent.click(selectAll)
    expect(selectAll).toBeChecked()
    expect((selectAll as HTMLInputElement).indeterminate).toBe(false)
    expect(screen.getByRole('group', { name: 'Export selected (3)' })).toBeInTheDocument()
    fireEvent.click(within(screen.getByRole('group', { name: 'Export selected (3)' })).getByRole('button', { name: 'CSV' }))
    await waitFor(() => expect(exports).toHaveLength(2))
    expect(new URL(exports[1], 'http://localhost').searchParams.getAll('ids')).toEqual(['rec-patrol', 'rec-camry-fix', 'rec-camry'])
    await waitFor(() => expect(saved).toHaveLength(2))

    fireEvent.click(screen.getByRole('button', { name: 'Clear selection' }))
    expect(screen.queryByRole('group', { name: /Export selected/ })).toBeNull()
    expect(selectAll).not.toBeChecked()
    // The focused button is gone: focus moves to the export buttons instead of the top of the page.
    expect(screen.getByRole('button', { name: 'Export CSV' })).toHaveFocus()
  })

  it('forgets the selection and an export error when the user comes back to an earlier page', async () => {
    stubApi({ rows: many(45) })
    stubExports(() => json({ error: { code: 'export_too_large', message: 'More than 5,000 records match.' } }, 422))
    open('/workshop/records')
    await findResults()
    const selectAll = () => screen.getByRole('checkbox', { name: 'Select all records on this page' })

    fireEvent.click(selectAll())
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('More than 5,000 records match.')
    expect(screen.getByRole('group', { name: 'Export selected (20)' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(await screen.findByText('Showing 21–40 of 45 records')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Previous page' }))
    expect(await screen.findByText('Showing 1–20 of 45 records')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /Export selected/ })).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(selectAll()).not.toBeChecked()

    fireEvent.click(selectAll())
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(await screen.findByText('Showing 21–40 of 45 records')).toBeInTheDocument()
    act(() => window.history.back())
    expect(await screen.findByText('Showing 1–20 of 45 records')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /Export selected/ })).toBeNull()
    expect(selectAll()).not.toBeChecked()
  })

  it('clears the selection when the page, sort or filters change', async () => {
    stubApi({ rows: many(45) })
    stubExports()
    open('/workshop/records')
    await findResults()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all records on this page' }))
    expect(screen.getByRole('group', { name: 'Export selected (20)' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(await screen.findByText('Showing 21–40 of 45 records')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /Export selected/ })).toBeNull()
    expect(screen.getByRole('checkbox', { name: 'Select all records on this page' })).not.toBeChecked()

    fireEvent.click(rowBox('JN8AY2NY4K9012345', '11/04/2026', '21,000 km'))
    expect(screen.getByRole('group', { name: 'Export selected (1)' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Odometer' }))
    await waitFor(() => expect(window.location.search).toBe('?sort=odometer_km'))
    await findResults()
    await waitFor(() => expect(screen.queryByRole('group', { name: /Export selected/ })).toBeNull())
  })

  it('shows the API’s message when the export is refused', async () => {
    stubApi()
    stubExports(() => json({
      error: { code: 'export_too_large', message: 'More than 5,000 records match. Narrow the filters and export again.' },
    }, 422))
    open('/workshop/records')
    await findResults()

    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The export could not be completed')
    expect(alert).toHaveTextContent('More than 5,000 records match. Narrow the filters and export again.')
    expect(saved).toEqual([])
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled())

    fireEvent.click(within(alert).getByRole('button', { name: 'Dismiss alert' }))
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('downloads platform-wide for admins, organisation filter included', async () => {
    stubApi({ user: ADMIN })
    const exports = stubExports()
    open('/admin/records?organization=Falcon&sort=organization_name&order=asc')
    await findResults()

    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    await waitFor(() => expect(exports).toEqual([
      '/api/v1/admin/records/export?organization=Falcon&sort=organization_name&order=asc&format=json',
    ]))
    await waitFor(() => expect(saved).toHaveLength(1))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export JSON' })).toBeEnabled())
  })

  it('offers no export when nothing matches', async () => {
    stubApi({ rows: [] })
    open('/workshop/records')
    expect(await screen.findByText('No service records yet')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Export CSV' })).toBeNull()
  })
})

describe('record search: platform admins', () => {
  it('searches every organisation and filters and sorts by organisation', async () => {
    const deleted = item({ id: 'rec-deleted', organization_id: null, organization_name: 'Sand Dune Garage', is_mileage_flagged: false })
    const searches = stubApi({ user: ADMIN, rows: [PATROL, deleted] })
    open('/admin/records')
    const table = await findResults()

    expect(searches).toEqual([`/api/v1/admin/records?${DEFAULT_QUERY}`])
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Records')
    expect(screen.queryByText(/^Organisation:/)).toBeNull()
    expect(within(table).getByRole('columnheader', { name: 'Organisation' })).toBeInTheDocument()
    expect(within(table).queryByRole('columnheader', { name: 'Staff' })).toBeNull()
    const [falcon, sandDune] = dataRows(table)
    expect(falcon).toHaveTextContent('Falcon Bay Auto Care')
    expect(sandDune).toHaveTextContent('Sand Dune Garage (deleted)')

    type('Organisation name', 'Falcon')
    type('Staff name', 'Arjun')
    search()
    await waitFor(() => expect(last(searches)).toBe(`/api/v1/admin/records?staff=Arjun&organization=Falcon&${DEFAULT_QUERY}`))
    await findResults()

    fireEvent.click(screen.getByRole('button', { name: 'Organisation' }))
    await waitFor(() => expect(window.location.search).toBe('?staff=Arjun&organization=Falcon&sort=organization_name&order=asc'))
    await waitFor(() => expect(last(searches)).toBe(
      '/api/v1/admin/records?staff=Arjun&organization=Falcon&sort=organization_name&order=asc&page=1&page_size=20',
    ))
    expect(screen.getByRole('columnheader', { name: 'Organisation' })).toHaveAttribute('aria-sort', 'ascending')
    await findResults()
  })

  it('says when no organisation has added a record', async () => {
    stubApi({ user: ADMIN, rows: [] })
    open('/admin/records')
    expect(await screen.findByText('No organisation has added a service record yet.')).toBeInTheDocument()
  })
})

describe('record search: access', () => {
  it.each([
    ['a consumer', CONSUMER, '/workshop/records'],
    ['a consumer', CONSUMER, '/admin/records'],
    ['workshop staff', STAFF, '/admin/records'],
    ['a platform admin', ADMIN, '/workshop/records'],
  ])('denies %s on %s', async (_, user, path) => {
    const searches = stubApi({ user })
    open(path)
    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument()
    expect(searches).toEqual([])
  })

  it('sends guests to log in', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ user: null })))
    open('/admin/records')
    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
  })
})
