import { cx } from './cx'

/** Indeterminate progress. Announces `label` to screen readers. */
export function Spinner({ label = 'Loading', size = 'md', className }: { label?: string; size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const dims = { sm: 'h-4 w-4 border-2', md: 'h-6 w-6 border-2', lg: 'h-10 w-10 border-[3px]' }[size]
  return (
    <span role="status" className={cx('inline-flex items-center gap-2', className)}>
      <span aria-hidden="true" className={cx('animate-spin rounded-full border-current border-e-transparent', dims)} />
      <span className="sr-only">{label}</span>
    </span>
  )
}
