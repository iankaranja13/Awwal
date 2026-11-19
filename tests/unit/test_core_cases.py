"""Core benchmark cases run end to end through the HTTP stack."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

CASE_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "cases" / "core"
CASE_FILES = sorted(CASE_DIR.glob("*.yaml"))


def _load_case(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_core_case_end_to_end(db_client: TestClient, case_path: Path) -> None:
    """Run one core case through session, consent, intake and assess."""
    case = _load_case(case_path)
    expected = case["expected"]
    token = db_client.post("/api/v1/sessions", json={}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    db_client.post("/api/v1/consent", headers=headers, json={"scope": "intake", "granted": True})
    db_client.put("/api/v1/intake", headers=headers, json={"answers": case["answers"]})
    body = db_client.post("/api/v1/assess", headers=headers).json()
    assert body["urgent"] is expected["urgent"], case["id"]
    assert body["route"] == expected["route"], case["id"]
    present = sorted(
        flag["id"] for flag in body["flags"] if flag["state"] == "PRESENT"
    )
    assert present == sorted(expected["flags_present"]), case["id"]
    if expected["urgent"]:
        assert body["explanation_source"] == "static", case["id"]
        assert body["flags"] == [], case["id"]
        assert body["static_safety_message"]["id"] == expected["static_safety_message_id"]
    else:
        assert body["explanation_source"] == "template", case["id"]
