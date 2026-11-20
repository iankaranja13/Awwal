#!/usr/bin/env python3
"""Build the draft RAG excerpt seed from snippets and rules.

Every excerpt reuses an existing draft snippet verbatim, so this script
invents no clinical text. The clinical advisor replaces these drafts
with approved verbatim quotes; until then each entry stays
requires_clinical_validation with verbatim=false.

Usage: .venv/bin/python scripts/build_excerpt_seed.py
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Regenerate the excerpt seed files for both languages."""
    flags_doc = yaml.safe_load((ROOT / "rules" / "flags.v0.1.yaml").read_text(encoding="utf-8"))
    flags = flags_doc["flags"]
    snippets = {}
    for language in ("en", "ar"):
        doc = json.loads((ROOT / "app" / "content" / f"snippets.{language}.json").read_text())
        snippets[language] = doc["snippets"]
    for language in ("en", "ar"):
        excerpts = []
        for flag in flags:
            snippet_id = flag["snippet_id"]
            excerpts.append(
                {
                    "id": f"EXC_{flag['id']}",
                    "text": snippets[language][snippet_id],
                    "applies_to_flags": [flag["id"]],
                    "source_hint": flag["source"],
                    "verbatim": False,
                    "requires_clinical_validation": True,
                }
            )
        payload = {"needs_native_review": True, "excerpts": excerpts}
        path = ROOT / "app" / "content" / f"excerpts.{language}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(flags)} excerpts per language")


if __name__ == "__main__":
    main()
