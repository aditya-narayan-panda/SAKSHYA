from fastapi import APIRouter, Depends

from app.core.auth import get_current_recipient_id
from app.ledger.ledger_state import get_ledger

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

# Read-only. There is intentionally NO route that creates, updates or deletes ledger blocks:
# blocks are only ever appended by the decrypt/render services.


@router.get("/blocks")
def list_blocks(_authed: str = Depends(get_current_recipient_id)):
    """Blocks come from a FRESH read of every node's database (majority-consensus view), each
    with its real confirmations k/N — nothing is trusted from process memory."""
    ledger = get_ledger()
    snap = ledger.snapshot()
    v = snap["verify"]
    return {
        "blocks": list(reversed(snap["blocks"])),
        "height": v["height"],
        "nodes": v["confirmations"],
        "node_status": v["nodes"],
        "status": v["status"],
    }


@router.get("/verify")
def verify_chain(_authed: str = Depends(get_current_recipient_id)):
    return get_ledger().verify_chain()
