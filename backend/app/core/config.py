import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
# Canonical local data directory. The SQLite database, wrapped private keys,
# encrypted/decrypted artifacts, watermarks, evidence and reports all live
# here.  Nothing under frontend/, nothing in any cloud.  Override with
# SAKSHYA_STORAGE_DIR if the demo machine needs a different disk location
# (e.g. backend/data); the default below is used by seed, Docker and docs.
STORAGE_DIR = Path(os.environ.get("SAKSHYA_STORAGE_DIR", PROJECT_ROOT / "storage"))

DOCUMENTS_DIR = STORAGE_DIR / "documents"
ENCRYPTED_DIR = STORAGE_DIR / "encrypted"
DECRYPTED_DIR = STORAGE_DIR / "decrypted"
WATERMARKS_DIR = STORAGE_DIR / "watermarks"
EVIDENCE_DIR = STORAGE_DIR / "evidence"
REPORTS_DIR = STORAGE_DIR / "reports"
KEYS_DIR = STORAGE_DIR / "keys"
TEMP_DIR = STORAGE_DIR / "temporary"
# One SQLite file per ledger node (ledger-node1.db, ledger-node2.db, ...).
# For a real deployment mount each file (or each backend replica's volume) on a
# different disk/host — see README "Ledger nodes".
LEDGER_DIR = Path(os.environ.get("SAKSHYA_LEDGER_DIR", STORAGE_DIR / "ledger"))

for d in [DOCUMENTS_DIR, ENCRYPTED_DIR, DECRYPTED_DIR, WATERMARKS_DIR, EVIDENCE_DIR, REPORTS_DIR, KEYS_DIR, TEMP_DIR, LEDGER_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("SAKSHYA_DATABASE_URL", f"sqlite:///{STORAGE_DIR / 'sakshya.db'}")

# Runtime environment: "development" (default) or "production". Controls
# whether uncaught-exception bodies include diagnostic detail and whether the
# permissive localhost-regex CORS fallback is enabled. The SIH demo runs
# "production" for clean JSON errors without tracebacks.
APP_ENV = os.environ.get("SAKSHYA_APP_ENV", os.environ.get("APP_ENV", "development")).lower()
IS_PRODUCTION = APP_ENV == "production"

# Local demo ports. Backend serves 8100 by default (see backend/main.py);
# the Vite dev server runs on 5173 and the Docker nginx frontend on 8080.
BACKEND_PORT = int(os.environ.get("SAKSHYA_PORT", "8100"))

# --- Master-key custody (see core/key_store.py) -------------------------------
# The wrapping key is DERIVED from an operator-supplied master password
# (PBKDF2-HMAC-SHA256, 600k iterations). It is never generated-and-written to
# disk. The password comes from, in order:
#   1. SAKSHYA_MASTER_PASSWORD_FILE  - path to an offline/USB/secret file (mode 0600)
#   2. SAKSHYA_MASTER_PASSWORD       - env var (discouraged: visible in /proc/<pid>/environ)
#   3. an interactive prompt         - only when stdin is a TTY
# If none is available the backend refuses to boot.
MASTER_PASSWORD_FILE_ENV = "SAKSHYA_MASTER_PASSWORD_FILE"
MASTER_PASSWORD_ENV = "SAKSHYA_MASTER_PASSWORD"
MASTER_KDF_ITERATIONS = 600_000
# Public, non-secret KDF parameters + password check value: KEYS_DIR/master.meta.json

# Post-quantum crypto is mandatory: see app/crypto/pqc_provider.py (SAKSHYA_ALLOW_FALLBACK is
# read there, dev-only, and refused in production).

MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("SAKSHYA_MAX_UPLOAD_MB", "25")) * 1024 * 1024
# Only formats we can actually watermark are accepted at Protect time:
#   .pdf  -> full dual-channel (metadata + per-page invisible content marker)
#   .docx -> metadata-only marker (clearly labelled as such)
# .txt / .xlsx would produce an un-attributable copy, so they are rejected
# with UNSUPPORTED_WATERMARK_TYPE instead of being stored with a NULL watermark.
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
LEDGER_NODE_COUNT = int(os.environ.get("SAKSHYA_LEDGER_NODES", "3"))
# When true, an investigation is only IDENTIFIED if ALL ledger nodes verify.
# Default (false): a >=2/3 majority of healthy, agreeing nodes is enough, and any
# divergent node is reported loudly in the result instead of silently ignored.
LEDGER_STRICT = os.environ.get("SAKSHYA_LEDGER_STRICT", "").strip().lower() in ("1", "true", "yes")

# Explicit local origins only — never "*" (which is incompatible with
# allow_credentials anyway). Covers Vite dev (5173), explicit 127.0.0.1, and
# the Docker nginx frontend (8080). Extra origins via SAKSHYA_CORS_ORIGINS.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "SAKSHYA_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if o.strip()
]


