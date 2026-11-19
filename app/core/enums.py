"""Shared domain enums (fixed value sets used across layers)."""

from enum import Enum


class ItemStatus(str, Enum):
    """Answer status for one intake item."""

    ANSWERED = "answered"
    SKIPPED = "skipped"
    UNSURE = "unsure"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class FlagState(str, Enum):
    """Three-state screening flag outcome."""

    PRESENT = "PRESENT"
    NOT_PRESENT_FROM_PROVIDED_DATA = "NOT_PRESENT_FROM_PROVIDED_DATA"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class Route(str, Enum):
    """Triage route outcome."""

    URGENT = "URGENT"
    ANDROLOGY_UROLOGY = "ANDROLOGY_UROLOGY"
    FERTILITY_SERVICES = "FERTILITY_SERVICES"
    PRIMARY_CARE = "PRIMARY_CARE"
    SELF_CARE = "SELF_CARE"
    SELF_CARE_PROVISIONAL = "SELF_CARE_PROVISIONAL"


class Role(str, Enum):
    """Caller role."""

    USER = "user"
    NAVIGATOR = "navigator"
    CLINICIAN = "clinician"


class Language(str, Enum):
    """Supported interface language."""

    EN = "en"
    AR = "ar"


class ConsentScope(str, Enum):
    """Consent scope for data use."""

    INTAKE = "intake"
    SHARE_WITH_CLINICIAN = "share_with_clinician"
    REMINDERS = "reminders"
    AGGREGATE_ANALYTICS = "aggregate_analytics"


class ItemType(str, Enum):
    """Intake schema item type."""

    BOOLEAN = "boolean"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    NUMBER = "number"
    TEXT = "text"
