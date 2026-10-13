// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import {afterEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {App} from './App'
import {AuthContext, type AuthState, type User} from './auth/auth-context'
import {SubmitButton} from './components/TextField'
import {RequireRole} from './routes/guards'
import {readFileSync} from 'node:fs'
afterEach(()=>{cleanup(); vi.unstubAllGlobals()})
it('keeps legacy submit buttons compatible with shared loading states', ()=>{
 render(<SubmitButton busy>Save</SubmitButton>)
 expect(screen.getByRole('button')).toHaveAttribute('aria-busy','true')
 expect(screen.getByRole('status')).toHaveTextContent('Working')
})
// Every view a visitor can land on, including the guard's own Access-denied screen. Palette compliance
// is checked tree-wide in design-tokens.test.ts, which does not need this list kept up to date.
it('uses shared ui in every view that renders chrome', ()=>{
 for (const file of ['pages/HomePage.tsx','pages/LoginPage.tsx','pages/SignupPage.tsx','pages/ProfilePage.tsx','pages/AdminUsersPage.tsx','pages/NotFoundPage.tsx','pages/DesignSystemPage.tsx','pages/VehicleTimelinePage.tsx','components/VinSearchForm.tsx','components/WatchVinButton.tsx','components/RecordFieldset.tsx','pages/workshop/NewRecordPage.tsx','pages/workshop/CorrectRecordPage.tsx','layouts/AppLayout.tsx','components/ErrorBoundary.tsx','routes/guards.tsx','App.tsx']) {
  const source=readFileSync(new URL('./'+file, import.meta.url),'utf8')
  expect(source, file).toMatch(/components\/ui|\.\/ui/)
 }
})
it('renders the role guard refusal through the shared Alert', ()=>{
 const consumer: User = {id:'u1', email:'c@example.test', full_name:'Consumer', role:'consumer',
  effective_role:'consumer', must_change_password:false, created_at:'2026-01-01T00:00:00Z', memberships:[]}
 const state = {user: consumer, sessionExpired: false} as unknown as AuthState
 render(<AuthContext.Provider value={state}><MemoryRouter>
  <RequireRole roles={['platform_admin']}><p>Admin only</p></RequireRole>
 </MemoryRouter></AuthContext.Provider>)
 expect(screen.getByRole('heading',{name:'Access denied'})).toBeInTheDocument()
 expect(screen.getByRole('alert')).toHaveTextContent('does not have permission')
 expect(screen.queryByText('Admin only')).toBeNull()
})
it('loads the public lazy showcase and demonstrates interactive shared components', async ()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:{message:'Signed out'}}),{status:401})))
 window.history.replaceState(null,'','/design-system')
 render(<App />)
 expect(await screen.findByRole('heading',{name:'Design system'})).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Open modal'}))
 expect(screen.getByRole('dialog',{name:'Example modal'})).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Close dialog'}))
 expect(screen.queryByRole('dialog')).toBeNull()
 expect(screen.getByRole('table',{name:'Example records'})).toBeInTheDocument()
})
