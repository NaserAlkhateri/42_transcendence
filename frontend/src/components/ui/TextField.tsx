import type { InputHTMLAttributes } from 'react'

import { Field } from './Field'
import { controlClass } from './control-styles'

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
  hideLabel?: boolean
}

/** Labelled text input with accessible hint and error. */
export function TextField({ id, label, error, hint, hideLabel, required, className, ...input }: TextFieldProps) {
  return (
    <Field id={id} label={label} error={error} hint={hint} required={required} hideLabel={hideLabel} className={className}>
      {(a11y) => <input {...a11y} required={required} className={controlClass(!!error, 'h-10')} {...input} />}
    </Field>
  )
}
