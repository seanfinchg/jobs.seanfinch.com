import json
import os
import time

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
