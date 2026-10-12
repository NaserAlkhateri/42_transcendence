// Thin fetch wrapper for /api/v1: sends cookies, adds the CSRF header to state-changing calls
// and turns the backend's {"error": {code, message, details}} body into an ApiError.

const API_PREFIX = '/api/v1'
const CSRF_COOKIE = 'sijil_csrf'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

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
    this.status = status
    this.code = code
    this.details = details
  }
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
  return error instanceof ApiError ? error.message : 'Could not reach the server. Please try again.'
}

function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1)
}

async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) return existing
  const response = await fetch(`${API_PREFIX}/auth/csrf`, { credentials: 'same-origin' })
  const body = (await response.json()) as { csrf_token: string }
  return body.csrf_token
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (init.body !== undefined) headers['Content-Type'] = 'application/json'
  if (!SAFE_METHODS.has(method)) headers['X-CSRF-Token'] = await csrfToken()

  const response = await fetch(`${API_PREFIX}${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  })

  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = (payload as { error?: { code: string; message: string; details?: FieldIssue[] } } | null)?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'http_error',
      error?.message ?? 'Something went wrong. Please try again.',
      error?.details,
    )
  }
  return payload as T
}
