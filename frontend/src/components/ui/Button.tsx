import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

import { cx } from './cx'
import { Icon, type IconName } from './Icon'
import { Spinner } from './Spinner'

import { buttonClass, type ButtonVariant, type ButtonSize } from './button-styles'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  block?: boolean
  /** Shows a spinner, disables the button and sets aria-busy. */
  loading?: boolean
  icon?: IconName
  children?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, block, loading = false, icon, type = 'button', disabled, className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(buttonClass({ variant, size, block }), className)}
      {...rest}
    >
      {loading ? <Spinner size="sm" label="Working" /> : icon ? <Icon name={icon} size={size === 'sm' ? 16 : 18} /> : null}
      {children}
    </button>
  )
})

/** Square button holding only an icon; `label` is required for screen readers. */
export function IconButton({ icon, label, variant = 'ghost', size = 'md', className, ...rest }: Omit<ButtonProps, 'children' | 'icon'> & { icon: IconName; label: string }) {
  const square = { sm: 'h-8 w-8', md: 'h-10 w-10', lg: 'h-12 w-12' }[size]
  return (
    <Button aria-label={label} title={label} variant={variant} size={size} icon={icon} className={cx(square, '!px-0', className)} {...rest} />
  )
}
