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
# This directory is a real git checkout (cloned via a repo-scoped,
# read-only deploy key in a local key file -- see ~/.ssh/config's
# github.com Host block), not a hand-copy of the source tree. Only rebuilds
# when origin/master has actually moved, so pushing to GitHub is the whole
# update mechanism now.

cd "$(dirname "$0")"

git fetch origin master --quiet

LOCAL_HEAD=$(git rev-parse HEAD)
REMOTE_HEAD=$(git rev-parse origin/master)

if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) no new commits, skipping rebuild"
    exit 0
fi

# `docker compose up -d --build` recreates the container outright, which
# kills whatever engine.run() was doing mid-flight -- and since a scrape has
# no per-board checkpoint, the next start re-fetches every board from #1,
# not just the ones it hadn't reached yet. Repeatedly interrupting a scrape
# this way is exactly the repeated-request pattern that got this project's
# client rate-limited once already.
# engine.py's own run-lock (jobfinder.db.run-lock, next to the db inside the
# container -- not on the shared volume, hence checking via `exec` rather
# than a host-side file test) already exists to stop concurrent runs; reused
# here as "is a scrape actually in flight right now." A container that isn't
# running at all (first-ever deploy) fails this check too, which correctly
# falls through to rebuilding since there's nothing to interrupt.
if docker compose exec -T jobfinder test -f jobfinder.db.run-lock 2>/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) origin/master moved but a scrape is in progress, deferring rebuild"
    exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) origin/master moved ($LOCAL_HEAD -> $REMOTE_HEAD), rebuilding and restarting"
git reset --hard origin/master
# NETLIFY_AUTH_TOKEN/NETLIFY_SITE_ID come from a .env file in this same
# directory (docker compose loads it automatically, and it's gitignored so
# `git reset --hard` never touches it) rather than being passed inline here,
# so a cron-triggered run picks them up the same way a manual
# `docker compose up` would -- cron jobs don't inherit your shell
# environment, so anything passed inline on the command line only would
# silently vanish the moment this runs unattended.
docker compose up -d --build
