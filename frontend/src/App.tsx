import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { useAuth } from './auth/auth-context'
import { LoginPage } from './pages/LoginPage'
import { ProfilePage } from './pages/ProfilePage'
import { SignupPage } from './pages/SignupPage'

// Minimal shell for NA-01 auth pages; HA-01 owns the full app shell and can replace this layout.
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
      <nav aria-label="Main" className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <Link to="/" className="text-lg font-bold text-emerald-800">
          Sijil
        </Link>
        {user ? (
          <div className="flex items-center gap-4 text-sm">
            <Link to="/profile" className="text-slate-700 hover:underline">
              {user.full_name}
            </Link>
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

function AppRoutes() {
  const { user } = useAuth()
  if (user === undefined) return <p className="text-center text-slate-500">Loading…</p>

  return (
    <Routes>
      <Route path="/" element={<Navigate to={user ? '/profile' : '/login'} replace />} />
      <Route path="/login" element={user ? <Navigate to="/profile" replace /> : <LoginPage />} />
      <Route path="/signup" element={user ? <Navigate to="/profile" replace /> : <SignupPage />} />
      <Route path="/profile" element={user ? <ProfilePage user={user} /> : <Navigate to="/login" replace />} />
      <Route path="*" element={<p className="text-center text-slate-600">Page not found.</p>} />
    </Routes>
  )
}
