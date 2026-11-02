# How to add a new data source (ATS adapter)

Worked example, using `lever.py` as the annotated reference — it's the
simplest adapter that still hits a real, live, unauthenticated API. Adding
a new source should mean writing one new file in `backend/jobfinder/adapters/`; nothing
outside that directory should need to change.

## 1. The contract you're implementing

Every adapter subclasses `Adapter` (`adapters/base.py`):

```python
class Adapter(ABC):
    name: str
    # False for aggregators (e.g. simplify_listings) whose apply_url points
    # at some other ATS rather than being the canonical source.
    is_native: bool = True

    @abstractmethod
    def fetch(self, board: dict) -> list[RawJob]:
        """Return every current posting for one board config entry.

        Must not filter. Must not raise on a board with zero open
        postings -- only on transport/parse failure, so the engine can log
        the board as unhealthy and move on.
        """

    def fetch_questions(self, job: RawJob) -> list[dict] | None:
        return None
```

`fetch` is the only required method, and the only one the engine ever
calls unconditionally. Two optional methods let an adapter opt into more,
each with a safe default so the engine never assumes behavior an adapter
doesn't provide:

- `fetch_questions(job) -> list[dict] | None` — the application-form
  question schema, if the ATS exposes one (`greenhouse.py` is the only
  adapter that overrides this today).
- `fetch_body(job) -> str | None` — a second, per-posting request for ATSes
  whose list endpoint doesn't include a description (`smartrecruiters` and
  `bamboohr` override it). The engine calls it only for a posting that
  already cleared the title/location filters, to bound the extra requests.
  If your list endpoint already includes a description, populate `body`
  directly in `fetch()`, the way `lever.py` does below.

An adapter must never filter, score, classify, or know anything about
disciplines/levels — that's the filter/scoring and classification layers'
job (`engine.py`/`scoring.py`/`classify.py`), not this one. It also must
never write to the database directly — `engine.run()` owns calling
`db.upsert_job()`.

## 2. `RawJob` — what `fetch()` returns

```python
@dataclass
class RawJob:
    adapter: str
    company: str
    board_token: str
    external_id: str
    title: str
    location: str
    url: str
    body: str = ""
    posted_at: str | None = None
```

Every field except `body`/`posted_at` is required. `adapter` is always
`self.name`. `board_token` and `external_id` together make up
`source_uid` (`models.source_uid()`) — the exact-identity key used for
closure and to update `last_seen`; get these right or a re-posted job
will look like a new one every run. `posted_at`, if you can get it, should
be an ISO 8601 UTC string (see `lever.py`'s `createdAt` conversion below) —
the dashboard prefers it over `first_seen` when present.

## 3. The reference implementation

```python
from __future__ import annotations

from datetime import datetime, timezone

import requests

from jobfinder.adapters.base import Adapter
from jobfinder.adapters.registry import register
from jobfinder.models import RawJob

POSTINGS_URL = "https://api.lever.co/v0/postings/{token}?mode=json"


@register
class LeverAdapter(Adapter):
    name = "lever"

    def fetch(self, board: dict) -> list[RawJob]:
        token = board["token"]
        company = board.get("company", token)

        resp = requests.get(POSTINGS_URL.format(token=token), timeout=15)
        resp.raise_for_status()
        postings = resp.json()

        jobs = []
        for item in postings:
            created_ms = item.get("createdAt")
            posted_at = (
                datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat()
                if created_ms
                else None
            )
            jobs.append(
                RawJob(
                    adapter=self.name,
                    company=company,
                    board_token=token,
                    external_id=item.get("id", ""),
                    title=item.get("text", ""),
                    location=(item.get("categories") or {}).get("location", ""),
                    url=item.get("hostedUrl", ""),
                    body=item.get("descriptionPlain", "") or "",
                    posted_at=posted_at,
                )
            )
        return jobs
```

Points worth calling out for your own adapter:

- **`@register` is the entire wiring step.** It writes `cls` into
  `registry.py`'s `_REGISTRY` dict keyed by `cls.name`, decorator-applied
  at class-definition time. There's no second config file to update — as
  long as your module gets imported (next step), the adapter exists as far
  as every profile's `boards:` key is concerned.
- **Let `resp.raise_for_status()` raise.** `engine.run()` wraps the call to
  `adapter.fetch(board)` in its own `try/except`, logs the board as
  unhealthy via `db.record_board_health(..., ok=False, ...)`, and moves on
  to the next board — a dead board must never abort the whole run. Don't
  swallow the exception yourself.
- **An empty list is a valid, successful result.** A board with zero
  current postings is not an error; only raise on a transport/parse
  failure (a non-2xx response, a shape the JSON parsing can't handle).
- **`board` is whatever that adapter's entry in a profile's `boards:` list
  looks like** — see the next section. `token` is universal across
  adapters; `company` is the friendly display name, defaulting to `token`
  if omitted, the same pattern every adapter uses.

## 4. Registering the module so it actually loads

`@register` only takes effect once the module has been imported once, and
that happens in exactly one place — `adapters/__init__.py`:

```python
from jobfinder.adapters import (  # noqa: F401
    ashby,
    greenhouse,
    lever,
    manual,
    rippling,
    simplify_listings,
    smartrecruiters,
    workable,
    workday,
)
```

Add your new module's name to this import list, alphabetically. Nothing
else in the engine, `db.py`, or `scoring.py` needs to know your adapter
exists.

## 5. Wiring a board into a profile

A profile's `boards:` key (or a shared file included via a profile's
`include:`, e.g. `boards/broad-tech.yaml`) maps your adapter's `name` to a
list of board configs:

```yaml
boards:
  lever:
    - {company: Acme, token: acme}
```

What `token` means is adapter-specific — for most ATSes it's the
company's board slug in that ATS's own URL. If your adapter needs more
than `token`/`company` (Workday needs `tenant`/`wd`/`site`, for example —
see `workday.py`), document that in [profile-schema.md](profile-schema.md)'s `boards`
section, the same way Workday's entry does.

## 6. Writing a fixture-based regression test

Reference: `tests/test_lever.py` + `tests/fixtures/lever_sample.json`.

```python
import json
from pathlib import Path

from jobfinder.adapters import lever

FIXTURE = Path(__file__).parent / "fixtures" / "lever_sample.json"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_parses_jobs(monkeypatch):
    payload = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(lever.requests, "get", lambda *a, **k: _FakeResponse(payload))

    jobs = lever.LeverAdapter().fetch({"company": "Acme", "token": "acme"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.adapter == "lever"
    assert job.external_id == "abc-123"
    assert job.title == "Security Engineer, New Grad"
    assert job.location == "Boston, MA"
    assert job.url == "https://jobs.lever.co/acme/abc-123"
    assert "Python" in job.body
    assert job.posted_at is not None
```

The fixture is a real (trimmed) response captured from the live endpoint.
Every adapter is verified against its real live API at least once before
being considered done, and the fixture that regression tests run against
should come from that real response, not a hand-typed guess at the shape.
`monkeypatch.setattr(<module>.requests, "get", ...)` is the standard
fake-the-transport pattern across every adapter test in this repo — copy
it rather than inventing a mocking approach per adapter.

## Definition of done

- Confirmed against the real, live endpoint at least once (a one-off
  script or REPL call is fine — it doesn't need to be automated).
- A fixture captured from that real call, and a test asserting `fetch()`
  parses it correctly.
- Registered in `adapters/__init__.py`.
- [profile-schema.md](profile-schema.md) updated if your adapter needs board-config keys
  beyond the universal `token`/`company`.
- `pytest` green from `backend/`.
