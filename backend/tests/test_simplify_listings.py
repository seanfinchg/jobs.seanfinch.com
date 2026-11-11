import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jobfinder.adapters import simplify_listings

FIXTURE = Path(__file__).parent / "fixtures" / "simplify_listings_sample.json"


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


def test_fetch_skips_inactive_and_points_at_the_real_ats(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(simplify_listings.session, "get", _respond(payload))

    jobs = simplify_listings.SimplifyListingsAdapter().fetch({"token": "new-grad"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Acme"
    assert job.external_id == "sl-1"
    assert job.url == "https://boards.greenhouse.io/acme/jobs/1001"
    assert job.location == "Boston, MA"


def test_is_not_native() -> None:
    assert simplify_listings.SimplifyListingsAdapter.is_native is False
