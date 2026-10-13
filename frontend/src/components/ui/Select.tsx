import type { SelectHTMLAttributes } from 'react'

import { Field } from './Field'
import { controlClass } from './control-styles'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label: string
  options: SelectOption[]
  /** Optional first option with an empty value ("All roles", "Choose…"). */
  placeholder?: string
  error?: string
  hint?: string
  hideLabel?: boolean
}

/** Native select (keyboard and screen-reader friendly) styled with the design tokens. */
export function Select({ id, label, options, placeholder, error, hint, hideLabel, required, className, ...rest }: SelectProps) {
  return (
    <Field id={id} label={label} error={error} hint={hint} required={required} hideLabel={hideLabel} className={className}>
      {(a11y) => (
        <select {...a11y} required={required} className={controlClass(!!error, 'h-10 pe-8')} {...rest}>
          {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
          {options.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}
