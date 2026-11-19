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
  with the shared `Role` enum when roles land (Phase 5). The intake schema
  must honour the option values the v0.1 rules assume: tobacco/anabolic/
  substances use never/former/current; alcohol uses never/occasional/regular;
  trying_to_conceive uses yes/no/not_applicable; semen/hormone results use
  normal/abnormal/not_done/unsure; partner bands include `35_plus`.
- Phase 4: LLM decision recorded (DR-006): mock default, openai_compatible
  real target with Anthropic as alternative. Still needed: the local server
  address or hosted keys, and the `LLM_MODEL` name.
- Phase 7: revisit `uv sync` for `make dev` once `uv.lock` exists. Benchmark
  invariants must use weak monotonicity (DR-007): only non-trigger answers
  go missing in the monotonicity check.
