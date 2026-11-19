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
