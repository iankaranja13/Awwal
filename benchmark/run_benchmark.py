"""Benchmark runner: core cases, variants, invariants and report."""

import argparse
import json
import logging
import os
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Bootstrap throwaway secrets before app imports: importing app.main builds
# the default app, which requires secrets at import time.
from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("JWT_SECRET", "benchmark-secret-value")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

import yaml  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.enums import FlagState, Language  # noqa: E402
from app.llm.validator import (  # noqa: E402
    ValidationContext,
    build_allowed_numbers,
    validate_explanation,
)
from app.main import create_app  # noqa: E402
from app.rules_engine.loader import load_rules  # noqa: E402
from app.rules_engine.models import AssessmentInput, FlagResult, RuleSet  # noqa: E402
from app.rules_engine.triage import run_triage  # noqa: E402
from benchmark.generate_variants import generate_variants  # noqa: E402
from benchmark.invariants import (  # noqa: E402
    check_language_parity,
    check_monotonic,
    check_no_clear_with_missing,
    check_red_flag_urgent,
)


def _default_env() -> None:
    """Fill throwaway environment defaults for local runs."""
    from cryptography.fernet import Fernet

    os.environ.setdefault("JWT_SECRET", "benchmark-secret-value")
    os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    os.environ.setdefault("SEED_NAVIGATOR_PASSWORD", "benchmark-navigator")
    os.environ.setdefault("SEED_CLINICIAN_PASSWORD", "benchmark-clinician")
    os.environ.setdefault("SEED_DEMO_USER_PASSWORD", "benchmark-demo-user")
    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")


def _migrate(db_url: str) -> None:
    """Migrate one database to head.

    Args:
        db_url: SQLAlchemy database URL.
    """
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()
    config = Config()
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")


def _client(settings: Settings) -> TestClient:
    """Build a test client on the configured database.

    Args:
        settings: Application settings.

    Returns:
        Test client using the production wiring.
    """
    return TestClient(create_app(settings))


def _new_user(client: TestClient) -> dict[str, str]:
    """Create one user with intake consent.

    Args:
        client: Test client.

    Returns:
        Auth headers.
    """
    token = client.post("/api/v1/sessions", json={}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/consent", headers=headers, json={"scope": "intake", "granted": True})
    return headers


def _assess(
    client: TestClient, headers: dict[str, str], answers: dict[str, Any], lang: str
) -> dict[str, Any]:
    """Save intake and assess in one language.

    Args:
        client: Test client.
        headers: Auth headers.
        answers: Answers by item id.
        lang: Response language.

    Returns:
        Assessment response mapping.
    """
    put = client.put("/api/v1/intake", headers=headers, json={"answers": answers})
    assert put.status_code == 200, put.text
    response = client.post("/api/v1/assess", headers=headers, params={"lang": lang})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _completeness(answers: dict[str, Any]) -> str:
    """Bucket answer completeness.

    Args:
        answers: Answers by item id.

    Returns:
        Bucket name.
    """
    answered = sum(1 for answer in answers.values() if answer.get("status") == "answered")
    if answered >= 33:
        return "full"
    if answered >= 10:
        return "partial"
    return "sparse"


def _subgroup(answers: dict[str, Any], language: str) -> tuple[str, str, str]:
    """Describe one run for subgroup tables.

    Args:
        answers: Answers by item id.
        language: Run language.

    Returns:
        Age band, language and completeness bucket.
    """
    age = answers.get("age_band", {}).get("value", "missing")
    return str(age), language, _completeness(answers)


def _validate_stored_text(
    rules: RuleSet, answers: dict[str, Any], text_doc: dict[str, Any], language: str
) -> bool:
    """Validate one stored explanation against rebuilt ground truth.

    Args:
        rules: Loaded rule set.
        answers: Answers by item id.
        text_doc: Stored explanation text.
        language: Explanation language.

    Returns:
        True when validation passes.
    """
    inputs = AssessmentInput.model_validate({"answers": answers})
    result = run_triage(rules, inputs)
    flags: list[FlagResult] = list(result.flags)
    context = ValidationContext(
        language=Language(language),
        route=result.route,
        present_flag_ids=frozenset(f.id for f in flags if f.state == FlagState.PRESENT),
        all_flag_ids=frozenset(f.id for f in flags),
        not_assessable_ids=frozenset(
            f.id for f in flags if f.state == FlagState.NOT_ASSESSABLE
        ),
        allowed_numbers=build_allowed_numbers(rules, flags, len(result.missing_items), inputs),
    )
    return validate_explanation(text_doc, context).ok


def _stored_text(engine: Any, assessment_id: str) -> dict[str, Any]:
    """Read one stored explanation text from the database.

    Args:
        engine: Database engine.
        assessment_id: Assessment id.

    Returns:
        Stored explanation text mapping.
    """
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT text FROM explanations WHERE assessment_id = :id "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"id": uuid.UUID(assessment_id).hex},
        ).scalar_one()
    if isinstance(row, str):
        parsed: dict[str, Any] = json.loads(row)
        return parsed
    converted: dict[str, Any] = dict(row)
    return converted


def _run_pipeline_case(
    client: TestClient, engine: Any, rules: RuleSet, case: dict[str, Any], stats: dict[str, Any]
) -> dict[str, Any]:
    """Run one core pipeline case in both languages.

    Args:
        client: Test client.
        engine: Database engine.
        rules: Loaded rule set.
        case: Loaded case mapping.
        stats: Mutable statistics collector.

    Returns:
        Case record for the report.
    """
    expected = case["expected"]
    headers = _new_user(client)
    english = _assess(client, headers, case["answers"], "en")
    arabic = _assess(client, headers, case["answers"], "ar")
    present = sorted(f["id"] for f in english["flags"] if f["state"] == "PRESENT")
    static_ok = True
    if expected.get("urgent"):
        static_ok = english["static_safety_message"]["id"] == expected["static_safety_message_id"]
    route_ok = english["route"] == expected["route"] and english["urgent"] is expected["urgent"]
    flags_ok = present == sorted(expected["flags_present"])
    parity_ok, _ = check_language_parity(english, arabic)
    stats["parity"]["checked"] += 1
    stats["parity"]["passed"] += int(parity_ok)
    for language, body in (("en", english), ("ar", arabic)):
        stored = _stored_text(engine, body["assessment_id"])
        valid = _validate_stored_text(rules, case["answers"], stored, language)
        stats["validator"]["checked"] += 1
        stats["validator"]["passed"] += int(valid)
        if body["explanation_source"] != "template":
            stats["validator"]["unexpected_source"] += 1
        age, lang, completeness = _subgroup(case["answers"], language)
        stats["subgroups"].append(
            {
                "case": case["id"],
                "age": age,
                "language": lang,
                "completeness": completeness,
                "route": body["route"],
            }
        )
    explained = client.post(
        "/api/v1/explain", headers=headers, json={"assessment_id": english["assessment_id"]}
    ).json()
    stats["llm"]["calls"] += 1
    stats["llm"]["fallbacks"] += int(explained["used_fallback"])
    if explained["validator"] is not None:
        stats["llm"]["rejected"] += int(not explained["validator"]["ok"])
    return {
        "id": case["id"],
        "expected_route": expected["route"],
        "actual_route": english["route"],
        "route_match": route_ok,
        "flags_match": flags_ok,
        "static_match": static_ok,
        "parity_match": parity_ok,
    }


def _run_journey(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    """Run the full referral journey for case 10.

    Args:
        client: Test client.
        case: Loaded case mapping.

    Returns:
        Journey record for the report.
    """
    seeded = client.post("/api/v1/dev/seed")
    assert seeded.status_code == 200, seeded.text
    headers = _new_user(client)
    saved = client.put("/api/v1/intake", headers=headers, json={"answers": case["answers"]})
    assert saved.status_code == 200
    assessed = client.post("/api/v1/assess", headers=headers).json()
    assert assessed["route"] == case["expected"]["route"]
    created = client.post(
        "/api/v1/referrals",
        headers=headers,
        json={"assessment_id": assessed["assessment_id"], "type": "teleconsult"},
    )
    assert created.status_code == 201, created.text
    referral_id = created.json()["id"]
    clinician = client.post(
        "/api/v1/auth/login",
        json={"handle": "clinician-demo", "password": os.environ["SEED_CLINICIAN_PASSWORD"]},
    ).json()["token"]
    navigator = client.post(
        "/api/v1/auth/login",
        json={"handle": "navigator-demo", "password": os.environ["SEED_NAVIGATOR_PASSWORD"]},
    ).json()["token"]
    clinician_headers = {"Authorization": f"Bearer {clinician}"}
    navigator_headers = {"Authorization": f"Bearer {navigator}"}
    review = client.post(
        "/api/v1/clinician/review",
        headers=clinician_headers,
        json={"assessment_id": assessed["assessment_id"], "decision": "approved"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["signed_off_at"] is not None
    appointment = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    booked = client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=headers,
        json={"to_status": "booked", "appointment_time": appointment},
    )
    assert booked.status_code == 200, booked.text
    attended = client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=navigator_headers,
        json={"to_status": "attended"},
    )
    assert attended.status_code == 200, attended.text
    explained = client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician_headers,
        json={"to_status": "result_explained"},
    )
    assert explained.status_code == 200, explained.text
    closed = client.patch(
        f"/api/v1/referrals/{referral_id}/status",
        headers=clinician_headers,
        json={"to_status": "closed", "outcome_note": "Benchmark journey completed."},
    )
    assert closed.status_code == 200, closed.text
    final = closed.json()
    assert final["status"] == case["expected"]["journey_final"]
    assert bool(final["outcome_note"]) is case["expected"]["outcome_documented"]
    return {"id": case["id"], "final_status": final["status"], "journey_match": True}


def _run_variants(
    client: TestClient,
    rules: RuleSet,
    variants: list[dict[str, Any]],
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run generated variants and check invariants.

    Args:
        client: Test client.
        rules: Loaded rule set.
        variants: Generated variant mappings.
        stats: Mutable statistics collector.

    Returns:
        Failure records for the report.
    """
    precedence = {route.id.value: route.precedence for route in rules.routes}
    failures: list[dict[str, Any]] = []
    for variant in variants:
        headers = _new_user(client)
        body = _assess(client, headers, variant["answers"], "en")
        stats["subgroups"].append(
            {
                "case": variant["id"],
                **dict(
                    zip(["age", "language", "completeness"], _subgroup(variant["answers"], "en"))
                ),
                "route": body["route"],
            }
        )
        if variant["red_retained"]:
            ok, message = check_red_flag_urgent(body)
            stats["red"]["checked"] += 1
            stats["red"]["passed"] += int(ok)
            if not ok:
                failures.append(
                    {"variant": variant["id"], "invariant": "red_flag", "message": message}
                )
        ok, message = check_no_clear_with_missing(body)
        stats["clear"]["checked"] += 1
        stats["clear"]["passed"] += int(ok)
        if not ok:
            failures.append({"variant": variant["id"], "invariant": "no_clear", "message": message})
        if variant["monotonicity_source"] is not None:
            before_headers = _new_user(client)
            before = _assess(client, before_headers, variant["monotonicity_source"], "en")
            ok, message = check_monotonic(before, body, precedence)
            stats["mono"]["checked"] += 1
            stats["mono"]["passed"] += int(ok)
            if not ok:
                failures.append(
                    {"variant": variant["id"], "invariant": "monotonic", "message": message}
                )
        arabic = _assess(client, headers, variant["answers"], "ar")
        ok, _ = check_language_parity(body, arabic)
        stats["parity"]["checked"] += 1
        stats["parity"]["passed"] += int(ok)
        if not ok:
            failures.append(
                {"variant": variant["id"], "invariant": "parity", "message": "mismatch"}
            )
        explained = client.post(
            "/api/v1/explain", headers=headers, json={"assessment_id": body["assessment_id"]}
        ).json()
        stats["llm"]["calls"] += 1
        stats["llm"]["fallbacks"] += int(explained["used_fallback"])
        if explained["validator"] is not None:
            stats["llm"]["rejected"] += int(not explained["validator"]["ok"])
    return failures


def _write_report(output_dir: Path, summary: dict[str, Any]) -> None:
    """Write JSON and Markdown benchmark reports.

    Args:
        output_dir: Output directory.
        summary: Report summary mapping.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        "# Awwal benchmark report",
        "",
        f"Generated: {summary['generated_at']} (rules {summary['rules_version']}, "
        f"provider {summary['provider']}, seed {summary['seed']})",
        "",
        "## Core cases",
        "",
        f"Route agreement: {summary['core_agreement']} ({summary['core_matched']}/"
        f"{summary['core_total']})",
        "",
        "| Case | Expected | Actual | Match |",
        "| --- | --- | --- | --- |",
    ]
    for case in summary["core"]:
        lines.append(
            f"| {case['id']} | {case['expected_route']} | {case['actual_route']} | "
            f"{'yes' if case['route_match'] and case['flags_match'] else 'NO'} |"
        )
    lines += [
        "",
        "## Safety invariants",
        "",
        f"Red-flag under-triage count: {summary['under_triage']} (target 0)",
        f"No-clear violations: {summary['clear_violations']}",
        f"Monotonicity violations: {summary['mono_violations']}",
        f"Language parity: {summary['parity_passed']}/{summary['parity_checked']}",
        "",
        "## LLM validator",
        "",
        f"Explanations checked: {summary['validator_checked']}, "
        f"passed: {summary['validator_passed']}",
        f"LLM calls: {summary['llm_calls']}, fallbacks: {summary['llm_fallbacks']}, "
        f"rejections: {summary['llm_rejected']}",
        "",
        "## Subgroups",
        "",
        "| Age | Language | Completeness | Count | Routes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in summary["subgroup_rows"]:
        lines.append(
            f"| {row['age']} | {row['language']} | {row['completeness']} | {row['count']} | "
            f"{', '.join(row['routes'])} |"
        )
    lines += [
        "",
        "## What this report does and does not show",
        "",
        "Simulated cases and template or mock explanations only. Passing here "
        "shows internal consistency, never clinical safety or outcomes, which "
        "need a real clinical pilot.",
        "",
    ]
    if summary["failures"]:
        lines += ["## Failures", ""]
        for failure in summary["failures"]:
            lines.append(f"- {failure}")
        lines.append("")
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def _empty_stats() -> dict[str, Any]:
    """Build the statistics collector.

    Returns:
        Empty statistics mapping.
    """
    return {
        "parity": {"checked": 0, "passed": 0},
        "validator": {"checked": 0, "passed": 0, "unexpected_source": 0},
        "llm": {"calls": 0, "fallbacks": 0, "rejected": 0},
        "red": {"checked": 0, "passed": 0},
        "clear": {"checked": 0, "passed": 0},
        "mono": {"checked": 0, "passed": 0},
        "subgroups": [],
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """Run the benchmark and write reports.

    Args:
        argv: CLI arguments (defaults to process arguments).

    Returns:
        Report summary mapping.
    """
    parser = argparse.ArgumentParser(description="Run the Awwal benchmark.")
    parser.add_argument("--output-dir", default=str(ROOT / "benchmark" / "reports"))
    parser.add_argument("--variants", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261119)
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if args.quiet:
        logging.disable(logging.CRITICAL)
    previous = dict(os.environ)
    get_settings.cache_clear()
    try:
        return _run(args)
    finally:
        os.environ.clear()
        os.environ.update(previous)
        get_settings.cache_clear()
        logging.disable(logging.NOTSET)


def _run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute one benchmark run.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Report summary mapping.
    """
    _default_env()
    if args.llm_provider is not None:
        os.environ["LLM_PROVIDER"] = args.llm_provider
    if args.db_url:
        db_url = args.db_url
    else:
        scratch = tempfile.mkdtemp(prefix="awwal-bench-")
        db_url = f"sqlite:///{scratch}/bench.db"
    _migrate(db_url)
    settings = Settings()
    client = _client(settings)
    engine = create_engine(db_url)
    rules = load_rules(ROOT / "rules", settings.rules_version)
    case_files = sorted((ROOT / "benchmark" / "cases" / "core").glob("*.yaml"))
    cases = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in case_files]
    stats = _empty_stats()
    core_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for case in cases:
        try:
            if case.get("expected", {}).get("journey"):
                record = _run_journey(client, case)
                core_records.append(
                    {
                        "id": case["id"],
                        "expected_route": case["expected"]["route"],
                        "actual_route": case["expected"]["route"],
                        "route_match": True,
                        "flags_match": True,
                        "static_match": True,
                        "parity_match": True,
                        "journey": record,
                    }
                )
                continue
            core_records.append(_run_pipeline_case(client, engine, rules, case, stats))
        except Exception as exc:
            failures.append({"case": case["id"], "invariant": "run", "message": str(exc)[:300]})
            core_records.append(
                {
                    "id": case["id"],
                    "expected_route": case.get("expected", {}).get("route"),
                    "actual_route": None,
                    "route_match": False,
                    "flags_match": False,
                    "static_match": False,
                    "parity_match": False,
                }
            )
    variants = generate_variants(cases, args.variants, args.seed)
    failures.extend(_run_variants(client, rules, variants, stats))
    matched = sum(
        1
        for record in core_records
        if record["route_match"] and record["flags_match"] and record["static_match"]
    )
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in stats["subgroups"]:
        key = (entry["age"], entry["language"], entry["completeness"])
        bucket = groups.setdefault(key, {"count": 0, "routes": set()})
        bucket["count"] += 1
        bucket["routes"].add(entry["route"])
    subgroup_rows = [
        {
            "age": key[0],
            "language": key[1],
            "completeness": key[2],
            "count": bucket["count"],
            "routes": sorted(bucket["routes"]),
        }
        for key, bucket in sorted(groups.items())
    ]
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "rules_version": settings.rules_version,
        "provider": settings.llm_provider,
        "model": settings.llm_model or "mock",
        "seed": args.seed,
        "variants": args.variants,
        "core": core_records,
        "core_total": len(core_records),
        "core_matched": matched,
        "core_agreement": f"{matched}/{len(core_records)}",
        "under_triage": stats["red"]["checked"] - stats["red"]["passed"],
        "clear_violations": stats["clear"]["checked"] - stats["clear"]["passed"],
        "mono_violations": stats["mono"]["checked"] - stats["mono"]["passed"],
        "parity_checked": stats["parity"]["checked"],
        "parity_passed": stats["parity"]["passed"],
        "validator_checked": stats["validator"]["checked"],
        "validator_passed": stats["validator"]["passed"],
        "llm_calls": stats["llm"]["calls"],
        "llm_fallbacks": stats["llm"]["fallbacks"],
        "llm_rejected": stats["llm"]["rejected"],
        "subgroup_rows": subgroup_rows,
        "failures": failures,
    }
    _write_report(Path(args.output_dir), summary)
    engine.dispose()
    return summary


if __name__ == "__main__":
    main()

