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
See [deployment](docs/deployment.md) for operations and demo credentials.

## Make targets

Run `make help` for the list. The quality gate is `make check`
(format-check, lint, typecheck, test). `make test` reports coverage when
`pytest-cov` is installed. `make openapi` regenerates `docs/openapi.json`.
`make benchmark` runs the evaluation harness into `benchmark/reports/`.
`make seed` and `make reset` manage demo data.

## Environment variables

See `.env.example` for the full list. `JWT_SECRET` and
`FIELD_ENCRYPTION_KEY` are required; the app fails fast without them.

## Tests

```sh
make test
```

Tests are deterministic: fixed clock injection, generated throwaway keys, no
network access. Most database tests run on isolated SQLite files; the
append-only trigger tests need Postgres and run when `DATABASE_URL` points
at a migrated Postgres (CI does this, otherwise they skip).

## Benchmark

```sh
make benchmark
```

Runs the 10 core cases plus 100 deterministic variants through the real
HTTP stack and writes `benchmark/reports/report.md` and `report.json`
with route agreement, under-triage count, invariant results, validator
rates, language parity and subgroup tables.

## Layout

- `app/core/` settings, errors, JSON logging, JWT/security, encryption,
  database, auth dependencies, rate limiting
- `app/api/` thin routers (`app/main.py` wires the application)
- `app/models/`, `app/schemas/` ORM models and Pydantic contracts
- `app/rules_engine/` deterministic flag and triage evaluation
- `app/orchestrator/` traced assessment pipeline
- `app/llm/` providers, prompts, validator and templates
- `app/services/` business logic (consent, intake, referrals, shares,
  privacy, seed, explain, brief)
- `rules/` versioned rule, route and param files (draft, unvalidated)
- `app/content/` bilingual user-facing strings (Arabic needs native review)
- `alembic/` migrations; `benchmark/` cases, harness and reports
- `tests/` pytest suite; `docs/` decisions, API, privacy and deployment
- `seed/` demo users, providers and prior results

## Docs

- `docs/backend-architecture.md` layers and request flow
- `docs/api.md` endpoint guide with a curl demo journey
- `docs/privacy-and-governance.md` data handling and governance
- `docs/deployment.md` deployment and operations
- `docs/decisions.md` short decision records
- `docs/open-clinical-questions.md` questions for the clinical advisor
- `docs/todo.md` follow-ups (no stray TODOs in code)

## Known limitations

- Draft rules, thresholds and Arabic strings are unvalidated; every rule
  and threshold needs the clinical advisor, every Arabic string a native
  reviewer, before any pilot.
- Benchmark evidence is simulated consistency only, never clinical
  safety or outcomes.
- No retention expiry, no key rotation, single-process rate limiting,
  no real messaging (reminders are simulated records).
- Privacy integrations (Malaffi/Sahhatna) and regulatory alignment
  (DoH AI standard, ADHICS, licensing, data residency) are roadmap only.
