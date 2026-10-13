import { Link } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export function HomePage() {
  useDocumentTitle()
  const { user } = useAuth()
  return (
    <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 py-10 text-center">
      <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl">Trusted vehicle service history</h1>
      <p className="max-w-xl text-lg text-slate-600">
        Approved workshops record every service against the car&apos;s VIN. Buyers see the full timeline, including
        corrections and mileage warnings, before they decide.
      </p>
      {user ? (
        <Link to="/profile" className="rounded-md bg-emerald-700 px-5 py-2.5 font-medium text-white hover:bg-emerald-800">
          Go to your account
        </Link>
      ) : (
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/signup" className="rounded-md bg-emerald-700 px-5 py-2.5 font-medium text-white hover:bg-emerald-800">
            Create an account
          </Link>
          <Link to="/login" className="rounded-md border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-800 hover:bg-slate-100">
            Log in
          </Link>
        </div>
      )}
    </section>
  )
}
