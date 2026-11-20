# Deployment

## Vercel + Neon (production)

One Vercel project serves the Next.js frontend and the FastAPI backend
(`api/index.py` serverless function) on the same origin; `/api/v1/*`
rewrites to the function (`vercel.json`). Postgres comes from the Neon
integration, which injects `DATABASE_URL` (pooled); the app also accepts
driverless `postgres://` URLs. Required production env: `JWT_SECRET`,
`FIELD_ENCRYPTION_KEY`, `CORS_ORIGINS` (the site domain),
`NEXT_PUBLIC_API_URL` (`https://<domain>/api/v1`),
`ENABLE_DEV_ADMIN=false`, `LLM_PROVIDER=mock` (or Azure settings).

Flow: push previews automatically → `vercel promote <preview-url>` for
production (CLI uploads are flaky; prefer git-driven deploys). Run
migrations and seed against the Neon URL from a machine with database
network access (`make migrate`, `make seed` with `DATABASE_URL` set);
re-run `make migrate` after any new migration (e.g. phase 7 trigger
update). Verify: `/api/v1/health`, then the journey in
`SUBMISSION.md`.

## Docker Compose (recommended for demos)

```sh
cp .env.example .env
# Edit .env: set JWT_SECRET, FIELD_ENCRYPTION_KEY and seed passwords.
docker compose up --build
```

The API runs migrations on start and serves on `http://localhost:8000`
(docs at `/api/docs`, health at `/api/v1/health`). Seed demo data with
`make seed` (needs `DATABASE_URL` pointing at the Compose database) or
`POST /api/v1/dev/seed` with dev admin enabled.

## Manual run

```sh
python3.11 -m venv .venv  # or: uv venv
make dev
alembic upgrade head     # or: make migrate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment

All configuration comes from the environment; see `.env.example` for
the full list with demo values. Production must set real secrets, a
managed Postgres 15+ URL, the public frontend origin for CORS, and the
LLM provider settings (mock by default needs nothing).

## Operational notes

- HTTPS is assumed at the deployment edge; Compose serves plain HTTP.
- The rate limiter is in-memory and single-process; put one replica
  behind the edge or add a shared store.
- Logs are JSON on stdout; no sensitive data is logged.
- Back up Postgres on the platform's schedule; there is no built-in
  retention expiry yet.
- Live URL and demo credentials are issued per deployment; demo
  handles live in `seed/users.json` with passwords from the
  `SEED_*_PASSWORD` variables.
