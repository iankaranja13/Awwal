"""Deterministic mock provider for tests and offline demos."""

from typing import Any

from app.core.enums import Language, Route
from app.services.content import load_explainer, load_snippets


class MockProvider:
    """Build valid outputs from job inputs without any model call."""

    def __init__(self, content_dir: str) -> None:
        """Store the content directory.

        Args:
            content_dir: Content directory.
        """
        self.content_dir = content_dir

    def generate(
        self, system: str, user_json: dict[str, Any], json_schema: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Build a deterministic valid output for the job.

        Args:
            system: System prompt text (ignored).
            user_json: Structured job input.
            json_schema: Expected schema (ignored; the shape is fixed).
            timeout: Timeout in seconds (ignored).

        Returns:
            Valid explanation or brief document.
        """
        language = Language(user_json.get("language", "en"))
        if user_json.get("job") == "brief":
            return self._brief(user_json, language)
        return self._explain(user_json, language)

    def _explain(self, user_json: dict[str, Any], language: Language) -> dict[str, Any]:
        """Build a mock explanation.

        Args:
            user_json: Job input.
            language: Output language.

        Returns:
            Explanation-shaped mapping.
        """
        explainer = load_explainer(self.content_dir, language)
        snippets = load_snippets(self.content_dir, language)
        flags = user_json.get("flags", [])
        excerpts = user_json.get("excerpts", [])
        present = [flag for flag in flags if flag.get("state") == "PRESENT"]
        if present:
            summary = explainer.summary_signals.format(count=len(present))
        elif user_json.get("route") == Route.SELF_CARE_PROVISIONAL.value:
            summary = explainer.summary_provisional
        else:
            summary = explainer.summary_clear
        explained = [
            {
                "flag_id": flag["flag_id"],
                "explanation": snippets.snippets.get(
                    flag.get("snippet_id", ""), flag.get("label", "")
                ),
                "unknowns": list(flag.get("unknowns", [])),
                "modifiable_note": (explainer.modifiable_note if flag.get("modifiable") else None),
                "sources": [
                    excerpt["excerpt_id"]
                    for excerpt in excerpts
                    if flag["flag_id"] in excerpt.get("flag_ids", [])
                ],
            }
            for flag in flags
        ]
        return {
            "language": language.value,
            "summary": summary,
            "flags": explained,
            "next_step_text": user_json.get("next_step_text", ""),
            "disclaimer": explainer.disclaimer,
        }

    def _brief(self, user_json: dict[str, Any], language: Language) -> dict[str, Any]:
        """Build a mock clinician brief.

        Args:
            user_json: Job input.
            language: Output language.

        Returns:
            Brief-shaped mapping.
        """
        excerpts = user_json.get("excerpts", [])
        flags = [
            {
                "flag_id": flag["flag_id"],
                "state": flag["state"],
                "label": flag.get("label", ""),
                "source": flag.get("source", ""),
                "note": None,
                "sources": [
                    excerpt["excerpt_id"]
                    for excerpt in excerpts
                    if flag["flag_id"] in excerpt.get("flag_ids", [])
                ],
            }
            for flag in user_json.get("flags", [])
        ]
        return {
            "language": language.value,
            "reason_for_contact": user_json.get("reason_hint", "Review."),
            "flags": flags,
            "missing_information": list(user_json.get("missing_information", [])),
            "route": user_json.get("route", ""),
            "route_rationale": user_json.get("rationale_hint", "Routine."),
            "scope_note": user_json.get("scope_note", ""),
        }
