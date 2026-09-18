import json
from pathlib import Path

from jobfinder.adapters import bamboohr

FIXTURE = Path(__file__).parent / "fixtures" / "bamboohr_sample.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_parses_jobs(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(bamboohr.session, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = bamboohr.BambooHRAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 2
    job = jobs[0]
    assert job.adapter == "bamboohr"
    assert job.external_id == "823"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, Massachusetts"
    assert job.url == "https://acme.bamboohr.com/careers/823"
    assert job.team == "Engineering"


def test_falls_back_to_ats_location_when_domestic_location_is_empty(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(bamboohr.session, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = bamboohr.BambooHRAdapter().fetch({"company": "Acme", "token": "acme"})

    assert jobs[1].location == "Rochester, New York, United States"


def test_fetch_body_strips_html(monkeypatch):
    detail_payload = {"result": {"jobOpening": {"description": "<p>Ship <b>security</b> tooling.</p>"}}}
    monkeypatch.setattr(bamboohr.session, "get", lambda *a, **k: _FakeResponse(detail_payload))

    body = bamboohr.BambooHRAdapter().fetch_body(
        bamboohr.RawJob(
            adapter="bamboohr", company="Acme", board_token="acme",
            external_id="823", title="x", location="x", url="x",
        )
    )

    assert body == "Ship security tooling."
