# Contributing

Thanks for taking a look. Pull requests are welcome.

Read [AGENTS.md](AGENTS.md) first: it explains the layout, the data flow, and the rules that tests enforce. [docs/getting-started.md](docs/getting-started.md) walks through setup and a first PR, and the rest of the documentation is indexed in [docs/README.md](docs/README.md).

## Picking a task

Choose one from [docs/good-first-tasks.md](docs/good-first-tasks.md) or an open issue labeled `good first issue`. For anything bigger than a small fix, open an issue first and say what you plan to do, so the maintainer can confirm the direction before you spend time on it. Ask first if the change touches the data files' shape ([docs/data-contract.md](docs/data-contract.md)), request pacing, dependencies, or the Docker, deploy, workflow, and lockfile paths.

## Branches

| Branch  | Purpose                        | How changes get in                 |
| ------- | ------------------------------ | ---------------------------------- |
| `dev`   | Integration. Base for all work | PR from a fork or `<type>/<slug>`  |
| `stage` | Pre-release check              | PR from `dev` only, maintainer     |
| `prod`  | What is deployed               | PR from `stage` only, maintainer   |

Contributors only ever open PRs into `dev`. Promotion to `stage` and `prod` is done by the maintainer.

## Making a change

1. Fork the repo and clone your fork.
2. `git switch dev && git pull`, then `git switch -c <type>/<short-slug>` where `<type>` is `feat`, `fix`, `docs`, `chore`, or `refactor`.
3. Make the change and add tests alongside it.
4. Run the checks locally (below), push to your fork, and open a PR into `dev` using the template.

## Checks

From `backend/`:

```
pip install -r requirements-lock.txt -r requirements-dev-lock.txt
pip install --no-deps -e ".[dev]"
python -m pytest
```

From `frontend/`, if you touched the dashboard:

```
npm ci
npm run build
```

CI runs backend tests, the frontend build, and secret and dependency scans. A first-time contributor's workflows need the maintainer's approval before they run, so a check that sits pending after you open the PR is normal.

## Ground rules

- **Fill, never submit.** The apply harness populates forms and pauses for a human. It must never click a submit control or defeat a CAPTCHA, and it never runs in CI. A static test enforces this; do not weaken it.
- **Real endpoints, not just mocks.** A change to an adapter, filter, classifier, or dedup rule must be run against the real live API at least once. Fixtures are for regression tests, not a substitute.
- **Be a polite client.** The per-board and per-request delays in `engine.py` and the adapters exist to avoid tripping rate limits. Don't lower them or add parallel fetching without discussing it first.
- **Keep the engine generic.** `engine.py` must not import a concrete adapter or hard-code an ATS name, and level and role behavior comes from the profile YAML, not code. Tests enforce both.
- **No personal data.** Never commit a resume, a database, an `.env` file, `answers.local.yaml`, credentials, or anyone's contact details. Use obviously fake values in tests and examples.
- **Tests ship with the logic.** New behavior comes with a test in the same PR.

## Style

- Type hints everywhere; dataclasses for records.
- Small pure functions where the logic is testable.
- Log board failures; one dead board must never abort a run.
- Comments explain why, not what: a non-obvious constraint, a bug's root cause, or a tradeoff.

## Merging and commits

Every PR is merged with **"Create a merge commit"**. No squash and no rebase-merge, so history keeps what changed and promotion PRs stay clean.

- **Commit subject:** one line, at most 72 characters, no trailing period.
- **Commit body (optional):** a blank line, then short `- ` bullets.
- **PR description:** fill in the template with bullets only.

## Review

The maintainer reviews and merges every PR; nobody else merges. Expect comments rather than silence: small PRs get reviewed faster. Push follow-up commits to the same branch to address feedback. A PR that touches a high-risk path (see AGENTS.md) is read line by line and may take longer.

## Labels

`bug`, `enhancement`, `documentation`, `question`, `good first issue` (approachable, scoped), and `help wanted` (open for anyone to take). The maintainer applies them; issue forms add `bug` or `enhancement` automatically.

## Reporting a security problem

Don't open a public issue. See [SECURITY.md](SECURITY.md).
