import { useEffect, useId, useState, type FormEvent } from 'react'

import { apiResponse, errorMessage, http } from '../lib/api'
import { downloadFile } from '../lib/download'
import { DOCUMENT_ACCEPT, documentIssue, documentsPath, uploadDocuments, validateDocuments, type LicenceDocument } from '../lib/licenceDocuments'
import { DocumentPreview } from './DocumentPreview'
import { Button, Card, FormAlert, Modal } from './ui'

export function DocumentPicker({ files, onChange, disabled }: {
  files: File[]; onChange: (files: File[]) => void; disabled: boolean
}) {
  const id = useId()
  const [preview, setPreview] = useState<File>()
  const [issue, setIssue] = useState<string>()

  return <div className="flex flex-col gap-2">
    <label htmlFor={id} className="font-medium">Licence and trade documents</label>
    <p id={`${id}-hint`} className="text-sm text-ink-600">PDF, JPEG or PNG, up to 5 MiB per file.</p>
    <input id={id} aria-describedby={`${id}-hint`} type="file" multiple accept={DOCUMENT_ACCEPT} disabled={disabled}
      onChange={(event) => {
        onChange(Array.from(event.currentTarget.files ?? []))
        event.currentTarget.value = ''
        setIssue(undefined)
      }} />
    <FormAlert message={issue} />
    {files.length ? <ul className="space-y-2 text-sm">
      {files.map((file, i) => <li key={`${i}-${file.name}`} className="flex flex-wrap items-center gap-x-3">
        <span className="break-all">{file.name}</span>
        <Button variant="ghost" size="sm" disabled={disabled} aria-label={`Preview selected ${file.name}`} onClick={() => {
          void documentIssue(file).then((problem) => { setIssue(problem); if (!problem) setPreview(file) })
            .catch(() => setIssue('Could not read that file.'))
        }}>Preview</Button>
        <Button variant="ghost" size="sm" disabled={disabled} aria-label={`Remove selected ${file.name}`}
          onClick={() => { onChange(files.filter((_, index) => index !== i)); setIssue(undefined) }}>Remove selection</Button>
      </li>)}
    </ul> : null}
    {preview ? <DocumentPreview name={preview.name} blob={preview} onClose={() => setPreview(undefined)} /> : null}
  </div>
}

export function DocumentProgress({ percent }: { percent: number | undefined }) {
  return percent === undefined ? null : <div className="flex items-center gap-3">
    <progress aria-label="Document upload progress" max="100" value={percent} />
    <span className="text-sm">{percent}%</span>
  </div>
}

export function DocumentList({ documents, path, onRemoved }: {
  documents: LicenceDocument[]; path: string; onRemoved?: (document: LicenceDocument) => void
}) {
  const [preview, setPreview] = useState<{ name: string; blob: Blob }>()
  const [confirming, setConfirming] = useState<LicenceDocument>()
  const [busy, setBusy] = useState(false)
  const [issue, setIssue] = useState<string>()

  async function act(request: () => Promise<void>) {
    setIssue(undefined)
    setBusy(true)
    try { await request() }
    catch (error) { setIssue(errorMessage(error)) }
    finally { setBusy(false) }
  }

  return <>
    <FormAlert message={issue} />
    {documents.length ? <ul className="divide-y divide-ink-200">
      {documents.map((file) => {
        const url = `${path}/${file.id}`
        return <li key={file.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
          <div className="min-w-0">
            <p className="break-all text-sm font-medium">{file.file_name}</p>
            {file.deleted_at ? <p className="text-sm text-ink-600">Document removed</p> : null}
          </div>
          <div className="flex flex-wrap gap-1">
            {!file.deleted_at ? <>
              <Button variant="ghost" size="sm" disabled={busy} aria-label={`Preview ${file.file_name}`}
                onClick={() => void act(async () => {
                  const response = await apiResponse(url)
                  setPreview({ name: file.file_name, blob: await response.blob() })
                })}>Preview</Button>
              <Button variant="ghost" size="sm" disabled={busy} aria-label={`Download ${file.file_name}`}
                onClick={() => void act(async () => { await downloadFile(url, { fallbackName: file.file_name }) })}>Download</Button>
            </> : null}
            {onRemoved && (!file.deleted_at || file.removal_pending) ? (
              <Button variant="danger" size="sm" disabled={busy} onClick={() => setConfirming(file)}>
                {file.removal_pending ? 'Retry removal' : 'Remove document'}
              </Button>
            ) : null}
          </div>
        </li>
      })}
    </ul> : <p className="text-sm text-ink-600">No licence documents uploaded.</p>}
    {preview ? <DocumentPreview name={preview.name} blob={preview.blob} onClose={() => setPreview(undefined)} /> : null}
    {confirming && onRemoved ? <Modal open title="Remove licence document?"
      onClose={() => { if (!busy) setConfirming(undefined) }}
      footer={<>
        <Button variant="secondary" disabled={busy} onClick={() => setConfirming(undefined)}>Cancel</Button>
        <Button variant="danger" loading={busy} onClick={() => void act(async () => {
          try {
            onRemoved(await http.delete<LicenceDocument>(`${path}/${confirming.id}`))
          } catch (error) {
            // The audit and removal marker may have been saved even if storage was unavailable.
            const detail = await http.get<{ documents: LicenceDocument[] }>(path.replace(/\/documents$/, '')).catch(() => null)
            const latest = detail?.documents.find((file) => file.id === confirming.id)
            if (latest) onRemoved(latest)
            throw error
          } finally {
            setConfirming(undefined)
          }
        })}>Remove document</Button>
      </>}>
      <p>This removes {confirming.file_name} from storage and records the removal in the audit log.</p>
    </Modal> : null}
  </>
}

export function EntityDocuments({ id }: { id: string }) {
  const path = documentsPath(id)
  const [documents, setDocuments] = useState<LicenceDocument[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [issue, setIssue] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<number>()

  useEffect(() => {
    const controller = new AbortController()
    void http.get<LicenceDocument[]>(path, { signal: controller.signal }).then(setDocuments).catch((error: unknown) => {
      if (!controller.signal.aborted) setIssue(errorMessage(error))
    })
    return () => controller.abort()
  }, [path])

  async function upload(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setIssue(undefined)
    try {
      const problem = await validateDocuments(files)
      if (problem) { setIssue(problem); return }
      setProgress(0)
      await uploadDocuments(id, files, setProgress, (saved) => setFiles((rest) => rest.filter((file) => file !== saved)))
    } catch (error) {
      setIssue(errorMessage(error))
    } finally {
      await http.get<LicenceDocument[]>(path).then(setDocuments).catch(() => {})
      setBusy(false)
      setProgress(undefined)
    }
  }

  return <Card title="Licence documents">
    <DocumentList documents={documents} path={path} />
    <form className="mt-4 flex flex-col items-start gap-3" onSubmit={upload}>
      <FormAlert message={issue} />
      <DocumentPicker files={files} onChange={setFiles} disabled={busy} />
      <DocumentProgress percent={progress} />
      <Button type="submit" disabled={!files.length} loading={busy}>Upload documents</Button>
    </form>
  </Card>
}
