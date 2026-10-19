import { describe, expect, it } from 'vitest'

import {
  EMPTY_FILTERS,
  describeRange,
  hasActiveFilters,
  nextSort,
  normalizeFilters,
  searchApiPath,
  searchFromParams,
  searchToParams,
  validateFilters,
  type SearchFilters,
  type SearchState,
} from './recordSearch'

const DEFAULTS: SearchState = { filters: EMPTY_FILTERS, sort: 'service_date', order: 'desc', page: 1, pageSize: 20 }

function filters(overrides: Partial<SearchFilters>): SearchFilters {
  return { ...EMPTY_FILTERS, ...overrides }
}

const FULL = filters({
  vin: 'JTN', make: 'Toyota', model: 'Land Cruiser', yearFrom: '2018', yearTo: '2022', category: 'repair',
  workCodes: ['AC_SERVICE', 'OIL_CHANGE'], flagged: 'true', recordType: 'correction', corrected: 'false',
  dateFrom: '2026-01-01', dateTo: '2026-04-11', odometerMin: '50000', odometerMax: '120000', staff: 'Arjun',
  organization: 'Falcon',
})

describe('searchFromParams / searchToParams', () => {
  it('reads defaults from an empty address and writes nothing back', () => {
    const state = searchFromParams(new URLSearchParams(), 'admin')
    expect(state).toEqual(DEFAULTS)
    expect(searchToParams(state, 'admin').toString()).toBe('')
  })

  it('round-trips every filter, the sort and the page through the address', () => {
    const state: SearchState = { filters: FULL, sort: 'organization_name', order: 'asc', page: 3, pageSize: 50 }
    const query = searchToParams(state, 'admin').toString()
    expect(query).toBe(
      'vin=JTN&make=Toyota&model=Land+Cruiser&year_from=2018&year_to=2022&category=repair&work_code=AC_SERVICE' +
        '&work_code=OIL_CHANGE&flagged=true&record_type=correction&corrected=false&date_from=2026-01-01' +
        '&date_to=2026-04-11&odometer_min=50000&odometer_max=120000&staff=Arjun&organization=Falcon' +
        '&sort=organization_name&order=asc&page=3&page_size=50',
    )
    expect(searchFromParams(new URLSearchParams(query), 'admin')).toEqual(state)
  })

  it('leaves the organisation filter and sort to platform admins', () => {
    const params = new URLSearchParams('organization=Falcon&sort=organization_name&make=Nissan')
    const state = searchFromParams(params, 'organization')
    expect(state.filters.organization).toBe('')
    expect(state.sort).toBe('service_date')
    expect(searchToParams({ ...state, filters: FULL }, 'organization').get('organization')).toBeNull()
  })

  it('ignores values the page could never have written', () => {
    const params = new URLSearchParams(
      'category=tyres&flagged=yes&corrected=1&record_type=other&sort=price&order=up&page=-2&page_size=37' +
        '&year_from=20x&odometer_min=1.5&date_from=11/04/2026',
    )
    expect(searchFromParams(params, 'admin')).toEqual(DEFAULTS)
  })

  it('caps the page at the API limit and drops repeated work codes', () => {
    const state = searchFromParams(new URLSearchParams('page=999999&work_code=OIL_CHANGE&work_code=OIL_CHANGE'), 'admin')
    expect(state.page).toBe(100_000)
    expect(state.filters.workCodes).toEqual(['OIL_CHANGE'])
  })
})

describe('searchApiPath', () => {
  it('always sends sort and paging, and scopes the path to the organisation', () => {
    expect(searchApiPath('organization', DEFAULTS, 'org-falcon')).toBe(
      '/organizations/org-falcon/records/search?sort=service_date&order=desc&page=1&page_size=20',
    )
    const state: SearchState = { ...DEFAULTS, filters: filters({ make: 'Nissan', organization: 'Oasis' }), page: 2 }
    expect(searchApiPath('organization', state, 'org-falcon')).toBe(
      '/organizations/org-falcon/records/search?make=Nissan&sort=service_date&order=desc&page=2&page_size=20',
    )
    expect(searchApiPath('admin', state)).toBe(
      '/admin/records?make=Nissan&organization=Oasis&sort=service_date&order=desc&page=2&page_size=20',
    )
  })
})

describe('hasActiveFilters', () => {
  it('is false for blank text and the default record type', () => {
    expect(hasActiveFilters(filters({ make: '   ' }), 'admin')).toBe(false)
    expect(hasActiveFilters(filters({ recordType: 'original' }), 'admin')).toBe(true)
    expect(hasActiveFilters(filters({ organization: 'Falcon' }), 'organization')).toBe(false)
  })
})

describe('normalizeFilters', () => {
  it('trims text, normalizes the VIN and maps Arabic-Indic digits', () => {
    const typed = filters({
      vin: ' jtn-bk3 ', make: ' Toyota ', yearFrom: '٢٠١٨', odometerMax: ' ۸۸۳۰۰ ', workCodes: ['OIL_CHANGE', 'OIL_CHANGE'],
    })
    expect(normalizeFilters(typed)).toEqual(
      filters({ vin: 'JTNBK3', make: 'Toyota', yearFrom: '2018', odometerMax: '88300', workCodes: ['OIL_CHANGE'] }),
    )
  })

  it('keeps an invalid VIN as typed so validation can report it', () => {
    expect(normalizeFilters(filters({ vin: ' JTO ' })).vin).toBe('JTO')
  })
})

describe('validateFilters', () => {
  it('accepts an empty search and complete, ordered ranges', () => {
    expect(validateFilters(EMPTY_FILTERS)).toEqual({})
    expect(validateFilters(FULL)).toEqual({})
    expect(validateFilters(filters({ dateFrom: '2026-04-11', dateTo: '2026-04-11', odometerMin: '0', odometerMax: '0' }))).toEqual({})
  })

  it('reports reversed ranges on the "to" field', () => {
    expect(validateFilters(filters({ yearFrom: '2022', yearTo: '2018' }))).toEqual({
      yearTo: "Choose a year on or after the 'from' year.",
    })
    expect(validateFilters(filters({ dateFrom: '2026-05-01', dateTo: '2026-04-11' }))).toEqual({
      dateTo: "Choose a date on or after the 'from' date.",
    })
    // Compared as numbers, not text ("9000" > "12000" as text).
    expect(validateFilters(filters({ odometerMin: '9000', odometerMax: '12000' }))).toEqual({})
    expect(validateFilters(filters({ odometerMin: '120000', odometerMax: '50000' }))).toEqual({
      odometerMax: 'Enter a maximum that is at least the minimum.',
    })
  })

  it('rejects VIN characters that are never in a VIN', () => {
    expect(validateFilters(filters({ vin: 'JTO' })).vin).toMatch(/never contains I, O or Q/)
    expect(validateFilters(filters({ vin: 'JTN%' })).vin).toMatch(/never contains I, O or Q/)
  })

  it('rejects years and distances outside what the API accepts', () => {
    expect(validateFilters(filters({ yearFrom: '1899', yearTo: 'abcd' }))).toEqual({
      yearFrom: 'Enter a year between 1900 and 2100.',
      yearTo: 'Enter a year between 1900 and 2100.',
    })
    expect(validateFilters(filters({ odometerMin: '-5', odometerMax: '2000001' }))).toEqual({
      odometerMin: 'Enter whole kilometres between 0 and 2,000,000.',
      odometerMax: 'Enter whole kilometres between 0 and 2,000,000.',
    })
  })
})

describe('nextSort', () => {
  it('flips the order of the sorted column', () => {
    expect(nextSort({ sort: 'service_date', order: 'desc' }, 'service_date')).toEqual({ sort: 'service_date', order: 'asc' })
    expect(nextSort({ sort: 'service_date', order: 'asc' }, 'service_date')).toEqual({ sort: 'service_date', order: 'desc' })
  })

  it('starts dates and distances newest/highest first, names and VINs A to Z', () => {
    const from = { sort: 'vin', order: 'asc' } as const
    expect(nextSort(from, 'odometer_km')).toEqual({ sort: 'odometer_km', order: 'desc' })
    expect(nextSort(from, 'created_at')).toEqual({ sort: 'created_at', order: 'desc' })
    expect(nextSort({ sort: 'service_date', order: 'desc' }, 'make')).toEqual({ sort: 'make', order: 'asc' })
    expect(nextSort({ sort: 'service_date', order: 'desc' }, 'organization_name')).toEqual({ sort: 'organization_name', order: 'asc' })
  })
})

describe('describeRange', () => {
  it('counts the rows on this page out of every match', () => {
    expect(describeRange(2, 20, 132, 20)).toBe('Showing 21–40 of 132 records')
    expect(describeRange(7, 20, 132, 12)).toBe('Showing 121–132 of 132 records')
    expect(describeRange(1, 100, 1320, 100)).toBe('Showing 1–100 of 1,320 records')
    expect(describeRange(1, 20, 1, 1)).toBe('Showing 1 of 1 record')
  })
})
