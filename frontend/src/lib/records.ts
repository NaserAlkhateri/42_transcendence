// Records and corrections (AG-03, AG-04): who may submit, and the client-side checks that mirror
// backend/app/schemas/records.py. The backend stays authoritative.

import type { Membership, User } from '../auth/auth-context'
import { ApiError, serverFieldErrors } from './api'
import type { CorrectionReason, RecordCategory, TimelineRecord } from './timeline'
import type { FieldErrors } from './validation'
import { parseVin } from './vin'

export const MAX_ODOMETER_KM = 2_000_000

/** The fields a record and a correction share, as the API takes them. */
export interface RecordFieldsBody {
  service_date: string
  category: RecordCategory
  work_codes: string[]
  odometer_km: number
  notes: string | null
}

/** POST /organizations/{id}/records */
export interface RecordSubmission extends RecordFieldsBody {
  vin: string
}

/** POST /organizations/{id}/records/{record}/corrections */
export interface CorrectionSubmission extends RecordFieldsBody {
  correction_reason: CorrectionReason
}

/** A record as its own organization sees it (OrgRecordOut). */
export interface OrgRecord extends TimelineRecord {
  vin: string
  staff_name: string
  notes: string | null
  corrected_by_id: string | null
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

/** Form state of the shared record fields (strings as typed). */
export interface RecordFieldsForm {
  serviceDate: string
  category: string
  workCodes: string[]
  odometer: string
  notes: string
}

export interface RecordForm extends Omit<RecordFieldsForm, 'notes'> {
  vin: string
}

export function blankRecordFields(serviceDate: string): RecordFieldsForm {
  return { serviceDate, category: '', workCodes: [], odometer: '', notes: '' }
}

export function validateRecordFields(form: Omit<RecordFieldsForm, 'notes'>, today: string): FieldErrors<RecordField> {
  const errors: FieldErrors<RecordField> = {}
  if (!form.serviceDate) errors.serviceDate = 'Enter the service date.'
  else if (form.serviceDate > today) errors.serviceDate = 'The service date cannot be in the future.'
  if (!form.category) errors.category = 'Choose a category.'
  if (form.workCodes.length === 0) errors.workCodes = 'Choose at least one item of work done.'
  const odometerError = validateOdometer(form.odometer)
  if (odometerError) errors.odometer = odometerError
  return errors
}

export function validateRecordForm(form: RecordForm, today: string): { errors: FieldErrors<RecordField>; vin?: string } {
  const vin = parseVin(form.vin)
  const errors: FieldErrors<RecordField> = vin.ok ? {} : { vin: vin.error }
  Object.assign(errors, validateRecordFields(form, today))
  return vin.ok ? { errors, vin: vin.vin } : { errors }
}

/** The API body for the shared fields of an already validated form. */
export function recordFieldsBody(form: RecordFieldsForm): RecordFieldsBody {
  return {
    service_date: form.serviceDate,
    category: form.category as RecordCategory,
    work_codes: form.workCodes,
    odometer_km: Number(form.odometer.trim()),
    notes: form.notes.trim() || null,
  }
}

/** A record's values as form state, to prefill a correction. */
export function recordToFields(record: TimelineRecord): RecordFieldsForm {
  return {
    serviceDate: record.service_date, category: record.category, workCodes: [...record.work_codes],
    odometer: String(record.odometer_km), notes: '',
  }
}

const SERVER_FIELDS: Record<string, RecordField | 'notes'> = {
  vin: 'vin', service_date: 'serviceDate', category: 'category', work_codes: 'workCodes', odometer_km: 'odometer', notes: 'notes',
}

/** Map a failed submission's 422 details (and invalid_vin) onto the form's fields. */
export function recordFieldErrors(failure: unknown): FieldErrors<RecordField | 'notes'> {
  const errors = serverFieldErrors(failure, SERVER_FIELDS)
  for (const key of Object.keys(errors) as (keyof typeof errors)[]) errors[key] = errors[key]?.replace(/^Value error, /, '')
  if (failure instanceof ApiError && failure.code === 'invalid_vin') errors.vin = failure.message
  return errors
}

function validateOdometer(value: string): string | undefined {
  const text = value.trim()
  if (!text) return 'Enter the odometer reading in km.'
  if (!/^\d+$/.test(text) || Number(text) > MAX_ODOMETER_KM) return 'Enter whole kilometres between 0 and 2,000,000.'
  return undefined
}
