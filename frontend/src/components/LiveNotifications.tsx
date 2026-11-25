import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { errorMessage, http } from '../lib/api'
import type { LiveEvent } from '../lib/liveSocket'
import { useLiveEvents } from '../live/live-context'
import { Button, FormAlert, Pagination } from './ui'

interface Notice {
  id: string
  event_type: string
  created_at: string
  read_at: string | null
  vin: string | null
  record_id: string | null
  organization_name: string | null
  status: string | null
}

interface Inbox { items: Notice[]; total: number; unread_count: number }
const PAGE_SIZE = 10
const date = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' })

function description(notice: Notice): string {
  const organization = notice.organization_name ?? 'Your organisation'
  switch (notice.event_type) {
    case 'record.added': return `New service record for ${notice.vin}.`
    case 'membership.added': return `You were added to ${organization}.`
    case 'membership.updated': return `Your membership in ${organization} changed.`
    case 'membership.removed': return `You were removed from ${organization}.`
    case 'organization.registered': return `${organization} submitted a registration for review.`
    case 'organization.resubmitted': return `${organization} resubmitted its registration.`
    case 'organization.reviewed': return notice.status === 'approved' ? `${organization} was approved.` : `${organization} was rejected.`
    case 'organization.updated': return `The details for ${organization} changed.`
    case 'organization.deleted': return `${organization} was deleted.`
    case 'account.updated': return 'A platform admin updated your account.'
    case 'account.password_reset': return 'A platform admin reset your password.'
    default: return 'You have a new account notification.'
  }
}

export function LiveNotifications() {
  const panelId = useId()
  const toggle = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [inbox, setInbox] = useState<Inbox>()
  const [incoming, setIncoming] = useState<Notice>()
  const [issue, setIssue] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [loadingPage, setLoadingPage] = useState(false)
  const request = useRef<AbortController>(undefined)
  const pendingNotice = useRef<string>(undefined)
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined)
  const selection = useRef({ unread: false, page: 1 })
  const [view, setView] = useState(selection.current)

  const refresh = useCallback(async (target = selection.current) => {
    request.current?.abort()
    const next = new AbortController()
    request.current = next
    const query = (page: number, unread: boolean) => `/notifications?page_size=${PAGE_SIZE}&page=${page}&unread=${unread}`
    try {
      // When browsing older pages, also fetch the newest page to resolve the latest live alert.
      const pending = pendingNotice.current
      const [result, latest] = await Promise.all([
        http.get<Inbox>(query(target.page, target.unread), { signal: next.signal }),
        pending && (target.page > 1 || target.unread)
          ? http.get<Inbox>(query(1, false), { signal: next.signal }) : undefined,
      ])
      if (next.signal.aborted) return
      const lastPage = Math.max(1, Math.ceil(result.total / PAGE_SIZE))
      const actual = { ...target, page: Math.min(target.page, lastPage) }
      const current = actual.page === target.page ? result
        : await http.get<Inbox>(query(actual.page, actual.unread), { signal: next.signal })
      if (next.signal.aborted) return
      selection.current = actual
      setView(actual)
      setInbox(current)
      setIssue(undefined)
      if (pending && pendingNotice.current === pending) {
        const notice = (latest ?? result).items.find(({ id }) => id === pending)
        if (notice && notice.read_at === null) setIncoming(notice)
        pendingNotice.current = undefined
      }
    } catch (error) {
      if (!next.signal.aborted) setIssue(errorMessage(error))
    } finally {
      if (!next.signal.aborted) setLoadingPage(false)
    }
  }, [])

  useEffect(() => () => { request.current?.abort(); clearTimeout(debounce.current) }, [])
  useLiveEvents(useCallback((event: LiveEvent) => {
    if (event.type === 'notification.created') pendingNotice.current = event.notificationId
    else if (event.type === 'notification.read_state_changed') setIncoming(undefined)
    else if (event.type !== 'connection.ready') return
    if (debounce.current === undefined) {
      debounce.current = setTimeout(() => { debounce.current = undefined; void refresh() }, 50)
    }
  }, [refresh]))

  function choose(next: typeof view) {
    selection.current = next
    setView(next)
    setLoadingPage(true)
    void refresh(next)
  }

  async function mutate(change: () => Promise<unknown>) {
    setBusy(true)
    setIssue(undefined)
    try { await change(); await refresh() }
    catch (error) { setIssue(errorMessage(error)) }
    finally { setBusy(false) }
  }

  function closePanel() { setOpen(false); toggle.current?.focus() }

  return <div className="relative flex items-center gap-2" onKeyDown={(event) => {
    if (event.key === 'Escape' && open) closePanel()
  }}>
    <Button ref={toggle} variant="ghost" size="sm" aria-expanded={open} aria-controls={open ? panelId : undefined} onClick={() => {
      if (!open) { setIncoming(undefined); void refresh() }
      setOpen((value) => !value)
    }}>Notifications{inbox?.unread_count ? ` (${inbox.unread_count})` : ''}</Button>
    {!open && incoming ? (
      <div className="absolute end-0 top-full z-20 mt-2 w-56 max-w-[68vw] rounded-card border border-brand-300 bg-white p-3 shadow-overlay">
        <p role="status">{description(incoming)}</p>
        {incoming.vin ? <Link className="text-brand-800 underline" to={`/vehicles/${incoming.vin}`} onClick={() => setIncoming(undefined)}>View timeline</Link> : null}
        <Button variant="ghost" size="sm" onClick={() => setIncoming(undefined)}>Dismiss</Button>
      </div>
    ) : null}
    {open ? (
      <section id={panelId} aria-label="Notifications" className="absolute end-0 top-full z-20 mt-2 w-80 max-w-[70vw] rounded-card border border-ink-200 bg-white p-3 shadow-overlay">
        <div className="mb-2 flex flex-wrap items-center gap-1">
          <Button size="sm" variant="ghost" aria-pressed={!view.unread} onClick={() => choose({ unread: false, page: 1 })}>All</Button>
          <Button size="sm" variant="ghost" aria-pressed={view.unread} onClick={() => choose({ unread: true, page: 1 })}>Unread</Button>
          <Button size="sm" variant="ghost" disabled={busy || !inbox?.unread_count}
            onClick={() => void mutate(() => http.post('/notifications/read-all'))}>Mark all as read</Button>
        </div>
        <FormAlert message={issue} />
        {loadingPage || !inbox ? !issue && <p role="status">Loading notifications…</p> : inbox.items.length === 0 ? (
          <p>{view.unread ? 'No unread notifications.' : 'No notifications.'}</p>
        ) : (
          <ul className="max-h-72 divide-y divide-ink-200 overflow-y-auto">
            {inbox.items.map((notice) => <li key={notice.id} className="py-2">
              <p className={notice.read_at ? '' : 'font-semibold'}>{description(notice)}</p>
              <p className="text-xs text-ink-600"><time dateTime={notice.created_at}>{date.format(new Date(notice.created_at))}</time>
                {notice.read_at === null ? ' · Unread' : ''}</p>
              <div className="flex flex-wrap items-center gap-1">
                {notice.vin ? <Link to={`/vehicles/${notice.vin}${notice.record_id ? `#record-${notice.record_id}` : ''}`}
                  className="text-sm text-brand-800 underline" onClick={closePanel}>View timeline</Link> : null}
                <Button variant="ghost" size="sm" disabled={busy} onClick={() => void mutate(() =>
                  http.patch(`/notifications/${notice.id}`, { read: notice.read_at === null }))}>
                  {notice.read_at === null ? 'Mark as read' : 'Mark as unread'}
                </Button>
              </div>
            </li>)}
          </ul>
        )}
        {inbox && inbox.total > PAGE_SIZE ? <Pagination total={inbox.total} pageSize={PAGE_SIZE} page={view.page}
          onPageChange={(page) => choose({ ...view, page })} /> : null}
      </section>
    ) : null}
  </div>
}
