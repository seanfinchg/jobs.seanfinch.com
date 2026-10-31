# Testing

```
cd backend
python -m pytest          # whole suite, offline, a few seconds
python -m pytest tests/test_lever.py -q
python -m pytest -k dedup
```

Tests never touch the network. Adapters are covered by recorded fixtures in `backend/tests/fixtures/`, and the database tests use in-memory SQLite.

## What the suite covers

| Area | Test files |
| --- | --- |
| Adapters (fetch parsing against recorded payloads) | `test_greenhouse`, `test_lever`, `test_ashby`, `test_smartrecruiters`, `test_workable`, `test_bamboohr`, `test_rippling`, `test_simplify_listings`, `test_manual`, `test_registry` |
| Workday URL parsing | `test_workday` |
| Engine: filters, profile loading, run loop, deadlines, run lock, reclassify | `test_engine` |
| Classification and scoring | `test_classify`, `test_scoring` |
| Normalization and content hash | `test_normalize` |
| Database: upsert, cross-source dedup, closure, board health, answers, field tables | `test_db` |
| Profiles run against real shipped YAML with real titles | `test_profile_new_grad_cs`, `test_profile_broad_cs` |
| Dashboard export shape and no-leak checks | `test_dashboard` |
| Featured and defense company lists | `test_featured`, `test_defense` |
| Question harvesting, answer bank, review queue | `test_questions`, `test_seed_answers`, `test_review` |
| Apply harness | `test_apply` |
| Token discovery script | `test_discover_tokens` |
| Status page | `test_status_server` |

## Guard tests that enforce project rules

These exist to protect rules from [AGENTS.md](../AGENTS.md). Do not weaken or delete them to make a feature easier. If one fails, the change is probably breaking a rule.

- `test_engine.py::test_engine_source_has_no_seniority_keyword` and `test_engine_imports_no_concrete_adapter_module`: the engine stays ATS-agnostic and level-agnostic.
- `test_apply.py::test_source_never_calls_click_on_anything` and `test_run_refuses_to_go_headless`: the harness fills forms but never submits, and never runs headless.
- `test_apply.py::test_workday_jobs_are_routed_to_manual_open_not_autofill`: Workday postings open for manual handling.
- `test_dashboard.py::test_export_shape_is_the_public_allowlist_only`, `test_export_never_leaks_answers_resume_or_application_state`, and `test_frontend_types_only_declare_the_public_allowlist`: the export contains only public fields, and `frontend/src/types.ts` stays in step with it. See [data-contract.md](data-contract.md).

## Adding an adapter test with a recorded fixture

1. Fetch one real response from the ATS (see [adding-an-adapter.md](adding-an-adapter.md)). Trim it to one or two postings that exercise the fields you map, and remove anything personal or irrelevant. Save it as `backend/tests/fixtures/<name>_sample.json`.
2. Create `backend/tests/test_<name>.py` modeled on `test_lever.py`:

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
    monkeypatch.setattr(lever.session, "get", lambda *a, **k: _FakeResponse(payload))
    jobs = lever.LeverAdapter().fetch({"company": "Acme", "token": "acme"})
    assert jobs[0].adapter == "lever"
```

3. Assert the mapped fields (id, title, location, URL, body, posted date, team where the API has one) and at least one edge case such as a missing location or an empty board.
4. Add the adapter name to `test_registry.py` if it should be guaranteed present.

## The real-endpoint rule

Fixtures catch regressions. They do not prove an adapter works. Before a change to an adapter, filter, classifier, scoring, or dedup rule counts as done, run it against the real live API at least once. For an adapter, a one-board scratch profile does it (see [getting-started.md](getting-started.md)). Say in the PR what you ran and what you saw. Keep it to one or a few boards; do not run a full scrape to test a change.

## What is not covered

- The frontend has no UI tests of any kind. `npm run build` runs the TypeScript typecheck, and that is the only automated check. Dashboard changes need a manual look in a browser at desktop and phone width.
- `npm run lint` fails: the `lint` script and the ESLint packages exist, but there is no ESLint config file yet. This is a known gap, not something you broke.
- The Workday adapter's `fetch` (pagination, parsing) has no fixture test; only its URL helpers are tested.
- There is no test that upgrades a database created at an older schema version through the later migrations.
- The Netlify function in `frontend/netlify/functions/` has no tests.
- Real-network behavior is untested by design. Rate limits, endpoint changes, and bot protection only show up on a live run.
- Layer merging in `load_profile` is exercised through the shipped profiles and a few included-board cases, but there is no focused unit test of the level plus fields merge order using synthetic YAML.

Gaps like these are good first contributions; see [good-first-tasks.md](good-first-tasks.md).

## Conventions

- Tests ship with the logic in the same PR.
- Use obviously fake data in tests (`alex@example.com`, `(555) 555-0100`, company `Acme`).
- When a bug comes from a real title or posting, add that real title to a test.
- Prefer small pure functions so a test can call them directly.
