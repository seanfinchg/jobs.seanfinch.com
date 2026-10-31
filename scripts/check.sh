#!/usr/bin/env bash
# The same checks CI's `check` job runs. Install dependencies first (see
# docs/getting-started.md); this script only runs the checks, so it stays fast.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== backend: tests"
(cd backend && python -m pytest -q)

echo "== frontend: tests and build"
(cd frontend && npm test --if-present && npm run build)

echo "OK"
