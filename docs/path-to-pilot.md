# Path to pilot

How Awwal goes from challenge prototype to a real-world pilot. No
clinical, regulatory or commercial claims are made today; this is the
ordered plan to earn them.

## 1. Clinical validation roadmap

1. **Advisor review (weeks):** resolve every item in
   `docs/open-clinical-questions.md` — rules, thresholds, routes,
   red-flag list, intake and RAG corpus wording. Replace draft RAG
   excerpts with approved verbatim quotes.
2. **Retrospective review (1–2 months):** run de-identified historical
   vignettes through the engine with andrologists scoring route
   appropriateness; target zero under-triage before any live use.
3. **Supervised pilot (3–6 months):** deploy inside one partner clinic
   with every non-self-care case reviewed same-day; measure
   route agreement vs clinician, referral completion, time to
   appropriate evaluation, and user trust (survey).
4. **Independent evaluation:** fairness review across age, language and
   literacy groups before wider rollout.

Exit criteria for each stage are sign-off by the clinical lead, not
benchmark scores — simulated consistency never substitutes for review.

## 2. Regulatory and governance path (UAE)

- DoH digital-product licensing scoping and Responsible AI Standard
  conformity assessment.
- ADHICS and UAE PDPL gap analysis; data-residency design on UAE-hosted
  infrastructure (e.g. Azure UAE North) with residency-attested
  subprocessors.
- DPIA completion from the outline in
  `docs/privacy-and-governance.md`; retention schedule with automatic
  expiry; key-rotation and break-glass procedures.
- Arabic content cleared by native clinical reviewers.

## 3. Integration path

- Provider directory replaces seed data with credentialed listings and
  live availability.
- EHR connectivity via FHIR (referral in, outcome back) and national
  platforms (Malaffi/Sahhatna) per DoH integration guidance.
- Real reminder delivery through approved channels with the existing
  consent gates unchanged.
- Arabic-first UX pass with the bilingual toggle enabled end to end.

## 4. Operations and scale

- Managed Postgres with pooled connections, backups and point-in-time
  recovery; distributed rate limiting; structured alerting on
  validator-rejection spikes and fallback rates.
- Load and soak testing of the assessment path; autoscaling targets
  from pilot traffic.
- Model evaluations on every prompt or provider change, recorded with
  the benchmark reports; pinned model versions per release.
- Incident runbook for mis-triage reports with clinician recall loop.

## 5. Commercial sketch

B2B2C through clinics, employers and payers seeking upstream men's
health engagement: licensed screening and referral-management module
with per-site operations, or outcomes-linked pilot contracts (referral
completion, time-to-evaluation). Pricing follows the supervised pilot's
measured costs — no figures are projected here. Partnerships with
health systems for validation sites precede any direct-to-consumer
scale-up.

## 6. What stays invariant

Whatever the deployment, the safety architecture does not change:
rules decide, AI explains, clinicians validate; no combined scores;
screening never diagnosis; missing data escalates; red flags override
with static text; consent and audit stay append-only.
