import type { ReactNode } from 'react'
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { useAuth, type EffectiveRole } from './auth/auth-context'
import { hasRole, navItemsFor } from './lib/roles'
import { AdminUsersPage } from './pages/AdminUsersPage'
import { LoginPage } from './pages/LoginPage'
import { ProfilePage } from './pages/ProfilePage'
import { SignupPage } from './pages/SignupPage'

// Minimal shell for NA-01/NA-02 pages; HA-01 owns the full app shell and can replace this layout.
export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="flex min-h-screen flex-col bg-slate-50">
          <Header />
          <main className="flex-1 px-4 py-10">
            <AppRoutes />
          </main>
        </div>
      </AuthProvider>
    </BrowserRouter>
  )
}

function Header() {
  const { user, logout } = useAuth()
  return (
    <header className="border-b border-slate-200 bg-white">
      <nav aria-label="Main" className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <Link to="/" className="text-lg font-bold text-emerald-800">
          Sijil
        </Link>
        {user ? (
          <div className="flex items-center gap-4 text-sm">
            {navItemsFor(user).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => (isActive ? 'font-semibold text-emerald-800' : 'text-slate-700 hover:underline')}
              >
                {item.label}
              </NavLink>
            ))}
            <button type="button" onClick={() => void logout()} className="text-slate-700 hover:underline">
              Log out
            </button>
          </div>
        ) : user === null ? (
          <div className="flex items-center gap-4 text-sm">
            <Link to="/login" className="text-slate-700 hover:underline">
              Log in
            </Link>
            <Link to="/signup" className="rounded-md bg-emerald-700 px-3 py-1.5 text-white hover:bg-emerald-800">
              Sign up
            </Link>
          </div>
        ) : null}
      </nav>
    </header>
  )
}

/** Route guard: the UI hides what a role can't use; the API still enforces every permission. */
function RequireRole({ roles, children }: { roles: readonly EffectiveRole[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.must_change_password) return <Navigate to="/profile" replace />
  if (!hasRole(user, roles)) {
    return (
      <section className="mx-auto max-w-md text-center">
        <h1 className="mb-2 text-2xl font-semibold text-slate-900">Access denied</h1>
        <p className="text-slate-600">Your account does not have permission to view this page.</p>
      </section>
    )
  }
  return children
}

function AppRoutes() {
  const { user } = useAuth()
  if (user === undefined) return <p className="text-center text-slate-500">Loading…</p>

  return (
    <Routes>
      <Route path="/" element={<Navigate to={user ? '/profile' : '/login'} replace />} />
      <Route path="/login" element={user ? <Navigate to="/profile" replace /> : <LoginPage />} />
      <Route path="/signup" element={user ? <Navigate to="/profile" replace /> : <SignupPage />} />
      <Route path="/profile" element={user ? <ProfilePage user={user} /> : <Navigate to="/login" replace />} />
      <Route
        path="/admin/users"
        element={
          <RequireRole roles={['platform_admin']}>
            <AdminUsersPage />
          </RequireRole>
        }
      />
      <Route path="*" element={<p className="text-center text-slate-600">Page not found.</p>} />
    </Routes>
  )
}
