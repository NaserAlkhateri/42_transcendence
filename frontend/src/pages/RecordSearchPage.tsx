import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'

import { useAuth, type Membership } from '../auth/auth-context'
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  EmptyState,
  Pagination,
  Select,
  Spinner,
  Table,
  TextField,
  type TableColumn,
} from '../components/ui'
import { errorMessage, http } from '../lib/api'
import { downloadFile } from '../lib/download'
import { submittingOrganizations } from '../lib/records'
import {
  EMPTY_FILTERS,
  PAGE_SIZES,
  describeRange,
  exportApiPath,
  hasActiveFilters,
  nextSort,
  normalizeFilters,
  searchApiPath,
  searchFromParams,
  searchToParams,
  validateFilters,
  type ExportFormat,
  type RecordSearchItem,
  type RecordSearchResults,
  type SearchField,
  type SearchFilters,
  type SearchScope,
  type SearchState,
  type SortKey,
} from '../lib/recordSearch'
import { CATEGORY_LABELS, describeVehicle, formatOdometer, formatTableDate, type RecordCategory } from '../lib/timeline'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import type { FieldErrors } from '../lib/validation'
import { useWorkCodes } from '../lib/workCodes'
import { AwaitingApproval, OrganizationPicker } from './workshop/NewRecordPage'

// Which of the user's organisations to search, when they belong to more than one.
const ORGANIZATION_PARAM = 'org'
// An export of up to 5,000 records is built before the first byte arrives: allow more than the usual 15 s.
const EXPORT_TIMEOUT_MS = 60_000

/** /workshop/records (scope "organization") and /admin/records (scope "admin"): advanced record search (AG-06)
 *  with CSV/JSON export of the whole search or of selected rows (AG-07). */
export function RecordSearchPage({ scope }: { scope: SearchScope }) {
  const admin = scope === 'admin'
  const title = admin ? 'Records' : 'Search records'
  useDocumentTitle(title)
  const { user } = useAuth()
  const organizations = user && !admin ? submittingOrganizations(user) : []

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1>{title}</h1>
        <p className="text-ink-600">
          {admin
            ? 'Search, sort and page through the service records of every organisation.'
            : 'Search, sort and page through the service records your organisation has added.'}
        </p>
      </header>
      {admin ? (
        <RecordSearch scope="admin" organizations={[]} />
      ) : organizations.length > 0 ? (
        <RecordSearch scope="organization" organizations={organizations} />
      ) : (
        <AwaitingApproval />
      )}
    </section>
  )
}

type LoadResult = { key: string; data: RecordSearchResults } | { key: string; error: string }

function RecordSearch({ scope, organizations }: { scope: SearchScope; organizations: Membership[] }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchFromParams(searchParams, scope)
  const requested = searchParams.get(ORGANIZATION_PARAM)
  const organizationId =
    organizations.find((m) => m.organization_id === requested)?.organization_id ?? organizations[0]?.organization_id
  const urlErrors = validateFilters(search.filters)
  const blocked = Object.keys(urlErrors).length > 0
  const path = blocked ? undefined : searchApiPath(scope, search, organizationId)

  // Searching again with the same filters re-runs the query (e.g. to see records added since).
  const [reload, setReload] = useState(0)
  const [result, setResult] = useState<LoadResult>()
  const requestKey = path ? `${reload}:${path}` : undefined

  useEffect(() => {
    if (!path) return
    const key = `${reload}:${path}`
    const controller = new AbortController()
    http
      .get<RecordSearchResults>(path, { signal: controller.signal })
      .then((data) => setResult({ key, data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setResult({ key, error: errorMessage(error) })
      })
    return () => controller.abort()
  }, [path, reload])

  const current = result?.key === requestKey ? result : undefined
  const loading = !!requestKey && !current

  // Selected rows and export errors belong to one result set: a new search, sort or page starts empty, and so
  // does coming back to an earlier one, whose rows may have changed since.
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [exporting, setExporting] = useState<string>()
  // Keyed, so an export that fails after the user moved on is not reported on the new results.
  const [exportError, setExportError] = useState<{ key: string; message: string }>()
  const [resultKey, setResultKey] = useState(requestKey)
  if (resultKey !== requestKey) {
    setResultKey(requestKey)
    setSelectedIds([])
    setExportError(undefined)
  }

  async function exportRecords(format: ExportFormat, ids: string[] = []) {
    const key = requestKey ?? ''
    setExporting(`${ids.length > 0 ? 'selected' : 'all'}:${format}`)
    setExportError(undefined)
    try {
      await downloadFile(exportApiPath(scope, search, format, organizationId, ids), {
        fallbackName: `sijil-records.${format}`,
        timeoutMs: EXPORT_TIMEOUT_MS,
      })
    } catch (error) {
      setExportError({ key, message: errorMessage(error) })
    } finally {
      setExporting(undefined)
    }
  }

  function paramsFor(next: Partial<SearchState>, organization = organizationId): URLSearchParams {
    const params = searchToParams({ ...search, ...next }, scope)
    if (organization && organizations.length > 1 && organization !== organizations[0].organization_id) {
      params.set(ORGANIZATION_PARAM, organization)
    }
    return params
  }

  function go(next: Partial<SearchState>, organization = organizationId) {
    const params = paramsFor(next, organization)
    // Compare the request, not the address: an address that spells out defaults (?page=1) is tidied
    // but asks for the same search, which still has to run again.
    if (searchApiPath(scope, searchFromParams(params, scope), organization) === path) setReload((value) => value + 1)
    if (params.toString() !== searchParams.toString()) setSearchParams(params)
  }

  // A shared link or a shrinking result set can point past the last page: show the last page instead.
  if (current && 'data' in current) {
    const { items, total, page_size: pageSize } = current.data
    const lastPage = Math.max(1, Math.ceil(total / pageSize))
    if (items.length === 0 && total > 0 && search.page > lastPage) {
      return <Navigate replace to={{ search: `?${paramsFor({ page: lastPage })}` }} />
    }
  }

  const clear = () => go({ filters: EMPTY_FILTERS, page: 1 })
  const shown = current ?? result // keep the previous rows on screen while the next page loads
  let results: ReactNode
  if (blocked) {
    results = <p className="text-sm text-ink-600">Correct the highlighted filters, then search again.</p>
  } else if (!shown || (loading && ('error' in shown || shown.data.total === 0))) {
    results = <div className="flex justify-center text-ink-600"><Spinner label="Loading records" /></div>
  } else if ('error' in shown) {
    results = <Alert variant="danger" title="The search could not be completed">{shown.error}</Alert>
  } else if (shown.data.total === 0) {
    results = hasActiveFilters(search.filters, scope) ? (
      <EmptyState
        title="No records match these filters"
        description="Try fewer filters or a wider range."
        action={<Button variant="secondary" onClick={clear}>Clear filters</Button>}
      />
    ) : (
      <EmptyState
        title="No service records yet"
        description={scope === 'admin' ? 'No organisation has added a service record yet.' : 'Records your organisation adds will appear here.'}
      />
    )
  } else {
    const exportBusy = exporting !== undefined
    results = (
      <ResultsTable
        scope={scope}
        search={search}
        data={shown.data}
        loading={loading}
        selected={selectedIds}
        onSelect={setSelectedIds}
        actions={
          <ExportBar
            selected={selectedIds.length}
            exporting={exporting}
            disabled={exportBusy || loading}
            error={exportError && exportError.key === requestKey ? exportError.message : undefined}
            onDismissError={() => setExportError(undefined)}
            onExport={(format) => void exportRecords(format)}
            onExportSelected={(format) => void exportRecords(format, selectedIds)}
            onClearSelection={() => setSelectedIds([])}
          />
        }
        onSort={(key) => go({ ...nextSort(search, key), page: 1 })}
        onPage={(page) => go({ page })}
        onPageSize={(pageSize) => go({ pageSize, page: 1 })}
      />
    )
  }

  return (
    <>
      {scope === 'organization' ? (
        <OrganizationPicker organizations={organizations} value={organizationId ?? ''}
          onChange={(id) => id && go({ page: 1 }, id)} />
      ) : null}
      <SearchForm
        scope={scope}
        applied={search.filters}
        appliedErrors={urlErrors}
        onSearch={(filters) => go({ filters, page: 1 })}
        onClear={clear}
      />
      {results}
    </>
  )
}

const ANY_YES_NO = [{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }]

function SearchForm({ scope, applied, appliedErrors, onSearch, onClear }: {
  scope: SearchScope
  applied: SearchFilters
  appliedErrors: FieldErrors<SearchField>
  onSearch: (filters: SearchFilters) => void
  onClear: () => void
}) {
  const { codes, error: codesError } = useWorkCodes()
  const [draft, setDraft] = useState(applied)
  // undefined until the user submits: until then show the errors of the search in the address.
  const [errors, setErrors] = useState<FieldErrors<SearchField>>()
  const shownErrors = errors ?? appliedErrors

  // Back/forward and Clear change the address: show its filters in the form again.
  const appliedKey = JSON.stringify(applied)
  const [syncedKey, setSyncedKey] = useState(appliedKey)
  if (syncedKey !== appliedKey) {
    setSyncedKey(appliedKey)
    setDraft(applied)
    setErrors(undefined)
  }

  const update = (patch: Partial<SearchFilters>) => setDraft((value) => ({ ...value, ...patch }))
  const text = (key: 'vin' | 'make' | 'model' | 'staff' | 'organization' | 'yearFrom' | 'yearTo' | 'dateFrom' | 'dateTo' | 'odometerMin' | 'odometerMax') => ({
    value: draft[key],
    onChange: (event: ChangeEvent<HTMLInputElement>) => update({ [key]: event.target.value }),
  })

  function toggleCode(code: string, checked: boolean) {
    setDraft((value) => ({
      ...value,
      workCodes: checked ? [...value.workCodes, code] : value.workCodes.filter((item) => item !== code),
    }))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const filters = normalizeFilters(draft)
    const found = validateFilters(filters)
    if (Object.keys(found).length > 0) {
      setErrors(found)
      return
    }
    setErrors(undefined)
    setDraft(filters)
    onSearch(filters)
  }

  function onClearClick() {
    setDraft(EMPTY_FILTERS)
    setErrors(undefined)
    onClear()
  }

  return (
    <Card>
      <form role="search" aria-label="Search records" noValidate onSubmit={onSubmit} className="flex flex-col gap-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TextField label="VIN (chassis number)" hint="Part of the VIN is enough." dir="ltr" autoComplete="off"
            spellCheck={false} maxLength={40} error={shownErrors.vin} {...text('vin')} />
          <TextField label="Make" maxLength={64} autoComplete="off" {...text('make')} />
          <TextField label="Model" maxLength={64} autoComplete="off" {...text('model')} />
          <Select label="Category" placeholder="All categories" value={draft.category}
            options={(Object.keys(CATEGORY_LABELS) as RecordCategory[]).map((value) => ({ value, label: CATEGORY_LABELS[value] }))}
            onChange={(event) => update({ category: event.target.value as SearchFilters['category'] })} />

          <TextField label="Service date from" type="date" max={draft.dateTo || undefined} {...text('dateFrom')} />
          <TextField label="Service date to" type="date" min={draft.dateFrom || undefined} error={shownErrors.dateTo}
            {...text('dateTo')} />
          <TextField label="Minimum odometer (km)" inputMode="numeric" autoComplete="off" maxLength={9}
            error={shownErrors.odometerMin} {...text('odometerMin')} />
          <TextField label="Maximum odometer (km)" inputMode="numeric" autoComplete="off" maxLength={9}
            error={shownErrors.odometerMax} {...text('odometerMax')} />

          <TextField label="Model year from" inputMode="numeric" autoComplete="off" maxLength={4}
            error={shownErrors.yearFrom} {...text('yearFrom')} />
          <TextField label="Model year to" inputMode="numeric" autoComplete="off" maxLength={4}
            error={shownErrors.yearTo} {...text('yearTo')} />
          <TextField label="Staff name" maxLength={120} autoComplete="off" {...text('staff')} />
          {scope === 'admin' ? (
            <TextField label="Organisation name" maxLength={200} autoComplete="off" {...text('organization')} />
          ) : null}

          <Select label="Mileage flag" placeholder="Any" value={draft.flagged}
            options={[{ value: 'true', label: 'Flagged' }, { value: 'false', label: 'Not flagged' }]}
            onChange={(event) => update({ flagged: event.target.value as SearchFilters['flagged'] })} />
          <Select label="Record type" value={draft.recordType}
            options={[
              { value: 'all', label: 'All records' },
              { value: 'original', label: 'Originals only' },
              { value: 'correction', label: 'Corrections only' },
            ]}
            onChange={(event) => update({ recordType: event.target.value as SearchFilters['recordType'] })} />
          <Select label="Corrected by a later record" placeholder="Any" value={draft.corrected} options={ANY_YES_NO}
            onChange={(event) => update({ corrected: event.target.value as SearchFilters['corrected'] })} />
        </div>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-medium text-ink-800">Work done</legend>
          <p className="text-sm text-ink-500">Shows records with any of the selected items.</p>
          {codes ? (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {codes.map((code) => (
                <Checkbox key={code.code} label={code.label} checked={draft.workCodes.includes(code.code)}
                  onChange={(event) => toggleCode(code.code, event.target.checked)} />
              ))}
            </div>
          ) : codesError ? (
            <Alert variant="danger">{codesError}</Alert>
          ) : (
            <Spinner label="Loading work codes" />
          )}
        </fieldset>

        <div className="flex flex-wrap gap-3">
          <Button type="submit" icon="search">Search</Button>
          <Button variant="secondary" onClick={onClearClick}>Clear</Button>
        </div>
      </form>
    </Card>
  )
}

function ResultsTable({ scope, search, data, loading, selected, onSelect, actions, onSort, onPage, onPageSize }: {
  scope: SearchScope
  search: SearchState
  data: RecordSearchResults
  loading: boolean
  /** Ids of the selected rows on this page. */
  selected: string[]
  onSelect: (ids: string[]) => void
  actions: ReactNode
  onSort: (key: SortKey) => void
  onPage: (page: number) => void
  onPageSize: (pageSize: number) => void
}) {
  const { label } = useWorkCodes()
  const pageIds = data.items.map((r) => r.id)
  const selectedOnPage = pageIds.filter((id) => selected.includes(id)).length
  const toggle = (id: string, checked: boolean) =>
    onSelect(checked ? [...selected, id] : selected.filter((item) => item !== id))

  function sortable(key: SortKey, text: string): Pick<TableColumn<RecordSearchItem>, 'header' | 'sort'> {
    const active = search.sort === key
    return {
      header: (
        <button type="button" onClick={() => onSort(key)}
          className="inline-flex items-center gap-1 whitespace-nowrap rounded-control hover:text-ink-900">
          {text}
          <span aria-hidden="true" className={active ? 'text-brand-700' : 'text-ink-400'}>
            {active ? (search.order === 'asc' ? '▲' : '▼') : '↕'}
          </span>
        </button>
      ),
      sort: active ? (search.order === 'asc' ? 'ascending' : 'descending') : undefined,
    }
  }

  const columns: TableColumn<RecordSearchItem>[] = [
    {
      key: 'select',
      header: (
        <SelectBox label="Select all records on this page" disabled={loading}
          checked={pageIds.length > 0 && selectedOnPage === pageIds.length}
          indeterminate={selectedOnPage > 0 && selectedOnPage < pageIds.length}
          onChange={(checked) => onSelect(checked ? pageIds : [])} />
      ),
      render: (r) => (
        <SelectBox label={`Select the record for ${r.vin}, ${formatTableDate(r.service_date)}, ${formatOdometer(r.odometer_km)}`}
          disabled={loading} checked={selected.includes(r.id)} onChange={(checked) => toggle(r.id, checked)} />
      ),
    },
    {
      key: 'service_date', ...sortable('service_date', 'Service date'),
      render: (r) => <time dateTime={r.service_date} className="whitespace-nowrap">{formatTableDate(r.service_date)}</time>,
    },
    {
      key: 'vin', ...sortable('vin', 'VIN'),
      render: (r) => (
        <Link to={`/vehicles/${r.vin}`} dir="ltr" className="font-mono font-medium text-brand-700 underline">{r.vin}</Link>
      ),
    },
    { key: 'vehicle', ...sortable('make', 'Vehicle'), render: (r) => describeVehicle(r) ?? '—' },
    { key: 'category', header: 'Category', render: (r) => CATEGORY_LABELS[r.category] },
    { key: 'work', header: 'Work done', render: (r) => r.work_codes.map(label).join(', ') },
    {
      key: 'odometer', ...sortable('odometer_km', 'Odometer'),
      render: (r) => <span dir="ltr" className="whitespace-nowrap">{formatOdometer(r.odometer_km)}</span>,
    },
    scope === 'admin'
      ? {
          key: 'organization', ...sortable('organization_name', 'Organisation'),
          render: (r) => (
            <>
              {r.organization_name}
              {r.organization_id ? null : <span className="text-ink-500"> (deleted)</span>}
            </>
          ),
        }
      : { key: 'staff', header: 'Staff', render: (r) => r.staff_name },
    {
      key: 'created_at', ...sortable('created_at', 'Recorded'),
      render: (r) => <time dateTime={r.created_at} className="whitespace-nowrap">{formatTableDate(r.created_at)}</time>,
    },
    {
      key: 'status', header: 'Status',
      render: (r) => (
        <div className="flex flex-wrap gap-1.5">
          {r.is_mileage_flagged ? <Badge variant="warning" className="whitespace-nowrap">Mileage flagged</Badge> : null}
          {r.corrects_record_id ? <Badge variant="info">Correction</Badge> : null}
          {r.corrected_by_id ? <Badge>Corrected</Badge> : null}
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-ink-700">
          {describeRange(data.page, data.page_size, data.total, data.items.length)}
          {loading ? <Spinner size="sm" label="Loading records" /> : null}
        </p>
        <Select label="Records per page" className="w-40" value={String(search.pageSize)}
          options={PAGE_SIZES.map((size) => ({ value: String(size), label: String(size) }))}
          onChange={(event) => onPageSize(Number(event.target.value))} />
      </div>
      {actions}
      <div aria-busy={loading || undefined} className={loading ? 'opacity-60' : undefined}>
        <Table<RecordSearchItem> caption="Service records matching the filters" rows={data.items} rowKey={(r) => r.id}
          columns={columns} />
      </div>
      <Pagination total={data.total} pageSize={data.page_size} page={data.page} onPageChange={onPage} />
    </div>
  )
}

/** A table checkbox; the visible column needs no text, so the label is for screen readers only. */
function SelectBox({ label, checked, indeterminate = false, disabled, onChange }: {
  label: string
  checked: boolean
  /** Some but not all rows selected (the header box). */
  indeterminate?: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate
  }, [indeterminate])
  return (
    <input ref={ref} type="checkbox" aria-label={label} checked={checked} disabled={disabled}
      onChange={(event) => onChange(event.target.checked)}
      className="h-4 w-4 cursor-pointer rounded border-ink-300 align-middle accent-brand-700 disabled:cursor-not-allowed" />
  )
}

/** Export the whole search (every page) or the selected rows of this page, as CSV or JSON (AG-07). */
function ExportBar({ selected, exporting, disabled, error, onDismissError, onExport, onExportSelected, onClearSelection }: {
  selected: number
  /** "all:csv", "selected:json"… while a download runs. */
  exporting?: string
  disabled: boolean
  error?: string
  onDismissError: () => void
  onExport: (format: ExportFormat) => void
  onExportSelected: (format: ExportFormat) => void
  onClearSelection: () => void
}) {
  const selectedLabel = useId()
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div role="group" aria-label="Export these results" className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" icon="document" loading={exporting === 'all:csv'} disabled={disabled}
            onClick={() => onExport('csv')}>Export CSV</Button>
          <Button variant="secondary" size="sm" icon="document" loading={exporting === 'all:json'} disabled={disabled}
            onClick={() => onExport('json')}>Export JSON</Button>
        </div>
        <p className="text-sm text-ink-500">Every page of these results, up to 5,000 records.</p>
      </div>
      {selected > 0 ? (
        <div role="group" aria-labelledby={selectedLabel}
          className="flex flex-wrap items-center gap-2 rounded-control border border-brand-200 bg-brand-50 px-3 py-2">
          <span id={selectedLabel} className="me-1 text-sm font-medium text-brand-800">Export selected ({selected})</span>
          <Button variant="secondary" size="sm" loading={exporting === 'selected:csv'} disabled={disabled}
            onClick={() => onExportSelected('csv')}>CSV</Button>
          <Button variant="secondary" size="sm" loading={exporting === 'selected:json'} disabled={disabled}
            onClick={() => onExportSelected('json')}>JSON</Button>
          <Button variant="ghost" size="sm" disabled={disabled} onClick={onClearSelection}>Clear selection</Button>
        </div>
      ) : null}
      {error ? (
        <Alert variant="danger" title="The export could not be completed" onDismiss={onDismissError}>{error}</Alert>
      ) : null}
    </div>
  )
}
