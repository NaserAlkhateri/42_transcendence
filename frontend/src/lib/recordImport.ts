// Bulk import of service records from a CSV or JSON file (AG-07): POST /organizations/{id}/records/import
// in backend/app/api/v1/record_transfer.py. The file goes as the raw request body. The browser only checks
// the file itself (type, size); the API checks every row with the same rules as the record form.

import { ApiError, api, errorMessage } from './api'
import type { RecordCategory } from './timeline'
import type { WorkCode } from './workCodes'

export type ImportFormat = 'csv' | 'json'
export type ImportField = 'vin' | 'service_date' | 'odometer_km' | 'category' | 'work_codes' | 'notes'

export const MAX_IMPORT_BYTES = 512 * 1024
export const MAX_IMPORT_ROWS = 500
export const REQUIRED_COLUMNS: readonly ImportField[] = ['vin', 'service_date', 'odometer_km', 'category', 'work_codes']
export const OPTIONAL_COLUMNS: readonly ImportField[] = ['notes']

export interface ImportRowError {
  /** null: the whole row (a duplicate, or a JSON item that is not an object). */
  field: ImportField | null
  code: string
  message: string
}

/** One data row. A value is null when that field has an error. */
export interface ImportRowReport {
  /** CSV: the data row number, the header not counted. JSON: the position in the list. Both start at 1. */
  row: number
  vin: string | null
  service_date: string | null
  odometer_km: number | null
  category: RecordCategory | null
  work_codes: string[]
  status: 'ok' | 'error'
  errors: ImportRowError[]
  /** The mileage flag this row would get if the file were imported now. */
  will_be_flagged: boolean
}

/** The dry run's answer, and the details of a refused import (422 import_invalid). */
export interface ImportReport {
  dry_run: boolean
  format: ImportFormat
  total_rows: number
  valid_rows: number
  invalid_rows: number
  flagged_rows: number
  warnings: string[]
  rows: ImportRowReport[]
}

export interface ImportResult {
  dry_run: false
  imported: number
  flagged: number
  record_ids: string[]
}

export const FIELD_LABELS: Record<ImportField, string> = {
  vin: 'VIN',
  service_date: 'Service date',
  odometer_km: 'Odometer',
  category: 'Category',
  work_codes: 'Work codes',
  notes: 'Notes',
}

const CONTENT_TYPES: Record<ImportFormat, string> = { csv: 'text/csv', json: 'application/json' }
const CHECK_TIMEOUT_MS = 30_000
// Every row of a real import goes through the single-record checks: 500 rows can take several seconds.
const IMPORT_TIMEOUT_MS = 120_000

/** The format a chosen file will be sent as, from its extension (a CSV's reported type varies by system). */
export function importFormatOf(file: Pick<File, 'name' | 'type'>): ImportFormat | undefined {
  const extension = /\.([^./\\]+)$/.exec(file.name)?.[1]?.toLowerCase()
  if (extension === 'csv' || extension === 'json') return extension
  if (extension) return undefined
  if (file.type === 'text/csv') return 'csv'
  if (file.type === 'application/json') return 'json'
  return undefined
}

export type FileCheck = { ok: true; format: ImportFormat } | { ok: false; error: string }

/** The checks the browser can make before sending anything. */
export function checkImportFile(file: Pick<File, 'name' | 'type' | 'size'> | undefined): FileCheck {
  if (!file) return { ok: false, error: 'Choose a CSV or JSON file.' }
  const format = importFormatOf(file)
  if (!format) return { ok: false, error: 'Choose a .csv or .json file.' }
  if (file.size === 0) return { ok: false, error: 'The file is empty. Choose a file with at least one record.' }
  if (file.size > MAX_IMPORT_BYTES) {
    return { ok: false, error: `The file is larger than 512 KB. Split it into files of at most ${MAX_IMPORT_ROWS} records.` }
  }
  return { ok: true, format }
}

function importPath(organizationId: string, dryRun: boolean): string {
  return `/organizations/${organizationId}/records/import?dry_run=${dryRun}`
}

/** Dry run: the row-by-row report. Nothing is saved. */
export function checkImport(organizationId: string, file: Blob, format: ImportFormat): Promise<ImportReport> {
  return api<ImportReport>(importPath(organizationId, true), {
    method: 'POST',
    rawBody: { data: file, contentType: CONTENT_TYPES[format] },
    timeoutMs: CHECK_TIMEOUT_MS,
  })
}

/** The real import: every row or none. A file with any row error fails with 422 import_invalid. */
export function runImport(organizationId: string, file: Blob, format: ImportFormat): Promise<ImportResult> {
  return api<ImportResult>(importPath(organizationId, false), {
    method: 'POST',
    rawBody: { data: file, contentType: CONTENT_TYPES[format] },
    timeoutMs: IMPORT_TIMEOUT_MS,
  })
}

/** The report a refused import carries in error.details, so the page can show which rows failed. */
export function rejectedImportReport(error: unknown): ImportReport | undefined {
  if (!(error instanceof ApiError) || error.code !== 'import_invalid') return undefined
  const details: unknown = error.details
  if (typeof details !== 'object' || details === null || Array.isArray(details)) return undefined
  const report = details as Partial<ImportReport>
  return Array.isArray(report.rows) && typeof report.total_rows === 'number' ? (report as ImportReport) : undefined
}

const FILE_ERROR_TITLES: Record<string, string> = {
  unsupported_media_type: 'This type of file cannot be imported',
  payload_too_large: 'The file is too large',
  invalid_encoding: 'The file is not UTF-8 text',
  empty_file: 'The file has no records',
  invalid_csv: 'The CSV file could not be read',
  invalid_json: 'The JSON file could not be read',
  missing_columns: 'Required columns are missing',
  duplicate_columns: 'A column appears more than once',
  too_many_rows: 'The file has too many records',
  organization_not_approved: 'Your organisation cannot add records yet',
}

/** Title and message for an error about the whole file or the request (not one row). */
export function describeImportError(error: unknown, fallbackTitle: string): { title: string; message: string } {
  const title = error instanceof ApiError ? FILE_ERROR_TITLES[error.code] ?? fallbackTitle : fallbackTitle
  return { title, message: errorMessage(error) }
}

export const TEMPLATE_FILENAME = 'sijil-import-template.csv'
// Fictional, but a valid VIN. The date is day first, which Excel keeps day first whatever its locale.
const EXAMPLE_ROW = { vin: 'JTEBR3FJ0PK012345', service_date: '11/04/2026', odometer_km: '45200', category: 'maintenance' }

const BOM = String.fromCharCode(0xfeff)

function csvCell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/** The CSV template: the header and one example row with real work codes. UTF-8 with a BOM, so Excel keeps
 *  Arabic notes intact. */
export function csvTemplate(codes: readonly WorkCode[]): string {
  const example = [
    EXAMPLE_ROW.vin, EXAMPLE_ROW.service_date, EXAMPLE_ROW.odometer_km, EXAMPLE_ROW.category,
    codes.slice(0, 2).map((code) => code.code).join(';'), 'Example row. Replace it with your own records.',
  ]
  const lines = [[...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS], example].map((cells) => cells.map(csvCell).join(','))
  return `${BOM}${lines.join('\r\n')}\r\n`
}
