import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { useAuth } from './auth/auth-context'
import { Spinner } from './components/ui'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AppLayout } from './layouts/AppLayout'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RequireAuth, RequireGuest, RequireRole } from './routes/guards'

// Pages behind a sign-in are split into their own chunks so the first load stays small.
const DesignSystemPage = lazy(() => import('./pages/DesignSystemPage').then(m => ({default: m.DesignSystemPage})))
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const SignupPage = lazy(() => import('./pages/SignupPage').then((m) => ({ default: m.SignupPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const AdminUsersPage = lazy(() => import('./pages/AdminUsersPage').then((m) => ({ default: m.AdminUsersPage })))
const AdminApiKeysPage = lazy(() => import('./pages/AdminApiKeysPage').then((m) => ({ default: m.AdminApiKeysPage })))
const AdminOrganizationsPage = lazy(() => import('./pages/AdminOrganizationsPage').then((m) => ({ default: m.AdminOrganizationsPage })))
const RegisterOrganizationPage = lazy(() => import('./pages/organizations/RegisterOrganizationPage').then((m) => ({ default: m.RegisterOrganizationPage })))
const OrganizationPage = lazy(() => import('./pages/organizations/OrganizationPage').then((m) => ({ default: m.OrganizationPage })))
const PrivacyPolicyPage = lazy(() => import('./pages/legal/LegalPages').then((m) => ({ default: m.PrivacyPolicyPage })))
const TermsOfServicePage = lazy(() => import('./pages/legal/LegalPages').then((m) => ({ default: m.TermsOfServicePage })))
const VehicleTimelinePage = lazy(() => import('./pages/VehicleTimelinePage').then((m) => ({ default: m.VehicleTimelinePage })))
const NewRecordPage = lazy(() => import('./pages/workshop/NewRecordPage').then((m) => ({ default: m.NewRecordPage })))
const CorrectRecordPage = lazy(() => import('./pages/workshop/CorrectRecordPage').then((m) => ({ default: m.CorrectRecordPage })))

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
    <div className="flex justify-center text-ink-600"><Spinner label="Loading page" /></div>
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
            <Route path="design-system" element={<Lazy><DesignSystemPage /></Lazy>} />
            <Route path="vehicles/:vin" element={<Lazy><VehicleTimelinePage /></Lazy>} />
            <Route path="login" element={<Lazy><RequireGuest><LoginPage /></RequireGuest></Lazy>} />
            <Route path="signup" element={<Lazy><RequireGuest><SignupPage /></RequireGuest></Lazy>} />
            <Route path="profile" element={<Lazy><RequireAuth>{user ? <ProfilePage user={user} /> : null}</RequireAuth></Lazy>} />
            <Route
              path="workshop/records/new"
              element={<Lazy><RequireRole roles={['entity_admin', 'entity_staff']}><NewRecordPage /></RequireRole></Lazy>}
            />
            <Route
              path="workshop/corrections"
              element={<Lazy><RequireRole roles={['entity_admin', 'entity_staff']}><CorrectRecordPage /></RequireRole></Lazy>}
            />
            <Route
              path="organizations/register"
              element={<Lazy><RequireAuth><RegisterOrganizationPage /></RequireAuth></Lazy>}
            />
            <Route path="organizations/:id" element={<Lazy><RequireAuth><OrganizationPage /></RequireAuth></Lazy>} />
            <Route
              path="admin/organizations"
              element={<Lazy><RequireRole roles={['platform_admin']}><AdminOrganizationsPage /></RequireRole></Lazy>}
            />
            <Route
              path="admin/api-keys"
              element={<Lazy><RequireRole roles={['platform_admin']}><AdminApiKeysPage /></RequireRole></Lazy>}
            />
            <Route
              path="admin/users"
              element={<Lazy><RequireRole roles={['platform_admin']}><AdminUsersPage /></RequireRole></Lazy>}
            />
            <Route path="privacy" element={<Lazy><PrivacyPolicyPage /></Lazy>} />
            <Route path="terms" element={<Lazy><TermsOfServicePage /></Lazy>} />
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
