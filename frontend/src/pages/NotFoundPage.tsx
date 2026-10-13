import { Link } from 'react-router-dom'

import { buttonClass, Alert } from '../components/ui'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export function NotFoundPage() {
  useDocumentTitle('Page not found')
  return (
    <section className="mx-auto max-w-md py-10 text-center">
      <p className="mb-2 text-sm font-semibold text-brand-800">404</p>
      <h1 className="mb-2">Page not found</h1>
      <p className="mb-6 text-ink-600">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className={buttonClass()}>
        Back to home
      </Link>
    </section>
  )
}

/** Placeholder for the legal pages until NA-07 delivers the real content. */
export function PolicyPlaceholderPage({ title }: { title: string }) {
  useDocumentTitle(title)
  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-4">{title}</h1>
      <Alert>This page is being written and will be published before release.</Alert>
    </section>
  )
}
