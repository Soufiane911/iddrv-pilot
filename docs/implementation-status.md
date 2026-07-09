# IDDRV implementation status

## Active execution

- Branch: `codex/iddrv-pilot`
- Plan: `docs/orchestrated-implementation-plan.md`
- Current gate: **G3 — interface atelier 2D**
- State: **READY TO START**
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

## Next gate

G3 is ready to start: workshop 2D with a real API client, state colors, machine
selection and incident side panel.

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
