import { useEffect, useId, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { navItemsFor } from '../lib/roles'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-emerald-50 font-semibold text-emerald-800' : 'text-slate-700 hover:bg-slate-100'}`

/** App shell: skip link, header with role-based nav (collapses on small screens), main outlet, footer. */
export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <Header />
      <SessionNotice />
      <main id="main" tabIndex={-1} className="flex-1 px-4 py-10 outline-none">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

function Header() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const menuId = useId()
  const [open, setOpen] = useState(false)

  // Close the mobile menu whenever the route changes.
  useEffect(() => setOpen(false), [location.pathname])

  const items = navItemsFor(user)

  const links = user ? (
    <>
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} className={navLinkClass}>
          {item.label}
        </NavLink>
      ))}
      <button type="button" onClick={() => void logout()} className="rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100">
        Log out
      </button>
    </>
  ) : user === null ? (
    <>
      <NavLink to="/login" className={navLinkClass}>
        Log in
      </NavLink>
      <Link to="/signup" className="rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-800">
        Sign up
      </Link>
    </>
  ) : null

  return (
    <header className="border-b border-slate-200 bg-white">
      <nav aria-label="Main" className="mx-auto max-w-5xl px-4">
        <div className="flex items-center justify-between gap-4 py-3">
          <Link to="/" className="text-lg font-bold text-emerald-800">
            Sijil
          </Link>
          <div className="hidden items-center gap-1 sm:flex">{links}</div>
          {user !== undefined ? (
            <button
              type="button"
              className="rounded-md p-2 text-slate-700 hover:bg-slate-100 sm:hidden"
              aria-expanded={open}
              aria-controls={menuId}
              onClick={() => setOpen((value) => !value)}
            >
              <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
                {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
              </svg>
            </button>
          ) : null}
        </div>
        {open ? (
          <div id={menuId} className="flex flex-col gap-1 border-t border-slate-100 py-3 sm:hidden">
            {links}
          </div>
        ) : null}
      </nav>
    </header>
  )
}

function SessionNotice() {
  const { sessionExpired, dismissSessionExpired } = useAuth()
  if (!sessionExpired) return null
  return (
    <div role="status" className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-2 text-sm text-amber-900">
        <span>Your session has ended. Please log in again.</span>
        <button type="button" onClick={dismissSessionExpired} className="underline">
          Dismiss
        </button>
      </div>
    </div>
  )
}

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-col gap-2 px-4 py-6 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between">
        <p>© {new Date().getFullYear()} Sijil · Demo vehicle data only. Not an official or government record.</p>
        <nav aria-label="Legal" className="flex gap-4">
          <Link to="/privacy" className="hover:underline">
            Privacy Policy
          </Link>
          <Link to="/terms" className="hover:underline">
            Terms of Service
          </Link>
        </nav>
      </div>
    </footer>
  )
}
