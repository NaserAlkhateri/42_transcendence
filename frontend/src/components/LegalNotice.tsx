import { Link } from 'react-router-dom'

/** "By … you agree to …" with links, shown above the button that creates an account or registers a business. */
export function LegalNotice({ action }: { action: string }) {
  return (
    <p className="text-sm text-ink-600">
      By {action} you agree to the <Link className="text-brand-800 underline" to="/terms">Terms of Service</Link> and
      confirm you have read the <Link className="text-brand-800 underline" to="/privacy">Privacy Policy</Link>.
    </p>
  )
}
