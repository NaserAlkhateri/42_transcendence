import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error?: Error
}

/** Last-resort boundary: a rendering bug shows a recoverable message instead of a blank page. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = {}

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Logged for developers; users see the fallback below.
    console.error('Unhandled UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <section role="alert" className="mx-auto max-w-md py-16 text-center">
        <h1 className="mb-2 text-2xl font-semibold text-slate-900">Something went wrong</h1>
        <p className="mb-6 text-slate-600">The page hit an unexpected error. Reloading usually fixes it.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800"
        >
          Reload page
        </button>
      </section>
    )
  }
}
