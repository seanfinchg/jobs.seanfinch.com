from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

from jobfinder import normalize
from jobfinder.models import RawJob, source_uid

# Schema evolves as an ordered list of migrations rather than one mutable
# CREATE TABLE block. This DB used to live only in a disposable CI cache;
# now it's meant to persist indefinitely, so it needs to be
# upgradeable in place instead of assuming a fresh file every time.
MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS jobs (
            content_hash TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            location_bucket TEXT,
            best_apply_url TEXT,
            best_is_native INTEGER NOT NULL DEFAULT 0,
            body TEXT,
            score INTEGER,
            reasons TEXT,
            posted_at TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            profile TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS sightings (
            source_uid TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL REFERENCES jobs(content_hash),
            adapter TEXT NOT NULL,
            board_token TEXT NOT NULL,
            apply_url TEXT,
            is_native INTEGER NOT NULL,
            last_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS board_health (
            adapter TEXT NOT NULL,
            board_token TEXT NOT NULL,
            last_ok TEXT,
            last_error TEXT,
            job_count INTEGER,
            PRIMARY KEY (adapter, board_token)
        );

        CREATE TABLE IF NOT EXISTS questions (
            source_uid TEXT NOT NULL,
            name TEXT NOT NULL,
            label TEXT,
            norm_label TEXT,
            field_type TEXT,
            required INTEGER,
            values_json TEXT,
            PRIMARY KEY (source_uid, name)
        );

        CREATE TABLE IF NOT EXISTS answers (
            pattern TEXT PRIMARY KEY,
            answer TEXT,
            field_type TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS applications (
            content_hash TEXT PRIMARY KEY REFERENCES jobs(content_hash),
            submitted_at TEXT,
            outcome TEXT,
            notes TEXT
        );
    """),
    (2, """
        ALTER TABLE jobs ADD COLUMN salary_min INTEGER;
        ALTER TABLE jobs ADD COLUMN salary_max INTEGER;
    """),
    (3, """
        ALTER TABLE jobs ADD COLUMN level TEXT;
        ALTER TABLE jobs ADD COLUMN matched_fields TEXT;
    """),
    (4, """
        ALTER TABLE jobs ADD COLUMN matched_subfields TEXT;
    """),
    (5, """
        ALTER TABLE jobs ADD COLUMN grad_year INTEGER;
    """),
    (6, """
        -- Normalizes what used to be jobs.matched_fields/matched_subfields
        -- (JSON text blobs, unindexable) into real join tables, so "every
        -- finance job" or "every appsec-tagged job" is an indexed lookup
        -- instead of a full-table scan plus a JSON parse per row. This
        -- matters once postings span more than one discipline (finance,
        -- mechanical engineering, ... alongside CS) instead of one. The
        -- JSON columns stay for now as the dashboard export's read path;
        -- these tables are the fast query path underneath.
        CREATE TABLE IF NOT EXISTS fields (
            slug TEXT PRIMARY KEY,
            label TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subfields (
            field_slug TEXT NOT NULL REFERENCES fields(slug),
            tag TEXT NOT NULL,
            label TEXT NOT NULL,
            PRIMARY KEY (field_slug, tag)
        );

        CREATE TABLE IF NOT EXISTS job_fields (
            content_hash TEXT NOT NULL REFERENCES jobs(content_hash),
            field_slug TEXT NOT NULL REFERENCES fields(slug),
            PRIMARY KEY (content_hash, field_slug)
        );
        CREATE INDEX IF NOT EXISTS idx_job_fields_field ON job_fields(field_slug);

        CREATE TABLE IF NOT EXISTS job_subfields (
            content_hash TEXT NOT NULL REFERENCES jobs(content_hash),
            field_slug TEXT NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (content_hash, field_slug, tag),
            FOREIGN KEY (field_slug, tag) REFERENCES subfields(field_slug, tag)
        );
        CREATE INDEX IF NOT EXISTS idx_job_subfields_tag ON job_subfields(field_slug, tag);

        -- Hot paths that were doing full scans: open_jobs()/new_jobs_by_score()
        -- filter on status every call, close_stale_sightings() looks up by
        -- (adapter, board_token) once per board every run.
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_sightings_adapter_board ON sightings(adapter, board_token);
    """),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_fields(conn: sqlite3.Connection, fields_dir: Path) -> None:
    """Mirrors each profiles/fields/<slug>.yaml's label:/subfields: into the
    fields/subfields tables, so job_fields/job_subfields can carry real
    foreign keys instead of a hand-parsed JSON array. The YAML stays the
    source of truth (same file classify.py already reads for matching) --
    this just keeps a queryable copy in the DB. Call once per run/reclassify,
    before any upsert_job()/set_job_fields() call, so the foreign keys below
    always resolve."""
    for path in sorted(Path(fields_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        slug = path.stem
        label = data.get("label") or slug
        conn.execute(
            "INSERT INTO fields (slug, label) VALUES (?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET label = excluded.label",
            (slug, label),
        )
        for sf in data.get("subfields") or []:
            conn.execute(
                "INSERT INTO subfields (field_slug, tag, label) VALUES (?, ?, ?) "
                "ON CONFLICT(field_slug, tag) DO UPDATE SET label = excluded.label",
                (slug, sf["tag"], sf.get("label") or sf["tag"]),
            )
    conn.commit()


def set_job_fields(
    conn: sqlite3.Connection,
    content_hash: str,
    field_slugs: list[str],
    subfield_pairs: list[tuple[str, str]],
) -> None:
    """Replaces this job's job_fields/job_subfields rows with the given set --
    called on every upsert/reclassify so a job whose classification changes
    (a tightened field pattern, a new subfield) doesn't keep stale rows.
    subfield_pairs is (field_slug, tag), not a bare tag list -- a tag string
    is only unique within its own field, not globally.

    Doesn't assume sync_fields() already registered every slug here -- a
    profile can point classify.py at a different fields_dir than the one
    sync_fields() was called with (real in tests, which use an isolated
    tmp_path profiles dir while classify.py's cache may already be warm
    from the real one), so any field_slug/tag not yet in fields/subfields
    gets a slug-as-label placeholder row rather than failing the foreign
    key. sync_fields()'s real label (if it runs for this dir) always wins
    on conflict, since it unconditionally overwrites the label."""
    for slug in field_slugs:
        conn.execute("INSERT OR IGNORE INTO fields (slug, label) VALUES (?, ?)", (slug, slug))
    for field_slug, tag in subfield_pairs:
        conn.execute("INSERT OR IGNORE INTO fields (slug, label) VALUES (?, ?)", (field_slug, field_slug))
        conn.execute(
            "INSERT OR IGNORE INTO subfields (field_slug, tag, label) VALUES (?, ?, ?)",
            (field_slug, tag, tag),
        )

    conn.execute("DELETE FROM job_fields WHERE content_hash = ?", (content_hash,))
    conn.execute("DELETE FROM job_subfields WHERE content_hash = ?", (content_hash,))
    for slug in field_slugs:
        conn.execute(
            "INSERT OR IGNORE INTO job_fields (content_hash, field_slug) VALUES (?, ?)",
            (content_hash, slug),
        )
    for field_slug, tag in subfield_pairs:
        conn.execute(
            "INSERT OR IGNORE INTO job_subfields (content_hash, field_slug, tag) VALUES (?, ?, ?)",
            (content_hash, field_slug, tag),
        )
    conn.commit()


def jobs_for_field(conn: sqlite3.Connection, field_slug: str) -> list[sqlite3.Row]:
    """Every open job tagged with this field, via the indexed join table --
    the fast path the JSON matched_fields column can't offer."""
    return conn.execute(
        """SELECT jobs.* FROM jobs
           JOIN job_fields ON job_fields.content_hash = jobs.content_hash
           WHERE job_fields.field_slug = ? AND jobs.status NOT IN ('closed', 'skipped')
           ORDER BY jobs.first_seen DESC""",
        (field_slug,),
    ).fetchall()


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    current = row[0] if row else 0

    for version, sql in MIGRATIONS:
        if version <= current:
            continue
        conn.executescript(sql)
        current = version

    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (current,))
    else:
        conn.execute("UPDATE schema_version SET version = ?", (current,))
    conn.commit()


def upsert_job(
    conn: sqlite3.Connection,
    job: RawJob,
    *,
    profile: str,
    is_native: bool,
    salary_min: int | None = None,
    salary_max: int | None = None,
    level: str | None = None,
    matched_fields: list[str] | None = None,
    matched_subfields: list[str] | None = None,
    grad_year: int | None = None,
    now: str | None = None,
) -> str:
    now = now or _now()
    uid = source_uid(job)
    hash_ = normalize.content_hash(job.company, job.title, job.location, job.team)

    sighting = conn.execute(
        "SELECT content_hash FROM sightings WHERE source_uid = ?", (uid,)
    ).fetchone()
    target_hash = sighting["content_hash"] if sighting else hash_

    job_row = conn.execute(
        "SELECT best_apply_url, best_is_native FROM jobs WHERE content_hash = ?",
        (target_hash,),
    ).fetchone()

    matched_fields_json = json.dumps(matched_fields or [])
    matched_subfields_json = json.dumps(matched_subfields or [])

    if job_row is None:
        conn.execute(
            """INSERT INTO jobs
               (content_hash, company, title, location, location_bucket, best_apply_url,
                best_is_native, body, posted_at, first_seen, last_seen,
                status, profile, notes, salary_min, salary_max, level, matched_fields,
                matched_subfields, grad_year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, '', ?, ?, ?, ?, ?, ?)""",
            (
                target_hash, job.company, job.title, job.location,
                normalize.location_bucket(job.location), job.url, int(is_native),
                job.body, job.posted_at, now, now, profile,
                salary_min, salary_max, level, matched_fields_json, matched_subfields_json,
                grad_year,
            ),
        )
    else:
        # first native source to show up wins the apply link; once native,
        # never downgrade back to an aggregator link.
        if is_native and not job_row["best_is_native"]:
            best_apply_url, best_is_native = job.url, 1
        else:
            best_apply_url, best_is_native = job_row["best_apply_url"], job_row["best_is_native"]
        conn.execute(
            """UPDATE jobs SET last_seen = ?,
               best_apply_url = ?, best_is_native = ?, salary_min = ?, salary_max = ?,
               level = ?, matched_fields = ?, matched_subfields = ?, grad_year = ?
               WHERE content_hash = ?""",
            (now, best_apply_url, best_is_native,
             salary_min, salary_max, level, matched_fields_json, matched_subfields_json,
             grad_year, target_hash),
        )

    if sighting:
        conn.execute(
            "UPDATE sightings SET apply_url = ?, is_native = ?, last_seen = ? WHERE source_uid = ?",
            (job.url, int(is_native), now, uid),
        )
    else:
        conn.execute(
            """INSERT INTO sightings
               (source_uid, content_hash, adapter, board_token, apply_url, is_native, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid, target_hash, job.adapter, job.board_token, job.url, int(is_native), now),
        )

    conn.commit()
    return target_hash


def touch_sighting(conn: sqlite3.Connection, uid: str, now: str) -> None:
    """Refresh last_seen for a sighting that's still listed on its board even
    though this run's profile filtered it out. Without this, switching to a
    stricter profile on a shared DB would make close_stale_sightings think
    perfectly live jobs from a looser profile had disappeared."""
    conn.execute("UPDATE sightings SET last_seen = ? WHERE source_uid = ?", (now, uid))
    conn.commit()


def close_stale_sightings(conn: sqlite3.Connection, adapter: str, board_token: str, run_started_at: str) -> int:
    """Call once per board, only for a board whose fetch succeeded this run.

    A sighting not refreshed since run_started_at means the board no longer
    lists it. The job itself only flips to closed if none of its *other*
    sightings (any adapter) are fresh as of this run either -- otherwise it's
    still open via another source.
    """
    stale = conn.execute(
        "SELECT source_uid, content_hash FROM sightings "
        "WHERE adapter = ? AND board_token = ? AND last_seen < ?",
        (adapter, board_token, run_started_at),
    ).fetchall()

    closed = 0
    for row in stale:
        fresh = conn.execute(
            "SELECT 1 FROM sightings WHERE content_hash = ? AND last_seen >= ? LIMIT 1",
            (row["content_hash"], run_started_at),
        ).fetchone()
        if fresh:
            continue
        current = conn.execute(
            "SELECT status FROM jobs WHERE content_hash = ?", (row["content_hash"],)
        ).fetchone()
        if current and current["status"] == "new":
            conn.execute("UPDATE jobs SET status = 'closed' WHERE content_hash = ?", (row["content_hash"],))
            closed += 1
    conn.commit()
    return closed


def record_board_health(
    conn: sqlite3.Connection,
    adapter: str,
    board_token: str,
    *,
    ok: bool,
    error: str | None = None,
    job_count: int = 0,
    now: str | None = None,
) -> None:
    now = now or _now()
    if ok:
        conn.execute(
            """INSERT INTO board_health (adapter, board_token, last_ok, last_error, job_count)
               VALUES (?, ?, ?, NULL, ?)
               ON CONFLICT(adapter, board_token) DO UPDATE SET
                   last_ok = excluded.last_ok, last_error = NULL, job_count = excluded.job_count""",
            (adapter, board_token, now, job_count),
        )
    else:
        conn.execute(
            """INSERT INTO board_health (adapter, board_token, last_ok, last_error, job_count)
               VALUES (?, ?, NULL, ?, 0)
               ON CONFLICT(adapter, board_token) DO UPDATE SET last_error = excluded.last_error""",
            (adapter, board_token, error),
        )
    conn.commit()


def get_job(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM jobs WHERE content_hash = ?", (content_hash,)).fetchone()


def list_sightings(conn: sqlite3.Connection, content_hash: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sightings WHERE content_hash = ?", (content_hash,)
    ).fetchall()


def sighting_urls(conn: sqlite3.Connection, content_hash: str) -> list[str]:
    """Every distinct apply URL a job was seen at, across all its sources --
    not just the single best_apply_url jobs.best_apply_url collapses to."""
    rows = conn.execute(
        "SELECT DISTINCT apply_url FROM sightings "
        "WHERE content_hash = ? AND apply_url IS NOT NULL AND apply_url != ''",
        (content_hash,),
    ).fetchall()
    return [row["apply_url"] for row in rows]


def open_jobs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM jobs WHERE status NOT IN ('closed', 'skipped') ORDER BY first_seen DESC"
    ).fetchall()


def queued_jobs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM jobs WHERE status = 'queued'").fetchall()


def new_jobs_by_score(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Name is legacy (scoring was removed) -- newest-discovered first."""
    return conn.execute("SELECT * FROM jobs WHERE status = 'new' ORDER BY first_seen DESC").fetchall()


def set_status(conn: sqlite3.Connection, content_hash: str, status: str) -> None:
    conn.execute("UPDATE jobs SET status = ? WHERE content_hash = ?", (status, content_hash))
    conn.commit()


def add_questions(conn: sqlite3.Connection, uid: str, questions: list[dict]) -> None:
    for q in questions:
        norm_label = normalize.norm(q.get("label", ""))
        conn.execute(
            """INSERT INTO questions (source_uid, name, label, norm_label, field_type, required, values_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_uid, name) DO UPDATE SET
                   label = excluded.label, norm_label = excluded.norm_label,
                   field_type = excluded.field_type, required = excluded.required,
                   values_json = excluded.values_json""",
            (
                uid, q.get("name", ""), q.get("label", ""), norm_label,
                q.get("field_type", ""), int(bool(q.get("required"))),
                json.dumps(q.get("values", [])),
            ),
        )
    conn.commit()


def seed_answer(
    conn: sqlite3.Connection,
    pattern: str,
    answer: str,
    field_type: str = "input_text",
    now: str | None = None,
) -> None:
    now = now or _now()
    conn.execute(
        """INSERT INTO answers (pattern, answer, field_type, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(pattern) DO UPDATE SET answer = excluded.answer, field_type = excluded.field_type""",
        (pattern, answer, field_type, now),
    )
    conn.commit()


def get_answer(conn: sqlite3.Connection, norm_label: str) -> sqlite3.Row | None:
    for row in conn.execute("SELECT * FROM answers").fetchall():
        if re.search(row["pattern"], norm_label):
            return row
    return None


def is_placeholder_answer(answer: str) -> bool:
    """A seeded "TODO: fill in yourself" entry (see scripts/seed_answers.py)
    matches a pattern but isn't a real answer -- it should still show up as
    novel/unanswered rather than be silently treated as handled."""
    return (answer or "").strip().upper().startswith("TODO")


def unanswered_questions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT source_uid, label, norm_label, field_type FROM questions WHERE required = 1"
    ).fetchall()

    novel: dict[str, dict] = {}
    for row in rows:
        match = get_answer(conn, row["norm_label"])
        if match is not None and not is_placeholder_answer(match["answer"]):
            continue
        key = row["norm_label"]
        if key not in novel:
            novel[key] = {
                "norm_label": key,
                "label": row["label"],
                "field_type": row["field_type"],
                "count": 0,
                "example_source_uid": row["source_uid"],
            }
        novel[key]["count"] += 1
    return sorted(novel.values(), key=lambda d: -d["count"])


def record_application(
    conn: sqlite3.Connection,
    content_hash: str,
    *,
    outcome: str,
    notes: str = "",
    now: str | None = None,
) -> None:
    now = now or _now()
    conn.execute(
        """INSERT INTO applications (content_hash, submitted_at, outcome, notes)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(content_hash) DO UPDATE SET
               submitted_at = excluded.submitted_at, outcome = excluded.outcome, notes = excluded.notes""",
        (content_hash, now, outcome, notes),
    )
    conn.commit()
