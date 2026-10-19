import { describe, expect, it } from 'vitest'

import { INVALID_VIN_FRAGMENT_MESSAGE, parseVin, parseVinFragment, westernDigits } from './vin'

// Same cases as backend/tests/test_vin.py: the backend stays authoritative, the UI only saves a round trip.
describe('parseVin', () => {
  it.each([
    ['JTDBR32E720123456', 'JTDBR32E720123456'],
    ['jtdbr32e720123456', 'JTDBR32E720123456'],
    ['  JTD BR32E7-2012 3456 ', 'JTDBR32E720123456'],
    ['JTDBR32E7٢٠١٢٣٤٥٦', 'JTDBR32E720123456'], // Arabic-Indic digits
    ['JTDBR32E7۲۰۱۲۳۴۵۶', 'JTDBR32E720123456'], // Extended (Persian) digits
  ])('normalizes %j to %s', (raw, vin) => {
    expect(parseVin(raw)).toEqual({ ok: true, vin })
  })

  it.each([
    ['JTDBR32E72012345', 'too short'],
    ['JTDBR32E7201234567', 'too long'],
    ['JTDBR32E72O123456', 'contains O'],
    ['JTDBI32E720123456', 'contains I'],
    ['JTDBQ32E720123456', 'contains Q'],
    ['JTDBR32E72012345!', 'punctuation'],
  ])('rejects %j (%s)', (raw) => {
    expect(parseVin(raw)).toEqual({
      ok: false,
      error: 'A VIN has exactly 17 letters or digits and never contains I, O or Q.',
    })
  })

  it('asks for a VIN when the input is blank', () => {
    expect(parseVin('   ')).toEqual({ ok: false, error: 'Enter a VIN.' })
  })
})

// Mirrors the normalize_vin_fragment cases in backend/tests/test_vin.py.
describe('parseVinFragment', () => {
  it.each([
    ['', ''],
    ['   ', ''],
    ['jtn', 'JTN'],
    ['jtn-bk3 ek', 'JTNBK3EK'],
    ['٣٠١٢٣٤٥', '3012345'], // Arabic-Indic digits
    ['۳۰۱۲', '3012'], // Extended (Persian) digits
    ['JTNBK3EK6N3012345', 'JTNBK3EK6N3012345'],
  ])('normalizes %j to %j', (raw, vin) => {
    expect(parseVinFragment(raw)).toEqual({ ok: true, vin })
  })

  it.each([
    ['JTNBK3EK6N30123456', 'too long'],
    ['JTO', 'contains O'],
    ['I', 'contains I'],
    ['Q1', 'contains Q'],
    ['JTN%', 'LIKE wildcard'],
    ['JT_N', 'underscore'],
    ['JTM.HX', 'full stop'],
    ['ÉTD', 'accented letter'],
  ])('rejects %j (%s)', (raw) => {
    expect(parseVinFragment(raw)).toEqual({ ok: false, error: INVALID_VIN_FRAGMENT_MESSAGE })
  })
})

describe('westernDigits', () => {
  it('maps both Arabic-Indic digit sets and leaves everything else alone', () => {
    expect(westernDigits('٨٨٣٠٠ km')).toBe('88300 km')
    expect(westernDigits('۲۰۲۴')).toBe('2024')
    expect(westernDigits('2026-04-11')).toBe('2026-04-11')
  })
})
