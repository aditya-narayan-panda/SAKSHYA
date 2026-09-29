from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.auth import require_auditor
from app.core.database import get_db
from app.services.investigation_service import investigate_leak
from app.ledger.ledger_state import get_ledger
from app.models.models import Investigation

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.get("")
def list_investigations(
    db: Session = Depends(get_db),
    _authed: str = Depends(require_auditor),
):
    items = db.query(Investigation).order_by(Investigation.id.desc()).all()
    return {
        "items": [
            {
                "investigation_id": i.investigation_id,
                "uploaded_filename": i.uploaded_filename,
                "status": i.status,
                "matched_event_id": i.matched_event_id,
                "matched_recipient_id": i.matched_recipient_id,
                "watermark_id": i.watermark_id,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
        "total": len(items),
    }


@router.post("")
async def create_investigation(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _authed: str = Depends(require_auditor),
):
    file_bytes = await file.read()
    result = investigate_leak(db, get_ledger(), file.filename, file_bytes, investigator_id=_authed)
    return result


@router.get("/{investigation_id}")
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(require_auditor),
):
    from fastapi import HTTPException

    i = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {
        "investigation_id": i.investigation_id,
        "uploaded_filename": i.uploaded_filename,
        "document_hash": i.document_hash,
        "watermark_id": i.watermark_id,
        "status": i.status,
        "matched_event_id": i.matched_event_id,
        "matched_recipient_id": i.matched_recipient_id,
        "matched_document_id": i.matched_document_id,
        "signature_valid": i.signature_valid,
        "ledger_verified": i.ledger_verified,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }
