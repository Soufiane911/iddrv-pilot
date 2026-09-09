# Pilot deployment

The Delivery workflow builds images tagged with the exact `workflow_run.head_sha`.
It only executes SSH promotion when the protected `pilot` environment sets
`DEPLOY_ENABLED=true`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, and
`DEPLOY_KNOWN_HOSTS`. Otherwise it reports **not deployed**; no dry-run is
reported as a successful release.

The pilot host must provide `OWNER_DATABASE_URL`, `API_DATABASE_URL`, and
`WORKER_DATABASE_URL` (three distinct PostgreSQL credentials), plus the session
secret and GHCR pull credentials as environment/secrets for `compose.pilot.yml`.
The API and worker URLs are wired to their respective containers; neither
runtime container receives the owner URL. The manifest pins
its internal web gateway to `172.31.0.10/32` as the only trusted proxy; override
`TRUSTED_PROXY_IPS` only when the network layout is changed accordingly. SSH host-key
verification is strict. `deploy-pilot.sh` pulls the immutable images, runs the
owner migration/runtime-role setup, starts the services, waits for `/ready`,
and records the current/previous image SHAs in `.last-image-tag` and
`.previous-image-tag`. Collector/scorer and the file worker are healthchecked;
all runtime services must become healthy before recording success.
`ROLLBACK_SCHEMA_COMPATIBLE=true deploy-pilot.sh rollback` performs an image-only
rollback after an operator has verified schema compatibility; it never runs
old migrations or removes volumes. If `.pending-image-tag` exists after an
incomplete attempt, rollback restores `.last-image-tag` (last known-good), not
`.previous-image-tag`. Without pending, it restores `.previous-image-tag`.
For example, last=A / previous=B / pending=C recovers A and keeps previous=B;
a normal successful rollback from last=A / previous=B restores B and records
previous=A. Pending is cleared only after runtime health/readiness succeeds.
A failed recovery remains retryable; missing last-good or invalid recorded SHAs
are refused before Docker runs. Schema confirmation and the host lock apply to
both modes. Deployment failure does not automatically
restore a partially updated stack. See [operations evidence and local sandbox](../docs/certification/operations.md)
for reproducible tests, limitations and the explicitly local alert channel.
