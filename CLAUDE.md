@AGENTS.md

Guidance for coding assistants working in this repo:

- Read [docs/architecture.md](docs/architecture.md) before any change that spans more than one module, and [docs/README.md](docs/README.md) to find the right guide.
- Run `python -m pytest` from `backend/` before proposing a commit, and `npm run build` from `frontend/` if you touched the dashboard.
- Do not edit the high-risk paths listed in AGENTS.md (Dockerfile, entrypoint and compose files, redeploy script, `.github/`, `package.json`, lockfiles) without asking the person you are working for.
- Never commit secrets or personal data: no resume, database, `.env`, `answers.local.yaml`, credentials, or real contact details.
- Never run a full scrape to test a change. Use a one-board scratch profile (see [docs/getting-started.md](docs/getting-started.md)).
- Keep pull requests small and focused, and target `dev`.
