"""End-to-end offline workflow (SIH demo requirement §29).

Officer-01 protects + decrypts (presenting THEIR signing key file); a separate auditor account
investigates the leaked copy and generates the report. No network, no external service.
"""

from tests.conftest import auth_headers, make_pdf_bytes, login_token, protect_pdf, decrypt


def test_full_offline_workflow_officer01(client, officer01_token, auditor_token):
    H = auth_headers(officer01_token)
    A = auth_headers(auditor_token)

    pdf = make_pdf_bytes()
    res = client.post("/api/protect", files={"document": ("Confidential_E2E_Report.pdf", pdf, "application/pdf")},
                      data={"recipient_ids": '["REC-OFFICER01"]'}, headers=H)
    assert res.status_code == 200, res.text
    document_id = res.json()["document_id"]
    assert document_id.startswith("DOC-")

    res = decrypt(client, officer01_token, document_id)
    assert res.status_code == 200, res.text
    dec = res.json()
    assert dec["recipient_id"] == "REC-OFFICER01" and dec["watermark_supported"] is True
    assert dec["visible_watermark_applied"] is False, "visible stamp is opt-in"
    assert dec["ledger_block"]["confirmations"] == "3/3"
    event_id = dec["event_id"]

    res = client.get(f"/api/events/{event_id}/download", headers=H)
    assert res.status_code == 200, res.text
    leaked_bytes = res.content
    assert leaked_bytes != pdf

    res = client.post(f"/api/events/{event_id}/render", json={"signing_private_key_b64": client.sig_keys["REC-OFFICER01"]}, headers=H)
    assert res.status_code == 200, res.text

    res = client.post("/api/investigations", files={"file": ("leaked_copy.pdf", leaked_bytes, "application/pdf")}, headers=A)
    assert res.status_code == 200, res.text
    inv = res.json()
    assert inv["watermark_id"] == dec["watermark_id"], "watermark must round-trip"
    assert inv["status"] == "IDENTIFIED", inv
    assert inv["matched_recipient_id"] == "REC-OFFICER01" and inv["matched_event_id"] == event_id
    assert inv["signature_valid"] is True and inv["ledger_verified"] is True
    assert all(inv["checks"].values()), inv["checks"]
    assert inv["exact_copy_match"] is True
    investigation_id = inv["investigation_id"]

    res = client.get("/api/ledger/verify", headers=H)
    assert res.status_code == 200 and res.json()["status"] == "VERIFIED", res.text

    res = client.post("/api/reports", params={"investigation_id": investigation_id}, headers=A)
    assert res.status_code == 200, res.text
    report_id = res.json()["report_id"]

    res = client.get(f"/api/reports/{report_id}/download?format=json", headers=A)
    payload = res.json()
    assert payload["attribution"]["recipient_id"] == "REC-OFFICER01"
    assert payload["investigation"]["status"] == "IDENTIFIED"
    assert payload["attribution"]["signature_valid"] is True and payload["attribution"]["ledger_verified"] is True

    res = client.get(f"/api/reports/{report_id}/download?format=pdf", headers=A)
    assert res.status_code == 200 and res.content[:4] == b"%PDF"


def test_cross_recipient_decrypt_is_forbidden(client, officer01_token):
    t2 = login_token(client, "REC-OFFICER02")
    document_id = protect_pdf(client, officer01_token, name="Only_Officer01.pdf")
    res = decrypt(client, t2, document_id, rid="REC-OFFICER02")
    assert res.status_code == 403, res.text
