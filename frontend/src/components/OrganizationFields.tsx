import { Select, TextField } from './ui'
import {
  EMIRATES,
  KIND_LABELS,
  type Emirate,
  type OrganizationField,
  type OrganizationForm,
  type OrganizationKind,
} from '../lib/organizations'
import type { FieldErrors } from '../lib/validation'

/** The four organisation fields, shared by registration, the member edit form and the admin forms. */
export function OrganizationFields({ form, errors, onChange, licenceLocked = false }: {
  form: OrganizationForm
  errors: FieldErrors<OrganizationField>
  onChange: (form: OrganizationForm) => void
  /** Approved organisations keep the licence number the admin verified. */
  licenceLocked?: boolean
}) {
  return (
    <>
      <TextField label="Business name" autoComplete="organization" maxLength={200} required
        value={form.name} error={errors.name}
        onChange={(event) => onChange({ ...form, name: event.target.value })} />
      <Select label="Type of business" required placeholder="Choose…" value={form.kind} error={errors.kind}
        options={(Object.keys(KIND_LABELS) as OrganizationKind[]).map((kind) => ({ value: kind, label: KIND_LABELS[kind] }))}
        onChange={(event) => onChange({ ...form, kind: event.target.value as OrganizationKind })} />
      <TextField label="Trade licence number" maxLength={64} required spellCheck={false}
        value={form.registrationNumber} error={errors.registrationNumber} disabled={licenceLocked}
        hint={licenceLocked ? 'Fixed after approval. Ask a platform admin if it changes.' : 'As printed on your trade licence.'}
        onChange={(event) => onChange({ ...form, registrationNumber: event.target.value })} />
      <Select label="Emirate" required placeholder="Choose…" value={form.emirate} error={errors.emirate}
        options={EMIRATES.map((emirate) => ({ value: emirate, label: emirate }))}
        onChange={(event) => onChange({ ...form, emirate: event.target.value as Emirate })} />
    </>
  )
}
