# IDDRV agent rules

## Source of truth

- Follow `docs/orchestrated-implementation-plan.md` and the current gate in `docs/implementation-status.md`.
- Do not use `.agents/` as current state; it is archived execution history.
- Do not advance to a later gate until the orchestrator marks the current gate PASS.

## Shared safety rules

- Work only inside the file ownership declared in the task briefing.
- Preserve user changes and unrelated work.
- Never run destructive Git commands or delete Docker volumes.
- Never commit unless the user explicitly asks you to. Before committing, run the full verification suite and stage only intended files. Never push or rewrite history.
- Use `apply_patch` for hand-written file changes.
- Keep secrets out of the repository and never print credentials.
- Do not add an OpenAI dependency or make OpenAI API calls before the deferred phase is explicitly activated.
- `data/scenarios/industrial_demo/ground_truth.json` is evaluation-only. Runtime code, prompts, containers, database tables, and application APIs must not read it.

## Ownership

- `iddrv_data_worker`: `db/`, `ingest/`, and data-ingestion tests explicitly assigned in its briefing.
- `iddrv_backend_worker`: `backend/`, except `backend/app/diagnostics/` when owned by the diagnostic worker.
- `iddrv_frontend_worker`: `frontend/`.
- `iddrv_diagnostic_worker`: `backend/app/diagnostics/`, diagnostic tests, and `evals/`.
- `iddrv_explorer` and `iddrv_reviewer`: read-only.
- Root manifests, `docker-compose.yml`, `.codex/`, `AGENTS.md`, shared contracts, status documents, and Git are orchestrator-only.

## Required handoff

Every implementation agent must report:

1. Outcome and whether the acceptance criterion is met.
2. Exact files changed.
3. Commands/tests run and their results.
4. Remaining risks, assumptions, or unverified behavior.
5. Any blocker requiring orchestrator or user action.

Do not claim completion without fresh verification.

## Baseline verification

Run the checks relevant to the assigned scope. The orchestrator owns the final cross-cutting run.

```bash
python -m pytest -q
docker compose config --quiet
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

