# Research grounding

How the Awwal prototype draws on published guidance, what it implements
from each source, and where to verify it. Key principle:

> **Rules decide. AI explains. Clinicians validate.**

Scope note: the guidelines below inform the *approach* (screening
structure, safety architecture, evaluation discipline). They do not
validate this prototype's draft rules, thresholds or wording — every rule
carries `requires_clinical_validation: true`, and nothing here is clinical
guidance. See `docs/open-clinical-questions.md` for what the clinical
advisor must still confirm.

## 1. Evidence-based clinical screening

Awwal's assessment approach draws on WHO infertility guidelines and
AUA/ASRM recommendations for male infertility evaluation and management
(World Health Organization [WHO], 2025; Brannigan et al., 2024).

Implemented:

- The intake covers the standard male-evaluation domains as screening
  questions: anatomical history, infection history, metabolic factors,
  lifestyle exposures, sexual function and symptoms, prior semen and
  hormone results, and family history (`app/content/intake_schema.json`).
- Flags are individual screening signals, never a combined score and
  never a diagnosis (`app/rules_engine/`, hard constraints 2–3).
- Each drafted rule records the guideline it is believed to come from
  alongside `source: "TO BE CONFIRMED BY CLINICAL ADVISOR"`
  (`rules/flags.v0.1.yaml`); thresholds live only in
  `rules/params.v0.1.yaml` for the advisor to confirm or replace.

## 2. Responsible AI in healthcare

The guarded AI approach reflects WHO recommendations on ethical AI
governance and NIST guidance on managing generative AI risks (WHO, 2021;
Autio et al., 2024).

Implemented, mapped to the AI RMF functions (Govern, Map, Measure,
Manage):

- Govern: the LLM is fenced by policy, not by prompting alone — it may
  only explain results and draft the clinician brief, never create,
  remove or change a flag or route, and never calculate anything
  (hard constraint 1; `app/llm/client.py`).
- Map: the known GenAI risks for this use (confabulation, diagnosis
  language, treatment advice, invented numbers) are enumerated as
  validator rejection categories (`app/llm/validator.py`,
  `app/llm/banned_patterns.py` in English and Arabic).
- Measure: the benchmark reports validator rejection and fallback rates
  plus Arabic–English parity on every run (`benchmark/run_benchmark.py`,
  `benchmark/reports/`).
- Manage: rejected or timed-out outputs fall back to deterministic
  bilingual templates; every explanation records its source, model and
  prompt version (`app/llm/templates.py`, `explanations` table).

## 3. Safety and human oversight

Awwal uses deterministic rules, missing-data checks, urgent red-flag
escalation and clinician sign-off rather than allowing AI to make
independent clinical decisions (WHO, 2021; Awwal Team, 2026).

Implemented:

- Flags and routes come from versioned rule files executed by pure code
  with no database or network access (`app/rules_engine/`).
- Every flag is three-state (`PRESENT`,
  `NOT_PRESENT_FROM_PROVIDED_DATA`, `NOT_ASSESSABLE`); missing answers
  escalate and the API never returns an all-clear
  (`app/rules_engine/flags.py`, hard constraints 4–6).
- Any present red flag stops the pipeline, routes `URGENT`, returns
  static pre-written text and makes no LLM call
  (`app/orchestrator/pipeline.py`, `app/content/static_safety.*.json`).
- Any route beyond self-care needs clinician sign-off before a referral
  can be confirmed, and every pipeline run keeps a workflow trace
  (`app/services/review.py`, `app/api/clinician.py`, `GET /trace/...`).

## 4. Testing and validation framework

The prototype includes 10 planned synthetic benchmark cases to evaluate
routing accuracy, urgent-case escalation, missing-data handling and
Arabic/English consistency (Awwal Team, 2026).

Implemented:

- Ten clinician-reviewable core cases plus ~100 generated variants run
  through the real HTTP stack (`benchmark/cases/core/`,
  `benchmark/generate_variants.py`, `benchmark/run_benchmark.py`).
- Invariants enforced on every variant: red-flag under-triage count
  target 0, no plain self-care with missing key items, route
  monotonicity under missing data, English–Arabic parity, validator pass
  (`benchmark/invariants.py`).
- The full pytest suite (unit, permissions, lifecycle, contract) with
  coverage gates, plus a frontend/backend golden contract test
  (`tests/`, `tests/fixtures/frontend_mapping_golden.json`).
- Reports state plainly what is simulated; passing shows internal
  consistency, never clinical safety or outcomes
  (`benchmark/reports/report.md`).

## References

1. World Health Organization. (2025). *Guideline for the prevention,
   diagnosis and treatment of infertility*.
   https://www.who.int/publications/i/item/9789240115774
2. Brannigan, R. E., Hermanson, L., Kaczmarek, J., Kim, S. K.,
   Kirkby, E., & Tanrikut, C. (2024). Updates to male infertility:
   AUA/ASRM guideline (2024). *The Journal of Urology*, 212(6),
   789–799. https://doi.org/10.1097/JU.0000000000004180
3. World Health Organization. (2021). *Ethics and governance of
   artificial intelligence for health*.
   https://www.who.int/publications/i/item/9789240029200
4. Autio, C., Schwartz, R., Dunietz, J., Jain, S., Stanley, M.,
   Tabassi, E., Hall, P., & Roberts, K. (2024). *Artificial
   intelligence risk management framework: Generative artificial
   intelligence profile* (NIST AI 600-1). National Institute of
   Standards and Technology. https://doi.org/10.6028/NIST.AI.600-1
5. Awwal Team. (2026). *Awwal: End-to-end build plan* [Unpublished
   project document].
