#!/usr/bin/env bash
# Executed on the pilot host by the gated Delivery workflow.
set -Eeuo pipefail

: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${GHCR_OWNER:?GHCR_OWNER is required}"
: "${DEPLOY_PATH:?DEPLOY_PATH is required}"

cd "$DEPLOY_PATH"
compose=(docker compose -f "$DEPLOY_PATH/compose.pilot.yml")

# `rollback` uses the previous immutable image only; it never invents a tag.
target_tag="$IMAGE_TAG"
if [[ "${1:-}" == rollback ]]; then
  [[ -f "$DEPLOY_PATH/.previous-image-tag" ]] || {
    echo "No previous image SHA is recorded; rollback refused." >&2
    exit 2
  }
  target_tag="$(tr -d '[:space:]' < "$DEPLOY_PATH/.previous-image-tag")"
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
if [[ -n "$previous_tag" && "$previous_tag" != "$target_tag" ]]; then
  printf '%s\n' "$previous_tag" > "$DEPLOY_PATH/.previous-image-tag"
fi
printf '%s\n' "$target_tag" > "$DEPLOY_PATH/.pending-image-tag"
export IMAGE_TAG="$target_tag"

# Pull is intentionally explicit: deployment never builds from a mutable tag.
"${compose[@]}" pull
"${compose[@]}" up --abort-on-container-exit --exit-code-from migrate migrate
"${compose[@]}" up -d api worker web

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

mv "$DEPLOY_PATH/.pending-image-tag" "$DEPLOY_PATH/.last-image-tag"
echo "Pilot deployed at immutable SHA $target_tag. Previous SHA: ${previous_tag:-none}."
