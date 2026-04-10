"""
Epistula auth shim. Tries the sys.path import from safeguard/ first
(local dev), falls back to the bundled copy (Docker / production).
"""
from __future__ import annotations

import sys
from pathlib import Path

_safeguard_root = Path(__file__).resolve().parents[2]
if str(_safeguard_root) not in sys.path:
    sys.path.insert(0, str(_safeguard_root))

try:
    from epistula import verify_epistula, create_epistula_headers  # noqa: E402,F401
except ImportError:
    from .epistula_impl import verify_epistula, create_epistula_headers  # noqa: E402,F401
