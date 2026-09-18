import json
from pathlib import Path

from jobfinder.adapters import greenhouse

FIXTURE = Path(__file__).parent / "fixtures" / "greenhouse_sample.json"
QUESTIONS_FIXTURE = Path(__file__).parent / "fixtures" / "greenhouse_questions.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_parses_jobs(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(greenhouse.session, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = greenhouse.GreenhouseAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 3
    first = jobs[0]
    assert first.adapter == "greenhouse"
    assert first.company == "Acme"
    assert first.board_token == "acme"
    assert first.external_id == "1001"
    assert first.title == "Security Engineer, New Grad"
    assert first.location == "Boston, MA"
    assert first.url == "https://boards.greenhouse.io/acme/jobs/1001"
    assert "Python" in first.body
    assert "<b>" not in first.body
    assert first.team == "Engineering"
    assert jobs[1].team is None


def test_fetch_questions_parses_schema(monkeypatch):
    payload = json.loads(QUESTIONS_FIXTURE.read_text())
    monkeypatch.setattr(greenhouse.session, "get", lambda *a, **k: _FakeResponse(payload))

    job = greenhouse.RawJob(
        adapter="greenhouse", company="Acme", board_token="acme",
        external_id="1001", title="", location="", url="",
    )
    questions = greenhouse.GreenhouseAdapter().fetch_questions(job)

    assert questions is not None
    labels = {q["label"] for q in questions}
    assert "First Name" in labels
    are_you_authorized = next(q for q in questions if q["label"] == "First Name")
    assert are_you_authorized["field_type"] == "input_text"
    assert are_you_authorized["required"] is True
