# SAKSHYA Backend — FastAPI + SQLite, fully local/offline

Local authentication (bcrypt) + SQLite + ML-KEM-768 / ML-DSA-65 + AES-256-GCM
+ forensic watermarking + hash-chain ledger + local forensic reports.
No Firebase / OAuth / cloud KMS / cloud DB / blockchain / external API.

## Layout

    app.py            FastAPI application factory (create_app) + shared `app`
    main.py           Executable entry point (`python main.py`, `uvicorn …`)
    app/              routers, services, crypto, watermark, ledger, models
    scripts/seed.py   idempotent deterministic demo seeding
    tests/            pytest suite (unit + HTTP auth + offline end-to-end)
    data/             optional alternate data dir (see data/README.md)
    requirements.txt  pinned runtime deps (cryptography==50.0.0 → real PQC)

## Run (Windows PowerShell)

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\seed.py
python main.py
```

Bash/macOS/Linux:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed.py
python main.py
```

Or with uvicorn directly (from `backend/`):

```powershell
uvicorn app:app --host 127.0.0.1 --port 8100
uvicorn main:app --host 127.0.0.1 --port 8100
```

Swagger: http://127.0.0.1:8100/docs · Health: http://127.0.0.1:8100/health

## Demo credentials (fixed, deterministic)

| Officer | Recipient ID | Password |
|---|---|---|
| Officer-01 | `REC-OFFICER01` | `sakshya-officer01` |
| Officer-02 | `REC-OFFICER02` | `sakshya-officer02` |
| Officer-03 | `REC-OFFICER03` | `sakshya-officer03` |

Re-running `python scripts/seed.py` never duplicates users or documents.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest tests\ -v
```

## Key endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | public | `{status: ok, service, offline: true}` |
| `GET /api/system/health` | public | backend liveness |
| `GET /api/system/crypto-status` | public | real PQC vs fallback report |
| `GET /api/system/status` | public | backend/db/ledger/PQC/storage/env |
| `GET /api/system/settings` | login | full configuration |
| `POST /api/auth/login` | public | bearer token (DB session, 12 h) |
| `GET /api/auth/me` | login | current recipient |
| `POST /api/auth/logout` | login | invalidate session |
| `GET/POST /api/documents…` | login | list/detail/delete |
| `GET/POST /api/recipients…` | login | list/detail/create/revoke |
| `POST /api/protect` | login | encrypt + authorize recipients |
| `POST /api/decrypt/{id}` | login (owner) | decrypt + watermark + sign + ledger |
| `GET /api/events[/{id}/download]` | login | events / owner-only download |
| `POST /api/events/{id}/render` | login (owner) | rendering receipt |
| `GET /api/ledger/blocks|verify` | login | ledger + verification |
| `GET/POST /api/investigations` | login | leak attribution |
| `GET/POST /api/reports…` | login | forensic reports + downloads |
| `GET /api/dashboard` | login | counts + algorithms + ledger status |
