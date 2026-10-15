// Partner API keys (NA-05). Types mirror backend/app/schemas/partner.py.

export interface ApiKeyRow {
  id: string
  partner_name: string
  key_prefix: string
  scopes: string[]
  created_at: string
  issued_by: string | null
  last_used_at: string | null
  revoked_at: string | null
  watch_count: number
}

export interface IssuedApiKey {
  key: ApiKeyRow
  /** The full key: shown once, never listed again. */
  api_key: string
}

export function validatePartnerName(name: string): string | undefined {
  const value = name.trim()
  if (value.length < 2) return 'Enter the partner’s name.'
  if (value.length > 120) return 'Use at most 120 characters.'
  return undefined
}
