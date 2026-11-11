"""Make the sibling ``ml/engage8`` package importable (one place for it).

Import ``engage8`` modules through here, e.g. ``from app.ml import engage8``,
or import this module before ``from engage8...`` imports.
"""
from __future__ import annotations

import sys

from app.config import settings

_ml_root = str(settings.ml_root)
if _ml_root not in sys.path:
    sys.path.insert(0, _ml_root)

import engage8  # noqa: E402,F401
