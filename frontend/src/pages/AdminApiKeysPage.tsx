import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { Alert, Badge, Button, FormAlert, Modal, Table, TextField } from '../components/ui'
import { errorMessage, http, serverFieldErrors } from '../lib/api'
import { validatePartnerName, type ApiKeyRow, type IssuedApiKey as Issued } from '../lib/apiKeys'
import { formatDay } from '../lib/organizations'
import { useDocumentTitle } from '../lib/useDocumentTitle'

/** /admin/api-keys: platform admins issue and revoke partner API keys (NA-05). */
export function AdminApiKeysPage() {
  useDocumentTitle('API keys')
  const [keys, setKeys] = useState<ApiKeyRow[]>()
  const [loadError, setLoadError] = useState<string>()
  const [issuing, setIssuing] = useState(false)
  const [issued, setIssued] = useState<Issued>()
  const [revoking, setRevoking] = useState<ApiKeyRow>()
  const [busy, setBusy] = useState(false)
  const [alert, setAlert] = useState<string>()

  const load = useCallback(async () => {
    try {
      setKeys(await http.get<ApiKeyRow[]>('/admin/api-keys'))
      setLoadError(undefined)
    } catch (error) {
      setLoadError(errorMessage(error))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function revoke(key: ApiKeyRow) {
    setAlert(undefined)
    setBusy(true)
    try {
      await http.post(`/admin/api-keys/${key.id}/revoke`)
      await load()
    } catch (error) {
      setAlert(errorMessage(error))
    } finally {
      setBusy(false)
      setRevoking(undefined)
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1>API keys</h1>
        <Button onClick={() => { setIssued(undefined); setIssuing(true) }}>Issue key</Button>
      </div>
      <p className="text-ink-600">
        Partners such as insurers read vehicle histories through the partner API with these keys. A key is shown once
        when you issue it; revoking stops it on the next call. Partner guide: <span className="font-mono">doc/PARTNER_API.md</span>,
        reference at <a className="text-brand-800 underline" href="/api/partner/v1/docs">/api/partner/v1/docs</a>.
      </p>

      {issued ? <IssuedKey issued={issued} onDismiss={() => setIssued(undefined)} /> : null}
      <FormAlert message={loadError ?? alert} />

      <Table<ApiKeyRow> caption="Partner API keys, active first" rows={keys ?? []} rowKey={(k) => k.id}
        emptyMessage={keys ? 'No keys issued yet.' : loadError ? 'Keys could not be loaded.' : 'Loading keys…'}
        columns={[
          { key: 'partner', header: 'Partner', render: (k) => k.partner_name },
          { key: 'prefix', header: 'Key', render: (k) => <span className="font-mono">sjl_{k.key_prefix}_…</span> },
          {
            key: 'status', header: 'Status',
            render: (k) => k.revoked_at
              ? <Badge variant="danger">Revoked {formatDay(k.revoked_at)}</Badge>
              : <Badge variant="success">Active</Badge>,
          },
          { key: 'used', header: 'Last used', render: (k) => k.last_used_at ? formatDay(k.last_used_at) : 'Never' },
          { key: 'watches', header: 'Watched VINs', render: (k) => k.watch_count },
          { key: 'issued', header: 'Issued', render: (k) => `${formatDay(k.created_at)}${k.issued_by ? ` by ${k.issued_by}` : ''}` },
          {
            key: 'actions', header: 'Actions',
            render: (k) => k.revoked_at ? null : (
              <Button variant="ghost" size="sm" aria-label={`Revoke key for ${k.partner_name}`} onClick={() => setRevoking(k)}>
                Revoke
              </Button>
            ),
          },
        ]} />

      <IssueKeyModal open={issuing} onClose={() => setIssuing(false)}
        onIssued={async (result) => { setIssuing(false); setIssued(result); await load() }} />

      <Modal open={!!revoking} title={revoking ? `Revoke key for ${revoking.partner_name}?` : 'Revoke key'}
        onClose={() => setRevoking(undefined)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRevoking(undefined)}>Cancel</Button>
            <Button variant="danger" loading={busy} onClick={() => { if (revoking) void revoke(revoking) }}>Revoke key</Button>
          </>
        }>
        <p>Their next API call will be refused. This cannot be undone; issue a new key if they need access again.</p>
      </Modal>
    </section>
  )
}

function IssuedKey({ issued, onDismiss }: { issued: Issued; onDismiss: () => void }) {
  return (
    <Alert variant="success" title={`Key issued for ${issued.key.partner_name}`} onDismiss={onDismiss}>
      <p>Copy it now and send it to the partner over a secure channel. It will not be shown again.</p>
      <p className="mt-2 break-all font-mono select-all" data-testid="issued-api-key">{issued.api_key}</p>
      <p className="mt-2">They send it in the <span className="font-mono">X-API-Key</span> header on every request.</p>
    </Alert>
  )
}

function IssueKeyModal({ open, onClose, onIssued }: {
  open: boolean
  onClose: () => void
  onIssued: (issued: Issued) => Promise<void>
}) {
  const [partnerName, setPartnerName] = useState('')
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function submit(event?: FormEvent) {
    event?.preventDefault()
    const problem = validatePartnerName(partnerName)
    setError(problem)
    if (problem) return
    setBusy(true)
    try {
      const result = await http.post<Issued>('/admin/api-keys', { partner_name: partnerName.trim() })
      setPartnerName('')
      await onIssued(result)
    } catch (failure) {
      setError(serverFieldErrors(failure, { partner_name: 'partnerName' as const }).partnerName ?? errorMessage(failure))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} title="Issue a partner API key" onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={busy} onClick={() => void submit()}>Issue key</Button>
        </>
      }>
      <form noValidate onSubmit={(event) => void submit(event)}>
        <TextField label="Partner name" maxLength={120} required value={partnerName} error={error}
          hint="The business the key is for, e.g. an insurer." onChange={(event) => setPartnerName(event.target.value)} />
      </form>
    </Modal>
  )
}
