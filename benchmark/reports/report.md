# Awwal benchmark report

Generated: 2026-11-20T11:23:29.605889+00:00 (rules 0.1, provider mock, seed 20261119)

## Core cases

Route agreement: 10/10 (10/10)

| Case | Expected | Actual | Match |
| --- | --- | --- | --- |
| case_01_clean | SELF_CARE | SELF_CARE | yes |
| case_02_lifestyle | PRIMARY_CARE | PRIMARY_CARE | yes |
| case_03_metabolic | PRIMARY_CARE | PRIMARY_CARE | yes |
| case_04_symptoms | ANDROLOGY_UROLOGY | ANDROLOGY_UROLOGY | yes |
| case_05_incomplete | SELF_CARE_PROVISIONAL | SELF_CARE_PROVISIONAL | yes |
| case_06_urgent | URGENT | URGENT | yes |
| case_07_prior_result | ANDROLOGY_UROLOGY | ANDROLOGY_UROLOGY | yes |
| case_08_private | SELF_CARE_PROVISIONAL | SELF_CARE_PROVISIONAL | yes |
| case_09_specialist | ANDROLOGY_UROLOGY | ANDROLOGY_UROLOGY | yes |
| case_10_journey | PRIMARY_CARE | PRIMARY_CARE | yes |

## Safety invariants

Red-flag under-triage count: 0 (target 0)
No-clear violations: 0
Monotonicity violations: 0
Language parity: 109/109

## LLM validator

Explanations checked: 18, passed: 18
LLM calls: 109, fallbacks: 0, rejections: 0

## Citations

Citation precision: 18/18
Present-flag coverage: 16/16
Cited-set parity: 9/9

## Subgroups

| Age | Language | Completeness | Count | Routes |
| --- | --- | --- | --- | --- |
| 18_24 | en | sparse | 7 | ANDROLOGY_UROLOGY, PRIMARY_CARE, SELF_CARE_PROVISIONAL |
| 25_29 | ar | sparse | 2 | PRIMARY_CARE, SELF_CARE_PROVISIONAL |
| 25_29 | en | partial | 1 | SELF_CARE_PROVISIONAL |
| 25_29 | en | sparse | 24 | ANDROLOGY_UROLOGY, PRIMARY_CARE, SELF_CARE_PROVISIONAL |
| 30_34 | ar | full | 1 | SELF_CARE |
| 30_34 | ar | sparse | 5 | ANDROLOGY_UROLOGY, SELF_CARE_PROVISIONAL, URGENT |
| 30_34 | en | full | 1 | SELF_CARE |
| 30_34 | en | partial | 5 | PRIMARY_CARE, SELF_CARE_PROVISIONAL |
| 30_34 | en | sparse | 31 | ANDROLOGY_UROLOGY, SELF_CARE_PROVISIONAL, URGENT |
| 35_39 | ar | sparse | 1 | PRIMARY_CARE |
| 35_39 | en | partial | 4 | SELF_CARE_PROVISIONAL |
| 35_39 | en | sparse | 18 | ANDROLOGY_UROLOGY, PRIMARY_CARE, SELF_CARE_PROVISIONAL, URGENT |
| 40_44 | en | partial | 1 | SELF_CARE_PROVISIONAL |
| 40_44 | en | sparse | 11 | ANDROLOGY_UROLOGY, PRIMARY_CARE, SELF_CARE_PROVISIONAL, URGENT |
| 45_plus | en | partial | 1 | SELF_CARE_PROVISIONAL |
| 45_plus | en | sparse | 5 | ANDROLOGY_UROLOGY, SELF_CARE_PROVISIONAL, URGENT |

## What this report does and does not show

Simulated cases and template or mock explanations only. Passing here shows internal consistency, never clinical safety or outcomes, which need a real clinical pilot.
