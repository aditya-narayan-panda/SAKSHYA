from __future__ import annotations

import json
import uuid
import datetime as dt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.config import REPORTS_DIR
from app.models.models import Investigation, DecryptionEvent, Recipient, Report


def generate_report_id() -> str:
    return f"RPT-{uuid.uuid4().hex[:6].upper()}"


def _draw_kv(c: canvas.Canvas, x: int, y: int, label: str, value: str) -> int:
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, f"{label}:")
    c.setFont("Helvetica", 9)
    c.drawString(x + 150, y, str(value)[:80])
    return y - 16


def build_forensic_report(db: Session, investigation_id: str) -> dict:
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise ValueError(f"Investigation {investigation_id} not found")

    event = None
    recipient = None
    if investigation.matched_event_id:
        event = db.query(DecryptionEvent).filter(DecryptionEvent.event_id == investigation.matched_event_id).first()
    if investigation.matched_recipient_id:
        recipient = db.query(Recipient).filter(Recipient.recipient_id == investigation.matched_recipient_id).first()

    details = {}
    try:
        details = json.loads(investigation.details_json) if investigation.details_json else {}
    except Exception:
        details = {}

    report_id = generate_report_id()
    generated_at = dt.datetime.now(dt.timezone.utc)

    json_payload = {
        "report_id": report_id,
        "report_type": "FORENSIC_ATTRIBUTION",
        "generated_at": generated_at.isoformat(),
        "investigation": {
            "investigation_id": investigation.investigation_id,
            "uploaded_filename": investigation.uploaded_filename,
            "document_hash": investigation.document_hash,
            "watermark_id": investigation.watermark_id,
            "status": investigation.status,
        },
        "attribution": {
            "event_id": investigation.matched_event_id,
            "document_id": investigation.matched_document_id,
            "recipient_id": investigation.matched_recipient_id,
            "recipient_name": recipient.name if recipient else None,
            "recipient_organization": recipient.organization if recipient else None,
            "signature_valid": investigation.signature_valid,
            "ledger_verified": investigation.ledger_verified,
            "checks": details.get("checks", {}),
            "exact_copy_match": details.get("exact_copy_match"),
            "ledger_status": details.get("ledger_status"),
            "ledger_nodes": details.get("ledger_nodes"),
            "warnings": details.get("warnings", []),
        },
        "cryptography": {
            "signature_algorithm": event.signature_algorithm if event else None,
            "hash_algorithm": "SHA-256",
        },
        "conclusion": (
            "ATTRIBUTION CONFIRMED — the decrypted copy that was leaked can be cryptographically "
            f"traced to recipient {investigation.matched_recipient_id}, whose digital signature and "
            "ledger record both verified successfully."
            if investigation.status == "IDENTIFIED"
            else "ATTRIBUTION NOT CONFIRMED — no verified decryption event matches this document's "
                 "forensic watermark, or signature/ledger verification failed."
        ),
    }

    if json_payload["attribution"]["warnings"]:
        json_payload["conclusion"] += " WARNING: " + "; ".join(json_payload["attribution"]["warnings"])

    json_path = REPORTS_DIR / f"{report_id}.json"
    json_path.write_text(json.dumps(json_payload, indent=2))

    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    _render_pdf(pdf_path, json_payload)

    report = Report(
        report_id=report_id,
        report_type="FORENSIC_ATTRIBUTION",
        document_id=investigation.matched_document_id,
        event_id=investigation.matched_event_id,
        investigation_id=investigation.investigation_id,
        pdf_path=str(pdf_path),
        json_path=str(json_path),
        status="GENERATED",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {"report_id": report_id, "pdf_path": str(pdf_path), "json_path": str(json_path), "status": "GENERATED"}


def _render_pdf(path, payload: dict) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    margin = 20 * mm

    c.setFillColor(colors.HexColor("#0b1f3a"))
    c.rect(0, height - 28 * mm, width, 28 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, height - 15 * mm, "SAKSHYA")
    c.setFont("Helvetica", 11)
    c.drawString(margin, height - 22 * mm, "Forensic Attribution Report")

    y = height - 38 * mm
    c.setFillColor(colors.black)

    inv = payload["investigation"]
    attr = payload["attribution"]
    crypto = payload["cryptography"]

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Investigation Details")
    y -= 18
    y = _draw_kv(c, margin, y, "Report ID", payload["report_id"])
    y = _draw_kv(c, margin, y, "Generated At", payload["generated_at"])
    y = _draw_kv(c, margin, y, "Investigation ID", inv["investigation_id"])
    y = _draw_kv(c, margin, y, "Uploaded File", inv["uploaded_filename"])
    y = _draw_kv(c, margin, y, "Document Hash (SHA-256)", inv["document_hash"])
    y = _draw_kv(c, margin, y, "Watermark ID", inv["watermark_id"] or "NOT FOUND")
    y = _draw_kv(c, margin, y, "Status", inv["status"])

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Attribution")
    y -= 18
    y = _draw_kv(c, margin, y, "Decryption Event", attr["event_id"] or "—")
    y = _draw_kv(c, margin, y, "Document ID", attr["document_id"] or "—")
    y = _draw_kv(c, margin, y, "Recipient ID", attr["recipient_id"] or "—")
    y = _draw_kv(c, margin, y, "Recipient Name", attr["recipient_name"] or "—")
    y = _draw_kv(c, margin, y, "Organization", attr["recipient_organization"] or "—")
    y = _draw_kv(c, margin, y, "Signature Valid", str(attr["signature_valid"]))
    y = _draw_kv(c, margin, y, "Ledger Verified", str(attr["ledger_verified"]))

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Cryptographic Algorithms")
    y -= 18
    y = _draw_kv(c, margin, y, "Signature Algorithm", crypto["signature_algorithm"] or "—")
    y = _draw_kv(c, margin, y, "Hash Algorithm", crypto["hash_algorithm"])

    y -= 16
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Conclusion")
    y -= 16
    c.setFont("Helvetica", 9)
    text_obj = c.beginText(margin, y)
    text_obj.setLeading(13)
    for line in _wrap_text(payload["conclusion"], 95):
        text_obj.textLine(line)
    c.drawText(text_obj)

    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(margin, 12 * mm, "Generated entirely locally by SAKSHYA — no external service was contacted.")
    c.save()


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for w in words:
        if len(current) + len(w) + 1 <= width:
            current = f"{current} {w}".strip()
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines
