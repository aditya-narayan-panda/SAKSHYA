"""Authentication unit tests — fully local (SQLite + bcrypt/PBKDF2, no network).

Covers password hashing and the database-backed session lifecycle, including
the stale-session fix: sessions live in ``auth_sessions`` so they are
resolvable through any connection to the same database file.
"""

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import SCHEME, hash_password, verify_password
from app.core import auth as auth_core
from app.models.models import Base


def _test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_password_hash_round_trip():
    salt, digest = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", salt, digest) is True


def test_password_hash_rejects_wrong_password():
    salt, digest = hash_password("correct horse battery staple")
    assert verify_password("wrong password", salt, digest) is False


def test_password_hash_is_salted():
    # Same password twice -> different stored hashes (bcrypt salt / PBKDF2
    # salt), so credential rows never collide across recipients.
    salt1, digest1 = hash_password("same-password")
    salt2, digest2 = hash_password("same-password")
    assert (salt1, digest1) != (salt2, digest2)
    assert verify_password("same-password", salt1, digest1) is True
    assert verify_password("same-password", salt2, digest2) is True


def test_password_scheme_is_documented():
    assert SCHEME in ("bcrypt", "pbkdf2-sha256")


def test_session_lifecycle_db_backed():
    db = _test_db()
    token = auth_core.create_session(db, "REC-TEST01")
    assert auth_core.resolve_session(db, token) == "REC-TEST01"
    auth_core.destroy_session(db, token)
    assert auth_core.resolve_session(db, token) is None
    db.close()


def test_unknown_token_resolves_to_none():
    db = _test_db()
    assert auth_core.resolve_session(db, "not-a-real-token") is None
    db.close()


def test_expired_session_resolves_to_none():
    from app.models.models import AuthSession

    db = _test_db()
    token = auth_core.create_session(db, "REC-TEST01")
    row = db.query(AuthSession).first()
    assert row is not None
    row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    db.commit()
    assert auth_core.resolve_session(db, token) is None
    db.close()


def test_session_survives_new_connection_same_db(tmp_path):
    """Regression test for the stale-session bug: a token created on one
    connection resolves on another connection to the same database file
    (the old in-memory dict store failed this by design)."""
    from app.core.database import SessionLocal as _RealSession  # noqa: F401 (import guard)

    db_path = tmp_path / "sessions.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Maker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db1, db2 = Maker(), Maker()
    token = auth_core.create_session(db1, "REC-OFFICER01")
    assert auth_core.resolve_session(db2, token) == "REC-OFFICER01"
    db1.close()
    db2.close()
