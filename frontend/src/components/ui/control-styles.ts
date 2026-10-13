import { cx } from './cx'
export function controlClass(invalid: boolean, extra?: string) {
  return cx(
    'w-full rounded-control border bg-white px-3 py-2 text-ink-900 placeholder:text-ink-400',
    'focus:outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0',
    'disabled:cursor-not-allowed disabled:bg-ink-100 disabled:text-ink-500',
    invalid ? 'border-danger-600' : 'border-ink-300',
    extra,
  )
}
