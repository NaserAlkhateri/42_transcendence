import type {ReactNode} from 'react'
import {Button} from './ui'
export {TextField, FormAlert} from './ui'
/** Compatibility API for HA-01 forms; new code imports components/ui. */
export function SubmitButton({busy, children}: {busy: boolean; children: ReactNode}) {
 return <Button type="submit" loading={busy}>{busy ? 'Please wait…' : children}</Button>
}
