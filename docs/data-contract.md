# Data contract

`jobfinder dashboard` writes three JSON files. The dashboard reads them, and other people may too (the live site serves them at `https://jobs.seanfinch.com/data.json`, `meta.json`, and `fields.json`). Treat their shape as a public contract.

## The promise

- Changes are additive only. New optional fields may appear; existing fields keep their name, type, and meaning.
- No field is removed or renamed, and no type changes, without a deprecation period announced in the pull request and the release notes.
- `data.json` stays a bare array of objects (not wrapped in an envelope). Run metadata lives in `meta.json` for exactly this reason.
- Consumers should ignore fields they do not recognize.
- Nothing private is ever exported. The export is an allowlist of columns (`PUBLIC_FIELDS` in `backend/jobfinder/dashboard.py`); answers, resume, application status, and notes stay in the local database.

If you change the shape, update all three together in one PR: `dashboard.py`, `frontend/src/types.ts`, and this document. `test_dashboard.py` fails when `types.ts` and the export drift apart.

## data.json

An array of job objects, ordered most recently confirmed open first. It includes jobs whose status is not `closed` or `skipped`.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable opaque id: the job's content hash (SHA-1 hex of company, title, location bucket, team). Use as a key. |
| `company` | string | Company name as the board reports it. |
| `title` | string | Posting title, whitespace trimmed. |
| `location` | string | Location text as posted; may hold several places separated by `;`. Can be empty. |
| `best_apply_url` | string | The preferred link to apply. A native ATS link wins over an aggregator link. |
| `apply_urls` | string[] | Every link the job was seen at, across sources. |
| `first_seen` | string | ISO 8601 UTC timestamp of the first run that stored the job. |
| `posted_at` | string or null | ISO 8601 posting time from the source, when it provides one. |
| `salary_min` | number or null | Lower bound of a salary range parsed from the posting text, in dollars per year. |
| `salary_max` | number or null | Upper bound; equals `salary_min` when only one figure was found. |
| `featured` | boolean | Company is on the hand-maintained featured list (`backend/jobfinder/featured.py`). |
| `defense` | boolean | Company is on the hand-maintained defense and surveillance list (`backend/jobfinder/defense.py`), so viewers can hide it. |
| `level` | string or null | One of `intern`, `new-grad`, `mid`, `senior`, `staff`, `senior-staff`, `principal`, `senior-principal`, `distinguished`, `manager`, `director`, `vp`. Derived from the title; defaults to `mid` when no marker is found. |
| `matched_fields` | string[] | Slugs of the career tracks the title matches (`profiles/fields/<slug>.yaml`). May be empty. |
| `matched_subfields` | string[] | Finer tags within those tracks. May be empty. |
| `grad_year` | number or null | A graduation year found in the title or body, when there is one. |

Salary figures are best-effort text extraction, not verified data. `salary_*` may be null even when a posting lists pay in a form the parser does not recognize.

## meta.json

```json
{ "generated_at": "2026-10-31T20:25:04.737013+00:00" }
```

| Field | Type | Meaning |
| --- | --- | --- |
| `generated_at` | string | ISO 8601 UTC time of the last real scrape. A redeploy that only regenerates files from the stored database passes the original scrape time, so this does not move on a code-only deploy. |

## fields.json

An array, one entry per `backend/profiles/fields/*.yaml` that declares a `label`. Use it to turn the slugs in `matched_fields` into display names.

| Field | Type | Meaning |
| --- | --- | --- |
| `slug` | string | The field file name without extension; matches values in `matched_fields`. |
| `label` | string | Display name, for example `Data / ML`. |
| `subfields` | object[] | Each `{ "tag": string, "label": string }`; `tag` matches values in `matched_subfields`. Empty when the field has none. |

## Trying it locally

Download the live files (see [getting-started.md](getting-started.md)) or generate your own from a local database with `python -m jobfinder dashboard` from `backend/`. For the HTTP API description see [/llms.txt](https://jobs.seanfinch.com/llms.txt) and [/openapi.json](https://jobs.seanfinch.com/openapi.json).
