// Client-side copy of backend/app/services/vin.py:normalize_vin. The backend stays authoritative.

const VIN_PATTERN = /^[A-HJ-NPR-Z0-9]{17}$/
const SEPARATORS = /[\s-]+/g
// Arabic-Indic (U+0660..0669) and Extended Arabic-Indic (U+06F0..06F9) digits, as typed on Arabic keyboards.
const ARABIC_DIGITS = /[٠-٩۰-۹]/g

export const INVALID_VIN_MESSAGE = 'A VIN has exactly 17 letters or digits and never contains I, O or Q.'

export type VinResult = { ok: true; vin: string } | { ok: false; error: string }

function toLatinDigit(digit: string): string {
  const code = digit.charCodeAt(0)
  return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660)
}

/** Canonical VIN: separators removed, Arabic-Indic digits mapped to 0-9, upper case, 17 of A-Z/0-9 without I, O, Q. */
export function parseVin(raw: string): VinResult {
  const vin = raw.replace(SEPARATORS, '').replace(ARABIC_DIGITS, toLatinDigit).toUpperCase()
  if (!vin) return { ok: false, error: 'Enter a VIN.' }
  if (!VIN_PATTERN.test(vin)) return { ok: false, error: INVALID_VIN_MESSAGE }
  return { ok: true, vin }
}
