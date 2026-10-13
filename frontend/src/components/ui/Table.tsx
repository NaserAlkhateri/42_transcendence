import type { ReactNode } from 'react'
import { EmptyState } from './EmptyState'
export interface TableColumn<T> {key: string; header: ReactNode; render: (row: T) => ReactNode}
export interface TableProps<T> {caption: string; columns: TableColumn<T>[]; rows: T[]; rowKey: (row: T) => string; emptyMessage?: string}
export function Table<T>({caption, columns, rows, rowKey, emptyMessage = 'No results'}: TableProps<T>) {
 return <div className="overflow-x-auto rounded-card border border-ink-200 bg-white"><table className="w-full text-start text-sm">
  <caption className="sr-only">{caption}</caption><thead className="bg-ink-100 text-ink-700"><tr>{columns.map(c=><th key={c.key} scope="col" className="px-3 py-3 text-start">{c.header}</th>)}</tr></thead>
  <tbody>{rows.map(row=><tr key={rowKey(row)} className="border-t border-ink-100">{columns.map(c=><td key={c.key} className="px-3 py-3">{c.render(row)}</td>)}</tr>)}
   {!rows.length && <tr><td colSpan={columns.length}><EmptyState title={emptyMessage} /></td></tr>}
  </tbody></table></div>
}
