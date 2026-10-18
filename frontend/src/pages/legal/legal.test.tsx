// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../App'
import { PRIVACY_POLICY } from './privacy'
import { TERMS_OF_SERVICE } from './terms'
import type { BilingualDocument, LegalDocument } from './types'

const DOCUMENTS: [string, BilingualDocument][] = [['privacy', PRIVACY_POLICY], ['terms', TERMS_OF_SERVICE]]
const ARABIC = /[؀-ۿ]/

function allText(doc: LegalDocument): string[] {
  return [doc.title, doc.updated, ...doc.intro, ...doc.sections.flatMap((s) => [s.heading, ...(s.paragraphs ?? []), ...(s.items ?? [])])]
}

function stubGuest() {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/auth/session') {
      return new Response(JSON.stringify({ user: null }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`unexpected request ${url.pathname}`)
  }))
}

function open(path: string) {
  stubGuest()
  window.history.replaceState(null, '', path)
  render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('legal content', () => {
  it.each(DOCUMENTS)('%s has the same sections in English and Arabic, none empty', (_, doc) => {
    expect(doc.ar.sections.map((s) => s.id)).toEqual(doc.en.sections.map((s) => s.id))
    for (const language of [doc.en, doc.ar]) {
      expect(language.sections.length).toBeGreaterThanOrEqual(8)
      for (const section of language.sections) {
        expect((section.paragraphs?.length ?? 0) + (section.items?.length ?? 0)).toBeGreaterThan(0)
      }
    }
  })

  it.each(DOCUMENTS)('%s is real text, not a placeholder', (_, doc) => {
    for (const text of [...allText(doc.en), ...allText(doc.ar)]) {
      expect(text.trim()).not.toBe('')
      expect(text).not.toMatch(/lorem|ipsum|todo|tbd|placeholder|being written/i)
    }
    expect(allText(doc.ar).filter((text) => !/^\d/.test(text)).every((text) => ARABIC.test(text))).toBe(true)
    expect(allText(doc.en).some((text) => ARABIC.test(text))).toBe(false)
  })

  it('the privacy policy covers what Sijil really stores and shares', () => {
    const text = allText(PRIVACY_POLICY.en).join(' ')
    for (const fact of ['sijil_session', 'sijil_csrf', 'Argon2id', 'Licence documents are visible only', 'vPIC',
      'append-only', 'Audit-log entries stay', 'never records who owns the car']) {
      expect(text).toContain(fact)
    }
  })
})

describe('legal pages', () => {
  it('are linked from the footer on every page', async () => {
    for (const path of ['/', '/login']) {
      open(path)
      const footer = await screen.findByRole('contentinfo')
      expect(within(footer).getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy')
      expect(within(footer).getByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', '/terms')
      cleanup()
      vi.unstubAllGlobals()
    }
  })

  it('show the privacy policy with its contents list', async () => {
    open('/privacy')
    expect(await screen.findByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeInTheDocument()
    expect(screen.getByText(/Last updated:/)).toBeInTheDocument()
    const contents = screen.getByRole('navigation', { name: 'Contents' })
    expect(within(contents).getAllByRole('link')).toHaveLength(PRIVACY_POLICY.en.sections.length)
    expect(screen.getByRole('heading', { name: /Cookies and browser storage/ })).toBeInTheDocument()
    expect(document.title).toContain('Privacy Policy')
  })

  it('switch to Arabic, right to left, and back', async () => {
    open('/privacy')
    fireEvent.click(await screen.findByRole('button', { name: 'اقرأ بالعربية' }))

    const heading = await screen.findByRole('heading', { level: 1, name: 'سياسة الخصوصية' })
    const article = heading.closest('article')
    expect(article).toHaveAttribute('dir', 'rtl')
    expect(article).toHaveAttribute('lang', 'ar')
    expect(window.location.search).toBe('?lang=ar')
    expect(screen.getByRole('link', { name: 'اقرأ شروط الخدمة' })).toHaveAttribute('href', '/terms?lang=ar')

    fireEvent.click(screen.getByRole('button', { name: 'Read in English' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeInTheDocument()
    expect(window.location.search).toBe('')
  })

  it('open the Arabic terms straight from a link', async () => {
    open('/terms?lang=ar')
    expect(await screen.findByRole('heading', { level: 1, name: 'شروط الخدمة' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /سجل نسخة تجريبية/ })).toBeInTheDocument()
  })

  it('are linked where people agree to them', async () => {
    open('/signup')
    const form = (await screen.findByRole('button', { name: 'Sign up' })).closest('form') as HTMLElement
    expect(within(form).getByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', '/terms')
    expect(within(form).getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy')
  })
})
