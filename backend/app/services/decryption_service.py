from __future__ import annotations

import base64
import hashlib
import os
import struct
import uuid
import datetime as dt

from sqlalchemy.orm import Session

from app.core.config import DECRYPTED_DIR
from app.core.key_store import load_private_key
from app.crypto.aes_cipher import unpack_encrypted_file, decrypt_bytes
from app.crypto.pqc_provider import get_provider, SIG_ALGORITHM_NAME
from app.watermark.watermark_service import (
    generate_watermark_id, watermark_document, apply_visible_watermark,
    WatermarkError, is_supported_filename,
)
from app.models.models import Document, Recipient, DocumentRecipient, DecryptionEvent
from app.ledger.ledger_service import LedgerService
from app.services.attribution import (  # noqa: F401  (re-exported: render_service imports it from here)
    build_attribution_payload, canonicalize_attribution_payload, event_hash_of,
)
from app.services.recipient_service import parse_private_key_text


class DecryptionError(Exception):
    pass


class SigningKeyError(DecryptionError):
    """The recipient did not supply a signing key, or the one supplied is not theirs."""


def generate_event_id(db: Session) -> str:
    n = db.query(DecryptionEvent).count() + 1
    while db.query(DecryptionEvent).filter(DecryptionEvent.event_id == f"DEC-{n:04d}").first() is not None:
        n += 1
    return f"DEC-{n:04d}"


def _unwrap_aes_key(wrapped_payload: bytes, kem_private_key: bytes) -> bytes:
    provider = get_provider()
    kem_ct_len = struct.unpack(">I", wrapped_payload[:4])[0]
    offset = 4
    kem_ciphertext = wrapped_payload[offset:offset + kem_ct_len]
    offset += kem_ct_len
    wrapped_key_blob = wrapped_payload[offset:]

    shared_secret = provider.decapsulate(kem_ciphertext, kem_private_key)
    blob = unpack_encrypted_file(wrapped_key_blob)
    return decrypt_bytes(blob, shared_secret)


def resolve_signing_key(recipient: Recipient, signing_private_key_b64: str | None) -> bytes:
    """MUST-3: the signing key comes from the RECIPIENT (upload/paste), lives in memory for
    this call only, and is proven to belong to ``recipient`` (sign a random challenge, verify
    with the public key on file) BEFORE any evidence is produced. A stolen password alone
    therefore cannot create a valid DecryptionEvent."""
    if not signing_private_key_b64 or not signing_private_key_b64.strip():
        raise SigningKeyError("Your ML-DSA signing private key file is required to decrypt (the server does not hold it)")
    try:
        key = parse_private_key_text(signing_private_key_b64)
        provider = get_provider()
        challenge = b"sakshya-key-possession:" + os.urandom(16)
        ok = provider.verify(base64.b64decode(recipient.public_signing_key), challenge,
                             provider.sign(key, challenge))
    except Exception:
        raise SigningKeyError("Invalid signing key file") from None
    if not ok:
        raise SigningKeyError("The supplied signing key does not match this recipient's registered public key")
    return key


def decrypt_document(
    db: Session,
    ledger: LedgerService,
    document_id: str,
    recipient_id: str,
    signing_private_key_b64: str | None,
    apply_visible: bool = False,
) -> dict:
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise DecryptionError(f"Document {document_id} not found")

    recipient = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    if not recipient:
        raise DecryptionError(f"Recipient {recipient_id} not found")
    if recipient.status != "Active":
        raise DecryptionError(f"Recipient {recipient_id} is not active (revoked)")
    if recipient.access_role != "officer":
        raise DecryptionError(f"{recipient_id} has role '{recipient.access_role}'; only officers can decrypt")

    link = (
        db.query(DocumentRecipient)
        .filter(
            DocumentRecipient.document_id == document_id,
            DocumentRecipient.recipient_id == recipient_id,
        )
        .first()
    )
    if not link or link.status != "AUTHORIZED":
        raise DecryptionError(f"{recipient_id} is not an authorized recipient of {document_id}")
    if not is_supported_filename(document.original_filename):
        raise DecryptionError("UNSUPPORTED_WATERMARK_TYPE: this document type cannot be attributed")

    # 0. Recipient must present THEIR signing key (in memory only) before anything is decrypted.
    sig_private_key = resolve_signing_key(recipient, signing_private_key_b64)

    # 1. Recover the AES key via this recipient's KEM key (wrapped copy, unwrapped in memory only)
    kem_private_key = load_private_key(recipient_id, "kem")
    aes_key = _unwrap_aes_key(base64.b64decode(link.encapsulated_key), kem_private_key)

    # 2. Decrypt the document body
    with open(document.encrypted_path, "rb") as fh:
        blob = unpack_encrypted_file(fh.read())
    plaintext = decrypt_bytes(blob, aes_key)

    # 3. Per-session forensic watermark. Invisible dual channel is ALWAYS on; the visible stamp is
    #    OPT-IN (apply_visible) so copies stay visually identical by default (MUST-4).
    event_id = generate_event_id(db)
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    session_id = uuid.uuid4().hex
    watermark_id = generate_watermark_id()
    try:
        watermarked_bytes, wm_result = watermark_document(plaintext, document.original_filename, watermark_id)
    except WatermarkError as e:
        raise DecryptionError(f"Watermarking failed, refusing to release an un-attributable copy: {e}") from e
    visible = bool(apply_visible) and wm_result.channel == "pdf-dual"
    if visible:
        watermarked_bytes = apply_visible_watermark(
            watermarked_bytes, watermark_id, recipient.name or recipient_id, recipient_id, timestamp,
        )
    decrypted_hash = hashlib.sha256(watermarked_bytes).hexdigest()
    watermark_hash = hashlib.sha256(watermark_id.encode()).hexdigest()

    # 4. Build + sign the attribution payload (now INCLUDING session_id) with the recipient's OWN key.
    attribution_payload = build_attribution_payload(
        event_id=event_id, document_id=document_id, document_hash=decrypted_hash,
        watermark_id=watermark_id, recipient_id=recipient_id, session_id=session_id, timestamp=timestamp,
    )
    canonical = canonicalize_attribution_payload(attribution_payload)
    provider = get_provider()
    signature = provider.sign(sig_private_key, canonical)
    del sig_private_key  # drop our reference; never written anywhere

    # 5. Commit to the persistent 3-node ledger; event_hash = sha256(canonical signed payload)
    ledger_result = ledger.append_event(          # raises LedgerError (API -> 503) without quorum
        event_id=event_id,
        document_hash=decrypted_hash,
        event_hash=event_hash_of(canonical),
    )

    # 6. Persist the (append-only) event record
    db_event = DecryptionEvent(
        event_id=event_id,
        document_id=document_id,
        recipient_id=recipient_id,
        session_id=session_id,
        signed_timestamp=timestamp,
        watermark_id=watermark_id,
        watermark_supported=True,
        document_hash=decrypted_hash,
        watermark_hash=watermark_hash,
        signature=base64.b64encode(signature).decode(),
        signature_algorithm=SIG_ALGORITHM_NAME,
        status="VERIFIED",
        ledger_block_id=ledger_result["block_number"],
    )
    db.add(db_event)
    document.status = "DISTRIBUTED"
    db.commit()

    out_path = DECRYPTED_DIR / f"{event_id}_{document.original_filename}"
    out_path.write_bytes(watermarked_bytes)

    return {
        "event_id": event_id,
        "document_id": document_id,
        "recipient_id": recipient_id,
        "session_id": session_id,
        "watermark_id": watermark_id,
        "watermark_supported": True,
        "watermark_channel": wm_result.channel,
        "visible_watermark_applied": visible,
        "signature_algorithm": SIG_ALGORITHM_NAME,
        "ledger_block": ledger_result,
        "decrypted_file_path": str(out_path),
        "timestamp": timestamp,
    }
