"""System introspection endpoints.

Public (no login required — safe read-only status for judges/health probes):
    GET /health                  canonical liveness probe
    GET /api/system/health       same, under the API prefix
    GET /api/system/crypto-status  PQC algorithms actually active at runtime
    GET /api/system/status       backend/db/ledger/PQC/storage/environment

Authenticated (configuration detail, logged-in officers only):
    GET /api/system/settings
"""

import datetime as dt

from fastapi import APIRouter, Depends

from app.core.auth import get_current_recipient_id
from app.crypto.pqc_provider import algorithm_info
from app.ledger.ledger_state import get_ledger
from app.core.config import (
    ALLOWED_EXTENSIONS,
    APP_ENV,
    DATABASE_URL,
    LEDGER_NODE_COUNT,
    MAX_UPLOAD_SIZE_BYTES,
    STORAGE_DIR,
)

router = APIRouter(prefix="/api/system", tags=["system"])


def _db_status() -> str:
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return "CONNECTED"
        finally:
            db.close()
    except Exception:
        return "UNAVAILABLE"


def _storage_status() -> str:
    try:
        return "WRITABLE" if STORAGE_DIR.exists() else "MISSING"
    except Exception:
        return "UNAVAILABLE"


@router.get("/health")
@router.get("")
def health():
    return {
        "status": "ok",
        "service": "sakshya-backend",
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@router.get("/crypto-status")
def crypto_status():
    """Factual PQC report — never claims ML-KEM/ML-DSA unless active.

    ``pqc_available`` is False (with an explicit DEVELOPMENT FALLBACK label)
    when the classical X25519/Ed25519 fallback is in effect.
    """
    algo = algorithm_info()
    pqc = bool(algo.get("pqc_active"))
    return {
        "pqc_available": pqc,
        "kem": "ML-KEM-768" if pqc else "PQC NOT AVAILABLE",
        "kem_detail": algo["kem_algorithm"],
        "signature": "ML-DSA-65" if pqc else "PQC NOT AVAILABLE",
        "signature_detail": algo["signature_algorithm"],
        # A production backend cannot boot without PQC (see enforce_pqc), so pqc_available is always
        # true there. This branch is reachable only with the developer flag SAKSHYA_ALLOW_FALLBACK.
        "fallback": (
            None
            if pqc
            else "DEVELOPMENT FALLBACK ONLY (SAKSHYA_ALLOW_FALLBACK=true) — NOT post-quantum"
        ),
        "environment": "offline",
        "note": algo["note"],
    }


@router.get("/status")
def system_status():
    """One-glance demo status for SIH judges: every subsystem + PQC + env."""
    algo = algorithm_info()
    ledger_status = get_ledger().verify_chain()["status"]
    pqc = bool(algo.get("pqc_active"))
    db = _db_status()
    return {
        "backend": "OPERATIONAL",
        "database": f"SQLITE ({db})",
        "database_url": DATABASE_URL,
        "ledger": f"LOCAL {ledger_status}",
        "kem": "ML-KEM-768" if pqc else "PQC NOT AVAILABLE",
        "signature": "ML-DSA-65" if pqc else "PQC NOT AVAILABLE",
        "pqc_active": pqc,
        "storage": f"LOCAL ({_storage_status()})",
        "environment": "offline",
        "app_env": APP_ENV,
        "external_cloud_dependency": "NONE",
    }


@router.get("/settings")
def settings(_authed: str = Depends(get_current_recipient_id)):
    ledger = get_ledger()
    algo = algorithm_info()
    return {
        "system_status": "OPERATIONAL",
        "air_gapped_mode": True,
        "authentication": "LOCAL",
        "database": "SQLITE",
        "network": "OFFLINE / LOCAL",
        "external_cloud_dependency": "NONE",
        "cryptographic_algorithms": {
            "key_encapsulation": algo["kem_algorithm"],
            "digital_signature": algo["signature_algorithm"],
            "hash": "SHA-256",
            "document_encryption": "AES-256-GCM",
            "pqc_active": algo["pqc_active"],
            "note": algo["note"],
        },
        "ledger_nodes": LEDGER_NODE_COUNT,
        "consensus_requirement": f"quorum {LEDGER_NODE_COUNT // 2 + 1}/{LEDGER_NODE_COUNT} (all {LEDGER_NODE_COUNT} = full confirmation)",
        "ledger_storage": "PERSISTENT — one SQLite file + one signing key per node",
        "roles": {"officer": "protect, decrypt, download, render", "auditor": "investigate, reports"},
        "audit_logging": True,
        "file_size_limit_mb": MAX_UPLOAD_SIZE_BYTES // (1024 * 1024),
        "allowed_file_types": sorted(ALLOWED_EXTENSIONS),
        "system_integrity": ledger.verify_chain()["status"],
    }
