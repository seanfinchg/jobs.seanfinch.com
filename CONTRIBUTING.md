# Contributing

Thanks for taking a look. Pull requests are welcome.

Read [AGENTS.md](AGENTS.md) first: it explains the layout, the data flow, and the rules that tests enforce.

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

CI runs the same commands, plus a secret scan and a dependency scan. A first-time contributor's workflows need the maintainer's approval before they run.

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

## Reporting a security problem

Don't open a public issue. See [SECURITY.md](SECURITY.md).
