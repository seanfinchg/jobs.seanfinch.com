from jobfinder import db, questions
from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.models import RawJob


def _job(**overrides):
    base = dict(
        adapter="fake-questions-test", company="Acme", board_token="acme",
        external_id="1", title="Security Engineer", location="Boston, MA",
        url="https://example.com/1", body="",
    )
    base.update(overrides)
    return RawJob(**base)


@register
class _FakeQuestionsAdapter(Adapter):
    name = "fake-questions-test"

    def fetch(self, board):
        return []

    def fetch_questions(self, job):
        return [{"name": "q1", "label": "Are you authorized?", "field_type": "boolean", "required": True, "values": []}]


@register
class _FakeNoQuestionsAdapter(Adapter):
    name = "fake-no-questions-test"

    def fetch(self, board):
        return []


def test_harvest_matched_stores_questions_for_open_jobs():
    conn = db.connect(":memory:")
    job = _job()
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")

    harvested = questions.harvest_matched(conn)

    assert harvested == 1
    rows = conn.execute("SELECT * FROM questions").fetchall()
    assert len(rows) == 1
    assert rows[0]["label"] == "Are you authorized?"


def test_harvest_skips_adapters_with_no_question_schema():
    conn = db.connect(":memory:")
    job = _job(adapter="fake-no-questions-test")
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")

    harvested = questions.harvest_matched(conn)

    assert harvested == 0
    assert conn.execute("SELECT * FROM questions").fetchall() == []


def test_harvest_matched_skips_postings_already_harvested():
    # Real cost this guards against: without this, a live run with
    # --questions re-requests every open posting's schema again every day,
    # a cost that only grows as the backlog of open postings grows.
    conn = db.connect(":memory:")
    job = _job()
    db.upsert_job(conn, job, profile="p", is_native=True, now="t1")

    first = questions.harvest_matched(conn)
    assert first == 1

    second = questions.harvest_matched(conn)
    assert second == 0
    assert len(conn.execute("SELECT * FROM questions").fetchall()) == 1


def test_harvest_ignores_closed_jobs():
    conn = db.connect(":memory:")
    job = _job()
    hash_ = db.upsert_job(conn, job, profile="p", is_native=True, now="t1")
    db.set_status(conn, hash_, "closed")

    harvested = questions.harvest_matched(conn)

    assert harvested == 0
