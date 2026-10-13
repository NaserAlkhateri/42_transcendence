import { describe, expect, it } from 'vitest'

import { parseVin } from './vin'

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
