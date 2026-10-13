import { useEffect } from 'react'

const APP_NAME = 'Sijil'

/** Sets the browser tab title for the current page ("Users · Sijil"). */
export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME
  }, [title])
}
