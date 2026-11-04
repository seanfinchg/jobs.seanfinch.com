import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jobfinder.adapters import workable

FIXTURE = Path(__file__).parent / "fixtures" / "workable_sample.json"


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
    monkeypatch.setattr(workable.session, "post", _respond(payload))

    jobs = workable.WorkableAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "workable"
    assert job.external_id == "ABCDEF1234"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, United States"
    assert job.url == "https://apply.workable.com/acme/j/ABCDEF1234/"
