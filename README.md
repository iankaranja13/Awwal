# Awwal (أوّل)

A discreet Arabic/English digital front door for men's reproductive health.
Prototype with synthetic data only; not clinically validated, not a
diagnosis, and making no compliance claims.

This repo holds both parts: a Python/FastAPI backend (`app/`,
`rules/`, `tests/`, …) and a Next.js frontend (`app/*.tsx`, `components/`,
`lib/`, `package.json`). See below for each part.

## Backend

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for environment management
- Docker and Docker Compose for Postgres (production-like runs)

### Quick start

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

### Make targets

Run `make help` for the list. The quality gate is `make check`
(format-check, lint, typecheck, test). `make test` reports coverage when
`pytest-cov` is installed. `make openapi` regenerates `docs/openapi.json`.
`make benchmark` runs the evaluation harness into `benchmark/reports/`.
`make seed` and `make reset` manage demo data.

### Environment variables

See `.env.example` for the full list. `JWT_SECRET` and
`FIELD_ENCRYPTION_KEY` are required; the app fails fast without them.

### Tests

```sh
make test
```

Tests are deterministic: fixed clock injection, generated throwaway keys, no
network access. Most database tests run on isolated SQLite files; the
append-only trigger tests need Postgres and run when `DATABASE_URL` points
at a migrated Postgres (CI does this, otherwise they skip).

### Benchmark

```sh
make benchmark
```

Runs the 10 core cases plus 100 deterministic variants through the real
HTTP stack and writes `benchmark/reports/report.md` and `report.json`
with route agreement, under-triage count, invariant results, validator
rates, language parity and subgroup tables.

### Backend layout

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

### Backend docs

- `docs/backend-architecture.md` layers and request flow
- `docs/api.md` endpoint guide with a curl demo journey
- `docs/privacy-and-governance.md` data handling and governance
- `docs/deployment.md` deployment and operations
- `docs/decisions.md` short decision records
- `docs/research-grounding.md` published guidance the design draws on
- `docs/rag-grounding-design.md` citation-grounding proposal (design only)
- `docs/open-clinical-questions.md` questions for the clinical advisor
- `docs/todo.md` follow-ups (no stray TODOs in code)

## Frontend

A private first step for men's reproductive health. Prototype with synthetic
data. Not a diagnosis.

### Run (full stack)

The frontend calls the live API; run both. In one terminal start the
backend (needs `.env` from `.env.example` with real secrets, plus Postgres
via `docker compose up -d db`, or point `DATABASE_URL` at SQLite for a
quick local run):

```sh
make migrate
make seed        # demo clinician/navigator accounts + mock providers
make dev         # API on http://localhost:8000
```

In another terminal:

```bash
npm install
npm run dev      # http://localhost:3000
```

Frontend checks: `npm run typecheck` (`tsc --noEmit`) and `npm run build`.
Optional env (all have working defaults): `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000/api/v1`), `NEXT_PUBLIC_DEMO_CLINICIAN_HANDLE`
/ `NEXT_PUBLIC_DEMO_CLINICIAN_PASSWORD` and the navigator equivalents
(defaults match the documented seed values in `.env.example`). The demo
staff controls and clinician sign-off log in with those seeded accounts.

English only, built as a desktop web app. Pages use a split layout: the
heading and main action sit on the left and stay in place, and the content
is on the right. Narrow windows stack the two columns. Arabic strings are
still in `lib/strings.ts` and `lib/intake.ts` but aren't shown; the
language is fixed in `lib/store.tsx`. The session lives in memory only, so
reloading the page starts a fresh anonymous session.

### Screens

| Route | Screen |
| --- | --- |
| `/` | Welcome |
| `/consent` | Four separate permissions, none pre-ticked |
| `/intake` | Seven short topics; every question has "Not sure" and "Rather not say"; blanks become `skipped` |
| `/results` | Flags in three states (filled, dashed, hollow marker plus text) and the workflow trace sheet |
| `/next` | One route on the care-path line; urgent gets a static full-screen message |
| `/booking` | Video call, blood test, sample or in person; language and clinician filters; phone asked only here |
| `/status` | Referral stages, simulated reminders, outcome; demo buttons stand in for staff (navigator/clinician per stage); outcome note closes the referral |
| `/privacy` | Permissions, shares with expiry and revoke, activity log, download, delete |
| `/clinician` | Review queue, brief, change route, sign off |

### Demo paths

- **Urgent:** answer Yes to any question in "Right now". You skip results and land on the static urgent screen.
- **Incomplete:** leave "Told you have a varicocele" or "Semen analysis" blank. You get "A few answers are missing" with the list.
- **Specialist through sign-off:** answer Yes to "Testicular twist, injury or surgery", book a teleconsult, then open the clinician view from the status page and sign off. The status moves to Confirmed; the demo button then advances it through Booked, Attended and Results explained, and an outcome note closes it.

### API wiring

`lib/types.ts` is the UI contract. `lib/api.ts` is the thin fetch client
for `/api/v1` (anonymous session plus seeded demo-role logins), and
`lib/mapping.ts` is the pure contract layer: UI answers to backend intake
ids/values and backend responses back to UI shapes. Every approximation
(combined screening questions, not-trying derives zero months, duration
bands to representative months) is documented in `mapping.ts` and covered
by `tests/unit/test_frontend_contract.py`, which runs the real mapper
output through the live API. The golden fixture
`tests/fixtures/frontend_mapping_golden.json` is generated from
`lib/mapping.ts`; regenerate it after mapping changes with:

```sh
node scripts/regen_frontend_golden.mjs
```

The contract suite also fails when the fixture is stale (skipped where
`node_modules` is absent, e.g. backend-only CI).

### Design notes

- Tokens live in `app/globals.css`. Saffron `#C8902E` is reserved for the user's path (progress bar, route line, status line) and is used nowhere else.
- Type: Readex Pro, light weight for headings.
- The care path on the next-step screen is horizontal, from self-care to urgent, and the line draws to the user's stop.
- Motion: one entrance per screen, the route line drawing to the user's stop, and responses to taps (chips, toggles, expanding rows, sheets). Reduced-motion settings are respected.
- All clinical content needs clinician review.

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
- The browser session is in-memory only (reload starts over), and the demo
  staff controls use the documented seeded demo credentials.
