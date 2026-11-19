# Follow-ups

## After Phase 0 (needs network or services)

- Generate `uv.lock` with network access (`uv lock`) and commit it.
- Run `make format-check`, `make lint` and `make typecheck` (ruff, mypy) with
  network access; fix any findings.
- Install the pre-commit hooks (`pre-commit install`) and run them once.
- Run `docker compose up --build` and `docker compose config` against a live
  Docker daemon; verify migrations run on API start.
- Run CI on push and confirm the quality gate passes there.
- Run `pip-audit` if available.

## Later phases

- Phase 2: first real Alembic migration; replace `TokenPayload.role: str`
  with the shared `Role` enum when roles land (Phase 5).
- Phase 4: confirm the LLM provider/model choice and key handling with the
  team before wiring a paid hosted provider (mock remains the default).
- Phase 7: revisit `uv sync` for `make dev` once `uv.lock` exists.
