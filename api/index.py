"""Vercel serverless entrypoint: expose the FastAPI app.

Vercel detects the ``app`` object as the ASGI handler. Paths resolve from
the project root (parent of this file's directory) because the function
working directory is not guaranteed.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RULES_DIR", str(ROOT / "rules"))
os.environ.setdefault("CONTENT_DIR", str(ROOT / "app" / "content"))

from app.main import app  # noqa: E402

__all__ = ["app"]
