import { uploadWithProgress } from './api'

export interface LicenceDocument {
  id: string
  file_name: string
  content_type: string
  size_bytes: number
  created_at: string
  deleted_at: string | null
  removal_pending: boolean
}

const FORMATS: Record<string, { extensions: RegExp; signature: number[] }> = {
  'application/pdf': { extensions: /\.pdf$/i, signature: [37, 80, 68, 70, 45] },
  'image/jpeg': { extensions: /\.jpe?g$/i, signature: [255, 216, 255] },
  'image/png': { extensions: /\.png$/i, signature: [137, 80, 78, 71, 13, 10, 26, 10] },
}

export const DOCUMENT_ACCEPT = Object.keys(FORMATS).join(',')
export const DOCUMENT_LIMIT = 5 * 1024 * 1024
export const MAX_DOCUMENTS = 10

export function documentsPath(id: string, admin = false): string {
  return `${admin ? '/admin' : ''}/organizations/${id}/documents`
}

export async function documentIssue(file: File): Promise<string | undefined> {
  const format = FORMATS[file.type]
  if (!format || !format.extensions.test(file.name)) return `${file.name}: choose a PDF, JPEG or PNG file.`
  if (file.size === 0 || file.size > DOCUMENT_LIMIT) return `${file.name}: choose a non-empty file up to 5 MiB.`
  if ([...file.name].length > 255 || /[/\\\p{C}]/u.test(file.name)) return 'Use a file name of up to 255 characters without path separators.'
  const actual = new Uint8Array(await file.slice(0, format.signature.length).arrayBuffer())
  if (!format.signature.every((byte, i) => actual[i] === byte)) return `${file.name}: the file contents do not match its type.`
}

export async function validateDocuments(files: File[]): Promise<string | undefined> {
  if (files.length > MAX_DOCUMENTS) return 'Choose up to ten files.'
  for (const file of files) {
    const issue = await documentIssue(file)
    if (issue) return issue
  }
}

export async function uploadDocuments(
  id: string, files: File[], onProgress: (percent: number) => void, onUploaded?: (file: File) => void,
): Promise<void> {
  for (const [index, file] of files.entries()) {
    await uploadWithProgress(documentsPath(id), file, (part) => {
      onProgress(Math.min(99, Math.round((index + part) * 100 / files.length)))
    })
    onUploaded?.(file)
    onProgress(Math.round((index + 1) * 100 / files.length))
  }
}
