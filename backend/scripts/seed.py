"""Demo-data seeding entry point.

Run from the ``backend/`` directory::

    python scripts/seed.py

Idempotent: safe to run multiple times, never duplicates demo users or
documents.  Delegates to :mod:`app.seed` so ``python -m app.seed`` keeps
working identically.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seed import run

if __name__ == "__main__":
    run()
