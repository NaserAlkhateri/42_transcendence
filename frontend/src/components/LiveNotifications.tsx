import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { http } from '../lib/api'
import type { LiveEvent } from '../lib/liveSocket'
import { useLiveEvents } from '../live/live-context'
import { Button } from './ui'

interface WatchNotice { id: string; vin: string; record_id: string }

export function LiveNotifications() {
  const panelId = useId()
  const [open, setOpen] = useState(false)
  const [notices, setNotices] = useState<WatchNotice[]>()
  const [incoming, setIncoming] = useState<WatchNotice>()
  const [failed, setFailed] = useState(false)
  const controller = useRef<AbortController>(undefined)
  const pendingNotice = useRef<string>(undefined)
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined)

  const refresh = useCallback(() => {
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    void http.get<WatchNotice[]>('/notifications', { signal: next.signal }).then((rows) => {
      if (next.signal.aborted) return
      setNotices(rows)
      setFailed(false)
      if (pendingNotice.current) {
        const newNotice = rows.find(({ id }) => id === pendingNotice.current)
        if (newNotice) setIncoming(newNotice)
        pendingNotice.current = undefined
      }
    }).catch(() => { if (!next.signal.aborted) setFailed(true) })
  }, [])

  useEffect(() => () => { controller.current?.abort(); clearTimeout(debounce.current) }, [])
  useLiveEvents(useCallback((event: LiveEvent) => {
    if (event.type === 'notification.created') pendingNotice.current = event.notificationId
    if ((event.type === 'notification.created' || event.type === 'connection.ready') && debounce.current === undefined) {
      debounce.current = setTimeout(() => { debounce.current = undefined; refresh() }, 50)
    }
  }, [refresh]))

  return <div className="relative flex items-center gap-2">
    <Button variant="ghost" size="sm" aria-expanded={open} aria-controls={panelId} onClick={() => {
      if (!open) { setIncoming(undefined); refresh() }
      setOpen((value) => !value)
    }}>Notifications{notices?.length ? ` (${notices.length})` : ''}</Button>
    {!open && incoming ? (
      <div className="absolute end-0 top-full z-20 mt-2 w-64 rounded-card border border-brand-300 bg-white p-3 shadow-overlay">
        <p role="status">New service record for {incoming.vin}.</p>
        <Link className="text-brand-800 underline" to={`/vehicles/${incoming.vin}`} onClick={() => setIncoming(undefined)}>View timeline</Link>
        <Button variant="ghost" size="sm" onClick={() => setIncoming(undefined)}>Dismiss</Button>
      </div>
    ) : null}
    {open ? (
      <section id={panelId} aria-label="Recent notifications" className="absolute end-0 top-full z-20 mt-2 w-64 rounded-card border border-ink-200 bg-white p-3 shadow-overlay">
        {failed ? <p role="status">Could not load notifications. Reopen to retry.</p> : notices === undefined ? <p role="status">Loading notifications…</p>
          : notices.length === 0 ? <p>No recent notifications.</p> : (
            <ul className="max-h-64 divide-y divide-ink-200 overflow-y-auto">
              {notices.map((notice) => <li key={notice.id} className="py-2">
                <Link to={`/vehicles/${notice.vin}`} className="text-brand-800 underline" onClick={() => { setOpen(false); setIncoming(undefined) }}>
                  New service record for {notice.vin}
                </Link>
              </li>)}
            </ul>
          )}
      </section>
    ) : null}
  </div>
}
