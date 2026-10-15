import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth, type User } from '../../auth/auth-context'
import { OrganizationFields } from '../../components/OrganizationFields'
import { Alert, Button, Card, FormAlert } from '../../components/ui'
import { errorMessage, http, serverFieldErrors } from '../../lib/api'
import {
  EMPTY_ORGANIZATION_FORM,
  ORGANIZATION_SERVER_FIELDS,
  organizationPayload,
  validateOrganization,
  type Organization,
  type OrganizationField,
} from '../../lib/organizations'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import type { FieldErrors } from '../../lib/validation'

/** /organizations/register: a workshop or dealership applies to join. It stays pending until reviewed. */
export function RegisterOrganizationPage() {
  useDocumentTitle('Register your business')
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY_ORGANIZATION_FORM)
  const [errors, setErrors] = useState<FieldErrors<OrganizationField>>({})
  const [alert, setAlert] = useState<string>()
  const [busy, setBusy] = useState(false)

  if (user?.role === 'platform_admin') {
    return (
      <section className="mx-auto flex w-full max-w-xl flex-col gap-4">
        <h1>Register your business</h1>
        <Alert variant="info">
          Platform admins add organisations from <Link className="underline" to="/admin/organizations">Organisations</Link>.
        </Alert>
      </section>
    )
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAlert(undefined)
    const clientErrors = validateOrganization(form)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length) return

    setBusy(true)
    try {
      const organization = await http.post<Organization>('/organizations', organizationPayload(form))
      setUser(await http.get<User>('/me'))  // picks up the new membership for the nav and profile
      navigate(`/organizations/${organization.id}`, { replace: true })
    } catch (error) {
      setErrors(serverFieldErrors(error, ORGANIZATION_SERVER_FIELDS))
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-6">
      <div>
        <h1>Register your business</h1>
        <p className="mt-2 text-ink-600">
          Workshops and dealerships apply here. A platform admin checks your trade licence before your team can add
          service records. You become the organisation&apos;s admin.
        </p>
      </div>
      <Card>
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          <FormAlert message={alert} />
          <OrganizationFields form={form} errors={errors} onChange={setForm} />
          <Button type="submit" loading={busy}>Submit for review</Button>
        </form>
      </Card>
    </section>
  )
}
