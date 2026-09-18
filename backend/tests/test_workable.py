import json
from pathlib import Path

from jobfinder.adapters import workable

FIXTURE = Path(__file__).parent / "fixtures" / "workable_sample.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_parses_jobs(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(workable.session, "post", lambda *a, **k: _FakeResponse(payload))

    jobs = workable.WorkableAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "workable"
    assert job.external_id == "ABCDEF1234"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, United States"
    assert job.url == "https://apply.workable.com/acme/j/ABCDEF1234/"
