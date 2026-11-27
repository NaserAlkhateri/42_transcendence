// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LiveSocket } from './liveSocket'

class FakeWebSocket {
  static readonly OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = 1
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  sent: { type: string; request_id: string; data: unknown }[] = []
  url: string
  constructor(url: string) { this.url = url; FakeWebSocket.instances.push(this) }
  send(message: string) { this.sent.push(JSON.parse(message)) }
  close() { this.readyState = 3 }
  disconnect(code: number) { this.close(); this.onclose?.({ code }) }
  receive(type: string, data: object, request_id?: string) {
    this.onmessage?.({ data: JSON.stringify({ v: 1, type, data, request_id }) })
  }
  ready() { this.receive('connection.ready', { heartbeat_seconds: 25 }) }
}

const VIN = 'JTMHX01J5M4012345'

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.useFakeTimers()
  vi.stubGlobal('WebSocket', FakeWebSocket)
  vi.spyOn(Math, 'random').mockReturnValue(0)
})

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('LiveSocket', () => {
  it('resubscribes on reconnect and dispatches only relevant, versioned events', () => {
    const client = new LiveSocket(vi.fn())
    const onEvent = vi.fn()
    client.onEvent(onEvent)
    const unwatch = client.watch(VIN)
    client.start()
    const [first] = FakeWebSocket.instances
    expect(first.url).toMatch(/\/api\/v1\/ws$/)
    expect(first.sent).toHaveLength(0)
    first.ready()
    expect(first.sent[0]).toMatchObject({ type: 'timeline.subscribe', data: { vin: VIN } })
    first.receive('record.added', { vin: 'not watched' })
    first.receive('record.added', { vin: VIN })
    expect(onEvent.mock.calls).toEqual([[{ type: 'connection.ready' }], [{ type: 'record.added', vin: VIN }]])

    first.disconnect(1006)
    expect(client.getStatus()).toBe('reconnecting')
    vi.advanceTimersByTime(500)
    const second = FakeWebSocket.instances[1]
    second.ready()
    second.receive('timeline.subscribed', { vin: VIN })
    second.receive('notification.created', { notification_id: 'notice' })
    expect(second.sent[0]).toMatchObject({ type: 'timeline.subscribe', data: { vin: VIN } })
    expect(onEvent).toHaveBeenLastCalledWith({ type: 'notification.created', notificationId: 'notice' })
    unwatch()
    expect(second.sent.slice(-1)[0]?.type).toBe('timeline.unsubscribe')
    client.stop()
    vi.advanceTimersByTime(90_000)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('detects a missing heartbeat and stops retrying after session expiry', () => {
    const authEnded = vi.fn()
    const client = new LiveSocket(authEnded)
    client.start()
    const [first] = FakeWebSocket.instances
    first.ready()
    vi.advanceTimersByTime(20_000)
    const ping = first.sent.slice(-1)[0]
    expect(ping?.type).toBe('ping')
    first.receive('pong', {}, ping?.request_id)
    vi.advanceTimersByTime(40_500)
    expect(client.getStatus()).toBe('reconnecting')
    FakeWebSocket.instances[1].disconnect(4401)
    expect(authEnded).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(90_000)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})
