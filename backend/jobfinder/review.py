from __future__ import annotations

import sqlite3
import webbrowser

from jobfinder import db

PROMPT = "     (q)ueue  (s)kip  (o)pen in browser  (n)ext  (b)ack  (Q)uit: "


def format_job(row: sqlite3.Row) -> str:
    location = f" — {row['location']}" if row["location"] else ""
    return f"{row['company']} — {row['title']}{location}\n     {row['best_apply_url'] or ''}"


def review_loop(
    conn: sqlite3.Connection,
    jobs: list[sqlite3.Row],
    *,
    ask=input,
    opener=webbrowser.open,
    printer=print,
) -> None:
    i = 0
    while 0 <= i < len(jobs):
        row = jobs[i]
        printer(format_job(row))
        action = ask(PROMPT).strip()

        if action == "q":
            db.set_status(conn, row["content_hash"], "queued")
            i += 1
        elif action == "s":
            db.set_status(conn, row["content_hash"], "skipped")
            i += 1
        elif action == "o":
            if row["best_apply_url"]:
                opener(row["best_apply_url"])
        elif action == "n":
            i += 1
        elif action == "b":
            i = max(0, i - 1)
        elif action == "Q":
            return


def run(conn: sqlite3.Connection) -> None:
    jobs = db.new_jobs_by_score(conn)
    if not jobs:
        print("nothing to review")
        return
    review_loop(conn, jobs)
