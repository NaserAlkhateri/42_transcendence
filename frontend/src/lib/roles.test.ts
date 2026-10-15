import { describe, expect, it } from 'vitest'

import type { EffectiveRole, User } from '../auth/auth-context'
import { hasRole, navItemsFor } from './roles'

function user(effective_role: EffectiveRole, must_change_password = false): User {
  return {
    id: '1',
    email: 'a@example.ae',
    full_name: 'A',
    role: effective_role === 'platform_admin' ? 'platform_admin' : 'consumer',
    effective_role,
    must_change_password,
    created_at: '2026-10-12T00:00:00Z',
    memberships: [],
  }
}

describe('hasRole', () => {
  it('matches the effective role', () => {
    expect(hasRole(user('platform_admin'), ['platform_admin'])).toBe(true)
    expect(hasRole(user('entity_admin'), ['platform_admin'])).toBe(false)
    expect(hasRole(null, ['consumer'])).toBe(false)
  })

  it('denies everything while a temporary password is pending', () => {
    expect(hasRole(user('platform_admin', true), ['platform_admin'])).toBe(false)
  })
})

describe('navItemsFor', () => {
  it('shows the Users link only to platform admins', () => {
    const labels = (role: EffectiveRole) => navItemsFor(user(role)).map((item) => item.label)
    expect(labels('platform_admin')).toContain('Users')
    for (const role of ['entity_admin', 'entity_staff', 'consumer'] as const) {
      expect(labels(role)).not.toContain('Users')
    }
    expect(navItemsFor(null)).toEqual([])
  })
})

describe('record tools in the navigation', () => {
  it('are offered to entity admins and staff only', () => {
    const labels = (role: EffectiveRole) => navItemsFor(user(role)).map((item) => item.label)
    for (const role of ['entity_admin', 'entity_staff'] as const) {
      expect(labels(role)).toContain('Add record')
      expect(labels(role)).toContain('Correct a record')
    }
    for (const role of ['consumer', 'platform_admin'] as const) {
      expect(labels(role)).not.toContain('Add record')
      expect(labels(role)).not.toContain('Correct a record')
    }
  })
})

describe('organisation links in the navigation', () => {
  const labels = (u: User) => navItemsFor(u).map((item) => item.label)
  const member = (organization_status: 'pending' | 'approved' | 'rejected'): User => ({
    ...user(organization_status === 'approved' ? 'entity_admin' : 'consumer'),
    memberships: [{
      id: 'm1', organization_id: 'org-1', organization_name: 'Corniche Tyre Centre', organization_status,
      role: 'entity_admin', status: 'active',
    }],
  })

  it('invites consumers without a membership to register a business', () => {
    expect(labels(user('consumer'))).toContain('Register a business')
    expect(labels(user('consumer'))).not.toContain('Organisation')
  })

  it('links members to their organisation, even while it is pending', () => {
    for (const status of ['pending', 'approved', 'rejected'] as const) {
      const items = navItemsFor(member(status))
      expect(items).toContainEqual({ to: '/organizations/org-1', label: 'Organisation' })
      expect(items.map((item) => item.label)).not.toContain('Register a business')
    }
    // Record tools only once the organisation is approved (effective_role comes from the backend).
    expect(labels(member('pending'))).not.toContain('Add record')
  })

  it('gives platform admins the organisation admin page instead', () => {
    expect(labels(user('platform_admin'))).toContain('Organisations')
    expect(labels(user('platform_admin'))).toContain('API keys')
    expect(labels(user('entity_admin'))).not.toContain('API keys')
    expect(labels(user('platform_admin'))).not.toContain('Register a business')
    expect(labels(user('consumer'))).not.toContain('Organisations')
  })

  it('offers nothing extra while a temporary password is pending', () => {
    expect(labels(user('consumer', true))).toEqual(['Profile'])
  })
})
