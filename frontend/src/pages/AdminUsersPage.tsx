import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { useAuth, type EffectiveRole, type MemberRole, type Membership, type PlatformRole, type User } from '../auth/auth-context'
import { Alert, FormAlert, TextField, Button, Badge, Modal, Select, Table, Pagination } from '../components/ui'
import { api, errorMessage, http, serverFieldErrors } from '../lib/api'
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
      const result = await api<UserPage>(`/admin/users?${params}`)
      const lastPage = Math.max(1, Math.ceil(result.total / result.page_size))
      if (page > lastPage) {
        setPage(lastPage)  // e.g. the only user on the last page was deleted: show the new last page
        return
      }
      setData(result)
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

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <h1>Users</h1>

      <form role="search" onSubmit={onSearch} className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <TextField label="Search by name or email" type="search" maxLength={320}
            value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} />
        </div>
        <Select label="Role" placeholder="All roles" options={(Object.keys(ROLE_LABELS) as EffectiveRole[]).map(role=>({value:role,label:ROLE_LABELS[role]}))} value={draft.role} onChange={event=>setDraft({...draft,role:event.target.value as Filters['role']})} />
        <Select label="Status" placeholder="Any status" options={[{value:'active',label:'Active'},{value:'disabled',label:'Disabled'}]} value={draft.status} onChange={event=>setDraft({...draft,status:event.target.value as Filters['status']})} />
        <Button type="submit">Search</Button>
      </form>

      <FormAlert message={loadError} />

      <Table<AdminUser> caption="Users matching the current filters" rows={data?.items ?? []} rowKey={item=>item.id} emptyMessage={data ? 'No users match these filters.' : loadError ? 'Users could not be loaded.' : 'Loading users…'} columns={[
        {key:'name',header:'Name',render:item=>item.full_name},
        {key:'email',header:'Email',render:item=>item.email},
        {key:'role',header:'Role',render:item=>ROLE_LABELS[item.effective_role]},
        {key:'organizations',header:'Organizations',render:item=>item.memberships.map(m=>m.organization_name).join(', ') || '—'},
        {key:'status',header:'Status',render:item=><Badge variant={item.status === 'active' ? 'success' : 'danger'}>{item.status}</Badge>},
        {key:'actions',header:'Actions',render:item=><Button variant="ghost" size="sm" onClick={()=>setSelectedId(item.id)} aria-label={`Manage ${item.full_name}`}>Manage</Button>},
      ]} />
      {data && <Pagination total={data.total} pageSize={data.page_size} page={page} onPageChange={setPage} />}

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
    <section aria-labelledby="manage-user-heading" className="rounded-control border border-ink-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 id="manage-user-heading">Manage {user.full_name}</h2>
        <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
      </div>

      <form noValidate onSubmit={onSave} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><FormAlert message={alert} /></div>
        <TextField label="Full name" maxLength={120} required value={form.fullName}
          onChange={(event) => setForm({ ...form, fullName: event.target.value })} error={errors.fullName} />
        <TextField label="Email" type="email" maxLength={320} required value={form.email}
          onChange={(event) => setForm({ ...form, email: event.target.value })} error={errors.email} />
        <Select label="Platform role" options={PLATFORM_ROLES.map(role=>({value:role,label:ROLE_LABELS[role]}))} value={form.role} disabled={isSelf} onChange={event=>setForm({...form,role:event.target.value as PlatformRole})} />
        <Select label="Account status" options={[{value:'active',label:'Active'},{value:'disabled',label:'Disabled (signs the user out)'}]} value={form.status} disabled={isSelf} onChange={event=>setForm({...form,status:event.target.value as UserStatus})} />
        {isSelf ? (
          <p className="text-sm text-ink-500 sm:col-span-2">You cannot change your own role or status, or delete yourself.</p>
        ) : null}
        <div className="sm:col-span-2"><Button type="submit" loading={busy}>Save changes</Button></div>
      </form>

      {user.memberships.length ? (
        <div className="mt-6">
          <h3 className="mb-2 font-semibold text-ink-900">Organization roles</h3>
          <ul className="flex flex-col gap-2">
            {user.memberships.map((membership) => (
              <MembershipRow key={membership.id} userId={user.id} membership={membership}
                onChanged={onChanged} onError={setAlert} />
            ))}
          </ul>
        </div>
      ) : null}

      {isSelf ? null : (
        <div className="mt-6 flex flex-col gap-4 border-t border-ink-200 pt-4">
          <ResetPassword user={user} onError={setAlert} />
          <div>
            <Button variant="danger" onClick={() => void onDelete()}>
              Delete user
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}

/** Platform admins give a locked-out user a temporary password (there is no email reset). */
function ResetPassword({ user, onError }: { user: AdminUser; onError: (message: string) => void }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [temporary, setTemporary] = useState<string>()

  async function reset() {
    setBusy(true)
    try {
      setTemporary((await http.post<{ temporary_password: string }>(`/admin/users/${user.id}/reset-password`)).temporary_password)
    } catch (error) {
      onError(errorMessage(error))
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {temporary ? (
        <Alert variant="success" title={`Temporary password for ${user.email}`} onDismiss={() => setTemporary(undefined)}>
          <p>Give it to them in person. It is shown only once; they must choose their own password when they sign in.</p>
          <p className="mt-2 font-mono select-all" data-testid="reset-temporary-password">{temporary}</p>
        </Alert>
      ) : null}
      <div>
        <Button variant="secondary" onClick={() => setConfirming(true)}>Reset password</Button>
      </div>
      <Modal open={confirming} title={`Reset the password of ${user.full_name}?`} onClose={() => setConfirming(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
            <Button loading={busy} onClick={() => void reset()}>Reset password</Button>
          </>
        }>
        <p>They are signed out everywhere and get a temporary password, which you will see once.</p>
      </Modal>
    </div>
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
      <span className="min-w-48 text-ink-900">
        {membership.organization_name}
        {membership.status === 'inactive' ? <span className="text-ink-500"> (inactive)</span> : null}
      </span>
      <Select label={`Role in ${membership.organization_name}`} hideLabel options={MEMBER_ROLES.map(role=>({value:role,label:ROLE_LABELS[role]}))} value={membership.role} onChange={event=>void changeRole(event.target.value as MemberRole)} />
    </li>
  )
}
