# Good first tasks

Concrete, approachable work. "Safe first PR" means it touches no pipeline logic and is hard to break. Comment on or open an issue before starting so two people do not take the same one. Read [getting-started.md](getting-started.md) first.

| # | Task | Safe first PR |
| --- | --- | --- |
| 1 | Add companies to the board lists | Yes |
| 2 | Add a workday adapter fetch test | Yes |
| 3 | Add a focused test for level plus fields merging | Yes |
| 4 | Add an ESLint flat config | Yes (frontend only, no source edits) |
| 5 | Add a new discipline (field YAML) | After one smaller PR |
| 6 | Tighten the featured and defense list tests | Yes |
| 7 | Add a migration upgrade test | Yes |
| 8 | Documentation polish | Yes |
| 9 | Fix a misclassified title | After one smaller PR |
| 10 | Add an ATS adapter | No, discuss first |

## 1. Add companies to the board lists

Files: `backend/boards/*.yaml` (for example `broad-tech.yaml`), helper `backend/scripts/discover_tokens.py`.

Steps: run `python scripts/discover_tokens.py "Company Name"` from `backend/`. It checks slug variants against each ATS's live endpoint and prints a YAML fragment. Paste the fragment under the right adapter in the board file, keeping the existing `{company: X, token: y}` style. Run `python -m jobfinder profile show broad-cs` to confirm the file still loads.

Done when: each added token returned postings from the live endpoint (say so in the PR, with the job count the script printed), nothing is duplicated, and the suite passes. Do not run a full scrape to test it; use a one-board scratch profile.

## 2. Add a workday adapter fetch test

Files: `backend/jobfinder/adapters/workday.py`, `backend/tests/test_workday.py`, new `backend/tests/fixtures/workday_sample.json`.

Only the URL helpers are tested today. Record one real response page from a Workday board (a single `POST` to the jobs endpoint described in the module), trim it to a few postings, and test `WorkdayAdapter.fetch` with the shared session monkeypatched, following the pattern in [testing.md](testing.md). Cover pagination stopping, the posted-date parsing (`_parse_posted_on`), and a board with no postings.

Done when: new tests pass offline, and the fixture holds no personal data.

## 3. Add a focused test for level plus fields merging

Files: `backend/jobfinder/engine.py` (`load_profile`, `_merge_filters`), `backend/tests/test_engine.py`.

The merge is only exercised through the shipped profiles. Using `tmp_path` and synthetic YAML, write tests that a level layer, two field layers, and a personal layer concatenate list filters in that order, that a profile with neither `level` nor `fields` keeps its flat filters, and that `{grad_years}` is expanded.

Done when: tests fail if the layer order changes, and no production code changed.

## 4. Add an ESLint flat config

Files: new `frontend/eslint.config.js`. `frontend/package.json` already lists `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, and `globals`, and a `lint` script.

Write the config so `npm run lint` runs. Do not edit `frontend/src` in the same PR. If lint reports existing violations, either set those rules to `warn` with a comment, or list them in the PR description for a follow-up; do not mass-fix.

Done when: `npm run lint` runs from `frontend/` and exits cleanly (or the PR lists exactly which rules are relaxed and why), and `npm run build` still passes. Do not change `package.json` or the lockfile without asking.

## 5. Add a new discipline

Files: `backend/profiles/fields/<name>.yaml`, [adding-a-field.md](adding-a-field.md), `backend/tests/test_profile_broad_cs.py` for the pattern.

Add a field file with `label`, `filters.title_include` and `title_exclude`, and optional `subfields`. Add the field to a profile's `fields:` list only if the owner agrees. Use `python -m jobfinder profile show broad-cs` and the real titles from the live `data.json` to check for false positives, and add the titles that motivated your regexes to a test. Remember to single-quote regexes in YAML.

Done when: the new field appears in `fields.json` after `jobfinder dashboard`, tests cover at least three titles that should match and three that should not, and the suite passes.

## 6. Tighten the featured and defense list tests

Files: `backend/jobfinder/featured.py`, `backend/jobfinder/defense.py`, `backend/tests/test_featured.py`, `backend/tests/test_defense.py`.

Add tests for properties that should always hold, such as every entry already being lowercase-normalized through the frozenset construction and `is_featured` handling `None` and empty strings. Propose list additions in an issue rather than editing the lists, since both are editorial.

Done when: new tests pass and the lists are unchanged.

## 7. Add a migration upgrade test

Files: `backend/jobfinder/db.py` (`MIGRATIONS`, `init_schema`), `backend/tests/test_db.py`.

Create a database at schema version 1 by running only the first migration, insert a row, then call `init_schema` and assert the later columns and tables exist and the row survived. Do not edit any shipped migration.

Done when: the test fails if a migration is edited to drop a column or the version bookkeeping breaks.

## 8. Documentation polish

Files: anything under `docs/`, `README.md`, the `*.md` files at the root.

Follow each guide from a clean clone and fix whatever does not work, is unclear, or has gone stale. Include the exact command and output that differed in the PR.

Done when: links resolve and commands in your diff were run.

## 9. Fix a misclassified title

Files: `backend/jobfinder/classify.py` or a `backend/profiles/fields/*.yaml`, with a test in `backend/tests/test_classify.py` or a `test_profile_*.py`.

Find a real title in the live `data.json` that has the wrong level or field. Fix the pattern, add that exact title to a test, then run `python -m jobfinder reclassify --profile <name>` against a local database to see the effect. Classifier changes need a real-endpoint check; see [testing.md](testing.md).

Done when: the title classifies correctly, existing classification tests still pass, and the PR lists other titles you checked for regressions.

## 10. Add an ATS adapter

Files: new `backend/jobfinder/adapters/<name>.py`, [adding-an-adapter.md](adding-an-adapter.md).

Open an issue first with a link to the ATS's public, unauthenticated postings endpoint. An adapter needs a recorded-fixture test, a registry entry, and a run against the real API. It must respect the polite-client delays.

Done when: the checklist at the end of the adapter guide is complete.
