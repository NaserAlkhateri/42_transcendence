import { describe, expect, it } from 'vitest'

import type { Membership, User } from '../auth/auth-context'
import { submittingOrganizations, validateRecordForm } from './records'

function membership(overrides: Partial<Membership>): Membership {
  return {
    id: 'm', organization_id: 'org', organization_name: 'Falcon Bay Auto Care', organization_status: 'approved',
    role: 'entity_staff', status: 'active', ...overrides,
  }
}

function staffUser(memberships: Membership[]): User {
  return {
    id: 'u', email: 'arjun@example.ae', full_name: 'Arjun Nair', role: 'consumer', effective_role: 'entity_staff',
    must_change_password: false, created_at: '2026-10-12T00:00:00Z', memberships,
  }
}

describe('submittingOrganizations', () => {
  it('keeps active memberships of approved organizations only', () => {
    const user = staffUser([
      membership({ organization_id: 'ok-staff' }),
      membership({ organization_id: 'ok-admin', role: 'entity_admin' }),
      membership({ organization_id: 'pending', organization_status: 'pending' }),
      membership({ organization_id: 'rejected', organization_status: 'rejected' }),
      membership({ organization_id: 'left', status: 'inactive' }),
    ])
    expect(submittingOrganizations(user).map((m) => m.organization_id)).toEqual(['ok-staff', 'ok-admin'])
  })
})

describe('validateRecordForm', () => {
  const valid = { vin: 'jn8ay2ny4k9-012345', serviceDate: '2026-03-01', category: 'maintenance', workCodes: ['OIL_CHANGE'], odometer: '30000' }
  const today = '2026-10-13'

  it('accepts a complete form and returns the canonical VIN', () => {
    expect(validateRecordForm(valid, today)).toEqual({ errors: {}, vin: 'JN8AY2NY4K9012345' })
  })

  it.each([
    [{ vin: 'ABC' }, 'vin'],
    [{ serviceDate: '' }, 'serviceDate'],
    [{ serviceDate: '2026-10-14' }, 'serviceDate'],
    [{ category: '' }, 'category'],
    [{ workCodes: [] }, 'workCodes'],
    [{ odometer: '' }, 'odometer'],
    [{ odometer: '12.5' }, 'odometer'],
    [{ odometer: '-1' }, 'odometer'],
    [{ odometer: '2000001' }, 'odometer'],
  ])('reports %j on the %s field', (override, field) => {
    expect(Object.keys(validateRecordForm({ ...valid, ...override }, today).errors)).toEqual([field])
  })
})
