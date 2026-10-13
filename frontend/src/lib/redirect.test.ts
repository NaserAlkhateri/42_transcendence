import { describe, expect, it } from 'vitest'

import { safeRedirect } from './redirect'

describe('safeRedirect', () => {
  it('keeps in-app paths with their query string', () => {
    expect(safeRedirect('/admin/users?page=2')).toBe('/admin/users?page=2')
  })

  it('rejects external, protocol-relative and non-string targets', () => {
    expect(safeRedirect('https://evil.example')).toBe('/profile')
    expect(safeRedirect('//evil.example')).toBe('/profile')
    expect(safeRedirect('/\\evil.example')).toBe('/profile')
    expect(safeRedirect(undefined)).toBe('/profile')
    expect(safeRedirect(42)).toBe('/profile')
  })

  it('does not loop back to the auth pages', () => {
    expect(safeRedirect('/login')).toBe('/profile')
    expect(safeRedirect('/signup')).toBe('/profile')
  })
})
