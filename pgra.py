#!/usr/bin/env python3
"""Cross-platform entry point for the profile-local PGRA runtime."""

from __future__ import annotations

import sys
from pathlib import Path


PROFILE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = PROFILE_ROOT / "runtime"
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from pgra.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
