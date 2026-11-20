"""Excerpt corpus loading and deterministic retrieval."""

import json
from pathlib import Path

import pytest

from app.core.enums import Language
from app.llm.retrieval import build_excerpt_index, excerpts_for_flag
from app.services.content import ContentError, ExcerptsFile, load_excerpts
from tests.unit.rule_helpers import APP_CONTENT_DIR


def _write_corpus(path: Path, payload: dict[str, object]) -> str:
    """Write one corpus file and return its directory."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "excerpts.en.json").write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _entry(excerpt_id: str = "EXC_A", flag: str = "FLAG_A") -> dict[str, object]:
    """Build one excerpt entry mapping."""
    return {
        "id": excerpt_id,
        "text": "Draft pointer.",
        "applies_to_flags": [flag],
        "source_hint": "TO BE CONFIRMED",
        "verbatim": False,
        "requires_clinical_validation": True,
    }


def test_shipped_corpus_covers_all_flags_in_both_languages() -> None:
    """Load the real corpus and require one draft excerpt per flag."""
    for language in (Language.EN, Language.AR):
        loaded = load_excerpts(str(APP_CONTENT_DIR), language)
        assert len(loaded.excerpts) == 24
        assert all(entry.id.startswith("EXC_") for entry in loaded.excerpts)
        assert all(entry.verbatim is False for entry in loaded.excerpts)
        assert all(entry.requires_clinical_validation for entry in loaded.excerpts)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    """Fail fast on duplicate excerpt ids."""
    content_dir = _write_corpus(
        tmp_path, {"needs_native_review": True, "excerpts": [_entry(), _entry()]}
    )
    load_excerpts.cache_clear()
    try:
        with pytest.raises(ContentError, match="Duplicate excerpt id"):
            load_excerpts(content_dir, Language.EN)
    finally:
        load_excerpts.cache_clear()


def test_loader_rejects_dropped_review_marker(tmp_path: Path) -> None:
    """Fail fast when the native-review marker is dropped."""
    content_dir = _write_corpus(tmp_path, {"needs_native_review": False, "excerpts": [_entry()]})
    load_excerpts.cache_clear()
    try:
        with pytest.raises(ContentError, match="needs_native_review"):
            load_excerpts(content_dir, Language.EN)
    finally:
        load_excerpts.cache_clear()


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    """Fail clearly when the corpus file is absent."""
    load_excerpts.cache_clear()
    try:
        with pytest.raises(ContentError, match="excerpts.en.json"):
            load_excerpts(str(tmp_path), Language.EN)
    finally:
        load_excerpts.cache_clear()


def test_index_groups_excerpts_by_flag_in_corpus_order() -> None:
    """Map each flag to its excerpt ids in corpus order."""
    corpus = ExcerptsFile.model_validate(
        {
            "needs_native_review": True,
            "excerpts": [
                _entry("EXC_1", "FLAG_A"),
                _entry("EXC_2", "FLAG_B"),
                _entry("EXC_3", "FLAG_A"),
            ],
        }
    )
    index = build_excerpt_index(corpus, ["FLAG_A", "FLAG_B"])
    assert index == {"FLAG_A": ("EXC_1", "EXC_3"), "FLAG_B": ("EXC_2",)}
    assert excerpts_for_flag(index, "FLAG_A") == ("EXC_1", "EXC_3")
    assert excerpts_for_flag(index, "FLAG_MISSING") == ()


def test_index_rejects_unknown_flag_reference() -> None:
    """Fail fast when an excerpt names a flag outside the rule set."""
    corpus = ExcerptsFile.model_validate(
        {"needs_native_review": True, "excerpts": [_entry("EXC_1", "FLAG_NOPE")]}
    )
    with pytest.raises(ContentError, match="unknown flag"):
        build_excerpt_index(corpus, ["FLAG_A"])
