import { useEffect, useId, useRef, type ReactNode } from 'react'
import { IconButton } from './Button'
export function Modal({open, title, onClose, children, footer}: {open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode}) {
 const id = useId()
 const ref = useRef<HTMLDialogElement>(null)
 useEffect(() => {
  const dialog = ref.current
  if (!open || !dialog) return
  const previous = document.activeElement as HTMLElement | null
  if (typeof dialog.showModal === 'function') dialog.showModal()
  else dialog.setAttribute('open', '')
  return () => { if (typeof dialog.close === 'function') dialog.close(); previous?.focus() }
 }, [open])
 if (!open) return null
 return <dialog onClick={event => {
   if (event.target !== event.currentTarget) return
   const rect = event.currentTarget.getBoundingClientRect()
   if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose()
  }} ref={ref} aria-modal="true" aria-labelledby={id} onCancel={event=>{event.preventDefault(); onClose()}}
  className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-card border border-ink-200 bg-white p-0 text-ink-900 shadow-overlay backdrop:bg-ink-900/50">
  <div className="p-5"><div className="mb-4 flex items-center justify-between gap-3"><h2 id={id}>{title}</h2><IconButton icon="close" label="Close dialog" onClick={onClose} /></div>{children}{footer && <div className="mt-5 flex justify-end gap-2 border-t border-ink-200 pt-4">{footer}</div>}</div>
 </dialog>
}
