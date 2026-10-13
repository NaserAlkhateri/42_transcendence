import { describe, expect, it } from 'vitest'

import { humanizeWorkCode } from './workCodes'

describe('humanizeWorkCode', () => {
  it('makes a code the list does not know readable instead of showing it raw', () => {
    expect(humanizeWorkCode('WHEEL_ALIGNMENT')).toBe('Wheel alignment')
  })
})
