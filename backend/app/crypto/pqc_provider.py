"""
PQCKeyProvider — post-quantum key encapsulation and signatures, PQC-ONLY.

  * KEM:        ML-KEM-768   (NIST FIPS 203)
  * Signatures: ML-DSA-65    (NIST FIPS 204)

We never implement ML-KEM/ML-DSA ourselves — we call into ``cryptography``
(>=48, pinned to 50.0.0 in requirements.txt and docker/backend.Dockerfile).

MUST-6: there is NO silent fallback. If the installed ``cryptography`` lacks
ML-KEM/ML-DSA, ``enforce_pqc()`` (called from the app's startup hook) raises
``RuntimeError`` and the backend refuses to boot; ``get_provider()`` raises too,
so nothing can quietly run on classical primitives. The single escape hatch is
the developer flag ``SAKSHYA_ALLOW_FALLBACK=true`` (never allowed when
``SAKSHYA_APP_ENV=production``), which loads the classical stand-in from
``app/crypto/_dev_classical.py`` and is reported honestly by
``GET /api/system/crypto-status`` as "PQC NOT AVAILABLE".
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

from app.core import config as _cfg

log = logging.getLogger("sakshya.crypto")

try:
    from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey, MLKEM768PublicKey
    from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PrivateKey, MLDSA65PublicKey
    _HAS_PQC = True
except ImportError:
    _HAS_PQC = False

KEM_ALGORITHM_NAME = "ML-KEM-768" if _HAS_PQC else "X25519 (dev fallback — NOT post-quantum)"
SIG_ALGORITHM_NAME = "ML-DSA-65" if _HAS_PQC else "Ed25519 (dev fallback — NOT post-quantum)"
PQC_ACTIVE = _HAS_PQC


@dataclass
class KeyPairBytes:
    public_key: bytes
    private_key: bytes  # caller is responsible for where this goes (see MUST-3)


@dataclass
class EncapsulationResult:
    ciphertext: bytes      # goes to DocumentRecipient.encapsulated_key (this IS the wrapped AES key material)
    shared_secret: bytes   # used directly as the AES-256 key


class KeyProvider(Protocol):
    def generate_kem_keypair(self) -> KeyPairBytes: ...
    def generate_sig_keypair(self) -> KeyPairBytes: ...
    def encapsulate(self, public_key: bytes) -> EncapsulationResult: ...
    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes: ...
    def sign(self, private_key: bytes, message: bytes) -> bytes: ...
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class _RealPQCProvider:
    """Backed by cryptography's native ML-KEM-768 / ML-DSA-65 (mlkem/mldsa modules)."""

    def generate_kem_keypair(self) -> KeyPairBytes:
        sk = MLKEM768PrivateKey.generate()
        pk = sk.public_key()
        return KeyPairBytes(
            public_key=pk.public_bytes_raw(),
            private_key=sk.private_bytes_raw(),
        )

    def generate_sig_keypair(self) -> KeyPairBytes:
        sk = MLDSA65PrivateKey.generate()
        pk = sk.public_key()
        return KeyPairBytes(
            public_key=pk.public_bytes_raw(),
            private_key=sk.private_bytes_raw(),
        )

    def encapsulate(self, public_key: bytes) -> EncapsulationResult:
        pk = MLKEM768PublicKey.from_public_bytes(public_key)
        # NOTE: real lib returns (shared_secret, ciphertext) in this order.
        shared_secret, ciphertext = pk.encapsulate()
        return EncapsulationResult(ciphertext=ciphertext, shared_secret=shared_secret)

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        sk = MLKEM768PrivateKey.from_seed_bytes(private_key)
        return sk.decapsulate(ciphertext)

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        sk = MLDSA65PrivateKey.from_seed_bytes(private_key)
        return sk.sign(message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            pk = MLDSA65PublicKey.from_public_bytes(public_key)
            pk.verify(signature, message)
            return True
        except Exception:
            return False


def _fallback_allowed() -> bool:
    return os.environ.get("SAKSHYA_ALLOW_FALLBACK", "").strip().lower() in ("1", "true", "yes")


def _refuse() -> RuntimeError:
    return RuntimeError(
        "Post-quantum cryptography is REQUIRED but the installed 'cryptography' package has no "
        "ML-KEM-768 / ML-DSA-65 (need cryptography>=48; this project pins 50.0.0). Refusing to run on "
        "classical X25519/Ed25519. Fix: pip install cryptography==50.0.0. "
        "(Developer machines only: SAKSHYA_ALLOW_FALLBACK=true, never in production.)"
    )


def get_provider() -> KeyProvider:
    if _HAS_PQC:
        return _RealPQCProvider()
    if _fallback_allowed() and not _cfg.IS_PRODUCTION:
        from app.crypto._dev_classical import _ClassicalFallbackProvider

        return _ClassicalFallbackProvider()
    raise _refuse()


def enforce_pqc() -> None:
    """Startup gate. Raises RuntimeError (=> backend refuses to boot) unless real
    ML-KEM-768 / ML-DSA-65 is active, then proves it with a round-trip self-test."""
    if not _HAS_PQC:
        if _fallback_allowed() and _cfg.IS_PRODUCTION:
            raise RuntimeError("SAKSHYA_ALLOW_FALLBACK is not permitted when SAKSHYA_APP_ENV=production")
        if not _fallback_allowed():
            raise _refuse()
        log.critical("DEVELOPER FALLBACK ACTIVE: classical X25519/Ed25519 in use — NOT post-quantum")
        return
    provider = _RealPQCProvider()
    kem = provider.generate_kem_keypair()
    enc = provider.encapsulate(kem.public_key)
    if provider.decapsulate(enc.ciphertext, kem.private_key) != enc.shared_secret:
        raise RuntimeError("ML-KEM-768 self-test failed")
    sig = provider.generate_sig_keypair()
    msg = b"sakshya-pqc-selftest"
    if not provider.verify(sig.public_key, msg, provider.sign(sig.private_key, msg)):
        raise RuntimeError("ML-DSA-65 self-test failed")


def algorithm_info() -> dict:
    return {
        "pqc_active": _HAS_PQC,
        "kem_algorithm": KEM_ALGORITHM_NAME,
        "signature_algorithm": SIG_ALGORITHM_NAME,
        "note": (
            "Real NIST post-quantum algorithms active (ML-KEM-768, ML-DSA-65)."
            if _HAS_PQC
            else "DEVELOPER FALLBACK (SAKSHYA_ALLOW_FALLBACK=true): classical X25519/Ed25519, NOT post-quantum."
        ),
    }
