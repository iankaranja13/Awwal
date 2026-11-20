"""Shared domain enums (fixed value sets used across layers)."""

from enum import StrEnum


class ItemStatus(StrEnum):
    """Answer status for one intake item."""

    ANSWERED = "answered"
    SKIPPED = "skipped"
    UNSURE = "unsure"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class FlagState(StrEnum):
    """Three-state screening flag outcome."""

    PRESENT = "PRESENT"
    NOT_PRESENT_FROM_PROVIDED_DATA = "NOT_PRESENT_FROM_PROVIDED_DATA"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class Route(StrEnum):
    """Triage route outcome."""

    URGENT = "URGENT"
    ANDROLOGY_UROLOGY = "ANDROLOGY_UROLOGY"
    FERTILITY_SERVICES = "FERTILITY_SERVICES"
    PRIMARY_CARE = "PRIMARY_CARE"
    SELF_CARE = "SELF_CARE"
    SELF_CARE_PROVISIONAL = "SELF_CARE_PROVISIONAL"


class Role(StrEnum):
    """Caller role."""

    USER = "user"
    NAVIGATOR = "navigator"
    CLINICIAN = "clinician"


class Language(StrEnum):
    """Supported interface language."""

    EN = "en"
    AR = "ar"


class ConsentScope(StrEnum):
    """Consent scope for data use."""

    INTAKE = "intake"
    SHARE_WITH_CLINICIAN = "share_with_clinician"
    REMINDERS = "reminders"
    AGGREGATE_ANALYTICS = "aggregate_analytics"


class ItemType(StrEnum):
    """Intake schema item type."""

    BOOLEAN = "boolean"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    NUMBER = "number"
    TEXT = "text"


class ExplanationSource(StrEnum):
    """Explanation origin."""

    LLM = "llm"
    TEMPLATE = "template"
    STATIC = "static"


class ReferralType(StrEnum):
    """Referral and provider service type."""

    TELECONSULT = "teleconsult"
    BLOOD_TEST = "blood_test"
    SAMPLE_COLLECTION = "sample_collection"
    IN_PERSON = "in_person"


class ReferralStatus(StrEnum):
    """Referral lifecycle status."""

    PROPOSED = "proposed"
    CLINICIAN_REVIEW = "clinician_review"
    CONFIRMED = "confirmed"
    BOOKED = "booked"
    ATTENDED = "attended"
    RESULT_EXPLAINED = "result_explained"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReviewDecision(StrEnum):
    """Clinician review decision."""

    APPROVED = "approved"
    REJECTED = "rejected"
