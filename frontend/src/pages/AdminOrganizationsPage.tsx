import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { OrganizationFields } from '../components/OrganizationFields'
import { Alert, Badge, Button, Card, FormAlert, Modal, Pagination, Select, Table, Textarea, TextField } from '../components/ui'
import { errorMessage, http, serverFieldErrors } from '../lib/api'
import {
  EMIRATES,
  EMPTY_ORGANIZATION_FORM,
  KIND_LABELS,
  ORGANIZATION_SERVER_FIELDS,
  REASON_MAX_LENGTH,
  STATUS_BADGE,
  STATUS_LABELS,
  formFromOrganization,
  formatDay,
  organizationPayload,
  validateOrganization,
  validateRejectionReason,
  type AdminOrganization,
  type AdminOrganizationDetail,
  type Emirate,
  type OrganizationField,
  type OrganizationKind,
  type OrganizationPage,
  type OrganizationStatus,
} from '../lib/organizations'
import { ROLE_LABELS } from '../lib/roles'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import type { FieldErrors } from '../lib/validation'

interface Filters {
  q: string
  status: OrganizationStatus | ''
  kind: OrganizationKind | ''
  emirate: Emirate | ''
}

const PAGE_SIZE = 20

/** /admin/organizations: the registration review queue (pending first) and organisation CRUD. */
export function AdminOrganizationsPage() {
  useDocumentTitle('Organisations')
  const [draft, setDraft] = useState<Filters>({ q: '', status: '', kind: '', emirate: '' })
  const [filters, setFilters] = useState<Filters>(draft)
  const [page, setPage] = useState(1)
  const [data, setData] = useState<OrganizationPage>()
  const [loadError, setLoadError] = useState<string>()
  const [selectedId, setSelectedId] = useState<string>()
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (filters.q.trim()) params.set('q', filters.q.trim())
    if (filters.status) params.set('status', filters.status)
    if (filters.kind) params.set('kind', filters.kind)
    if (filters.emirate) params.set('emirate', filters.emirate)
    try {
      setData(await http.get<OrganizationPage>(`/admin/organizations?${params}`))
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

  const pendingOnPage = data?.items.filter((item) => item.status === 'pending').length ?? 0

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1>Organisations</h1>
        <Button onClick={() => setCreating(true)}>Add organisation</Button>
      </div>

      <form role="search" onSubmit={onSearch} className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <TextField label="Search by name or trade licence" type="search" maxLength={200}
            value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} />
        </div>
        <Select label="Status" placeholder="Any status" value={draft.status}
          options={(Object.keys(STATUS_LABELS) as OrganizationStatus[]).map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
          onChange={(event) => setDraft({ ...draft, status: event.target.value as Filters['status'] })} />
        <Select label="Type" placeholder="Any type" value={draft.kind}
          options={(Object.keys(KIND_LABELS) as OrganizationKind[]).map((k) => ({ value: k, label: KIND_LABELS[k] }))}
          onChange={(event) => setDraft({ ...draft, kind: event.target.value as Filters['kind'] })} />
        <Select label="Emirate" placeholder="Any emirate" value={draft.emirate}
          options={EMIRATES.map((e) => ({ value: e, label: e }))}
          onChange={(event) => setDraft({ ...draft, emirate: event.target.value as Filters['emirate'] })} />
        <Button type="submit">Search</Button>
      </form>

      <FormAlert message={loadError} />
      {pendingOnPage > 0 ? (
        <Alert variant="warning">{pendingOnPage} registration{pendingOnPage === 1 ? '' : 's'} awaiting review.</Alert>
      ) : null}

      <Table<AdminOrganization> caption="Organisations matching the current filters, pending first" rows={data?.items ?? []}
        rowKey={(item) => item.id}
        emptyMessage={data ? 'No organisations match these filters.' : loadError ? 'Organisations could not be loaded.' : 'Loading organisations…'}
        columns={[
          { key: 'name', header: 'Name', render: (item) => item.name },
          { key: 'licence', header: 'Trade licence', render: (item) => <span className="font-mono">{item.registration_number}</span> },
          { key: 'emirate', header: 'Emirate', render: (item) => item.emirate ?? '—' },
          { key: 'kind', header: 'Type', render: (item) => KIND_LABELS[item.kind] },
          { key: 'status', header: 'Status', render: (item) => <Badge variant={STATUS_BADGE[item.status]}>{STATUS_LABELS[item.status]}</Badge> },
          { key: 'members', header: 'Members', render: (item) => item.member_count },
          { key: 'records', header: 'Records', render: (item) => item.record_count },
          {
            key: 'actions', header: 'Actions',
            render: (item) => (
              <Button variant="ghost" size="sm" onClick={() => setSelectedId(item.id)}
                aria-label={`${item.status === 'pending' ? 'Review' : 'Manage'} ${item.name}`}>
                {item.status === 'pending' ? 'Review' : 'Manage'}
              </Button>
            ),
          },
        ]} />
      {data && <Pagination total={data.total} pageSize={data.page_size} page={page} onPageChange={setPage} />}

      {selectedId ? (
        <ManageOrganization key={selectedId} id={selectedId} onClose={() => setSelectedId(undefined)} onChanged={load} />
      ) : null}

      <CreateOrganization open={creating} onClose={() => setCreating(false)}
        onCreated={async (created) => { setCreating(false); setSelectedId(created.id); await load() }} />
    </section>
  )
}

function ManageOrganization({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => Promise<void> }) {
  const [organization, setOrganization] = useState<AdminOrganizationDetail>()
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    http.get<AdminOrganizationDetail>(`/admin/organizations/${id}`, { signal: controller.signal })
      .then(setOrganization)
      .catch((error: unknown) => { if (!controller.signal.aborted) setAlert(errorMessage(error)) })
    return () => controller.abort()
  }, [id])

  async function act(request: () => Promise<AdminOrganizationDetail | void>) {
    setAlert(undefined)
    setBusy(true)
    try {
      const updated = await request()
      if (updated) setOrganization(updated)
      await onChanged()
    } catch (error) {
      setAlert(errorMessage(error))
      throw error
    } finally {
      setBusy(false)
    }
  }

  if (!organization) {
    return <Card title="Organisation">{alert ? <Alert variant="danger">{alert}</Alert> : <p className="text-ink-600">Loading…</p>}</Card>
  }

  return (
    <Card title={`Manage ${organization.name}`}
      actions={<Button variant="ghost" size="sm" onClick={onClose}>Close</Button>}>
      <div className="flex flex-col gap-6">
        <FormAlert message={alert} />

        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={STATUS_BADGE[organization.status]}>{STATUS_LABELS[organization.status]}</Badge>
          <span className="text-sm text-ink-600">
            Registered {formatDay(organization.created_at)}
            {organization.reviewed_at ? ` · last reviewed ${formatDay(organization.reviewed_at)}` : ''}
          </span>
        </div>
        {organization.status === 'rejected' ? (
          <Alert variant="danger" title="Rejection reason">{organization.rejection_reason}</Alert>
        ) : null}

        <section aria-labelledby="review-heading" className="flex flex-col gap-3">
          <h3 id="review-heading">Review</h3>
          <p className="text-sm text-ink-600">
            Check the business name and trade licence number before approving. Approved members can add service
            records; rejecting stops new records but keeps existing history.
          </p>
          <div className="flex flex-wrap gap-3">
            {organization.status !== 'approved' ? (
              <Button loading={busy}
                onClick={() => void act(() => http.post<AdminOrganizationDetail>(`/admin/organizations/${organization.id}/approve`)).catch(() => {})}>
                Approve
              </Button>
            ) : null}
            {organization.status !== 'rejected' ? (
              <Button variant="secondary" onClick={() => setRejecting(true)}>
                {organization.status === 'approved' ? 'Withdraw approval' : 'Reject'}
              </Button>
            ) : null}
          </div>
        </section>

        <EditDetails key={organization.updated_at} organization={organization}
          onSave={(changes) => act(() => http.patch<AdminOrganizationDetail>(`/admin/organizations/${organization.id}`, changes))} />

        <section aria-labelledby="members-heading">
          <h3 id="members-heading" className="mb-2">Members</h3>
          {organization.members.length ? (
            <ul className="flex flex-col gap-1 text-sm">
              {organization.members.map((member) => (
                <li key={member.membership_id}>
                  {member.full_name} <span className="text-ink-500">({member.email})</span> · {ROLE_LABELS[member.role]}
                  {member.status === 'inactive' ? <span className="text-ink-500"> · inactive</span> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">No members yet.</p>
          )}
        </section>

        <div className="border-t border-ink-200 pt-4">
          <Button variant="danger" onClick={() => setDeleting(true)}>Delete organisation</Button>
        </div>
      </div>

      <RejectModal open={rejecting} organizationName={organization.name} busy={busy}
        onClose={() => setRejecting(false)}
        onReject={async (reason) => {
          await act(() => http.post<AdminOrganizationDetail>(`/admin/organizations/${organization.id}/reject`, { reason }))
          setRejecting(false)
        }} />

      <Modal open={deleting} title={`Delete ${organization.name}?`} onClose={() => setDeleting(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleting(false)}>Cancel</Button>
            <Button variant="danger" loading={busy} onClick={() => void act(async () => {
              await http.delete(`/admin/organizations/${organization.id}`)
              setDeleting(false)
              onClose()
            }).catch(() => setDeleting(false))}>Delete permanently</Button>
          </>
        }>
        <p>
          This removes the organisation and its {organization.member_count} membership{organization.member_count === 1 ? '' : 's'}.
          Member accounts stay. Its {organization.record_count} service record{organization.record_count === 1 ? '' : 's'} stay
          on vehicle histories under the name &quot;{organization.name}&quot;. This cannot be undone.
        </p>
      </Modal>
    </Card>
  )
}

function EditDetails({ organization, onSave }: {
  organization: AdminOrganizationDetail
  onSave: (changes: Record<string, string>) => Promise<void>
}) {
  const [form, setForm] = useState(formFromOrganization(organization))
  const [errors, setErrors] = useState<FieldErrors<OrganizationField>>({})

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const clientErrors = validateOrganization(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return
    const changes = organizationPayload(form, organization)
    if (!Object.keys(changes).length) return
    try {
      await onSave(changes)
    } catch (error) {
      setErrors(serverFieldErrors(error, ORGANIZATION_SERVER_FIELDS))
    }
  }

  return (
    <section aria-labelledby="details-heading">
      <h3 id="details-heading" className="mb-2">Details</h3>
      <form noValidate onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
        <OrganizationFields form={form} errors={errors} onChange={setForm} />
        <div className="sm:col-span-2"><Button type="submit" variant="secondary">Save details</Button></div>
      </form>
    </section>
  )
}

function RejectModal({ open, organizationName, busy, onClose, onReject }: {
  open: boolean
  organizationName: string
  busy: boolean
  onClose: () => void
  onReject: (reason: string) => Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string>()

  async function submit() {
    const problem = validateRejectionReason(reason)
    setError(problem)
    if (problem) return
    try {
      await onReject(reason.trim())
      setReason('')
    } catch (failure) {
      setError(serverFieldErrors(failure, { reason: 'reason' as const }).reason ?? errorMessage(failure))
    }
  }

  return (
    <Modal open={open} title={`Reject ${organizationName}`} onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={busy} onClick={() => void submit()}>Reject</Button>
        </>
      }>
      <Textarea label="Reason shown to the business" required maxLength={REASON_MAX_LENGTH} value={reason} error={error}
        onChange={(event) => setReason(event.target.value)}
        hint="Say what to fix, e.g. the licence number does not match the document." />
    </Modal>
  )
}

function CreateOrganization({ open, onClose, onCreated }: {
  open: boolean
  onClose: () => void
  onCreated: (organization: AdminOrganizationDetail) => Promise<void>
}) {
  const [form, setForm] = useState(EMPTY_ORGANIZATION_FORM)
  const [errors, setErrors] = useState<FieldErrors<OrganizationField>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function submit() {
    setAlert(undefined)
    const clientErrors = validateOrganization(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return
    setBusy(true)
    try {
      const created = await http.post<AdminOrganizationDetail>('/admin/organizations', organizationPayload(form))
      setForm(EMPTY_ORGANIZATION_FORM)
      await onCreated(created)
    } catch (error) {
      setErrors(serverFieldErrors(error, ORGANIZATION_SERVER_FIELDS))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} title="Add organisation" onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={busy} onClick={() => void submit()}>Add and approve</Button>
        </>
      }>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-600">Organisations you add are approved straight away and start with no members.</p>
        <FormAlert message={alert} />
        <OrganizationFields form={form} errors={errors} onChange={setForm} />
      </div>
    </Modal>
  )
}
