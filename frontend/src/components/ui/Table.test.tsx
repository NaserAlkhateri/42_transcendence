// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
afterEach(cleanup)
import { Table } from './Table'
it('provides caption, column scopes, rows and empty content', () => {
 const columns = [{key:'name', header:'Name', render:(row: {id:string; name:string}) => row.name}]
 const {rerender} = render(<Table caption="People" columns={columns} rows={[{id:'1', name:'Sara'}]} rowKey={r=>r.id} />)
 expect(screen.getByRole('table', {name:'People'})).toBeInTheDocument()
 expect(screen.getByRole('columnheader', {name:'Name'})).toHaveAttribute('scope','col')
 expect(screen.getByRole('cell', {name:'Sara'})).toBeInTheDocument()
 rerender(<Table caption="People" columns={columns} rows={[]} rowKey={r=>r.id} emptyMessage="No people" />)
 expect(screen.getByText('No people')).toBeInTheDocument()
})
