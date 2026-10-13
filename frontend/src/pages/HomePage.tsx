import { Link } from 'react-router-dom'

import { buttonClass, Icon } from '../components/ui'
import { useAuth } from '../auth/auth-context'
import { VinSearchForm } from '../components/VinSearchForm'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export function HomePage() {
  useDocumentTitle()
  const { user } = useAuth()
  return (
    <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 py-10 text-center">
      <Icon name="shield" size={48} className="text-brand-700" />
      <h1 className="text-3xl font-bold sm:text-4xl">Trusted vehicle service history</h1>
      <p className="max-w-xl text-lg text-ink-600">
        Approved workshops record every service against the car&apos;s VIN. Buyers see the full timeline, including
        corrections and mileage warnings, before they decide.
      </p>
      <div className="w-full max-w-xl">
        <VinSearchForm />
      </div>
      {user ? (
        <Link to="/profile" className={buttonClass({size: 'lg'})}>
          Go to your account
        </Link>
      ) : (
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/signup" className={buttonClass({size: 'lg'})}>
            Create an account
          </Link>
          <Link to="/login" className={buttonClass({size: 'lg', variant: 'secondary'})}>
            Log in
          </Link>
        </div>
      )}
    </section>
  )
}
