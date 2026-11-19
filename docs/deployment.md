# Deployment

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
