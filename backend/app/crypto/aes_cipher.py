"""
AES-256-GCM authenticated encryption for document bodies.

The 32-byte AES key itself is never stored anywhere in plaintext on disk —
it only ever exists in memory, either freshly generated (protect flow) or
freshly recovered via PQCKeyProvider.decapsulate() (decrypt flow).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AES_KEY_SIZE = 32          # AES-256
NONCE_SIZE = 12            # 96-bit nonce, standard for GCM


@dataclass
class EncryptedBlob:
    nonce: bytes
    ciphertext: bytes  # includes GCM tag appended (cryptography lib default)


def generate_aes_key() -> bytes:
    return os.urandom(AES_KEY_SIZE)


def encrypt_bytes(plaintext: bytes, key: bytes, aad: bytes | None = None) -> EncryptedBlob:
    if len(key) != AES_KEY_SIZE:
        raise ValueError(f"AES-256 key must be {AES_KEY_SIZE} bytes, got {len(key)}")
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=aad)
    return EncryptedBlob(nonce=nonce, ciphertext=ciphertext)


def decrypt_bytes(blob: EncryptedBlob, key: bytes, aad: bytes | None = None) -> bytes:
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(blob.nonce, blob.ciphertext, associated_data=aad)


def pack_encrypted_file(nonce: bytes, ciphertext: bytes) -> bytes:
    """On-disk format: [12-byte nonce][ciphertext+tag]. Kept simple & inspectable."""
    return nonce + ciphertext


def unpack_encrypted_file(blob: bytes) -> EncryptedBlob:
    return EncryptedBlob(nonce=blob[:NONCE_SIZE], ciphertext=blob[NONCE_SIZE:])
