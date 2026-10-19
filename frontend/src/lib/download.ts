// File downloads (AG-07). An export is fetched like any API call (session cookie, ApiError on failure), so the
// page can show a spinner and the API's error message, then the file is handed to the browser to save.

import { ApiError, apiResponse } from './api'

/** The file name from a Content-Disposition header, or `fallback`. Only a plain base name is kept. */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  let name: string | undefined
  const encoded = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)
  if (encoded) {
    try {
      name = decodeURIComponent(encoded[1].trim())
    } catch {
      name = undefined
    }
  }
  name ??= /filename\s*=\s*"([^"]*)"/i.exec(header)?.[1] ?? /filename\s*=\s*([^;]+)/i.exec(header)?.[1]
  // Never let a header pick a folder or a hidden file.
  const base = name?.trim().split(/[\\/]/).pop()?.replace(/^\.+/, '')
  return base || fallback
}

/** Hand a blob to the browser's "save file": a temporary object URL on a temporary <a download>. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.append(link)
  try {
    link.click()
  } finally {
    link.remove()
    // Some browsers start reading the URL only after the click handler returns, so revoke it a moment later.
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }
}

export interface DownloadOptions {
  /** Used when the response names no file. */
  fallbackName: string
  signal?: AbortSignal
  timeoutMs?: number
}

/** GET an API path and save the response as a file. Resolves with the saved file name; failures are ApiError. */
export async function downloadFile(path: string, { fallbackName, signal, timeoutMs }: DownloadOptions): Promise<string> {
  const response = await apiResponse(path, { signal, timeoutMs })
  let blob: Blob
  try {
    blob = await response.blob()
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, 'network_error', 'The download was interrupted. Please try again.')
  }
  const filename = filenameFromDisposition(response.headers.get('Content-Disposition'), fallbackName)
  saveBlob(blob, filename)
  return filename
}
