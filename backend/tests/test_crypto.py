"""
These tests exercise exactly the code paths that were manually verified during
development (see the project README's "What's been tested" section). Run with:
    cd backend && pytest tests/ -v
"""
import os
import pytest

from app.crypto import pqc_provider
from app.crypto.pqc_provider import get_provider
from app.crypto.aes_cipher import generate_aes_key, encrypt_bytes, decrypt_bytes, pack_encrypted_file, unpack_encrypted_file


def test_kem_round_trip():
    provider = get_provider()
    kp = provider.generate_kem_keypair()
    enc = provider.encapsulate(kp.public_key)
    recovered = provider.decapsulate(enc.ciphertext, kp.private_key)
    assert recovered == enc.shared_secret


def test_signature_valid_and_tamper_rejected():
    provider = get_provider()
    kp = provider.generate_sig_keypair()
    msg = b"DEC-0086|DOC-2026-001|WM-72A91F"
    sig = provider.sign(kp.private_key, msg)
    assert provider.verify(kp.public_key, msg, sig) is True
    assert provider.verify(kp.public_key, msg + b"tampered", sig) is False


def test_wrong_recipient_cannot_forge_signature():
    provider = get_provider()
    kp_a = provider.generate_sig_keypair()
    kp_b = provider.generate_sig_keypair()
    msg = b"attribution-payload"
    sig = provider.sign(kp_a.private_key, msg)
    assert provider.verify(kp_b.public_key, msg, sig) is False


def test_aes_gcm_round_trip():
    key = generate_aes_key()
    data = os.urandom(4096)
    blob = encrypt_bytes(data, key)
    packed = pack_encrypted_file(blob.nonce, blob.ciphertext)
    out = decrypt_bytes(unpack_encrypted_file(packed), key)
    assert out == data


def test_aes_gcm_tamper_detected():
    key = generate_aes_key()
    blob = encrypt_bytes(b"secret document contents", key)
    packed = bytearray(pack_encrypted_file(blob.nonce, blob.ciphertext))
    packed[-1] ^= 0xFF
    with pytest.raises(Exception):
        decrypt_bytes(unpack_encrypted_file(bytes(packed)), key)


def test_aes_wrong_key_fails():
    key1 = generate_aes_key()
    key2 = generate_aes_key()
    blob = encrypt_bytes(b"secret", key1)
    with pytest.raises(Exception):
        decrypt_bytes(blob, key2)


# ---- MUST-6: PQC-only, no silent classical fallback -------------------------------------
def test_missing_pqc_refuses_boot_and_provider(monkeypatch):
    """Simulates `pip install cryptography==47` (no ML-KEM/ML-DSA): loud failure, never silent."""
    monkeypatch.setattr(pqc_provider, "_HAS_PQC", False)
    monkeypatch.delenv("SAKSHYA_ALLOW_FALLBACK", raising=False)
    with pytest.raises(RuntimeError, match="Post-quantum cryptography is REQUIRED"):
        pqc_provider.enforce_pqc()
    with pytest.raises(RuntimeError, match="Post-quantum cryptography is REQUIRED"):
        pqc_provider.get_provider()


def test_fallback_flag_is_refused_in_production(monkeypatch):
    from app.core import config as cfg
    monkeypatch.setattr(pqc_provider, "_HAS_PQC", False)
    monkeypatch.setenv("SAKSHYA_ALLOW_FALLBACK", "true")
    monkeypatch.setattr(cfg, "IS_PRODUCTION", True)
    with pytest.raises(RuntimeError):
        pqc_provider.enforce_pqc()
    with pytest.raises(RuntimeError):
        pqc_provider.get_provider()


def test_real_pqc_selftest_passes_when_available():
    if not pqc_provider.PQC_ACTIVE:
        pytest.skip("cryptography<48 in this environment: real ML-KEM/ML-DSA unavailable")
    pqc_provider.enforce_pqc()
    info = pqc_provider.algorithm_info()
    assert info["kem_algorithm"] == "ML-KEM-768" and info["signature_algorithm"] == "ML-DSA-65"
