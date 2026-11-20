# Awwal — Challenge submission

A discreet Arabic/English digital front door for men's reproductive
health: consented intake → explainable screening signals → safe triage →
clinician-reviewed referral → documented outcome. Track: Challenge 01,
Male Reproductive Health.

- **Live demo:** https://awwal-dun.vercel.app
- **API docs:** https://awwal-dun.vercel.app/api/docs
- **Repo / branch:** `iankaranja13/Awwal`, `feature/awwal-backend`
- **Principle:** rules decide, AI explains, clinicians validate.

## Demo script (5 minutes, no login needed)

Everything runs as a guest; staff demo controls sign in automatically.

1. **Full journey:** Start → grant all four consents → answer intake
   (say Yes to "Testicular twist, injury or surgery") → signals →
   next step → book a teleconsult → status shows `clinician_review` →
   open Clinician view → sign off → back on status, advance through
   Booked → Attended → Results explained → write an outcome note to
   close. Privacy page shows shares, activity, download, delete.
2. **Urgent path:** answer Yes to any "Right now" question → static
   urgent screen, no booking, no AI text.
3. **Missing-data path:** leave "Semen analysis" blank → "A few answers
   are missing" (provisional route, never an all-clear).

Direct API staff logins (documented demo values): `navigator-demo` /
`navigator-demo`, `clinician-demo` / `clinician-demo`.

## Architecture (one paragraph)

Next.js frontend + FastAPI backend (one Vercel project, same-origin
API) on Neon Postgres. Deterministic YAML rules produce three-state
flags and one route; an LLM only writes explanations and briefs behind
a rejecting validator with template fallback; citations come from a
draft excerpt corpus. Consent ledger, encrypted fields, shares, audit,
export and delete implement privacy by design. Details:
`docs/backend-architecture.md`, `docs/api.md`,
`docs/privacy-and-governance.md`, `docs/research-grounding.md`.

## Judging criteria mapping

- **Health impact / clinical relevance:** male-specific upstream
  screening across history, lifestyle, metabolic, infectious,
  anatomical and prior-test inputs; research grounding in WHO + AUA/ASRM
  guidance (`docs/research-grounding.md`); clinician review queue with
  mandatory sign-off.
- **Technical depth:** pure rules engine, three-state logic with
  monotonicity proofs, LLM validator (EN/AR banned patterns, invented
  numbers/routes), deterministic RAG citations, contract-tested
  frontend/backend mapping, 300+ tests, CI on Postgres.
- **Working solution / demo:** live deployment above; scripted 5-minute
  journey; OpenAPI + curl guide (`docs/api.md`).
- **Responsible AI / safety / governance:** rules decide and AI only
  explains; red-flag short-circuit with static text and no LLM call;
  uncertainty escalates; NIST AI RMF-mapped guardrails; append-only
  consent/audit; honest prototype labelling, no compliance claims.
- **Scalability / deployment readiness:** serverless API + managed
  Postgres; stateless requests; migrations + seed; known gaps listed
  below and in `docs/path-to-pilot.md`.
- **Commercial viability / path to pilot:** `docs/path-to-pilot.md`
  (validation roadmap, regulatory path, integration, ops, model).

## Assumptions

- Synthetic demo data only; no real patient data anywhere.
- Rules, thresholds, routes and Arabic strings are unvalidated drafts
  (`requires_clinical_validation`, `needs_native_review`).
- Seeded demo staff credentials are public by design for evaluation.
- Reminder "sending" is simulated records; no real messaging.
- Single-process rate limiting; sessions are in-memory anonymous tokens.

## Limitations

- Not clinically validated; screening signals only, never diagnosis.
- No clinician has reviewed the rules yet
  (`docs/open-clinical-questions.md` tracks every question).
- No retention expiry, key rotation, or load testing; RAG corpus holds
  draft pointers, not verbatim guideline quotes.
- Benchmark evidence is simulated consistency (10 core cases + 100
  variants, 0 under-triage), not clinical outcomes.
- Regulatory alignment (DoH licensing, ADHICS, PDPL, data residency)
  and EHR integration (Malaffi/Sahhatna) are roadmap, not implemented.

## Reproduce locally

```sh
cp .env.example .env   # fill secrets
make migrate && make seed
make dev               # API on :8000
npm install && npm run dev   # app on :3000
make check             # gate: format, lint, typecheck, tests
make benchmark         # reports into benchmark/reports/
```
