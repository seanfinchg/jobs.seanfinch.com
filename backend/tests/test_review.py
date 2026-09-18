from jobfinder import db, review
from jobfinder.models import RawJob


def _job(conn, company, title, now):
    return db.upsert_job(
        conn,
        RawJob(adapter="greenhouse", company=company, board_token=company.lower(), external_id=company,
               title=title, location="Boston, MA", url=f"https://example.com/{company}"),
        profile="p", is_native=True, now=now,
    )


def _scripted(inputs):
    it = iter(inputs)
    return lambda _prompt: next(it)


def test_queue_and_skip_mark_status_and_advance():
    conn = db.connect(":memory:")
    h1 = _job(conn, "Acme", "Engineer", "t1")
    h2 = _job(conn, "Globex", "Analyst", "t2")
    # new_jobs_by_score orders by recency (first_seen DESC) -- h2 (later
    # first_seen) comes first.
    jobs = db.new_jobs_by_score(conn)

    review.review_loop(conn, jobs, ask=_scripted(["q", "s"]))

    assert db.get_job(conn, h2)["status"] == "queued"
    assert db.get_job(conn, h1)["status"] == "skipped"


def test_open_stays_on_same_job_without_changing_status():
    conn = db.connect(":memory:")
    h1 = _job(conn, "Acme", "Engineer", "t1")
    opened = []

    review.review_loop(
        conn, [db.get_job(conn, h1)], ask=_scripted(["o", "n"]), opener=lambda url: opened.append(url)
    )

    assert opened == ["https://example.com/Acme"]
    assert db.get_job(conn, h1)["status"] == "new"


def test_back_returns_to_previous_job():
    conn = db.connect(":memory:")
    h1 = _job(conn, "Acme", "Engineer", "t1")
    h2 = _job(conn, "Globex", "Analyst", "t2")
    jobs = db.new_jobs_by_score(conn)

    review.review_loop(conn, jobs, ask=_scripted(["n", "b", "q", "Q"]))

    assert db.get_job(conn, h2)["status"] == "queued"
    assert db.get_job(conn, h1)["status"] == "new"


def test_quit_leaves_remaining_jobs_untouched():
    conn = db.connect(":memory:")
    h1 = _job(conn, "Acme", "Engineer", "t1")
    h2 = _job(conn, "Globex", "Analyst", "t2")
    jobs = db.new_jobs_by_score(conn)

    review.review_loop(conn, jobs, ask=_scripted(["q", "Q"]))

    assert db.get_job(conn, h2)["status"] == "queued"
    assert db.get_job(conn, h1)["status"] == "new"


def test_new_jobs_by_score_orders_by_recency_and_excludes_other_statuses():
    conn = db.connect(":memory:")
    h1 = _job(conn, "Acme", "Engineer", "t1")
    h2 = _job(conn, "Globex", "Analyst", "t2")
    db.set_status(conn, h1, "queued")

    jobs = db.new_jobs_by_score(conn)

    assert [row["content_hash"] for row in jobs] == [h2]


def test_run_reports_when_nothing_to_review(capsys):
    conn = db.connect(":memory:")
    review.run(conn)
    assert "nothing to review" in capsys.readouterr().out
