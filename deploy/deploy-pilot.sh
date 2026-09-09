#!/usr/bin/env bash
# Executed on the pilot host by the gated Delivery workflow.
set -Eeuo pipefail

: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${GHCR_OWNER:?GHCR_OWNER is required}"
: "${DEPLOY_PATH:?DEPLOY_PATH is required}"

cd "$DEPLOY_PATH"
compose=(docker compose -f "$DEPLOY_PATH/compose.pilot.yml")

# Serialize tag bookkeeping and migration on this host.
mkdir "$DEPLOY_PATH/.deploy-lock" 2>/dev/null || {
  echo 'Deployment lock exists; concurrent deployment refused.' >&2; exit 2;
}
trap 'rmdir "$DEPLOY_PATH/.deploy-lock"' EXIT
case "${1:-deploy}" in deploy|rollback) ;; *) echo 'Expected deploy or rollback' >&2; exit 2 ;; esac

# Validate persisted state before selecting or overwriting any tag.
for tag_file in .last-image-tag .previous-image-tag .pending-image-tag; do
  if [[ -e "$DEPLOY_PATH/$tag_file" ]]; then
    recorded_tag="$(tr -d '[:space:]' < "$DEPLOY_PATH/$tag_file")"
    [[ "$recorded_tag" =~ ^[0-9a-f]{40}$ ]] || {
      echo "Invalid immutable SHA in $tag_file; deployment refused." >&2; exit 2;
    }
  fi
done

# Pending means an incomplete attempt, not a successful release. Recover the
# last known-good image in that case; otherwise undo the last successful release.
target_tag="$IMAGE_TAG"
if [[ "${1:-}" == rollback ]]; then
  rollback_file=.previous-image-tag
  if [[ -e "$DEPLOY_PATH/.pending-image-tag" ]]; then
    rollback_file=.last-image-tag
  fi
  [[ -f "$DEPLOY_PATH/$rollback_file" ]] || {
    echo "No known-good image SHA in $rollback_file; rollback refused." >&2
    exit 2
  }
  target_tag="$(tr -d '[:space:]' < "$DEPLOY_PATH/$rollback_file")"
  [[ "${ROLLBACK_SCHEMA_COMPATIBLE:-false}" == true ]] || {
    echo 'Rollback requires operator confirmation ROLLBACK_SCHEMA_COMPATIBLE=true; no schema downgrade is performed.' >&2
    exit 2
  }
fi
if [[ ! "$DEPLOY_PATH" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  echo "Refusing deployment: DEPLOY_PATH contains unsupported characters." >&2
  exit 2
fi
if [[ ! "$target_tag" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Refusing deployment: image tag must be a full commit SHA." >&2
  exit 2
fi

# Keep both immutable tags available to an operator for image rollback.
previous_tag=""
if [[ -f "$DEPLOY_PATH/.last-image-tag" ]]; then
  previous_tag="$(tr -d '[:space:]' < "$DEPLOY_PATH/.last-image-tag")"
fi
printf '%s\n' "$target_tag" > "$DEPLOY_PATH/.pending-image-tag"
export IMAGE_TAG="$target_tag"

# Pull is intentionally explicit: deployment never builds from a mutable tag.
"${compose[@]}" pull
# Do not use --abort-on-container-exit with database dependencies: it stops them.
"${compose[@]}" up -d --wait --wait-timeout 180 timescaledb redis
if [[ "${1:-deploy}" != rollback ]]; then
  "${compose[@]}" run --rm --no-deps migrate
fi
# Migration was explicitly run above; rollback must not rerun an old migration.
"${compose[@]}" up -d --no-deps --wait --wait-timeout 180 api worker collector scorer web

ready=false
for _ in {1..30}; do
  if "${compose[@]}" exec -T api python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=3)" \
      >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo "Pilot readiness probe failed; deployment is not considered successful." >&2
  exit 1
fi

# Recovery to last-good must preserve its predecessor (A/B stays A/B).
# A successful normal rollback rotates the pair, just like a deployment.
if [[ -n "$previous_tag" && "$previous_tag" != "$target_tag" ]]; then
  printf '%s\n' "$previous_tag" > "$DEPLOY_PATH/.previous-image-tag"
fi
mv "$DEPLOY_PATH/.pending-image-tag" "$DEPLOY_PATH/.last-image-tag"
echo "Pilot deployed at immutable SHA $target_tag. Previous SHA: ${previous_tag:-none}."
