import { describe, expect, it } from 'vitest'

import { validateLogin, validatePasswordChange, validateSignup } from './validation'

describe('validateSignup', () => {
  it('accepts a valid signup', () => {
    expect(validateSignup({ email: 'layla@example.ae', password: 'long-enough-pw', fullName: 'Layla' })).toEqual({})
  })

  it('flags each invalid field', () => {
    const errors = validateSignup({ email: 'not-an-email', password: 'short', fullName: '   ' })
    expect(Object.keys(errors).sort()).toEqual(['email', 'fullName', 'password'])
  })

  it('caps password length like the backend', () => {
    expect(validateSignup({ email: 'a@b.ae', password: 'x'.repeat(129), fullName: 'A' }).password).toBeDefined()
  })
})

describe('validateLogin', () => {
  it('requires both fields', () => {
    expect(Object.keys(validateLogin({ email: '', password: '' })).sort()).toEqual(['email', 'password'])
  })
})

describe('validatePasswordChange', () => {
  it('rejects a mismatch and an unchanged password', () => {
    const errors = validatePasswordChange({ current: 'same-password', next: 'same-password', confirm: 'other' })
    expect(errors.next).toMatch(/different/)
    expect(errors.confirm).toMatch(/match/)
  })
})
