// Record submission (AG-03): who may submit and the client-side checks that mirror backend/app/schemas/records.py.

import type { Membership, User } from '../auth/auth-context'
import type { RecordCategory, TimelineRecord } from './timeline'
import type { FieldErrors } from './validation'
import { parseVin } from './vin'

export const MAX_ODOMETER_KM = 2_000_000

/** POST /organizations/{id}/records body. */
export interface RecordSubmission {
  vin: string
  service_date: string
  category: RecordCategory
  work_codes: string[]
  odometer_km: number
  notes: string | null
}

/** A record as its own organization sees it (OrgRecordOut). */
export interface OrgRecord extends TimelineRecord {
  vin: string
  staff_name: string
  notes: string | null
}

/** Organizations the user can add records for: active admin/staff membership of an approved organization. */
export function submittingOrganizations(user: User): Membership[] {
  return user.memberships.filter((m) => m.status === 'active' && m.organization_status === 'approved')
}

/** Today's date in the UAE (UTC+4, no daylight saving) as YYYY-MM-DD. */
export function uaeToday(now = Date.now()): string {
  return new Date(now + 4 * 60 * 60 * 1000).toISOString().slice(0, 10)
}

export type RecordField = 'vin' | 'serviceDate' | 'category' | 'workCodes' | 'odometer'

export interface RecordForm {
  vin: string
  serviceDate: string
  category: string
  workCodes: string[]
  odometer: string
}

export function validateRecordForm(form: RecordForm, today: string): { errors: FieldErrors<RecordField>; vin?: string } {
  const errors: FieldErrors<RecordField> = {}
  const vin = parseVin(form.vin)
  if (!vin.ok) errors.vin = vin.error
  if (!form.serviceDate) errors.serviceDate = 'Enter the service date.'
  else if (form.serviceDate > today) errors.serviceDate = 'The service date cannot be in the future.'
  if (!form.category) errors.category = 'Choose a category.'
  if (form.workCodes.length === 0) errors.workCodes = 'Choose at least one item of work done.'
  const odometerError = validateOdometer(form.odometer)
  if (odometerError) errors.odometer = odometerError
  return vin.ok ? { errors, vin: vin.vin } : { errors }
}

function validateOdometer(value: string): string | undefined {
  const text = value.trim()
  if (!text) return 'Enter the odometer reading in km.'
  if (!/^\d+$/.test(text) || Number(text) > MAX_ODOMETER_KM) return 'Enter whole kilometres between 0 and 2,000,000.'
  return undefined
}
