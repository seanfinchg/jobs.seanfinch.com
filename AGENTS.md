# Working in this repo

A guide for anyone (or any coding assistant) picking this project up cold. Read it before changing code. [CONTRIBUTING.md](CONTRIBUTING.md) covers the branch and PR workflow; this file covers how the code is organized and what must not break. Deeper guides live in [docs/](docs/README.md): [architecture](docs/architecture.md), [testing](docs/testing.md), [data contract](docs/data-contract.md), and [getting started](docs/getting-started.md).

## What this is

A job-discovery tool. It polls public applicant-tracking-system (ATS) APIs on a schedule, normalizes and dedupes postings, classifies them by discipline and level, stores them in SQLite, and exports static JSON that a React dashboard reads. An optional local harness fills application forms and stops for a human to submit.

## Layout and data flow

```
backend/jobfinder/
  adapters/    one module per ATS (greenhouse, lever, ashby, smartrecruiters, workable,
               rippling, bamboohr, workday, simplify_listings, manual); registry.py + base.py
  engine.py    the run loop: load profile -> fetch each board -> filter -> classify -> store
  classify.py  discipline / subfield / level / grad-year classification (regex, deterministic)
  normalize.py content hashing for cross-source dedup
  scoring.py   salary-range extraction from posting text
  db.py        SQLite access; schema is an ordered list of MIGRATIONS, never edit an old one
  dashboard.py exports data.json / meta.json / fields.json for the frontend
  questions.py harvests application-form question schemas
  apply.py     fill-and-pause harness (never submits)
  status_server.py  tiny read-only progress page for the host running the scheduled scrape
backend/profiles/   YAML: which boards to poll, which titles pass, level/field layers
backend/boards/     shared company -> board-token lists a profile can include
backend/tests/      pytest; no test touches the network
frontend/src/       React + Vite + Tailwind dashboard, builds to frontend/dist
```

Flow: `jobfinder run --profile X` -> `engine.run` -> each adapter's `fetch(board)` returns `RawJob`s -> title/location/body filters from the profile -> classify -> `db.upsert_job`. `jobfinder dashboard` then writes the three JSON files the frontend loads.

Dedup has two layers: `source_uid = "{adapter}:{board_token}:{external_id}"` identifies a posting within one source, and `content_hash` (company, title, location bucket, optional team) collapses the same posting listed on several sources.

## Rules that must not break

1. **The engine knows no ATS and no level.** `engine.py` must not import a concrete adapter or hard-code an ATS name. It must not contain the words for seniority tiers; that behavior comes from profile YAML. Tests enforce both (`test_engine_source_has_no_seniority_keyword`, `test_engine_imports_no_concrete_adapter_module`).
2. **Fill, never submit.** The apply harness populates forms and pauses for a human. It must never click a submit control, defeat a CAPTCHA, or run in CI. `test_source_never_calls_click_on_anything` enforces it; do not weaken it to make a feature easier.
3. **The scheduled pipeline is deterministic code.** Discovery, filtering, classification, dedup, and question harvesting are plain functions. No generated or model-driven logic, and no network calls beyond the job boards' own public APIs.
4. **Real endpoints, not only fixtures.** Any change to an adapter, filter, classifier, scoring, or dedup rule must be run against the real live API at least once before it counts as done. Fixtures are regression tests, not a substitute.
5. **Tests ship with the logic.** New behavior comes with a test in the same PR.
6. **No personal data in the repo.** Never commit a resume, a database, an `.env` file, `backend/answers.local.yaml`, credentials, or anyone's contact details. Use obviously fake values (`alex@example.com`, `(555) 555-0100`) in tests and examples.
7. **Be a polite client.** `BOARD_FETCH_DELAY_SECONDS`, `BODY_FETCH_DELAY_SECONDS`, and the Workday page delay exist because a burst of requests got a client rate-limited. Don't lower them or add parallel fetching without discussing it first. Each board fetch also has a wall-clock deadline (`BOARD_FETCH_DEADLINE_SECONDS`) so one hung board cannot stall a run.

## Commands

From `backend/`:

```
pip install -r requirements-lock.txt -r requirements-dev-lock.txt
pip install --no-deps -e ".[dev]"            # add ,apply for the form-fill harness
python -m pytest                             # the whole suite, offline, a few seconds
python -m jobfinder profile show new-grad-cs # a profile's fully merged filters and boards
python -m jobfinder run --profile new-grad-cs
python -m jobfinder reclassify --profile new-grad-cs   # re-run classification, no network
python -m jobfinder dashboard                # writes ../frontend/public/*.json
```

From `frontend/`: `npm ci`, `npm run dev`, `npm run build` (typecheck + build).

For dashboard work you don't need to run a scrape. The three data files are public: download `data.json`, `meta.json`, and `fields.json` from `https://jobs.seanfinch.com/` into `frontend/public/` (they are gitignored).

## Common tasks

- **Add a company to poll:** add `{company, token}` under the right adapter in `backend/boards/*.yaml`. Confirm the token against the live endpoint first; `backend/scripts/discover_tokens.py` does that.
- **Add an ATS:** follow [docs/adding-an-adapter.md](docs/adding-an-adapter.md). Subclass `Adapter`, register it, add a recorded-fixture test, and run it against the real API.
- **Add a discipline:** follow [docs/adding-a-field.md](docs/adding-a-field.md); keys are in [docs/profile-schema.md](docs/profile-schema.md). Fields and levels are YAML layers under `backend/profiles/`; check the result with `jobfinder profile show`.
- **Change classification:** edit `classify.py` or the field YAML, add the real titles that motivated the change to a test, then run `jobfinder reclassify` against a local DB to see the effect on stored rows.
- **Change the schema:** append a new numbered migration in `db.py`. Never edit a shipped one.
- **Dashboard changes:** build, then actually open it in a browser at desktop and phone width. The build passing does not mean the UI works; there are no UI tests.

## Gotchas

- Regexes in YAML must be single-quoted. In a double-quoted YAML string `\b` is a backspace, not a word boundary.
- Classification and filters only apply at ingest. After changing them, stored rows keep their old labels until `reclassify` or a re-ingest.
- `frontend` has a `lint` script but no ESLint config yet, so `npm run lint` fails. It is a known gap, not something you broke.
- Windows: long `node_modules` paths can break cleanup and some `pip` installs. Work close to a drive root or enable long paths.
- The Netlify function behind application tracking exists but the dashboard does not render it; leave it alone until its data flow is decided.

## High-risk paths

Anything merged to `prod` is built and run on the maintainer's server. Changes to `Dockerfile`, `docker-entrypoint.sh`, `docker-compose.yml`, `redeploy-watch.sh`, `.github/`, `package.json`, and any lockfile get read line by line before merging, because they can execute at build or deploy time. Don't touch them in an unrelated PR.

## Before you start

- Pick something from [docs/good-first-tasks.md](docs/good-first-tasks.md), or open an issue describing what you plan to change. Small fixes can go straight to a PR.
- Ask first before: changing the export shape ([docs/data-contract.md](docs/data-contract.md)), lowering a fetch delay or adding parallel fetching, adding a dependency, editing a high-risk path, or restructuring directories.
- Never run a full scrape to test a change; use a one-board scratch profile ([docs/getting-started.md](docs/getting-started.md)).
- Every docs file lives under `docs/`. Link new ones from `docs/README.md`.

## Style

- Type hints everywhere; dataclasses for records.
- Small pure functions where logic is testable (normalize, classify, filter-matching).
- Log board failures; one dead board must never abort a run.
- Comments explain why (a non-obvious constraint, a root cause, a tradeoff), not what. Name things so the what is obvious.
- Commit subject: one line, at most 72 characters, no trailing period. PRs go into `dev` with merge commits only.

## Definition of done

`python -m pytest` is green from `backend/`; pipeline changes were run against a real endpoint; dashboard changes were built and opened in a browser; nothing in the diff holds personal data or credentials; the PR template is filled in.
