import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'

import { useAuth, type User } from '../../auth/auth-context'
import { MembersPanel } from '../../components/MembersPanel'
import { OrganizationFields } from '../../components/OrganizationFields'
import { Alert, Badge, Button, Card, FormAlert, Spinner } from '../../components/ui'
import { ApiError, errorMessage, http, serverFieldErrors } from '../../lib/api'
import {
  KIND_LABELS,
  ORGANIZATION_SERVER_FIELDS,
  STATUS_BADGE,
  STATUS_LABELS,
  formFromOrganization,
  formatDay,
  organizationPayload,
  validateOrganization,
  type Organization,
  type OrganizationField,
} from '../../lib/organizations'
import { ROLE_LABELS } from '../../lib/roles'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import type { FieldErrors } from '../../lib/validation'

/** /organizations/:id: members see their organisation's status; its entity admins keep the details current
 * and resubmit after a rejection. */
export function OrganizationPage() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const [organization, setOrganization] = useState<Organization>()
  const [loadError, setLoadError] = useState<string>()
  useDocumentTitle(organization?.name ?? 'Organisation')

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setOrganization(await http.get<Organization>(`/organizations/${id}`, { signal }))
      setLoadError(undefined)
    } catch (error) {
      if (signal?.aborted) return
      setLoadError(
        error instanceof ApiError && (error.status === 403 || error.status === 404)
          ? 'This organisation does not exist or you are not a member of it.'
          : errorMessage(error),
      )
    }
  }, [id])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  if (loadError) {
    return <section className="mx-auto w-full max-w-2xl"><h1 className="mb-4">Organisation</h1><Alert variant="danger">{loadError}</Alert></section>
  }
  if (!organization || !user) {
    return <div className="flex justify-center text-ink-600"><Spinner label="Loading organisation" /></div>
  }

  const membership = user.memberships.find((m) => m.organization_id === organization.id && m.status === 'active')
  const isEntityAdmin = membership?.role === 'entity_admin'

  return (
    <section className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1>{organization.name}</h1>
        <Badge variant={STATUS_BADGE[organization.status]}>{STATUS_LABELS[organization.status]}</Badge>
      </div>

      <StatusNotice organization={organization} />

      <Card title="Details">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-ink-500">Type</dt><dd>{KIND_LABELS[organization.kind]}</dd>
          <dt className="text-ink-500">Trade licence</dt><dd className="font-mono">{organization.registration_number}</dd>
          <dt className="text-ink-500">Emirate</dt><dd>{organization.emirate ?? '—'}</dd>
          <dt className="text-ink-500">Registered</dt><dd>{formatDay(organization.created_at)}</dd>
          {organization.approved_at ? <><dt className="text-ink-500">Approved</dt><dd>{formatDay(organization.approved_at)}</dd></> : null}
          {membership ? <><dt className="text-ink-500">Your role</dt><dd>{ROLE_LABELS[membership.role]}</dd></> : null}
        </dl>
      </Card>

      {isEntityAdmin ? (
        <EditOrganization key={organization.updated_at} organization={organization} onSaved={setOrganization} />
      ) : null}

      {isEntityAdmin && organization.status === 'approved' ? <MembersPanel organizationId={organization.id} /> : null}
      {isEntityAdmin && organization.status !== 'approved' ? (
        <Alert variant="info">You can add your team once a platform admin approves this organisation.</Alert>
      ) : null}
    </section>
  )
}

function StatusNotice({ organization }: { organization: Organization }) {
  if (organization.status === 'pending') {
    return (
      <Alert variant="warning" title="Awaiting review">
        A platform admin will check your trade licence. Until then your team cannot add service records.
      </Alert>
    )
  }
  if (organization.status === 'rejected') {
    return (
      <Alert variant="danger" title="Registration rejected">
        <p>{organization.rejection_reason}</p>
        <p className="mt-1">Fix the details below, then resubmit for review.</p>
      </Alert>
    )
  }
  return null
}

function EditOrganization({ organization, onSaved }: { organization: Organization; onSaved: (o: Organization) => void }) {
  const { setUser } = useAuth()
  const [form, setForm] = useState(formFromOrganization(organization))
  const [errors, setErrors] = useState<FieldErrors<OrganizationField>>({})
  const [alert, setAlert] = useState<string>()
  const [status, setStatus] = useState<string>()
  const [busy, setBusy] = useState(false)
  const isRejected = organization.status === 'rejected'

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    setStatus(undefined)
    const clientErrors = validateOrganization(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return

    setBusy(true)
    try {
      const changes = organizationPayload(form, organization)
      let saved = organization
      if (Object.keys(changes).length) saved = await http.patch<Organization>(`/organizations/${organization.id}`, changes)
      if (isRejected) saved = await http.post<Organization>(`/organizations/${organization.id}/resubmit`)
      setUser(await http.get<User>('/me'))  // organisation name/status also show in the nav and profile
      onSaved(saved)
      setStatus(isRejected ? 'Resubmitted for review.' : 'Details saved.')
    } catch (error) {
      setErrors(serverFieldErrors(error, ORGANIZATION_SERVER_FIELDS))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={isRejected ? 'Fix and resubmit' : 'Edit details'}>
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
        <FormAlert message={alert} />
        <OrganizationFields form={form} errors={errors} onChange={setForm}
          licenceLocked={organization.status === 'approved'} />
        {status ? <Alert variant="success">{status}</Alert> : null}
        <Button type="submit" loading={busy}>{isRejected ? 'Save and resubmit' : 'Save changes'}</Button>
      </form>
    </Card>
  )
}
