import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { FormAlert, TextField, Button } from '../components/ui'
import { errorMessage, serverFieldErrors } from '../lib/api'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, validateSignup, type FieldErrors } from '../lib/validation'

type Field = 'email' | 'password' | 'fullName'

export function SignupPage() {
  useDocumentTitle('Sign up')
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '', fullName: '' })
  const [errors, setErrors] = useState<FieldErrors<Field>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const clientErrors = validateSignup(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return

    setBusy(true)
    try {
      await signup({ email: form.email.trim(), password: form.password, full_name: form.fullName.trim() })
      navigate('/profile')
    } catch (error) {
      setErrors(serverFieldErrors(error, { email: 'email', password: 'password', full_name: 'fullName' }))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  const update = (field: Field) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  return (
    <section className="mx-auto w-full max-w-md">
      <h1 className="mb-6">Create an account</h1>
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
        <FormAlert message={alert} />
        <TextField label="Full name" autoComplete="name" maxLength={120} required
          value={form.fullName} onChange={update('fullName')} error={errors.fullName} />
        <TextField label="Email" type="email" autoComplete="email" maxLength={320} required
          value={form.email} onChange={update('email')} error={errors.email} />
        <TextField label="Password" type="password" autoComplete="new-password" required
          minLength={PASSWORD_MIN_LENGTH} maxLength={PASSWORD_MAX_LENGTH}
          hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
          value={form.password} onChange={update('password')} error={errors.password} />
        <Button type="submit" loading={busy}>Sign up</Button>
      </form>
      <p className="mt-4 text-sm text-ink-600">
        Already have an account? <Link className="text-brand-800 underline" to="/login">Log in</Link>
      </p>
    </section>
  )
}
