"""
Epistula auth shim. Re-exports verify_epistula from the existing
safeguard/epistula.py via a sys.path injection so we don't fork the
implementation. When this project graduates and the old safeguard/ tree
goes away, copy epistula.py in here directly and delete the shim.
"""
from __future__ import annotations

import sys
from pathlib import Path

# safeguard/vali-django/validator/epistula.py -> safeguard/
_safeguard_root = Path(__file__).resolve().parents[2]
if str(_safeguard_root) not in sys.path:
    sys.path.insert(0, str(_safeguard_root))

from epistula import verify_epistula, create_epistula_headers  # noqa: E402,F401
