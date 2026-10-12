import { createContext, useContext } from 'react'

export interface User {
  id: string
  email: string
  full_name: string
  role: 'consumer' | 'platform_admin'
  must_change_password: boolean
  created_at: string
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
