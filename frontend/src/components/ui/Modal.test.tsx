// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { Modal } from './Modal'
afterEach(cleanup)
it('ignores empty panel clicks but closes on a true backdrop click', () => {
 const close = vi.fn()
 render(<Modal open title="Confirm" onClose={close}>Body</Modal>)
 const dialog = screen.getByRole('dialog')
 vi.spyOn(dialog, 'getBoundingClientRect').mockReturnValue({left:100, right:500, top:100, bottom:400, x:100, y:100, width:400, height:300, toJSON:()=>({})})
 fireEvent.click(dialog, {clientX:120, clientY:120})
 expect(close).not.toHaveBeenCalled()
 fireEvent.click(dialog, {clientX:20, clientY:20})
 expect(close).toHaveBeenCalledOnce()
})
it('opens a labelled modal and closes through cancel or close button', () => {
 const close = vi.fn()
 const {rerender} = render(<Modal open title="Confirm" onClose={close}>Body</Modal>)
 const dialog = screen.getByRole('dialog', {name:'Confirm'})
 expect(dialog).toHaveAttribute('aria-modal','true')
 fireEvent(dialog, new Event('cancel', {bubbles:true, cancelable:true}))
 expect(close).toHaveBeenCalledOnce()
 fireEvent.click(screen.getByRole('button', {name:'Close dialog'}))
 expect(close).toHaveBeenCalledTimes(2)
 rerender(<Modal open={false} title="Confirm" onClose={close}>Body</Modal>)
 expect(screen.queryByRole('dialog')).toBeNull()
})
