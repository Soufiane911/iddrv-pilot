# Registre de preuves frontend

| Claim | Source | Confidence | Allowed wording | Usage |
|---|---|---:|---|---|
| IDDRV reconciles ERP and machine-cycle data | Repository README and implementation plan | High | Describe the implemented ingestion/reconciliation purpose | Product descriptions |
| IDDRV presents incidents, hypotheses, and persisted evidence | Existing API, pages, and implementation plan | High | Exact functional wording only | Overview and investigation UI |
| The pilot runs on-premise | `docs/implementation-status.md` and Compose configuration | High | “Pilote local” or “déploiement on-premise” | Shell and administration |
| Production authentication uses an HttpOnly cookie | Backend auth contract and `frontend/src/lib/api.ts` | High | Describe cookie session; never claim browser token storage | Login and protected routes |
| OpenAI runtime integration is active | Missing; explicitly deferred | 0 | MUST NOT USE | Omit |
| OPC UA is connected | Missing; explicitly preview-only | 0 | MUST NOT USE | Omit |
| Browser file upload transfers and profiles file contents | Current frontend only registers metadata | 0 | MUST NOT USE | Workspace must say preview/metadata only |
| Any displayed economic saving is validated | Missing | 0 | MUST NOT USE | Opportunity/demo figures must be labeled fictitious |
| Any customer count, testimonial, award, certification, ROI, or benchmark | Missing | 0 | MUST NOT USE | Omit |
| Machine, incident, import, quality, and evidence values | Runtime API responses | Contextual | Display exact returned values with state/source/time labels | Operational pages |
| Showroom S001 values are production observations | Frontend demonstration model | 0 | MUST NOT USE | Must be labeled fictitious demonstration data |
| The application controls industrial presses | Missing and prohibited during pilot | 0 | MUST NOT USE | Omit |
| Replay cutoff is a source-data timestamp | `last_cycle_at` from machine status and incident `data_cutoff`; frontend replay tests | High | Say “horodatage source” only after one of these values is available | Workshop replay |
| Import completion time is a valid replay cutoff | Backend `last_import_at` is processing time | 0 | MUST NOT USE | Workshop must not anchor replay to it |
| Watched-folder output is automatically linked to a browser workspace | No correlation contract in the current worker | 0 | MUST NOT USE | Workspace explicitly describes metadata-only preview and unavailable validation |
| A persisted investigation is readable after reload | Backend `GET /investigations/{run_id}` when the run ID is retained in the URL | High | Qualify readability by the run-bearing URL and authorized site scope; reject runs bound to another incident | Incident detail |
| Write permissions are global for every authorized site | Backend returns and enforces `site_roles` | 0 | MUST NOT USE | Derive investigation, feedback, and workspace controls from the role for the current site |
| Product is validated in the field | Missing; pilot is only ready to qualify | 0 | MUST NOT USE | Omit |

## Validation evidence

- `fix-ai-slop --check frontend`: 0 em-dashes; three deterministic false positives where the scanner interprets JavaScript `import.meta` as the company name “Meta”.
- `analyze-layout.mjs .`: 0 blockers. Its two warnings are Tailwind-only heuristics; this frontend keeps responsive breakpoints and font sizes in authored CSS.
- `impeccable detect frontend/src`: no findings.
- Browser audits cover 375px, 1024px, and 1440px without horizontal overflow or WCAG axe violations; the opt-in 3D view is also checked at mobile, tablet, and desktop widths.
- Final frontend verification: ESLint passed, 50 Vitest tests passed, standard production build passed, and the opt-in 3D build passed. The isolated Three.js chunk remains intentionally lazy and triggers Vite’s size warning only when enabled.
- Repository verification on a dedicated `iddrv_test` database: `python -m pytest -q` passes all 166 tests, including 53 database/Redis E2E cases. The pilot database is not truncated by this suite.
- The complete Compose stack is running locally with healthy PostgreSQL, Redis, API and web services; the worker is running. Local secrets live only in Git-ignored `.env` with mode `0600`.
- Real cookie-authenticated browser coverage through the Nginx gateway validates login, logout, overview, sites, workshop, incidents, incident detail, imports, workspace and health at 375px, 1024px and 1440px: zero axe violations, zero horizontal overflow, zero undersized controls, zero page errors and zero server 5xx responses.
- `npm audit` against the official registry reports 0 vulnerabilities after removing unused ECharts and upgrading Vitest to 4.1.10.
- E2E cleanup now refuses non-local databases, database names without the `_test` suffix, and Redis databases other than local DB 1. The E2E runner redacts URL credentials from console and report output.
- Compose consumes an explicit `DOCKER_DATABASE_URL`, so reserved password characters can be URL-encoded without breaking API or worker startup.
