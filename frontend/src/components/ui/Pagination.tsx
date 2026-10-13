import { Button } from './Button'
export interface PaginationProps {total: number; pageSize: number; page: number; onPageChange: (page: number) => void}
export function Pagination({total, pageSize, page, onPageChange}: PaginationProps) {
 const validSize = Number.isInteger(pageSize) && pageSize > 0
 const count = Number.isFinite(total) ? Math.max(0, Math.floor(total)) : 0
 const pages = validSize ? Math.max(1, Math.ceil(count / pageSize)) : 1
 const current = Math.min(pages, Math.max(1, Number.isFinite(page) ? Math.floor(page) : 1))
 return <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 text-sm text-ink-600">
  <span role="status">{total} results · Page {current} of {pages}</span><div className="flex gap-2">
   <Button variant="secondary" size="sm" aria-label="Previous page" disabled={current <= 1} onClick={()=>onPageChange(current-1)}>Previous</Button>
   <Button variant="secondary" size="sm" aria-label="Next page" disabled={current >= pages} onClick={()=>onPageChange(current+1)}>Next</Button>
  </div></nav>
}
