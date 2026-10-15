import { describe, expect, it } from 'vitest'

import { validatePartnerName } from './apiKeys'

describe('validatePartnerName', () => {
  it('matches the backend: 2 to 120 characters after trimming', () => {
    expect(validatePartnerName(' ')).toBeDefined()
    expect(validatePartnerName('A')).toBeDefined()
    expect(validatePartnerName('Gulf Shield Insurance')).toBeUndefined()
    expect(validatePartnerName('x'.repeat(121))).toBeDefined()
  })
})
