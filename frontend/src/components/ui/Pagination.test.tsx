// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
afterEach(cleanup)
import { vi } from 'vitest'
it.each([0, -2, NaN, Infinity, 1.5])('disables invalid page sizes (%s)', pageSize => {
 render(<Pagination total={45} pageSize={pageSize} page={1} onPageChange={vi.fn()} />)
 expect(screen.getByRole('status')).toHaveTextContent('Page 1 of 1')
 expect(screen.getByRole('button', {name:'Next page'})).toBeDisabled()
})
import { fireEvent } from '@testing-library/react'
import { Pagination } from './Pagination'
it('clamps page bounds and navigates a controlled result set', () => {
 const change = vi.fn()
 const {rerender} = render(<Pagination total={45} pageSize={20} page={1} onPageChange={change} />)
 expect(screen.getByRole('button', {name:'Previous page'})).toBeDisabled()
 fireEvent.click(screen.getByRole('button', {name:'Next page'}))
 expect(change).toHaveBeenCalledWith(2)
 rerender(<Pagination total={45} pageSize={20} page={99} onPageChange={change} />)
 expect(screen.getByRole('button', {name:'Next page'})).toBeDisabled()
 expect(screen.getByRole('status')).toHaveTextContent('Page 3 of 3')
})
