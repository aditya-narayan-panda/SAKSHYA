"""Shared hermetic fixtures for the HTTP-level test suite.

Every test gets an isolated temp SQLite DB, isolated storage dirs (keys, ledger nodes,
encrypted, decrypted ...), a test master key (no prompt, no .env), fresh persistent
ledger node files, and demo identities:

    REC-OFFICER01/02/03  (access_role officer)  - each with its own recipient-held signing key
    REC-AUDITOR01        (access_role auditor)  - password sakshya-auditor01

``client.sig_keys[rid]`` holds each officer's exported ``*.sig.private`` file contents: the
test plays the role of the recipient's USB stick. Nothing touches the real ``storage/``.
"""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crypto import pqc_provider

# Developer machines whose `cryptography` predates ML-KEM/ML-DSA may still run the suite by
# opting in to the (dev-only, never production) classical stand-in. With cryptography>=48
# this is a no-op and the tests exercise real ML-KEM-768 / ML-DSA-65.
if not pqc_provider.PQC_ACTIVE:
    os.environ.setdefault("SAKSHYA_ALLOW_FALLBACK", "true")

from app import create_app  # noqa: E402
from app.core import config as cfg  # noqa: E402
from app.core import database, key_store  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.ledger import ledger_state  # noqa: E402
from app.models.models import Base  # noqa: E402
from app.services.recipient_service import register_recipient, set_recipient_password  # noqa: E402

_DIR_ATTRS = ["DOCUMENTS_DIR", "ENCRYPTED_DIR", "DECRYPTED_DIR", "WATERMARKS_DIR",
              "EVIDENCE_DIR", "REPORTS_DIR", "KEYS_DIR", "TEMP_DIR", "LEDGER_DIR"]

_FROM_IMPORT_MODULES = [
    "app.services.protection_service",
    "app.services.decryption_service",
    "app.services.report_service",
    "app.api.decryption",
]

DEMO_PASSWORDS = {
    "REC-OFFICER01": "sakshya-officer01",
    "REC-OFFICER02": "sakshya-officer02",
    "REC-OFFICER03": "sakshya-officer03",
    "REC-AUDITOR01": "sakshya-auditor01",
}
TEST_MASTER_PASSWORD = "correct-horse-battery-staple-test"


class _Client(TestClient):
    sig_keys: dict
    engine: object
    storage: object
    Maker: object


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import importlib

    storage = tmp_path / "storage"
    for name in _DIR_ATTRS:
        d = storage / name.lower().replace("_dir", "")
        d.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(cfg, name, d)
    for mod_name in _FROM_IMPORT_MODULES:
        mod = importlib.import_module(mod_name)
        for name in _DIR_ATTRS:
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, getattr(cfg, name))

    monkeypatch.delenv("SAKSHYA_MASTER_KEY", raising=False)
    monkeypatch.delenv("SAKSHYA_MASTER_PASSWORD_FILE", raising=False)
    monkeypatch.setattr(cfg, "MASTER_KDF_ITERATIONS", 1_000)   # fast; production uses 600k
    key_store.lock_master_key()
    key_store.unlock_master_key(TEST_MASTER_PASSWORD)

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)     # app startup's init_db() hits THIS db
    database.init_db()
    Maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    sig_keys: dict[str, str] = {}
    setup = Maker()
    for i in ("01", "02", "03"):
        rid = f"REC-OFFICER{i}"
        reg = register_recipient(setup, name=f"Officer-{i}", organization="Test Org",
                                 department="Test Dept", role="Test Officer",
                                 email=f"officer{i}@example.mil", recipient_id=rid)
        set_recipient_password(setup, reg.recipient, DEMO_PASSWORDS[rid])
        sig_keys[rid] = reg.key_bundle.sig_private_file
    reg = register_recipient(setup, name="Auditor-01", organization="Test Org", department="Audit",
                             role="Forensic Auditor", email="auditor01@example.mil",
                             recipient_id="REC-AUDITOR01", access_role="auditor")
    set_recipient_password(setup, reg.recipient, DEMO_PASSWORDS["REC-AUDITOR01"])
    setup.close()

    ledger_state.reset_ledger_singleton()      # fresh ledger objects; node files are per-test tmp
    application = create_app()

    def _override_db():
        db = Maker()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _override_db

    with TestClient(application, raise_server_exceptions=False) as tc:
        tc.sig_keys = sig_keys
        tc.engine = engine
        tc.storage = storage
        tc.Maker = Maker
        yield tc

    application.dependency_overrides.clear()
    ledger_state.reset_ledger_singleton()
    key_store.lock_master_key()


def _login(client, rid):
    res = client.post("/api/auth/login", json={"recipient_id": rid, "password": DEMO_PASSWORDS[rid]})
    assert res.status_code == 200, res.text
    return res.json()["token"]


@pytest.fixture()
def officer01_token(client):
    return _login(client, "REC-OFFICER01")


@pytest.fixture()
def auditor_token(client):
    return _login(client, "REC-AUDITOR01")


def login_token(client, rid):
    return _login(client, rid)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_pdf_bytes(pages: int = 1, text: str = "Confidential body text") -> bytes:
    """Small real PDF (with visible body text) built locally with reportlab."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    for i in range(pages):
        c.drawString(72, 700, f"{text} - page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def protect_pdf(client, token, recipients=("REC-OFFICER01",), pages=1, name="Doc.pdf"):
    res = client.post("/api/protect",
                      files={"document": (name, make_pdf_bytes(pages), "application/pdf")},
                      data={"recipient_ids": str(list(recipients)).replace("'", '"')},
                      headers=auth_headers(token))
    assert res.status_code == 200, res.text
    return res.json()["document_id"]


def decrypt(client, token, document_id, rid="REC-OFFICER01", **extra):
    body = {"signing_private_key_b64": client.sig_keys[rid], **extra}
    return client.post(f"/api/decrypt/{document_id}", json=body, headers=auth_headers(token))
