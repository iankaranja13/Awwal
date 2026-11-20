"""Dev-only reset and seed endpoints."""

from fastapi import APIRouter

from app.core.deps import DevAdminDep, SessionDep, SettingsDep
from app.services.seed import reset_demo_data, seed_data

router = APIRouter(tags=["dev"])


@router.post("/dev/seed")
def post_seed(_admin: DevAdminDep, session: SessionDep, settings: SettingsDep) -> dict[str, int]:
    """Seed demo accounts, providers, consents and intakes.

    Args:
        _admin: Dev-admin gate (unused beyond gating).
        session: Request database session.
        settings: Application settings.

    Returns:
        Created row counts by section.
    """
    return seed_data(session, settings.field_encryption_key, settings.content_dir)


@router.post("/dev/reset")
def post_reset(_admin: DevAdminDep, session: SessionDep) -> dict[str, int]:
    """Delete every end-user account with its data.

    Args:
        _admin: Dev-admin gate (unused beyond gating).
        session: Request database session.

    Returns:
        Removed user count.
    """
    return reset_demo_data(session)
