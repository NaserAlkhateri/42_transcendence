import { useEffect, useState } from 'react'
import { Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { VinSearchForm } from '../components/VinSearchForm'
import { WatchVinButton } from '../components/WatchVinButton'
import { Alert, Badge, Button, Card, Checkbox, EmptyState, Select, Spinner, TextField } from '../components/ui'
import { errorMessage, http } from '../lib/api'
import {
  CATEGORY_LABELS,
  describeVehicle,
  filtersFromParams,
  filtersToParams,
  formatOdometer,
  formatServiceDate,
  workCodeLabel,
  type TimelineFilters,
  type TimelineRecord,
  type VehicleTimeline,
} from '../lib/timeline'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { parseVin } from '../lib/vin'

/** /vehicles/:vin — public, consumer-safe service history for one VIN. */
export function VehicleTimelinePage() {
  const { vin: raw = '' } = useParams()
  const location = useLocation()
  const parsed = parseVin(raw)

  if (parsed.ok && parsed.vin !== raw) {
    return <Navigate to={{ pathname: `/vehicles/${parsed.vin}`, search: location.search }} replace />
  }
  if (!parsed.ok) {
    return (
      <section className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <h1>VIN lookup</h1>
        <Alert variant="danger">{parsed.error}</Alert>
        <VinSearchForm />
      </section>
    )
  }
  return <Timeline key={parsed.vin} vin={parsed.vin} />
}

const RANGE_ERROR = "'To' must be on or after 'From'."

type LoadState = { query: string; data: VehicleTimeline } | { query: string; error: string }

function Timeline({ vin }: { vin: string }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = filtersFromParams(searchParams)
  const query = filtersToParams(filters).toString()
  const rangeError = filters.from && filters.to && filters.from > filters.to ? RANGE_ERROR : undefined
  const [state, setState] = useState<LoadState>()

  useEffect(() => {
    if (rangeError) return
    const controller = new AbortController()
    http
      .get<VehicleTimeline>(`/vehicles/${vin}/timeline${query ? `?${query}` : ''}`, { signal: controller.signal })
      .then((data) => setState({ query, data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ query, error: errorMessage(error) })
      })
    return () => controller.abort()
  }, [vin, query, rangeError])

  const current = state?.query === query ? state : undefined
  const data = current && 'data' in current ? current.data : undefined
  useDocumentTitle(`VIN ${vin}`)

  function update(patch: Partial<TimelineFilters>) {
    setSearchParams(filtersToParams({ ...filters, ...patch }), { replace: true })
  }

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <VinSearchForm />

      <header className="flex flex-col gap-1">
        <h1>{describeVehicle(data?.vehicle ?? null) ?? 'Vehicle history'}</h1>
        <p className="text-ink-600">
          VIN <span className="font-mono font-semibold text-ink-800">{vin}</span>
        </p>
      </header>

      <form aria-label="Filter records" onSubmit={(event) => event.preventDefault()} className="flex flex-wrap items-start gap-3">
        <Select
          label="Category"
          placeholder="All categories"
          options={(Object.keys(CATEGORY_LABELS) as (keyof typeof CATEGORY_LABELS)[]).map((value) => ({ value, label: CATEGORY_LABELS[value] }))}
          value={filters.category}
          onChange={(event) => update({ category: event.target.value as TimelineFilters['category'] })}
        />
        <TextField label="From" type="date" value={filters.from} max={filters.to || undefined}
          onChange={(event) => update({ from: event.target.value })} />
        <TextField label="To" type="date" value={filters.to} min={filters.from || undefined} error={rangeError}
          onChange={(event) => update({ to: event.target.value })} />
        <Select
          label="Order"
          options={[{ value: 'desc', label: 'Newest first' }, { value: 'asc', label: 'Oldest first' }]}
          value={filters.order}
          onChange={(event) => update({ order: event.target.value === 'asc' ? 'asc' : 'desc' })}
        />
        <Checkbox
          label="Only mileage warnings"
          checked={filters.flaggedOnly}
          onChange={(event) => update({ flaggedOnly: event.target.checked })}
          className="sm:mt-8"
        />
      </form>

      {rangeError ? null : !current ? (
        <div className="flex justify-center text-ink-600"><Spinner label="Loading service history" /></div>
      ) : 'error' in current ? (
        <Alert variant="danger">{current.error}</Alert>
      ) : current.data.records.length > 0 ? (
        <RecordList records={current.data.records} />
      ) : query ? (
        <EmptyState
          title="No records match these filters"
          action={<Button variant="secondary" onClick={() => setSearchParams({}, { replace: true })}>Clear filters</Button>}
        />
      ) : (
        <EmptyState
          title="No service history yet"
          description={`No approved workshop has recorded a service for VIN ${vin}. Watch it to get an alert when one does.`}
          action={<WatchVinButton vin={vin} />}
        />
      )}
    </section>
  )
}

function RecordList({ records }: { records: TimelineRecord[] }) {
  const byId = new Map(records.map((record) => [record.id, record]))
  const corrected = new Set(records.map((record) => record.corrects_record_id).filter(Boolean))

  return (
    <ol aria-label="Service history" className="flex flex-col gap-4">
      {records.map((record) => {
        const original = record.corrects_record_id ? byId.get(record.corrects_record_id) : undefined
        return (
          <li key={record.id} id={`record-${record.id}`} className="scroll-mt-6">
            <Card>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-ink-900">
                  <time dateTime={record.service_date}>{formatServiceDate(record.service_date)}</time>
                </p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant={record.category === 'repair' ? 'info' : 'brand'}>{CATEGORY_LABELS[record.category]}</Badge>
                  {record.is_mileage_flagged ? <Badge variant="warning">Mileage warning</Badge> : null}
                  {record.corrects_record_id ? <Badge variant="info">Correction</Badge> : null}
                  {corrected.has(record.id) ? <Badge>Corrected</Badge> : null}
                </div>
              </div>

              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-ink-500">Odometer</dt>
                  <dd className="font-semibold text-ink-900">{formatOdometer(record.odometer_km)}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">Workshop</dt>
                  <dd className="text-ink-800">{record.organization_name}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">Work done</dt>
                  <dd className="text-ink-800">{record.work_codes.map(workCodeLabel).join(', ')}</dd>
                </div>
              </dl>

              {record.is_mileage_flagged ? (
                <p className="mt-3 text-sm text-warning-700">
                  This reading is lower than an earlier one. It is shown as recorded, not hidden.
                </p>
              ) : null}
              {record.corrects_record_id ? (
                <p className="mt-3 text-sm text-ink-600">
                  {original ? (
                    <>Corrects the <a href={`#record-${original.id}`} className="font-medium text-brand-700 underline">{formatServiceDate(original.service_date)} record</a>.</>
                  ) : (
                    'Corrects an earlier record that the current filters hide.'
                  )}
                </p>
              ) : null}
            </Card>
          </li>
        )
      })}
    </ol>
  )
}
