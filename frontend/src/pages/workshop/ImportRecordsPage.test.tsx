// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../App'
import type { Membership, User } from '../../auth/auth-context'
import type { ImportReport, ImportRowReport } from '../../lib/recordImport'

// Mirror backend/app/schemas: work codes, the signed-in staff user and the import report (record_transfer.py).
const WORK_CODES = [
  { code: 'OIL_CHANGE', label: 'Oil change', label_ar: 'تغيير الزيت' },
  { code: 'AIR_FILTER', label: 'Air filter', label_ar: 'فلتر الهواء' },
  { code: 'AC_SERVICE', label: 'A/C service', label_ar: 'صيانة المكيف' },
]

function member(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'mem-1', organization_id: 'org-falcon', organization_name: 'Falcon Bay Auto Care',
    organization_status: 'approved', role: 'entity_staff', status: 'active', ...overrides,
  }
}

function staff(memberships: Membership[] = [member()]): User {
  return {
    id: 'user-arjun', email: 'falcon.staff@sijil.demo', full_name: 'Arjun Nair', role: 'consumer',
    effective_role: 'entity_staff', must_change_password: false, created_at: '2026-10-12T08:00:00Z', memberships,
  }
}

const CONSUMER: User = { ...staff([]), id: 'user-omar', email: 'omar@sijil.demo', full_name: 'Omar Haddad', effective_role: 'consumer' }

function row(overrides: Partial<ImportRowReport>): ImportRowReport {
  return {
    row: 1, vin: 'JN8AY2NY4K9012345', service_date: '2026-04-11', odometer_km: 88300, category: 'maintenance',
    work_codes: ['OIL_CHANGE', 'AC_SERVICE'], status: 'ok', errors: [], will_be_flagged: false, ...overrides,
  }
}

function report(rows: ImportRowReport[], overrides: Partial<ImportReport> = {}): ImportReport {
  const valid = rows.filter((r) => r.status === 'ok')
  return {
    dry_run: true, format: 'csv', total_rows: rows.length, valid_rows: valid.length, invalid_rows: rows.length - valid.length,
    flagged_rows: valid.filter((r) => r.will_be_flagged).length, warnings: [], rows, ...overrides,
  }
}

const CLEAN = report([
  row({ row: 1, vin: 'JTMHX01J5M4012345', odometer_km: 61200, work_codes: ['AIR_FILTER'] }),
  row({ row: 2, service_date: '2026-03-01', odometer_km: 81000, will_be_flagged: true }),
])

const WITH_ERRORS = report([
  row({ row: 1, will_be_flagged: true }),
  row({
    row: 2, vin: null, work_codes: [], status: 'error',
    errors: [
      { field: 'vin', code: 'invalid_vin', message: 'A VIN has exactly 17 letters or digits and never contains I, O or Q.' },
      { field: 'work_codes', code: 'invalid_work_code', message: 'Unknown work code: WINDOW_TINT.' },
    ],
  }),
  row({
    row: 4, vin: 'JTNBK3EK6N3012345', service_date: '2025-11-05', odometer_km: 45100, category: 'repair', work_codes: ['AC_SERVICE'],
    status: 'error', errors: [{ field: null, code: 'duplicate_in_file', message: 'Same VIN, service date and odometer reading as row 3.' }],
  }),
], { warnings: ['Ignored columns: record_id, make.'] })

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

interface Post {
  path: string
  contentType: string | undefined
  csrf: string | undefined
  body: unknown
}

/** Network stub; records each import POST. Unknown requests fail the test. */
function stubApi(user: User, onImport: (dryRun: boolean, post: Post) => Response | Promise<Response> = () => json(CLEAN)) {
  const posts: Post[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/auth/session') return json({ user })
    if (url.pathname === '/api/v1/work-codes') return json(WORK_CODES)
    if (url.pathname === '/api/v1/auth/csrf') return json({ csrf_token: 'token' })
    if (init?.method === 'POST' && url.pathname.endsWith('/records/import')) {
      const headers = init.headers as Record<string, string>
      const post = { path: `${url.pathname}${url.search}`, contentType: headers['Content-Type'], csrf: headers['X-CSRF-Token'], body: init.body }
      posts.push(post)
      return onImport(url.searchParams.get('dry_run') === 'true', post)
    }
    throw new Error(`unexpected request ${init?.method ?? 'GET'} ${url.pathname}`)
  }))
  return posts
}

function open(path = '/workshop/records/import') {
  window.history.replaceState(null, '', path)
  render(<App />)
}

const csvFile = (name = 'falcon-records.csv', content = 'vin,service_date,odometer_km,category,work_codes\r\nJN8AY2NY4K9012345,11/04/2026,"88,300",maintenance,OIL_CHANGE;AC_SERVICE\r\n') =>
  new File([content], name, { type: 'text/csv' })

async function chooseFile(file: File) {
  fireEvent.change(await screen.findByLabelText(/^File \(CSV or JSON\)/), { target: { files: [file] } })
}

function check() {
  fireEvent.click(screen.getByRole('button', { name: 'Check file' }))
}

function resultRows() {
  return within(screen.getByRole('table', { name: 'Rows in the file' })).getAllByRole('row').slice(1)
}

let saved: { name: string; blob: Blob }[] = []

beforeEach(() => {
  saved = []
  // jsdom has no object URLs and cannot follow a download link: record what would be saved.
  const blobs = new Map<string, Blob>()
  Object.assign(URL, {
    createObjectURL: vi.fn((blob: Blob) => {
      const url = `blob:http://localhost/${blobs.size + 1}`
      blobs.set(url, blob)
      return url
    }),
    revokeObjectURL: vi.fn(),
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved.push({ name: this.download, blob: blobs.get(this.href) as Blob })
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('import records: preparing the file', () => {
  it('explains the format and lists the work codes with their labels', async () => {
    stubApi(staff())
    open()

    expect(await screen.findByRole('heading', { level: 1, name: 'Import records' })).toBeInTheDocument()
    expect(screen.getByText(/^Organisation:/)).toHaveTextContent('Falcon Bay Auto Care')
    const instructions = screen.getByRole('region', { name: 'Prepare the file' })
    expect(instructions).toHaveTextContent('Required: vin, service_date, odometer_km, category, work_codes. Optional: notes.')
    expect(instructions).toHaveTextContent('YYYY-MM-DD or DD/MM/YYYY, day first')
    expect(instructions).toHaveTextContent('separated by “;”')
    expect(instructions).toHaveTextContent('At most 512 KB and 500 records per file')
    expect(instructions).toHaveTextContent('All or nothing: if any row has an error, nothing is imported.')

    fireEvent.click(await screen.findByText('Work codes (3)'))
    const codes = screen.getByRole('table', { name: 'Work codes for the work_codes column' })
    expect(within(codes).getAllByRole('row').slice(1).map((r) => r.textContent)).toEqual([
      'OIL_CHANGEOil change', 'AIR_FILTERAir filter', 'AC_SERVICEA/C service',
    ])
  })

  it('downloads a CSV template with a fictional VIN and real work codes', async () => {
    stubApi(staff())
    open()

    const button = await screen.findByRole('button', { name: 'Download CSV template' })
    await waitFor(() => expect(button).toBeEnabled()) // once the work codes have loaded
    fireEvent.click(button)

    expect(saved).toHaveLength(1)
    expect(saved[0].name).toBe('sijil-import-template.csv')
    const text = await saved[0].blob.text()
    expect(text.split('\r\n')).toEqual([
      expect.stringMatching(/vin,service_date,odometer_km,category,work_codes,notes$/),
      'JTEBR3FJ0PK012345,11/04/2026,45200,maintenance,OIL_CHANGE;AIR_FILTER,Example row. Replace it with your own records.',
      '',
    ])
  })

  it('checks the file in the browser before sending anything', async () => {
    const posts = stubApi(staff())
    open()

    await screen.findByLabelText(/^File \(CSV or JSON\)/)
    check()
    expect(await screen.findByText('Choose a CSV or JSON file.')).toBeInTheDocument()

    await chooseFile(new File(['x'], 'mulkiya.png', { type: 'image/png' }))
    expect(screen.getByText('Choose a .csv or .json file.')).toBeInTheDocument()
    expect(screen.getByLabelText(/^File \(CSV or JSON\)/)).toHaveAttribute('aria-invalid', 'true')

    await chooseFile(new File([], 'empty.csv', { type: 'text/csv' }))
    expect(screen.getByText(/^The file is empty/)).toBeInTheDocument()

    await chooseFile(new File([new Uint8Array(512 * 1024 + 1)], 'huge.csv', { type: 'text/csv' }))
    expect(screen.getByText(/^The file is larger than 512 KB/)).toBeInTheDocument()
    check()
    expect(screen.getByText(/^The file is larger than 512 KB/)).toBeInTheDocument()

    await chooseFile(csvFile())
    expect(screen.queryByText(/^The file is larger than 512 KB/)).toBeNull()
    expect(posts).toEqual([])
  })
})

describe('import records: checking a file', () => {
  it('sends the file itself for a dry run and previews every row with UAE formats', async () => {
    const posts = stubApi(staff(), () => json(WITH_ERRORS))
    open()
    const file = csvFile()

    await chooseFile(file)
    check()
    expect(await screen.findByRole('heading', { name: 'Check results' })).toBeInTheDocument()
    expect(posts).toEqual([{
      path: '/api/v1/organizations/org-falcon/records/import?dry_run=true', contentType: 'text/csv', csrf: 'token', body: file,
    }])

    const summary = (term: string) => screen.getByText(term, { selector: 'dt' }).nextElementSibling
    expect(summary('Rows in the file')).toHaveTextContent('3')
    expect(summary('Ready to import')).toHaveTextContent('1')
    expect(summary('With errors')).toHaveTextContent('2')
    expect(summary('Mileage will be flagged')).toHaveTextContent('1')
    expect(screen.getByText('2 rows with errors')).toBeInTheDocument()
    expect(screen.getByText('Ignored columns: record_id, make.')).toBeInTheDocument()

    const [first, second, fourth] = resultRows()
    expect(first).toHaveTextContent('1')
    expect(within(first).getByText('OK')).toBeInTheDocument()
    expect(within(first).getByText('Mileage will be flagged')).toBeInTheDocument()
    expect(first).toHaveTextContent('JN8AY2NY4K9012345')
    expect(first).toHaveTextContent('11/04/2026')
    expect(first).toHaveTextContent('88,300 km')
    expect(first).toHaveTextContent('Maintenance')
    await waitFor(() => expect(first).toHaveTextContent('Oil change, A/C service'))

    expect(within(second).getByText('Error')).toBeInTheDocument()
    expect(second).toHaveTextContent('VIN: A VIN has exactly 17 letters or digits and never contains I, O or Q.')
    expect(second).toHaveTextContent('Work codes: Unknown work code: WINDOW_TINT.')
    expect(fourth).toHaveTextContent('4')
    expect(fourth).toHaveTextContent('05/11/2025')
    expect(fourth).toHaveTextContent('Row: Same VIN, service date and odometer reading as row 3.')

    const importButton = screen.getByRole('button', { name: 'Import 1 record' })
    expect(importButton).toBeDisabled()
    expect(importButton).toHaveAccessibleDescription('Fix every row with an error and check the file again before importing.')

    fireEvent.click(screen.getByLabelText('Show only rows with errors'))
    expect(resultRows().map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['2', '4'])
    fireEvent.click(screen.getByLabelText('Show only rows with errors'))
    expect(resultRows()).toHaveLength(3)
  })

  it('sends a JSON file as application/json', async () => {
    const posts = stubApi(staff(), () => json({ ...CLEAN, format: 'json' }))
    open()

    await chooseFile(new File(['{"records": []}'], 'sijil-records-20261020-0815.json', { type: 'application/json' }))
    check()
    await screen.findByRole('heading', { name: 'Check results' })
    expect(posts[0].contentType).toBe('application/json')
  })

  it.each([
    [413, 'payload_too_large', 'The file is larger than 512 KB. Split it into smaller files.', 'The file is too large'],
    [415, 'unsupported_media_type', 'Send the file as text/csv or application/json.', 'This type of file cannot be imported'],
    [422, 'invalid_encoding', 'The file must be UTF-8 text. In Excel, save it as "CSV UTF-8".', 'The file is not UTF-8 text'],
    [422, 'empty_file', 'The file has no records.', 'The file has no records'],
    [422, 'missing_columns', 'Missing required columns: odometer_km, work_codes.', 'Required columns are missing'],
    [422, 'too_many_rows', 'A file can hold at most 500 records. Split it into smaller files.', 'The file has too many records'],
  ])('explains a %s %s for the whole file', async (status, code, message, title) => {
    stubApi(staff(), () => json({ error: { code, message } }, status))
    open()

    await chooseFile(csvFile())
    check()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(title)
    expect(alert).toHaveTextContent(message)
    expect(screen.queryByRole('heading', { name: 'Check results' })).toBeNull()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Check file' })).toBeEnabled())
  })
})

describe('import records: importing', () => {
  it('imports a clean file after confirmation and links to the newest records', async () => {
    const posts = stubApi(staff(), (dryRun) => (dryRun ? json(CLEAN) : json({
      dry_run: false, imported: 2, flagged: 1, record_ids: ['rec-1', 'rec-2'],
    }, 201)))
    open()
    const file = csvFile()

    await chooseFile(file)
    check()
    expect(await screen.findByText('All 2 rows are ready to import')).toBeInTheDocument()
    expect(screen.getByText(/1 record will be saved with a mileage warning/)).toBeInTheDocument()
    expect(screen.getByLabelText('Show only rows with errors')).toBeDisabled()

    // Cancelling the confirmation sends nothing.
    fireEvent.click(screen.getByRole('button', { name: 'Import 2 records' }))
    let dialog = screen.getByRole('dialog', { name: 'Import 2 records?' })
    expect(dialog).toHaveTextContent('2 records will be added to the vehicle histories for Falcon Bay Auto Care.')
    expect(dialog).toHaveTextContent('1 record will be saved with a mileage warning.')
    expect(dialog).toHaveTextContent('Records are permanent.')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(posts).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Import 2 records' }))
    dialog = screen.getByRole('dialog', { name: 'Import 2 records?' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Import 2 records' }))

    expect(await screen.findByText('Imported 2 records (1 flagged)')).toBeInTheDocument()
    expect(posts[1]).toEqual({
      path: '/api/v1/organizations/org-falcon/records/import?dry_run=false', contentType: 'text/csv', csrf: 'token', body: file,
    })
    expect(screen.getByRole('link', { name: 'View the newest records' })).toHaveAttribute('href', '/workshop/records?sort=created_at')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Check results' })).toBeNull()
    expect(screen.getByLabelText(/^File \(CSV or JSON\)/)).toHaveValue('')
  })

  it('shows why nothing was imported when the import is refused', async () => {
    const refused = report([
      row({ row: 1 }),
      row({
        row: 2, status: 'error',
        errors: [{ field: null, code: 'already_recorded', message: 'Your organization has already recorded this service.' }],
      }),
    ], { dry_run: false })
    stubApi(staff(), (dryRun) => (dryRun ? json(CLEAN) : json({
      error: { code: 'import_invalid', message: '1 of 2 rows have errors. Nothing was imported.', details: refused },
    }, 422)))
    open()

    await chooseFile(csvFile())
    check()
    fireEvent.click(await screen.findByRole('button', { name: 'Import 2 records' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Import 2 records' }))

    expect(await screen.findByRole('heading', { name: 'Import refused' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Nothing was imported')
    expect(screen.getByRole('alert')).toHaveTextContent('1 of 2 rows have errors. Nothing was imported.')
    expect(resultRows()[1]).toHaveTextContent('Row: Your organization has already recorded this service.')
    expect(screen.getByRole('button', { name: 'Import 1 record' })).toBeDisabled()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByText(/^Imported/)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Choose another file' }))
    expect(screen.queryByRole('heading', { name: 'Import refused' })).toBeNull()
  })

  it('reports a failed import that is not about the rows', async () => {
    stubApi(staff(), (dryRun) => (dryRun ? json(CLEAN) : json({
      error: { code: 'organization_not_approved', message: 'Your organization is not approved yet.' },
    }, 403)))
    open()

    await chooseFile(csvFile())
    check()
    fireEvent.click(await screen.findByRole('button', { name: 'Import 2 records' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Import 2 records' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your organisation cannot add records yet')
    expect(alert).toHaveTextContent('Your organization is not approved yet.')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe('import records: organisations and access', () => {
  it('asks which organisation when the user works for more than one', async () => {
    const posts = stubApi(staff([
      member(),
      member({ id: 'mem-oasis', organization_id: 'org-oasis', organization_name: 'Oasis Line Motors' }),
    ]), (dryRun) => (dryRun ? json(CLEAN) : json({ dry_run: false, imported: 2, flagged: 1, record_ids: ['a', 'b'] }, 201)))
    open()

    await chooseFile(csvFile())
    check()
    expect(await screen.findByText('Choose an organisation.')).toBeInTheDocument()
    expect(posts).toEqual([])

    fireEvent.change(screen.getByLabelText(/^Organisation/), { target: { value: 'org-oasis' } })
    check()
    await screen.findByRole('heading', { name: 'Check results' })
    expect(posts[0].path).toBe('/api/v1/organizations/org-oasis/records/import?dry_run=true')

    fireEvent.click(screen.getByRole('button', { name: 'Import 2 records' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('for Oasis Line Motors')
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Import 2 records' }))
    expect(await screen.findByRole('link', { name: 'View the newest records' }))
      .toHaveAttribute('href', '/workshop/records?sort=created_at&org=org-oasis')
  })

  it('drops the check when the organisation changes', async () => {
    stubApi(staff([
      member(),
      member({ id: 'mem-oasis', organization_id: 'org-oasis', organization_name: 'Oasis Line Motors' }),
    ]))
    open()

    fireEvent.change(await screen.findByLabelText(/^Organisation/), { target: { value: 'org-falcon' } })
    await chooseFile(csvFile())
    check()
    await screen.findByRole('heading', { name: 'Check results' })
    fireEvent.change(screen.getByLabelText(/^Organisation/), { target: { value: 'org-oasis' } })
    expect(screen.queryByRole('heading', { name: 'Check results' })).toBeNull()
  })

  it('tells members of an organisation awaiting approval why they cannot import', async () => {
    stubApi(staff([member({ organization_status: 'pending', organization_name: 'Sand Dune Garage' })]))
    open()

    expect(await screen.findByText(/waiting for approval/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Check file' })).toBeNull()
  })

  it('is in the navigation and marked as the current page', async () => {
    stubApi(staff())
    open()

    expect(await screen.findByRole('link', { name: 'Import records' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Search records' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'Add record' })).not.toHaveAttribute('aria-current')
    await screen.findByText('Work codes (3)')
  })

  it('denies consumers', async () => {
    const posts = stubApi(CONSUMER)
    open()
    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument()
    expect(posts).toEqual([])
  })
})
