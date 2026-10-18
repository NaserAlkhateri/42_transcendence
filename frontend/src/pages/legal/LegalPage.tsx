import { Link, useSearchParams } from 'react-router-dom'

import { useDocumentTitle } from '../../lib/useDocumentTitle'
import type { BilingualDocument, LegalLanguage } from './types'

const LANGUAGE_LABELS: Record<LegalLanguage, { label: string; switchTo: string }> = {
  en: { label: 'English', switchTo: 'Read in English' },
  ar: { label: 'العربية', switchTo: 'اقرأ بالعربية' },
}

/** One legal document in English or Arabic. The language is in the URL (?lang=ar), so a link can point
 * straight at the Arabic text and nothing is stored in the browser. */
export function LegalPage({ document: bilingual, otherPage }: {
  document: BilingualDocument
  otherPage: { to: string; label: Record<LegalLanguage, string> }
}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const language: LegalLanguage = searchParams.get('lang') === 'ar' ? 'ar' : 'en'
  const doc = bilingual[language]
  const other: LegalLanguage = language === 'en' ? 'ar' : 'en'
  useDocumentTitle(doc.title)

  return (
    <article lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'} className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1>{doc.title}</h1>
          <button
            type="button"
            lang={other}
            className="text-sm font-medium text-brand-800 underline"
            onClick={() => setSearchParams(other === 'ar' ? { lang: 'ar' } : {}, { replace: true })}
          >
            {LANGUAGE_LABELS[other].switchTo}
          </button>
        </div>
        <p className="text-sm text-ink-600">
          {language === 'ar' ? 'آخر تحديث: ' : 'Last updated: '}
          {doc.updated}
        </p>
        {doc.intro.map((paragraph) => (
          <p key={paragraph} className="text-ink-800">{paragraph}</p>
        ))}
      </header>

      <nav aria-label={language === 'ar' ? 'المحتويات' : 'Contents'} className="rounded-card border border-ink-200 bg-white p-4">
        <h2 className="mb-2 text-base">{language === 'ar' ? 'المحتويات' : 'Contents'}</h2>
        <ol className="list-decimal space-y-1 ps-5 text-sm">
          {doc.sections.map((section) => (
            <li key={section.id}>
              <a className="text-brand-800 underline" href={`#${section.id}`}>{section.heading}</a>
            </li>
          ))}
        </ol>
      </nav>

      {doc.sections.map((section, index) => (
        <section key={section.id} id={section.id} aria-labelledby={`${section.id}-heading`} className="flex scroll-mt-20 flex-col gap-3">
          <h2 id={`${section.id}-heading`}>{index + 1}. {section.heading}</h2>
          {section.paragraphs?.map((paragraph) => (
            <p key={paragraph} className="text-ink-800">{paragraph}</p>
          ))}
          {section.items ? (
            <ul className="list-disc space-y-1 ps-5 text-ink-800">
              {section.items.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : null}
        </section>
      ))}

      <p className="border-t border-ink-200 pt-4 text-sm text-ink-600">
        <Link className="text-brand-800 underline" to={language === 'ar' ? `${otherPage.to}?lang=ar` : otherPage.to}>
          {otherPage.label[language]}
        </Link>
      </p>
    </article>
  )
}
