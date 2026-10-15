import { describe, expect, it } from 'vitest'

import {
  formatDay,
  organizationPayload,
  validateOrganization,
  validateRejectionReason,
  type Organization,
} from './organizations'

const valid = { name: 'Corniche Tyre Centre', kind: 'workshop', registrationNumber: 'dxb-778899', emirate: 'Dubai' } as const

const existing: Organization = {
  id: '1', name: 'Corniche Tyre Centre', kind: 'workshop', registration_number: 'DXB-778899', emirate: 'Dubai',
  status: 'approved', rejection_reason: null, approved_at: null, reviewed_at: null,
  created_at: '2026-04-11T08:00:00Z', updated_at: '2026-04-11T08:00:00Z',
}

describe('validateOrganization', () => {
  it('accepts a complete registration', () => {
    expect(validateOrganization(valid)).toEqual({})
  })

  it('flags every missing field', () => {
    const errors = validateOrganization({ name: ' ', kind: '', registrationNumber: '', emirate: '' })
    expect(Object.keys(errors).sort()).toEqual(['emirate', 'kind', 'name', 'registrationNumber'])
  })

  it('rejects licence numbers the backend would refuse', () => {
    expect(validateOrganization({ ...valid, registrationNumber: '%%%' }).registrationNumber).toBeDefined()
    expect(validateOrganization({ ...valid, registrationNumber: 'x'.repeat(65) }).registrationNumber).toBeDefined()
    expect(validateOrganization({ ...valid, registrationNumber: 'CN-123/45 A' }).registrationNumber).toBeUndefined()
  })
})

describe('validateRejectionReason', () => {
  it('needs a real explanation', () => {
    expect(validateRejectionReason('no')).toBeDefined()
    expect(validateRejectionReason('Licence has expired.')).toBeUndefined()
    expect(validateRejectionReason('x'.repeat(501))).toBeDefined()
  })
})

describe('organizationPayload', () => {
  it('sends every field for a new organisation, licence upper-cased', () => {
    expect(organizationPayload(valid)).toEqual({
      name: 'Corniche Tyre Centre', kind: 'workshop', registration_number: 'DXB-778899', emirate: 'Dubai',
    })
  })

  it('sends only what changed for an edit', () => {
    expect(organizationPayload({ ...valid, emirate: 'Sharjah' }, existing)).toEqual({ emirate: 'Sharjah' })
    expect(organizationPayload(valid, existing)).toEqual({})
  })
})

describe('formatDay', () => {
  it('puts the day before the month', () => {
    expect(formatDay('2026-04-11T08:00:00Z')).toBe('11 Apr 2026')
    expect(formatDay(null)).toBe('—')
  })
})
