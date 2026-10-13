// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
afterEach(cleanup)
import { Card } from './Card'
it('labels repeated and Arabic titles with unique ids', () => {
 render(<><Card title="Details">One</Card><Card title="Details">Two</Card><Card title="تفاصيل">Three</Card></>)
 const cards = screen.getAllByRole('region')
 const ids = cards.map(c => c.getAttribute('aria-labelledby'))
 expect(new Set(ids).size).toBe(3)
 for (const id of ids) expect(document.getElementById(id!)).not.toBeNull()
 expect(screen.getByRole('region', {name: 'تفاصيل'})).toHaveTextContent('Three')
})
