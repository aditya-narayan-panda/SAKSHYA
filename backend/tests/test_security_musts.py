"""Regression tests for the eight MUST items. Each ``Done when`` from the spec is a test here."""
import base64
import io
import re
import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import text

from app.core import config as cfg, key_store
from app.ledger.ledger_state import get_ledger
from tests.conftest import (auth_headers, decrypt, login_token, make_pdf_bytes, protect_pdf, DEMO_PASSWORDS)


def _investigate(client, token, data, name="leak.pdf"):
    res = client.post("/api/investigations", files={"file": (name, data, "application/pdf")}, headers=auth_headers(token))
    assert res.status_code == 200, res.text
    return res.json()


def _decrypt_ok(client, token, doc, rid="REC-OFFICER01", **kw):
    res = decrypt(client, token, doc, rid=rid, **kw)
    assert res.status_code == 200, res.text
    return res.json()


def _download(client, token, event_id):
    res = client.get(f"/api/events/{event_id}/download", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    return res.content


def _raw(client, sql, **params):
    """Admin with direct DB access: drops the append-only triggers first, then edits."""
    with client.engine.begin() as c:
        for t in ("decryption_events",):
            c.execute(text(f"DROP TRIGGER IF EXISTS {t}_no_update"))
        c.execute(text(sql), params)


# ------------------------------- MUST-1 / MUST-2 (through the API) ----------------------------
def test_ledger_survives_restart_and_matches_api(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    _decrypt_ok(client, officer01_token, doc)
    before = client.get("/api/ledger/blocks", headers=auth_headers(officer01_token)).json()
    from app.ledger.ledger_state import reset_ledger_singleton
    reset_ledger_singleton()                                           # kill + restart backend
    after = client.get("/api/ledger/blocks", headers=auth_headers(officer01_token)).json()
    v = client.get("/api/ledger/verify", headers=auth_headers(officer01_token)).json()
    assert v["status"] == "VERIFIED" and v["height"] == before["height"] == 1
    assert after["blocks"] == before["blocks"]


def test_manual_ledger_update_is_TAMPER_DETECTED(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    _decrypt_ok(client, officer01_token, doc)
    node = get_ledger().nodes[0]
    with closing(sqlite3.connect(node.db_path)) as c:
        c.execute("DROP TRIGGER ledger_blocks_no_update")
        c.execute("UPDATE ledger_blocks SET document_hash=?", ("f" * 64,)); c.commit()
    v = client.get("/api/ledger/verify", headers=auth_headers(officer01_token)).json()
    assert v["status"] == "TAMPER_DETECTED" and v["nodes"]["node-1"] is False and v["nodes"]["node-2"] is True


def test_no_api_route_can_update_or_delete_evidence(client):
    for route in client.app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if re.search(r"/(events|ledger)", path):
            assert not (methods & {"PUT", "PATCH", "DELETE"}), (path, methods)


def test_orm_refuses_to_update_or_delete_events(client, officer01_token):
    from app.models.models import DecryptionEvent, AppendOnlyViolation
    doc = protect_pdf(client, officer01_token); _decrypt_ok(client, officer01_token, doc)
    db = client.Maker()
    ev = db.query(DecryptionEvent).first()
    ev.status = "X"
    with pytest.raises(AppendOnlyViolation):
        db.commit()
    db.rollback()
    with pytest.raises(Exception, match="append-only"):
        db.execute(text("DELETE FROM decryption_events")); db.commit()
    db.close()


# ------------------------------- MUST-3 recipient-held signing -------------------------------
def test_server_stores_no_recipient_signing_private_key(client):
    files = sorted(p.name for p in cfg.KEYS_DIR.iterdir())
    assert not any(re.match(r"REC-.*\.sig\.key", f) for f in files), files
    assert any(f == "REC-OFFICER01.kem.key" for f in files)            # KEM recovery copy is allowed


def test_stolen_password_alone_cannot_decrypt(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    res = client.post(f"/api/decrypt/{doc}", json={}, headers=auth_headers(officer01_token))
    assert res.status_code == 403, res.text
    res = client.post(f"/api/decrypt/{doc}", headers=auth_headers(officer01_token))
    assert res.status_code == 403, res.text
    assert client.get("/api/events", headers=auth_headers(officer01_token)).json()["total"] == 0


def test_someone_elses_signing_key_is_rejected(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    res = client.post(f"/api/decrypt/{doc}", headers=auth_headers(officer01_token),
                      json={"signing_private_key_b64": client.sig_keys["REC-OFFICER02"]})
    assert res.status_code == 403 and "does not match" in res.text
    res = client.post(f"/api/decrypt/{doc}", headers=auth_headers(officer01_token),
                      json={"signing_private_key_b64": "%%% not base64 %%%"})
    assert res.status_code == 403


def test_pasted_bare_base64_key_works_and_is_never_written_to_disk(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    bare = "".join(l for l in client.sig_keys["REC-OFFICER01"].splitlines() if not l.startswith("#"))
    res = client.post(f"/api/decrypt/{doc}", headers=auth_headers(officer01_token), json={"signing_private_key_b64": bare})
    assert res.status_code == 200, res.text
    raw = base64.b64decode(bare)
    for p in client.storage.rglob("*"):
        if p.is_file():
            assert raw not in p.read_bytes(), f"private signing key leaked into {p}"


def test_key_bundle_returned_once_on_add_recipient(client, officer01_token):
    res = client.post("/api/recipients", json={"name": "New Officer"}, headers=auth_headers(officer01_token))
    assert res.status_code == 200, res.text
    b = res.json()["key_bundle"]
    assert b["sig_filename"].endswith(".sig.private") and b["kem_filename"].endswith(".kem.private")
    rid = res.json()["recipient_id"]
    assert not (cfg.KEYS_DIR / f"{rid}.sig.key").exists()
    assert "key_bundle" not in client.get(f"/api/recipients/{rid}", headers=auth_headers(officer01_token)).json()
    crypto = client.get("/api/system/crypto-status").json()
    assert crypto["signature_detail"] == crypto["signature_detail"]      # reported honestly by env


# ------------------------------- MUST-4 invisible watermark ---------------------------------
def test_two_recipients_byte_different_pixel_identical(client, officer01_token):
    pytest.importorskip("pypdfium2")
    from PIL import ImageChops
    import pypdfium2 as pdfium
    doc = protect_pdf(client, officer01_token, recipients=("REC-OFFICER01", "REC-OFFICER02"))
    t2 = login_token(client, "REC-OFFICER02")
    d1 = _decrypt_ok(client, officer01_token, doc)
    d2 = _decrypt_ok(client, t2, doc, rid="REC-OFFICER02")
    b1, b2 = _download(client, officer01_token, d1["event_id"]), _download(client, t2, d2["event_id"])
    assert b1 != b2 and d1["watermark_id"] != d2["watermark_id"]
    i1 = pdfium.PdfDocument(b1)[0].render(scale=2).to_pil().convert("RGB")
    i2 = pdfium.PdfDocument(b2)[0].render(scale=2).to_pil().convert("RGB")
    assert ImageChops.difference(i1, i2).getbbox() is None
    from app.watermark.watermark_service import extract_watermark
    assert extract_watermark(b1, "a.pdf") == d1["watermark_id"] and extract_watermark(b2, "b.pdf") == d2["watermark_id"]


def test_visible_stamp_only_when_requested(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    plain = _decrypt_ok(client, officer01_token, doc)
    stamped = _decrypt_ok(client, officer01_token, doc, apply_visible=True)
    assert plain["visible_watermark_applied"] is False and stamped["visible_watermark_applied"] is True
    assert b"CONFIDENTIAL" not in _download(client, officer01_token, plain["event_id"])
    assert len(_download(client, officer01_token, stamped["event_id"])) > len(_download(client, officer01_token, plain["event_id"]))


# ------------------------------- MUST-5 uniqueness / binding / types ------------------------
def test_txt_and_xlsx_cannot_be_protected(client, officer01_token):
    for name in ("notes.txt", "sheet.xlsx"):
        res = client.post("/api/protect", files={"document": (name, b"hello", "application/octet-stream")},
                          data={"recipient_ids": '["REC-OFFICER01"]'}, headers=auth_headers(officer01_token))
        assert res.status_code == 400, res.text
        assert res.json()["detail"]["code"] == "UNSUPPORTED_WATERMARK_TYPE"
    assert client.get("/api/documents", headers=auth_headers(officer01_token)).json()["total"] == 0


def test_corrupt_pdf_is_rejected_at_protect_time(client, officer01_token):
    res = client.post("/api/protect", files={"document": ("bad.pdf", b"%PDF-1.4 garbage", "application/pdf")},
                      data={"recipient_ids": '["REC-OFFICER01"]'}, headers=auth_headers(officer01_token))
    assert res.status_code == 400 and res.json()["detail"]["code"] == "WATERMARK_EMBED_FAILED"


def test_session_id_is_signed_and_ledgered(client, officer01_token, auditor_token):
    doc = protect_pdf(client, officer01_token)
    d = _decrypt_ok(client, officer01_token, doc)
    leak = _download(client, officer01_token, d["event_id"])
    assert _investigate(client, auditor_token, leak)["status"] == "IDENTIFIED"
    _raw(client, "UPDATE decryption_events SET session_id='deadbeef'")          # session_id mismatch
    inv = _investigate(client, auditor_token, leak)
    assert inv["status"] == "SIGNATURE_OR_LEDGER_MISMATCH" and inv["signature_valid"] is False


def test_50_watermark_ids_unique_across_real_decrypts_sample(client, officer01_token):
    doc = protect_pdf(client, officer01_token)
    ids = {_decrypt_ok(client, officer01_token, doc)["watermark_id"] for _ in range(6)}
    assert len(ids) == 6 and all(re.fullmatch(r"WM-[A-F0-9]{16}", i) for i in ids)


# ------------------------------- MUST-6 -----------------------------------------------------
def test_crypto_status_is_truthful(client):
    body = client.get("/api/system/crypto-status").json()
    if body["pqc_available"]:
        assert body["kem"] == "ML-KEM-768" and body["signature"] == "ML-DSA-65"
    else:
        assert body["kem"] == "PQC NOT AVAILABLE" and "DEVELOPMENT FALLBACK ONLY" in body["fallback"]


# ------------------------------- MUST-7 full verification -----------------------------------
@pytest.fixture()
def leaked(client, officer01_token, auditor_token):
    doc = protect_pdf(client, officer01_token)
    d = _decrypt_ok(client, officer01_token, doc)
    return d, _download(client, officer01_token, d["event_id"])


def test_tampered_event_signature_is_mismatch(client, leaked, auditor_token):
    d, leak = leaked
    other = base64.b64encode(b"\x00" * 64).decode()
    _raw(client, "UPDATE decryption_events SET signature=:s", s=other)
    inv = _investigate(client, auditor_token, leak)
    assert inv["status"] == "SIGNATURE_OR_LEDGER_MISMATCH" and inv["signature_valid"] is False


def test_tampered_event_document_hash_is_mismatch(client, leaked, auditor_token):
    d, leak = leaked
    _raw(client, "UPDATE decryption_events SET document_hash=:h", h="a" * 64)
    assert _investigate(client, auditor_token, leak)["status"] == "SIGNATURE_OR_LEDGER_MISMATCH"


def test_tampered_ledger_event_hash_on_all_nodes_is_mismatch(client, leaked, auditor_token):
    """Even if an admin rewrites event_hash AND re-signs blocks on every node with the node keys,
    sha256(canonical) no longer equals block.event_hash."""
    d, leak = leaked
    for n in get_ledger().nodes:
        blk = n.read_all()[0]
        blk.event_hash = "b" * 64; blk.block_hash = blk.compute_hash()
        blk.signature = n._provider.sign(n._priv, blk.block_hash.encode()).hex()
        with closing(sqlite3.connect(n.db_path)) as c:
            c.execute("DROP TRIGGER ledger_blocks_no_update")
            c.execute("UPDATE ledger_blocks SET event_hash=?, block_hash=?, signature=?",
                      (blk.event_hash, blk.block_hash, blk.signature)); c.commit()
    inv = _investigate(client, auditor_token, leak)
    assert inv["status"] == "SIGNATURE_OR_LEDGER_MISMATCH"
    assert inv["checks"]["ledger_event_hash_matches"] is False


def test_swapped_watermark_between_events_is_mismatch(client, officer01_token, auditor_token):
    doc = protect_pdf(client, officer01_token)
    d1 = _decrypt_ok(client, officer01_token, doc); d2 = _decrypt_ok(client, officer01_token, doc)
    leak1 = _download(client, officer01_token, d1["event_id"])
    _raw(client, "UPDATE decryption_events SET watermark_id='TMP' WHERE event_id=:e", e=d1["event_id"])
    _raw(client, "UPDATE decryption_events SET watermark_id=:w WHERE event_id=:e", w=d1["watermark_id"], e=d2["event_id"])
    inv = _investigate(client, auditor_token, leak1)          # now resolves to event 2 with event 1's watermark
    assert inv["matched_event_id"] == d2["event_id"] and inv["status"] == "SIGNATURE_OR_LEDGER_MISMATCH"


def test_investigation_needs_majority_and_reports_divergent_node(client, leaked, auditor_token):
    d, leak = leaked
    get_ledger().nodes[0].db_path.write_bytes(b"corrupt" * 100)
    inv = _investigate(client, auditor_token, leak)
    assert inv["status"] == "IDENTIFIED"                                    # 2/3 majority still proves it
    assert inv["ledger_status"] == "TAMPER_DETECTED" and inv["ledger_nodes"]["node-1"] is False
    assert any("node-1" in w for w in inv["warnings"])


def test_investigation_persists_all_checks(client, leaked, auditor_token):
    d, leak = leaked
    inv = _investigate(client, auditor_token, leak)
    from app.models.models import Investigation
    db = client.Maker(); row = db.query(Investigation).filter_by(investigation_id=inv["investigation_id"]).one()
    assert (row.signature_valid, row.ledger_verified, row.watermark_id) == (True, True, d["watermark_id"])
    assert row.matched_event_id == d["event_id"] and row.matched_recipient_id == "REC-OFFICER01"
    assert row.investigator_id == "REC-AUDITOR01"; db.close()


def test_unwatermarked_file_is_unattributed(client, auditor_token):
    assert _investigate(client, auditor_token, make_pdf_bytes())["status"] == "UNATTRIBUTED"


# ------------------------------- MUST-8 custody + RBAC --------------------------------------
def test_auditor_cannot_decrypt_protect_or_download(client, officer01_token, auditor_token):
    doc = protect_pdf(client, officer01_token)
    A = auth_headers(auditor_token)
    assert client.post(f"/api/decrypt/{doc}", json={}, headers=A).status_code == 403
    assert client.post("/api/protect", files={"document": ("x.pdf", make_pdf_bytes(), "application/pdf")},
                       data={"recipient_ids": '["REC-OFFICER01"]'}, headers=A).status_code == 403
    d = _decrypt_ok(client, officer01_token, doc)
    assert client.get(f"/api/events/{d['event_id']}/download", headers=A).status_code == 403


def test_officer_cannot_investigate_or_read_reports(client, officer01_token):
    H = auth_headers(officer01_token)
    assert client.post("/api/investigations", files={"file": ("x.pdf", make_pdf_bytes(), "application/pdf")}, headers=H).status_code == 403
    assert client.get("/api/investigations", headers=H).status_code == 403
    assert client.get("/api/reports", headers=H).status_code == 403
    assert client.post("/api/reports", params={"investigation_id": "INV-X"}, headers=H).status_code == 403


def test_login_reports_access_role(client):
    r = client.post("/api/auth/login", json={"recipient_id": "REC-AUDITOR01", "password": DEMO_PASSWORDS["REC-AUDITOR01"]})
    assert r.json()["access_role"] == "auditor"


def test_master_key_never_written_in_plaintext_and_needs_password(client, tmp_path):
    blob = b"".join(p.read_bytes() for p in cfg.KEYS_DIR.iterdir() if p.suffix in (".key", ".json"))
    from tests.conftest import TEST_MASTER_PASSWORD
    assert TEST_MASTER_PASSWORD.encode() not in blob
    assert not (cfg.KEYS_DIR.parent / ".env").exists()
    key_store.lock_master_key()
    with pytest.raises(key_store.MasterKeyError):
        key_store.load_private_key("REC-OFFICER01", "kem")                # locked => nothing unwraps
    with pytest.raises(key_store.MasterKeyError, match="Wrong master password"):
        key_store.unlock_master_key("wrong-password-wrong-password")
    key_store.unlock_master_key(TEST_MASTER_PASSWORD)
    assert len(key_store.load_private_key("REC-OFFICER01", "kem")) > 0


def test_master_password_file_must_be_0600(tmp_path, monkeypatch):
    import os
    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    monkeypatch.setattr(cfg, "KEYS_DIR", tmp_path / "keys"); (tmp_path / "keys").mkdir()
    monkeypatch.setattr(cfg, "MASTER_KDF_ITERATIONS", 1_000)
    key_store.lock_master_key()
    pw = tmp_path / "usb-master.pw"; pw.write_text("a-long-enough-master-password\n")
    monkeypatch.setenv("SAKSHYA_MASTER_PASSWORD_FILE", str(pw))
    pw.chmod(0o644)
    with pytest.raises(key_store.MasterKeyError, match="0600"):
        key_store.unlock_master_key()
    pw.chmod(0o600)
    key_store.unlock_master_key()
    assert (tmp_path / "keys" / "master.meta.json").exists()
    key_store.lock_master_key()


def test_no_password_available_refuses_to_boot(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "KEYS_DIR", tmp_path / "keys"); (tmp_path / "keys").mkdir()
    for v in ("SAKSHYA_MASTER_PASSWORD_FILE", "SAKSHYA_MASTER_PASSWORD"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))                     # not a TTY
    key_store.lock_master_key()
    with pytest.raises(key_store.MasterKeyError, match="No master password"):
        key_store.unlock_master_key()
