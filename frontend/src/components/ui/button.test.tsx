// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { IconButton } from './Button'
it('supports loading on icon-only buttons without leaking props', () => {
 render(<IconButton icon="plus" label="Add" loading />)
 const button = screen.getByRole('button', {name: 'Add'})
 expect(button).toBeDisabled()
 expect(button).toHaveAttribute('aria-busy', 'true')
 expect(screen.getByRole('status')).toHaveTextContent('Working')
 expect(button).not.toHaveAttribute('loading')
})
