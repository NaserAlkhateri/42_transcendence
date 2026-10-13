import { useId, type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './cx'
export function Card({title, actions, children, className, ...rest}: Omit<HTMLAttributes<HTMLElement>, 'title'> & {title?: string; actions?: ReactNode}) {
 const id = useId()
 return <section {...rest} aria-labelledby={title ? id : undefined} className={cx('rounded-card border border-ink-200 bg-white p-5 shadow-card', className)}>
  {(title || actions) && <div className="mb-4 flex items-center justify-between gap-3">{title && <h2 id={id}>{title}</h2>}{actions}</div>}{children}
 </section>
}
