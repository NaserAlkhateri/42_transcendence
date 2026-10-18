import { LegalPage } from './LegalPage'
import { PRIVACY_POLICY } from './privacy'
import { TERMS_OF_SERVICE } from './terms'

export function PrivacyPolicyPage() {
  return <LegalPage document={PRIVACY_POLICY} otherPage={{ to: '/terms', label: { en: 'Read the Terms of Service', ar: 'اقرأ شروط الخدمة' } }} />
}

export function TermsOfServicePage() {
  return <LegalPage document={TERMS_OF_SERVICE} otherPage={{ to: '/privacy', label: { en: 'Read the Privacy Policy', ar: 'اقرأ سياسة الخصوصية' } }} />
}
