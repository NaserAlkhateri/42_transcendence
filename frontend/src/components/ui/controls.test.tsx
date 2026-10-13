// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { TextField } from './TextField'
import { Textarea } from './Textarea'
import { Select } from './Select'
import { Checkbox } from './Checkbox'
afterEach(cleanup)
it('keeps explicit ids associated with all control labels and hints', () => {
  render(<><TextField id="email" label="Email" hint="Work email" /><Textarea id="notes" label="Notes" hint="Optional" /><Select id="role" label="Role" options={[]} hint="Choose" /><Checkbox id="consent" label="Consent" description="Required" /></>)
  for (const [label, id] of [['Email', 'email'], ['Notes', 'notes'], ['Role', 'role'], ['Consent', 'consent']]) {
    const control = screen.getByLabelText(label)
    expect(control).toHaveAttribute('id', id)
    expect(document.getElementById(control.getAttribute('aria-describedby')!)).not.toBeNull()
  }
})
