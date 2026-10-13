// Types and helpers for GET /api/v1/vehicles/{vin}/timeline (backend/app/api/v1/vehicles.py).

export type RecordCategory = 'maintenance' | 'repair'
export type TimelineOrder = 'asc' | 'desc'

export interface VehicleSummary {
  vin: string
  make: string | null
  model: string | null
  model_year: number | null
}

export interface TimelineRecord {
  id: string
  service_date: string
  created_at: string
  category: RecordCategory
  work_codes: string[]
  odometer_km: number
  organization_name: string
  is_mileage_flagged: boolean
  corrects_record_id: string | null
}

export interface VehicleTimeline {
  vin: string
  /** null: a valid VIN nobody has recorded yet (the page offers "Watch"). */
  vehicle: VehicleSummary | null
  records: TimelineRecord[]
}

export const CATEGORY_LABELS: Record<RecordCategory, string> = { maintenance: 'Maintenance', repair: 'Repair' }

/** The page URL and the API share these query parameters, so a filtered timeline can be bookmarked or shared. */
export interface TimelineFilters {
  category: RecordCategory | ''
  flaggedOnly: boolean
  from: string
  to: string
  order: TimelineOrder
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export function filtersFromParams(params: URLSearchParams): TimelineFilters {
  const category = params.get('category')
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  return {
    category: category === 'maintenance' || category === 'repair' ? category : '',
    flaggedOnly: params.get('flagged') === 'true',
    from: ISO_DATE.test(from) ? from : '',
    to: ISO_DATE.test(to) ? to : '',
    order: params.get('order') === 'asc' ? 'asc' : 'desc',
  }
}

/** Only non-default values, so the unfiltered timeline has a clean URL. */
export function filtersToParams(filters: TimelineFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.category) params.set('category', filters.category)
  if (filters.flaggedOnly) params.set('flagged', 'true')
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  if (filters.order === 'asc') params.set('order', 'asc')
  return params
}

export function describeVehicle(vehicle: VehicleSummary | null): string | undefined {
  if (!vehicle) return undefined
  return [vehicle.model_year, vehicle.make, vehicle.model].filter(Boolean).join(' ') || undefined
}

/** Service dates are calendar dates (YYYY-MM-DD): format in UTC so no time zone shifts them by a day. */
export function formatServiceDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

export function formatOdometer(km: number): string {
  return `${new Intl.NumberFormat('en-GB').format(km)} km`
}
