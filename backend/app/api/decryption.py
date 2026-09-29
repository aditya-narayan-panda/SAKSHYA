from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_recipient_id, require_officer
from app.schemas.schemas import DecryptRequest, RenderRequest
from app.services.decryption_service import decrypt_document, DecryptionError, SigningKeyError
from app.services.render_service import record_render, list_renders, RenderError
from app.ledger.ledger_service import LedgerError
from app.ledger.ledger_state import get_ledger
from app.models.models import DecryptionEvent

router = APIRouter(prefix="/api", tags=["decryption"])


@router.post("/decrypt/{document_id}")
def decrypt(
    document_id: str,
    body: DecryptRequest | None = None,
    recipient_id: str = Depends(require_officer),
    db: Session = Depends(get_db),
):
    # recipient_id comes ONLY from the authenticated session. The signing key comes from the
    # RECIPIENT (body.signing_private_key_b64): the server holds no key that can sign for them,
    # so a stolen password alone yields 403, not a forged DecryptionEvent.
    body = body or DecryptRequest()
    try:
        return decrypt_document(
            db, get_ledger(), document_id, recipient_id,
            signing_private_key_b64=body.signing_private_key_b64,
            apply_visible=body.apply_visible,
        )
    except SigningKeyError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except DecryptionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LedgerError as e:
        raise HTTPException(status_code=503, detail=f"Ledger unavailable, nothing was released: {e}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Key material missing: {e}")


@router.get("/events")
def list_events(
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    events = db.query(DecryptionEvent).order_by(DecryptionEvent.id.desc()).all()
    return {
        "items": [
            {
                "event_id": e.event_id,
                "document_id": e.document_id,
                "recipient_id": e.recipient_id,
                "timestamp": e.signed_timestamp,
                "watermark_id": e.watermark_id,
                "status": e.status,
                "ledger_block_id": e.ledger_block_id,
                "signature_algorithm": e.signature_algorithm,
            }
            for e in events
        ],
        "total": len(events),
    }


@router.get("/events/{event_id}/download")
def download_decrypted(
    event_id: str,
    recipient_id: str = Depends(require_officer),
    db: Session = Depends(get_db),
):
    from app.core.config import DECRYPTED_DIR

    event = db.query(DecryptionEvent).filter(DecryptionEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.recipient_id != recipient_id:
        raise HTTPException(status_code=403, detail="This decrypted file was not issued to the logged-in recipient")
    matches = list(DECRYPTED_DIR.glob(f"{event_id}_*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Decrypted file no longer on disk")
    return FileResponse(matches[0], filename=matches[0].name)


@router.post("/events/{event_id}/render")
def render_receipt(
    event_id: str,
    body: RenderRequest | None = None,
    recipient_id: str = Depends(require_officer),
    db: Session = Depends(get_db),
):
    """Called by the recipient's client each time it actually renders/opens the decrypted file.
    Signed with the recipient-supplied key, like the decryption itself."""
    body = body or RenderRequest()
    try:
        return record_render(db, get_ledger(), event_id, recipient_id,
                             signing_private_key_b64=body.signing_private_key_b64)
    except RenderError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LedgerError as e:
        raise HTTPException(status_code=503, detail=f"Ledger unavailable, receipt not recorded: {e}")


@router.get("/events/{event_id}/renders")
def render_receipts(
    event_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    return {"items": list_renders(db, event_id)}
