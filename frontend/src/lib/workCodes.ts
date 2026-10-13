import { useEffect, useState } from 'react'

import { errorMessage, http } from './api'

/** GET /api/v1/work-codes: the predefined work codes (backend/app/services/work_codes.py). */
export interface WorkCode {
  code: string
  label: string
  label_ar: string
}

let cached: Promise<WorkCode[]> | undefined

/** Loaded once per page load; a failed load is retried next time. */
export function loadWorkCodes(): Promise<WorkCode[]> {
  cached ??= http.get<WorkCode[]>('/work-codes').catch((error: unknown) => {
    cached = undefined
    throw error
  })
  return cached
}

/** Readable fallback for a code the list doesn't know (or before it has loaded): OIL_CHANGE -> "Oil change". */
export function humanizeWorkCode(code: string): string {
  const words = code.toLowerCase().replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function useWorkCodes(): { codes?: WorkCode[]; error?: string; label: (code: string) => string } {
  const [codes, setCodes] = useState<WorkCode[]>()
  const [error, setError] = useState<string>()
  useEffect(() => {
    let active = true
    loadWorkCodes()
      .then((list) => active && setCodes(list))
      .catch((failure: unknown) => active && setError(errorMessage(failure)))
    return () => {
      active = false
    }
  }, [])
  const label = (code: string) => codes?.find((item) => item.code === code)?.label ?? humanizeWorkCode(code)
  return { codes, error, label }
}
