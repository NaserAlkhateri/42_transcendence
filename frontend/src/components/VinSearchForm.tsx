import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { parseVin } from '../lib/vin'
import { Button, TextField } from './ui'

/** VIN lookup: normalizes what was typed (case, spaces, dashes, Arabic digits) and opens that vehicle's timeline. */
export function VinSearchForm() {
  const navigate = useNavigate()
  const [value, setValue] = useState('')
  const [error, setError] = useState<string>()

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const result = parseVin(value)
    if (!result.ok) {
      setError(result.error)
      return
    }
    setError(undefined)
    navigate(`/vehicles/${result.vin}`)
  }

  return (
    <form role="search" aria-label="VIN lookup" noValidate onSubmit={onSubmit} className="flex w-full flex-wrap items-start gap-3">
      <TextField
        label="VIN"
        hint="17 characters, printed on the windscreen and the registration card."
        value={value}
        onChange={(event) => setValue(event.target.value)}
        error={error}
        autoComplete="off"
        spellCheck={false}
        maxLength={40}
        className="min-w-64 flex-1 text-start"
      />
      <Button type="submit" icon="search" className="sm:mt-6.5">
        Look up
      </Button>
    </form>
  )
}
