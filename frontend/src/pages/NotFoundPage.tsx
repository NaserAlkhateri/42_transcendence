import { Link } from 'react-router-dom'

import { useDocumentTitle } from '../lib/useDocumentTitle'

export function NotFoundPage() {
  useDocumentTitle('Page not found')
  return (
    <section className="mx-auto max-w-md py-10 text-center">
      <p className="mb-2 text-sm font-semibold text-emerald-800">404</p>
      <h1 className="mb-2 text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="mb-6 text-slate-600">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800">
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
      <h1 className="mb-4 text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="text-slate-600">This page is being written and will be published before release.</p>
    </section>
  )
}
