import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jobfinder.adapters import smartrecruiters

FIXTURE = Path(__file__).parent / "fixtures" / "smartrecruiters_sample.json"


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
    monkeypatch.setattr(smartrecruiters.session, "get", _respond(payload))

    jobs = smartrecruiters.SmartRecruitersAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "smartrecruiters"
    assert job.external_id == "9001"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, MA, United States"
    assert job.url == "https://jobs.smartrecruiters.com/acme/9001"
    assert job.team == "Engineering"


def test_fetch_body_strips_html_across_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    detail_payload = {
        "jobAd": {
            "sections": {
                "jobDescription": {
                    "title": "Job Description",
                    "text": "<p>Ship <b>security</b> tooling.</p>",
                },
                "qualifications": {
                    "title": "Qualifications",
                    "text": "<ul><li>CS degree</li></ul>",
                },
            }
        }
    }
    monkeypatch.setattr(smartrecruiters.session, "get", _respond(detail_payload))

    body = smartrecruiters.SmartRecruitersAdapter().fetch_body(
        smartrecruiters.RawJob(
            adapter="smartrecruiters",
            company="Acme",
            board_token="acme",
            external_id="9001",
            title="x",
            location="x",
            url="x",
        )
    )

    assert body is not None
    assert "Ship security tooling." in body
    assert "CS degree" in body
