import { startTransition, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { http, setUnauthorizedHandler } from '../lib/api'
import { AuthContext, type AuthState, type User } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    // /auth/session answers 200 with user=null for guests, so a signed-out visit logs no console error.
    // Any failure also leaves the visitor signed out.
    http
      .get<{ user: User | null }>('/auth/session', { silent401: true, signal: controller.signal })
      .then((session) => setUser(session.user))
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

  // Only forget the user once the server has revoked the session: the HttpOnly cookie would otherwise
  // still sign them back in on reload. Failures reach the caller, which tells the user.
  // Go home in the same render as the sign-out: a guarded page left on screen would remember itself
  // as the "return to" target for whoever logs in next. The router applies navigation in a transition,
  // so the sign-out joins that transition instead of rendering first on the old page.
  const logout = useCallback(async () => {
    await http.post<void>('/auth/logout', undefined, { silent401: true })
    startTransition(() => {
      navigate('/', { replace: true })
      setUser(null)
    })
  }, [navigate])

  const dismissSessionExpired = useCallback(() => setSessionExpired(false), [])

  const value = useMemo<AuthState>(
    () => ({ user, signup, login, logout, setUser, sessionExpired, dismissSessionExpired }),
    [user, signup, login, logout, sessionExpired, dismissSessionExpired],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
