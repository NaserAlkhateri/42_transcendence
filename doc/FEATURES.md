# Sijil - Platform Overview and Features

## What Sijil does
Sijil is a UAE-focused **demo** vehicle service-history web app. Approved workshops and dealerships add service/repair events for a VIN; consumers look up a VIN, see the decoded car details and its history, download a vehicle-only PDF, and watch VINs for future records. Outside businesses read histories through a key-protected partner API. It is not connected to official UAE vehicle databases.

**Launch constraints:** 3 weeks; demo records; English + Arabic with complete RTL; in-app notifications delivered live over WebSocket; email/password login; no SMTP; runs fully offline (VIN decoding is richer when online). Google OAuth and authenticator-app 2FA are optional, not MVP commitments.

## Users and permissions
| Role | Key features |
| --- | --- |
| Consumer | Register/login, search VIN, see decoded car details, filter history, view mileage and flags, download PDF, watch/unwatch VIN, read in-app alerts, manage account. |
| Entity staff | Log in under an approved entity, find VIN, add maintenance/repair event using predefined options, enter mileage, submit linked correction, see own entity records. |
| Entity admin | All entity-staff actions; upload licence documents at registration; manage entity profile, add/edit/remove staff members, assign allowed roles and review entity submissions. |
| Platform admin | Approve/reject entities after reviewing their licence documents, delete documents, create/edit/delete organizations, view/edit/delete user accounts and manage roles, issue/revoke partner API keys, review flags/disputes, view platform audit events. |
| API partner | Holds an admin-issued key (no login). Reads vehicle summaries and histories and manages its own VIN watchlist through the partner API. Cannot write vehicle history. |

Consumers cannot create vehicle service records. Staff cannot see another organization's private data. A platform admin cannot rewrite historical events; corrections remain visible.

## Main user journeys
1. **Consumer:** sign up -> search valid VIN -> see decoded car details and timeline (including warnings) -> download PDF or watch an empty VIN -> receive a live in-app alert (WebSocket, no refresh) when a new record arrives.
2. **Entity:** submit organization registration with trade licence upload -> platform admin previews the documents and approves -> entity admin creates staff account -> staff logs in -> selects VIN and service type/work codes -> enters odometer -> submits append-only record.
3. **Correction:** staff links a corrective event to an earlier event -> report shows original and correction together with clear labels.
4. **Mileage anomaly:** a value lower than the latest effective prior mileage is accepted, marked as suspicious, listed in admin review and visibly flagged to consumers.
5. **Platform admin:** reviews pending businesses and their documents, flagged events, organizations, users and partner keys, and inspects audit history without editing vehicle history.
6. **API partner:** platform admin issues a key -> partner calls the vehicle summary/history endpoints and manages its watchlist -> polls `GET /watches` to see which VINs have new records.

## Feature scope
### Core (must be demo-ready)
- Account registration/login, logout and profile; secure passwords and sessions.
- Entity registration with licence document upload, pending/approved/rejected states, and full organization/member management (create, edit, delete organizations; add/remove members).
- Live updates over WebSocket: notifications and new records on an open timeline appear for all connected users without refresh; clients reconnect after drops.
- Role- and organization-scoped permission checks for every API and screen.
- VIN lookup with decoded car details (offline decode, enriched from NHTSA vPIC when reachable) and a sorted/filterable vehicle timeline; no-result state with watchlist action.
- Immutable service/repair records, append-only corrections and transactional mileage flags.
- Consumer-safe PDF report with decoded car details, record sources and conspicuous anomaly markers.
- Responsive React UI; English/Arabic switch; true layout mirroring in Arabic.
- Privacy Policy and Terms of Service linked from UI footer (actual content, not placeholders).
- Docker Compose/HTTPS, .env example, safe error handling, and a reliable multi-user demo.

### Module-completion scope (prioritize by evaluation points)
- **Real-time features (WebSockets):** live updates across clients, graceful connect/disconnect with auto-reconnect, efficient broadcasting through Redis pub/sub.
- **Public partner API:** six documented endpoints (GET vehicle summary, GET vehicle history, GET/POST/PUT/DELETE partner watches), keys issued by the platform admin with read-only scope, revocation and observable rate limiting.
- **File management:** entity licence and trade documents (images and PDFs); client/server size/type checks, upload progress, preview, protected access, platform-admin-only delete with audit trail.
- **Advanced search:** filters, sorting and pagination, including a practical admin/workshop search.
- **Additional browsers:** test all flows in Firefox and Edge as well as mandatory Chrome; document exceptions.
- **Custom design system:** at least 10 reusable components with documented palette, typography and icons.
- **Complete notifications (stretch):** in-app notices for relevant creation, update **and deletion** actions (not only watchlist events), with read/unread state.
- **CSV/JSON import/export (stretch):** validate bulk workshop CSV imports, show row-level errors, support bulk operations, export data in at least CSV and JSON.

## Scope boundaries
- **No real integrations** with government, car dealers or insurer databases. The one external call is optional VIN decoding through the public NHTSA vPIC API; the app must work without it.
- **No sending emails:** alerts are in-app; no SMTP, email verification or emailed password reset.
- **Only two languages:** English and Arabic. This is enough for the RTL minor; the three-language minor is not claimed.
- Do **not** claim the GDPR minor: the subject requires confirmation emails for data operations. Still handle personal data carefully and provide accurate privacy/terms pages.
- Google OAuth and TOTP 2FA may be added after the 16-point core is stable; neither counts before fully implemented.
- No file attachments on service records; the only uploads are entity documents.
- No games, chat/friends, blockchain, microservices, Prometheus/Grafana monitoring, ELK or WAF/Vault modules.

## Acceptance tests for the most important promises
- Two workshops submit records to the same VIN concurrently: no race, lost write or inconsistent mileage comparison.
- A lower odometer reading appears in both timeline and PDF with a flag; the original is not silently removed.
- Correcting a record preserves original and correction and displays their relationship.
- Pending/rejected entities cannot submit records; staff cannot cross organization boundaries.
- Deleting an organization or user really removes it (and its memberships/access) while vehicle history still shows its records under the stored name.
- A record submitted in one browser appears live in another browser watching that VIN, including after a dropped connection reconnects.
- Consumers never receive customer names, contact details or entity documents in reports.
- An entity uploads its licence during registration; the platform admin previews it; an entity admin cannot delete it; the platform admin can, and an audit event is written.
- With the network disconnected, a VIN lookup still shows the manufacturer and model year from the offline decoder; with the network up, vPIC details are added and cached.
- All six partner API routes work with an authorized key; missing or revoked keys get 401; a burst gets 429; no partner call can change service records.
- English/Arabic switch mirrors layout; desktop/mobile and Chrome/Firefox/Edge journeys work.
