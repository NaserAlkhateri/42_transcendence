import { Component, type ErrorInfo, type ReactNode } from 'react'

import { Button } from './ui'

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
        <h1 className="mb-2">Something went wrong</h1>
        <p className="mb-6 text-ink-600">The page hit an unexpected error. Reloading usually fixes it.</p>
        <Button
          onClick={() => window.location.reload()}
        >
          Reload page
        </Button>
      </section>
    )
  }
}
