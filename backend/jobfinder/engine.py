from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from jobfinder import adapters as _adapters  # noqa: F401  (populates the registry)
from jobfinder import classify, db, questions, scoring
from jobfinder.adapters import registry
from jobfinder.adapters.base import Adapter
from jobfinder.models import RawJob, source_uid

logger = logging.getLogger(__name__)

DB_PATH = Path("jobfinder.db")
PROFILES_DIR = Path("profiles")

# A real run hits 150+ distinct external hosts (Greenhouse, Lever, Workday,
# ...) back to back with zero delay, and fetch_body's lazy per-job fetch
# (smartrecruiters, bamboohr) can add hundreds more within a single board --
# that back-to-back, many-host burst pattern is exactly what tripped a
# CDN-side bot/DDoS heuristic on a real run of this tool, blocking
# the client. These delays exist to keep this looking
# like a slow, ordinary client, not an absence-of-delay bug.
BOARD_FETCH_DELAY_SECONDS = 0.5
BODY_FETCH_DELAY_SECONDS = 0.2

# A real run can legitimately take many hours now (Workday's page size is
# capped at 20 by the real server, confirmed live -- a single large tenant
# needs well over a hundred paginated requests, each deliberately paced) --
# "stale" has to mean "no activity in a while," not "running longer than X,"
# or a long-but-genuinely-still-running scrape looks identical to a crashed
# one. The lock's mtime is touched alongside every progress write (see
# _write_progress's callers), so this threshold only needs to cover the
# gap between two board completions, not an entire run. Also what
# redeploy-watch.sh checks (via `find -mmin`) before deciding it's safe to
# rebuild -- keep that in sync with this if it ever changes.
RUN_LOCK_MAX_AGE_SECONDS = 30 * 60


class RunAlreadyInProgress(RuntimeError):
    """Raised by run() when a lock file shows another real run is active.

    Found the hard way: two concurrent `jobfinder run --profile broad-cs`
    processes against the same real DB doubled the actual request volume
    against every external host for no benefit (same boards, same result),
    and both had stale in-memory classify.py caches from before an
    unrelated fix landed, silently re-writing over-broad classifications.
    Nothing previously stopped this."""


def _run_lock_path(db_path: Path | str) -> Path | None:
    # Only real, persistent DB files need locking -- :memory: is exclusively
    # a test/isolated-check path (fake in-process adapters, no real network
    # calls), so it never has a concurrent-real-run problem to guard against.
    if str(db_path) == ":memory:":
        return None
    return Path(str(db_path) + ".run-lock")


def _acquire_run_lock(db_path: Path | str) -> Path | None:
    lock_path = _run_lock_path(db_path)
    if lock_path is None:
        return None
    if lock_path.exists():
        age = time.time() - lock_path.stat().st_mtime
        if age < RUN_LOCK_MAX_AGE_SECONDS:
            raise RunAlreadyInProgress(
                f"{lock_path} exists and is {age:.0f}s old (under the "
                f"{RUN_LOCK_MAX_AGE_SECONDS}s stale threshold) -- another "
                "run appears to already be in progress against this DB. "
                "Refusing to start a second one against the same real "
                "boards at the same time."
            )
        logger.warning("stale run lock at %s (%.0fs old) -- treating as abandoned, proceeding", lock_path, age)
    lock_path.write_text(datetime.now(timezone.utc).isoformat())
    return lock_path


def _progress_path(db_path: Path | str) -> Path | None:
    """Sibling of the run-lock, same :memory: exemption -- a running total
    the status server (see status_server.py) reads to answer "how far along
    is the current scrape," since board-by-board progress is otherwise only
    visible by tailing container logs."""
    if str(db_path) == ":memory:":
        return None
    return Path(str(db_path) + ".scrape-progress.json")


def _write_progress(path: Path | None, data: dict) -> None:
    if path is None:
        return
    path.write_text(json.dumps(data))


def _touch_run_lock(lock_path: Path | None) -> None:
    """Called alongside every _write_progress -- keeps the lock's mtime
    reflecting "last real activity," which is what RUN_LOCK_MAX_AGE_SECONDS
    actually measures against now, not "time since this run started"."""
    if lock_path is not None:
        lock_path.write_text(datetime.now(timezone.utc).isoformat())


def _release_run_lock(lock_path: Path | None) -> None:
    if lock_path is not None:
        lock_path.unlink(missing_ok=True)


def _substitute_grad_years(value):
    """Recursively replaces the `{grad_years}` placeholder token in any
    string loaded from a profile/level/field YAML with the real, current
    year-window regex (classify.grad_year_pattern()) -- computed once per
    load rather than baked into the YAML as a literal year."""
    if isinstance(value, str):
        return value.replace("{grad_years}", classify.grad_year_pattern())
    if isinstance(value, list):
        return [_substitute_grad_years(v) for v in value]
    if isinstance(value, dict):
        return {k: _substitute_grad_years(v) for k, v in value.items()}
    return value


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _substitute_grad_years(data)


# A profile's filters can come from three layers instead of being written
# out flat every time: at most one `level` file (profiles/levels/ --
# properties tied to a candidate's experience tier, not any particular
# career track) and any number of `fields` files (profiles/fields/, e.g.
# security vs. software-engineering vocabulary -- properties of a track, not
# of a tier), with the persona's own YAML layered on top last for anything
# genuinely personal (location preferences, ad hoc exclusions). A profile
# that doesn't declare `level`/`fields` behaves exactly as before: flat
# filters straight off its own YAML.
_LIST_FILTER_KEYS = [
    "title_include", "title_include_weak", "body_include_for_weak_title",
    "title_exclude", "location_include", "location_exclude", "body_exclude",
]


def _merge_filters(*filter_dicts: dict) -> dict:
    merged: dict[str, list[str]] = {}
    for key in _LIST_FILTER_KEYS:
        combined: list[str] = []
        for fd in filter_dicts:
            combined.extend(fd.get(key) or [])
        merged[key] = combined
    return merged


def load_profile(name: str, profiles_dir: Path = PROFILES_DIR) -> dict:
    profile = _load_yaml(profiles_dir / f"{name}.yaml")

    include = profile.pop("include", None)
    if include:
        include_paths = [include] if isinstance(include, str) else include
        boards: dict[str, list] = {}
        for path in include_paths:
            included = _load_yaml(profiles_dir.parent / path)
            for adapter_key, board_list in (included.get("boards") or {}).items():
                boards[adapter_key] = boards.get(adapter_key, []) + board_list
        for adapter_key, board_list in (profile.get("boards") or {}).items():
            boards[adapter_key] = boards.get(adapter_key, []) + board_list
        profile["boards"] = boards

    level_name = profile.pop("level", None)
    field_names = profile.pop("fields", None) or []

    if level_name or field_names:
        level_layer = _load_yaml(profiles_dir / "levels" / f"{level_name}.yaml") if level_name else {}
        field_layers = {name: _load_yaml(profiles_dir / "fields" / f"{name}.yaml") for name in field_names}
        persona_layer = profile  # own filters apply last, always active

        layers = [level_layer, *field_layers.values(), persona_layer]
        profile["filters"] = _merge_filters(*(layer.get("filters") or {} for layer in layers))

    return profile


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in patterns)


def passes_filters(job: RawJob, filters: dict) -> bool:
    title_include = filters.get("title_include") or []
    title_include_weak = filters.get("title_include_weak") or []
    body_include_for_weak_title = filters.get("body_include_for_weak_title") or []
    title_exclude = filters.get("title_exclude") or []
    location_include = filters.get("location_include") or []
    location_exclude = filters.get("location_exclude") or []
    body_exclude = filters.get("body_exclude") or []

    if title_exclude and _matches_any(job.title, title_exclude):
        return False

    if title_include or title_include_weak:
        matches_strong = bool(title_include) and _matches_any(job.title, title_include)
        matches_weak = bool(title_include_weak) and _matches_any(job.title, title_include_weak)
        if not (matches_strong or matches_weak):
            return False
        # A weak-only match (a generic title with no explicit security
        # signal) needs the body to back it up. No body_include_for_weak_title
        # configured means the weak tier is trusted as-is.
        if matches_weak and not matches_strong and body_include_for_weak_title:
            if not _matches_any(job.body, body_include_for_weak_title):
                return False

    if location_exclude and _matches_any(job.location, location_exclude):
        return False
    if location_include and not _matches_any(job.location, location_include):
        return False
    if body_exclude and _matches_any(job.body, body_exclude):
        return False
    return True


def _passes_title_and_location_filters(job: RawJob, filters: dict) -> bool:
    """Subset of passes_filters() that never needs body text -- used as a
    cheap pre-check before an adapter's optional fetch_body() call, so the
    lazy body fetch only ever runs for a posting that already looks
    relevant on title/location alone. Doesn't enforce the weak-tier's
    body-backup requirement (that needs body); passes_filters() is still
    the authoritative check once body is available."""
    title_include = filters.get("title_include") or []
    title_include_weak = filters.get("title_include_weak") or []
    title_exclude = filters.get("title_exclude") or []
    location_include = filters.get("location_include") or []
    location_exclude = filters.get("location_exclude") or []

    if title_exclude and _matches_any(job.title, title_exclude):
        return False
    if title_include or title_include_weak:
        if not (_matches_any(job.title, title_include) or _matches_any(job.title, title_include_weak)):
            return False
    if location_exclude and _matches_any(job.location, location_exclude):
        return False
    if location_include and not _matches_any(job.location, location_include):
        return False
    return True


def run(
    profile_name: str,
    *,
    harvest_questions: bool = False,
    db_path: Path | str = DB_PATH,
    profiles_dir: Path = PROFILES_DIR,
    conn=None,
) -> None:
    profile = load_profile(profile_name, profiles_dir)
    own_conn = conn is None
    if own_conn:
        conn = db.connect(db_path)
    db.sync_fields(conn, profiles_dir / "fields")

    lock_path = _acquire_run_lock(db_path)
    progress_path = _progress_path(db_path)
    # :memory: is exclusively a test/isolated-check path (fake in-process
    # adapters registered per-test, no real HTTP calls ever happen) -- the
    # inter-request delays below exist only to protect real external hosts,
    # so they'd just slow the test suite down for no reason if applied there.
    throttle = str(db_path) != ":memory:"
    try:
        run_started_at = datetime.now(timezone.utc).isoformat()
        successful_boards: list[tuple[str, str]] = []
        # A real run against 150+ boards takes long enough (each board now
        # deliberately paced, see BOARD_FETCH_DELAY_SECONDS above) that
        # logging only a final summary looks indistinguishable from a hung
        # process. Logging per board as it completes -- not per job, which
        # would be noisy for a board with hundreds of postings -- gives a
        # steady, frequent "yes, it's actually working" signal instead.
        total_stored = 0
        boards_done = 0
        boards_total = sum(len(board_list) for board_list in (profile.get("boards") or {}).values())

        for adapter_key, board_list in (profile.get("boards") or {}).items():
            try:
                adapter_cls = registry.get(adapter_key)
            except KeyError as exc:
                logger.error("unknown adapter %r in profile %r: %s", adapter_key, profile_name, exc)
                continue

            adapter = adapter_cls()
            # None (the default) means the adapter's list endpoint already
            # returns full body text; only bother calling fetch_body for an
            # adapter that actually overrides it (smartrecruiters, bamboohr).
            fetches_body = type(adapter).fetch_body is not Adapter.fetch_body

            for board in board_list:
                token = board.get("token", "")
                try:
                    jobs = adapter.fetch(board)
                except Exception as exc:
                    logger.error("skipping %s:%s, fetch failed: %s", adapter_key, token, exc)
                    db.record_board_health(conn, adapter_key, token, ok=False, error=str(exc), now=run_started_at)
                    boards_done += 1
                    _write_progress(progress_path, {
                        "profile": profile_name, "adapter": adapter_key, "token": token,
                        "boards_done": boards_done, "boards_total": boards_total,
                        "total_stored": total_stored, "started_at": run_started_at,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    _touch_run_lock(lock_path)
                    if throttle:
                        time.sleep(BOARD_FETCH_DELAY_SECONDS)
                    continue

                stored_count = 0
                for job in jobs:
                    # Several adapters' raw API responses carry stray leading/
                    # trailing whitespace straight through from the ATS's own
                    # data (e.g. "Security Operations Analyst ") -- trimmed
                    # once, centrally, here rather than per-adapter, since
                    # every job from every adapter passes through this same
                    # loop before anything else (hashing, filtering, storage)
                    # touches it.
                    job.company = job.company.strip()
                    job.title = job.title.strip()
                    job.location = job.location.strip()

                    db.touch_sighting(conn, source_uid(job), run_started_at)

                    if not _passes_title_and_location_filters(job, profile.get("filters") or {}):
                        continue

                    if fetches_body:
                        try:
                            body = adapter.fetch_body(job)
                        except Exception as exc:
                            logger.error("fetch_body failed for %s: %s", source_uid(job), exc)
                            body = None
                        if throttle:
                            time.sleep(BODY_FETCH_DELAY_SECONDS)
                        if body is not None:
                            job.body = body

                    if not passes_filters(job, profile.get("filters") or {}):
                        continue

                    salary_min, salary_max = scoring.extract_salary_range(job.body)
                    matched_fields = classify.classify_fields(job.title)
                    target_hash = db.upsert_job(
                        conn, job,
                        profile=profile_name,
                        is_native=adapter.is_native,
                        salary_min=salary_min, salary_max=salary_max,
                        level=classify.classify_level(job.title),
                        matched_fields=matched_fields,
                        matched_subfields=classify.classify_subfields(job.title),
                        grad_year=classify.classify_grad_year(job.title, job.body),
                        now=run_started_at,
                    )
                    db.set_job_fields(
                        conn, target_hash, matched_fields,
                        classify.classify_subfields_by_field(job.title),
                    )
                    stored_count += 1

                db.record_board_health(conn, adapter_key, token, ok=True, job_count=len(jobs), now=run_started_at)
                successful_boards.append((adapter_key, token))
                total_stored += stored_count
                boards_done += 1
                logger.info(
                    "%s:%s -- fetched %d, stored %d (running total: %d)",
                    adapter_key, token, len(jobs), stored_count, total_stored,
                )
                _write_progress(progress_path, {
                    "profile": profile_name, "adapter": adapter_key, "token": token,
                    "boards_done": boards_done, "boards_total": boards_total,
                    "total_stored": total_stored, "started_at": run_started_at,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                _touch_run_lock(lock_path)
                if throttle:
                    time.sleep(BOARD_FETCH_DELAY_SECONDS)

        for adapter_key, token in successful_boards:
            db.close_stale_sightings(conn, adapter_key, token, run_started_at)

        if harvest_questions:
            harvested = questions.harvest_matched(conn)
            logger.info("harvested question schemas for %d posting(s)", harvested)

        logger.info(
            "run complete: %d board(s) succeeded, %d posting(s) stored/updated this run",
            len(successful_boards), total_stored,
        )
        _write_progress(progress_path, {
            "profile": profile_name, "adapter": None, "token": None,
            "boards_done": boards_done, "boards_total": boards_total,
            "total_stored": total_stored, "started_at": run_started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
    finally:
        _release_run_lock(lock_path)
        if own_conn:
            conn.close()


def reclassify(
    profile_name: str,
    *,
    db_path: Path | str = DB_PATH,
    profiles_dir: Path = PROFILES_DIR,
    conn=None,
) -> tuple[int, int]:
    """Re-evaluate every already-stored job tagged with this profile against
    its *current* filters, with no network fetch. run()'s main loop
    only ever calls db.upsert_job() for a job that currently passes filters
    -- a job that passed under an older, looser filter keeps its stale
    classification forever once the filter tightens, since nothing
    ever re-checks it again unless it happens to close on its own. A real
    case this hit: tightening profiles/fields/systems.yaml and qa.yaml's
    title_include/title_exclude (a false-positive fix, not a network-visible
    change) left already-ingested rows like "GTM Systems Engineer" still
    tagged under the old, too-permissive rules. Returns
    (updated, newly_skipped)."""
    profile = load_profile(profile_name, profiles_dir)
    own_conn = conn is None
    if own_conn:
        conn = db.connect(db_path)
    db.sync_fields(conn, profiles_dir / "fields")

    updated = 0
    newly_skipped = 0
    rows = conn.execute(
        "SELECT * FROM jobs WHERE profile = ? AND status NOT IN ('closed', 'skipped')",
        (profile_name,),
    ).fetchall()

    for row in rows:
        job = RawJob(
            adapter="", company=row["company"], board_token="", external_id=row["content_hash"],
            title=row["title"], location=row["location"] or "", url=row["best_apply_url"] or "",
            body=row["body"] or "", posted_at=row["posted_at"],
        )
        if not passes_filters(job, profile.get("filters") or {}):
            db.set_status(conn, row["content_hash"], "skipped")
            newly_skipped += 1
            continue

        salary_min, salary_max = scoring.extract_salary_range(job.body)
        matched_fields = classify.classify_fields(job.title)
        conn.execute(
            """UPDATE jobs SET salary_min = ?, salary_max = ?,
               level = ?, matched_fields = ?, matched_subfields = ?, grad_year = ?
               WHERE content_hash = ?""",
            (
                salary_min, salary_max,
                classify.classify_level(job.title),
                json.dumps(matched_fields),
                json.dumps(classify.classify_subfields(job.title)),
                classify.classify_grad_year(job.title, job.body),
                row["content_hash"],
            ),
        )
        db.set_job_fields(
            conn, row["content_hash"], matched_fields,
            classify.classify_subfields_by_field(job.title),
        )
        updated += 1

    conn.commit()
    if own_conn:
        conn.close()
    return updated, newly_skipped
