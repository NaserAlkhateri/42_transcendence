import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useAuth, type Membership } from '../../auth/auth-context'
import { RecordFieldset } from '../../components/RecordFieldset'
import { Alert, Button, Card, FormAlert, Select, TextField } from '../../components/ui'
import { errorMessage, http } from '../../lib/api'
import {
  blankRecordFields,
  recordFieldErrors,
  recordFieldsBody,
  submittingOrganizations,
  uaeToday,
  validateRecordForm,
  type OrgRecord,
  type RecordField,
  type RecordSubmission,
} from '../../lib/records'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import type { FieldErrors } from '../../lib/validation'

/** /workshop/records/new: entity staff and admins append a service record for their approved organization. */
export function NewRecordPage() {
  useDocumentTitle('Add a service record')
  const { user } = useAuth()
  const organizations = user ? submittingOrganizations(user) : []

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1>Add a service record</h1>
        <p className="text-ink-600">
          Records are permanent. A mistake is fixed with a correction, and both stay on the vehicle&apos;s history.
        </p>
      </header>
      {organizations.length > 0 ? <RecordFormCard organizations={organizations} /> : <AwaitingApproval />}
    </section>
  )
}

export function AwaitingApproval() {
  return (
    <Alert variant="info" title="Your organisation is waiting for approval">
      You can add and correct records once a platform admin approves your organisation and your membership is active.
    </Alert>
  )
}

/** Shown only when the user can submit for more than one organization. */
export function OrganizationPicker({ organizations, value, onChange, error }: {
  organizations: Membership[]; value: string; onChange: (id: string) => void; error?: string
}) {
  if (organizations.length === 1) {
    return (
      <p className="text-sm text-ink-600">
        Organisation: <span className="font-semibold text-ink-900">{organizations[0].organization_name}</span>
      </p>
    )
  }
  return (
    <Select label="Organisation" required placeholder="Choose…" value={value} error={error}
      options={organizations.map((m) => ({ value: m.organization_id, label: m.organization_name }))}
      onChange={(event) => onChange(event.target.value)} />
  )
}

/** Success notice after a record or correction is saved, with the mileage-warning explanation when flagged. */
export function SavedNotice({ record, message, onDismiss }: { record: OrgRecord; message: string; onDismiss: () => void }) {
  return (
    <div className="flex flex-col gap-3">
      <Alert variant="success" onDismiss={onDismiss}>
        {message} VIN <span className="font-mono">{record.vin}</span>.{' '}
        <Link to={`/vehicles/${record.vin}`} className="font-medium underline">View vehicle history</Link>
      </Alert>
      {record.is_mileage_flagged ? (
        <Alert variant="warning">
          The odometer reading does not fit this vehicle&apos;s earlier readings, so it was saved with a mileage
          warning. It stays visible on the public history.
        </Alert>
      ) : null}
    </div>
  )
}

function RecordFormCard({ organizations }: { organizations: Membership[] }) {
  const [organizationId, setOrganizationId] = useState(organizations.length === 1 ? organizations[0].organization_id : '')
  const [vin, setVin] = useState('')
  const [fields, setFields] = useState(() => blankRecordFields(uaeToday()))
  const [errors, setErrors] = useState<FieldErrors<RecordField | 'notes' | 'organization'>>({})
  const [alert, setAlert] = useState<string>()
  const [saved, setSaved] = useState<OrgRecord>()
  const [busy, setBusy] = useState(false)
  const today = uaeToday()

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const checked = validateRecordForm({ ...fields, vin }, today)
    const clientErrors = { ...checked.errors, ...(organizationId ? {} : { organization: 'Choose an organisation.' }) }
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0 || !checked.vin) return

    const body: RecordSubmission = { vin: checked.vin, ...recordFieldsBody(fields) }
    setBusy(true)
    try {
      setSaved(await http.post<OrgRecord>(`/organizations/${organizationId}/records`, body))
      setVin('')
      setFields(blankRecordFields(fields.serviceDate))
    } catch (failure) {
      const fieldErrors = recordFieldErrors(failure)
      setErrors(fieldErrors)
      if (Object.keys(fieldErrors).length === 0) setAlert(errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      {saved ? (
        <div className="mb-5"><SavedNotice record={saved} message="Record saved for" onDismiss={() => setSaved(undefined)} /></div>
      ) : null}
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-5">
        <FormAlert message={alert} />
        <OrganizationPicker organizations={organizations} value={organizationId} onChange={setOrganizationId} error={errors.organization} />
        <TextField label="VIN (chassis number)" required hint="17 characters. On the Mulkiya it is the Chassis No."
          autoComplete="off" spellCheck={false} maxLength={40} value={vin} error={errors.vin}
          onChange={(event) => setVin(event.target.value)} />
        <RecordFieldset value={fields} onChange={setFields} errors={errors} today={today} />
        <Button type="submit" loading={busy} className="self-start">Save record</Button>
      </form>
    </Card>
  )
}
