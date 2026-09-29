# SAKSHYA — Cryptographic Document Attribution & Provenance System

**SIH 2026 · Problem Statement SIH26237 · offline/air-gapped demonstration.**

Log in as an authorized officer, decrypt a protected document with **your own
signing key file**, and receive a visually identical copy carrying an invisible
per-recipient forensic watermark — post-quantum signed by the recipient and
committed to a persistent 3-node ledger. A separate **auditor** account then
traces a leaked copy back to the recipient, re-verifying signature, watermark and
ledger from scratch.

```
              ┌───────────────────────┐
              │       Browser         │
              │   React/Vite Frontend │
              └───────────┬───────────┘
                          │
                     localhost
                          │
              ┌───────────▼───────────┐
              │      FastAPI Backend   │
              │                       │
              │ Local Authentication  │
              │ Local SQLite          │
              │ ML-KEM-768            │
              │ ML-DSA-65             │
              │ Watermark Engine      │
              │ Investigation Engine  │
              │ Local Ledger           │
              │ Report Generator      │
              └───────────┬───────────┘
                          │
                ┌─────────▼─────────┐
                │ Local Files/DB    │
                │ No Cloud          │
                │ No Public Chain   │
                └───────────────────┘
```

**INSTALLATION/BUILD: internet required once. RUNTIME: no internet required.**

## Layout

    frontend/          React/Vite only (src/api.js = single API config)
    backend/           FastAPI/Python only (app.py factory + main.py entry)
      app.py           create_app() + shared `app`
      main.py          `python main.py` / `uvicorn app:app` / `uvicorn main:app`
      app/             routers, services, crypto, watermark, ledger, models
      scripts/seed.py  idempotent deterministic seeding
      tests/           pytest suite incl. offline login + end-to-end test
      data/            optional alternate data dir (default: ../storage)
      requirements.txt pinned (cryptography==50.0.0 → real ML-KEM/ML-DSA)
      .env.example     backend-only config (no secrets in frontend)
    docker/            backend.Dockerfile, frontend.Dockerfile, nginx.conf
    docker-compose.yml Browser → frontend:8080 → backend:8100 → SQLite/files
    storage/           canonical local data dir (SQLite + keys + artifacts)

## Quick start (local, Windows PowerShell)

The backend **needs the master password at boot** (see "Air-gapped key ceremony" below) and
**refuses to start without real ML-KEM-768 / ML-DSA-65** (`cryptography==50.0.0`).

```powershell
# Backend
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\seed.py     # first run: asks for a NEW master password (twice); creates keys + demo data
python main.py             # asks for the master password; http://127.0.0.1:8100
```

Non-interactive: put the password in a file only you can read and point at it, e.g.
`$env:SAKSHYA_MASTER_PASSWORD_FILE="E:\sakshya-master.pw"` (USB stick). On Linux/macOS the file must be `chmod 600`.

```powershell
# Frontend (second terminal)
cd frontend
npm install
npm run dev             # http://localhost:5173
```

Bash equivalents: `python3 -m venv .venv && source .venv/bin/activate`,
`pip install -r requirements.txt`, `python scripts/seed.py`, `python main.py`;
`npm install`, `npm run dev`. Uvicorn alternative (from `backend/`):
`uvicorn app:app --host 127.0.0.1 --port 8100` (or `uvicorn main:app …`).

## Docker

```powershell
docker compose build
docker compose up
# first run only, in another terminal (needs ./secrets/master_password.txt, chmod 600):
docker compose exec backend python -m app.seed
# stop:
docker compose down
```

Then open Frontend http://localhost:8080 and API docs
http://localhost:8100/docs.

## Demo credentials (deterministic — same on every machine, every run)

| Officer | Recipient ID | Password |
|---|---|---|
| Officer-01 | `REC-OFFICER01` | `sakshya-officer01` |
| Officer-02 | `REC-OFFICER02` | `sakshya-officer02` |
| Officer-03 | `REC-OFFICER03` | `sakshya-officer03` |
| Auditor-01 | `REC-AUDITOR01` | `sakshya-auditor01` |

Officers protect / decrypt / view; **auditors** run Leak Investigation and Reports and
cannot decrypt. Each officer's **signing key file** is exported by the seed to
`backend/demo-recipient-keys/<ID>.sig.private` (stand-in for their offline USB) — you load it in
the Decrypt panel. Recipients created later via **Add Recipient** get a random ID, a one-time
password, and one-time downloads of `*.sig.private` + `*.kem.private`.

## Judge demo path (one machine, internet disconnected)

1. **LOGIN** as REC-OFFICER01 (`sakshya-officer01`)
2. **PROTECT** a PDF/DOCX for Officer-01 (TXT/XLSX are refused: `UNSUPPORTED_WATERMARK_TYPE`)
3. **DECRYPT** — load `REC-OFFICER01.sig.private`. Without it (stolen password) → 403. Officer-02 → 403.
4. **WATERMARK** — invisible, per-recipient, on every page; the copy is pixel-identical (visible stamp is opt-in)
5. **LEAK** — download the decrypted file
6. Log out, **LOGIN as REC-AUDITOR01**, **INVESTIGATE** → `IDENTIFIED` (signature, watermark, ledger event/doc hashes all re-verified)
7. **VERIFY LEDGER** — 3/3 nodes; corrupt one node file → `TAMPER_DETECTED`, other two still verify, demo continues
8. **RESTART** the backend → same ledger height, still `VERIFIED`
9. **GENERATE REPORT** — local PDF + JSON

Settings → **Security Status (live)** shows the factual posture:
Authentication LOCAL · Database SQLITE · Network OFFLINE/LOCAL ·
KEM ML-KEM-768 · Signature ML-DSA-65 · Ledger LOCAL VERIFIED ·
External Cloud Dependency NONE.

## Tests

```powershell
cd backend
pip install -r requirements-dev.txt
pytest tests\ -v
```

Covers: password hashing, DB session lifecycle, HTTP login (200/401/401),
protected-without-token (401/403), protected-with-token, `/auth/me`,
network-disabled login, health, crypto-status honesty, KEM/signature
round-trips, AES-GCM tamper rejection, ledger integrity + tamper detection,
watermark embed/extract, and the full 13-step offline end-to-end workflow.

## Offline guarantee

* Runtime makes **zero** external requests: local auth (bcrypt, SQLite
  sessions), local SQLite, local `cryptography` (ML-KEM-768/ML-DSA-65),
  local watermarking (pypdf), local hash-chain ledger, local reportlab PDFs.
* No Firebase/Supabase/Auth0/Clerk/OAuth/AWS/Azure/KMS/cloud DB/blockchain/
  AI API anywhere in code, deps, or UI (audited: only localhost URLs and one
  docstring reference URL; frontend has no CDN/fonts/analytics).
* PQC honesty: `/api/system/crypto-status` reports `PQC NOT AVAILABLE` +
  `DEVELOPMENT FALLBACK ONLY` instead of fake ML-KEM/ML-DSA badges when
  `cryptography<48` is installed. This repo pins `cryptography==50.0.0`
  (verified real ML-KEM-768 + ML-DSA-65).

## Security architecture (what changed and what it does / does not prove)

| # | Property | Implementation |
|---|---|---|
| 1 | Persistent, append-only ledger | Every block is written to SQLite (`ledger_blocks`) with CHECK/UNIQUE constraints and `BEFORE UPDATE/DELETE` triggers that abort. `verify_chain()` re-reads from disk, recomputes hashes and verifies signatures with **persistent** node keys (`storage/keys/ledger-node-N.sig.key`). No `tamper_block()`, no update/delete route. `DecryptionEvent`/`RenderEvent` are append-only in ORM + DB. |
| 2 | 3-node ledger | 3 independent stores (`storage/ledger/ledger-node{1,2,3}.db`), each signing with its own key. `append_event` = prepare on every node → compare block hashes → commit; `3/3` only if all three independently agree. `verify_chain()` cross-compares `block_hash` per height (`TAMPER_DETECTED`, `nodes:{node-1:false}`); lookups need a ≥2/3 majority. |
| 3 | Recipient-held signing | ML-DSA-65 signing private key is exported once at registration and **never stored** server-side (KEM key keeps a wrapped recovery copy). Decrypt (`POST /api/decrypt/{id}` body `signing_private_key_b64`) needs the key each session; it is checked against the registered public key, used in memory, never written. |
| 4 | Invisible watermark | PDF text render mode 3 (`3 Tr`) 1 pt run at (2,2) on **every page** + `/SakshyaWatermarkID` metadata. Visible stamp is opt-in (`apply_visible`, default false). |
| 5 | Uniqueness / binding | `WM-` + 64-bit ID; `session_id` is signed and ledgered; visible micro-text carries `SAKSHYA::`; only `.pdf` (full) and `.docx` (metadata-only) are accepted. |
| 6 | PQC-only | Backend refuses to boot without ML-KEM-768/ML-DSA-65 (self-test at startup). Classical fallback exists only behind `SAKSHYA_ALLOW_FALLBACK=true`, never in production. Dockerfile pins and asserts `cryptography==50.0.0` at build time. |
| 7 | Full verification | Investigation rebuilds the canonical payload, verifies the signature, checks `sha256(watermark_id)`, runs a fresh `verify_chain()`, and requires `block.event_hash == sha256(canonical)` and `block.document_hash == event.document_hash` on a majority of nodes. Otherwise `SIGNATURE_OR_LEDGER_MISMATCH`. |
| 8 | Custody + RBAC | Wrapping key is derived (PBKDF2-SHA256, 600k) from an operator password; nothing secret is written to `.env`/`storage/`. Roles: `officer` (protect/decrypt/download/recipients) vs `auditor` (investigate/reports). |

### Air-gapped key ceremony

1. On the offline host, create a long random master password (≥12 chars; use a passphrase of 5+ words). Write it to a file on removable media: `umask 077; printf '%s' '…' > /media/usb/sakshya-master.pw` (`chmod 600`).
2. Start with `SAKSHYA_MASTER_PASSWORD_FILE=/media/usb/sakshya-master.pw` (or type it at the prompt). First boot writes only `storage/keys/master.meta.json` (public KDF salt + check value).
3. Remove the USB stick after boot. The derived key lives in process memory only; without the password, `storage/keys/*.key` cannot be unwrapped.
4. Store a sealed copy of the password with a second custodian. **Lost password = keys unrecoverable.** There is no reset.
5. Hand each officer their `*.sig.private` (USB) at registration. The server cannot recreate it.

### Ledger nodes

Default: three SQLite files on one host — three *replicas*. For "no single administrator can alter history" in the strict sense, run each node file under a different custodian: point separate processes/hosts at different `SAKSHYA_LEDGER_DIR`s (the interface is unchanged). `SAKSHYA_LEDGER_STRICT=1` makes investigations require all nodes healthy instead of a 2/3 majority.

## Known limitations (disclosed, not hidden)

* **Upgrading from the previous version is not supported in place**: the old `storage/` was wrapped under an auto-generated key and holds server-side signing keys and NULL-watermark rows. Start from a clean `storage/` and re-seed (this package ships it clean).
* **Invisible ≠ un-extractable.** Render-mode-3 text draws no pixels but PDF text extractors still return it; that is why the marker is an opaque random ID. A leaker who rasterizes/prints-to-PDF removes both invisible channels — only the opt-in visible layer survives a screenshot.
* **DOCX watermarking is metadata-only** and trivially stripped; it is labelled as such.
* **Three replicas on one machine are not three administrative domains** (see "Ledger nodes"). A root user who can edit all three files *and* read the node keys from a running process can still rewrite history; distribute the nodes to close that gap.
* **The master key is not an HSM key.** Root on a running host can read the derived key from memory; the password model protects data at rest.
* **The KEM recovery copy** lets the server unwrap document keys, so a compromised server can read documents it holds — but can no longer forge a recipient's signature.
* Reference `SAKSHYA_MASTER_PASSWORD` (env) is supported but discouraged.
