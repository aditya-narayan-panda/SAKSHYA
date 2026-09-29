from __future__ import annotations

import base64
import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from app.core import config as _cfg
from app.crypto.pqc_provider import get_provider
from app.watermark.watermark_service import extract_watermark
from app.models.models import DecryptionEvent, Recipient, Investigation
from app.services.attribution import canonicalize_attribution_payload, payload_from_event, event_hash_of
from app.ledger.ledger_service import LedgerService


def generate_investigation_id() -> str:
    return f"INV-{uuid.uuid4().hex[:6].upper()}"


def investigate_leak(db: Session, ledger: LedgerService, filename: str, file_bytes: bytes,
                     investigator_id: str | None = None) -> dict:
    """MUST-7: IDENTIFIED only when EVERY link in the evidence chain independently checks out:

      1. signature:  provider.verify(recipient.public_key, canonical, signature) where
                     canonical is REBUILT from the stored event (incl. session_id and the
                     verbatim signed_timestamp);
      2. watermark:  sha256(watermark_id) == event.watermark_hash;
      3. ledger:     a FRESH verify_chain() (never a stored status), the block exists on a
                     >=2/3 majority of nodes, block.event_hash == sha256(canonical) and
                     block.document_hash == event.document_hash.

    Anything else with a matching watermark is SIGNATURE_OR_LEDGER_MISMATCH.
    """
    investigation_id = generate_investigation_id()
    doc_hash = hashlib.sha256(file_bytes).hexdigest()
    watermark_id = extract_watermark(file_bytes, filename)

    result = {
        "investigation_id": investigation_id,
        "uploaded_filename": filename,
        "document_hash": doc_hash,
        "watermark_id": watermark_id,
        "status": "UNATTRIBUTED",
        "matched_event_id": None,
        "matched_recipient_id": None,
        "matched_document_id": None,
        "signature_valid": None,
        "ledger_verified": None,
        "exact_copy_match": None,
        "ledger_status": None,
        "ledger_nodes": None,
        "checks": {},
        "warnings": [],
    }

    event = None
    if watermark_id:
        event = db.query(DecryptionEvent).filter(DecryptionEvent.watermark_id == watermark_id).first()

    if event is not None:
        recipient = db.query(Recipient).filter(Recipient.recipient_id == event.recipient_id).first()
        canonical = canonicalize_attribution_payload(payload_from_event(event))
        checks: dict[str, bool] = {}

        # 1. signature over the REBUILT payload
        sig_valid = False
        if recipient is not None:
            try:
                sig_valid = bool(get_provider().verify(
                    base64.b64decode(recipient.public_signing_key), canonical, base64.b64decode(event.signature)))
            except Exception:
                sig_valid = False
        checks["signature_valid"] = sig_valid

        # 2. watermark binding
        checks["watermark_hash_matches"] = (
            event.watermark_hash == hashlib.sha256(event.watermark_id.encode()).hexdigest())

        # 3. ledger — always fresh, cross-node
        chain = ledger.verify_chain()
        block = ledger.get_block_for_event(event.event_id)
        checks["ledger_block_on_majority"] = block is not None
        checks["ledger_event_hash_matches"] = bool(block) and block["event_hash"] == event_hash_of(canonical)
        checks["ledger_document_hash_matches"] = bool(block) and block["document_hash"] == event.document_hash
        if _cfg.LEDGER_STRICT:
            checks["ledger_all_nodes_verified"] = chain["status"] == "VERIFIED"
        else:
            checks["ledger_quorum_verified"] = bool(chain["quorum_ok"])
        ledger_ok = all(v for k, v in checks.items() if k.startswith("ledger_"))

        warnings: list[str] = []
        if chain["status"] != "VERIFIED":
            bad = [f"{nid} ({chain['details'].get(nid, '?')})" for nid, ok in chain["nodes"].items() if not ok]
            warnings.append(f"Ledger status {chain['status']}: divergent node(s): {', '.join(bad)}")

        identified = sig_valid and checks["watermark_hash_matches"] and ledger_ok
        result.update({
            "status": "IDENTIFIED" if identified else "SIGNATURE_OR_LEDGER_MISMATCH",
            "matched_event_id": event.event_id,
            "matched_recipient_id": event.recipient_id,
            "matched_document_id": event.document_id,
            "signature_valid": sig_valid,
            "ledger_verified": ledger_ok,
            # Informational, not a gate: a re-saved/edited leak still carries the watermark.
            "exact_copy_match": doc_hash == event.document_hash,
            "ledger_status": chain["status"],
            "ledger_nodes": chain["nodes"],
            "checks": checks,
            "warnings": warnings,
        })

    db.add(Investigation(
        investigation_id=investigation_id,
        uploaded_filename=filename,
        document_hash=doc_hash,
        watermark_id=watermark_id,
        matched_event_id=result["matched_event_id"],
        matched_recipient_id=result["matched_recipient_id"],
        matched_document_id=result["matched_document_id"],
        signature_valid=result["signature_valid"],
        ledger_verified=result["ledger_verified"],
        investigator_id=investigator_id,
        details_json=json.dumps({k: result[k] for k in
                                 ("checks", "warnings", "exact_copy_match", "ledger_status", "ledger_nodes")}),
        status=result["status"],
    ))
    db.commit()
    return result
