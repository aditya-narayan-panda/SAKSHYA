"""
Seed script — sets up a ready-to-demo SAKSHYA instance.

Run from the ``backend/`` directory::

    python scripts/seed.py

(or ``python -m app.seed`` — identical).  Safe to run repeatedly: existing
demo recipients are reused (missing passwords backfilled), existing documents
are never duplicated, and keys are never regenerated.

Deterministic demo identities (fixed IDs AND fixed passwords)::

    Officer-01  REC-OFFICER01  sakshya-officer01   (officer: protect / decrypt / view)
    Officer-02  REC-OFFICER02  sakshya-officer02   (officer)
    Officer-03  REC-OFFICER03  sakshya-officer03   (officer)
    Auditor-01  REC-AUDITOR01  sakshya-auditor01   (auditor: investigate / reports only)

The master password is required (SAKSHYA_MASTER_PASSWORD_FILE, SAKSHYA_MASTER_PASSWORD or an
interactive prompt) - the seed never invents one.

Recipient-held signing keys (MUST-3): the server does not keep them. For DEMO convenience the seed
writes each officer's exported ``<id>.sig.private`` / ``<id>.kem.private`` to
``backend/demo-recipient-keys/`` - that folder plays the role of the officers' offline USB sticks.
In a real deployment hand those files to the recipient and delete them from the server.

The seed documents under ``storage/documents/seed/`` are protected for
Officer-01 (skipped individually if a document with the same filename is
already protected — never duplicated).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal, init_db
from app.core.config import STORAGE_DIR
from app.core.key_store import unlock_master_key
from app.crypto.pqc_provider import enforce_pqc
from app.models.models import Document, Recipient
from app.services.recipient_service import register_recipient, set_recipient_password
from app.services.protection_service import protect_document

SEED_DOCS_DIR = STORAGE_DIR / "documents" / "seed"
DEMO_KEYS_DIR = Path(__file__).resolve().parent.parent / "demo-recipient-keys"

DEMO_RECIPIENTS = [
    {"recipient_id": "REC-OFFICER01", "name": "Officer-01", "organization": "Naval Operations",
     "department": "Operations", "role": "Operations Officer",
     "email": "officer01@example.mil", "password": "sakshya-officer01"},
    {"recipient_id": "REC-OFFICER02", "name": "Officer-02", "organization": "Intelligence",
     "department": "Intelligence", "role": "Intelligence Officer",
     "email": "officer02@example.mil", "password": "sakshya-officer02"},
    {"recipient_id": "REC-OFFICER03", "name": "Officer-03", "organization": "Logistics",
     "department": "Logistics", "role": "Logistics Officer",
     "email": "officer03@example.mil", "password": "sakshya-officer03"},
    {"recipient_id": "REC-AUDITOR01", "name": "Auditor-01", "organization": "Internal Audit",
     "department": "Forensics", "role": "Forensic Auditor", "access_role": "auditor",
     "email": "auditor01@example.mil", "password": "sakshya-auditor01"},
]


def _export_keys(bundle) -> None:
    DEMO_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in ((bundle.sig_filename, bundle.sig_private_file), (bundle.kem_filename, bundle.kem_private_file)):
        path = DEMO_KEYS_DIR / name
        path.write_text(text)
        try:
            path.chmod(0o600)
        except OSError:
            pass


def run():
    enforce_pqc()
    unlock_master_key()
    init_db()
    db = SessionLocal()
    try:
        recipients: list[Recipient] = []
        for spec in DEMO_RECIPIENTS:
            existing = db.query(Recipient).filter(
                Recipient.recipient_id == spec["recipient_id"]
            ).first()
            if existing:
                # Idempotent: reuse, backfill login if an older DB lacks it.
                if not existing.password_hash:
                    set_recipient_password(db, existing, spec["password"])
                    print(f"Set login password for existing {existing.recipient_id} ({existing.name})")
                else:
                    print(f"Recipient {existing.recipient_id} ({existing.name}) already exists — skipping.")
                recipients.append(existing)
                continue
            reg = register_recipient(
                db, name=spec["name"], organization=spec["organization"],
                department=spec["department"], role=spec["role"], email=spec["email"],
                recipient_id=spec["recipient_id"], access_role=spec.get("access_role", "officer"),
            )
            r = reg.recipient
            if reg.key_bundle is not None:
                _export_keys(reg.key_bundle)
                print(f"  exported one-time key files for {r.recipient_id} -> {DEMO_KEYS_DIR}")
            # Overwrite the random one-time password with the fixed demo
            # password so the documented credentials always work.
            set_recipient_password(db, r, spec["password"])
            recipients.append(r)
            print(f"Created recipient {r.recipient_id} ({r.name}) — login password: {spec['password']}")

        if not SEED_DOCS_DIR.exists():
            print(f"No seed documents found at {SEED_DOCS_DIR} — skipping document seeding.")
        else:
            officer_01 = next((r for r in recipients if r.name == "Officer-01"), recipients[0])
            for pdf_path in sorted(SEED_DOCS_DIR.glob("*.pdf")):
                already = db.query(Document).filter(
                    Document.original_filename == pdf_path.name
                ).first()
                if already:
                    print(f"Document {pdf_path.name} already protected as {already.document_id} — skipping.")
                    continue
                file_bytes = pdf_path.read_bytes()
                result = protect_document(db, pdf_path.name, file_bytes, [officer_01.recipient_id])
                print(f"Protected {pdf_path.name} -> {result['document_id']} (assigned to {officer_01.recipient_id})")

        print("\nSeed complete (idempotent — safe to re-run). Demo credentials:")
        for spec in DEMO_RECIPIENTS:
            print(f"  {spec['name']}  {spec['recipient_id']}  password: {spec['password']}")
        print("\n  1. Log in as REC-OFFICER01 (Officer-01)")
        print("  2. Decrypt a seeded document - load demo-recipient-keys/REC-OFFICER01.sig.private when asked")
        print("  3. Download & view the decrypted file (signed rendering receipt)")
        print("  4. Log out, log in as REC-AUDITOR01 and upload that file to Leak Investigation")
        print("  5. Generate the forensic report (auditor only)")
    finally:
        db.close()


if __name__ == "__main__":
    run()
