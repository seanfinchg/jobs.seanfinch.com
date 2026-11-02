# Architecture

How the pieces fit. Read this before a change that spans more than one module. File names are relative to `backend/jobfinder/` unless stated.

## Layers and data flow

```
 backend/profiles/*.yaml            backend/boards/*.yaml
 (filters, level, fields, include)  (company -> board token lists)
            \                          /
             v                        v
        engine.load_profile()  -> merged profile {filters, boards}
                      |
                      v
   for each adapter, for each board:           adapters/<ats>.py
        adapter.fetch(board) ------------------> public ATS JSON API
                      |  list[RawJob]
                      v
   strip text -> touch_sighting -> title/location filter
        -> (optional) adapter.fetch_body -> full filter
                      |
                      v
   scoring.extract_salary_range   classify.classify_{level,fields,subfields,grad_year}
                      |
                      v
        db.upsert_job  ->  SQLite (jobs, sightings, job_fields, ...)
                      |
                      v
        dashboard.export_data  ->  data.json  meta.json  fields.json
                      |
                      v
   frontend/ (React + Vite) fetches the three files and renders a static site
```

Three rules shape this layout (the tests enforce them, see [testing.md](testing.md)):

- Adapters only fetch and map raw data. They never filter, classify, or touch the database.
- The engine knows no ATS name and no seniority tier. Which boards to poll and which titles pass come from YAML.
- Everything in the scheduled pipeline is deterministic code.

## Adapters and the registry

`adapters/base.py` defines `Adapter`: a class with a `name`, an `is_native` flag, a required `fetch(board) -> list[RawJob]`, and two optional hooks, `fetch_questions(job)` and `fetch_body(job)`, that default to "not supported". `models.RawJob` is the dataclass every adapter returns (adapter, company, board_token, external_id, title, location, url, body, posted_at, team).

`adapters/registry.py` is a name-to-class dict filled by the `@register` decorator. `adapters/__init__.py` imports each adapter module so importing the package populates it. `engine.run` looks adapters up with `registry.get(name)` using the keys of a profile's `boards:` map, so a new adapter needs only a new module, a `@register`, and an import line in `adapters/__init__.py`. Walkthrough: [adding-an-adapter.md](adding-an-adapter.md).

`is_native` is false for aggregators (`simplify_listings`), whose apply link points at some other ATS. A native source wins the "best apply URL" for a job once it shows up. `manual` serves hand-entered postings for companies with no usable public API. `workday` needs `tenant`, `wd`, and `site` in its board config.

All adapters share one `requests` session from `http.py`.

## The engine run loop

`engine.run(profile_name, ...)`:

1. `load_profile` merges the profile (below) and `db.sync_fields` mirrors `profiles/fields/*.yaml` into the `fields`/`subfields` tables.
2. It takes a lock file next to the DB so two runs cannot overlap, and writes a progress file that the read-only `status_server.py` page shows.
3. For each adapter and each board, it calls `adapter.fetch(board)` under a wall-clock deadline (`BOARD_FETCH_DEADLINE_SECONDS`). A failure is logged, recorded in `board_health`, and the loop moves on; one dead board never aborts a run.
4. For each returned job it trims text, refreshes the sighting's `last_seen`, applies the cheap title/location filters, optionally calls `fetch_body` (only for adapters that override it) under its own deadline, then applies the full filter set.
5. Surviving jobs get a salary range, level, fields, subfields, and grad year, then `db.upsert_job`.
6. Sleeps between boards and bodies (`BOARD_FETCH_DELAY_SECONDS`, `BODY_FETCH_DELAY_SECONDS`) keep it a slow, polite client. They are skipped for the in-memory test DB.
7. After the loop, `close_stale_sightings` runs for each board that fetched successfully, and `--questions` harvests application-form schemas.

`engine.reclassify(profile)` re-applies the current filters and classifiers to stored jobs with no network, marking jobs that no longer pass as `skipped`. Classification and filters only apply at ingest, so run it after changing YAML or `classify.py`.

## Classification

`classify.py` is regex-based and deterministic:

- `classify_level(title)` returns a level from an ordered pattern list, defaulting to `mid`. `LEVEL_ORDER` is the canonical sort order and is mirrored in `frontend/src/types.ts`.
- `classify_fields(title)` returns every field whose `title_include` patterns match. It reads `profiles/fields/*.yaml` directly, independent of which profile ingested the job, so the dashboard can filter by track however narrow the ingesting profile was.
- `classify_subfields` and `classify_subfields_by_field` use each field's own `subfields:` patterns.
- `classify_grad_year(title, body)` finds a graduation year in a rolling window around the current year.

`scoring.py` extracts a salary range from posting text, with plausibility limits.

Paths like `profiles/fields` are relative to the working directory, which is why backend commands run from `backend/`.

## Profiles, levels, fields

A profile (`profiles/<name>.yaml`) can compose its filters from layers instead of writing them flat:

```
profiles/levels/<level>.yaml    experience tier: seniority, intern, PhD exclusions
profiles/fields/<field>.yaml    career track: title vocabulary, label, subfields
profiles/<name>.yaml            personal layer (locations), applied last
boards/*.yaml                   company lists, pulled in with `include:`
```

`load_profile` concatenates the list-valued filter keys across layers in that order (level, each field, then the profile). `include:` merges board lists per adapter. Strings containing `{grad_years}` are expanded to a current year-window regex when loaded. `python -m jobfinder profile show <name>` prints the merged result. Full reference: [profile-schema.md](profile-schema.md); adding a track: [adding-a-field.md](adding-a-field.md).

## Dedup

Two identifiers, two jobs:

- `source_uid = "{adapter}:{board_token}:{external_id}"` identifies one posting in one source. It is the primary key of `sightings`.
- `content_hash` is a SHA-1 of the normalized company, title, location bucket, and (when the adapter exposes one) team. It is the primary key of `jobs`. `normalize.py` lowercases, strips punctuation, folds common abbreviations, and buckets locations (for example `boston`, `new york`, `remote-us`) so the same role listed on two sources collapses into one `jobs` row with two `sightings`.

`upsert_job` reuses the hash from an existing sighting if there is one, so a later change to the hash rules does not orphan stored rows until a full re-ingest. A job closes (`status = 'closed'`) only when none of its sightings, from any source, were seen in the latest successful fetch of their board.

## SQLite and migrations

`db.py` holds the schema as `MIGRATIONS`, an ordered list of `(version, sql)`. `init_schema` reads the stored number from a one-row `schema_version` table and applies every migration above it, so an existing database upgrades in place. Rules: append a new numbered migration; never edit a shipped one, because deployed databases have already run it. Main tables: `jobs`, `sightings`, `board_health`, `questions`, `answers`, `applications` (the last two hold personal data and never leave the local DB), plus `fields`, `subfields`, `job_fields`, `job_subfields` for indexed discipline lookups. Job `status` is `new`, `queued`, `skipped`, or `closed`.

## Dashboard export

`dashboard.export_data` selects an allowlist of columns (`PUBLIC_FIELDS`) for jobs that are not closed or skipped, adds computed fields (`apply_urls`, `featured`, `defense`), and writes three files to `frontend/public/`. Nothing outside the allowlist leaves the database. The shape is a public contract: [data-contract.md](data-contract.md).

`featured.py` and `defense.py` are hand-maintained company lists behind the `featured` and `defense` flags. Matching is exact, case-insensitive, on the company name.

## Frontend

`frontend/` is a Vite app using React 19, TypeScript, and Tailwind 4.

```
src/main.tsx        entry
src/App.tsx         loads data.json / meta.json / fields.json, owns filter state
src/types.ts        Job, FieldMeta, level order and labels (mirrors the export)
src/components/     FilterBar, JobTable, StatsBar, DisciplinePicker, RolePicker,
                    LocationTreeFilter, MultiSelectDropdown, FeaturedToday, ...
src/lib/            small helpers: date, location, company, applied-state sync
public/             static files; data.json, meta.json, fields.json are generated
netlify/            serverless function behind application tracking
```

The site is static: `npm run build` produces `frontend/dist`, and Netlify serves it. Filtering and sorting happen in the browser over the downloaded JSON. For the public API description, see [/llms.txt](https://jobs.seanfinch.com/llms.txt) and [/openapi.json](https://jobs.seanfinch.com/openapi.json).

## Release flow

Branches are `dev` -> `stage` -> `prod`. Merging to `prod` deploys. The maintainer does promotions; contributors only open PRs into `dev` and never need infrastructure access.
