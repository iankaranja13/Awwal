# Awwal backend

Prototype backend for Awwal, a discreet Arabic/English digital front door for
men's reproductive health. This prototype uses synthetic data only, is not
clinically validated, and makes no compliance claims.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for environment management
- Docker and Docker Compose for Postgres (production-like runs)

## Quick start

```sh
cp .env.example .env
# Generate a key and put it in .env as FIELD_ENCRYPTION_KEY:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
make dev
make check
JWT_SECRET=dev-secret-value FIELD_ENCRYPTION_KEY='<key>' \
  .venv/bin/python -m uvicorn app.main:app --port 8000
```

Then open `http://localhost:8000/api/v1/health` (docs at `/api/docs`).
With Docker: `docker compose up --build` (needs `.env` with real secrets).

## Make targets

Run `make help` for the list. The quality gate is `make check`
(format-check, lint, typecheck, test). `make test` reports coverage when
`pytest-cov` is installed. `make openapi` regenerates `docs/openapi.json`.

## Environment variables

See `.env.example` for the full list. `JWT_SECRET` and
`FIELD_ENCRYPTION_KEY` are required; the app fails fast without them.

## Tests

```sh
make test
```

Tests are deterministic: fixed clock injection, generated throwaway keys, no
network access. Most database tests run on isolated SQLite files; the two
append-only trigger tests need Postgres and run when `DATABASE_URL` points
at a migrated Postgres (CI does this, otherwise they skip).

## Layout

- `app/core/` settings, errors, JSON logging, JWT/security, encryption
- `app/api/` thin routers (`app/main.py` wires the application)
- `app/models/`, `app/schemas/` ORM base and Pydantic models
- `rules/`, `app/rules_engine/`, `app/orchestrator/`, `app/llm/` land in later phases
- `alembic/` migrations (none yet; environment only)
- `tests/` pytest suite
- `docs/` decisions, clinical questions, todos, OpenAPI snapshot

## Docs

- `docs/decisions.md` short decision records
- `docs/open-clinical-questions.md` questions for the clinical advisor
- `docs/todo.md` follow-ups (no stray TODOs in code)
