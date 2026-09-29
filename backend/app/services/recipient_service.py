from __future__ import annotations

import base64
import secrets
import uuid
import datetime as dt
from dataclasses import dataclass
from typing import NamedTuple, Optional

from sqlalchemy.orm import Session

from app.models.models import Recipient
from app.crypto.pqc_provider import get_provider, SIG_ALGORITHM_NAME, KEM_ALGORITHM_NAME
from app.core.key_store import store_private_key, revoke_keys
from app.core.security import hash_password

ACCESS_ROLES = ("officer", "auditor")


def generate_recipient_id() -> str:
    return f"REC-{uuid.uuid4().hex[:6].upper()}"


def generate_initial_password() -> str:
    # Shown to the caller exactly once (see register_recipient's return value) — never stored
    # in plaintext, never retrievable again after this call returns.
    return secrets.token_urlsafe(9)


# --------------------------------------------------------------------------- #
# Recipient-held private keys (MUST-3)
# --------------------------------------------------------------------------- #
@dataclass
class KeyBundle:
    """One-time export handed to the recipient. It is returned to the caller of
    register_recipient() and NEVER persisted by the server (not in the DB, not in
    storage/keys/). The recipient keeps the signing key offline (USB) and presents it
    at decrypt time."""
    recipient_id: str
    sig_algorithm: str
    kem_algorithm: str
    sig_private_file: str      # contents of <id>.sig.private
    kem_private_file: str      # contents of <id>.kem.private
    sig_filename: str
    kem_filename: str


class Registration(NamedTuple):
    recipient: Recipient
    initial_password: str
    key_bundle: Optional[KeyBundle]      # None for auditors (they never sign anything)


def render_private_key_file(kind: str, recipient_id: str, algorithm: str, key: bytes) -> str:
    what = "signing" if kind == "sig" else "key-encapsulation"
    return (
        f"# SAKSHYA {algorithm} {what} PRIVATE key for {recipient_id}\n"
        f"# Store OFFLINE (USB). The server does not keep a copy of the signing key:\n"
        f"# if you lose it nobody can sign on your behalf, and it cannot be recovered.\n"
        f"{base64.b64encode(key).decode()}\n"
    )


def parse_private_key_text(text: str) -> bytes:
    """Accepts the exported *.private file contents OR a bare base64 string (paste).
    Lines starting with '#' are comments. Raises ValueError on garbage."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        raise ValueError("empty key")
    try:
        return base64.b64decode("".join(lines), validate=True)
    except Exception as e:
        raise ValueError("signing key is not valid base64") from e


def register_recipient(
    db: Session, name: str, organization: str, department: str, role: str, email: str,
    recipient_id: str | None = None, access_role: str = "officer",
) -> Registration:
    if access_role not in ACCESS_ROLES:
        raise ValueError(f"access_role must be one of {ACCESS_ROLES}")
    provider = get_provider()

    # Deterministic IDs (e.g. REC-OFFICER01) when the caller supplies one — used by the demo seed.
    recipient_id = (recipient_id or generate_recipient_id()).strip().upper()
    if db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first():
        raise ValueError(f"Recipient {recipient_id} already exists")

    kem_kp = provider.generate_kem_keypair()
    sig_kp = provider.generate_sig_keypair()

    bundle: Optional[KeyBundle] = None
    if access_role == "officer":
        # KEM private key: a master-key-wrapped copy stays server-side (the server unwraps the
        # per-document AES key on decrypt; also the recovery copy the spec allows).
        store_private_key(recipient_id, "kem", kem_kp.private_key)
        # SIGNING private key: NOT stored anywhere on the server. Only its public half goes in the DB.
        bundle = KeyBundle(
            recipient_id=recipient_id,
            sig_algorithm=SIG_ALGORITHM_NAME,
            kem_algorithm=KEM_ALGORITHM_NAME,
            sig_private_file=render_private_key_file("sig", recipient_id, SIG_ALGORITHM_NAME, sig_kp.private_key),
            kem_private_file=render_private_key_file("kem", recipient_id, KEM_ALGORITHM_NAME, kem_kp.private_key),
            sig_filename=f"{recipient_id}.sig.private",
            kem_filename=f"{recipient_id}.kem.private",
        )

    initial_password = generate_initial_password()
    salt_b64, hash_b64 = hash_password(initial_password)

    recipient = Recipient(
        recipient_id=recipient_id,
        name=name,
        organization=organization,
        department=department,
        role=role,
        access_role=access_role,
        email=email,
        status="Active",
        public_kem_key=base64.b64encode(kem_kp.public_key).decode(),
        public_signing_key=base64.b64encode(sig_kp.public_key).decode(),
        key_status="ACTIVE",
        password_salt=salt_b64,
        password_hash=hash_b64,
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    # Returned ONLY here, at creation time. The caller (API layer) hands the key bundle and the
    # initial password to the recipient once and must not log or persist either.
    return Registration(recipient, initial_password, bundle)


def set_recipient_password(db: Session, recipient: Recipient, password: str) -> None:
    """Used by seed.py to set known demo passwords."""
    salt_b64, hash_b64 = hash_password(password)
    recipient.password_salt = salt_b64
    recipient.password_hash = hash_b64
    db.commit()


def revoke_recipient(db: Session, recipient_id: str) -> Recipient | None:
    recipient = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    if not recipient:
        return None
    recipient.status = "Revoked"
    recipient.key_status = "REVOKED"
    recipient.revoked_at = dt.datetime.now(dt.timezone.utc)
    revoke_keys(recipient_id)
    db.commit()
    db.refresh(recipient)
    return recipient
