# Backend architecture

One FastAPI service plus PostgreSQL. No queues, no microservices, one
transaction per request.

## Layout

- `app/main.py` builds the app: settings, startup validation (rules,
  schema, content, prompts), engine, middleware, routers.
- `app/core/` holds settings, errors, JSON logging, JWT/security, field
  encryption, database sessions, auth dependencies and rate limiting.
- `app/rules_engine/` is pure and deterministic: rule models, a fail-fast
  loader, a three-valued evaluator, three-state flags and triage. It never
  touches the database or network.
- `app/orchestrator/` runs the assessment pipeline in seven traced steps.
- `app/llm/` holds providers (mock, Anthropic, OpenAI-compatible), prompts,
  the validator, banned patterns and deterministic templates.
- `app/services/` holds business logic; `app/api/` holds thin routers;
  `app/models/` holds SQLAlchemy models; `app/schemas/` holds Pydantic
  contracts; `app/content/` holds bilingual user-facing strings.

## Request flow (assessment)

`POST /assess` requires authentication plus intake consent, then runs:
consent check, intake load and decrypt, red-flag evaluation (short-circuits
to urgent with static text and no model call), flag evaluation, triage by
route precedence, template explanation, and persistence of the assessment,
explanation and workflow trace. `GET /trace/{id}` replays the timed steps.

## Rules decide, the model explains

Flags and routes come only from versioned YAML rule files with
`requires_clinical_validation` markers. The LLM receives structured data
(flag ids, states, snippets, language) and returns an explanation document
that the validator checks: known flags only, every present flag covered,
unknowns for unknowns, no route change, no diagnosis or treatment wording
(English and Arabic patterns), no invented numbers, and the required
disclaimer. Any failure falls back to deterministic templates. Urgent
results never call the model.

## Data and privacy

Intake answers, contacts, outcome notes and review notes are encrypted
with Fernet at the application level. Consent is append-only and checked
server-side before storing, sharing, reminding or analysis. The consent
ledger, referral events and audit log are append-only, enforced by
Postgres triggers (plus application discipline). Shares expire and
revoke; every clinician read is audited and visible to the owner.
Deletion removes personal rows, anonymises audit entries and keeps
consent receipts as the legal record.

## Roles

Anonymous users authenticate with JWT sessions; seeded navigator and
clinician accounts log in with passwords. Dependencies enforce the
permission matrix: users own their data, navigators handle logistics,
clinicians sign off and read shared records only.

## Configuration

Everything runs from environment variables (see `.env.example`):
database URL, JWT secret, field encryption key, content and rule paths,
rule version, LLM provider settings and rate limits. Missing or invalid
configuration fails fast at startup.
