import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { useAuth, type MemberRole, type User } from '../auth/auth-context'
import { Alert, Badge, Button, Card, FormAlert, Modal, Select, Table, TextField } from './ui'
import { errorMessage, http, serverFieldErrors } from '../lib/api'
import type { OrganizationMember } from '../lib/organizations'
import { MEMBER_ROLES, ROLE_LABELS } from '../lib/roles'
import { validateEmail, validateFullName, type FieldErrors } from '../lib/validation'

const ROLE_OPTIONS = MEMBER_ROLES.map((role) => ({ value: role, label: ROLE_LABELS[role] }))

/** Members of one organisation, for its entity admins and for platform admins (NA-04). The API decides
 * who may do what; it also keeps at least one active entity admin and refuses unapproved organisations. */
export function MembersPanel({ organizationId, onChanged }: { organizationId: string; onChanged?: () => void }) {
  const { user: me, setUser } = useAuth()
  const [members, setMembers] = useState<OrganizationMember[]>()
  const [alert, setAlert] = useState<string>()
  const [removing, setRemoving] = useState<OrganizationMember>()
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setMembers(await http.get<OrganizationMember[]>(`/organizations/${organizationId}/members`))
    } catch (error) {
      setAlert(errorMessage(error))
    }
  }, [organizationId])

  useEffect(() => {
    void load()
  }, [load])

  /** Run a change, then refresh the list, the caller, and the signed-in user if their own membership moved. */
  async function change(request: () => Promise<unknown>, affectedUserId?: string) {
    setAlert(undefined)
    setBusy(true)
    try {
      await request()
      await load()
      onChanged?.()
      if (affectedUserId && affectedUserId === me?.id) setUser(await http.get<User>('/me'))
      return true
    } catch (error) {
      setAlert(errorMessage(error))
      return false
    } finally {
      setBusy(false)
    }
  }

  const base = `/organizations/${organizationId}/members`

  return (
    <Card title="Members">
      <div className="flex flex-col gap-6">
        <FormAlert message={alert} />
        <Table<OrganizationMember> caption="Organisation members" rows={members ?? []} rowKey={(m) => m.membership_id}
          emptyMessage={members ? 'No members yet.' : 'Loading members…'}
          columns={[
            { key: 'name', header: 'Name', render: (m) => <>{m.full_name}{m.user_id === me?.id ? <span className="text-ink-500"> (you)</span> : null}</> },
            { key: 'email', header: 'Email', render: (m) => m.email },
            {
              key: 'role', header: 'Role',
              render: (m) => (
                <Select label={`Role of ${m.full_name}`} hideLabel options={ROLE_OPTIONS} value={m.role} disabled={busy}
                  onChange={(event) => void change(
                    () => http.patch(`${base}/${m.membership_id}`, { role: event.target.value as MemberRole }), m.user_id)} />
              ),
            },
            {
              key: 'status', header: 'Status',
              render: (m) => <Badge variant={m.status === 'active' ? 'success' : 'neutral'}>{m.status === 'active' ? 'Active' : 'Inactive'}</Badge>,
            },
            {
              key: 'actions', header: 'Actions',
              render: (m) => (
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size="sm" disabled={busy}
                    aria-label={`${m.status === 'active' ? 'Deactivate' : 'Reactivate'} ${m.full_name}`}
                    onClick={() => void change(() => http.patch(`${base}/${m.membership_id}`, {
                      status: m.status === 'active' ? 'inactive' : 'active',
                    }), m.user_id)}>
                    {m.status === 'active' ? 'Deactivate' : 'Reactivate'}
                  </Button>
                  <Button variant="ghost" size="sm" disabled={busy} aria-label={`Remove ${m.full_name}`}
                    onClick={() => setRemoving(m)}>
                    Remove
                  </Button>
                </div>
              ),
            },
          ]} />

        <div className="grid gap-6 md:grid-cols-2">
          <AddExistingMember base={base} onAdded={() => change(async () => {})} />
          <CreateStaffAccount base={base} onCreated={() => change(async () => {})} />
        </div>
      </div>

      <Modal open={!!removing} title={removing ? `Remove ${removing.full_name}?` : 'Remove member'} onClose={() => setRemoving(undefined)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRemoving(undefined)}>Cancel</Button>
            <Button variant="danger" loading={busy} onClick={() => {
              const target = removing
              if (!target) return
              void change(() => http.delete(`${base}/${target.membership_id}`), target.user_id).then(() => setRemoving(undefined))
            }}>Remove</Button>
          </>
        }>
        <p>
          They lose access to this organisation straight away. Their account stays, and records they added keep their name.
        </p>
      </Modal>
    </Card>
  )
}

type AddField = 'email'

function AddExistingMember({ base, onAdded }: { base: string; onAdded: () => Promise<boolean> }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<MemberRole>('entity_staff')
  const [errors, setErrors] = useState<FieldErrors<AddField>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const problem = validateEmail(email)
    setErrors(problem ? { email: problem } : {})
    if (problem) return
    setBusy(true)
    try {
      await http.post(base, { email: email.trim(), role })
      setEmail('')
      await onAdded()
    } catch (error) {
      setErrors(serverFieldErrors(error, { email: 'email' as const }))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-3" aria-labelledby="add-member-heading">
      <h3 id="add-member-heading">Add someone with an account</h3>
      <FormAlert message={alert} />
      <TextField label="Their account email" type="email" autoComplete="off" maxLength={320} required
        value={email} error={errors.email} onChange={(event) => setEmail(event.target.value)} />
      <Select label="Their role" options={ROLE_OPTIONS} value={role} onChange={(event) => setRole(event.target.value as MemberRole)} />
      <Button type="submit" variant="secondary" loading={busy}>Add member</Button>
    </form>
  )
}

type StaffField = 'email' | 'fullName'

interface Created {
  member: OrganizationMember
  temporary_password: string
}

function CreateStaffAccount({ base, onCreated }: { base: string; onCreated: () => Promise<boolean> }) {
  const [form, setForm] = useState({ fullName: '', email: '', role: 'entity_staff' as MemberRole })
  const [errors, setErrors] = useState<FieldErrors<StaffField>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<Created>()

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    setCreated(undefined)
    const clientErrors: FieldErrors<StaffField> = {}
    const nameError = validateFullName(form.fullName)
    const emailError = validateEmail(form.email)
    if (nameError) clientErrors.fullName = nameError
    if (emailError) clientErrors.email = emailError
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return
    setBusy(true)
    try {
      const result = await http.post<Created>(`${base}/staff-accounts`, {
        full_name: form.fullName.trim(), email: form.email.trim(), role: form.role,
      })
      setCreated(result)
      setForm({ fullName: '', email: '', role: 'entity_staff' })
      await onCreated()
    } catch (error) {
      setErrors(serverFieldErrors(error, { email: 'email', full_name: 'fullName' }))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-3" aria-labelledby="create-staff-heading">
      <h3 id="create-staff-heading">Create a staff account</h3>
      <FormAlert message={alert} />
      {created ? (
        <Alert variant="success" title={`Account created for ${created.member.full_name}`}>
          <p>Give them this temporary password in person. It is shown only once; they must change it when they first sign in.</p>
          <p className="mt-2">
            Email: <span className="font-mono">{created.member.email}</span><br />
            Temporary password: <span className="font-mono select-all" data-testid="temporary-password">{created.temporary_password}</span>
          </p>
        </Alert>
      ) : null}
      <TextField label="Full name" autoComplete="off" maxLength={120} required
        value={form.fullName} error={errors.fullName} onChange={(event) => setForm({ ...form, fullName: event.target.value })} />
      <TextField label="Work email" type="email" autoComplete="off" maxLength={320} required
        value={form.email} error={errors.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
      <Select label="Role of the new account" options={ROLE_OPTIONS} value={form.role}
        onChange={(event) => setForm({ ...form, role: event.target.value as MemberRole })} />
      <Button type="submit" variant="secondary" loading={busy}>Create account</Button>
    </form>
  )
}
