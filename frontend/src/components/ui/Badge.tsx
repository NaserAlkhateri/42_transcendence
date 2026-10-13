import type { HTMLAttributes } from 'react'
import { cx } from './cx'
export type BadgeVariant = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info'
const styles = {neutral: 'bg-ink-100 text-ink-700', brand: 'bg-brand-100 text-brand-800', success: 'bg-success-50 text-success-700', warning: 'bg-warning-50 text-warning-700', danger: 'bg-danger-50 text-danger-700', info: 'bg-info-50 text-info-700'}
export function Badge({variant = 'neutral', className, ...rest}: HTMLAttributes<HTMLSpanElement> & {variant?: BadgeVariant}) {
 return <span className={cx('inline-flex rounded-full px-2.5 py-1 text-xs font-semibold', styles[variant], className)} {...rest} />
}
