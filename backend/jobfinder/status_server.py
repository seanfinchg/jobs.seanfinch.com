from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jobfinder.engine import DB_PATH, RUN_LOCK_MAX_AGE_SECONDS

# Not on the public internet -- no auth, no personal data (board health and
# scrape progress only, never job content or the answer bank). Meant to be
# reachable only from a private network; never expose this port publicly.
PORT = int(os.environ.get("JOBFINDER_STATUS_PORT", "8787"))

LOCK_PATH = Path(str(DB_PATH) + ".run-lock")
PROGRESS_PATH = Path(str(DB_PATH) + ".scrape-progress.json")
LAST_SCRAPE_PATH = Path(os.environ.get("JOBFINDER_DATA_DIR", "/data")) / "last-scrape-epoch"

# Real boards finish in low single-digit seconds to about a minute (even a
# huge Workday tenant with hundreds of paginated requests lands well under
# this). Found the hard way on 2026-10-02: a single board hung for 9+ hours
# with zero network activity and nothing on the dashboard said so -- it just
# kept showing the last board that *had* completed, looking perfectly
# healthy. This is a separate, earlier warning than RUN_LOCK_MAX_AGE_SECONDS
# (which means "abandon and allow a redeploy to recreate the container") --
# this one means "still within the no-redeploy window, but worth a human
# looking at."
STALL_WARNING_SECONDS = 10 * 60


def _read_progress() -> dict | None:
    if not PROGRESS_PATH.exists():
        return None
    try:
        return json.loads(PROGRESS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _lock_age_seconds() -> float | None:
    if not LOCK_PATH.exists():
        return None
    return time.time() - LOCK_PATH.stat().st_mtime


def _is_scraping() -> bool:
    age = _lock_age_seconds()
    return age is not None and age < RUN_LOCK_MAX_AGE_SECONDS


def _last_scrape_iso() -> str | None:
    if not LAST_SCRAPE_PATH.exists():
        return None
    try:
        epoch = float(LAST_SCRAPE_PATH.read_text().strip())
    except (OSError, ValueError):
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _board_health_summary() -> dict:
    """Read-only against the live DB -- board_health is written by engine.py
    mid-run, so this needs to tolerate reading while a write is in flight
    rather than lock the writer out (SQLite's WAL mode already makes that
    safe, see docker-entrypoint.sh's own symlink comment for why the DB
    lives on the persistent volume in the first place)."""
    if not Path(DB_PATH).exists():
        return {"total_boards": 0, "failing": [], "total_jobs": None}
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        total_boards = conn.execute("SELECT COUNT(*) FROM board_health").fetchone()[0]
        failing = [
            dict(row)
            for row in conn.execute(
                """SELECT adapter, board_token, last_ok, last_error FROM board_health
                   WHERE last_error IS NOT NULL ORDER BY adapter, board_token LIMIT 50"""
            ).fetchall()
        ]
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        return {"total_boards": total_boards, "failing": failing, "total_jobs": total_jobs}
    finally:
        conn.close()


def _in_flight_seconds(progress: dict | None) -> float | None:
    if not progress or not progress.get("in_flight_since"):
        return None
    since = datetime.fromisoformat(progress["in_flight_since"])
    return (datetime.now(timezone.utc) - since).total_seconds()


def build_status() -> dict:
    progress = _read_progress()
    health = _board_health_summary()
    in_flight_seconds = _in_flight_seconds(progress)
    return {
        "scraping": _is_scraping(),
        "progress": progress,
        "in_flight_seconds": in_flight_seconds,
        "stalled": in_flight_seconds is not None and in_flight_seconds > STALL_WARNING_SECONDS,
        "last_scrape_at": _last_scrape_iso(),
        "board_health": health,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _render_html(status: dict) -> str:
    progress = status["progress"]
    if status["scraping"] and progress:
        pct = round(100 * progress["boards_done"] / progress["boards_total"]) if progress["boards_total"] else 0
        in_flight_seconds = status["in_flight_seconds"]
        if in_flight_seconds is not None:
            board_line = (
                f"-- currently fetching <code>{progress['adapter']}:{progress['token']}</code> "
                f"(started {round(in_flight_seconds)}s ago)"
            )
            stall_html = (
                f"""<p style="color:#e07b39;"><strong>Possibly stalled</strong> --
                    no activity on this board for over {round(in_flight_seconds / 60)} minute(s),
                    well past how long any real board has taken historically.</p>"""
                if status["stalled"]
                else ""
            )
        else:
            board_line = f"-- last completed <code>{progress['adapter']}:{progress['token']}</code>"
            stall_html = ""
        progress_html = f"""
        <p><strong>Scraping now</strong> -- profile <code>{progress['profile']}</code></p>
        <p>Board {progress['boards_done']} of {progress['boards_total']} ({pct}%) {board_line}</p>
        {stall_html}
        <p>{progress['total_stored']} posting(s) stored/updated so far this run, started {progress['started_at']}</p>
        """
    elif progress:
        progress_html = f"""
        <p><strong>Idle</strong> -- last run (<code>{progress['profile']}</code>) finished
           {progress.get('finished_at', 'unknown')}</p>
        <p>{progress['boards_done']} of {progress['boards_total']} boards,
           {progress['total_stored']} posting(s) stored/updated</p>
        """
    else:
        progress_html = "<p>No scrape has run yet since this container started.</p>"

    failing_rows = "".join(
        f"<tr><td>{f['adapter']}</td><td>{f['board_token']}</td>"
        f"<td>{f['last_ok'] or '&mdash;'}</td><td>{f['last_error']}</td></tr>"
        for f in status["board_health"]["failing"]
    )
    failing_html = (
        f"<table><thead><tr><th>Adapter</th><th>Board</th><th>Last OK</th><th>Last error</th></tr></thead>"
        f"<tbody>{failing_rows}</tbody></table>"
        if failing_rows
        else "<p>No boards currently failing.</p>"
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="15">
<title>jobfinder status</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #e5e5e5; padding: 2rem; max-width: 800px; margin: 0 auto; }}
code {{ background: #2a2a2a; padding: 0.1rem 0.3rem; border-radius: 3px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #333; font-size: 0.85rem; }}
h1 {{ font-size: 1.3rem; }} h2 {{ font-size: 1rem; color: #aaa; margin-top: 2rem; }}
</style></head>
<body>
<h1>jobfinder scrape status</h1>
{progress_html}
<h2>Last completed scrape</h2>
<p>{status['last_scrape_at'] or 'never'}</p>
<h2>Total jobs in DB</h2>
<p>{status['board_health']['total_jobs']}</p>
<h2>Board health -- {len(status['board_health']['failing'])} of {status['board_health']['total_boards']} currently failing</h2>
{failing_html}
<p style="color:#666; font-size:0.8rem; margin-top:2rem;">Checked {status['checked_at']} -- refreshes every 15s.</p>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # the container's own stdout is for scrape progress, not HTTP access logs

    def do_GET(self) -> None:  # noqa: N802
        status = build_status()
        if self.path == "/health.json":
            body = json.dumps(status).encode("utf-8")
            content_type = "application/json"
        else:
            body = _render_html(status).encode("utf-8")
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    ThreadingHTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()  # noqa: S104


if __name__ == "__main__":
    serve()
