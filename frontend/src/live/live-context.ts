import { createContext, useContext, useEffect, useState, useSyncExternalStore } from 'react'

import type { LiveEvent, LiveSocket, LiveStatus } from '../lib/liveSocket'

export const LiveContext = createContext<LiveSocket | null>(null)
const unsubscribed = () => () => {}
const closed = (): LiveStatus => 'closed'

export function useLiveStatus() {
  const socket = useContext(LiveContext)
  return useSyncExternalStore(socket?.onStatus ?? unsubscribed, socket?.getStatus ?? closed)
}

export function useLiveEvents(onEvent: (event: LiveEvent) => void) {
  const socket = useContext(LiveContext)
  useEffect(() => socket?.onEvent(onEvent), [socket, onEvent])
}

export function useTimelineRevision(vin: string) {
  const socket = useContext(LiveContext)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    if (!socket) return
    let debounce: ReturnType<typeof setTimeout> | undefined
    const unsubscribe = socket.onEvent((event) => {
      if ((event.type === 'record.added' || event.type === 'timeline.subscribed') && event.vin === vin && debounce === undefined) {
        debounce = setTimeout(() => { debounce = undefined; setRevision((value) => value + 1) }, 50)
      }
    })
    const unwatch = socket.watch(vin)
    return () => { clearTimeout(debounce); unsubscribe(); unwatch() }
  }, [socket, vin])
  return revision
}
