/** Only follow in-app paths so a crafted link cannot send the user off-site after login. */
export function safeRedirect(from: unknown, fallback = '/profile'): string {
  if (typeof from !== 'string') return fallback
  if (!from.startsWith('/') || from.startsWith('//') || from.startsWith('/\\')) return fallback
  if (from === '/login' || from === '/signup') return fallback
  return from
}
