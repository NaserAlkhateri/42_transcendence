import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './api'
import {
  MAX_IMPORT_BYTES,
  checkImport,
  checkImportFile,
  csvTemplate,
  describeImportError,
  importFormatOf,
  rejectedImportReport,
  runImport,
  type ImportReport,
} from './recordImport'

const file = (name: string, size = 100, type = '') => ({ name, size, type })

describe('importFormatOf', () => {
  it('goes by the extension, whatever type the system reports', () => {
    expect(importFormatOf(file('falcon-records.CSV', 1, 'application/vnd.ms-excel'))).toBe('csv')
    expect(importFormatOf(file('sijil-records-20261020-0815.json'))).toBe('json')
    expect(importFormatOf(file('records.xlsx', 1, 'text/csv'))).toBeUndefined()
    expect(importFormatOf(file('records.csv.txt', 1, 'text/plain'))).toBeUndefined()
  })

  it('uses the reported type only when the name has no extension', () => {
    expect(importFormatOf(file('records', 1, 'text/csv'))).toBe('csv')
    expect(importFormatOf(file('records', 1, 'application/json'))).toBe('json')
    expect(importFormatOf(file('records', 1, 'text/plain'))).toBeUndefined()
  })
})

describe('checkImportFile', () => {
  it('accepts a CSV or JSON file up to 512 KB', () => {
    expect(checkImportFile(file('a.csv', MAX_IMPORT_BYTES))).toEqual({ ok: true, format: 'csv' })
    expect(checkImportFile(file('a.json', 1))).toEqual({ ok: true, format: 'json' })
  })

  it('explains what is wrong before anything is sent', () => {
    expect(checkImportFile(undefined)).toEqual({ ok: false, error: 'Choose a CSV or JSON file.' })
    expect(checkImportFile(file('photo.png'))).toEqual({ ok: false, error: 'Choose a .csv or .json file.' })
    expect(checkImportFile(file('a.csv', 0))).toEqual({ ok: false, error: expect.stringMatching(/^The file is empty/) })
    expect(checkImportFile(file('a.csv', MAX_IMPORT_BYTES + 1)))
      .toEqual({ ok: false, error: expect.stringMatching(/^The file is larger than 512 KB/) })
  })
})

describe('csvTemplate', () => {
  it('has the BOM, the columns and one example row with known work codes', () => {
    const codes = [
      { code: 'OIL_CHANGE', label: 'Oil change', label_ar: 'تغيير الزيت' },
      { code: 'AIR_FILTER', label: 'Air filter', label_ar: 'فلتر الهواء' },
      { code: 'AC_SERVICE', label: 'A/C service', label_ar: 'صيانة المكيف' },
    ]
    expect(csvTemplate(codes)).toBe(
      `${String.fromCharCode(0xfeff)}vin,service_date,odometer_km,category,work_codes,notes\r\n` +
      'JTEBR3FJ0PK012345,11/04/2026,45200,maintenance,OIL_CHANGE;AIR_FILTER,Example row. Replace it with your own records.\r\n',
    )
  })
})

const REPORT: ImportReport = {
  dry_run: false, format: 'csv', total_rows: 1, valid_rows: 0, invalid_rows: 1, flagged_rows: 0, warnings: [],
  rows: [{
    row: 1, vin: null, service_date: '2026-04-11', odometer_km: 45200, category: 'maintenance', work_codes: ['OIL_CHANGE'],
    status: 'error', errors: [{ field: 'vin', code: 'invalid_vin', message: 'A VIN has exactly 17 letters or digits.' }],
    will_be_flagged: false,
  }],
}

describe('rejectedImportReport', () => {
  it('reads the report out of a refused import', () => {
    const error = new ApiError(422, 'import_invalid', '1 of 1 rows have errors. Nothing was imported.', REPORT as never)
    expect(rejectedImportReport(error)).toEqual(REPORT)
  })

  it('ignores other errors and malformed details', () => {
    expect(rejectedImportReport(new ApiError(422, 'missing_columns', 'Missing required columns: vin.'))).toBeUndefined()
    expect(rejectedImportReport(new ApiError(422, 'import_invalid', 'x', []))).toBeUndefined()
    expect(rejectedImportReport(new Error('x'))).toBeUndefined()
  })
})

describe('describeImportError', () => {
  it('titles file errors and keeps the API’s message', () => {
    expect(describeImportError(new ApiError(422, 'missing_columns', 'Missing required columns: vin.'), 'Fallback'))
      .toEqual({ title: 'Required columns are missing', message: 'Missing required columns: vin.' })
    expect(describeImportError(new ApiError(413, 'payload_too_large', 'The file is larger than 512 KB.'), 'Fallback').title)
      .toBe('The file is too large')
    expect(describeImportError(new ApiError(500, 'http_error', 'Something went wrong.'), 'The file could not be checked'))
      .toEqual({ title: 'The file could not be checked', message: 'Something went wrong.' })
  })
})

describe('checkImport / runImport', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubFetch(body: unknown, status = 200) {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: 'tok' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('posts the file itself as the body, typed by its format, with the CSRF header', async () => {
    const fetchMock = stubFetch(REPORT)
    const csv = new Blob(['vin,service_date,odometer_km,category,work_codes\r\n'])
    await expect(checkImport('org-falcon', csv, 'csv')).resolves.toEqual(REPORT)
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/v1/organizations/org-falcon/records/import?dry_run=true')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(csv)
    expect(init?.headers).toMatchObject({ 'Content-Type': 'text/csv', 'X-CSRF-Token': 'tok' })
  })

  it('imports for real with dry_run=false', async () => {
    const fetchMock = stubFetch({ dry_run: false, imported: 1, flagged: 0, record_ids: ['rec-1'] }, 201)
    const json = new Blob(['[]'])
    await expect(runImport('org-falcon', json, 'json')).resolves.toMatchObject({ imported: 1 })
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/v1/organizations/org-falcon/records/import?dry_run=false')
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/json' })
  })
})
