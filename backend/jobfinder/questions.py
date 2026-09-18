from __future__ import annotations

import sqlite3

from jobfinder import db
from jobfinder.adapters import registry
from jobfinder.models import RawJob


def harvest_matched(conn: sqlite3.Connection) -> int:
    """Pull question schemas for every open, matched posting whose adapter
    exposes one. Greenhouse does; most others return None from
    fetch_questions() and are silently skipped -- that's expected, not an
    error.
    """
    rows = conn.execute(
        "SELECT s.source_uid, s.adapter, s.board_token, s.apply_url "
        "FROM sightings s JOIN jobs j ON j.content_hash = s.content_hash "
        "WHERE j.status = 'new'",
    ).fetchall()

    harvested = 0
    for row in rows:
        try:
            adapter_cls = registry.get(row["adapter"])
        except KeyError:
            continue

        external_id = row["source_uid"].rsplit(":", 1)[-1]
        stub = RawJob(
            adapter=row["adapter"],
            company="",
            board_token=row["board_token"],
            external_id=external_id,
            title="",
            location="",
            url=row["apply_url"] or "",
        )

        try:
            found = adapter_cls().fetch_questions(stub)
        except Exception:
            continue
        if not found:
            continue

        db.add_questions(conn, row["source_uid"], found)
        harvested += 1

    return harvested


def print_novel_report(novel: list[dict]) -> None:
    if not novel:
        print("no novel required questions")
        return
    for item in novel:
        print(f"[{item['count']:>3} jobs] {item['label']!r} ({item['field_type']})")
