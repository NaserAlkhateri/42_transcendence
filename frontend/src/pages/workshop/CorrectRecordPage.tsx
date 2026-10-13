import { useState, type FormEvent } from 'react'

import { useAuth, type Membership } from '../../auth/auth-context'
import { RecordFieldset } from '../../components/RecordFieldset'
import { Badge, Button, Card, EmptyState, FormAlert, Select, Table, TextField } from '../../components/ui'
import { errorMessage, http } from '../../lib/api'
import {
  recordFieldErrors,
  recordFieldsBody,
  recordToFields,
  submittingOrganizations,
  uaeToday,
  validateRecordFields,
  type CorrectionSubmission,
  type OrgRecord,
  type RecordField,
} from '../../lib/records'
import {
  CATEGORY_LABELS,
  CORRECTION_REASON_LABELS,
  formatOdometer,
  formatServiceDate,
  type CorrectionReason,
} from '../../lib/timeline'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import type { FieldErrors } from '../../lib/validation'
import { parseVin } from '../../lib/vin'
import { useWorkCodes } from '../../lib/workCodes'
import { AwaitingApproval, OrganizationPicker, SavedNotice } from './NewRecordPage'

/** /workshop/corrections: staff find their organization's records for a VIN and append a correction. */
export function CorrectRecordPage() {
  useDocumentTitle('Correct a record')
  const { user } = useAuth()
  const organizations = user ? submittingOrganizations(user) : []

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1>Correct a record</h1>
        <p className="text-ink-600">
          A correction is added next to the original. Both stay on the vehicle&apos;s history and in its report, clearly
          labelled. Only your organisation&apos;s own records can be corrected.
        </p>
      </header>
      {organizations.length > 0 ? <Corrections organizations={organizations} /> : <AwaitingApproval />}
    </section>
  )
}

function Corrections({ organizations }: { organizations: Membership[] }) {
  const { label } = useWorkCodes()
  const [organizationId, setOrganizationId] = useState(organizations.length === 1 ? organizations[0].organization_id : '')
  const [vinInput, setVinInput] = useState('')
  const [searchError, setSearchError] = useState<string>()
  const [found, setFound] = useState<{ vin: string; records: OrgRecord[] }>()
  const [editing, setEditing] = useState<OrgRecord>()
  const [saved, setSaved] = useState<OrgRecord>()

  async function load(vin: string, organization = organizationId) {
    setFound({ vin, records: await http.get<OrgRecord[]>(`/organizations/${organization}/records?vin=${vin}`) })
  }

  async function onSearch(event: FormEvent) {
    event.preventDefault()
    setSaved(undefined)
    setEditing(undefined)
    const vin = parseVin(vinInput)
    if (!organizationId) return setSearchError('Choose an organisation.')
    if (!vin.ok) return setSearchError(vin.error)
    setSearchError(undefined)
    try {
      await load(vin.vin)
    } catch (failure) {
      setSearchError(errorMessage(failure))
    }
  }

  async function onSaved(correction: OrgRecord) {
    setEditing(undefined)
    setSaved(correction)
    await load(correction.vin).catch(() => undefined) // the list refreshes; the success notice stays either way
  }

  return (
    <>
      <Card>
        <form role="search" aria-label="Find records" noValidate onSubmit={onSearch} className="flex flex-col gap-4">
          <OrganizationPicker organizations={organizations} value={organizationId}
            onChange={(id) => { setOrganizationId(id); setFound(undefined) }} />
          <div className="flex flex-wrap items-start gap-3">
            <TextField label="VIN (chassis number)" required hint="17 characters. On the Mulkiya it is the Chassis No."
              autoComplete="off" spellCheck={false} maxLength={40} value={vinInput} error={searchError}
              onChange={(event) => setVinInput(event.target.value)} className="min-w-64 flex-1" />
            <Button type="submit" icon="search" variant="secondary" className="sm:mt-6.5">Find records</Button>
          </div>
        </form>
      </Card>

      {saved ? <SavedNotice record={saved} message="Correction saved. Both records stay on the history of" onDismiss={() => setSaved(undefined)} /> : null}

      {editing ? (
        <CorrectionForm organizationId={organizationId} original={editing} onCancel={() => setEditing(undefined)} onSaved={onSaved} />
      ) : null}

      {found ? (
        found.records.length === 0 ? (
          <EmptyState title="Your organisation has no records for this VIN." />
        ) : (
          <Table<OrgRecord>
            caption={`Your organisation's records for this VIN (${found.vin})`}
            rows={found.records}
            rowKey={(record) => record.id}
            columns={[
              { key: 'date', header: 'Date', render: (r) => formatServiceDate(r.service_date) },
              { key: 'category', header: 'Category', render: (r) => CATEGORY_LABELS[r.category] },
              { key: 'work', header: 'Work done', render: (r) => r.work_codes.map(label).join(', ') },
              { key: 'odometer', header: 'Odometer', render: (r) => formatOdometer(r.odometer_km) },
              {
                key: 'state', header: 'Status',
                render: (r) => (
                  <div className="flex flex-wrap items-center gap-2">
                    {r.correction_reason ? <Badge variant="info">Correction · {CORRECTION_REASON_LABELS[r.correction_reason]}</Badge> : null}
                    {r.is_mileage_flagged ? <Badge variant="warning">Mileage warning</Badge> : null}
                    {r.corrected_by_id ? (
                      <Badge>Corrected</Badge>
                    ) : (
                      <Button variant="ghost" size="sm" aria-label={`Correct the ${formatServiceDate(r.service_date)} record`}
                        onClick={() => { setSaved(undefined); setEditing(r) }}>
                        Correct
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )
      ) : null}
    </>
  )
}

function CorrectionForm({ organizationId, original, onCancel, onSaved }: {
  organizationId: string; original: OrgRecord; onCancel: () => void; onSaved: (correction: OrgRecord) => void
}) {
  const [reason, setReason] = useState('')
  const [fields, setFields] = useState(() => recordToFields(original))
  const [errors, setErrors] = useState<FieldErrors<RecordField | 'notes' | 'reason'>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)
  const today = uaeToday()

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const clientErrors = { ...validateRecordFields(fields, today), ...(reason ? {} : { reason: 'Choose what the correction fixes.' }) }
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0) return

    const body: CorrectionSubmission = { correction_reason: reason as CorrectionReason, ...recordFieldsBody(fields) }
    setBusy(true)
    try {
      onSaved(await http.post<OrgRecord>(`/organizations/${organizationId}/records/${original.id}/corrections`, body))
    } catch (failure) {
      const fieldErrors = recordFieldErrors(failure)
      setErrors(fieldErrors)
      if (Object.keys(fieldErrors).length === 0) setAlert(errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={`Correct the ${formatServiceDate(original.service_date)} record`}>
      <p className="mb-4 text-sm text-ink-600">
        The form starts with the original values ({formatOdometer(original.odometer_km)}). Change what was wrong.
      </p>
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-5">
        <FormAlert message={alert} />
        <Select label="What does this correction fix?" required placeholder="Choose…" value={reason} error={errors.reason}
          options={(Object.keys(CORRECTION_REASON_LABELS) as CorrectionReason[]).map((value) => ({ value, label: CORRECTION_REASON_LABELS[value] }))}
          onChange={(event) => setReason(event.target.value)} />
        <RecordFieldset value={fields} onChange={setFields} errors={errors} today={today} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" loading={busy}>Save correction</Button>
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}
