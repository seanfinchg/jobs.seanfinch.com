#!/bin/sh
set -eu

# jobfinder.db lives on a mounted volume (JOBFINDER_DATA_DIR, defaulting to
# /data) instead of the container's own ephemeral filesystem -- a symlink
# keeps engine.py's relative Path("jobfinder.db") working unmodified rather
# than adding a --db-path flag this repo doesn't otherwise need.
DATA_DIR="${JOBFINDER_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
ln -sf "$DATA_DIR/jobfinder.db" jobfinder.db

# Runs for the whole container lifetime, independent of the scrape/deploy
# loop below -- reads jobfinder.db.run-lock/.scrape-progress.json (see
# engine.py) to answer "is it scraping right now, and how far along," which
# was previously only visible by tailing container logs. Not on the public
# internet: reachable only from wherever this box's own ports already are
# (a private network) via docker-compose.yml's port mapping, no auth needed
# since it exposes board health/progress only, never job content.
python -m jobfinder.status_server &

INTERVAL="${JOBFINDER_INTERVAL_SECONDS:-86400}"

# Scraping (many ATS API calls, 30-40 minutes) and deploying (fast: an
# already-scraped export, a static build, a netlify-cli push) used to be one
# fused function, run in full on every container start. That meant a
# code-only redeploy (redeploy-watch.sh rebuilding the image after a git
# change) paid the full scrape cost before the new code ever reached
# Netlify. This timestamp -- persisted on the same volume as jobfinder.db,
# so it survives a rebuild -- lets a restart tell "it's actually time to
# scrape again" apart from "I was just restarted for a code change," so only
# the former re-runs the scrape.
LAST_SCRAPE_FILE="$DATA_DIR/last-scrape-epoch"

seconds_until_next_scrape() {
    if [ ! -f "$LAST_SCRAPE_FILE" ]; then
        echo 0  # never scraped -- due immediately
        return
    fi
    last=$(cat "$LAST_SCRAPE_FILE")
    now=$(date +%s)
    remaining=$((INTERVAL - (now - last)))
    [ "$remaining" -gt 0 ] && echo "$remaining" || echo 0
}

scrape() {
    python -m jobfinder run --profile new-grad-cs --questions
    python -m jobfinder run --profile broad-cs
    # Writes frontend/public/meta.json's generated_at -- the site's "jobs
    # last updated" timestamp -- so it only ever advances on a real scrape,
    # never on a code-only deploy that reused the existing data.
    python -m jobfinder dashboard
    date +%s > "$LAST_SCRAPE_FILE"
}

deploy() {
    # jobfinder.db lives on the persistent volume (see the symlink above)
    # and survives a rebuild; data.json/meta.json/fields.json don't (see
    # .dockerignore -- they're deliberately never baked into the image, so
    # a stale snapshot can't silently ship). Regenerating them here from the
    # already-persisted DB means a code-only redeploy (no new scrape) still
    # has real data to build from, instead of frontend/public/ being empty
    # in the freshly-built image. --generated-at keeps meta.json's "jobs
    # last updated" timestamp honest -- it reports the last REAL scrape,
    # not whenever this regeneration happened to run, unless nothing has
    # ever scraped yet (no LAST_SCRAPE_FILE), in which case there's no real
    # timestamp to report and dashboard falls back to its own default.
    if [ -f "$LAST_SCRAPE_FILE" ]; then
        generated_at=$(date -u -d "@$(cat "$LAST_SCRAPE_FILE")" +%Y-%m-%dT%H:%M:%SZ)
        python -m jobfinder dashboard --generated-at "$generated_at"
    else
        python -m jobfinder dashboard
    fi

    (cd ../frontend && npm run build)

    if [ -n "${NETLIFY_AUTH_TOKEN:-}" ] && [ -n "${NETLIFY_SITE_ID:-}" ]; then
        # `--prefix ../frontend` alone does NOT change npx's working
        # directory (only where it resolves node_modules from), so
        # --dir=dist would resolve against backend/ instead of the
        # frontend/dist that npm run build just populated -- cd into
        # frontend the same way the build step above does.
        (cd ../frontend && npx netlify deploy --prod --dir=dist \
            --auth "$NETLIFY_AUTH_TOKEN" --site "$NETLIFY_SITE_ID")
    else
        echo "NETLIFY_AUTH_TOKEN / NETLIFY_SITE_ID not set -- built frontend/dist but skipped deploy" >&2
    fi
}

while true; do
    remaining=$(seconds_until_next_scrape)
    if [ "$remaining" -le 0 ]; then
        scrape || echo "scrape failed, will retry next cycle" >&2
        remaining="$INTERVAL"
    else
        echo "next scrape due in ${remaining}s -- deploying current data with current code now"
    fi
    deploy || echo "deploy failed" >&2
    sleep "$remaining"
done
