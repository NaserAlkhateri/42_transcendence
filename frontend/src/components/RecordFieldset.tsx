import type { RecordFieldsForm, RecordField } from '../lib/records'
import { CATEGORY_LABELS, type RecordCategory } from '../lib/timeline'
import type { FieldErrors } from '../lib/validation'
import { useWorkCodes } from '../lib/workCodes'
import { Alert, Checkbox, Select, Spinner, Textarea, TextField } from './ui'

export const NOTES_MAX = 1000

/** The fields a service record and a correction share: date, category, odometer, work done, private notes. */
export function RecordFieldset({ value, onChange, errors, today }: {
  value: RecordFieldsForm
  onChange: (value: RecordFieldsForm) => void
  errors: FieldErrors<RecordField | 'notes'>
  today: string
}) {
  const { codes, error: codesError } = useWorkCodes()
  const errorId = 'work-codes-error'

  function toggleCode(code: string, checked: boolean) {
    onChange({ ...value, workCodes: checked ? [...value.workCodes, code] : value.workCodes.filter((c) => c !== code) })
  }

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        <TextField label="Service date" type="date" required max={today} value={value.serviceDate} error={errors.serviceDate}
          onChange={(event) => onChange({ ...value, serviceDate: event.target.value })} />
        <Select label="Category" required placeholder="Choose…" value={value.category} error={errors.category}
          options={(Object.keys(CATEGORY_LABELS) as RecordCategory[]).map((category) => ({ value: category, label: CATEGORY_LABELS[category] }))}
          onChange={(event) => onChange({ ...value, category: event.target.value })} />
        <TextField label="Odometer reading (km)" required inputMode="numeric" autoComplete="off" value={value.odometer}
          error={errors.odometer} hint="Whole kilometres, as shown on the dashboard."
          onChange={(event) => onChange({ ...value, odometer: event.target.value })} />
      </div>

      <fieldset aria-describedby={errors.workCodes ? errorId : undefined} className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-medium text-ink-800">
          Work done <span aria-hidden="true" className="text-danger-600">*</span>
        </legend>
        {codes ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {codes.map((code) => (
              <Checkbox key={code.code} label={code.label} checked={value.workCodes.includes(code.code)}
                onChange={(event) => toggleCode(code.code, event.target.checked)} />
            ))}
          </div>
        ) : codesError ? (
          <Alert variant="danger">{codesError}</Alert>
        ) : (
          <Spinner label="Loading work codes" />
        )}
        {errors.workCodes ? <p id={errorId} className="text-sm text-danger-700">{errors.workCodes}</p> : null}
      </fieldset>

      <Textarea label="Private notes" maxLength={NOTES_MAX} value={value.notes} error={errors.notes}
        hint="Only your organisation and platform admins see notes. They never appear on public reports."
        onChange={(event) => onChange({ ...value, notes: event.target.value })} />
    </>
  )
}
