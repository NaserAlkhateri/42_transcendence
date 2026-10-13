import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { http, setUnauthorizedHandler } from '../lib/api'
import { AuthContext, type AuthState, type User } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    // 401 simply means "signed out"; any other failure also leaves the visitor signed out.
    http
      .get<User>('/me', { silent401: true, signal: controller.signal })
      .then(setUser)
      .catch(() => {
        if (!controller.signal.aborted) setUser(null)
      })
    return () => controller.abort()
  }, [])

  // Any later 401 means the session ended (expired, revoked, signed out elsewhere).
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser((current) => {
        if (current) setSessionExpired(true)
        return null
      })
    })
    return () => setUnauthorizedHandler(undefined)
  }, [])

  const signup = useCallback<AuthState['signup']>(async (input) => {
    const created = await http.post<User>('/auth/signup', input)
    setSessionExpired(false)
    setUser(created)
    return created
  }, [])

  const login = useCallback<AuthState['login']>(async (input) => {
    // invalid_credentials is a 401 too: it must not trigger the "session expired" path.
    const signedIn = await http.post<User>('/auth/login', input, { silent401: true })
    setSessionExpired(false)
    setUser(signedIn)
    return signedIn
  }, [])

  const logout = useCallback(async () => {
    try {
      await http.post<void>('/auth/logout', undefined, { silent401: true })
    } finally {
      setUser(null)
    }
  }, [])

  const dismissSessionExpired = useCallback(() => setSessionExpired(false), [])

  const value = useMemo<AuthState>(
    () => ({ user, signup, login, logout, setUser, sessionExpired, dismissSessionExpired }),
    [user, signup, login, logout, sessionExpired, dismissSessionExpired],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
