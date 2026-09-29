"""
DEVELOPER-ONLY classical stand-in (X25519 + Ed25519). NOT post-quantum.

This module is imported lazily by ``pqc_provider.get_provider()`` and ONLY when
``SAKSHYA_ALLOW_FALLBACK=true`` AND the process is not running in production.
It is deliberately outside the normal import path so a production backend can
never end up on classical crypto by accident (MUST-6).
"""
from __future__ import annotations

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.crypto.pqc_provider import EncapsulationResult, KeyPairBytes


class _ClassicalFallbackProvider:
    """
    Used ONLY under SAKSHYA_ALLOW_FALLBACK=true (developer machines). Same interface shape as the
    real provider so the rest of the app never has to know which one is active.
    X25519 does not natively "encapsulate" like a KEM, so we build a standard
    ECDH-then-HKDF construction and package the ephemeral public key as the
    'ciphertext' — this is a well-known, safe pattern (ECIES-style), just not PQC.
    """

    def generate_kem_keypair(self) -> KeyPairBytes:
        sk = x25519.X25519PrivateKey.generate()
        pk = sk.public_key()
        return KeyPairBytes(
            public_key=pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw),
            private_key=sk.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
            ),
        )

    def generate_sig_keypair(self) -> KeyPairBytes:
        sk = ed25519.Ed25519PrivateKey.generate()
        pk = sk.public_key()
        return KeyPairBytes(
            public_key=pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw),
            private_key=sk.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
            ),
        )

    def encapsulate(self, public_key: bytes) -> EncapsulationResult:
        recipient_pk = x25519.X25519PublicKey.from_public_bytes(public_key)
        ephemeral_sk = x25519.X25519PrivateKey.generate()
        ephemeral_pk_bytes = ephemeral_sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        raw_shared = ephemeral_sk.exchange(recipient_pk)
        shared_secret = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"sakshya-kem-fallback"
        ).derive(raw_shared)
        # "ciphertext" = ephemeral public key; recipient re-derives the same secret on decapsulate
        return EncapsulationResult(ciphertext=ephemeral_pk_bytes, shared_secret=shared_secret)

    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        recipient_sk = x25519.X25519PrivateKey.from_private_bytes(private_key)
        ephemeral_pk = x25519.X25519PublicKey.from_public_bytes(ciphertext)
        raw_shared = recipient_sk.exchange(ephemeral_pk)
        return HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"sakshya-kem-fallback"
        ).derive(raw_shared)

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        sk = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        return sk.sign(message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        pk = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
        try:
            pk.verify(signature, message)
            return True
        except Exception:
            return False
