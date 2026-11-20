"""Deterministic benchmark variant generation from core cases.

Variants change age band, language, skipped or unsure fields and add
contradictory inputs. Nothing here carries clinician expectations; variants
are checked against invariants only.
"""

import copy
import random
from typing import Any

AGE_BANDS = ["18_24", "25_29", "30_34", "35_39", "40_44", "45_plus"]
MISSING_STATUSES = ["skipped", "unsure", "prefer_not_to_say"]

# Contradictory but valid inputs the engine must handle gracefully.
CONTRADICTIONS: list[dict[str, dict[str, Any]]] = [
    {"trying_to_conceive": {"value": "no", "status": "answered"},
     "months_trying": {"value": 14, "status": "answered"}},
    {"prior_semen_analysis_result": {"value": "normal", "status": "answered"},
     "months_trying": {"value": 24, "status": "answered"}},
    {"tobacco_vaping_shisha": {"value": "never", "status": "answered"},
     "alcohol_use": {"value": "regular", "status": "answered"}},
]

# Fields whose trigger values must never be dropped by missing-ing.
TRIGGER_GUARD = {"testicular_pain_sudden_severe", "testicular_lump", "testicular_swelling",
                 "fever_with_testicular_pain", "blood_in_semen"}


def _is_trigger(item_id: str, answer: dict[str, Any]) -> bool:
    """Detect trigger-valued answers that missing-ing must keep.

    Args:
        item_id: Intake item id.
        answer: Stored answer mapping.

    Returns:
        True when the answer could drive presence or urgency.
    """
    if answer.get("status") != "answered":
        return False
    value = answer.get("value")
    if item_id in TRIGGER_GUARD:
        return value is True
    if value is True:
        return True
    if isinstance(value, str) and value not in ("no", "never", "normal", "not_done",
                                                "not_applicable", "unsure", "under_30"):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value != 0:
        return item_id == "months_trying"
    return False


def generate_variants(
    cases: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    """Generate deterministic answer variants from core cases.

    Args:
        cases: Loaded core case mappings.
        count: Number of variants to produce.
        seed: Random seed.

    Returns:
        Variant mappings with answers, base id, mutation notes, an optional
        monotonicity source and a red-retained flag.
    """
    rng = random.Random(seed)
    pipeline_cases = [case for case in cases if not case.get("expected", {}).get("journey")]
    variants: list[dict[str, Any]] = []
    for index in range(count):
        base = pipeline_cases[index % len(pipeline_cases)]
        answers = copy.deepcopy(base["answers"])
        mutations: list[str] = []
        if rng.random() < 0.6:
            answers["age_band"] = {"value": rng.choice(AGE_BANDS), "status": "answered"}
            mutations.append("age_band")
        droppable = [item for item, answer in answers.items() if not _is_trigger(item, answer)]
        dropped = [item for item in droppable if rng.random() < 0.35]
        before = copy.deepcopy(answers) if dropped else None
        for item in dropped:
            answers[item] = {"value": None, "status": rng.choice(MISSING_STATUSES)}
        if dropped:
            mutations.append(f"dropped:{len(dropped)}")
        if rng.random() < 0.25:
            extra = copy.deepcopy(rng.choice(CONTRADICTIONS))
            for item_id, answer in extra.items():
                current = answers.get(item_id)
                if current is None or not _is_trigger(item_id, current):
                    answers[item_id] = answer
            mutations.append("contradiction")
        red_retained = any(
            item in TRIGGER_GUARD and answers.get(item, {}).get("value") is True
            for item in answers
        )
        variants.append(
            {
                "id": f"variant_{index:03d}",
                "base": base["id"],
                "mutations": mutations,
                "answers": answers,
                "monotonicity_source": before,
                "red_retained": red_retained,
            }
        )
    return variants
