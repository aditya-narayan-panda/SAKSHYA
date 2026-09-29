from __future__ import annotations

import base64
import hashlib
import os
import struct
import uuid
import datetime as dt

from sqlalchemy.orm import Session

from app.core.config import DOCUMENTS_DIR, ENCRYPTED_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES
from app.crypto.aes_cipher import generate_aes_key, encrypt_bytes, pack_encrypted_file
from app.crypto.pqc_provider import get_provider, KEM_ALGORITHM_NAME
from app.models.models import Document, Recipient, DocumentRecipient
from app.watermark.watermark_service import (
    watermark_document, generate_watermark_id, WatermarkError, UnsupportedWatermarkType,
)


class ProtectionError(Exception):
    """``code`` is machine-readable (e.g. UNSUPPORTED_WATERMARK_TYPE) and surfaced by the API."""

    def __init__(self, message: str, code: str = "PROTECTION_ERROR"):
        super().__init__(message)
        self.code = code


def generate_document_id() -> str:
    year = dt.datetime.now().year
    return f"DOC-{year}-{uuid.uuid4().hex[:6].upper()}"


def sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename)
    return "".join(c for c in base if c.isalnum() or c in "._- ") or "document"


def validate_upload(filename: str, file_bytes: bytes) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        # MUST-5: never store a document we cannot attribute (it would have a NULL watermark).
        raise ProtectionError(
            f"File type '{ext}' cannot be forensically watermarked. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            code="UNSUPPORTED_WATERMARK_TYPE",
        )
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise ProtectionError(f"File exceeds max upload size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB",
                              code="FILE_TOO_LARGE")
    if len(file_bytes) == 0:
        raise ProtectionError("Uploaded file is empty", code="EMPTY_FILE")
    # Dry-run: prove this exact file can carry (and yield back) a marker, so a corrupt PDF/DOCX is
    # rejected NOW instead of failing at every future decrypt.
    try:
        watermark_document(file_bytes, filename, generate_watermark_id())
    except UnsupportedWatermarkType as e:
        raise ProtectionError(str(e), code="UNSUPPORTED_WATERMARK_TYPE") from e
    except WatermarkError as e:
        raise ProtectionError(f"File cannot be watermarked: {e}", code="WATERMARK_EMBED_FAILED") from e
    except Exception as e:
        raise ProtectionError(f"File is not a valid {ext} document: {e}", code="WATERMARK_EMBED_FAILED") from e


def protect_document(db: Session, filename: str, file_bytes: bytes, recipient_ids: list[str]) -> dict:
    validate_upload(filename, file_bytes)
    if not recipient_ids:
        raise ProtectionError("At least one authorized recipient is required")

    recipients = db.query(Recipient).filter(Recipient.recipient_id.in_(recipient_ids)).all()
    found_ids = {r.recipient_id for r in recipients}
    missing = set(recipient_ids) - found_ids
    if missing:
        raise ProtectionError(f"Unknown or unregistered recipients: {sorted(missing)}")
    revoked = [r.recipient_id for r in recipients if r.status != "Active"]
    if revoked:
        raise ProtectionError(f"Cannot authorize revoked recipients: {revoked}")

    safe_name = sanitize_filename(filename)
    document_id = generate_document_id()
    document_hash = hashlib.sha256(file_bytes).hexdigest()

    # Backend calculates the hash itself — never trusts a client-provided hash (spec requirement).
    provider = get_provider()
    aes_key = generate_aes_key()
    blob = encrypt_bytes(file_bytes, aes_key)
    packed = pack_encrypted_file(blob.nonce, blob.ciphertext)

    encrypted_filename = f"{document_id}.enc"
    encrypted_path = ENCRYPTED_DIR / encrypted_filename
    encrypted_path.write_bytes(packed)

    document = Document(
        document_id=document_id,
        original_filename=safe_name,
        stored_filename=encrypted_filename,
        file_type=os.path.splitext(safe_name)[1].lower(),
        file_size=len(file_bytes),
        sha256_hash=document_hash,
        encrypted_path=str(encrypted_path),
        status="PROTECTED",
    )
    db.add(document)
    db.flush()  # get document_id constraints checked before we commit recipient rows

    for recipient in recipients:
        recipient_pub = base64.b64decode(recipient.public_kem_key)
        enc = provider.encapsulate(recipient_pub)
        # Package (kem_ciphertext + aes_key XOR-free direct wrap): we store the KEM
        # ciphertext AND the AES key wrapped by the KEM shared secret via AES-GCM,
        # so only the recipient's private key can ever recover the real AES key.
        wrap_blob = encrypt_bytes(aes_key, enc.shared_secret)
        # Length-prefixed (not delimiter-based) so raw ciphertext bytes can never be
        # mistaken for a separator: [4-byte kem_ct_len][kem_ct][wrapped_aes_key_blob]
        wrapped_payload = struct.pack(">I", len(enc.ciphertext)) + enc.ciphertext + pack_encrypted_file(
            wrap_blob.nonce, wrap_blob.ciphertext
        )

        db.add(DocumentRecipient(
            document_id=document_id,
            recipient_id=recipient.recipient_id,
            encapsulated_key=base64.b64encode(wrapped_payload).decode(),
            status="AUTHORIZED",
        ))

    db.commit()
    db.refresh(document)

    return {
        "document_id": document_id,
        "filename": safe_name,
        "status": "PROTECTED",
        "recipients": len(recipients),
        "encryption": "AES-256-GCM",
        "key_encapsulation": KEM_ALGORITHM_NAME,
        "integrity": "SHA-256",
        "sha256_hash": document_hash,
    }
