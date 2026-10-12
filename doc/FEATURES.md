# Sijil - Platform Overview and Features

## What Sijil does
Sijil is a UAE-focused **demo** vehicle service-history web app. Approved workshops and dealerships add service/repair events for a VIN; consumers search history, download a vehicle-only PDF, and watch VINs for future records. It is not connected to official UAE vehicle databases.

**Launch constraints:** 3 weeks; demo records; English + Arabic with complete RTL; in-app notifications delivered live over WebSocket; email/password login; no SMTP. Google OAuth and authenticator-app 2FA are optional, not MVP commitments.

## Users and permissions
| Role | Key features |
| --- | --- |
| Consumer | Register/login, search VIN, filter history, view mileage and flags, download PDF, watch/unwatch VIN, read in-app alerts, manage account. |
| Entity staff | Log in under an approved entity, find VIN, add maintenance/repair event using predefined options, enter mileage, attach files, submit linked correction, see own entity records. |
| Entity admin | All entity-staff actions; manage entity profile, add/edit/remove staff members, assign allowed roles and review entity submissions. |
| Platform admin | Approve/reject entities, create/edit/delete organizations, view/edit/delete user accounts and manage roles, review flags/disputes, view platform audit events. |

Consumers cannot create vehicle service records. Staff cannot see another organization's private data. A platform admin cannot rewrite historical events; corrections remain visible.

## Main user journeys
1. **Consumer:** sign up -> search valid VIN -> see timeline (including warnings) -> download PDF or watch an empty VIN -> receive a live in-app alert (WebSocket, no refresh) when a new record arrives.
2. **Entity:** submit organization registration -> platform admin approves -> entity admin creates staff account -> staff logs in -> selects VIN and service type/work codes -> enters odometer -> uploads optional evidence -> submits append-only record.
3. **Correction:** staff links a corrective event to an earlier event -> report shows original and correction together with clear labels.
4. **Mileage anomaly:** a value lower than the latest effective prior mileage is accepted, marked as suspicious, listed in admin review and visibly flagged to consumers.
5. **Platform admin:** reviews pending businesses and flagged events, manages organizations/users, and inspects audit history without editing vehicle history.

## Feature scope
### Core (must be demo-ready)
- Account registration/login, logout and profile; secure passwords and sessions.
- Entity registration, pending/approved/rejected states, and full organization/member management (create, edit, delete organizations; add/remove members).
- Live updates over WebSocket: notifications and new records on an open timeline appear for all connected users without refresh; clients reconnect after drops.
- Role- and organization-scoped permission checks for every API and screen.
- VIN lookup and sorted/filterable vehicle timeline; no-result state with watchlist action.
- Immutable service/repair records, append-only corrections and transactional mileage flags.
- Consumer-safe PDF report with record sources and conspicuous anomaly markers.
- Responsive React UI; English/Arabic switch; true layout mirroring in Arabic.
- Privacy Policy and Terms of Service linked from UI footer (actual content, not placeholders).
- Docker Compose/HTTPS, .env example, safe error handling, and a reliable multi-user demo.

### Module-completion scope (prioritize by evaluation points)
- **Advanced search:** filters, sorting and pagination, including a practical admin/workshop search.
- **File management:** images and PDFs; client/server size/type checks, progress, preview, protected access, authorized delete and audit trail.
- **Public partner API:** at least five documented endpoints, GET/POST/PUT/DELETE, scoped API keys and rate limiting. Example: GET VIN summary, GET VIN history, POST partner watch, PUT partner watch preferences, DELETE partner watch.
- **Complete notifications:** in-app notices for relevant creation, update **and deletion** actions (not only watchlist events), with read/unread state.
- **CSV/JSON import/export:** validate bulk workshop CSV imports, show row-level errors, support bulk operations, export data in at least CSV and JSON.
- **Additional browsers:** test all flows in Firefox and Edge as well as mandatory Chrome; document exceptions.
- **Custom design system:** at least 10 reusable components with documented palette, typography and icons.
- **Monitoring:** Prometheus exporters/scraping, Grafana dashboards, alerting and protected access to qualify for its major module.

## Scope boundaries
- **No real integrations** with government, car dealers or insurer databases in the initial demo.
- **No sending emails:** alerts are in-app; no SMTP, email verification or emailed password reset.
- **Only two languages for now:** English and Arabic are fine for the app, but the three-language minor module cannot be claimed until a third full translation is delivered.
- Do **not** claim the GDPR minor: the subject requires confirmation emails for data operations. Still handle personal data carefully and provide accurate privacy/terms pages.
- Google OAuth and TOTP 2FA may be added after the 14-point core is stable; neither counts before fully implemented.
- No games, chat/friends, blockchain, microservices, ELK or WAF/Vault modules.

## Acceptance tests for the most important promises
- Two workshops submit records to the same VIN concurrently: no race, lost write or inconsistent mileage comparison.
- A lower odometer reading appears in both timeline and PDF with a flag; the original is not silently removed.
- Correcting a record preserves original and correction and displays their relationship.
- Pending/rejected entities cannot submit records; staff cannot cross organization boundaries.
- Deleting an organization or user really removes it (and its memberships/access) while vehicle history still shows its records under the stored name.
- A record submitted in one browser appears live in another browser watching that VIN, including after a dropped connection reconnects.
- Consumers never receive customer names, contact details or raw invoices in reports.
- Five partner API routes work with an authorized key and reject missing/revoked keys; rate limiting is observable.
- English/Arabic switch mirrors layout; desktop/mobile and Chrome/Firefox/Edge journeys work.
