import sqlite3

import pytest

from jobfinder import db
from jobfinder.models import RawJob


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    db.init_schema(connection)
    yield connection
    connection.close()


def _job(**overrides):
    base = dict(
        adapter="greenhouse", company="Acme", board_token="acme", external_id="1",
        title="Security Engineer", location="Boston, MA",
        url="https://boards.greenhouse.io/acme/jobs/1", body="",
    )
    base.update(overrides)
    return RawJob(**base)


def test_upsert_is_idempotent(conn):
    job = _job()
    db.upsert_job(conn, job, profile="p", is_native=True, now="2026-01-01T00:00:00")
    db.upsert_job(conn, job, profile="p", is_native=True, now="2026-01-01T01:00:00")

    rows = conn.execute("SELECT * FROM jobs").fetchall()
    assert len(rows) == 1
    assert rows[0]["last_seen"] == "2026-01-01T01:00:00"

    sightings = conn.execute("SELECT * FROM sightings").fetchall()
    assert len(sightings) == 1


def test_cross_source_dedup_links_one_job_two_sightings(conn):
    aggregator_job = _job(
        adapter="simplify_listings", board_token="new-grad", external_id="sl-1",
        url="https://simplify.jobs/redirect/1",
    )
    native_job = _job(
        adapter="greenhouse", board_token="acme", external_id="1",
        url="https://boards.greenhouse.io/acme/jobs/1",
    )

    db.upsert_job(conn, aggregator_job, profile="p", is_native=False, now="t1")
    hash_ = db.upsert_job(conn, native_job, profile="p", is_native=True, now="t2")

    jobs = conn.execute("SELECT * FROM jobs").fetchall()
    assert len(jobs) == 1
    assert jobs[0]["best_apply_url"] == "https://boards.greenhouse.io/acme/jobs/1"

    sightings = db.list_sightings(conn, hash_)
    assert len(sightings) == 2


def test_native_apply_url_is_never_downgraded(conn):
    native_job = _job(adapter="greenhouse", board_token="acme", external_id="1")
    aggregator_job = _job(
        adapter="simplify_listings", board_token="new-grad", external_id="sl-1",
        url="https://simplify.jobs/redirect/1",
    )

    hash_ = db.upsert_job(conn, native_job, profile="p", is_native=True, now="t1")
    db.upsert_job(conn, aggregator_job, profile="p", is_native=False, now="t2")

    job = db.get_job(conn, hash_)
    assert job["best_apply_url"] == native_job.url


def test_closure_flips_status_when_board_stops_listing_it(conn):
    job = _job()
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    # second run: board no longer returns this job at all
    closed = db.close_stale_sightings(conn, "greenhouse", "acme", "t2")

    assert closed == 1
    assert db.get_job(conn, db.normalize.content_hash(job.company, job.title, job.location))["status"] == "closed"


def test_closure_spares_a_job_still_open_via_another_source(conn):
    native_job = _job(adapter="greenhouse", board_token="acme", external_id="1")
    aggregator_job = _job(
        adapter="simplify_listings", board_token="new-grad", external_id="sl-1",
        url="https://simplify.jobs/redirect/1",
    )

    db.upsert_job(conn, native_job, profile="p", is_native=True, now="t1")
    hash_ = db.upsert_job(conn, aggregator_job, profile="p", is_native=False, now="t1")

    # greenhouse board is repolled at t2 and this job is gone from it, but the
    # aggregator sighting is still fresh from t1 -- wait, it needs to be
    # refreshed at t2 too for this to prove the "still open elsewhere" case.
    db.upsert_job(conn, aggregator_job, profile="p", is_native=False, now="t2")
    closed = db.close_stale_sightings(conn, "greenhouse", "acme", "t2")

    assert closed == 0
    assert db.get_job(conn, hash_)["status"] == "new"


def test_a_failing_board_is_never_passed_to_closure(conn):
    # simulates engine.py's behavior: close_stale_sightings is simply never
    # called for a board whose fetch raised this run.
    job = _job()
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")

    job_row_before = db.get_job(conn, db.normalize.content_hash(job.company, job.title, job.location))
    assert job_row_before["status"] == "new"
    # no close_stale_sightings call here -- board fetch "failed"
    job_row_after = db.get_job(conn, db.normalize.content_hash(job.company, job.title, job.location))
    assert job_row_after["status"] == "new"


def test_closure_does_not_touch_a_different_boards_jobs(conn):
    job_a = _job(board_token="acme", external_id="a1")
    job_b = _job(company="Other Co", board_token="other", external_id="b1")

    db.upsert_job(conn, job_a, profile="p", is_native=True, now="t1")
    db.upsert_job(conn, job_b, profile="p", is_native=True, now="t1")

    db.close_stale_sightings(conn, "greenhouse", "acme", "t2")

    hash_b = db.normalize.content_hash(job_b.company, job_b.title, job_b.location)
    assert db.get_job(conn, hash_b)["status"] == "new"


def test_touch_sighting_prevents_false_closure_when_filtered_out(conn):
    job = _job()
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")

    # simulate a later run where the job is still on the board but a
    # stricter profile filtered it out before upsert_job would be called
    db.touch_sighting(conn, "greenhouse:acme:1", "t2")
    closed = db.close_stale_sightings(conn, "greenhouse", "acme", "t2")

    assert closed == 0


def test_queued_or_applied_status_is_not_clobbered_by_closure(conn):
    job = _job()
    hash_ = db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    db.set_status(conn, hash_, "queued")

    db.close_stale_sightings(conn, "greenhouse", "acme", "t2")

    assert db.get_job(conn, hash_)["status"] == "queued"


def test_board_health_records_failure_without_wiping_last_ok(conn):
    db.record_board_health(conn, "greenhouse", "acme", ok=True, job_count=5, now="t1")
    db.record_board_health(conn, "greenhouse", "acme", ok=False, error="404", now="t2")

    row = conn.execute(
        "SELECT * FROM board_health WHERE adapter='greenhouse' AND board_token='acme'"
    ).fetchone()
    assert row["last_ok"] == "t1"
    assert row["last_error"] == "404"
    assert row["job_count"] == 5


def test_seed_answer_then_question_is_no_longer_novel(conn):
    db.add_questions(conn, "greenhouse:acme:1", [
        {"name": "q1", "label": "Are you authorized to work in the US?", "field_type": "boolean", "required": True, "values": []},
        {"name": "q2", "label": "What is your favorite color?", "field_type": "input_text", "required": True, "values": []},
    ])

    novel = db.unanswered_questions(conn)
    assert len(novel) == 2

    db.seed_answer(conn, r"authorized to work", "Yes", now="t1")

    novel = db.unanswered_questions(conn)
    assert len(novel) == 1
    assert novel[0]["label"] == "What is your favorite color?"


def test_todo_placeholder_answer_still_counts_as_unanswered(conn):
    db.add_questions(conn, "greenhouse:acme:1", [
        {"name": "q1", "label": "Are you authorized to work in the US?", "field_type": "boolean", "required": True, "values": []},
    ])
    db.seed_answer(conn, r"authorized to work", "TODO: fill in yourself -- work authorization status")

    novel = db.unanswered_questions(conn)
    assert len(novel) == 1
    assert novel[0]["label"] == "Are you authorized to work in the US?"


def test_unanswered_questions_batches_by_norm_label_with_count(conn):
    db.add_questions(conn, "greenhouse:acme:1", [
        {"name": "q1", "label": "Are You Authorized?", "field_type": "boolean", "required": True, "values": []},
    ])
    db.add_questions(conn, "greenhouse:acme:2", [
        {"name": "q1", "label": "are you authorized?", "field_type": "boolean", "required": True, "values": []},
    ])

    novel = db.unanswered_questions(conn)
    assert len(novel) == 1
    assert novel[0]["count"] == 2


def test_sync_fields_mirrors_yaml_label_and_subfields(conn, tmp_path):
    (tmp_path / "finance.yaml").write_text(
        "label: Finance\nsubfields:\n  - tag: trading\n    label: Sales & Trading\n"
    )
    db.sync_fields(conn, tmp_path)

    field = conn.execute("SELECT * FROM fields WHERE slug = 'finance'").fetchone()
    assert field["label"] == "Finance"
    subfield = conn.execute("SELECT * FROM subfields WHERE field_slug = 'finance' AND tag = 'trading'").fetchone()
    assert subfield["label"] == "Sales & Trading"


def test_set_job_fields_populates_join_tables_and_is_queryable(conn):
    job = _job(title="Sales & Trading Analyst")
    hash_ = db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    db.set_job_fields(conn, hash_, ["finance"], [("finance", "trading")])

    assert [r["field_slug"] for r in conn.execute("SELECT * FROM job_fields")] == ["finance"]
    assert [r["tag"] for r in conn.execute("SELECT * FROM job_subfields")] == ["trading"]

    matches = db.jobs_for_field(conn, "finance")
    assert [r["content_hash"] for r in matches] == [hash_]


def test_set_job_fields_replaces_rather_than_accumulates_on_reclassify(conn):
    job = _job()
    hash_ = db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    db.set_job_fields(conn, hash_, ["finance"], [("finance", "trading")])
    db.set_job_fields(conn, hash_, ["mechanical-engineering"], [])

    assert [r["field_slug"] for r in conn.execute("SELECT * FROM job_fields")] == ["mechanical-engineering"]
    assert conn.execute("SELECT * FROM job_subfields").fetchall() == []


def test_set_job_fields_self_registers_a_slug_sync_fields_never_saw(conn):
    """set_job_fields() must not depend on sync_fields() having already run
    for the same fields_dir -- classify.py's own cache can be warm from a
    different dir (see db.py's set_job_fields() docstring), so this needs to
    resolve its own foreign keys rather than assume they're already there."""
    job = _job()
    hash_ = db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    db.set_job_fields(conn, hash_, ["unregistered-field"], [("unregistered-field", "some-tag")])

    field = conn.execute("SELECT * FROM fields WHERE slug = 'unregistered-field'").fetchone()
    assert field["label"] == "unregistered-field"
    assert conn.execute(
        "SELECT * FROM job_fields WHERE field_slug = 'unregistered-field'"
    ).fetchone() is not None
