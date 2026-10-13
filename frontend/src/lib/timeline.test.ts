import { describe, expect, it } from 'vitest'

import { workCodeLabel } from './timeline'

describe('workCodeLabel', () => {
  it.each([
    ['AC_SERVICE', 'A/C service'],
    ['BATTERY_REPLACE', 'Battery replacement'],
    ['TYRE_REPLACE', 'Tyre replacement'],
    ['AIR_FILTER', 'Air filter'],
  ])('labels the seeded UAE work code %s as %j', (code, label) => {
    expect(workCodeLabel(code)).toBe(label)
  })

  it('makes an unknown code readable instead of showing it raw', () => {
    expect(workCodeLabel('WHEEL_ALIGNMENT')).toBe('Wheel alignment')
  })
})
