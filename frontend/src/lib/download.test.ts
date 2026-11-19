// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './api'
import { downloadFile, filenameFromDisposition } from './download'

describe('filenameFromDisposition', () => {
  it('reads quoted, unquoted and UTF-8 encoded names', () => {
    expect(filenameFromDisposition('attachment; filename="sijil-records-20261020-0815.csv"', 'x.csv'))
      .toBe('sijil-records-20261020-0815.csv')
    expect(filenameFromDisposition('attachment; filename=sijil-records.json', 'x.json')).toBe('sijil-records.json')
    expect(filenameFromDisposition("attachment; filename=\"plain.csv\"; filename*=UTF-8''sijil%20records.csv", 'x.csv'))
      .toBe('sijil records.csv')
  })

  it('falls back when the header is missing or names no usable file', () => {
    expect(filenameFromDisposition(null, 'sijil-records.csv')).toBe('sijil-records.csv')
    expect(filenameFromDisposition('attachment', 'sijil-records.csv')).toBe('sijil-records.csv')
    expect(filenameFromDisposition('attachment; filename=""', 'sijil-records.csv')).toBe('sijil-records.csv')
  })

  it('keeps only the base name', () => {
    expect(filenameFromDisposition('attachment; filename="../../etc/passwd"', 'x.csv')).toBe('passwd')
    expect(filenameFromDisposition('attachment; filename="C:\\Users\\a\\.hidden.csv"', 'x.csv')).toBe('hidden.csv')
  })
})

describe('downloadFile', () => {
  const fetchMock = vi.fn<typeof fetch>()
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:http://localhost/export-1')
  const revokeObjectURL = vi.fn()
  let clicked: HTMLAnchorElement[] = []

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    // jsdom has no object URLs and cannot follow a download link.
    Object.assign(URL, { createObjectURL, revokeObjectURL })
    clicked = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this)
      expect(document.body.contains(this)).toBe(true)
    })
  })

  afterEach(() => {
    fetchMock.mockReset()
    createObjectURL.mockClear()
    revokeObjectURL.mockClear()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('fetches with the session cookie and saves the body under the server’s file name', async () => {
    fetchMock.mockResolvedValueOnce(new Response('\uFEFFrecord_id,vin\r\n', {
      status: 200,
      headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="sijil-records-20261020-0815.csv"' },
    }))

    await expect(downloadFile('/admin/records/export?format=csv', { fallbackName: 'sijil-records.csv' }))
      .resolves.toBe('sijil-records-20261020-0815.csv')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/admin/records/export?format=csv')
    expect(init?.credentials).toBe('same-origin')
    expect(init?.method).toBe('GET')
    const blob = createObjectURL.mock.calls[0][0]
    expect(blob.size).toBeGreaterThan(0)
    expect(clicked).toHaveLength(1)
    expect(clicked[0].href).toBe('blob:http://localhost/export-1')
    expect(clicked[0].download).toBe('sijil-records-20261020-0815.csv')
    expect(document.querySelector('a[download]')).toBeNull() // the temporary link is gone
    await vi.waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith('blob:http://localhost/export-1'))
  })

  it('uses the fallback name when the response names no file', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await expect(downloadFile('/x', { fallbackName: 'sijil-records.json' })).resolves.toBe('sijil-records.json')
    expect(clicked[0].download).toBe('sijil-records.json')
  })

  it('throws the API’s error and saves nothing', async () => {
    fetchMock.mockResolvedValueOnce(new Response(
      JSON.stringify({ error: { code: 'export_too_large', message: 'More than 5,000 records match. Narrow the filters and export again.' } }),
      { status: 422, headers: { 'Content-Type': 'application/json' } },
    ))
    const error = (await downloadFile('/x', { fallbackName: 'a.csv' }).catch((e: unknown) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('export_too_large')
    expect(error.message).toMatch(/Narrow the filters/)
    expect(createObjectURL).not.toHaveBeenCalled()
    expect(clicked).toHaveLength(0)
  })
})
