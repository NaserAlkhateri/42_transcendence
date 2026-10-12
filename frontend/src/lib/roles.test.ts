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
