# IDDRV implementation status

## Active execution

- Branch: `codex/iddrv-pilot`
- Plan: `docs/orchestrated-implementation-plan.md`
- Current gate: **G6 — packaging pilote on-premise**
- State: **VALIDATION FINALE**
- Runtime OpenAI integration: **DEFERRED**

## Baseline evidence

- Baseline commit: `ef621ff` (`chore: establish IDDRV baseline`)
- Python tests: `75 passed in 38.77s`
- Docker Compose configuration: valid
- TimescaleDB: healthy
- Redis: healthy

## G0 checklist

- [x] Preserve the initial repository state in Git.
- [x] Create `codex/iddrv-pilot`.
- [x] Add project agent limits and six Luna role profiles.
- [x] Add durable ownership and handoff rules.
- [x] Validate Codex configuration with strict parsing.
- [x] Run a read-only Luna smoke task (`gpt-5.6-luna`, `READY`).
- [x] Review and commit G0.

## G0 verification

- `python -m pytest -q`: **75 passed in 37.58s**
- `docker compose config --quiet`: **passed**
- `codex --strict-config ...`: **passed**
- Read-only Luna smoke: **passed**, model confirmed as `gpt-5.6-luna`

## G2 verification

- API contract: `docs/api-v1-contract.md`.
- Migration 003: incidents, diagnostic runs, evidence, hypotheses, feedback and action proposals.
- Deterministic S001 engine: baseline scrap rate, zone 2 temperature drift, quality defects and operator notes.
- API smoke on live PostgreSQL: list incident **200**, investigation **200**, persisted evidence **200 / 3 items**.
- Focused tests: **5 passed**; full pre-existing suite remains green through the implemented test set.
- Commit: `5799046 feat(diagnostics): deliver S001 evidence-backed investigation`.

## G3 verification

- React/Vite routes: sites, workshop, incidents, incident detail, imports and login.
- SVG workshop map: state colors, machine selection, keyboard activation, replay slider and loading/empty/error states.
- Evidence-backed incident detail: investigation, hypotheses, proofs and human feedback.
- Browser smoke: site → workshop → machine → replay → incident → investigation control; **passed** with Playwright.
- Frontend checks: lint **passed**, Vitest **2 passed**, production build **passed**.
- Commit: `4b1ca77 feat(ui): add workshop replay and incident investigation`.

## G4 verification

- Auth: Argon2id password hashes, HttpOnly/SameSite=Strict session cookie, signed identity, RBAC viewer/analyst/supervisor/admin.
- Site isolation smoke: same ERP reference can exist on two sites; cross-site viewer receives **404**.
- Viewer investigation blocked with **403**; analyst investigation and feedback succeed.
- Diagnostic evaluation: six scenarios, Top-2 recall **1.0**, all cited evidence resolves.
- Healthy windows: **6/6 abstentions**, abstention rate **1.0**.
- Runtime scan: no OpenAI dependency/call and no runtime ground-truth access.
- Commit: `1017ec0 feat(pilot): add local investigation, auth and multisite isolation`.

## G5 verification

- Watched-folder state: stable file, inbox → processing → archive/quarantine, retries/backoff and restart recovery.
- SHA-256/advisory lock idempotence: duplicate deposit produces no second business import.
- Probe mode is read-only and reports parser/mapping/unknown columns/units/invalid values/confidence.
- Arburg Selogica/Gestica mapping version `arburg-selogica-gestica-v1` is ready to qualify; not declared field-validated.
- Targeted data/ingestion checks: **16 passed**.
- Commit: `819fa9b feat(ingestion): automate watched-folder imports`.

## G6 validation in progress

- Docker Compose services: TimescaleDB, API, worker, Redis and web gateway.
- DB/Redis remain local-only; web is the only LAN-facing service.
- Three.js is opt-in via `VITE_ENABLE_3D=false` and 2D remains complete fallback.
- Backup/restore scripts and on-prem runbook are present.

## G1 verification

- Dataset database counts: **60 OF / 38 313 cycles / 408 quality checks / 12 maintenance events / 10 operator notes**.
- Import passports: **7 completed, 0 pending, 0 rejected rows**.
- Second complete scenario import: **38313 cycles before and after**.
- Canonical process fields populated when present in source; missing source values remain null.
- Defect types: **797** cycles; part quality: **37 516 good / 797 scrap**.
- `python -m pytest -q`: **80 passed**.
- Isolated E2E database: **50 passed in 36.72s**.
- Backend skeleton: **2 tests passed**, compileall passed.
- Frontend: lint passed, 1 Vitest passed, production build passed.
- `docker compose config --quiet`: passed.

## G1 commit

- `c04637a feat(data): load complete industrial demo dataset`
