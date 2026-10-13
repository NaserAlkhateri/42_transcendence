import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
export function EmptyState({title, description, icon = 'search', action}: {title: string; description?: string; icon?: IconName; action?: ReactNode}) {
 return <div className="flex flex-col items-center gap-3 px-4 py-10 text-center"><Icon name={icon} size={32} className="text-ink-500" /><h3>{title}</h3>{description && <p className="max-w-md text-sm text-ink-600">{description}</p>}{action}</div>
}
