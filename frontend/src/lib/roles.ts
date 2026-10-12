import type { EffectiveRole, MemberRole, PlatformRole, User } from '../auth/auth-context'

export const ROLE_LABELS: Record<EffectiveRole, string> = {
  platform_admin: 'Platform admin',
  entity_admin: 'Entity admin',
  entity_staff: 'Entity staff',
  consumer: 'Consumer',
}

export const PLATFORM_ROLES: PlatformRole[] = ['consumer', 'platform_admin']
export const MEMBER_ROLES: MemberRole[] = ['entity_admin', 'entity_staff']

/** Signed-in, past any temporary password, and holding one of `roles`. The backend re-checks every call. */
export function hasRole(user: User | null | undefined, roles: readonly EffectiveRole[]): boolean {
  return !!user && !user.must_change_password && roles.includes(user.effective_role)
}

export interface NavItem {
  to: string
  label: string
}

/** Role-specific navigation. Later cards add entries (organization dashboard, record form, review queue). */
export function navItemsFor(user: User | null | undefined): NavItem[] {
  if (!user) return []
  const items: NavItem[] = [{ to: '/profile', label: 'Profile' }]
  if (hasRole(user, ['platform_admin'])) items.push({ to: '/admin/users', label: 'Users' })
  return items
}
