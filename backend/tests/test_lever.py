import json
from pathlib import Path

from jobfinder.adapters import lever

FIXTURE = Path(__file__).parent / "fixtures" / "lever_sample.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_parses_jobs(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(lever.session, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = lever.LeverAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "lever"
    assert job.external_id == "abc-123"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, MA"
    assert job.url == "https://jobs.lever.co/acme/abc-123"
    assert "Python" in job.body
    assert job.posted_at is not None
    assert job.team == "Security"
