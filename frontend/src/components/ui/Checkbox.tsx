import { useId, type InputHTMLAttributes } from 'react'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  description?: string
}

/** Checkbox with a clickable label and optional helper text. */
export function Checkbox({ id: suppliedId, label, description, className, ...rest }: CheckboxProps) {
  const generatedId = useId()
  const id = suppliedId ?? generatedId
  return (
    <div className={className}>
      <div className="flex items-start gap-3">
        <input
          id={id}
          type="checkbox"
          aria-describedby={description ? `${id}-desc` : undefined}
          className="mt-0.5 h-4 w-4 shrink-0 rounded border-ink-300 accent-brand-700"
          {...rest}
        />
        <div className="text-sm">
          <label htmlFor={id} className="font-medium text-ink-800">
            {label}
          </label>
          {description ? (
            <p id={`${id}-desc`} className="text-ink-500">
              {description}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
