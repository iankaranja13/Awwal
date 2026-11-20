"""Deterministic excerpt retrieval (flag id to citable excerpt ids)."""

from collections.abc import Collection, Mapping

from app.services.content import ContentError, ExcerptsFile


def build_excerpt_index(
    excerpts: ExcerptsFile, known_flag_ids: Collection[str]
) -> dict[str, tuple[str, ...]]:
    """Index excerpts by flag id, rejecting unknown flag references.

    Args:
        excerpts: Loaded excerpt corpus.
        known_flag_ids: Flag ids from the loaded rule set.

    Returns:
        Excerpt ids by flag id, in corpus order.

    Raises:
        ContentError: If an excerpt references an unknown flag.
    """
    known = set(known_flag_ids)
    index: dict[str, list[str]] = {}
    for entry in excerpts.excerpts:
        for flag_id in entry.applies_to_flags:
            if flag_id not in known:
                raise ContentError(f"Excerpt {entry.id} references unknown flag {flag_id}.")
            index.setdefault(flag_id, []).append(entry.id)
    return {flag_id: tuple(ids) for flag_id, ids in index.items()}


def excerpts_for_flag(index: Mapping[str, tuple[str, ...]], flag_id: str) -> tuple[str, ...]:
    """Return citable excerpt ids for one flag.

    Args:
        index: Excerpt ids by flag id.
        flag_id: Flag id to look up.

    Returns:
        Excerpt ids in corpus order, or empty when none apply.
    """
    return index.get(flag_id, ())
