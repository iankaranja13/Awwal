"""Banned verdict, diagnosis and treatment patterns (English and Arabic).

Lists are intentionally tight: a false hit rejects good output and forces a
template fallback. The clinician and native reviewer extend these lists.
"""

import re

# English patterns run case-insensitively with word boundaries.
EN_PATTERNS = (
    r"\byou are ((in)?fertile|sterile|diabetic)\b",
    r"\byou're ((in)?fertile|sterile|diabetic)\b",
    r"\bsterile\b",
    r"\byou are (completely |totally |perfectly )?healthy\b",
    r"\ball clear\b",
    r"\bnothing to worry about\b",
    r"\byou have (a|an|the)\b",
    r"\byou have (diabetes|varicocele|hypertension|cholesterol|infections?|"
    r"inflammation|mumps|torsion|lump|swelling|fever|infertility|sterility)\b",
    r"\byou've got\b",
    r"\byou suffer from\b",
    r"\bdiagnosed\b",
    r"\bdiagnose you\b",
    r"\bdiagnoses you\b",
    r"\byour diagnosis\b",
    r"\bprescri\w*\b",
    r"\bdosage\b",
    r"\bdoses?\b",
    r"\bmg\b",
    r"\bmcg\b",
    r"\byou should take\b",
    r"\bstart taking\b",
)

# Extra patterns for clinician briefs (third-person verdicts).
EN_BRIEF_PATTERNS = (
    r"\bhe is (in)?fertile\b",
    r"\bman is (in)?fertile\b",
    r"\bpatient is (in)?fertile\b",
    r"\bdiagnosed with\b",
)

# Arabic patterns run on normalised text (tashkeel stripped, alef and
# ta-marbuta unified). Write patterns in normalised form.
AR_PATTERNS = (
    "انت عقيم",
    "انت خصب",
    "سليم تماما",
    "لا داعي للقلق",
    "تم تشخيصك",
    "تشخيصك",
    "شخصت",
    "الجرعه",
    "جرعتك",
    "تناول الدواء",
    "خذ الدواء",
    "ابدا العلاج",
    "وصفه",
)

AR_BRIEF_PATTERNS = (
    "شخص بالعقم",
    "تم تشخيصه",
)

# Route keywords per route. Explanations must not name a different route.
# Kept tight to avoid false hits on ordinary wording. Arabic keywords are in
# normalised form (see normalize_arabic).
ROUTE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "URGENT": ("emergency", "urgent", "ambulance", "طوارئ", "طارئه", "اسعاف", "عاجل"),
    "ANDROLOGY_UROLOGY": ("urolog", "androlog", "مسالك", "ذكوره"),
    "FERTILITY_SERVICES": ("fertil", "خصوبه"),
    "PRIMARY_CARE": (
        "primary care",
        "primary-care",
        "general practitioner",
        "family doctor",
        "family physician",
        "رعايه اوليه",
        "طبيب عام",
        "طبيب الاسره",
    ),
    "SELF_CARE": ("self-care", "self care", "رعايه ذاتيه"),
    "SELF_CARE_PROVISIONAL": ("self-care", "self care", "رعايه ذاتيه"),
}

# Each disclaimer group needs at least one phrase present (English matched
# case-insensitively, Arabic on normalised text).
REQUIRED_DISCLAIMER_GROUPS = {
    "en": (("screening",), ("not a diagnosis", "not a medical diagnosis", "no diagnosis")),
    "ar": (("فحص",), ("ليس", "ليست"), ("تشخيص",)),
}

_AR_DIACRITICS = re.compile(r"[\u064b-\u0652]")
_AR_ALEF = re.compile(r"[أإآ]")


def normalize_arabic(text: str) -> str:
    """Normalise Arabic text for robust matching.

    Args:
        text: Raw text.

    Returns:
        Text without diacritics and with unified alef and ta-marbuta.
    """
    text = _AR_DIACRITICS.sub("", text)
    text = _AR_ALEF.sub("ا", text)
    return text.replace("ة", "ه")


def find_banned(text: str, language: str, brief: bool = False) -> list[str]:
    """Find banned patterns in output text.

    Args:
        text: Text to scan.
        language: "en" or "ar".
        brief: Whether to include brief-only patterns.

    Returns:
        Matched pattern strings (empty when clean).
    """
    if language == "ar":
        haystack = normalize_arabic(text)
        patterns = list(AR_PATTERNS) + (list(AR_BRIEF_PATTERNS) if brief else [])
        return [pattern for pattern in patterns if pattern in haystack]
    lowered = text.lower()
    patterns = list(EN_PATTERNS) + (list(EN_BRIEF_PATTERNS) if brief else [])
    return [pattern for pattern in patterns if re.search(pattern, lowered)]


def find_other_route(text: str, route: str) -> list[str]:
    """Find keywords of routes other than the given one.

    Args:
        text: Text to scan (next-step text).
        route: Actual route id.

    Returns:
        Matched "<route>:<keyword>" entries (empty when clean).
    """
    lowered = text.lower()
    normalised = normalize_arabic(text)
    hits: list[str] = []
    for other, keywords in ROUTE_KEYWORDS.items():
        if other == route:
            continue
        for keyword in keywords:
            if any("\u0600" <= char <= "\u06ff" for char in keyword):
                if keyword in normalised:
                    hits.append(f"{other}:{keyword}")
            elif re.search(rf"\b{re.escape(keyword)}", lowered):
                hits.append(f"{other}:{keyword}")
    return hits


NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def find_numbers(text: str) -> list[str]:
    """Extract number tokens from output text.

    Args:
        text: Text to scan.

    Returns:
        Number strings in order of appearance.
    """
    return NUMBER_PATTERN.findall(text)
