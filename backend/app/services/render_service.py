"""Rendering receipts.

A DecryptionEvent proves the ciphertext was decrypted once. It does NOT prove
the resulting file was ever actually opened/rendered on screen — nor does it
distinguish "recipient opened it once" from "recipient (or whoever now has the
file) opened it five times over three days." A RenderEvent is a second,
separately-signed, separately-ledgered receipt for that: recorded each time the
recipient's own client asks the server to attest a viewing, signed with the
SAME recipient signing key as the decryption event (non-repudiation carries
over), and chained into the same ledger.
"""
from __future__ import annotations

import base64
import hashlib
import uuid
import datetime as dt

from sqlalchemy.orm import Session

from app.crypto.pqc_provider import get_provider, SIG_ALGORITHM_NAME
from app.models.models import DecryptionEvent, RenderEvent, Recipient
from app.ledger.ledger_service import LedgerService
from app.services.decryption_service import canonicalize_attribution_payload, resolve_signing_key, SigningKeyError


class RenderError(Exception):
    pass


def generate_render_id() -> str:
    return f"VIEW-{uuid.uuid4().hex[:6].upper()}"


def record_render(db: Session, ledger: LedgerService, decryption_event_id: str, recipient_id: str,
                  signing_private_key_b64: str | None = None) -> dict:
    event = db.query(DecryptionEvent).filter(DecryptionEvent.event_id == decryption_event_id).first()
    if not event:
        raise RenderError(f"Decryption event {decryption_event_id} not found")
    # The logged-in recipient must be the same one who decrypted it — otherwise
    # anyone with an event_id (these are shown in the UI, not secret) could
    # forge a receipt claiming someone else viewed the file.
    if event.recipient_id != recipient_id:
        raise RenderError("This decryption event does not belong to the logged-in recipient")

    # Same rule as decrypt: the receipt is signed with the RECIPIENT-supplied key (never a server copy).
    recipient = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    if recipient is None or recipient.status != "Active":
        raise RenderError("Recipient is not active")
    try:
        sig_private_key = resolve_signing_key(recipient, signing_private_key_b64)
    except SigningKeyError as e:
        raise RenderError(str(e)) from e

    render_id = generate_render_id()
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "render_id": render_id,
        "decryption_event_id": decryption_event_id,
        "document_id": event.document_id,
        "recipient_id": recipient_id,
        # Reuses the ORIGINAL decryption event's document_hash rather than
        # rehashing anything on disk — this receipt attests "the file from
        # THIS decryption was rendered," and that hash is what was already
        # committed to the ledger at decrypt time.
        "document_hash": event.document_hash,
        "timestamp": timestamp,
    }
    canonical = canonicalize_attribution_payload(payload)

    provider = get_provider()
    signature = provider.sign(sig_private_key, canonical)
    del sig_private_key

    ledger_result = ledger.append_event(
        event_id=render_id,
        document_hash=event.document_hash,
        event_hash=hashlib.sha256(canonical).hexdigest(),
    )

    db_render = RenderEvent(
        render_id=render_id,
        decryption_event_id=decryption_event_id,
        document_id=event.document_id,
        recipient_id=recipient_id,
        signed_timestamp=timestamp,
        document_hash=event.document_hash,
        signature=base64.b64encode(signature).decode(),
        signature_algorithm=SIG_ALGORITHM_NAME,
        ledger_block_id=ledger_result["block_number"],
    )
    db.add(db_render)
    db.commit()

    return {
        "render_id": render_id,
        "decryption_event_id": decryption_event_id,
        "document_id": event.document_id,
        "recipient_id": recipient_id,
        "timestamp": timestamp,
        "signature_algorithm": SIG_ALGORITHM_NAME,
        "ledger_block": ledger_result,
    }


def list_renders(db: Session, decryption_event_id: str) -> list[dict]:
    rows = (
        db.query(RenderEvent)
        .filter(RenderEvent.decryption_event_id == decryption_event_id)
        .order_by(RenderEvent.id.desc())
        .all()
    )
    return [
        {
            "render_id": r.render_id,
            "recipient_id": r.recipient_id,
            "timestamp": r.signed_timestamp,
            "ledger_block_id": r.ledger_block_id,
            "signature_algorithm": r.signature_algorithm,
        }
        for r in rows
    ]
