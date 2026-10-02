import json
import os
import time
from datetime import datetime, timedelta, timezone

from jobfinder import status_server


def test_is_scraping_false_when_no_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "LOCK_PATH", tmp_path / "jobfinder.db.run-lock")
    assert status_server._is_scraping() is False


def test_is_scraping_true_for_a_fresh_lock(tmp_path, monkeypatch):
    lock_path = tmp_path / "jobfinder.db.run-lock"
    lock_path.write_text("running")
    monkeypatch.setattr(status_server, "LOCK_PATH", lock_path)
    assert status_server._is_scraping() is True


def test_is_scraping_false_for_a_stale_lock(tmp_path, monkeypatch):
    # Same staleness threshold engine.py itself uses -- a lock this old is
    # from a crashed run, not a real scrape still in flight.
    lock_path = tmp_path / "jobfinder.db.run-lock"
    lock_path.write_text("abandoned")
    old_time = time.time() - status_server.RUN_LOCK_MAX_AGE_SECONDS - 60
    os.utime(lock_path, (old_time, old_time))
    monkeypatch.setattr(status_server, "LOCK_PATH", lock_path)
    assert status_server._is_scraping() is False


def test_read_progress_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(status_server, "PROGRESS_PATH", tmp_path / "missing.json")
    assert status_server._read_progress() is None


def test_read_progress_parses_real_content(tmp_path, monkeypatch):
    progress_path = tmp_path / "jobfinder.db.scrape-progress.json"
    progress_path.write_text(json.dumps({"profile": "broad-cs", "boards_done": 5, "boards_total": 10}))
    monkeypatch.setattr(status_server, "PROGRESS_PATH", progress_path)
    progress = status_server._read_progress()
    assert progress == {"profile": "broad-cs", "boards_done": 5, "boards_total": 10}


def test_read_progress_returns_none_for_corrupt_json(tmp_path, monkeypatch):
    # A crash mid-write (container killed while writing the file) shouldn't
    # take the status page down with it.
    progress_path = tmp_path / "corrupt.json"
    progress_path.write_text("{not valid json")
    monkeypatch.setattr(status_server, "PROGRESS_PATH", progress_path)
    assert status_server._read_progress() is None


def test_in_flight_seconds_none_when_nothing_in_flight():
    assert status_server._in_flight_seconds({"in_flight_since": None}) is None
    assert status_server._in_flight_seconds(None) is None


def test_in_flight_seconds_measures_time_since_board_started():
    since = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    seconds = status_server._in_flight_seconds({"in_flight_since": since})
    assert 89 < seconds < 91


def test_build_status_flags_stalled_past_the_warning_threshold(tmp_path, monkeypatch):
    # Real incident (2026-10-02): a board hung for 9+ hours with the
    # dashboard showing no sign anything was wrong. This is the earlier,
    # separate warning from the 30-minute abandon-and-redeploy threshold.
    lock_path = tmp_path / "jobfinder.db.run-lock"
    lock_path.write_text("running")
    monkeypatch.setattr(status_server, "LOCK_PATH", lock_path)

    progress_path = tmp_path / "jobfinder.db.scrape-progress.json"
    stale_since = (
        datetime.now(timezone.utc) - timedelta(seconds=status_server.STALL_WARNING_SECONDS + 60)
    ).isoformat()
    progress_path.write_text(json.dumps({
        "profile": "broad-cs", "adapter": "workday", "token": "leidos",
        "boards_done": 123, "boards_total": 172, "total_stored": 7022,
        "started_at": "t0", "in_flight_since": stale_since,
    }))
    monkeypatch.setattr(status_server, "PROGRESS_PATH", progress_path)
    monkeypatch.setattr(status_server, "DB_PATH", tmp_path / "jobfinder.db")

    status = status_server.build_status()

    assert status["stalled"] is True
    assert "Possibly stalled" in status_server._render_html(status)
