// Shared test setup. Page tests render the whole app (lazy routes, auth probe, API stubs). Running ~20 files
// in parallel can push those first renders past Testing Library's default 1 s wait, so allow 5 s: a passing
// test still finishes as soon as the element appears.
import { configure } from '@testing-library/react'

configure({ asyncUtilTimeout: 5000 })
