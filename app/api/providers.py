"""Provider directory endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import ReferralType
from app.schemas.provider import ProviderOut
from app.services.provider import list_providers

router = APIRouter(tags=["providers"])


@router.get("/providers", response_model=list[ProviderOut])
def get_providers(
    _user: CurrentUserDep,
    session: SessionDep,
    type: Annotated[ReferralType | None, Query()] = None,
    language: Annotated[str | None, Query(max_length=16)] = None,
    clinician_gender: Annotated[Literal["male", "female"] | None, Query()] = None,
    tele: Annotated[bool | None, Query()] = None,
    home_sampling: Annotated[bool | None, Query()] = None,
) -> list[ProviderOut]:
    """List providers with optional filters.

    Args:
        _user: Authenticated user (unused beyond authentication).
        session: Request database session.
        type: Service type filter.
        language: Language filter.
        clinician_gender: Clinician gender filter.
        tele: Teleconsult filter.
        home_sampling: Home sampling filter.

    Returns:
        Matching providers ordered by name.
    """
    rows = list_providers(
        session,
        type=type,
        language=language,
        clinician_gender=clinician_gender,
        tele=tele,
        home_sampling=home_sampling,
    )
    return [
        ProviderOut(
            id=row.id,
            name=row.name,
            type=row.type,
            languages=list(row.languages),
            clinician_gender=row.clinician_gender,
            tele=row.tele,
            home_sampling=row.home_sampling,
            notes=row.notes,
            mock=row.mock,
        )
        for row in rows
    ]
