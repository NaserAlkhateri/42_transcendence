import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { useAuth, type EffectiveRole, type MemberRole, type Membership, type PlatformRole, type User } from '../auth/auth-context'
import { FormAlert, SubmitButton, TextField } from '../components/TextField'
import { api, errorMessage, serverFieldErrors } from '../lib/api'
import { MEMBER_ROLES, PLATFORM_ROLES, ROLE_LABELS } from '../lib/roles'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { validateEmail, validateFullName, type FieldErrors } from '../lib/validation'

type UserStatus = 'active' | 'disabled'

interface AdminUser extends User {
  status: UserStatus
  updated_at: string
}

interface UserPage {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

interface Filters {
  q: string
  role: EffectiveRole | ''
  status: UserStatus | ''
}

const PAGE_SIZE = 20
const selectClass = 'rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900'

export function AdminUsersPage() {
  useDocumentTitle('Users')
  const { user: me } = useAuth()
  const [draft, setDraft] = useState<Filters>({ q: '', role: '', status: '' })
  const [filters, setFilters] = useState<Filters>(draft)
  const [page, setPage] = useState(1)
  const [data, setData] = useState<UserPage>()
  const [loadError, setLoadError] = useState<string>()
  const [selectedId, setSelectedId] = useState<string>()

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (filters.q.trim()) params.set('q', filters.q.trim())
    if (filters.role) params.set('role', filters.role)
    if (filters.status) params.set('status', filters.status)
    try {
      setData(await api<UserPage>(`/admin/users?${params}`))
      setLoadError(undefined)
    } catch (error) {
      setLoadError(errorMessage(error))
    }
  }, [filters, page])

  useEffect(() => {
    void load()
  }, [load])

  function onSearch(event: FormEvent) {
    event.preventDefault()
    setPage(1)
    setFilters(draft)
  }

  const selected = data?.items.find((item) => item.id === selectedId)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <h1 className="text-2xl font-semibold text-slate-900">Users</h1>

      <form role="search" onSubmit={onSearch} className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <TextField label="Search by name or email" type="search" maxLength={320}
            value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} />
        </div>
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-800">
          Role
          <select className={selectClass} value={draft.role}
            onChange={(event) => setDraft({ ...draft, role: event.target.value as Filters['role'] })}>
            <option value="">All roles</option>
            {(Object.keys(ROLE_LABELS) as EffectiveRole[]).map((role) => (
              <option key={role} value={role}>{ROLE_LABELS[role]}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-800">
          Status
          <select className={selectClass} value={draft.status}
            onChange={(event) => setDraft({ ...draft, status: event.target.value as Filters['status'] })}>
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </select>
        </label>
        <button type="submit" className="rounded-md bg-slate-800 px-4 py-2 font-medium text-white hover:bg-slate-900">
          Search
        </button>
      </form>

      <FormAlert message={loadError} />

      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Users matching the current filters</caption>
          <thead className="bg-slate-100 text-slate-700">
            <tr>
              <th scope="col" className="px-3 py-2">Name</th>
              <th scope="col" className="px-3 py-2">Email</th>
              <th scope="col" className="px-3 py-2">Role</th>
              <th scope="col" className="px-3 py-2">Organizations</th>
              <th scope="col" className="px-3 py-2">Status</th>
              <th scope="col" className="px-3 py-2"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((item) => (
              <tr key={item.id} className="border-t border-slate-100">
                <td className="px-3 py-2 text-slate-900">{item.full_name}</td>
                <td className="px-3 py-2 text-slate-700">{item.email}</td>
                <td className="px-3 py-2">{ROLE_LABELS[item.effective_role]}</td>
                <td className="px-3 py-2 text-slate-700">
                  {item.memberships.map((m) => m.organization_name).join(', ') || '—'}
                </td>
                <td className="px-3 py-2">
                  <span className={item.status === 'active' ? 'text-emerald-800' : 'text-red-700'}>{item.status}</span>
                </td>
                <td className="px-3 py-2 text-right">
                  <button type="button" className="text-emerald-800 underline" onClick={() => setSelectedId(item.id)}>
                    Manage<span className="sr-only"> {item.full_name}</span>
                  </button>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-slate-500">No users match these filters.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {data ? (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm text-slate-700">
          <span>{data.total} users · page {data.page} of {pages}</span>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}
              className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-50">Previous</button>
            <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)}
              className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-50">Next</button>
          </div>
        </nav>
      ) : null}

      {selected && me ? (
        <ManageUser
          key={selected.id + selected.updated_at}
          user={selected}
          isSelf={selected.id === me.id}
          onClose={() => setSelectedId(undefined)}
          onChanged={load}
        />
      ) : null}
    </section>
  )
}

type EditField = 'fullName' | 'email'

function ManageUser({ user, isSelf, onClose, onChanged }: {
  user: AdminUser
  isSelf: boolean
  onClose: () => void
  onChanged: () => Promise<void>
}) {
  const [form, setForm] = useState({ fullName: user.full_name, email: user.email, role: user.role, status: user.status })
  const [errors, setErrors] = useState<FieldErrors<EditField>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function onSave(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const clientErrors: FieldErrors<EditField> = {}
    const nameError = validateFullName(form.fullName)
    const emailError = validateEmail(form.email)
    if (nameError) clientErrors.fullName = nameError
    if (emailError) clientErrors.email = emailError
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return

    const changes: Record<string, string> = {}
    if (form.fullName.trim() !== user.full_name) changes.full_name = form.fullName.trim()
    if (form.email.trim().toLowerCase() !== user.email) changes.email = form.email.trim()
    if (form.role !== user.role) changes.role = form.role
    if (form.status !== user.status) changes.status = form.status
    if (!Object.keys(changes).length) return

    setBusy(true)
    try {
      await api(`/admin/users/${user.id}`, { method: 'PATCH', body: changes })
      await onChanged()
    } catch (error) {
      setErrors(serverFieldErrors(error, { full_name: 'fullName', email: 'email' }))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function onDelete() {
    if (!window.confirm(`Delete ${user.email}? This removes the account, its sessions and memberships. It cannot be undone.`)) {
      return
    }
    try {
      await api(`/admin/users/${user.id}`, { method: 'DELETE' })
      onClose()
      await onChanged()
    } catch (error) {
      setAlert(errorMessage(error))
    }
  }

  return (
    <section aria-labelledby="manage-user-heading" className="rounded-md border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 id="manage-user-heading" className="text-lg font-semibold text-slate-900">Manage {user.full_name}</h2>
        <button type="button" onClick={onClose} className="text-sm text-slate-600 underline">Close</button>
      </div>

      <form noValidate onSubmit={onSave} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><FormAlert message={alert} /></div>
        <TextField label="Full name" maxLength={120} required value={form.fullName}
          onChange={(event) => setForm({ ...form, fullName: event.target.value })} error={errors.fullName} />
        <TextField label="Email" type="email" maxLength={320} required value={form.email}
          onChange={(event) => setForm({ ...form, email: event.target.value })} error={errors.email} />
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-800">
          Platform role
          <select className={selectClass} value={form.role} disabled={isSelf}
            onChange={(event) => setForm({ ...form, role: event.target.value as PlatformRole })}>
            {PLATFORM_ROLES.map((role) => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-800">
          Account status
          <select className={selectClass} value={form.status} disabled={isSelf}
            onChange={(event) => setForm({ ...form, status: event.target.value as UserStatus })}>
            <option value="active">Active</option>
            <option value="disabled">Disabled (signs the user out)</option>
          </select>
        </label>
        {isSelf ? (
          <p className="text-sm text-slate-500 sm:col-span-2">You cannot change your own role or status, or delete yourself.</p>
        ) : null}
        <div className="sm:col-span-2"><SubmitButton busy={busy}>Save changes</SubmitButton></div>
      </form>

      {user.memberships.length ? (
        <div className="mt-6">
          <h3 className="mb-2 font-semibold text-slate-900">Organization roles</h3>
          <ul className="flex flex-col gap-2">
            {user.memberships.map((membership) => (
              <MembershipRow key={membership.id} userId={user.id} membership={membership}
                onChanged={onChanged} onError={setAlert} />
            ))}
          </ul>
        </div>
      ) : null}

      {isSelf ? null : (
        <div className="mt-6 border-t border-slate-200 pt-4">
          <button type="button" onClick={() => void onDelete()}
            className="rounded-md border border-red-300 px-4 py-2 text-red-800 hover:bg-red-50">
            Delete user
          </button>
        </div>
      )}
    </section>
  )
}

function MembershipRow({ userId, membership, onChanged, onError }: {
  userId: string
  membership: Membership
  onChanged: () => Promise<void>
  onError: (message: string) => void
}) {
  async function changeRole(role: MemberRole) {
    try {
      await api(`/admin/users/${userId}/memberships/${membership.id}`, { method: 'PATCH', body: { role } })
      await onChanged()
    } catch (error) {
      onError(errorMessage(error))
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-3 text-sm">
      <span className="min-w-48 text-slate-900">
        {membership.organization_name}
        {membership.status === 'inactive' ? <span className="text-slate-500"> (inactive)</span> : null}
      </span>
      <label className="flex items-center gap-2">
        <span className="sr-only">Role in {membership.organization_name}</span>
        <select className={selectClass} value={membership.role}
          onChange={(event) => void changeRole(event.target.value as MemberRole)}>
          {MEMBER_ROLES.map((role) => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}
        </select>
      </label>
    </li>
  )
}
