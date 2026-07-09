# IDDRV implementation status

## Active execution

- Branch: `codex/iddrv-pilot`
- Plan: `docs/orchestrated-implementation-plan.md`
- Current gate: **G1 — dataset réaliste intégral en base**
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

## Next gate

G1 is ready to start. It requires three workers with non-overlapping ownership:
`iddrv_data_worker`, `iddrv_backend_worker`, and `iddrv_frontend_worker`.
