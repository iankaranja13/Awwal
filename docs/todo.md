# Follow-ups

## Needs network or services (could not run in the sandbox)

- Generate `uv.lock` with network access (`uv lock`) and commit it.
- Run `make format-check`, `make lint` and `make typecheck` (ruff, mypy) with
  network access; fix any findings.
- Install the pre-commit hooks (`pre-commit install`) and run them once.
- Run `docker compose up --build` against a live Docker daemon; verify
  migrations run on API start and the demo journey works.
- Run CI on push and confirm the quality gate passes there.
- Run `pip-audit` if available.

## Needs people or decisions

- Clinical advisor: confirm or replace every draft rule, threshold, route
  and red flag in `docs/open-clinical-questions.md`.
- Arabic reviewer: review every string marked `needs_native_review`.
- Team: pick the local OpenAI-compatible server address (or hosted keys)
  and the `LLM_MODEL` name for non-mock runs.
- Extend `banned_patterns.py` with the clinician and native reviewer.
