import { useEffect, useRef, useState } from 'react'
import type { PDFDocumentLoadingTask, RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

import { Alert, Modal } from './ui'

function PdfPreview({ blob }: { blob: Blob }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [failed, setFailed] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true
    let loading: PDFDocumentLoadingTask | undefined
    let rendering: RenderTask | undefined
    async function render() {
      const [{ getDocument, GlobalWorkerOptions }, data] = await Promise.all([import('pdfjs-dist'), blob.arrayBuffer()])
      if (!active) return
      GlobalWorkerOptions.workerSrc = workerUrl
      loading = getDocument({ data, enableXfa: false, useWasm: false, isOffscreenCanvasSupported: false })
      const pdf = await loading.promise
      const page = await pdf.getPage(1)
      if (!active || !canvas.current) return
      const base = page.getViewport({ scale: 1 })
      if (base.width <= 0 || base.height <= 0) throw new Error('Invalid PDF page dimensions')
      const viewport = page.getViewport({ scale: Math.min(900 / base.width, 1200 / base.height) })
      canvas.current.width = Math.max(1, Math.ceil(viewport.width))
      canvas.current.height = Math.max(1, Math.ceil(viewport.height))
      rendering = page.render({ canvas: canvas.current, viewport })
      await rendering.promise
      if (active) setReady(true)
    }
    void render().catch(() => { if (active) setFailed(true) })
    return () => { active = false; rendering?.cancel(); void loading?.destroy().catch(() => {}) }
  }, [blob])

  if (failed) return <Alert variant="warning">Preview unavailable. Download the PDF to view it.</Alert>
  return <>
    {!ready ? <p role="status">Rendering preview…</p> : null}
    <canvas ref={canvas} hidden={!ready} role="img" aria-label="First page of the PDF" className="h-auto w-full" />
    {ready ? <p className="mt-2 text-sm">First page. Download the file to view all pages.</p> : null}
  </>
}

function ImagePreview({ blob, name }: { blob: Blob; name: string }) {
  const ref = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const url = URL.createObjectURL(blob)
    if (ref.current) ref.current.src = url
    return () => URL.revokeObjectURL(url)
  }, [blob])
  return <img ref={ref} alt={`Preview of ${name}`} className="max-h-[65dvh] w-full object-contain" />
}

export function DocumentPreview({ name, blob, onClose }: { name: string; blob: Blob; onClose: () => void }) {
  return <Modal open title="Document preview" onClose={onClose}>
    <p className="mb-3 break-all">{name}</p>
    {blob.type === 'application/pdf' ? <PdfPreview blob={blob} /> : <ImagePreview blob={blob} name={name} />}
  </Modal>
}
