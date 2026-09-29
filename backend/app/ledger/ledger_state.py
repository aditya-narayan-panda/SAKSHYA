"""
Process-wide LedgerService singleton.

The ledger is persistent (per-node SQLite files under ``LEDGER_DIR`` + per-node signing
keys under ``KEYS_DIR``), so a backend restart re-opens the SAME chain: same height,
same hashes, ``GET /api/ledger/verify`` still VERIFIED. ``init_ledger()`` is called from
the app startup hook so key-loading / DB problems surface at boot, not on first request.
"""
from __future__ import annotations

from app.ledger.ledger_service import LedgerService
from app.core.config import LEDGER_NODE_COUNT

_ledger_instance: LedgerService | None = None


def get_ledger() -> LedgerService:
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = LedgerService(node_count=LEDGER_NODE_COUNT)
    return _ledger_instance


def init_ledger() -> LedgerService:
    return get_ledger()


def reset_ledger_singleton() -> None:
    """Drop the in-process handle (does NOT touch disk). Used by tests to simulate a restart."""
    global _ledger_instance
    _ledger_instance = None
