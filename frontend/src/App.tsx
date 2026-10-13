import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { useAuth } from './auth/auth-context'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AppLayout } from './layouts/AppLayout'
import { HomePage } from './pages/HomePage'
import { NotFoundPage, PolicyPlaceholderPage } from './pages/NotFoundPage'
import { RequireAuth, RequireGuest, RequireRole } from './routes/guards'

// Pages behind a sign-in are split into their own chunks so the first load stays small.
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const SignupPage = lazy(() => import('./pages/SignupPage').then((m) => ({ default: m.SignupPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const AdminUsersPage = lazy(() => import('./pages/AdminUsersPage').then((m) => ({ default: m.AdminUsersPage })))

export function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

function PageLoading() {
  return (
    <p role="status" className="text-center text-slate-500">
      Loading…
    </p>
  )
}

/** Route table. Add new pages here and their nav entry in `lib/roles.ts` (navItemsFor). */
function AppRoutes() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route element={<AppLayout />}>
        {user === undefined ? (
          // Waiting for the first /me answer: don't flash the login page for signed-in users.
          <Route path="*" element={<PageLoading />} />
        ) : (
          <>
            <Route index element={<HomePage />} />
            <Route path="login" element={<Lazy><RequireGuest><LoginPage /></RequireGuest></Lazy>} />
            <Route path="signup" element={<Lazy><RequireGuest><SignupPage /></RequireGuest></Lazy>} />
            <Route path="profile" element={<Lazy><RequireAuth>{user ? <ProfilePage user={user} /> : null}</RequireAuth></Lazy>} />
            <Route
              path="admin/users"
              element={<Lazy><RequireRole roles={['platform_admin']}><AdminUsersPage /></RequireRole></Lazy>}
            />
            <Route path="privacy" element={<PolicyPlaceholderPage title="Privacy Policy" />} />
            <Route path="terms" element={<PolicyPlaceholderPage title="Terms of Service" />} />
            <Route path="*" element={<NotFoundPage />} />
          </>
        )}
      </Route>
    </Routes>
  )
}

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoading />}>{children}</Suspense>
}
