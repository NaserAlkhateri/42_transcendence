// Legal pages (NA-07) are typed content, one document per language, so HA-03 can hook them into the app-wide
// language switch without rewriting the text.

export type LegalLanguage = 'en' | 'ar'

export interface LegalSection {
  id: string
  heading: string
  paragraphs?: string[]
  items?: string[]
}

export interface LegalDocument {
  title: string
  /** Shown as "Last updated", already formatted for the language (day before month, Western digits). */
  updated: string
  intro: string[]
  sections: LegalSection[]
}

export type BilingualDocument = Record<LegalLanguage, LegalDocument>

/** Date of the current text. Change it whenever the wording changes. */
export const LEGAL_UPDATED = { en: '18 Oct 2026', ar: '18 أكتوبر 2026' }
