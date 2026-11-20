# Awwal (أوّل)

A discreet Arabic/English digital front door for men's reproductive
health: consented intake → explainable screening signals → safe triage →
clinician-reviewed referral → documented outcome. Built for Challenge
01 (Male Reproductive Health) of the Future Health Digital Innovation
Challenge. Principle: **rules decide, AI explains, clinicians validate.**

Prototype with synthetic data only; not clinically validated, not a
diagnosis, and making no compliance claims.

- **Live demo:** https://awwal-dun.vercel.app (API docs at `/api/docs`)
- **Submission pack:** [`SUBMISSION.md`](SUBMISSION.md) (demo script,
  credentials, judging-criteria mapping, assumptions, limitations)
- **Demo video script:** [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
- **Path to pilot:** [`docs/path-to-pilot.md`](docs/path-to-pilot.md)

This repo holds both parts: a Python/FastAPI backend (`app/`,
`rules/`, `tests/`, …) and a Next.js frontend (`app/*.tsx`,
`components/`, `lib/`, `package.json`).

## Run everything

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 22,
Docker + Compose for local Postgres (or point `DATABASE_URL` at SQLite
for a quick run).

```sh
cp .env.example .env   # fill in JWT_SECRET, FIELD_ENCRYPTION_KEY
make dev               # create venv + install
make migrate && make seed
make serve             # API on http://localhost:8000 (docs: /api/docs)
npm install && npm run dev   # app on http://localhost:3000
```

With Docker: `docker compose up --build` (needs `.env` with real
secrets). Production runs on Vercel (Next.js + Python serverless
function, same origin) with Neon Postgres — see
[deployment](docs/deployment.md).

## What it does (challenge requirements)

1. **Earlier, explainable risk identification** — consented history,
   lifestyle, metabolic, infectious, anatomical and prior-test inputs
   become individual three-state screening flags; screening is never
   presented as diagnosis.
2. **Culturally trusted experience** — discreet bilingual UI, no
   assumptions about marital status or family plans, neutral
   sample-collection wording.
3. **Lower-friction assessment** — anonymous session, teleconsult /
   blood test / sample / in-person booking with language, clinician
   and home-sampling filters.
4. **Safe triage and referral** — one route of five, red-flag override
   with static text and no LLM call, mandatory clinician sign-off,
   referral tracked to a documented outcome.
5. **Privacy by design** — consent ledger, encrypted fields,
   user-controlled shares, role access control, audit trail, export
   and one-tap delete.
6. **Demonstrable value** — 10 core + 100 variant synthetic cases with
   route agreement, zero under-triage target, citation and fairness
   metrics (`benchmark/reports/`).

## Architecture

```
intake → consent check → red flags → flags (three-state) → route
                                               ↓
trace ← persist ← explain (LLM + validator → template fallback)
                                               ↓
providers → referral → clinician sign-off → booked → outcome
```

- `app/rules_engine/` pure deterministic flags and triage (no DB or
  network); `app/orchestrator/` traced pipeline.
- `app/llm/` providers (mock, Anthropic, OpenAI-compatible, Azure
  OpenAI), versioned prompts, rejecting validator, deterministic
  templates, deterministic RAG citations over a draft excerpt corpus.
- `app/services/` business logic; `app/api/` thin routers;
  `app/models/` + `app/schemas/` ORM and Pydantic contracts.
- `rules/` versioned rule/route/param files (draft, unvalidated);
  `app/content/` bilingual strings + excerpts (Arabic needs review);
  `alembic/` migrations (7, incl. append-only triggers).
- `benchmark/` cases, variants, invariants, harness, reports;
  `tests/` pytest suite incl. Postgres-only and frontend-contract
  tests; `seed/` demo users, providers, prior results.
- `api/index.py` Vercel serverless entrypoint; `scripts/` fixture and
  corpus generators.

## Backend reference

- `make help` lists targets. Gate: `make check` (format, lint,
  typecheck, tests with coverage). `make openapi` regenerates
  `docs/openapi.json`; `make benchmark` refreshes reports.
- Env: see `.env.example`. `JWT_SECRET` + `FIELD_ENCRYPTION_KEY`
  required (fail fast). `LLM_PROVIDER=mock` by default; Azure needs
  `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_API_VERSION`.
- Tests (`make test`): deterministic, isolated SQLite per test; the
  trigger/erase tests need Postgres and run when `DATABASE_URL` points
  at a migrated Postgres (CI does this, otherwise they skip).
- Benchmark (`make benchmark`): route agreement, under-triage,
  monotonicity, parity, validator + citation + service measures,
  subgroup tables. With Azure credentials set it measures a real model.

Docs: `backend-architecture.md` (layers/flow),
`api.md` (endpoints + curl journey), `privacy-and-governance.md`,
`deployment.md`, `decisions.md`, `research-grounding.md` (WHO, AUA/ASRM,
NIST sources), `rag-grounding-design.md` (implemented, draft corpus),
`open-clinical-questions.md`, `todo.md`.

## Frontend reference

Checks: `npm run typecheck`, `npm run build`. Optional env (working
defaults): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_*_HANDLE/PASSWORD`
for the demo staff controls. Session lives in memory only (reload
starts a fresh anonymous user). English UI today; Arabic strings ship
in the data files for review.

| Route | Screen |
| --- | --- |
| `/` | Welcome |
| `/consent` | Four separate permissions, none pre-ticked |
| `/intake` | Seven topics; "Not sure" / "Rather not say" everywhere; blanks become `skipped` |
| `/results` | Flags in three states plus the workflow trace sheet |
| `/next` | One route on the care-path line; urgent gets a static full-screen message |
| `/booking` | Four service types; language/clinician filters; phone asked only here |
| `/status` | Referral stages, simulated reminders, outcome; staff demo controls; outcome note closes |
| `/privacy` | Permissions, shares with expiry/revoke, activity log, download, delete |
| `/clinician` | Review queue, brief, route edit, sign off |

Demo paths: urgent (Yes to any "Right now" item), incomplete (leave
items blank → provisional route), full journey (Yes to twist/injury →
book teleconsult → clinician sign-off → advance to closed).

`lib/types.ts` is the UI contract; `lib/api.ts` the `/api/v1` client;
`lib/mapping.ts` the pure UI↔API mapping (approximations documented
in-file, pinned by `tests/unit/test_frontend_contract.py` and the
golden fixture — regenerate with
`node scripts/regen_frontend_golden.mjs`).

Design: tokens in `app/globals.css`; saffron reserved for the user's
path; Readex Pro; reduced-motion respected; all clinical content
pending review.

## Known limitations

- Draft rules, thresholds, RAG excerpts and Arabic strings are
  unvalidated; everything clinical needs the advisor, every Arabic
  string a native reviewer, before any pilot.
- Benchmark evidence is simulated consistency only, never clinical
  safety or outcomes. No user-trust study yet (planned for the pilot).
- No retention expiry, key rotation, or load testing; single-process
  rate limiting; reminders are simulated records.
- Regulatory alignment (DoH licensing, ADHICS, PDPL, data residency)
  and EHR integration (Malaffi/Sahhatna) are roadmap, not implemented.
- Seeded demo staff credentials are public by design for evaluation.
