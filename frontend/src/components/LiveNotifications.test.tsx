// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import { http } from '../lib/api'
import { LiveNotifications } from './LiveNotifications'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('filters the inbox, marks items in either direction, and clears the unread badge', async () => {
  const item = { id: 'n1', event_type: 'membership.removed', organization_name: 'Falcon Bay',
    created_at: '2026-11-23T12:00:00Z', read_at: null as string | null, vin: null, record_id: null, status: null }
  vi.spyOn(http, 'get').mockImplementation(async (path) => {
    const items = path.includes('unread=true') && item.read_at ? [] : [{ ...item }]
    return { items, total: items.length, unread_count: item.read_at ? 0 : 1 } as never
  })
  const patch = vi.spyOn(http, 'patch').mockImplementation(async (_path, body) => {
    item.read_at = (body as { read: boolean }).read ? '2026-11-23T12:01:00Z' : null
    return item as never
  })
  const post = vi.spyOn(http, 'post').mockImplementation(async () => {
    item.read_at = '2026-11-23T12:02:00Z'
    return undefined as never
  })

  render(<MemoryRouter><LiveNotifications /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
  const panel = within(screen.getByRole('region', { name: 'Notifications' }))
  await panel.findByText('You were removed from Falcon Bay.')
  await screen.findByRole('button', { name: 'Notifications (1)' })
  fireEvent.click(panel.getByRole('button', { name: 'Unread' }))
  fireEvent.click(await panel.findByRole('button', { name: 'Mark as read' }))
  await panel.findByText('No unread notifications.')
  expect(patch).toHaveBeenLastCalledWith('/notifications/n1', { read: true })
  fireEvent.click(panel.getByRole('button', { name: 'All' }))
  fireEvent.click(await panel.findByRole('button', { name: 'Mark as unread' }))
  await screen.findByRole('button', { name: 'Notifications (1)' })
  expect(patch).toHaveBeenLastCalledWith('/notifications/n1', { read: false })
  fireEvent.click(panel.getByRole('button', { name: 'Mark all as read' }))
  await screen.findByRole('button', { name: 'Notifications' })
  expect(post).toHaveBeenCalledWith('/notifications/read-all')
})
