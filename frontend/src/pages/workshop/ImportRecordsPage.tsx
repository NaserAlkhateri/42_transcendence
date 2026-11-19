import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent, type RefObject } from 'react'
import { Link } from 'react-router-dom'

import { useAuth, type Membership } from '../../auth/auth-context'
import { Alert, Badge, Button, Card, Checkbox, Field, Modal, Spinner, Table, type TableColumn } from '../../components/ui'
import { cx } from '../../components/ui/cx'
import { errorMessage } from '../../lib/api'
import { saveBlob } from '../../lib/download'
import {
  FIELD_LABELS,
  MAX_IMPORT_ROWS,
  OPTIONAL_COLUMNS,
  REQUIRED_COLUMNS,
  TEMPLATE_FILENAME,
  checkImport,
  checkImportFile,
  csvTemplate,
  describeImportError,
  rejectedImportReport,
  runImport,
  type ImportReport,
  type ImportResult,
  type ImportRowReport,
} from '../../lib/recordImport'
import { submittingOrganizations } from '../../lib/records'
import { CATEGORY_LABELS, formatOdometer, formatTableDate } from '../../lib/timeline'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useWorkCodes, type WorkCode } from '../../lib/workCodes'
import { AwaitingApproval, OrganizationPicker } from './NewRecordPage'

/** /workshop/records/import: entity staff and admins add many records at once from a CSV or JSON file (AG-07). */
export function ImportRecordsPage() {
  useDocumentTitle('Import records')
  const { user } = useAuth()
  const organizations = user ? submittingOrganizations(user) : []

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1>Import records</h1>
        <p className="text-ink-600">
          Add many service records at once from a CSV or JSON file. Check the file first: nothing is saved until you
          import it, and imported records are permanent.
        </p>
      </header>
      {organizations.length > 0 ? <Importer organizations={organizations} /> : <AwaitingApproval />}
    </section>
  )
}

const count = new Intl.NumberFormat('en-GB')

/** "1 record", "12 records". */
function records(n: number): string {
  return `${count.format(n)} ${n === 1 ? 'record' : 'records'}`
}

function rows(n: number): string {
  return `${count.format(n)} ${n === 1 ? 'row' : 'rows'}`
}

type Failure = { title: string; message: string }

function Importer({ organizations }: { organizations: Membership[] }) {
  const { codes, error: codesError, label } = useWorkCodes()
  const [organizationId, setOrganizationId] = useState(organizations.length === 1 ? organizations[0].organization_id : '')
  const [organizationError, setOrganizationError] = useState<string>()
  const [file, setFile] = useState<File>()
  const [fileError, setFileError] = useState<string>()
  const [inputKey, setInputKey] = useState(0) // a new key empties the file input
  const fileInputRef = useRef<HTMLInputElement>(null)
  const focusFileInput = useRef(false)
  const [checking, setChecking] = useState(false)
  // The report of the last check, with the organisation it was made for: an import goes to that one.
  const [checked, setChecked] = useState<{ report: ImportReport; organizationId: string }>()
  const report = checked?.report
  // Bumped whenever the outcome is cleared, so the answer of an outdated check is dropped.
  const checkSeq = useRef(0)
  // Set when a real import was refused: the report then explains why nothing was imported.
  const [rejection, setRejection] = useState<string>()
  const [failure, setFailure] = useState<Failure>()
  const [confirming, setConfirming] = useState(false)
  const [importing, setImporting] = useState(false)
  const [imported, setImported] = useState<{ result: ImportResult; organizationId: string }>()
  const outcomeRef = useRef<HTMLDivElement>(null)

  // Move focus to the outcome of a check or an import, so keyboard and screen-reader users land on it.
  useEffect(() => {
    if (report || imported) outcomeRef.current?.focus()
  }, [report, imported])

  // After "Choose another file" the focused button is gone: continue at the new, empty file input.
  useEffect(() => {
    if (!focusFileInput.current) return
    focusFileInput.current = false
    fileInputRef.current?.focus()
  }, [inputKey])

  function clearOutcome() {
    checkSeq.current += 1
    setChecked(undefined)
    setRejection(undefined)
    setFailure(undefined)
    setImported(undefined)
  }

  function chooseOrganization(id: string) {
    setOrganizationId(id)
    setOrganizationError(undefined)
    clearOutcome() // "already recorded" depends on the organisation
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0]
    clearOutcome()
    setFile(chosen)
    const check = chosen ? checkImportFile(chosen) : undefined
    setFileError(check && !check.ok ? check.error : undefined)
  }

  function reset() {
    clearOutcome()
    setFile(undefined)
    setFileError(undefined)
    setInputKey((key) => key + 1)
  }

  async function onCheck(event: FormEvent) {
    event.preventDefault()
    clearOutcome()
    const check = checkImportFile(file)
    setFileError(check.ok ? undefined : check.error)
    setOrganizationError(organizationId ? undefined : 'Choose an organisation.')
    if (!check.ok || !file || !organizationId) return
    const seq = checkSeq.current
    setChecking(true)
    try {
      const result = await checkImport(organizationId, file, check.format)
      if (seq === checkSeq.current) setChecked({ report: result, organizationId })
    } catch (error) {
      if (seq === checkSeq.current) setFailure(describeImportError(error, 'The file could not be checked'))
    } finally {
      setChecking(false)
    }
  }

  async function onImport() {
    if (!file || !checked) return
    const target = checked.organizationId
    setImporting(true)
    try {
      const result = await runImport(target, file, checked.report.format)
      reset()
      setImported({ result, organizationId: target })
    } catch (error) {
      const refused = rejectedImportReport(error)
      if (refused) {
        setChecked({ report: refused, organizationId: target })
        setRejection(errorMessage(error))
      } else {
        setChecked(undefined)
        setFailure(describeImportError(error, 'Nothing was imported'))
      }
    } finally {
      setImporting(false)
      setConfirming(false)
    }
  }

  function downloadTemplate() {
    if (codes) saveBlob(new Blob([csvTemplate(codes)], { type: 'text/csv;charset=utf-8' }), TEMPLATE_FILENAME)
  }

  const checkedName = organizations.find((m) => m.organization_id === checked?.organizationId)?.organization_name
  const searchLink = (id: string) => {
    const params = new URLSearchParams({ sort: 'created_at' })
    if (organizations.length > 1) params.set('org', id)
    return `/workshop/records?${params}`
  }

  return (
    <>
      <Instructions codes={codes} codesError={codesError} onTemplate={downloadTemplate} />

      <Card title="Check a file">
        <form noValidate onSubmit={onCheck} className="flex flex-col gap-5">
          <OrganizationPicker organizations={organizations} value={organizationId} onChange={chooseOrganization}
            error={organizationError} disabled={checking || importing} />
          <FileInput key={inputKey} inputRef={fileInputRef} error={fileError} disabled={checking || importing}
            onChange={chooseFile} />
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={checking} disabled={importing} className="self-start">Check file</Button>
            {checking ? <p className="text-sm text-ink-600">Checking every row. This can take a few seconds.</p> : null}
          </div>
        </form>
      </Card>

      {failure ? <Alert variant="danger" title={failure.title}>{failure.message}</Alert> : null}

      <div ref={outcomeRef} tabIndex={-1} className="flex flex-col gap-6 outline-none">
        {imported ? (
          <Alert variant="success" title={`Imported ${records(imported.result.imported)} (${count.format(imported.result.flagged)} flagged)`}
            onDismiss={() => setImported(undefined)}>
            {imported.result.flagged > 0
              ? 'Flagged records carry a mileage warning on the vehicle history, because their reading does not fit the earlier readings. '
              : null}
            <Link to={searchLink(imported.organizationId)} className="font-medium underline">View the newest records</Link>
          </Alert>
        ) : null}
        {report ? (
          <ReportView report={report} rejection={rejection} label={label}
            onImport={() => setConfirming(true)} onReset={() => { focusFileInput.current = true; reset() }}
            busy={importing} />
        ) : null}
      </div>

      {report ? (
        <Modal open={confirming} title={`Import ${records(report.valid_rows)}?`} onClose={() => !importing && setConfirming(false)}
          footer={
            <>
              <Button variant="secondary" disabled={importing} onClick={() => setConfirming(false)}>Cancel</Button>
              <Button loading={importing} onClick={() => void onImport()}>Import {records(report.valid_rows)}</Button>
            </>
          }>
          <div className="flex flex-col gap-3 text-sm text-ink-700">
            <p>
              {records(report.valid_rows)} will be added to the vehicle histories
              {checkedName ? <> for <span className="font-semibold text-ink-900">{checkedName}</span></> : null}.
            </p>
            {report.flagged_rows > 0 ? (
              <p>{records(report.flagged_rows)} will be saved with a mileage warning.</p>
            ) : null}
            <p>Records are permanent. A mistake can only be fixed with a correction, and both stay on the history.</p>
          </div>
        </Modal>
      ) : null}
    </>
  )
}

function Code({ children }: { children: string }) {
  return <code dir="ltr" className="rounded bg-ink-100 px-1 font-mono text-[0.9em] text-ink-900">{children}</code>
}

function Instructions({ codes, codesError, onTemplate }: {
  codes?: WorkCode[]
  codesError?: string
  onTemplate: () => void
}) {
  const columns = (names: readonly string[]) =>
    names.map((name, index) => <span key={name}>{index > 0 ? ', ' : null}<Code>{name}</Code></span>)
  return (
    <Card title="Prepare the file">
      <div className="flex flex-col gap-4 text-sm text-ink-700">
        <ul className="flex list-disc flex-col gap-2 ps-5">
          <li>
            The first row names the columns. Required: {columns(REQUIRED_COLUMNS)}. Optional: {columns(OPTIONAL_COLUMNS)}.
            Other columns are ignored, so a CSV exported from Search records also works.
          </li>
          <li>
            <Code>service_date</Code>: YYYY-MM-DD or DD/MM/YYYY, day first (11/04/2026 is 11 April 2026).
          </li>
          <li><Code>odometer_km</Code>: whole kilometres, for example 88300 or 88,300.</li>
          <li><Code>category</Code>: maintenance or repair.</li>
          <li>
            <Code>work_codes</Code>: one or more codes from the list below, separated by &ldquo;;&rdquo;, for
            example <Code>OIL_CHANGE;AC_SERVICE</Code>.
          </li>
          <li>A JSON file is a list of objects with the same names. <Code>work_codes</Code> can be a list.</li>
          <li>
            At most 512 KB and {count.format(MAX_IMPORT_ROWS)} records per file. Save a CSV as UTF-8 (in Excel:
            &ldquo;CSV UTF-8&rdquo;).
          </li>
          <li>
            <strong className="font-semibold text-ink-900">All or nothing:</strong> if any row has an error, nothing
            is imported.
          </li>
        </ul>
        <div>
          <Button variant="secondary" icon="document" disabled={!codes} onClick={onTemplate}>Download CSV template</Button>
        </div>
        {codesError ? <Alert variant="danger" title="The work codes could not be loaded">{codesError}</Alert> : null}
        <details className="rounded-control border border-ink-200">
          <summary className="cursor-pointer px-3 py-2 font-medium text-ink-800">
            Work codes{codes ? ` (${codes.length})` : ''}
          </summary>
          <div className="px-3 pb-3">
            {codes ? (
              <Table<WorkCode> caption="Work codes for the work_codes column" rows={codes} rowKey={(code) => code.code}
                columns={[
                  { key: 'code', header: 'Code', render: (code) => <Code>{code.code}</Code> },
                  { key: 'label', header: 'Work done', render: (code) => code.label },
                ]} />
            ) : codesError ? null : (
              <Spinner label="Loading work codes" />
            )}
          </div>
        </details>
      </div>
    </Card>
  )
}

function FileInput({ inputRef, error, disabled, onChange }: {
  inputRef: RefObject<HTMLInputElement | null>
  error?: string
  disabled: boolean
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <Field label="File (CSV or JSON)" required error={error} hint="A .csv or .json file, up to 512 KB and 500 records.">
      {(a11y) => (
        <input {...a11y} ref={inputRef} type="file" accept=".csv,.json,text/csv,application/json" disabled={disabled} onChange={onChange}
          className={cx(
            'block w-full rounded-control border bg-white text-sm text-ink-700',
            'file:me-3 file:h-10 file:cursor-pointer file:border-0 file:border-e file:border-ink-300 file:bg-ink-100',
            'file:px-4 file:font-medium file:text-ink-800 hover:file:bg-ink-200 disabled:cursor-not-allowed disabled:opacity-60',
            error ? 'border-danger-600' : 'border-ink-300',
          )} />
      )}
    </Field>
  )
}

function ReportView({ report, rejection, label, onImport, onReset, busy }: {
  report: ImportReport
  rejection?: string
  label: (code: string) => string
  onImport: () => void
  onReset: () => void
  busy: boolean
}) {
  const [onlyErrors, setOnlyErrors] = useState(false)
  const hintId = useId()
  const hasErrors = report.invalid_rows > 0
  const canImport = !rejection && !hasErrors && report.valid_rows > 0
  const shown = onlyErrors && hasErrors ? report.rows.filter((row) => row.status === 'error') : report.rows

  const columns: TableColumn<ImportRowReport>[] = [
    { key: 'row', header: 'Row', render: (r) => <span dir="ltr">{r.row}</span> },
    {
      key: 'status', header: 'Status',
      render: (r) => (
        <div className="flex flex-wrap gap-1.5">
          {r.status === 'ok' ? <Badge variant="success">OK</Badge> : <Badge variant="danger">Error</Badge>}
          {r.will_be_flagged ? <Badge variant="warning" className="whitespace-nowrap">Mileage will be flagged</Badge> : null}
        </div>
      ),
    },
    { key: 'vin', header: 'VIN', render: (r) => (r.vin ? <span dir="ltr" className="font-mono">{r.vin}</span> : '—') },
    {
      key: 'service_date', header: 'Service date',
      render: (r) => (r.service_date
        ? <time dateTime={r.service_date} className="whitespace-nowrap">{formatTableDate(r.service_date)}</time>
        : '—'),
    },
    {
      key: 'odometer', header: 'Odometer',
      render: (r) => (r.odometer_km === null ? '—' : <span dir="ltr" className="whitespace-nowrap">{formatOdometer(r.odometer_km)}</span>),
    },
    { key: 'category', header: 'Category', render: (r) => (r.category ? CATEGORY_LABELS[r.category] : '—') },
    { key: 'work', header: 'Work done', render: (r) => (r.work_codes.length ? r.work_codes.map(label).join(', ') : '—') },
    {
      key: 'errors', header: 'Problems',
      render: (r) => (r.errors.length ? (
        <ul className="flex flex-col gap-1 text-danger-700">
          {r.errors.map((error, index) => (
            <li key={index}>
              <span className="font-semibold">{error.field ? FIELD_LABELS[error.field] : 'Row'}:</span> {error.message}
            </li>
          ))}
        </ul>
      ) : '—'),
    },
  ]

  return (
    <Card title={rejection ? 'Import refused' : 'Check results'}>
      <div className="flex flex-col gap-5">
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Summary term="Rows in the file" value={report.total_rows} />
          <Summary term="Ready to import" value={report.valid_rows} />
          <Summary term="With errors" value={report.invalid_rows} tone={hasErrors ? 'danger' : undefined} />
          <Summary term="Mileage will be flagged" value={report.flagged_rows} tone={report.flagged_rows ? 'warning' : undefined} />
        </dl>

        {rejection ? (
          <Alert variant="danger" title="Nothing was imported">
            {rejection} Something changed since the check, for example another import added the same service. Fix the
            rows with errors, then check the file again.
          </Alert>
        ) : hasErrors ? (
          <Alert variant="danger" title={`${rows(report.invalid_rows)} with errors`}>
            Fix them in your file, then check it again. Nothing is imported while any row has an error.
          </Alert>
        ) : (
          <Alert variant="success" title={`All ${rows(report.total_rows)} are ready to import`}>
            {report.flagged_rows > 0
              ? `${records(report.flagged_rows)} will be saved with a mileage warning, because the reading does not fit the vehicle's earlier readings.`
              : 'No mileage warnings expected.'}
          </Alert>
        )}

        {report.warnings.length > 0 ? (
          <Alert variant="warning" title="Warnings">
            <ul className="list-disc ps-5">
              {report.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </Alert>
        ) : null}

        <div className="flex flex-col gap-3">
          <Checkbox label="Show only rows with errors" checked={onlyErrors && hasErrors} disabled={!hasErrors}
            onChange={(event) => setOnlyErrors(event.target.checked)} />
          <p className="text-sm text-ink-500">
            Row numbers count the data rows: in a CSV, row 1 is the line after the header. In JSON, row 1 is the
            first item.
          </p>
          <Table<ImportRowReport> caption="Rows in the file" rows={shown} rowKey={(r) => String(r.row)} columns={columns} />
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-3">
            <Button disabled={!canImport || busy} aria-describedby={canImport ? undefined : hintId} onClick={onImport}>
              Import {records(report.valid_rows)}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={onReset}>Choose another file</Button>
          </div>
          {canImport ? null : (
            <p id={hintId} className="text-sm text-ink-600">
              {report.valid_rows === 0 && !hasErrors ? 'The file has no records to import.' : 'Fix every row with an error and check the file again before importing.'}
            </p>
          )}
        </div>
      </div>
    </Card>
  )
}

function Summary({ term, value, tone }: { term: string; value: number; tone?: 'danger' | 'warning' }) {
  return (
    <div className={cx('rounded-control border px-3 py-2',
      tone === 'danger' ? 'border-danger-200 bg-danger-50' : tone === 'warning' ? 'border-warning-200 bg-warning-50' : 'border-ink-200 bg-ink-50')}>
      <dt className="text-sm text-ink-600">{term}</dt>
      <dd className={cx('text-xl font-semibold', tone === 'danger' ? 'text-danger-700' : tone === 'warning' ? 'text-warning-700' : 'text-ink-900')}>
        {count.format(value)}
      </dd>
    </div>
  )
}
