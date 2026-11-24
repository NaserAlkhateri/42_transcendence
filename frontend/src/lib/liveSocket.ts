export type LiveStatus = 'connecting' | 'live' | 'reconnecting' | 'closed'

export type LiveEvent =
  | { type: 'connection.ready' }
  | { type: 'timeline.subscribed' | 'record.added'; vin: string }
  | { type: 'notification.created'; notificationId: string }

const RETRY_MAX_MS = 15_000
const READY_TIMEOUT_MS = 10_000

export class LiveSocket {
  private socket?: WebSocket
  private retry?: ReturnType<typeof setTimeout>
  private readyTimeout?: ReturnType<typeof setTimeout>
  private heartbeat?: ReturnType<typeof setInterval>
  private status: LiveStatus = 'connecting'
  private started = false
  private failures = 0
  private pendingPing?: string
  private readonly watches = new Map<string, number>()
  private readonly listeners = new Set<(event: LiveEvent) => void>()
  private readonly statusListeners = new Set<() => void>()
  private readonly authEnded: () => void

  constructor(authEnded: () => void) { this.authEnded = authEnded }

  getStatus = () => this.status

  onStatus = (listener: () => void) => {
    this.statusListeners.add(listener)
    return () => { this.statusListeners.delete(listener) }
  }

  onEvent(listener: (event: LiveEvent) => void) {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  watch(vin: string) {
    const count = this.watches.get(vin) ?? 0
    this.watches.set(vin, count + 1)
    if (count === 0 && this.status === 'live') this.send('timeline.subscribe', { vin })
    return () => {
      const remaining = (this.watches.get(vin) ?? 1) - 1
      if (remaining > 0) this.watches.set(vin, remaining)
      else {
        this.watches.delete(vin)
        if (this.status === 'live') this.send('timeline.unsubscribe', { vin })
      }
    }
  }

  start() {
    this.started = true
    window.addEventListener('online', this.onOnline)
    window.addEventListener('offline', this.onOffline)
    this.setStatus('connecting')
    this.connect()
  }

  stop() {
    this.started = false
    window.removeEventListener('online', this.onOnline)
    window.removeEventListener('offline', this.onOffline)
    clearTimeout(this.retry)
    this.releaseSocket()
    this.setStatus('closed')
  }

  private setStatus(status: LiveStatus) {
    if (this.status === status) return
    this.status = status
    this.statusListeners.forEach((listener) => listener())
  }

  private connect() {
    if (!this.started || this.socket) return
    if (!navigator.onLine) { this.setStatus('reconnecting'); return }
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:'
    let socket: WebSocket
    try { socket = new WebSocket(`${scheme}//${location.host}/api/v1/ws`) }
    catch { this.scheduleRetry(); return }
    this.socket = socket
    this.readyTimeout = setTimeout(() => this.reconnect(), READY_TIMEOUT_MS)
    socket.onmessage = (event) => this.receive(event.data)
    socket.onclose = (event) => {
      this.releaseSocket()
      if (!this.started) return
      if (event.code === 4401 || event.code === 4403) {
        this.stop()
        this.authEnded()
      } else this.scheduleRetry()
    }
  }

  private releaseSocket() {
    clearTimeout(this.readyTimeout)
    clearInterval(this.heartbeat)
    this.pendingPing = undefined
    if (this.socket) {
      this.socket.onclose = null
      this.socket.onmessage = null
      if (this.socket.readyState <= WebSocket.OPEN) this.socket.close()
      this.socket = undefined
    }
  }

  private scheduleRetry() {
    this.setStatus('reconnecting')
    if (!this.started || !navigator.onLine) return
    const delay = Math.min(RETRY_MAX_MS, 500 * 2 ** Math.min(this.failures++, 6))
    clearTimeout(this.retry)
    this.retry = setTimeout(() => this.connect(), delay + Math.random() * 250)
  }

  private reconnect() {
    this.releaseSocket()
    this.scheduleRetry()
  }

  private onOnline = () => {
    if (!this.started) return
    clearTimeout(this.retry)
    this.connect()
  }

  private onOffline = () => this.reconnect()

  private send(type: string, data: object): string | undefined {
    if (this.socket?.readyState !== WebSocket.OPEN) return
    const request_id = crypto.randomUUID()
    this.socket.send(JSON.stringify({ v: 1, type, request_id, data }))
    return request_id
  }

  private receive(raw: unknown) {
    if (typeof raw !== 'string') return
    let message: { v?: number; type?: string; request_id?: string; data?: Record<string, unknown> } | null
    try { message = JSON.parse(raw) as typeof message } catch { return }
    if (message?.v !== 1 || !message.data) return
    const data = message.data
    if (message.type === 'connection.ready' && this.status !== 'live') {
      const seconds = data.heartbeat_seconds
      if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 5 || seconds > 120) return
      clearTimeout(this.readyTimeout)
      this.failures = 0
      this.setStatus('live')
      for (const vin of this.watches.keys()) this.send('timeline.subscribe', { vin })
      this.emit({ type: 'connection.ready' })
      this.heartbeat = setInterval(() => {
        if (this.pendingPing) this.reconnect()
        else this.pendingPing = this.send('ping', {})
      }, seconds * 800)
    } else if (this.status === 'live') {
      if (message.type === 'pong' && message.request_id === this.pendingPing) this.pendingPing = undefined
      else if ((message.type === 'record.added' || message.type === 'timeline.subscribed') && typeof data.vin === 'string') {
        if (this.watches.has(data.vin)) this.emit({ type: message.type, vin: data.vin })
      } else if (message.type === 'notification.created' && typeof data.notification_id === 'string') {
        this.emit({ type: message.type, notificationId: data.notification_id })
      }
    }
  }

  private emit(event: LiveEvent) {
    this.listeners.forEach((listener) => listener(event))
  }
}
