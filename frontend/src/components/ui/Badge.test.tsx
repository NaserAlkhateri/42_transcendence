// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
afterEach(cleanup)
import { Badge } from './Badge'
it('renders status as text as well as color', () => {
 render(<Badge variant="success">Approved</Badge>)
 expect(screen.getByText('Approved')).toHaveClass('text-success-700')
})
