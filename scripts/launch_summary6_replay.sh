#!/usr/bin/env bash
# Server-only profile. Run in the exact private-package environment. No workers.
set -euo pipefail
cd "$(dirname "$0")/.."
export HDT_RUNTIME_MODE=summary6_replay
: "${SUMMARY6_PACKAGE_DIR:?Set private approved package directory}"
: "${SUMMARY6_MANIFEST_SHA256:?Set independently approved manifest pin}"
python - <<'PY'
from backend.app.services.summary6 import current
state = current()
if not state['replay_enabled']:
    raise SystemExit('Summary6 unavailable: '+','.join(state['reasons']))
print(state)
PY
exec python -m uvicorn backend.app.main:app --workers 1 --host 127.0.0.1 --port "${SUMMARY6_PORT:-8096}"
