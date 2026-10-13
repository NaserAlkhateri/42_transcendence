# Sijil design system (HA-02)

The public `/design-system` route is a lazy-loaded, interactive component showcase linked from the footer. All existing pages use shared UI and the token palette; no HA-03 localization or later business features are included. Peer approval is required before the module is signed off.

## Foundations

`frontend/src/index.css` is the source of truth. Tailwind v4 generates utilities from the tokens; prefer `bg-brand-700`, `text-ink-600`, `rounded-control` and `shadow-card` over stock palette colors.

| Family | Usage | Main color |
| --- | --- | --- |
| Brand | Primary actions, identity, focus | brand-700 `#126150` |
| Ink | Text, surfaces, borders | ink-900 `#161a21`, ink-50 `#f7f8fa` |
| Success | Successful operations | success-700 `#067647` |
| Warning | Attention, session notices | warning-700 `#b54708` |
| Danger | Errors and destructive actions | danger-700 `#b42318` |
| Info | Informational notices | info-700 `#175cd3` |

Each semantic family includes pale background and border shades. Never convey state through color alone: include a text label and/or icon.

Typography uses offline system stacks: Segoe UI/system sans for content (with Arabic fallbacks), system monospace for identifiers. Base headings: h1 28/36px, h2 20/28px, h3 17/24px; body 16px, helpers 14px. Write `<h1>Users</h1>`, not `<h1 className="text-2xl font-semibold text-ink-900">` — the base layer already owns the size, weight and colour, and re-declaring them per page is how a documented scale quietly stops being the one that ships. Keep utilities for genuine exceptions only (the home hero is `text-3xl sm:text-4xl`). Controls have 8px corners; cards 12px. Keyboard focus uses a shared visible teal outline; reduced-motion preference suppresses animations.

Icons are local, consistent 24px-grid SVG stroke paths with round caps and 2px stroke. `IconName` and `ICON_NAMES` expose the set. Icons are decorative by default; use `label` for standalone meaningful icons, and `IconButton` for icon-only controls.

## Reusable components

Import from `src/components/ui` (barrel). Components are typed and accept native attributes where relevant.

| Component | Usage |
| --- | --- |
| Button | `variant`: primary/secondary/ghost/danger; `size`: sm/md/lg; `loading` disables and announces progress; default type button |
| IconButton | Requires `icon` and accessible `label`; supports Button loading/disabled/size props |
| TextField | Required `label`; optional `error`, `hint`, `hideLabel`; native input props |
| Field | Label/hint/error render-prop wiring for custom controls; optional explicit `id` |
| Textarea | Native multiline control with label, error/hint and controlled character count |
| Select | Label and `{value,label,disabled?}[]` options; optional empty placeholder |
| Checkbox | Clickable label, optional description, native checked/onChange |
| Alert | info/success/warning/danger, optional title and dismiss callback; danger announces alert, others status |
| FormAlert | Optional message; renders nothing when absent, danger Alert otherwise |
| Badge | Text status with neutral/brand/success/warning/danger/info styling |
| Card | Optional title/actions and children; generated unique title ids, including repeated or non-Latin titles |
| Modal | Controlled `open`, title, onClose, children and optional footer; native dialog focus isolation/Escape and focus restoration; only true backdrop clicks dismiss |
| Table | Generic `columns`, `rows`, stable `rowKey`, required caption, optional emptyMessage; horizontal overflow and scoped headings |
| Pagination | Controlled page, total, pageSize, onPageChange; clamps page bounds; invalid page sizes disable navigation |
| EmptyState | Title, optional description, icon and action |
| Icon | Typed local icon name, optional label and size |
| Spinner | Accessible progress status with label and sm/md/lg sizes |

`buttonClass()` styles router links without nesting interactive elements. `controlClass()` is available for custom native controls. The old `components/TextField` module is a compatibility wrapper exporting shared TextField/FormAlert and SubmitButton (`busy` maps to Button loading); new code imports the barrel directly.

```tsx
import { Button, Card, FormAlert, TextField, Table, Pagination } from '../components/ui'

<Card title="Details">
  <form onSubmit={save}>
    <FormAlert message={error} />
    <TextField id="full-name" label="Full name" required value={name}
      onChange={event => setName(event.target.value)} hint="As shown on your account" />
    <Button type="submit" loading={busy}>Save</Button>
  </form>
</Card>

<Table caption="Records" rows={rows} rowKey={row => row.id}
  columns={[{key: 'name', header: 'Name', render: row => row.name}]} />
<Pagination total={total} pageSize={20} page={page} onPageChange={setPage} />
```

## Verification

Run from `frontend`: `npm test`, `npm run lint -- --max-warnings 0`, `npm run build`, `npm audit`.

**Automated tests (40 across 15 files).** Component tests cover explicit-id labels, icon-button loading, semantic alerts, unique Card title ids, table semantics/empty results, pagination invalid sizes and bounds, modal cancel/backdrop versus panel clicks, legacy submit compatibility, and the lazy showcase. DOM tests use jsdom and Testing Library; the existing API/validation tests keep the node environment.

`src/design-tokens.test.ts` walks the whole source tree rather than a hand-written file list, because two palette mistakes are invisible to both the compiler and the linter:

- a utility whose token is undefined. Tailwind v4 emits **nothing** for `text-warning-800` when only `--color-warning-700` exists, so the element silently renders with no colour. The test resolves every `bg-/text-/border-…` token reference against the `--color-*` definitions in `index.css`.
- a stock Tailwind colour slipping back in. The test fails on any `slate/emerald/red/amber/...` utility anywhere in `src`.

Both checks were confirmed to fail on the real defects before the fixes landed.

**Real-browser checks.** 26 Playwright checks against the production build in Chromium, all passing with zero unexpected console or page errors: modal open/Escape/backdrop-versus-panel click/close button with focus restored to the trigger each time, `:modal` focus trapping and background inertness, pagination across 3 pages on both the showcase and a 45-row admin table, label/hint/error wiring and the disabled `aria-busy` submit state, no sideways scrolling on any route at 375px with the admin table scrolling inside its own box, the mobile menu, login redirect-back, and the consumer-versus-admin role guard.

> These browser checks ran against a **stub API**, not the FastAPI backend: `backend/` needs PostgreSQL 16 and its own test suite needs Docker (testcontainers), neither of which was available. Everything above verifies frontend behaviour and the shape of the API contract. **End-to-end verification against the real backend is still outstanding** and should happen before this module is signed off.
