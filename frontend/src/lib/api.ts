// Typed fetch wrapper for /api/v1.
// - Sends the session cookie and adds the CSRF header to state-changing calls.
// - Turns the backend's {"error": {code, message, details}} envelope into an ApiError.
// - Network failures and timeouts also become ApiError (status 0) so callers handle one error type.
// - A 401 on any call except the initial session probe notifies the auth layer (session expired).

const API_PREFIX = '/api/v1'
const CSRF_COOKIE = 'sijil_csrf'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
const DEFAULT_TIMEOUT_MS = 15_000

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface FieldIssue {
  loc: (string | number)[]
  message: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: FieldIssue[]

  constructor(status: number, code: string, message: string, details: FieldIssue[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export interface ApiOptions {
  method?: HttpMethod
  body?: unknown
  signal?: AbortSignal
  /** Milliseconds before the request is aborted. Default 15 s. */
  timeoutMs?: number
  /** Skip the global 401 handler (used by the initial session probe). */
  silent401?: boolean
}

let onUnauthorized: (() => void) | undefined

/** Register the callback run when the API answers 401 (the auth provider signs the user out). */
export function setUnauthorizedHandler(handler: (() => void) | undefined): void {
  onUnauthorized = handler
}

let onForbidden: (() => void) | undefined

/** Register the callback run when the API answers 403 `forbidden`: the user's role may have changed since
 * the page loaded (e.g. an admin was demoted), so the auth provider re-reads the session. */
export function setForbiddenHandler(handler: (() => void) | undefined): void {
  onForbidden = handler
}

/** Map backend 422 details (loc: ["body", "full_name"]) onto form field keys. */
export function serverFieldErrors<K extends string>(error: unknown, fields: Record<string, K>): Partial<Record<K, string>> {
  if (!(error instanceof ApiError)) return {}
  const result: Partial<Record<K, string>> = {}
  for (const issue of error.details) {
    const field = fields[String(issue.loc[issue.loc.length - 1])]
    if (field && !result[field]) result[field] = issue.message
  }
  return result
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Could not reach the server. Please try again.'
  if (error.code === 'validation_error') {
    // "Request validation failed" means nothing to a user; say what was wrong instead.
    const first = error.details[0]?.message
    return first ? `Please check your details: ${first.replace(/^Value error, /, '')}` : 'Please check your details and try again.'
  }
  return error.message
}

function readCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1)
}

async function csrfToken(signal: AbortSignal): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) return existing
  const response = await fetch(`${API_PREFIX}/auth/csrf`, { credentials: 'same-origin', signal })
  if (!response.ok) throw new ApiError(response.status, 'csrf_unavailable', 'Could not start a secure session. Please reload.')
  const body = (await response.json()) as { csrf_token: string }
  return body.csrf_token
}

/** Combine the caller's signal with a timeout. */
function withTimeout(outer: AbortSignal | undefined, timeoutMs: number) {
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const forward = () => controller.abort()
  if (outer) {
    if (outer.aborted) forward()
    else outer.addEventListener('abort', forward, { once: true })
  }
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    cancel: () => {
      clearTimeout(timer)
      outer?.removeEventListener('abort', forward)
    },
  }
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  const timeout = withTimeout(options.signal, options.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  let response: Response
  try {
    if (!SAFE_METHODS.has(method)) headers['X-CSRF-Token'] = await csrfToken(timeout.signal)
    response = await fetch(`${API_PREFIX}${path}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: timeout.signal,
    })
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (options.signal?.aborted) throw error // cancelled by the caller (e.g. unmount): let it be ignored
    const timedOut = timeout.timedOut()
    throw new ApiError(
      0,
      timedOut ? 'timeout' : 'network_error',
      timedOut ? 'The server took too long to answer. Please try again.' : 'Could not reach the server. Please try again.',
    )
  } finally {
    timeout.cancel()
  }

  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && !options.silent401) onUnauthorized?.()
    const error = (payload as { error?: { code: string; message: string; details?: FieldIssue[] } } | null)?.error
    if (response.status === 403 && error?.code === 'forbidden') onForbidden?.()
    throw new ApiError(
      response.status,
      error?.code ?? 'http_error',
      error?.message ?? 'Something went wrong. Please try again.',
      error?.details,
    )
  }
  return payload as T
}

type Opts = Omit<ApiOptions, 'method' | 'body'>

/** Shorthands so call sites read as intent. */
export const http = {
  get: <T>(path: string, options?: Opts) => api<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: Opts) => api<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, options?: Opts) => api<T>(path, { ...options, method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, options?: Opts) => api<T>(path, { ...options, method: 'PUT', body }),
  delete: <T = void>(path: string, options?: Opts) => api<T>(path, { ...options, method: 'DELETE' }),
}
