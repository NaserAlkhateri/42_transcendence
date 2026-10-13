import { useEffect, useId, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { Alert, Button, Icon, IconButton, buttonClass } from '../components/ui'
import { navItemsFor } from '../lib/roles'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-control px-3 py-2 text-sm ${isActive ? 'bg-brand-50 font-semibold text-brand-800' : 'text-ink-700 hover:bg-ink-100'}`

/** App shell: skip link, header with role-based nav (collapses on small screens), main outlet, footer. */
export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-ink-50 text-ink-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-white focus:px-3 focus:py-2 focus:shadow"
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
      <Button variant="ghost" icon="logout" onClick={() => void logout()}>
        Log out
      </Button>
    </>
  ) : user === null ? (
    <>
      <NavLink to="/login" className={navLinkClass}>
        Log in
      </NavLink>
      <Link to="/signup" className={buttonClass({size: 'sm'})}>
        Sign up
      </Link>
    </>
  ) : null

  return (
    <header className="border-b border-ink-200 bg-white">
      <nav aria-label="Main" className="mx-auto max-w-5xl px-4">
        <div className="flex items-center justify-between gap-4 py-3">
          <Link to="/" className="text-lg font-bold text-brand-800">
            <Icon name="car" className="inline me-2" />Sijil
          </Link>
          <div className="hidden items-center gap-1 sm:flex">{links}</div>
          {user !== undefined ? (
            <IconButton icon={open ? 'close' : 'menu'} label={open ? 'Close menu' : 'Open menu'} className="sm:hidden" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen(value => !value)} />
          ) : null}
        </div>
        {open ? (
          <div id={menuId} className="flex flex-col gap-1 border-t border-ink-100 py-3 sm:hidden">
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
    <Alert variant="warning" onDismiss={dismissSessionExpired} className="mx-auto w-full max-w-5xl">Your session has ended. Please log in again.</Alert>
  )
}

function Footer() {
  return (
    <footer className="border-t border-ink-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-col gap-2 px-4 py-6 text-sm text-ink-600 sm:flex-row sm:items-center sm:justify-between">
        <p>© {new Date().getFullYear()} Sijil · Demo vehicle data only. Not an official or government record.</p>
        <nav aria-label="Legal" className="flex flex-wrap gap-4"><Link to="/design-system" className="hover:underline">Design system</Link>
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
