"""Provider directory service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ReferralType
from app.models import Provider


def list_providers(
    session: Session,
    *,
    type: ReferralType | None = None,
    language: str | None = None,
    clinician_gender: str | None = None,
    tele: bool | None = None,
    home_sampling: bool | None = None,
) -> list[Provider]:
    """List providers with optional filters.

    Args:
        session: Database session.
        type: Service type filter.
        language: Language filter (provider must support it).
        clinician_gender: Clinician gender filter.
        tele: Teleconsult filter.
        home_sampling: Home sampling filter.

    Returns:
        Matching providers ordered by name.
    """
    query = select(Provider).order_by(Provider.name)
    if type is not None:
        query = query.where(Provider.type == type)
    if clinician_gender is not None:
        query = query.where(Provider.clinician_gender == clinician_gender)
    if tele is not None:
        query = query.where(Provider.tele == tele)
    if home_sampling is not None:
        query = query.where(Provider.home_sampling == home_sampling)
    rows = list(session.scalars(query).all())
    if language is not None:
        rows = [row for row in rows if language in row.languages]
    return rows


def get_provider(session: Session, provider_id: UUID) -> Provider | None:
    """Load one provider by id.

    Args:
        session: Database session.
        provider_id: Provider id.

    Returns:
        The provider, or None when unknown.
    """
    return session.get(Provider, provider_id)
