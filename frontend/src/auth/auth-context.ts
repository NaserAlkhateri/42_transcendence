import { createContext, useContext } from 'react'

export type PlatformRole = 'consumer' | 'platform_admin'
export type MemberRole = 'entity_admin' | 'entity_staff'
export type EffectiveRole = PlatformRole | MemberRole

export interface Membership {
  id: string
  organization_id: string
  organization_name: string
  organization_status: 'pending' | 'approved' | 'rejected'
  role: MemberRole
  status: 'active' | 'inactive'
}

export interface User {
  id: string
  email: string
  full_name: string
  /** Platform role; entity roles live on memberships. */
  role: PlatformRole
  /** Highest role across platform role and active memberships: drives role-based views. */
  effective_role: EffectiveRole
  must_change_password: boolean
  created_at: string
  memberships: Membership[]
}

export interface AuthState {
  /** undefined while the first /me request is in flight, null when signed out. */
  user: User | null | undefined
  signup: (input: { email: string; password: string; full_name: string }) => Promise<User>
  login: (input: { email: string; password: string }) => Promise<User>
  logout: () => Promise<void>
  setUser: (user: User) => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth must be used inside <AuthProvider>')
  return state
}
