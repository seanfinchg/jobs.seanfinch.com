#!/bin/sh
set -eu

# Run this on the deploy host itself, on a schedule (System Settings ->
# Advanced Settings -> Cron Jobs -- point it at this script's path, e.g.
# every 5-10 minutes), not inside the app container. Rebuilding requires
# control of the host's Docker daemon; the "obvious" way to give a
# container that is mounting /var/run/docker.sock into it, which hands
# that container root-equivalent control of the whole host -- a real
# privilege escalation just to save an SSH session. A host-side cron job
# running the same `docker compose` commands you'd type by hand keeps that
# privilege where it already belongs.
#
# Idempotent and cheap to run often: hashes the actual source files (not
# mtimes, which change on every copy regardless of content) and only
# rebuilds when that hash actually changes.

cd "$(dirname "$0")"

HASH_FILE=".last-deploy-hash"

CURRENT_HASH=$(find backend frontend Dockerfile docker-compose.yml docker-entrypoint.sh .dockerignore \
    -type f \
    ! -path "*/node_modules/*" ! -path "*/.venv/*" ! -path "*/dist/*" \
    ! -path "*/__pycache__/*" ! -path "*.egg-info/*" \
    ! -name "jobfinder.db*" ! -name "data.json" ! -name "meta.json" \
    -exec md5sum {} \; 2>/dev/null | sort | md5sum | cut -d' ' -f1)

PREVIOUS_HASH=$(cat "$HASH_FILE" 2>/dev/null || echo "")

if [ "$CURRENT_HASH" = "$PREVIOUS_HASH" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) no source changes, skipping rebuild"
    exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) source changed, rebuilding and restarting"
# NETLIFY_AUTH_TOKEN/NETLIFY_SITE_ID come from a .env file in this same
# directory (docker compose loads it automatically) rather than being
# passed inline here, so a cron-triggered run picks them up the same way
# a manual `docker compose up` would -- cron jobs don't inherit your shell
# environment, so anything passed inline on the command line only would
# silently vanish the moment this runs unattended.
docker compose up -d --build
echo "$CURRENT_HASH" > "$HASH_FILE"
