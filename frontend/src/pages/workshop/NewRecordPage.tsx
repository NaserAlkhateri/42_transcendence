import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../auth/auth-context'
import { Alert, Button, Card, Checkbox, FormAlert, Select, Spinner, Textarea, TextField } from '../../components/ui'
import { ApiError, errorMessage, http, serverFieldErrors } from '../../lib/api'
import {
  submittingOrganizations,
  uaeToday,
  validateRecordForm,
  type OrgRecord,
  type RecordField,
  type RecordForm,
  type RecordSubmission,
} from '../../lib/records'
import { CATEGORY_LABELS, type RecordCategory } from '../../lib/timeline'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import type { FieldErrors } from '../../lib/validation'
import { useWorkCodes } from '../../lib/workCodes'

const SERVER_FIELDS: Record<string, RecordField | 'notes'> = {
  vin: 'vin', service_date: 'serviceDate', category: 'category', work_codes: 'workCodes', odometer_km: 'odometer', notes: 'notes',
}
const NOTES_MAX = 1000

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
      {organizations.length > 0 ? (
        <RecordFormCard organizations={organizations} />
      ) : (
        <Alert variant="info" title="Your organisation is waiting for approval">
          You can add records once a platform admin approves your organisation and your membership is active.
        </Alert>
      )}
    </section>
  )
}

type FormState = RecordForm & { notes: string }
const blankForm = (serviceDate: string): FormState => ({ vin: '', serviceDate, category: '', workCodes: [], odometer: '', notes: '' })

function RecordFormCard({ organizations }: { organizations: ReturnType<typeof submittingOrganizations> }) {
  const { codes, error: codesError } = useWorkCodes()
  const [organizationId, setOrganizationId] = useState(organizations.length === 1 ? organizations[0].organization_id : '')
  const [form, setForm] = useState(() => blankForm(uaeToday()))
  const [errors, setErrors] = useState<FieldErrors<RecordField | 'notes' | 'organization'>>({})
  const [alert, setAlert] = useState<string>()
  const [saved, setSaved] = useState<OrgRecord>()
  const [busy, setBusy] = useState(false)
  const today = uaeToday()

  function toggleCode(code: string, checked: boolean) {
    setForm({ ...form, workCodes: checked ? [...form.workCodes, code] : form.workCodes.filter((c) => c !== code) })
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const checked = validateRecordForm(form, today)
    const clientErrors = { ...checked.errors, ...(organizationId ? {} : { organization: 'Choose an organisation.' }) }
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0 || !checked.vin) return

    const body: RecordSubmission = {
      vin: checked.vin,
      service_date: form.serviceDate,
      category: form.category as RecordCategory,
      work_codes: form.workCodes,
      odometer_km: Number(form.odometer.trim()),
      notes: form.notes.trim() || null,
    }
    setBusy(true)
    try {
      setSaved(await http.post<OrgRecord>(`/organizations/${organizationId}/records`, body))
      setForm(blankForm(form.serviceDate))
    } catch (failure) {
      const fieldErrors = serverFieldErrors(failure, SERVER_FIELDS)
      for (const key of Object.keys(fieldErrors) as (keyof typeof fieldErrors)[]) {
        fieldErrors[key] = fieldErrors[key]?.replace(/^Value error, /, '')
      }
      if (failure instanceof ApiError && failure.code === 'invalid_vin') fieldErrors.vin = failure.message
      setErrors(fieldErrors)
      if (Object.keys(fieldErrors).length === 0) setAlert(errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      {saved ? (
        <div className="mb-5 flex flex-col gap-3">
          <Alert variant="success" onDismiss={() => setSaved(undefined)}>
            Record saved for VIN <span className="font-mono">{saved.vin}</span>.{' '}
            <Link to={`/vehicles/${saved.vin}`} className="font-medium underline">View vehicle history</Link>
          </Alert>
          {saved.is_mileage_flagged ? (
            <Alert variant="warning">
              The odometer reading does not fit this vehicle&apos;s earlier readings, so it was saved with a mileage
              warning. It stays visible on the public history.
            </Alert>
          ) : null}
        </div>
      ) : null}

      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-5">
        <FormAlert message={alert} />
        {organizations.length > 1 ? (
          <Select label="Organisation" required placeholder="Choose…" value={organizationId} error={errors.organization}
            options={organizations.map((m) => ({ value: m.organization_id, label: m.organization_name }))}
            onChange={(event) => setOrganizationId(event.target.value)} />
        ) : (
          <p className="text-sm text-ink-600">
            Organisation: <span className="font-semibold text-ink-900">{organizations[0].organization_name}</span>
          </p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="VIN (chassis number)" required hint="17 characters. On the Mulkiya it is the Chassis No."
            autoComplete="off" spellCheck={false} maxLength={40} value={form.vin} error={errors.vin}
            onChange={(event) => setForm({ ...form, vin: event.target.value })} />
          <TextField label="Service date" type="date" required max={today} value={form.serviceDate} error={errors.serviceDate}
            onChange={(event) => setForm({ ...form, serviceDate: event.target.value })} />
          <Select label="Category" required placeholder="Choose…" value={form.category} error={errors.category}
            options={(Object.keys(CATEGORY_LABELS) as RecordCategory[]).map((value) => ({ value, label: CATEGORY_LABELS[value] }))}
            onChange={(event) => setForm({ ...form, category: event.target.value })} />
          <TextField label="Odometer reading (km)" required inputMode="numeric" autoComplete="off" value={form.odometer}
            error={errors.odometer} hint="Whole kilometres, as shown on the dashboard."
            onChange={(event) => setForm({ ...form, odometer: event.target.value })} />
        </div>

        <fieldset aria-describedby={errors.workCodes ? 'work-codes-error' : undefined} className="flex flex-col gap-3">
          <legend className="mb-2 text-sm font-medium text-ink-800">
            Work done <span aria-hidden="true" className="text-danger-600">*</span>
          </legend>
          {codes ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {codes.map((code) => (
                <Checkbox key={code.code} label={code.label} checked={form.workCodes.includes(code.code)}
                  onChange={(event) => toggleCode(code.code, event.target.checked)} />
              ))}
            </div>
          ) : codesError ? (
            <Alert variant="danger">{codesError}</Alert>
          ) : (
            <Spinner label="Loading work codes" />
          )}
          {errors.workCodes ? <p id="work-codes-error" className="text-sm text-danger-700">{errors.workCodes}</p> : null}
        </fieldset>

        <Textarea label="Private notes" maxLength={NOTES_MAX} value={form.notes} error={errors.notes}
          hint="Only your organisation and platform admins see notes. They never appear on public reports."
          onChange={(event) => setForm({ ...form, notes: event.target.value })} />

        <Button type="submit" loading={busy} className="self-start">Save record</Button>
      </form>
    </Card>
  )
}
