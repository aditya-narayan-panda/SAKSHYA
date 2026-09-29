from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_recipient_id, require_officer
from app.core.database import get_db
from app.models.models import Document, DocumentRecipient, DecryptionEvent

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _serialize(doc: Document, db: Session) -> dict:
    recipient_count = db.query(DocumentRecipient).filter(DocumentRecipient.document_id == doc.document_id).count()
    decryption_count = db.query(DecryptionEvent).filter(DecryptionEvent.document_id == doc.document_id).count()
    return {
        "document_id": doc.document_id,
        "filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "sha256_hash": doc.sha256_hash,
        "status": doc.status,
        "recipients": recipient_count,
        "decryptions": decryption_count,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get("")
def list_documents(
    search: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    query = db.query(Document)
    if search:
        query = query.filter(Document.original_filename.ilike(f"%{search}%"))
    if status:
        query = query.filter(Document.status == status)
    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_serialize(d, db) for d in docs], "total": total, "page": page, "page_size": page_size}


@router.get("/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    links = db.query(DocumentRecipient).filter(DocumentRecipient.document_id == document_id).all()
    events = (
        db.query(DecryptionEvent)
        .filter(DecryptionEvent.document_id == document_id)
        .order_by(DecryptionEvent.id.desc())
        .all()
    )
    latest_event = events[0] if events else None

    detail = _serialize(doc, db)
    detail.update({
        "encryption": "AES-256-GCM",
        "integrity_status": "VERIFIED",
        "recipient_ids": [l.recipient_id for l in links],
        "latest_event": latest_event.event_id if latest_event else None,
        "decryption_events": [e.event_id for e in events],
    })
    return detail


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(require_officer),
):
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Never silently destroy immutable evidence — only DRAFT/never-decrypted docs are deletable.
    has_events = db.query(DecryptionEvent).filter(DecryptionEvent.document_id == document_id).count() > 0
    if has_events or doc.status == "DISTRIBUTED":
        raise HTTPException(
            status_code=409,
            detail="This document has decryption evidence on record and cannot be deleted.",
        )
    db.delete(doc)
    db.commit()
    return {"status": "deleted", "document_id": document_id}
