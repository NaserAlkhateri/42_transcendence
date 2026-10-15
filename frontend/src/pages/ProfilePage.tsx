import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useAuth, type User } from '../auth/auth-context'
import { FormAlert, TextField, Button } from '../components/ui'
import { api, errorMessage, serverFieldErrors } from '../lib/api'
import { STATUS_LABELS } from '../lib/organizations'
import { ROLE_LABELS } from '../lib/roles'
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  validateFullName,
  validatePasswordChange,
  type FieldErrors,
} from '../lib/validation'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export function ProfilePage({ user }: { user: User }) {
  useDocumentTitle('Your profile')
  return (
    <section className="mx-auto flex w-full max-w-md flex-col gap-10">
      <div>
        <h1 className="mb-4">Your profile</h1>
        {user.must_change_password ? (
          <FormAlert message="You are using a temporary password. Choose your own password below to continue." />
        ) : null}
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-ink-500">Email</dt>
          <dd className="text-ink-900">{user.email}</dd>
          <dt className="text-ink-500">Account type</dt>
          <dd className="text-ink-900">{ROLE_LABELS[user.effective_role]}</dd>
          <dt className="text-ink-500">Member since</dt>
          <dd className="text-ink-900">{new Date(user.created_at).toLocaleDateString()}</dd>
        </dl>
        {user.memberships.length ? (
          <div className="mt-6">
            <h2 className="mb-2">Organizations</h2>
            <ul className="flex flex-col gap-1 text-sm">
              {user.memberships.map((membership) => (
                <li key={membership.id} className="text-ink-800">
                  <Link className="text-brand-800 underline" to={`/organizations/${membership.organization_id}`}>
                    {membership.organization_name}
                  </Link>{' '}· {ROLE_LABELS[membership.role]}
                  {membership.organization_status !== 'approved' ? (
                    <span className="text-warning-700"> · {STATUS_LABELS[membership.organization_status].toLowerCase()}</span>
                  ) : null}
                  {membership.status === 'inactive' ? <span className="text-ink-500"> · inactive</span> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      {user.must_change_password ? null : <NameForm user={user} />}
      <PasswordForm />
    </section>
  )
}

function NameForm({ user }: { user: User }) {
  const { setUser } = useAuth()
  const [fullName, setFullName] = useState(user.full_name)
  const [error, setError] = useState<string>()
  const [status, setStatus] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setStatus(undefined)
    const clientError = validateFullName(fullName)
    setError(clientError)
    if (clientError) return

    setBusy(true)
    try {
      setUser(await api<User>('/me', { method: 'PATCH', body: { full_name: fullName.trim() } }))
      setStatus('Name saved.')
    } catch (failure) {
      setError(serverFieldErrors(failure, { full_name: 'fullName' }).fullName ?? errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
      <h2>Details</h2>
      <TextField label="Full name" autoComplete="name" maxLength={120} required
        value={fullName} onChange={(event) => setFullName(event.target.value)} error={error} />
      {status ? <p role="status" className="text-sm text-brand-800">{status}</p> : null}
      <Button type="submit" loading={busy}>Save name</Button>
    </form>
  )
}

type PasswordField = 'current' | 'next' | 'confirm'

function PasswordForm() {
  const { setUser } = useAuth()
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [errors, setErrors] = useState<FieldErrors<PasswordField>>({})
  const [alert, setAlert] = useState<string>()
  const [status, setStatus] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    setStatus(undefined)
    const clientErrors = validatePasswordChange(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return

    setBusy(true)
    try {
      await api<void>('/me/password', {
        method: 'POST',
        body: { current_password: form.current, new_password: form.next },
      })
      setForm({ current: '', next: '', confirm: '' })
      setStatus('Password changed. Other devices have been signed out.')
      setUser(await api<User>('/me'))
    } catch (failure) {
      setErrors(serverFieldErrors(failure, { current_password: 'current', new_password: 'next' }))
      setAlert(errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  const update = (field: PasswordField) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }))

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
      <h2>Change password</h2>
      <FormAlert message={alert} />
      <TextField label="Current password" type="password" autoComplete="current-password" required
        value={form.current} onChange={update('current')} error={errors.current} />
      <TextField label="New password" type="password" autoComplete="new-password" required
        minLength={PASSWORD_MIN_LENGTH} maxLength={PASSWORD_MAX_LENGTH}
        hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
        value={form.next} onChange={update('next')} error={errors.next} />
      <TextField label="Confirm new password" type="password" autoComplete="new-password" required
        value={form.confirm} onChange={update('confirm')} error={errors.confirm} />
      {status ? <p role="status" className="text-sm text-brand-800">{status}</p> : null}
      <Button type="submit" loading={busy}>Change password</Button>
    </form>
  )
}
