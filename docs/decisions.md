# Decision records

Short what/why records for key choices. Newest last.

## DR-001: Dual health paths (`/health` and `/api/v1/health`)

What: the versioned path is canonical and appears in OpenAPI; the bare
`/health` alias is hidden from the schema and serves probes.

Why: the API contract uses the `/api/v1` base path, but liveness probes and
the Phase 0 acceptance check expect `/health` to return 200. Alternatives
(single path only) would break one of the two callers.

## DR-002: bcrypt pinned to 4.0.1

What: `bcrypt==4.0.1` is pinned in `pyproject.toml`.

Why: passlib 1.7.4 cannot detect bcrypt>=4.1 (it removed `__about__`), so an
unbounded install breaks password hashing. Revisit if passlib is replaced.

## DR-003: `make dev` uses system site packages with an offline fallback

What: the project venv is created with `--system-site-packages`; `make dev`
installs `-e ".[dev]"` online and falls back to an offline subset install.

Why: this keeps setup working in sandboxes without PyPI access while CI with
network installs the full declared set. Venv packages shadow system packages,
so declared versions always win. Revisit `uv sync` once `uv.lock` exists.

## DR-004: Normalised error body for framework errors too

What: 404, 405 and request-validation failures use the same
`{"error": {"code", "message", "details"}}` body; validation details carry
location/message/type but never raw input values.

Why: one body shape keeps the frontend contract simple, and echoing inputs
could leak sensitive data into logs and error messages. `SHARE_EXPIRED` maps
to 403 (decided now with the error table; used from Phase 6).

## DR-005: Injectable clock for token expiry checks

What: `decode_access_token` disables the JWT library expiry check and compares
`exp` against an injectable `now_fn` (default: real UTC clock).

Why: expiry behaviour becomes deterministic in tests without monkeypatching
library internals. Production callers use the default real clock. The library
issued-at check is disabled so the injected clock stays authoritative; tokens
remain short-lived through the enforced expiry check.

## DR-006: LLM provider choice (mock default, openai_compatible real target)

What: tests and offline demos use the deterministic mock provider; the real
provider target is `openai_compatible` pointed at a local server, with the
`anthropic` provider implemented as a swappable alternative. The model name
always comes from `LLM_MODEL`, never from code.

Why: a local OpenAI-compatible server keeps sensitive data on premises and
costs nothing per call during the pilot, while the provider interface keeps
Anthropic one environment variable away for quality comparison. Alternatives
(hosted-first) were rejected on privacy-by-design grounds for a prototype
handling reproductive-health answers.

## DR-007: Monotonicity holds for added uncertainty, not removed evidence

What: the tested invariant is weak monotonicity: turning non-trigger answers
into missing ones never lowers the route and never un-presents a flag.

Why: literal monotonicity (any newly missing item never lowers the route) is
unsatisfiable under the spec's own three-state rules: removing the decisive
true value of the only present flag must drop the route, since nothing
remains to route on. The engine guarantees the weak form: present conditions
evaluate only on answered values, so missing non-decisive data only adds
unknowns, which can only raise SELF_CARE to SELF_CARE_PROVISIONAL.

## DR-008: Key flags and red-flag missingness force provisional routes

What: each flag carries `key` (default true); only key-flag unknowns and
red-flag unknowns feed `missing_items` and force SELF_CARE_PROVISIONAL.
Non-key flags cover optional items (family history, prior hormones, partner
age band). Unassessed red-flag symptoms also force provisional, never plain
self-care.

Why: optional items must not block a self-care route, or nothing optional
stays optional; but an unanswered red-flag symptom is never a clean bill of
health, so uncertainty escalates. The per-flag marker keeps the choice
versioned and clinician-reviewable instead of hard-coded.

## DR-009: Hand-rolled sliding-window rate limiter

What: rate limiting is a small pure function over buckets stored on
`app.state`, instead of the stack-listed slowapi.

Why: slowapi needs a module-level limiter whose counters are global mutable
state, which the coding standards forbid; the custom limiter keeps state in
the sanctioned app holder, is deterministic under injected clocks, and adds
no dependency. It is single-process and in-memory, which fits a prototype;
a shared store would be needed for multi-worker deployment.

## DR-010: SQLite-compatible schema with Postgres-only triggers

What: the schema uses portable types (VARCHAR enums with CHECKs, generic
JSON) so tests run on SQLite; the append-only triggers apply on Postgres
only. Timestamps use an aware-UTC column type with Python-side defaults, and
the consent ledger orders by timestamp plus id for determinism.

Why: no Postgres runs in the sandbox, so SQLite keeps every test except the
two trigger-behaviour tests runnable everywhere; CI runs those against a
real Postgres service. Storing enum values (not names) keeps CHECKs honest
on both backends, and microsecond Python timestamps avoid SQLite's
second-precision ties in ledger ordering.

## DR-011: Assessment API semantics

What: POST /assess with no saved intake returns provisional (never 404);
GET /assessments shows the latest explanation; route action codes live in
code (they are frontend codes, not user-facing strings); urgent responses
carry an empty flags list with red drivers in route_reason.

Why: empty intake is just maximal missingness, so provisional is the honest
answer; latest-explanation keeps one stable record per assessment; codes in
code keep content files to human-readable strings only.

