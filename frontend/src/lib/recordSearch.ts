// Advanced record search (AG-06). The page URL uses the same query parameters as the API
// (backend/app/api/v1/record_search.py), so refresh, back/forward and shared links keep the search.
// The backend stays authoritative; these checks only save a round trip.

import { MAX_ODOMETER_KM, type OrgRecord } from './records'
import type { RecordCategory } from './timeline'
import type { FieldErrors } from './validation'
import { parseVinFragment, westernDigits } from './vin'

export type SearchScope = 'organization' | 'admin'
export type SortKey = 'service_date' | 'created_at' | 'odometer_km' | 'vin' | 'make' | 'organization_name'
export type SortOrder = 'asc' | 'desc'
export type RecordType = 'all' | 'original' | 'correction'
/** '' means either. */
export type YesNo = '' | 'true' | 'false'

/** RecordSearchItem: the record as its organization sees it, plus the vehicle. */
export interface RecordSearchItem extends OrgRecord {
  make: string | null
  model: string | null
  model_year: number | null
  /** null once the organization is deleted; organization_name keeps its name. */
  organization_id: string | null
}

export interface RecordSearchResults {
  items: RecordSearchItem[]
  /** Every match, not just this page. */
  total: number
  page: number
  page_size: number
}

/** Filter values as typed (strings), so the form and the URL share one shape. */
export interface SearchFilters {
  vin: string
  make: string
  model: string
  yearFrom: string
  yearTo: string
  category: RecordCategory | ''
  workCodes: string[]
  flagged: YesNo
  recordType: RecordType
  corrected: YesNo
  dateFrom: string
  dateTo: string
  odometerMin: string
  odometerMax: string
  staff: string
  /** Organisation name; platform admins only. */
  organization: string
}

export interface SearchState {
  filters: SearchFilters
  sort: SortKey
  order: SortOrder
  page: number
  pageSize: number
}

export type SearchField = 'vin' | 'yearFrom' | 'yearTo' | 'dateTo' | 'odometerMin' | 'odometerMax'

export const EMPTY_FILTERS: SearchFilters = {
  vin: '', make: '', model: '', yearFrom: '', yearTo: '', category: '', workCodes: [], flagged: '', recordType: 'all',
  corrected: '', dateFrom: '', dateTo: '', odometerMin: '', odometerMax: '', staff: '', organization: '',
}

export const PAGE_SIZES = [10, 20, 50, 100] as const
export const DEFAULT_PAGE_SIZE = 20
export const DEFAULT_SORT: SortKey = 'service_date'
const MAX_PAGE = 100_000
const MIN_YEAR = 1900
const MAX_YEAR = 2100

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const DIGITS = /^\d+$/

type TextKey = 'vin' | 'make' | 'model' | 'staff' | 'organization'
type NumberKey = 'yearFrom' | 'yearTo' | 'odometerMin' | 'odometerMax'
type DateKey = 'dateFrom' | 'dateTo'

const TEXT_PARAMS: Record<TextKey, string> = { vin: 'vin', make: 'make', model: 'model', staff: 'staff', organization: 'organization' }
const NUMBER_PARAMS: Record<NumberKey, string> = {
  yearFrom: 'year_from', yearTo: 'year_to', odometerMin: 'odometer_min', odometerMax: 'odometer_max',
}
const DATE_PARAMS: Record<DateKey, string> = { dateFrom: 'date_from', dateTo: 'date_to' }

/** Sort keys a scope offers: only platform admins see more than one organisation. */
export function sortKeysFor(scope: SearchScope): SortKey[] {
  const keys: SortKey[] = ['service_date', 'created_at', 'odometer_km', 'vin', 'make']
  return scope === 'admin' ? [...keys, 'organization_name'] : keys
}

function textKeys(scope: SearchScope): TextKey[] {
  return scope === 'admin' ? ['vin', 'make', 'model', 'staff', 'organization'] : ['vin', 'make', 'model', 'staff']
}

function yesNo(value: string | null): YesNo {
  return value === 'true' || value === 'false' ? value : ''
}

/** A real calendar day as YYYY-MM-DD: the only value a date input can hold (not 2026-02-31). */
function isRealDate(value: string): boolean {
  if (!ISO_DATE.test(value) || value.startsWith('0000')) return false
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
}

function pageNumber(value: string | null): number {
  const page = value && DIGITS.test(value) ? Number(value) : 1
  return page >= 1 ? Math.min(page, MAX_PAGE) : 1
}

/** Read the search from the page URL. Values the page could never have written fall back to the defaults. */
export function searchFromParams(params: URLSearchParams, scope: SearchScope): SearchState {
  const filters: SearchFilters = { ...EMPTY_FILTERS }
  for (const key of textKeys(scope)) filters[key] = params.get(TEXT_PARAMS[key]) ?? ''
  for (const key of Object.keys(NUMBER_PARAMS) as NumberKey[]) {
    const value = params.get(NUMBER_PARAMS[key]) ?? ''
    filters[key] = DIGITS.test(value) ? value : ''
  }
  for (const key of Object.keys(DATE_PARAMS) as DateKey[]) {
    const value = params.get(DATE_PARAMS[key]) ?? ''
    filters[key] = isRealDate(value) ? value : ''
  }
  const category = params.get('category')
  filters.category = category === 'maintenance' || category === 'repair' ? category : ''
  filters.workCodes = [...new Set(params.getAll('work_code').map((code) => code.trim()).filter(Boolean))]
  filters.flagged = yesNo(params.get('flagged'))
  filters.corrected = yesNo(params.get('corrected'))
  const recordType = params.get('record_type')
  filters.recordType = recordType === 'original' || recordType === 'correction' ? recordType : 'all'

  const sort = params.get('sort') as SortKey | null
  const pageSize = Number(params.get('page_size'))
  return {
    filters,
    sort: sort && sortKeysFor(scope).includes(sort) ? sort : DEFAULT_SORT,
    order: params.get('order') === 'asc' ? 'asc' : 'desc',
    page: pageNumber(params.get('page')),
    pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : DEFAULT_PAGE_SIZE,
  }
}

function filterParams(filters: SearchFilters, scope: SearchScope): URLSearchParams {
  const params = new URLSearchParams()
  const text = (key: TextKey) => {
    const value = filters[key].trim()
    if (value && textKeys(scope).includes(key)) params.set(TEXT_PARAMS[key], value)
  }
  const number = (key: NumberKey) => filters[key] && params.set(NUMBER_PARAMS[key], filters[key])
  const date = (key: DateKey) => filters[key] && params.set(DATE_PARAMS[key], filters[key])
  text('vin')
  text('make')
  text('model')
  number('yearFrom')
  number('yearTo')
  if (filters.category) params.set('category', filters.category)
  for (const code of filters.workCodes) params.append('work_code', code)
  if (filters.flagged) params.set('flagged', filters.flagged)
  if (filters.recordType !== 'all') params.set('record_type', filters.recordType)
  if (filters.corrected) params.set('corrected', filters.corrected)
  date('dateFrom')
  date('dateTo')
  number('odometerMin')
  number('odometerMax')
  text('staff')
  text('organization')
  return params
}

/** The page URL's query: only non-default values, so an unfiltered search has a clean address. */
export function searchToParams(state: SearchState, scope: SearchScope): URLSearchParams {
  const params = filterParams(state.filters, scope)
  if (state.sort !== DEFAULT_SORT) params.set('sort', state.sort)
  if (state.order !== 'desc') params.set('order', state.order)
  if (state.page > 1) params.set('page', String(state.page))
  if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set('page_size', String(state.pageSize))
  return params
}

/** The API path for a search. Sort and paging are always sent, so the result never depends on API defaults. */
export function searchApiPath(scope: SearchScope, state: SearchState, organizationId?: string): string {
  const params = filterParams(state.filters, scope)
  params.set('sort', state.sort)
  params.set('order', state.order)
  params.set('page', String(state.page))
  params.set('page_size', String(state.pageSize))
  return scope === 'admin' ? `/admin/records?${params}` : `/organizations/${organizationId}/records/search?${params}`
}

export type ExportFormat = 'csv' | 'json'

/** The API path that downloads a search (AG-07): its filters and sort, every page. `ids` narrows it to
 *  selected records; the API still applies the filters, so a selection never reaches outside the search. */
export function exportApiPath(
  scope: SearchScope, state: Pick<SearchState, 'filters' | 'sort' | 'order'>, format: ExportFormat,
  organizationId?: string, ids: readonly string[] = [],
): string {
  const params = filterParams(state.filters, scope)
  params.set('sort', state.sort)
  params.set('order', state.order)
  params.set('format', format)
  for (const id of ids) params.append('ids', id)
  return scope === 'admin' ? `/admin/records/export?${params}` : `/organizations/${organizationId}/records/export?${params}`
}

export function hasActiveFilters(filters: SearchFilters, scope: SearchScope): boolean {
  return filterParams(filters, scope).toString() !== ''
}

/** Typed values made canonical before searching: trimmed, VIN normalized, Arabic-Indic digits to 0-9. */
export function normalizeFilters(filters: SearchFilters): SearchFilters {
  const vin = parseVinFragment(filters.vin)
  const digits = (value: string) => westernDigits(value.trim())
  return {
    ...filters,
    vin: vin.ok ? vin.vin : filters.vin.trim(),
    make: filters.make.trim(),
    model: filters.model.trim(),
    staff: filters.staff.trim(),
    organization: filters.organization.trim(),
    yearFrom: digits(filters.yearFrom),
    yearTo: digits(filters.yearTo),
    odometerMin: digits(filters.odometerMin),
    odometerMax: digits(filters.odometerMax),
    workCodes: [...new Set(filters.workCodes)],
  }
}

/** Errors are keyed by the field that shows them; a reversed range is reported on its "to" field. */
export function validateFilters(filters: SearchFilters): FieldErrors<SearchField> {
  const errors: FieldErrors<SearchField> = {}
  const vin = parseVinFragment(filters.vin)
  if (!vin.ok) errors.vin = vin.error

  for (const key of ['yearFrom', 'yearTo'] as const) {
    const value = filters[key]
    if (value && (!DIGITS.test(value) || Number(value) < MIN_YEAR || Number(value) > MAX_YEAR)) {
      errors[key] = `Enter a year between ${MIN_YEAR} and ${MAX_YEAR}.`
    }
  }
  for (const key of ['odometerMin', 'odometerMax'] as const) {
    const value = filters[key]
    if (value && (!DIGITS.test(value) || Number(value) > MAX_ODOMETER_KM)) {
      errors[key] = 'Enter whole kilometres between 0 and 2,000,000.'
    }
  }

  const reversed = (from: string, to: string, numeric: boolean) =>
    !!from && !!to && (numeric ? Number(from) > Number(to) : from > to)
  if (!errors.yearFrom && !errors.yearTo && reversed(filters.yearFrom, filters.yearTo, true)) {
    errors.yearTo = "Choose a year on or after the 'from' year."
  }
  if (reversed(filters.dateFrom, filters.dateTo, false)) {
    errors.dateTo = "Choose a date on or after the 'from' date."
  }
  if (!errors.odometerMin && !errors.odometerMax && reversed(filters.odometerMin, filters.odometerMax, true)) {
    errors.odometerMax = 'Enter a maximum that is at least the minimum.'
  }
  return errors
}

// Dates and distances read best newest/highest first; names and VINs alphabetically.
const DESCENDING_FIRST: SortKey[] = ['service_date', 'created_at', 'odometer_km']

/** A click on a column heading: the sorted column flips its order, another column starts with its natural order. */
export function nextSort(current: Pick<SearchState, 'sort' | 'order'>, key: SortKey): Pick<SearchState, 'sort' | 'order'> {
  if (current.sort === key) return { sort: key, order: current.order === 'asc' ? 'desc' : 'asc' }
  return { sort: key, order: DESCENDING_FIRST.includes(key) ? 'desc' : 'asc' }
}

const count = new Intl.NumberFormat('en-GB')

/** "Showing 21–40 of 132 records". */
export function describeRange(page: number, pageSize: number, total: number, shown: number): string {
  if (total === 1) return 'Showing 1 of 1 record'
  const first = (page - 1) * pageSize + 1
  if (shown === 1) return `Showing ${count.format(first)} of ${count.format(total)} records`
  return `Showing ${count.format(first)}–${count.format(first + shown - 1)} of ${count.format(total)} records`
}
