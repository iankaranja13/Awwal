"""Privacy endpoints: audit view, export, deletion and privacy copy."""

from fastapi import APIRouter

from app.core.deps import CurrentUserDep, SessionDep, SettingsDep
from app.core.enums import Language
from app.schemas.privacy import AuditEntryOut, DeleteResponse, ExportResponse, PrivacyCopy
from app.services.content import load_privacy_copy
from app.services.privacy import build_export, erase_user_data, own_audit

router = APIRouter(tags=["privacy"])


@router.get("/privacy/audit", response_model=list[AuditEntryOut])
def get_own_audit(user: CurrentUserDep, session: SessionDep) -> list[AuditEntryOut]:
    """List the caller's own audit entries.

    Args:
        user: Authenticated user.
        session: Request database session.

    Returns:
        Audit entries newest first.
    """
    return own_audit(session, user)


@router.get("/export", response_model=ExportResponse)
def get_export(user: CurrentUserDep, session: SessionDep, settings: SettingsDep) -> ExportResponse:
    """Export the caller's full data.

    Args:
        user: Authenticated user.
        session: Request database session.
        settings: Application settings.

    Returns:
        Complete export document.
    """
    return build_export(session, user, settings.field_encryption_key)


@router.delete("/me", response_model=DeleteResponse)
def delete_me(user: CurrentUserDep, session: SessionDep) -> DeleteResponse:
    """Delete the caller's personal data.

    Args:
        user: Authenticated user.
        session: Request database session.

    Returns:
        Deletion summary.
    """
    return erase_user_data(session, user, hard=False)


@router.get("/content/privacy", response_model=dict[str, PrivacyCopy])
def get_privacy_copy(settings: SettingsDep) -> dict[str, PrivacyCopy]:
    """Return bilingual privacy and data-use copy.

    Args:
        settings: Application settings.

    Returns:
        Privacy copy by language.
    """
    return {
        "en": load_privacy_copy(settings.content_dir, Language.EN),
        "ar": load_privacy_copy(settings.content_dir, Language.AR),
    }
