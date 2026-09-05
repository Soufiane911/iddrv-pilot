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
`.previous-image-tag`; `deploy-pilot.sh rollback` performs an image rollback.
