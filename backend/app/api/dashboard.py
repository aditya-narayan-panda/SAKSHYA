from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_recipient_id
from app.core.database import get_db
from app.models.models import Document, Recipient, DecryptionEvent
from app.crypto.pqc_provider import algorithm_info
from app.ledger.ledger_state import get_ledger

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    _authed: str = Depends(get_current_recipient_id),
):
    ledger = get_ledger()
    chain_status = ledger.verify_chain()

    recent_events = (
        db.query(DecryptionEvent)
        .order_by(DecryptionEvent.id.desc())
        .limit(8)
        .all()
    )

    return {
        "protected_documents": db.query(Document).count(),
        "authorized_recipients": db.query(Recipient).filter(Recipient.status == "Active").count(),
        "decryption_events": db.query(DecryptionEvent).count(),
        "ledger_status": chain_status["status"],
        "ledger_nodes": chain_status["confirmations"],
        "algorithms": algorithm_info(),
        "recent_events": [
            {
                "event_id": e.event_id,
                "document_id": e.document_id,
                "recipient_id": e.recipient_id,
                "status": e.status,
                "ledger_block_id": e.ledger_block_id,
            }
            for e in recent_events
        ],
    }
