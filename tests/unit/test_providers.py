"""Provider directory behaviour."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import ReferralType
from tests.unit.staff_helpers import make_provider


def _seed(db_session: Session) -> None:
    make_provider(
        db_session,
        name="Alpha Tele",
        type=ReferralType.TELECONSULT,
        languages=["en"],
        clinician_gender="female",
        tele=True,
        home_sampling=False,
    )
    make_provider(
        db_session,
        name="Beta Lab",
        type=ReferralType.BLOOD_TEST,
        languages=["ar"],
        clinician_gender="male",
        tele=False,
        home_sampling=True,
    )


def test_lists_all_providers(
    db_client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """List every provider ordered by name."""
    _seed(db_session)
    body = db_client.get("/api/v1/providers", headers=auth_headers).json()
    assert [row["name"] for row in body] == ["Alpha Tele", "Beta Lab"]
    assert body[0]["mock"] is True


def test_filters_combine(
    db_client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    """Combine provider filters."""
    _seed(db_session)
    teleconsult = db_client.get("/api/v1/providers?type=teleconsult", headers=auth_headers)
    assert len(teleconsult.json()) == 1
    arabic = db_client.get("/api/v1/providers?language=ar", headers=auth_headers)
    assert len(arabic.json()) == 1
    assert (
        len(db_client.get("/api/v1/providers?clinician_gender=female", headers=auth_headers).json())
        == 1
    )
    assert len(db_client.get("/api/v1/providers?tele=true", headers=auth_headers).json()) == 1
    assert (
        len(db_client.get("/api/v1/providers?home_sampling=true", headers=auth_headers).json()) == 1
    )
    combined = db_client.get(
        "/api/v1/providers?type=teleconsult&language=ar", headers=auth_headers
    ).json()
    assert combined == []


def test_providers_require_authentication(db_client: TestClient) -> None:
    """Reject anonymous provider reads."""
    assert db_client.get("/api/v1/providers").status_code == 401
