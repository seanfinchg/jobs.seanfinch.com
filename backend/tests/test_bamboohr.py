import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jobfinder.adapters import bamboohr

FIXTURE = Path(__file__).parent / "fixtures" / "bamboohr_sample.json"


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._payload


def _respond(payload: object) -> Callable[..., _FakeResponse]:
    def fake(*args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(payload)

    return fake


def test_fetch_parses_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(bamboohr.session, "get", _respond(payload))

    jobs = bamboohr.BambooHRAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 2
    job = jobs[0]
    assert job.adapter == "bamboohr"
    assert job.external_id == "823"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, Massachusetts"
    assert job.url == "https://acme.bamboohr.com/careers/823"
    assert job.team == "Engineering"


def test_falls_back_to_ats_location_when_domestic_location_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(bamboohr.session, "get", _respond(payload))

    jobs = bamboohr.BambooHRAdapter().fetch({"company": "Acme", "token": "acme"})

    assert jobs[1].location == "Rochester, New York, United States"


def test_fetch_body_strips_html(monkeypatch: pytest.MonkeyPatch) -> None:
    detail_payload = {
        "result": {"jobOpening": {"description": "<p>Ship <b>security</b> tooling.</p>"}}
    }
    monkeypatch.setattr(bamboohr.session, "get", _respond(detail_payload))

    body = bamboohr.BambooHRAdapter().fetch_body(
        bamboohr.RawJob(
            adapter="bamboohr",
            company="Acme",
            board_token="acme",
            external_id="823",
            title="x",
            location="x",
            url="x",
        )
    )

    assert body == "Ship security tooling."
