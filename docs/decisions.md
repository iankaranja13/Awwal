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
