// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
afterEach(cleanup)
import { EmptyState } from './EmptyState'
it('renders an empty-state explanation and optional action', () => {
 render(<EmptyState title="No records" description="Try another search" action={<button>Reset</button>} />)
 expect(screen.getByRole('heading', {name:'No records'})).toBeInTheDocument()
 expect(screen.getByText('Try another search')).toBeInTheDocument()
 expect(screen.getByRole('button', {name:'Reset'})).toBeInTheDocument()
})
