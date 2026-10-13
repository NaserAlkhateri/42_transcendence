// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
afterEach(cleanup)
import { Alert, FormAlert } from './Alert'
it('announces semantic alerts and dismisses errors', () => {
 const close = vi.fn()
 const {rerender} = render(<Alert variant="danger" title="Failed" onDismiss={close}>Retry</Alert>)
 expect(screen.getByRole('alert')).toHaveTextContent('Failed')
 fireEvent.click(screen.getByRole('button', {name: 'Dismiss alert'}))
 expect(close).toHaveBeenCalledOnce()
 rerender(<Alert variant="success">Saved</Alert>)
 expect(screen.getByRole('status')).toHaveTextContent('Saved')
 rerender(<FormAlert />)
 expect(screen.queryByRole('alert')).toBeNull()
})
