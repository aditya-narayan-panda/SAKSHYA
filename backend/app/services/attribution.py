"""
Single source of truth for the signed attribution payload (MUST-5 / MUST-7).

Decrypt builds it, the recipient signs its canonical bytes, sha256(canonical) goes on the
ledger as ``event_hash``, and the investigator REBUILDS it from the stored DecryptionEvent
row with this very function — so signer and verifier can never drift apart. ``session_id``
is part of the payload (previously generated but never signed nor ledgered).
"""
from __future__ import annotations

import hashlib
import json

PAYLOAD_FIELDS = (
    "event_id", "document_id", "document_hash", "watermark_id",
    "recipient_id", "session_id", "timestamp",
)


def build_attribution_payload(*, event_id: str, document_id: str, document_hash: str,
                              watermark_id: str, recipient_id: str, session_id: str,
                              timestamp: str) -> dict:
    return {
        "event_id": event_id,
        "document_id": document_id,
        "document_hash": document_hash,
        "watermark_id": watermark_id,
        "recipient_id": recipient_id,
        "session_id": session_id,
        "timestamp": timestamp,
    }


def canonicalize_attribution_payload(payload: dict) -> bytes:
    """Deterministic JSON so sign() and verify() always hash the exact same bytes."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def event_hash_of(canonical: bytes) -> str:
    return hashlib.sha256(canonical).hexdigest()


def payload_from_event(event) -> dict:
    """Rebuild the signed payload from a stored DecryptionEvent. ``signed_timestamp`` is used
    VERBATIM (the DateTime column is display-only and may not round-trip byte-for-byte)."""
    return build_attribution_payload(
        event_id=event.event_id,
        document_id=event.document_id,
        document_hash=event.document_hash,
        watermark_id=event.watermark_id,
        recipient_id=event.recipient_id,
        session_id=event.session_id,
        timestamp=event.signed_timestamp,
    )
