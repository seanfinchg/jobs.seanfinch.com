import json
from pathlib import Path

from jobfinder.adapters import simplify_listings

FIXTURE = Path(__file__).parent / "fixtures" / "simplify_listings_sample.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_skips_inactive_and_points_at_the_real_ats(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(simplify_listings.session, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = simplify_listings.SimplifyListingsAdapter().fetch({"token": "new-grad"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Acme"
    assert job.external_id == "sl-1"
    assert job.url == "https://boards.greenhouse.io/acme/jobs/1001"
    assert job.location == "Boston, MA"


def test_is_not_native():
    assert simplify_listings.SimplifyListingsAdapter.is_native is False
