import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api } from '../lib/api'
import { AuthContext, type AuthState, type User } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined)

  useEffect(() => {
    // 401 simply means "signed out"; any other failure also leaves the visitor signed out.
    api<User>('/me')
      .then(setUser)
      .catch(() => setUser(null))
  }, [])

  const signup = useCallback<AuthState['signup']>(async (input) => {
    const created = await api<User>('/auth/signup', { method: 'POST', body: input })
    setUser(created)
    return created
  }, [])

  const login = useCallback<AuthState['login']>(async (input) => {
    const signedIn = await api<User>('/auth/login', { method: 'POST', body: input })
    setUser(signedIn)
    return signedIn
  }, [])

  const logout = useCallback(async () => {
    await api<void>('/auth/logout', { method: 'POST' })
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, signup, login, logout, setUser }), [user, signup, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
