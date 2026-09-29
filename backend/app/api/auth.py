from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password
from app.core.auth import (
    create_session,
    destroy_session,
    get_current_recipient_id,
    get_token_for_logout,
    purge_expired_sessions,
)
from app.models.models import Recipient
from app.schemas.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    recipient_id = payload.recipient_id.strip().upper()
    recipient = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    # Same generic error for "no such recipient" and "wrong password" —
    # distinguishing them would let an attacker enumerate valid recipient IDs.
    invalid = HTTPException(status_code=401, detail="Invalid recipient ID or password")
    if not recipient or not recipient.password_hash:
        raise invalid
    if not verify_password(payload.password, recipient.password_salt, recipient.password_hash):
        raise invalid
    if recipient.status != "Active":
        raise HTTPException(status_code=403, detail=f"{recipient.recipient_id} is revoked and cannot log in")

    purge_expired_sessions(db)
    token = create_session(db, recipient.recipient_id)
    return LoginResponse(
        token=token,
        recipient_id=recipient.recipient_id,
        name=recipient.name,
        organization=recipient.organization or "",
        role=recipient.role or "",
        access_role=recipient.access_role or "officer",
    )


@router.post("/logout")
def logout(token: str = Depends(get_token_for_logout), db: Session = Depends(get_db)):
    destroy_session(db, token)
    return {"status": "logged_out"}


@router.get("/me")
def me(recipient_id: str = Depends(get_current_recipient_id), db: Session = Depends(get_db)):
    recipient = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return {
        "recipient_id": recipient.recipient_id,
        "name": recipient.name,
        "organization": recipient.organization,
        "role": recipient.role,
        "access_role": recipient.access_role,
        "status": recipient.status,
    }
