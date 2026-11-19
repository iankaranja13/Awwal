"""Explanation and brief validator behaviour."""

from typing import Any

from app.core.enums import Language, Route
from app.llm.banned_patterns import find_banned
from app.llm.templates import build_brief_template, build_template_explanation
from app.llm.validator import ValidationContext, validate_brief, validate_explanation
from app.rules_engine.models import FlagResult
from app.services.content import (
    load_explainer,
    load_next_steps,
    load_snippets,
    load_static_safety,
)
from app.services.intake import load_intake_schema
from tests.unit.rule_helpers import APP_CONTENT_DIR


def _context(**overrides: Any) -> ValidationContext:
    base: dict[str, Any] = {
        "language": Language.EN,
        "route": Route.PRIMARY_CARE,
        "present_flag_ids": frozenset({"MB_DIABETES"}),
        "all_flag_ids": frozenset({"MB_DIABETES", "LS_TOBACCO"}),
        "not_assessable_ids": frozenset({"LS_TOBACCO"}),
        "allowed_numbers": frozenset({"1"}),
    }
    base.update(overrides)
    return ValidationContext(**base)


def _output(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "language": "en",
        "summary": "Screening found 1 signal that suggests follow-up.",
        "flags": [
            {
                "flag_id": "MB_DIABETES",
                "explanation": "Diabetes is managed together with general health.",
                "unknowns": [],
                "modifiable_note": None,
            }
        ],
        "next_step_text": "Book a primary-care appointment.",
        "disclaimer": "This is a screening tool, not a diagnosis.",
    }
    base.update(overrides)
    return base


def _flag(flag_id: str, state: str, snippet_id: str) -> FlagResult:
    return FlagResult.model_validate(
        {
            "id": flag_id,
            "state": state,
            "domain": "metabolic",
            "label": {"en": "Label", "ar": "تسمية"},
            "reason_fields": [],
            "missing_fields": ["tobacco_vaping_shisha"] if state == "NOT_ASSESSABLE" else [],
            "modifiable": False,
            "suggests_route": "PRIMARY_CARE",
            "snippet_id": snippet_id,
            "source": "TO BE CONFIRMED",
            "requires_clinical_validation": True,
        }
    )


def test_valid_output_passes() -> None:
    """Accept clean well-formed explanations."""
    assert validate_explanation(_output(), _context()).ok is True


def test_template_output_passes_in_both_languages() -> None:
    """Accept template output so fallbacks never fail validation."""
    flags = [
        _flag("MB_DIABETES", "PRESENT", "SNP_DIABETES"),
        _flag("LS_TOBACCO", "NOT_ASSESSABLE", "SNP_TOBACCO"),
    ]
    for language in (Language.EN, Language.AR):
        snippets = load_snippets(str(APP_CONTENT_DIR), language)
        explainer = load_explainer(str(APP_CONTENT_DIR), language)
        output = build_template_explanation(
            Route.PRIMARY_CARE,
            flags,
            {"tobacco_vaping_shisha": "Why tobacco?"},
            language,
            snippets,
            load_next_steps(str(APP_CONTENT_DIR), language),
            explainer,
        )
        context = ValidationContext(
            language=language,
            route=Route.PRIMARY_CARE,
            present_flag_ids=frozenset({"MB_DIABETES"}),
            all_flag_ids=frozenset({"MB_DIABETES", "LS_TOBACCO"}),
            not_assessable_ids=frozenset({"LS_TOBACCO"}),
            allowed_numbers=frozenset({"1"}),
        )
        result = validate_explanation(output.model_dump(mode="json"), context)
        assert result.ok is True, (language, result.errors)


def test_template_brief_passes() -> None:
    """Accept template briefs."""
    flags = [_flag("MB_DIABETES", "PRESENT", "SNP_DIABETES")]
    explainer = load_explainer(str(APP_CONTENT_DIR), Language.EN)
    brief = build_brief_template(
        Route.PRIMARY_CARE, ["MB_DIABETES"], flags, [], Language.EN, explainer
    )
    context = ValidationContext(
        language=Language.EN,
        route=Route.PRIMARY_CARE,
        present_flag_ids=frozenset({"MB_DIABETES"}),
        all_flag_ids=frozenset({"MB_DIABETES"}),
        allowed_numbers=frozenset({"1", "24", "5", "0"}),
    )
    result = validate_brief(brief.model_dump(mode="json"), context)
    assert result.ok is True, result.errors


def test_invented_flag_rejected() -> None:
    """Reject flags outside the input."""
    output = _output()
    output["flags"].append(
        {"flag_id": "NOPE", "explanation": "Invented.", "unknowns": [], "modifiable_note": None}
    )
    result = validate_explanation(output, _context())
    assert result.ok is False
    assert any("unknown flag" in error for error in result.errors)


def test_omitted_present_flag_rejected() -> None:
    """Reject outputs that drop present flags."""
    result = validate_explanation(_output(flags=[]), _context())
    assert result.ok is False
    assert any("omitted" in error for error in result.errors)


def test_route_change_rejected() -> None:
    """Reject next steps naming a different route."""
    output = _output(next_step_text="Book an andrology or urology review.")
    result = validate_explanation(output, _context())
    assert result.ok is False
    assert any("different route" in error for error in result.errors)


def test_diagnosis_verdicts_rejected() -> None:
    """Reject fertile/infertile verdicts and condition assignment."""
    for text in ("You are infertile.", "You are fertile.", "You have diabetes."):
        output = _output()
        output["flags"][0]["explanation"] = text
        result = validate_explanation(output, _context())
        assert result.ok is False, text
    output = _output()
    output["flags"][0]["explanation"] = "You have been trying long enough to discuss review."
    assert validate_explanation(output, _context()).ok is True


def test_arabic_verdicts_rejected() -> None:
    """Reject Arabic verdicts while allowing condition nouns."""
    context = _context(language=Language.AR)
    bad = _output(
        language="ar",
        summary="وجد الفحص 1 من المؤشرات.",
        next_step_text="احجز موعد رعاية أولية.",
        disclaimer="هذه أداة فحص وليست تشخيصاً.",
    )
    bad["flags"][0]["explanation"] = "أنت عقيم."
    assert validate_explanation(bad, context).ok is False
    good = _output(
        language="ar",
        summary="وجد الفحص 1 من المؤشرات.",
        next_step_text="احجز موعد رعاية أولية.",
        disclaimer="هذه أداة فحص وليست تشخيصاً.",
    )
    good["flags"][0]["explanation"] = "العقم موضوع شائع يناقش مع الطبيب."
    assert validate_explanation(good, context).ok is True, validate_explanation(
        good, context
    ).errors


def test_treatment_advice_rejected() -> None:
    """Reject medication and dosage advice."""
    output = _output()
    output["flags"][0]["explanation"] = "Take this prescription daily; dosage 5mg."
    result = validate_explanation(output, _context())
    assert result.ok is False
    arabic = _output(
        language="ar",
        summary="وجد الفحص 1 من المؤشرات.",
        next_step_text="احجز موعد رعاية أولية.",
        disclaimer="هذه أداة فحص وليست تشخيصاً.",
    )
    arabic["flags"][0]["explanation"] = "خذ الدواء بالجرعة اليومية."
    assert validate_explanation(arabic, _context(language=Language.AR)).ok is False


def test_invented_numbers_rejected() -> None:
    """Reject numbers absent from the input."""
    output = _output(summary="Screening found 7 signals with 90 percent risk.")
    result = validate_explanation(output, _context())
    assert result.ok is False
    assert any("90" in error for error in result.errors)


def test_missing_disclaimer_rejected() -> None:
    """Reject outputs without the required disclaimer."""
    result = validate_explanation(_output(disclaimer="Thanks for using Awwal."), _context())
    assert result.ok is False


def test_missing_unknowns_rejected() -> None:
    """Reject unexplained unknowns for not-assessable flags."""
    context = _context(
        present_flag_ids=frozenset(),
        not_assessable_ids=frozenset({"MB_DIABETES"}),
    )
    result = validate_explanation(_output(), context)
    assert result.ok is False
    assert any("unknowns" in error for error in result.errors)


def test_schema_and_language_checked() -> None:
    """Reject malformed outputs and language mismatches."""
    assert validate_explanation({}, _context()).ok is False
    assert validate_explanation(_output(language="ar"), _context()).ok is False


def test_brief_route_mismatch_rejected() -> None:
    """Reject briefs that change the route."""
    brief = {
        "language": "en",
        "reason_for_contact": "Diabetes.",
        "flags": [
            {
                "flag_id": "MB_DIABETES",
                "state": "PRESENT",
                "label": "Diabetes",
                "source": "TO BE CONFIRMED",
                "note": None,
            }
        ],
        "missing_information": [],
        "route": "ANDROLOGY_UROLOGY",
        "route_rationale": "Wrong.",
        "scope_note": "Owner view.",
    }
    context = ValidationContext(
        language=Language.EN,
        route=Route.PRIMARY_CARE,
        present_flag_ids=frozenset({"MB_DIABETES"}),
        all_flag_ids=frozenset({"MB_DIABETES"}),
        allowed_numbers=frozenset(),
    )
    result = validate_brief(brief, context)
    assert result.ok is False
    assert any("route mismatch" in error for error in result.errors)


def test_content_files_hold_no_banned_language() -> None:
    """Keep every content string validator-clean in both languages."""
    content_dir = str(APP_CONTENT_DIR)
    schema = load_intake_schema(content_dir)
    for language in (Language.EN, Language.AR):
        snippets = load_snippets(content_dir, language)
        explainer = load_explainer(content_dir, language)
        next_steps = load_next_steps(content_dir, language)
        safety = load_static_safety(content_dir, language)
        texts = (
            list(snippets.snippets.values())
            + list(next_steps.steps.values())
            + [
                explainer.disclaimer,
                explainer.summary_signals,
                explainer.summary_provisional,
                explainer.summary_clear,
                explainer.modifiable_note,
            ]
            + [message.title for message in safety.messages.values()]
            + [message.body for message in safety.messages.values()]
            + [
                item.why_we_ask.en if language == Language.EN else item.why_we_ask.ar
                for item in schema.items
            ]
        )
        for text in texts:
            assert find_banned(text, language.value) == [], (language, text[:60])


def test_brief_verdicts_rejected() -> None:
    """Reject third-person verdicts in briefs."""
    brief = {
        "language": "en",
        "reason_for_contact": "Review.",
        "flags": [
            {
                "flag_id": "MB_DIABETES",
                "state": "PRESENT",
                "label": "Diabetes",
                "source": "TO BE CONFIRMED",
                "note": "He is infertile.",
            }
        ],
        "missing_information": [],
        "route": "PRIMARY_CARE",
        "route_rationale": "Routine.",
        "scope_note": "Owner view.",
    }
    context = ValidationContext(
        language=Language.EN,
        route=Route.PRIMARY_CARE,
        present_flag_ids=frozenset({"MB_DIABETES"}),
        all_flag_ids=frozenset({"MB_DIABETES"}),
        allowed_numbers=frozenset(),
    )
    assert validate_brief(brief, context).ok is False
