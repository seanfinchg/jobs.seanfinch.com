from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

from jobfinder import classify, db, defense, featured

# The React app lives in ../frontend (a sibling of this package's repo,
# backend/) and reads this at runtime via fetch("data.json").
DASHBOARD_PUBLIC_DIR = Path("..") / "frontend" / "public"

# Allowlist, not a denylist -- anything not named here never leaves the
# private DB. In particular: no answers, no resume, no application status,
# no notes, no internal profile/reasons fields. content_hash is exposed
# only as an opaque row id (a hash of company+title+location, not personal
# data) -- gives the frontend a stable React key and lets it look up every
# apply_url a job was seen at, not just the single best one.
PUBLIC_FIELDS = [
    "content_hash", "company", "title", "location",
    "best_apply_url", "first_seen", "posted_at", "salary_min", "salary_max",
    "level", "matched_fields", "matched_subfields", "grad_year",
]


def _load_fields_metadata(fields_dir: Path = classify.FIELDS_DIR) -> list[dict]:
    """Per-field display metadata for the dashboard's role filter -- a
    field's slug, label, and its {tag, label} subfields, read straight off
    profiles/fields/*.yaml so a new field file needs no frontend edit to
    show up with a real label instead of its raw slug."""
    fields = []
    for path in sorted(fields_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        label = data.get("label")
        if not label:
            continue
        subfields = [
            {"tag": sf["tag"], "label": sf.get("label", sf["tag"])}
            for sf in (data.get("subfields") or [])
        ]
        fields.append({"slug": path.stem, "label": label, "subfields": subfields})
    return fields


def export_data(
    conn: sqlite3.Connection,
    docs_dir: Path = DASHBOARD_PUBLIC_DIR,
    *,
    generated_at: str | None = None,
) -> Path:
    docs_dir.mkdir(parents=True, exist_ok=True)
    # last_seen DESC, not a relevance score -- the ranking-bonus system this
    # used to sort by is gone; most-recently-confirmed-open is the closest
    # sensible substitute (the frontend's own default sort is by posted
    # date, so this only matters as the pre-sort order data.json ships in).
    rows = conn.execute(
        f"SELECT {', '.join(PUBLIC_FIELDS)} FROM jobs "
        "WHERE status NOT IN ('closed', 'skipped') ORDER BY last_seen DESC"
    ).fetchall()

    data = []
    for row in rows:
        entry = dict(row)
        content_hash = entry.pop("content_hash")
        entry["id"] = content_hash
        entry["apply_urls"] = db.sighting_urls(conn, content_hash)
        entry["featured"] = featured.is_featured(entry["company"])
        entry["defense"] = defense.is_defense_surveillance(entry["company"])
        entry["matched_fields"] = json.loads(entry["matched_fields"] or "[]")
        entry["matched_subfields"] = json.loads(entry["matched_subfields"] or "[]")
        data.append(entry)

    out_path = docs_dir / "data.json"
    out_path.write_text(json.dumps(data, indent=2))

    # Separate from data.json on purpose -- data.json's shape is a bare
    # array (the frontend fetches it straight into Job[]), so run metadata
    # goes in its own small file rather than changing that contract. This is
    # meant to be "when the last real scrape finished," not "whenever this
    # function happened to run" -- export_data() is also called from
    # docker-entrypoint.sh's deploy() to regenerate data.json/fields.json
    # from the already-persisted DB on a code-only redeploy (no new fetch),
    # which must NOT make the site's "jobs last updated" timestamp lie about
    # a scrape that didn't happen. Callers that just finished a real scrape
    # pass their own current-time string; callers regenerating from
    # already-scraped data pass the real last-scrape timestamp instead (see
    # docker-entrypoint.sh's deploy()). Defaults to now for plain ad hoc
    # `jobfinder dashboard` CLI usage, which has no other timestamp to use.
    meta_path = docs_dir / "meta.json"
    meta_path.write_text(json.dumps({"generated_at": generated_at or datetime.now(timezone.utc).isoformat()}))

    # Also separate from data.json: per-field display metadata (label,
    # subfields) doesn't change per job row, so it belongs in its own file
    # rather than repeated on every entry in the array.
    fields_path = docs_dir / "fields.json"
    fields_path.write_text(json.dumps(_load_fields_metadata(), indent=2))

    return out_path
