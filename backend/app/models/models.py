from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, event, text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    document_id = Column(String, unique=True, index=True, nullable=False)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    sha256_hash = Column(String, nullable=False)
    encrypted_path = Column(String, nullable=False)
    status = Column(String, default="PROTECTED")  # PROTECTED | DRAFT | DISTRIBUTED
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recipients = relationship("DocumentRecipient", back_populates="document", cascade="all, delete-orphan")
    events = relationship("DecryptionEvent", back_populates="document")


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True)
    recipient_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    organization = Column(String)
    department = Column(String)
    role = Column(String)                      # job title shown in the UI (free text)
    # RBAC (MUST-8): "officer" protects/decrypts/views; "auditor" investigates + reports.
    # Deliberately separate from the free-text `role` job title above. The protector/decryptor
    # and the investigator are different people by construction.
    access_role = Column(String, nullable=False, default="officer")  # officer | auditor
    email = Column(String)
    status = Column(String, default="Active")  # Active | Revoked
    public_kem_key = Column(Text, nullable=False)      # base64
    # The matching PRIVATE signing key is held ONLY by the recipient (MUST-3); the server
    # stores nothing that can produce a signature for this recipient.
    public_signing_key = Column(Text, nullable=False)  # base64
    key_status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=utcnow)
    revoked_at = Column(DateTime, nullable=True)
    # Login credentials — PBKDF2-HMAC-SHA256, see app/core/security.py. Nullable
    # because older/imported recipients may not have a password set yet; such a
    # recipient simply cannot log in (register_recipient always sets one now).
    password_salt = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)

    documents = relationship("DocumentRecipient", back_populates="recipient")
    events = relationship("DecryptionEvent", back_populates="recipient")


class DocumentRecipient(Base):
    __tablename__ = "document_recipients"

    id = Column(Integer, primary_key=True)
    document_id = Column(String, ForeignKey("documents.document_id"), nullable=False)
    recipient_id = Column(String, ForeignKey("recipients.recipient_id"), nullable=False)
    encapsulated_key = Column(Text, nullable=False)  # base64 KEM ciphertext, NOT the AES key
    assigned_at = Column(DateTime, default=utcnow)
    status = Column(String, default="AUTHORIZED")  # AUTHORIZED | REVOKED

    document = relationship("Document", back_populates="recipients")
    recipient = relationship("Recipient", back_populates="documents")


class DecryptionEvent(Base):
    __tablename__ = "decryption_events"

    id = Column(Integer, primary_key=True)
    event_id = Column(String, unique=True, index=True, nullable=False)
    document_id = Column(String, ForeignKey("documents.document_id"), nullable=False)
    recipient_id = Column(String, ForeignKey("recipients.recipient_id"), nullable=False)
    session_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=utcnow)
    # Exact ISO string that was actually signed — MUST be used verbatim when
    # reconstructing the attribution payload for verification. `timestamp` above
    # is a DateTime column for display/sorting only; re-deriving an ISO string
    # from it is not guaranteed to byte-match what was signed (rounding/tz
    # formatting differences), which would make every re-verification fail.
    signed_timestamp = Column(String, nullable=False)
    # NEVER NULL (MUST-5): unsupported types are rejected at Protect time, so every event has a
    # real, globally-unique (64-bit) watermark. UNIQUE also makes a "swap watermark to another
    # event" edit impossible without breaking the signature.
    watermark_id = Column(String, nullable=False, unique=True, index=True)
    watermark_supported = Column(Boolean, default=True)
    document_hash = Column(String, nullable=False)      # hash of the DECRYPTED+watermarked copy
    watermark_hash = Column(String, nullable=False)     # sha256(watermark_id), re-checked on investigation
    signature = Column(Text, nullable=False)             # base64
    signature_algorithm = Column(String, nullable=False)
    status = Column(String, default="VERIFIED")
    ledger_block_id = Column(Integer, nullable=True)

    document = relationship("Document", back_populates="events")
    recipient = relationship("Recipient", back_populates="events")


class RenderEvent(Base):
    """Proof-of-viewing receipt: distinct from DecryptionEvent, which only proves
    the ciphertext was decrypted. This proves the recipient's client actually
    rendered/opened the resulting file, signed the same way (their own signing
    key) and committed to the same ledger, so a single decryption that gets
    reopened and redistributed later can be told apart from one that never was.
    """
    __tablename__ = "render_events"

    id = Column(Integer, primary_key=True)
    render_id = Column(String, unique=True, index=True, nullable=False)
    decryption_event_id = Column(String, ForeignKey("decryption_events.event_id"), nullable=False)
    document_id = Column(String, nullable=False)
    recipient_id = Column(String, nullable=False)
    signed_timestamp = Column(String, nullable=False)
    document_hash = Column(String, nullable=False)  # copied from the decryption event, not recomputed
    signature = Column(Text, nullable=False)          # base64
    signature_algorithm = Column(String, nullable=False)
    ledger_block_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AuthSession(Base):
    """Database-persisted bearer-token session.

    Replaces the old in-process ``dict`` session store so a backend restart
    no longer silently invalidates every login while the frontend still holds
    its token (the stale-session bug). Only the SHA-256 of the token is
    stored — a database leak does not expose live session tokens. Expired
    rows are purged opportunistically on login/logout.
    """

    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True)
    token_sha256 = Column(String, unique=True, index=True, nullable=False)
    recipient_id = Column(String, ForeignKey("recipients.recipient_id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True)
    investigation_id = Column(String, unique=True, index=True, nullable=False)
    uploaded_filename = Column(String, nullable=False)
    document_hash = Column(String, nullable=False)
    watermark_id = Column(String, nullable=True)
    matched_event_id = Column(String, nullable=True)
    matched_recipient_id = Column(String, nullable=True)
    matched_document_id = Column(String, nullable=True)
    signature_valid = Column(Boolean, nullable=True)
    ledger_verified = Column(Boolean, nullable=True)
    investigator_id = Column(String, nullable=True)      # auditor who ran it
    details_json = Column(Text, nullable=True)           # per-check results + warnings (JSON)
    status = Column(String, default="PENDING")  # IDENTIFIED | UNATTRIBUTED | SIGNATURE_OR_LEDGER_MISMATCH
    created_at = Column(DateTime, default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    report_id = Column(String, unique=True, index=True, nullable=False)
    report_type = Column(String, default="FORENSIC_ATTRIBUTION")
    document_id = Column(String, nullable=True)
    event_id = Column(String, nullable=True)
    investigation_id = Column(String, nullable=True)
    generated_at = Column(DateTime, default=utcnow)
    pdf_path = Column(String, nullable=True)
    json_path = Column(String, nullable=True)
    status = Column(String, default="GENERATED")


# --------------------------------------------------------------------------- #
# Append-only evidence tables (MUST-1)
#
# DecryptionEvent / RenderEvent are evidence: there is no API route that updates or deletes
# them, the ORM refuses to (listeners below), and on SQLite BEFORE UPDATE / BEFORE DELETE
# triggers abort raw SQL too. The ledger itself lives in the per-node files created by
# app/ledger/ledger_service.py, which carry the same guards.
# --------------------------------------------------------------------------- #
class AppendOnlyViolation(RuntimeError):
    pass


def _refuse(mapper, connection, target):
    raise AppendOnlyViolation(f"{type(target).__name__} rows are append-only (evidence)")


for _model in (DecryptionEvent, RenderEvent):
    event.listen(_model, "before_update", _refuse)
    event.listen(_model, "before_delete", _refuse)

APPEND_ONLY_TABLES = ("decryption_events", "render_events")


def install_append_only_guards(engine) -> None:
    """Create the BEFORE UPDATE / BEFORE DELETE triggers on evidence tables (SQLite)."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        for t in APPEND_ONLY_TABLES:
            for op in ("UPDATE", "DELETE"):
                conn.execute(text(
                    f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} "
                    f"BEGIN SELECT RAISE(ABORT, '{t} is append-only: {op} forbidden'); END;"
                ))
