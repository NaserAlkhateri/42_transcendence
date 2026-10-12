# Sijil - Team, Work Distribution and Trello Plan

Timebox: **3 weeks maximum (15 working days)**. Team of four; everyone codes, tests and reviews. Each member owns 8 starting Trello cards with an **estimated** 36 effort points. Points reflect relative effort, not guaranteed equal hours; rebalance twice a week.

## Required 42 roles
Everyone is a **full-stack developer**: each member owns their features end to end (API + UI + tests) across all three weeks, on top of their 42 role.

| Member | Team role | Feature ownership (end to end) |
| --- | --- | --- |
| **Agegnew Mersha** | Project Manager / Full-stack Developer | Vehicle history: schema, VIN timeline, service records + mileage flags, corrections, PDF, advanced search, import/export |
| **Naser** | Product Owner / Full-stack Developer (Security) | Accounts and access: auth, users + roles, organizations, members/staff, partner API, security, policy pages |
| **Burhan** | Technical Lead / Architect / Full-stack Developer (DevOps) | Platform: Docker/Caddy/HTTPS, file uploads, WebSocket live updates, notifications, monitoring, CI/backups |
| **Hasan** | Full-stack Developer (Frontend) / QA Lead | UI foundation and experience: app shell, design system, EN/AR RTL, watchlist, admin review, entity dashboard, e2e/browser QA |

## Trello card ownership
### Agegnew - Vehicle history + PM (36 pts)
| Card | Task | Week | Estimate |
| --- | --- | :---: | ---: |
| AG-01 | Backend bootstrap, database schema, ORM migrations and demo seed | 1 | 5 |
| AG-02 | VIN lookup and vehicle timeline (API + page) | 1 | 5 |
| AG-03 | Service record submission with mileage flags (API + workshop form) | 2 | 5 |
| AG-04 | Corrections linked to original records (API + UI) | 2 | 3 |
| AG-05 | Consumer-safe PDF report (generation + download) | 2 | 3 |
| AG-06 | Advanced search with filters, sorting and pagination (API + UI) | 3 | 5 |
| AG-07 | CSV/JSON import and export (API + UI) - stretch | 3 | 5 |
| AG-08 | PM: Trello coordination, weekly demos, integration and README contributions | 3 | 5 |
| | **Total** | | **36** |

### Naser - Accounts, access + PO (36 pts)
| Card | Task | Week | Estimate |
| --- | --- | :---: | ---: |
| NA-01 | Signup, login, logout and profile (API + pages) | 1 | 5 |
| NA-02 | Users and roles: user CRUD and role-based views (API + admin UI) | 1 | 5 |
| NA-03 | Organizations: registration, approval and CRUD incl. delete (API + UI) | 2 | 5 |
| NA-04 | Organization members and staff accounts (API + UI) | 2 | 3 |
| NA-05 | Partner API with scoped keys, rate limiting and docs (API + key UI) | 2 | 5 |
| NA-06 | Security hardening and review | 3 | 5 |
| NA-07 | Privacy Policy and Terms of Service pages | 3 | 3 |
| NA-08 | PO: backlog, acceptance criteria and module sign-off | 3 | 5 |
| | **Total** | | **36** |

### Burhan - Platform + Tech Lead (36 pts)
| Card | Task | Week | Estimate |
| --- | --- | :---: | ---: |
| BU-01 | Architecture, repo layout and API/WebSocket contracts | 1 | 3 |
| BU-02 | Docker Compose, Caddy HTTPS and single-command start | 1 | 5 |
| BU-03 | File uploads: MinIO storage, upload API and upload UI | 2 | 5 |
| BU-04 | WebSocket live updates (server + client) | 2 | 5 |
| BU-05 | Notifications for create/update/delete actions (API + notification centre) | 2 | 5 |
| BU-06 | Deployment docs, README instructions and integration support | 3 | 3 |
| BU-07 | Prometheus and Grafana monitoring - stretch | 3 | 5 |
| BU-08 | CI, smoke tests, backups and hardening | 3 | 5 |
| | **Total** | | **36** |

### Hasan - UI foundation, experience + QA (36 pts)
| Card | Task | Week | Estimate |
| --- | --- | :---: | ---: |
| HA-01 | Frontend bootstrap: React/Vite/Tailwind, routing, app shell and API client | 1 | 3 |
| HA-02 | Custom design system (10+ components) | 1 | 5 |
| HA-03 | English/Arabic i18n and full RTL mirroring | 2 | 5 |
| HA-04 | Watchlist: watch/unwatch VINs (API + UI) | 2 | 3 |
| HA-05 | Admin review: flagged records queue and audit log (API + UI) | 2 | 5 |
| HA-06 | Entity dashboard: organization submissions and staff activity (API + UI) | 3 | 5 |
| HA-07 | Playwright e2e and Chrome/Firefox/Edge testing | 3 | 5 |
| HA-08 | Responsive, accessible UI and release bug triage | 3 | 5 |
| | **Total** | | **36** |

## Three-week milestones
| Week | Goal | Demonstration gate |
| --- | --- | --- |
| **1 - Foundation** | Container stack, HTTPS, DB migrations, agreed API contracts, auth/RBAC skeleton, React UI shell, demo seeds | From a fresh clone, single-command start; users log in; approved workshop and sample VIN exist. |
| **2 - Product** | Core service history/corrections/mileage flags, workshop/consumer/admin flows, PDF, uploads, watchlist, partner API, Arabic RTL | End-to-end service submission -> flagged customer report -> correction, with access controls. |
| **3 - Completion** | Module checklists, imports/exports, full notifications, monitoring/alerts, browser tests, concurrency/security tests, policies and README | Full 42 evaluation rehearsal; 14 verified points first, then stretch modules; code freeze before submission. |

## Trello workflow and definition of done
Board: https://trello.com/b/iRrhRK44 (Transcendence workspace). Columns: `Backlog -> To Do -> In Progress -> Review -> Done`, plus a pinned `📌 Info` list. Card IDs: `AG-` Agegnew, `NA-` Naser, `BU-` Burhan, `HA-` Hasan; week-1 cards start in To Do, the rest in Backlog, each due on the Friday of its milestone week.

Each card has one owner, an estimate and a target week. No more than two cards in progress per person. Re-estimate and rebalance every 3-4 days. Naser prioritizes features; Burhan resolves architecture questions; Agegnew facilitates delivery; Hasan coordinates QA. No one self-approves their own pull request.

A task is **Done** only when: requirements met, API/UI integrated as needed, tests passing, permissions checked, no browser-console errors, reviewer approved and relevant documentation updated. Unfinished modules earn zero points in the subject.

## Team communication and evaluation
- Short daily stand-up in Trello or team chat; planning/review at least weekly.
- Document decisions in the relevant file rather than multiplying documents.
- Track commits and PRs for all four contributors; each member must explain their implementation during evaluation.
- Update the README with **actual** individual contributions before submission, not just this proposed assignment.
