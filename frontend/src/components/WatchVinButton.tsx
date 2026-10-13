import { useId } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { Button, buttonClass } from './ui'

/** "Watch" action for a VIN with no history yet. Guests are sent to log in and brought back here.
 *  The watchlist itself (API and toggling) is HA-04; until then signed-in users see the action disabled. */
export function WatchVinButton({ vin }: { vin: string }) {
  const { user } = useAuth()
  const hintId = useId()

  if (!user) {
    return (
      <Link to="/login" state={{ from: `/vehicles/${vin}` }} className={buttonClass()}>
        Log in to watch this VIN
      </Link>
    )
  }
  return (
    <div className="flex flex-col items-center gap-1">
      <Button icon="eye" disabled aria-describedby={hintId}>
        Watch this VIN
      </Button>
      <p id={hintId} className="text-sm text-ink-500">
        Watch alerts are coming soon.
      </p>
    </div>
  )
}
