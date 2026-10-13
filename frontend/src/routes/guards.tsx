import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth, type EffectiveRole } from '../auth/auth-context'
import { Alert } from '../components/ui'
import { hasRole } from '../lib/roles'
import { safeRedirect } from '../lib/redirect'

/** Signed-in users only. Remembers where the visitor was going so login can send them back. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return children
}

/** Guests only (login/signup): signed-in users go back where they were heading, or to their profile. */
export function RequireGuest({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()
  if (user) return <Navigate to={safeRedirect((location.state as { from?: unknown } | null)?.from)} replace />
  return children
}

/** Route guard: the UI hides what a role can't use; the API still enforces every permission. */
export function RequireRole({ roles, children }: { roles: readonly EffectiveRole[]; children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (user.must_change_password) return <Navigate to="/profile" replace />
  if (!hasRole(user, roles)) {
    return (
      <section className="mx-auto flex max-w-md flex-col gap-4 py-10 text-center">
        <h1>Access denied</h1>
        <Alert variant="danger">Your account does not have permission to view this page.</Alert>
      </section>
    )
  }
  return children
}
