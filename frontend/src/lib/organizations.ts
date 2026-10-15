// Organisation types, labels and client-side checks. They mirror backend/app/schemas/organizations.py;
// the backend stays authoritative. UI copy uses UK spelling (organisation, licence) per doc/UAE_MARKET.md.

import type { BadgeVariant } from '../components/ui'
import type { MemberRole } from '../auth/auth-context'
import type { FieldErrors } from './validation'

export type OrganizationKind = 'workshop' | 'dealership'
export type OrganizationStatus = 'pending' | 'approved' | 'rejected'

export const EMIRATES = [
  'Abu Dhabi', 'Dubai', 'Sharjah', 'Ajman', 'Umm Al Quwain', 'Ras Al Khaimah', 'Fujairah',
] as const
export type Emirate = (typeof EMIRATES)[number]

export const KIND_LABELS: Record<OrganizationKind, string> = { workshop: 'Workshop', dealership: 'Dealership' }

export const STATUS_LABELS: Record<OrganizationStatus, string> = {
  pending: 'Awaiting review',
  approved: 'Approved',
  rejected: 'Rejected',
}

export const STATUS_BADGE: Record<OrganizationStatus, BadgeVariant> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}

export interface Organization {
  id: string
  name: string
  kind: OrganizationKind
  registration_number: string
  emirate: Emirate | null
  status: OrganizationStatus
  rejection_reason: string | null
  approved_at: string | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
}

export interface OrganizationMember {
  membership_id: string
  user_id: string
  full_name: string
  email: string
  role: MemberRole
  status: 'active' | 'inactive'
}

export interface AdminOrganization extends Organization {
  member_count: number
  record_count: number
}

export interface AdminOrganizationDetail extends AdminOrganization {
  members: OrganizationMember[]
}

export interface OrganizationPage {
  items: AdminOrganization[]
  total: number
  page: number
  page_size: number
}

export interface OrganizationForm {
  name: string
  kind: OrganizationKind | ''
  registrationNumber: string
  emirate: Emirate | ''
}

export type OrganizationField = keyof OrganizationForm

export const EMPTY_ORGANIZATION_FORM: OrganizationForm = { name: '', kind: '', registrationNumber: '', emirate: '' }

/** Backend field names → form fields, for serverFieldErrors(). */
export const ORGANIZATION_SERVER_FIELDS: Record<string, OrganizationField> = {
  name: 'name',
  kind: 'kind',
  registration_number: 'registrationNumber',
  emirate: 'emirate',
}

const LICENCE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9/\- ]*$/
export const REASON_MIN_LENGTH = 5
export const REASON_MAX_LENGTH = 500

export function validateOrganization(form: OrganizationForm): FieldErrors<OrganizationField> {
  const errors: FieldErrors<OrganizationField> = {}
  const name = form.name.trim()
  const licence = form.registrationNumber.trim()
  if (name.length < 2) errors.name = 'Enter the business name.'
  else if (name.length > 200) errors.name = 'Use at most 200 characters.'
  if (!form.kind) errors.kind = 'Choose workshop or dealership.'
  if (licence.length < 3) errors.registrationNumber = 'Enter the trade licence number.'
  else if (licence.length > 64) errors.registrationNumber = 'Use at most 64 characters.'
  else if (!LICENCE_PATTERN.test(licence)) errors.registrationNumber = 'Use letters, digits, spaces, "-" or "/".'
  if (!form.emirate) errors.emirate = 'Choose the emirate.'
  return errors
}

export function validateRejectionReason(reason: string): string | undefined {
  const value = reason.trim()
  if (value.length < REASON_MIN_LENGTH) return 'Tell the business what to fix (at least 5 characters).'
  if (value.length > REASON_MAX_LENGTH) return `Use at most ${REASON_MAX_LENGTH} characters.`
  return undefined
}

/** Request body for register/create, or only the changed fields for an edit. */
export function organizationPayload(form: OrganizationForm, original?: Organization): Record<string, string> {
  const values: Record<string, string> = {
    name: form.name.trim(),
    kind: form.kind,
    registration_number: form.registrationNumber.trim().toUpperCase(),
    emirate: form.emirate,
  }
  if (!original) return values
  return Object.fromEntries(
    Object.entries(values).filter(([key, value]) => value !== (original[key as keyof Organization] ?? '')),
  )
}

export function formFromOrganization(organization: Organization): OrganizationForm {
  return {
    name: organization.name,
    kind: organization.kind,
    registrationNumber: organization.registration_number,
    emirate: organization.emirate ?? '',
  }
}

/** "11 Apr 2026": day before month, as the UAE market guide asks. */
export function formatDay(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
