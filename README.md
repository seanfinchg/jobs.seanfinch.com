# jobfinder

Polls public applicant-tracking-system APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Rippling, BambooHR, Workday) on a schedule, normalizes and dedupes postings across sources, classifies them by discipline and level, and stores everything in SQLite. A React dashboard reads the exported JSON and builds into a static site.

Discovery, filtering, classification, and dedup are plain deterministic code. An optional local apply harness fills application forms and stops for a human to review and submit; it never submits anything itself.

## Layout

```
backend/    Python package (jobfinder/), CLI, tests, profiles, board lists
frontend/   React + Vite + Tailwind dashboard, builds into frontend/dist
```

## Setup

```
cd backend
pip install -r requirements-lock.txt -r requirements-dev-lock.txt
pip install --no-deps -e ".[dev,apply]"
python -m pytest
```

## Running it

From `backend/`:

```
python -m jobfinder run --profile new-grad-cs           # fetch, dedupe, classify, store
python -m jobfinder run --profile new-grad-cs --questions   # also harvest application question schemas
python -m jobfinder dashboard                            # writes ../frontend/public/data.json
python -m jobfinder profile show new-grad-cs             # print a profile's merged filters and boards
```

Board lists and filters live in `backend/profiles/` (see `backend/profiles/_schema.md`) and `backend/boards/`. To add a new ATS, see `backend/jobfinder/adapters/HOW_TO_ADD_AN_ADAPTER.md`. To add a discipline, see `backend/profiles/HOW_TO_ADD_A_FIELD.md`.

The dashboard:

```
cd frontend
npm ci
npm run dev      # local dev server
npm run build    # builds into frontend/dist
```

## Answer bank (optional)

The apply harness answers form questions from a local SQLite table. Copy `backend/answers.example.yaml` to `backend/answers.local.yaml`, fill in your own details, drop a resume at `backend/resume.pdf`, then run `python scripts/seed_answers.py` from `backend/`. Both files and `jobfinder.db` are gitignored. Work authorization, sponsorship, demographic, clearance, and salary questions are never seeded; the harness always stops and asks.

## Contributing

Start with [AGENTS.md](AGENTS.md) for how the code is organized and the rules that must not break. Branches are `dev` -> `stage` -> `prod`. Fork the repo, branch from `dev`, and open a pull request into `dev`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
