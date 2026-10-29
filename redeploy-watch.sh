#!/bin/sh
set -eu

# Run this on the deploy host itself, on a schedule (cron, every 5-10
# minutes), not inside the app container. Rebuilding requires control of
# the host's Docker daemon; the "obvious" way to give a container that is
# mounting /var/run/docker.sock into it, which hands that container
# root-equivalent control of the whole host -- a real privilege escalation
# just to save an SSH session. A host-side cron job running the same
# `docker compose` commands you'd type by hand keeps that privilege where
# it already belongs.
#
# This directory is a real git checkout, not a hand-copy of the source
# tree, so pushing to the deploy branch is the whole update mechanism.
#
# SECURITY: whatever lands on the deploy branch is built and run on this
# host, with the deploy credentials in .env in scope. That branch must stay
# protected (pull request required, no force-push, only the maintainer can
# merge); never point DEPLOY_BRANCH at a branch outside contributors' reach
# to write to.
DEPLOY_BRANCH="${DEPLOY_BRANCH:-prod}"

cd "$(dirname "$0")"

git fetch origin "$DEPLOY_BRANCH" --quiet

LOCAL_HEAD=$(git rev-parse HEAD)
REMOTE_HEAD=$(git rev-parse "origin/$DEPLOY_BRANCH")

if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) no new commits, skipping rebuild"
    exit 0
fi

# `docker compose up -d --build` recreates the container outright, which
# kills whatever engine.run() was doing mid-flight -- and since a scrape has
# no per-board checkpoint, the next start re-fetches every board from #1,
# not just the ones it hadn't reached yet. Repeatedly interrupting a scrape
# this way is exactly the repeated-request pattern that gets a client
# rate-limited by the sites it scrapes.
# engine.py's own run-lock (jobfinder.db.run-lock, next to the db inside the
# container -- not on the shared volume, hence checking via `exec` rather
# than a host-side file test) already exists to stop concurrent runs; reused
# here as "is a scrape actually in flight right now." `find -mmin -30`
# matches engine.py's own RUN_LOCK_MAX_AGE_SECONDS (30 minutes -- the lock's
# mtime is touched on every board completion now, so this measures "no
# activity recently," not "running longer than X"; a real run can legitimately
# take many hours). A container that isn't running at all (first-ever
# deploy) fails this check too, which correctly falls through to rebuilding
# since there's nothing to interrupt.
LIVE_LOCK=$(docker compose exec -T jobfinder find jobfinder.db.run-lock -mmin -30 2>/dev/null || true)
if [ -n "$LIVE_LOCK" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $DEPLOY_BRANCH moved but a scrape is in progress, deferring rebuild"
    exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $DEPLOY_BRANCH moved ($LOCAL_HEAD -> $REMOTE_HEAD), rebuilding and restarting"
git reset --hard "origin/$DEPLOY_BRANCH"
# NETLIFY_AUTH_TOKEN/NETLIFY_SITE_ID come from a .env file in this same
# directory (docker compose loads it automatically, and it's gitignored so
# `git reset --hard` never touches it) rather than being passed inline here,
# so a cron-triggered run picks them up the same way a manual
# `docker compose up` would -- cron jobs don't inherit your shell
# environment, so anything passed inline on the command line only would
# silently vanish the moment this runs unattended.
docker compose up -d --build
