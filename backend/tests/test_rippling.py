import json
from pathlib import Path

from jobfinder.adapters import rippling

FIXTURE = Path(__file__).parent / "fixtures" / "rippling_sample.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_parses_jobs(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(rippling.session, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = rippling.RipplingAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "rippling"
    assert job.external_id == "job-1"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, MA"
    assert job.url == "https://ats.rippling.com/acme/jobs/job-1"
    assert job.team == "Engineering"
