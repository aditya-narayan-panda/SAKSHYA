"""Offline login/authentication tests (SIH demo requirement §5).

Proves, over real HTTP through the full FastAPI stack with zero network
(no external IdP, Firebase, OAuth, or cloud of any kind):

  1. Correct credentials            -> HTTP 200 + bearer token
  2. Wrong password                 -> HTTP 401
  3. Unknown user                   -> HTTP 401
  4. Protected endpoint, no token   -> HTTP 401/403
  5. Protected endpoint, valid token-> success
  6. /api/auth/me                   -> the authenticated user
  7. Login works with the network completely unavailable
"""

import socket

from tests.conftest import auth_headers


def _no_network():
    real_create = socket.socket.connect

    def blocked(*args, **kwargs):
        raise OSError("network unavailable (simulated air-gap)")

    return blocked


def test_1_login_correct_credentials_returns_200_and_token(client):
    res = client.post(
        "/api/auth/login",
        json={"recipient_id": "REC-OFFICER01", "password": "sakshya-officer01"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token"]
    assert body["recipient_id"] == "REC-OFFICER01"
    assert body["name"] == "Officer-01"


def test_2_login_wrong_password_returns_401(client):
    res = client.post(
        "/api/auth/login",
        json={"recipient_id": "REC-OFFICER01", "password": "wrong-password"},
    )
    assert res.status_code == 401, res.text


def test_3_login_unknown_user_returns_401(client):
    res = client.post(
        "/api/auth/login",
        json={"recipient_id": "REC-NOPE99", "password": "sakshya-officer01"},
    )
    assert res.status_code == 401, res.text


def test_4_protected_endpoint_without_token_is_rejected(client):
    for method, path in [
        ("get", "/api/documents"),
        ("get", "/api/recipients"),
        ("post", "/api/protect"),
        ("post", "/api/decrypt/DOC-1"),
        ("get", "/api/investigations"),
        ("get", "/api/reports"),
        ("get", "/api/ledger/blocks"),
        ("get", "/api/auth/me"),
    ]:
        res = getattr(client, method)(path)
        assert res.status_code in (401, 403), f"{method} {path} -> {res.status_code}"


def test_5_protected_endpoint_with_valid_token_succeeds(client, officer01_token):
    res = client.get("/api/documents", headers=auth_headers(officer01_token))
    assert res.status_code == 200, res.text
    res = client.get("/api/recipients", headers=auth_headers(officer01_token))
    assert res.status_code == 200, res.text
    assert any(
        r["recipient_id"] == "REC-OFFICER01" for r in res.json()["items"]
    )


def test_6_auth_me_returns_authenticated_user(client, officer01_token):
    res = client.get("/api/auth/me", headers=auth_headers(officer01_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["recipient_id"] == "REC-OFFICER01"
    assert body["name"] == "Officer-01"


def test_7_login_works_with_network_unavailable(client, monkeypatch):
    """Simulate a fully air-gapped machine: every socket connect raises."""
    monkeypatch.setattr(socket.socket, "connect", _no_network())
    # Localhost TestClient transport never opens a real socket, so this only
    # fails if the app itself tries a hidden external call.
    res = client.post(
        "/api/auth/login",
        json={"recipient_id": "REC-OFFICER02", "password": "sakshya-officer02"},
    )
    assert res.status_code == 200, res.text
    me = client.get("/api/auth/me", headers=auth_headers(res.json()["token"]))
    assert me.status_code == 200, me.text
    assert me.json()["recipient_id"] == "REC-OFFICER02"


def test_health_is_public_and_reports_offline(client):
    res = client.get("/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "SAKSHYA Backend"
    assert body["offline"] is True


def test_crypto_status_reports_real_pqc_or_honest_fallback(client):
    res = client.get("/api/system/crypto-status")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["environment"] == "offline"
    if body["pqc_available"]:
        assert body["kem"] == "ML-KEM-768"
        assert body["signature"] == "ML-DSA-65"
        assert body["fallback"] is None
    else:
        assert body["kem"] == "PQC NOT AVAILABLE"
        assert body["signature"] == "PQC NOT AVAILABLE"
        assert "DEVELOPMENT FALLBACK ONLY" in body["fallback"]
