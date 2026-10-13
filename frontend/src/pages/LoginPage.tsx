import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/auth-context'
import { FormAlert, SubmitButton, TextField } from '../components/TextField'
import { errorMessage } from '../lib/api'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { safeRedirect } from '../lib/redirect'
import { validateLogin, type FieldErrors } from '../lib/validation'

type Field = 'email' | 'password'

export function LoginPage() {
  useDocumentTitle('Log in')
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = safeRedirect((location.state as { from?: unknown } | null)?.from)
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState<FieldErrors<Field>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const clientErrors = validateLogin(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return

    setBusy(true)
    try {
      await login({ email: form.email.trim(), password: form.password })
      navigate(redirectTo, { replace: true })
    } catch (error) {
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  const update = (field: Field) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  return (
    <section className="mx-auto w-full max-w-md">
      <h1 className="mb-6 text-2xl font-semibold text-slate-900">Log in</h1>
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
        <FormAlert message={alert} />
        <TextField label="Email" type="email" autoComplete="email" required
          value={form.email} onChange={update('email')} error={errors.email} />
        <TextField label="Password" type="password" autoComplete="current-password" required
          value={form.password} onChange={update('password')} error={errors.password} />
        <SubmitButton busy={busy}>Log in</SubmitButton>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        New to Sijil? <Link className="text-emerald-800 underline" to="/signup">Create an account</Link>
      </p>
    </section>
  )
}
