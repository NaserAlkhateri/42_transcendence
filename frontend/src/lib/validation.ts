// Client-side checks mirror backend/app/schemas/auth.py. The backend stays authoritative.

export const PASSWORD_MIN_LENGTH = 10
export const PASSWORD_MAX_LENGTH = 128
export const NAME_MAX_LENGTH = 120
export const EMAIL_MAX_LENGTH = 320

export type FieldErrors<K extends string> = Partial<Record<K, string>>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmail(email: string): string | undefined {
  const value = email.trim()
  if (!value) return 'Email is required.'
  if (value.length > EMAIL_MAX_LENGTH || !EMAIL_PATTERN.test(value)) return 'Enter a valid email address.'
  return undefined
}

export function validateNewPassword(password: string): string | undefined {
  if (password.length < PASSWORD_MIN_LENGTH) return `Use at least ${PASSWORD_MIN_LENGTH} characters.`
  if (password.length > PASSWORD_MAX_LENGTH) return `Use at most ${PASSWORD_MAX_LENGTH} characters.`
  return undefined
}

export function validateFullName(name: string): string | undefined {
  const value = name.trim()
  if (!value) return 'Name is required.'
  if (value.length > NAME_MAX_LENGTH) return `Use at most ${NAME_MAX_LENGTH} characters.`
  return undefined
}

export function validateSignup(input: { email: string; password: string; fullName: string }) {
  const errors: FieldErrors<'email' | 'password' | 'fullName'> = {
    email: validateEmail(input.email),
    password: validateNewPassword(input.password),
    fullName: validateFullName(input.fullName),
  }
  return dropEmpty(errors)
}

export function validateLogin(input: { email: string; password: string }) {
  return dropEmpty<'email' | 'password'>({
    email: validateEmail(input.email),
    password: input.password ? undefined : 'Password is required.',
  })
}

export function validatePasswordChange(input: { current: string; next: string; confirm: string }) {
  return dropEmpty<'current' | 'next' | 'confirm'>({
    current: input.current ? undefined : 'Current password is required.',
    next:
      validateNewPassword(input.next) ??
      (input.next === input.current ? 'Choose a password different from the current one.' : undefined),
    confirm: input.confirm === input.next ? undefined : 'Passwords do not match.',
  })
}

function dropEmpty<K extends string>(errors: FieldErrors<K>): FieldErrors<K> {
  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message)) as FieldErrors<K>
}
