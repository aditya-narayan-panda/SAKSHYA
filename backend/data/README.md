# Local data directory (alternative location)

The SAKSHYA backend stores its SQLite database and all file artifacts in the
**canonical local data directory** `<repo>/storage/` by default:

    storage/sakshya.db        SQLite database (auth sessions, documents,
                              recipients, events, ledger mirror, reports)
    storage/keys/             AES-wrapped recipient private keys
    storage/encrypted/        AES-256-GCM ciphertext blobs
    storage/decrypted/        watermarked decrypted copies
    storage/reports/          generated forensic PDFs/JSON

To keep the database inside `backend/data/` instead (e.g. per-site policy),
set before starting the backend:

    PowerShell:  $env:SAKSHYA_STORAGE_DIR = "<repo>\backend\data"
    Bash:        export SAKSHYA_STORAGE_DIR="<repo>/backend/data"

then run `python scripts/seed.py` once. Everything (DB, keys, artifacts) is
created under that directory; nothing cloud, nothing outside the machine.
