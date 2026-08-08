"""
Backward-compatibility shim.

The prompt templates used to live here and were reached from the backend via
a sys.path hack. They now live in backend/app/prompts.py and are imported
normally by the backend package. This module is kept as a thin re-export so
any script under scripts/legacy/ (or other external code) that still does
`from src.prompt import TRANSCRIPT_WRITER_PROMPT` keeps working.
"""
import sys
from pathlib import Path

# backend/ is a sibling of src/ at the project root.
_backend_app_dir = Path(__file__).parent.parent / "backend"
if str(_backend_app_dir) not in sys.path:
    sys.path.insert(0, str(_backend_app_dir))

from app.prompts import TRANSCRIPT_WRITER_PROMPT, TRANSCRIPT_REWRITER_PROMPT  # noqa: E402,F401

__all__ = ["TRANSCRIPT_WRITER_PROMPT", "TRANSCRIPT_REWRITER_PROMPT"]
