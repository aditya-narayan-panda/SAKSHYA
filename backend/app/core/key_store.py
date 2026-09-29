"""
Protected local key store + master-key custody.

What lives here
---------------
* KEM private keys of recipients (needed server-side to unwrap the per-document
  AES key on decrypt; a wrapped recovery copy, per spec).
* The three ledger-node signing keys (``ledger-node-N.sig.key``), generated ONCE
  and reloaded on every boot.
* Their public halves (``*.sig.pub``), which are not secret.

What does NOT live here (MUST-3)
--------------------------------
Recipient *signing* private keys. They are handed to the recipient once at
registration and never stored by the server.

Master-key custody (MUST-8)
---------------------------
Every private-key file is AES-256-GCM wrapped under a *wrapping key derived from
an operator-supplied master password* with PBKDF2-HMAC-SHA256 (600 000
iterations). Nothing secret is written to ``storage/`` or ``.env``:

    storage/keys/master.meta.json   {salt, iterations, check-value}   <- public data

so ``cat storage/.env`` / reading the whole storage tree yields no key material,
and unwrapping anything needs the password. The password is supplied at boot
via (in order) ``SAKSHYA_MASTER_PASSWORD_FILE`` (offline USB/secret file, must be
mode 0600), ``SAKSHYA_MASTER_PASSWORD`` (discouraged), or an interactive prompt.

Honest limits: this raises the bar from "read a file" to "know the password", it
is still not an HSM, and a root user on a *running* host can read the derived key
out of process memory. See README "Air-gapped key ceremony".
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import logging
import os
import stat
import sys
from pathlib import Path

from app.core import config as _cfg
from app.crypto.aes_cipher import encrypt_bytes, decrypt_bytes, pack_encrypted_file, unpack_encrypted_file

log = logging.getLogger("sakshya.keys")

MIN_PASSWORD_LEN = 12
_CHECK_LABEL = b"sakshya-master-key-check-v1"

# Derived wrapping key, held in process memory only.
_master_key: bytes | None = None


class MasterKeyError(RuntimeError):
    """Master key could not be unlocked — the backend must not serve requests."""


# --------------------------------------------------------------------------- #
# Master key derivation / unlock
# --------------------------------------------------------------------------- #
def _keys_dir() -> Path:
    # Dynamic lookup so tests (and SAKSHYA_STORAGE_DIR overrides) are honoured.
    return Path(_cfg.KEYS_DIR)


def _meta_path() -> Path:
    return _keys_dir() / "master.meta.json"


def _kdf(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)


def _check_value(key: bytes) -> str:
    return hmac.new(key, _CHECK_LABEL, hashlib.sha256).hexdigest()


def _read_password_file(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise MasterKeyError(f"{_cfg.MASTER_PASSWORD_FILE_ENV}={path} is not a readable file")
    if os.name == "posix":
        mode = stat.S_IMODE(p.stat().st_mode)
        if mode & 0o077:
            raise MasterKeyError(
                f"Refusing to read master password file {path}: mode is {oct(mode)}, "
                f"must be 0600 (chmod 600 {path})"
            )
    return p.read_text(encoding="utf-8").rstrip("\r\n")


def _obtain_password(*, confirm: bool) -> str:
    pw_file = os.environ.get(_cfg.MASTER_PASSWORD_FILE_ENV)
    if pw_file:
        return _read_password_file(pw_file)
    env_pw = os.environ.get(_cfg.MASTER_PASSWORD_ENV)
    if env_pw:
        log.warning("Master password taken from %s; prefer %s (offline file, 0600)",
                    _cfg.MASTER_PASSWORD_ENV, _cfg.MASTER_PASSWORD_FILE_ENV)
        return env_pw
    if sys.stdin is not None and sys.stdin.isatty():
        pw = getpass.getpass("SAKSHYA master password: ")
        if confirm:
            if getpass.getpass("Confirm master password: ") != pw:
                raise MasterKeyError("Master passwords do not match")
        return pw
    raise MasterKeyError(
        "No master password available. Set SAKSHYA_MASTER_PASSWORD_FILE to a 0600 file "
        "(e.g. on an offline USB stick) or start the backend from an interactive terminal."
    )


def unlock_master_key(password: str | None = None) -> bytes:
    """Derive + cache the wrapping key. First boot creates ``master.meta.json``
    (salt + check value only). Raises MasterKeyError on any problem."""
    global _master_key
    if _master_key is not None:
        return _master_key

    if os.environ.get("SAKSHYA_MASTER_KEY"):
        log.warning("SAKSHYA_MASTER_KEY is set but IGNORED: raw master keys in the "
                    "environment/.env are no longer supported (see README key ceremony).")

    meta_path = _meta_path()
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        pw = password if password is not None else _obtain_password(confirm=False)
        salt = base64.b64decode(meta["salt_b64"])
        key = _kdf(pw, salt, int(meta["iterations"]))
        if not hmac.compare_digest(_check_value(key), meta["check"]):
            raise MasterKeyError("Wrong master password")
        _master_key = key
        return key

    # ---- first boot: key ceremony -------------------------------------- #
    existing = [p.name for p in _keys_dir().glob("*.key")]
    if existing:
        raise MasterKeyError(
            "Found wrapped key files but no master.meta.json — they were wrapped under a "
            "legacy auto-generated master key. There is no in-place migration: delete storage/keys/*.key and "
            "storage/sakshya.db, then re-seed."
        )
    pw = password if password is not None else _obtain_password(confirm=True)
    if len(pw) < MIN_PASSWORD_LEN:
        raise MasterKeyError(f"Master password must be at least {MIN_PASSWORD_LEN} characters")
    salt = os.urandom(32)
    iterations = _cfg.MASTER_KDF_ITERATIONS
    key = _kdf(pw, salt, iterations)
    meta = {
        "version": 1,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": iterations,
        "salt_b64": base64.b64encode(salt).decode(),
        "check": _check_value(key),
    }
    _write_private(meta_path, json.dumps(meta, indent=2).encode())
    _master_key = key
    log.info("Master key ceremony completed: %s created", meta_path.name)
    return key


def load_master_key() -> bytes:
    """Return the in-memory wrapping key. NEVER generates, never reads .env."""
    if _master_key is None:
        raise MasterKeyError("Master key is locked — unlock_master_key() must run at boot")
    return _master_key


def lock_master_key() -> None:
    global _master_key
    _master_key = None


def _set_master_key_for_tests(key: bytes | None) -> None:  # pragma: no cover - test hook
    global _master_key
    _master_key = key


# --------------------------------------------------------------------------- #
# Wrapped private-key files
# --------------------------------------------------------------------------- #
def _write_private(path: Path, data: bytes, *, overwrite: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if overwrite else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - non-POSIX
        pass


def _safe(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "-_")


def _key_path(owner_id: str, suffix: str) -> Path:
    return _keys_dir() / f"{_safe(owner_id)}.{suffix}.key"


def _pub_path(owner_id: str, suffix: str) -> Path:
    return _keys_dir() / f"{_safe(owner_id)}.{suffix}.pub"


def _aad(owner_id: str, suffix: str) -> bytes:
    # Binds a wrapped blob to its owner+purpose so key files can't be swapped.
    return f"sakshya-key:{_safe(owner_id)}.{suffix}".encode()


def store_private_key(owner_id: str, suffix: str, private_key: bytes, *, overwrite: bool = False) -> None:
    master = load_master_key()
    blob = encrypt_bytes(private_key, master, aad=_aad(owner_id, suffix))
    _write_private(_key_path(owner_id, suffix), pack_encrypted_file(blob.nonce, blob.ciphertext),
                   overwrite=overwrite)


def load_private_key(owner_id: str, suffix: str) -> bytes:
    master = load_master_key()
    path = _key_path(owner_id, suffix)
    if not path.exists():
        raise FileNotFoundError(f"No stored '{suffix}' private key for {owner_id}")
    blob = unpack_encrypted_file(path.read_bytes())
    return decrypt_bytes(blob, master, aad=_aad(owner_id, suffix))


def has_private_key(owner_id: str, suffix: str) -> bool:
    return _key_path(owner_id, suffix).exists()


def store_public_key(owner_id: str, suffix: str, public_key: bytes) -> None:
    _write_private(_pub_path(owner_id, suffix), base64.b64encode(public_key))


def load_public_key(owner_id: str, suffix: str) -> bytes:
    path = _pub_path(owner_id, suffix)
    if not path.exists():
        raise FileNotFoundError(f"No stored '{suffix}' public key for {owner_id}")
    return base64.b64decode(path.read_bytes())


def revoke_keys(recipient_id: str) -> None:
    """Delete any server-side key material of a recipient (KEM recovery copy;
    a stray legacy 'sig' file if one still exists)."""
    for suffix in ("kem", "sig"):
        path = _key_path(recipient_id, suffix)
        if path.exists():
            path.unlink()
