from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_recipient_id, require_officer
from app.core.database import get_db
from app.models.models import Recipient
from app.schemas.schemas import RecipientCreate
from app.services.recipient_service import register_recipient, revoke_recipient

router = APIRouter(prefix="/api/recipients", tags=["recipients"])


def _serialize(r: Recipient) -> dict:
    return {
        "recipient_id": r.recipient_id,
        "name": r.name,
        "organization": r.organization,
        "department": r.department,
        "role": r.role,
        "access_role": r.access_role,
        "email": r.email,
        "status": r.status,
        "key_status": r.key_status,
        "can_login": bool(r.password_hash),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        # Public keys ARE safe to expose (that's the point of asymmetric crypto) — never private keys.
        "public_kem_key": r.public_kem_key,
        "public_signing_key": r.public_signing_key,
    }


@router.get("")
def list_recipients(
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    recipients = db.query(Recipient).order_by(Recipient.created_at.desc()).all()
    return {"items": [_serialize(r) for r in recipients], "total": len(recipients)}


@router.get("/{recipient_id}")
def get_recipient(
    recipient_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    r = db.query(Recipient).filter(Recipient.recipient_id == recipient_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return _serialize(r)


@router.post("")
def create_recipient(
    payload: RecipientCreate,
    db: Session = Depends(get_db),
    _authed: str = Depends(require_officer),
):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if payload.access_role not in ("officer", "auditor"):
        raise HTTPException(status_code=400, detail="access_role must be 'officer' or 'auditor'")
    recipient, initial_password, bundle = register_recipient(
        db, name=payload.name, organization=payload.organization,
        department=payload.department, role=payload.role, email=payload.email,
        access_role=payload.access_role,
    )
    out = _serialize(recipient)
    # Shown exactly once, in this response only — the server never stores or re-displays the
    # plaintext password or the private key files. They are relayed to the recipient out-of-band
    # (the UI turns key_bundle into one-time file downloads for offline/USB storage).
    out["initial_password"] = initial_password
    out["key_bundle"] = None if bundle is None else {
        "sig_filename": bundle.sig_filename,
        "sig_private_file": bundle.sig_private_file,
        "kem_filename": bundle.kem_filename,
        "kem_private_file": bundle.kem_private_file,
        "sig_algorithm": bundle.sig_algorithm,
        "kem_algorithm": bundle.kem_algorithm,
        "notice": "One-time export. The server does not keep the signing key; store it offline.",
    }
    return out


@router.post("/{recipient_id}/revoke")
def revoke(
    recipient_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(require_officer),
):
    r = revoke_recipient(db, recipient_id)
    if not r:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return _serialize(r)
