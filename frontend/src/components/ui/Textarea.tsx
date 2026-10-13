import type { TextareaHTMLAttributes } from 'react'

import { Field } from './Field'
import { controlClass } from './control-styles'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  error?: string
  hint?: string
}

/** Multi-line text input. Shows a live character count when maxLength is set. */
export function Textarea({ id, label, error, hint, required, className, maxLength, value, rows = 4, ...rest }: TextareaProps) {
  const count = typeof value === 'string' && maxLength ? `${value.length}/${maxLength}` : undefined
  return (
    <Field id={id} label={label} error={error} hint={hint ?? count} required={required} className={className}>
      {(a11y) => (
        <textarea {...a11y} required={required} rows={rows} maxLength={maxLength} value={value}
          className={controlClass(!!error, 'resize-y')} {...rest} />
      )}
    </Field>
  )
}
