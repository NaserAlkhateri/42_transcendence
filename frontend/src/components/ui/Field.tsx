import { useId, type ReactNode } from 'react'

import { cx } from './cx'

export interface FieldRenderProps {
  id: string
  'aria-invalid'?: true
  'aria-describedby'?: string
}

interface FieldProps {
  id?: string
  label: string
  error?: string
  hint?: string
  required?: boolean
  /** Visually hide the label (it stays available to screen readers). */
  hideLabel?: boolean
  className?: string
  children: (props: FieldRenderProps) => ReactNode
}

/** Label + control + hint/error wiring shared by every form control. */
export function Field({ id: suppliedId, label, error, hint, required, hideLabel, className, children }: FieldProps) {
  const generatedId = useId()
  const id = suppliedId ?? generatedId
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className={cx('text-sm font-medium text-ink-800', hideLabel && 'sr-only')}>
        {label}
        {required ? <span aria-hidden="true" className="text-danger-600"> *</span> : null}
      </label>
      {children({ id, 'aria-invalid': error ? true : undefined, 'aria-describedby': describedBy })}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-danger-700">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-sm text-ink-500">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

