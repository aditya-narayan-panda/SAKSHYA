"""Password hashing for recipient login — fully local, no external IdP.

Primary scheme is **bcrypt** (``bcrypt`` package, bundled in requirements).
If bcrypt is unavailable for any reason (minimal offline mirror), the module
falls back to **PBKDF2-HMAC-SHA256** from the Python standard library, which
has zero dependencies and always works.

Scheme tagging: ``password_salt == "bcrypt"`` marks a bcrypt hash in
``password_hash``; anything else is the legacy PBKDF2 ``(salt_b64, hash_b64)``
pair, so databases seeded before this change keep verifying without a
migration.  Plaintext passwords are never stored.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

try:
    import bcrypt as _bcrypt

    _HAS_BCRYPT = True
except ImportError:  # minimal offline environment — PBKDF2 fallback below
    _bcrypt = None  # type: ignore[assignment]
    _HAS_BCRYPT = False

BCRYPT_MARKER = "bcrypt"
SCHEME = "bcrypt" if _HAS_BCRYPT else "pbkdf2-sha256"

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> tuple[str, str]:
    """Hash a NEW password. Returns (salt_marker, hash_value) for storage."""
    if _HAS_BCRYPT:
        assert _bcrypt is not None
        digest = _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("ascii")
        return BCRYPT_MARKER, digest
    salt = os.urandom(16)
    digest_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return base64.b64encode(salt).decode(), base64.b64encode(digest_bytes).decode()


def verify_password(password: str, salt_b64: str | None, hash_b64: str | None) -> bool:
    """Verify against a stored pair. Returns False for missing/corrupt entries."""
    if not salt_b64 or not hash_b64:
        return False
    if salt_b64 == BCRYPT_MARKER:
        if not _HAS_BCRYPT:
            return False
        assert _bcrypt is not None
        try:
            return _bcrypt.checkpw(password.encode("utf-8"), hash_b64.encode("ascii"))
        except Exception:
            return False
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)
