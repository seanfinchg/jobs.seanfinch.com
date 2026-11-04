import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jobfinder.adapters import rippling

FIXTURE = Path(__file__).parent / "fixtures" / "rippling_sample.json"


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
    monkeypatch.setattr(rippling.session, "get", _respond(payload))

    jobs = rippling.RipplingAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "rippling"
    assert job.external_id == "job-1"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, MA"
    assert job.url == "https://ats.rippling.com/acme/jobs/job-1"
    assert job.team == "Engineering"
