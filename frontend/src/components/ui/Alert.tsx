import type { ReactNode } from 'react'
import { cx } from './cx'
import { Icon, type IconName } from './Icon'
import { IconButton } from './Button'
export type AlertVariant = 'info' | 'success' | 'warning' | 'danger'
const styles = { info: 'border-info-200 bg-info-50 text-info-700', success: 'border-success-200 bg-success-50 text-success-700', warning: 'border-warning-200 bg-warning-50 text-warning-700', danger: 'border-danger-200 bg-danger-50 text-danger-700' }
const icons: Record<AlertVariant, IconName> = {info: 'info', success: 'check', warning: 'alert', danger: 'alert'}
export function Alert({variant = 'info', title, children, onDismiss, className}: {variant?: AlertVariant; title?: string; children: ReactNode; onDismiss?: () => void; className?: string}) {
 return <div role={variant === 'danger' ? 'alert' : 'status'} className={cx('flex items-start gap-3 rounded-control border p-3 text-sm', styles[variant], className)}>
  <Icon name={icons[variant]} className="shrink-0" /><div className="flex-1">{title && <p className="font-semibold">{title}</p>}{children}</div>
  {onDismiss && <IconButton icon="close" label="Dismiss alert" size="sm" onClick={onDismiss} />}
 </div>
}
export function FormAlert({message}: {message?: string}) { return message ? <Alert variant="danger">{message}</Alert> : null }
