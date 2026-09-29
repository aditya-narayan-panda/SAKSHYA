"""Bearer-token sessions for recipient login.

Sessions are persisted in the local SQLite database (``auth_sessions``
table, keyed by SHA-256 of the token — never the raw token), so they
survive a backend restart and there is no stale-session split-brain where
the frontend holds a token the backend has forgotten.  This is still fully
local: no Redis, no external session store, no network.

Expiry is 12 hours.  If the frontend presents an unknown/expired token it
gets a clean ``401`` and must redirect to ``/login`` with the message
"Your session has expired. Please log in again." (see ``frontend/src/api.js``
and ``LoginScreen``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db

_SESSION_TTL = dt.timedelta(hours=12)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def purge_expired_sessions(db: Session) -> None:
    """Best-effort cleanup of expired rows; safe to call on every login."""
    from app.models.models import AuthSession

    try:
        db.query(AuthSession).filter(AuthSession.expires_at < _utcnow()).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()


def create_session(db: Session, recipient_id: str) -> str:
    """Create a session for ``recipient_id``; returns the raw bearer token."""
    from app.models.models import AuthSession

    purge_expired_sessions(db)
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_sha256=_token_hash(token),
            recipient_id=recipient_id,
            expires_at=_utcnow() + _SESSION_TTL,
        )
    )
    db.commit()
    return token


def destroy_session(db: Session, token: str) -> None:
    from app.models.models import AuthSession

    db.query(AuthSession).filter(
        AuthSession.token_sha256 == _token_hash(token)
    ).delete(synchronize_session=False)
    db.commit()


def resolve_session(db: Session, token: str) -> str | None:
    """Return the ``recipient_id`` for a live token, else None."""
    from app.models.models import AuthSession

    row = (
        db.query(AuthSession)
        .filter(AuthSession.token_sha256 == _token_hash(token))
        .first()
    )
    if not row:
        return None
    if _as_aware(row.expires_at) <= _utcnow():
        db.delete(row)
        db.commit()
        return None
    return row.recipient_id


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header — please log in",
        )
    return authorization.split(" ", 1)[1].strip()


def get_current_recipient_id(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    """FastAPI dependency: resolves the bearer token to the recipient_id who
    is actually logged in.  Endpoints must use THIS value for authorization
    decisions, never a client-supplied recipient_id from body/path."""
    token = _extract_token(authorization)
    recipient_id = resolve_session(db, token)
    if not recipient_id:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid — please log in again",
        )
    return recipient_id


def get_current_recipient(
    recipient_id: str = Depends(get_current_recipient_id),
    db: Session = Depends(get_db),
):
    """The authenticated Recipient row (used for role checks). Revoked recipients are refused
    even if an old session token is still unexpired."""
    from app.models.models import Recipient

    r = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    if r is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid — please log in again")
    if r.status != "Active":
        raise HTTPException(status_code=403, detail=f"{recipient_id} is revoked")
    return r


def require_role(*allowed: str):
    """RBAC dependency factory (MUST-8). Returns the recipient_id like get_current_recipient_id,
    but 403s unless the account's ``access_role`` is in ``allowed``.

        officer -> protect / decrypt / download / render receipts / manage recipients
        auditor -> leak investigation + forensic reports
    Protector/decryptor and investigator are different accounts by construction."""

    def _dep(recipient=Depends(get_current_recipient)) -> str:
        if recipient.access_role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{recipient.access_role}' is not permitted here (requires: {', '.join(allowed)})",
            )
        return recipient.recipient_id

    return _dep


require_officer = require_role("officer")
require_auditor = require_role("auditor")


def get_token_for_logout(
    authorization: str | None = Header(default=None),
) -> str:
    return _extract_token(authorization)
