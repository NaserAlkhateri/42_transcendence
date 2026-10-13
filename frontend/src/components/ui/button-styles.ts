import { cx } from './cx'
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-brand-700 text-white hover:bg-brand-800 active:bg-brand-900',
  secondary: 'border border-ink-300 bg-white text-ink-800 hover:bg-ink-100',
  ghost: 'text-ink-700 hover:bg-ink-100',
  danger: 'bg-danger-600 text-white hover:bg-danger-700',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 gap-1.5 px-3 text-sm',
  md: 'h-10 gap-2 px-4 text-sm',
  lg: 'h-12 gap-2 px-5 text-base',
}

/** Shared look for <Button> and link-styled buttons (e.g. a router <Link className={buttonClass()}>). */
export function buttonClass({ variant = 'primary', size = 'md', block = false }: { variant?: ButtonVariant; size?: ButtonSize; block?: boolean } = {}) {
  return cx(
    'inline-flex items-center justify-center rounded-control font-medium transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-60',
    VARIANTS[variant],
    SIZES[size],
    block && 'w-full',
  )
}

