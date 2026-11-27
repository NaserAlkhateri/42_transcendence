import { useEffect, useMemo, type ReactNode } from 'react'

import { useAuth } from '../auth/auth-context'
import { LiveSocket } from '../lib/liveSocket'
import { LiveContext } from './live-context'

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user, refreshSession } = useAuth()
  const userId = user?.must_change_password ? undefined : user?.id
  const socket = useMemo(() => userId ? new LiveSocket(() => {
    void refreshSession(userId).catch(() => {})
  }) : null, [userId, refreshSession])

  useEffect(() => {
    if (!socket || !userId) return
    const controller = new AbortController()
    const removeListener = socket.onEvent((event) => {
      if (event.type === 'connection.ready') void refreshSession(userId, controller.signal).catch(() => {})
    })
    socket.start()
    return () => { controller.abort(); removeListener(); socket.stop() }
  }, [socket, userId, refreshSession])

  return <LiveContext.Provider value={socket}>{children}</LiveContext.Provider>
}
