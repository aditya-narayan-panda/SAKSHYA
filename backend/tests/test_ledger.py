"""Persistent, multi-node, tamper-evident ledger (MUST-1 / MUST-2)."""
import sqlite3
from contextlib import closing

import pytest

from app.core import config as cfg, key_store
from app.ledger.ledger_service import LedgerService, LedgerError

H = lambda c: c * 64  # noqa: E731  - 64-char hash placeholder
TEST_MASTER_PASSWORD = "correct-horse-battery-staple-test"


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    kd = tmp_path / "keys"; kd.mkdir()
    monkeypatch.setattr(cfg, "KEYS_DIR", kd)
    monkeypatch.setattr(cfg, "MASTER_KDF_ITERATIONS", 1_000)
    monkeypatch.delenv("SAKSHYA_MASTER_PASSWORD_FILE", raising=False)
    key_store.lock_master_key(); key_store.unlock_master_key(TEST_MASTER_PASSWORD)
    yield LedgerService(node_count=3, base_dir=tmp_path / "ledger")
    key_store.lock_master_key()


def _dir(ledger):
    return ledger.nodes[0].db_path.parent


def _raw_tamper(db_path, sql, *args):
    with closing(sqlite3.connect(db_path)) as c:      # an admin with raw sqlite3 access
        c.execute("DROP TRIGGER IF EXISTS ledger_blocks_no_update")
        c.execute(sql, args); c.commit()


def test_append_verify_and_confirmations(ledger):
    r = ledger.append_event("DEC-0001", H("a"), H("1"))
    assert r["confirmations"] == "3/3" and r["status"] == "VERIFIED"
    ledger.append_event("DEC-0002", H("b"), H("2"))
    v = ledger.verify_chain()
    assert v["status"] == "VERIFIED" and v["height"] == 2 and all(v["nodes"].values())


def test_hash_chain_links_blocks(ledger):
    b1 = ledger.append_event("DEC-0001", H("a"), H("1"))
    b2 = ledger.append_event("DEC-0002", H("b"), H("2"))
    assert b2["previous_block_hash"] == b1["block_hash"]


def test_survives_restart_same_height_and_verified(ledger, tmp_path):
    ledger.append_event("DEC-0001", H("a"), H("1")); ledger.append_event("DEC-0002", H("b"), H("2"))
    before = ledger.list_blocks()
    reopened = LedgerService(node_count=3, base_dir=_dir(ledger))     # "kill + restart backend"
    v = reopened.verify_chain()
    assert v["status"] == "VERIFIED" and v["height"] == 2
    assert reopened.list_blocks() == before
    reopened.append_event("DEC-0003", H("c"), H("3"))                 # keeps signing with the SAME keys
    assert reopened.verify_chain()["status"] == "VERIFIED"
    assert reopened.verify_chain()["height"] == 3


def test_node_keys_are_persistent_not_per_boot(ledger):
    pub = [n.public_key for n in ledger.nodes]
    again = LedgerService(node_count=3, base_dir=_dir(ledger))
    assert [n.public_key for n in again.nodes] == pub
    kd = cfg.KEYS_DIR
    assert all((kd / f"ledger-node-{i}.sig.key").exists() for i in (1, 2, 3))


def test_no_tamper_method_in_production_code():
    assert not hasattr(LedgerService, "tamper_block")


def test_manual_update_of_document_hash_is_detected(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    _raw_tamper(ledger.nodes[0].db_path, "UPDATE ledger_blocks SET document_hash=? WHERE block_number=1", H("f"))
    v = ledger.verify_chain()
    assert v["status"] == "TAMPER_DETECTED"
    assert v["nodes"] == {"node-1": False, "node-2": True, "node-3": True}
    assert v["quorum_ok"] is True
    assert ledger.get_block_for_event("DEC-0001") is not None      # 2/3 majority still serves it


def test_admin_rewrites_hash_and_resigns_one_node_still_caught_by_cross_compare(ledger):
    """Even a fully self-consistent forged chain on ONE node (recomputed hash) is caught."""
    ledger.append_event("DEC-0001", H("a"), H("1"))
    n = ledger.nodes[0]
    blk = n.read_all()[0]
    blk.document_hash = H("f"); blk.block_hash = blk.compute_hash()
    blk.signature = n._provider.sign(n._priv, blk.block_hash.encode()).hex()   # admin holds this key
    _raw_tamper(n.db_path, "UPDATE ledger_blocks SET document_hash=?, block_hash=?, signature=? WHERE block_number=1",
                blk.document_hash, blk.block_hash, blk.signature)
    v = ledger.verify_chain()
    assert v["status"] == "TAMPER_DETECTED" and v["nodes"]["node-1"] is False
    assert v["details"]["node-1"].startswith("DIVERGES_FROM_MAJORITY")
    assert ledger.get_block_for_event("DEC-0001")["document_hash"] == H("a")   # majority truth wins


def test_delete_and_update_are_blocked_at_db_level(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    with closing(sqlite3.connect(ledger.nodes[0].db_path)) as c:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            c.execute("DELETE FROM ledger_blocks")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            c.execute("UPDATE ledger_blocks SET document_hash='x'")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO ledger_blocks(block_number,event_id,document_hash,event_hash,previous_block_hash,"
                      "merkle_root,timestamp,block_hash,signature,node_id) VALUES (9,'E','short','x','y','z',0,'q','s','n')")


def test_corrupt_one_node_file_others_stay_verifiable_and_demo_survives(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    ledger.nodes[1].db_path.write_bytes(b"this is not a sqlite file" * 100)
    v = ledger.verify_chain()
    assert v["status"] == "TAMPER_DETECTED" and v["nodes"]["node-2"] is False
    assert v["nodes"]["node-1"] and v["nodes"]["node-3"] and v["quorum_ok"]
    r = ledger.append_event("DEC-0002", H("b"), H("2"))            # still writes on the 2/3 majority
    assert r["confirmations"] == "2/3" and r["status"] == "PARTIAL"
    assert ledger.get_block_for_event("DEC-0002") is not None


def test_stop_one_node_missing_file(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    ledger.nodes[2].db_path.unlink()
    v = ledger.verify_chain()
    assert v["status"] == "TAMPER_DETECTED" and v["nodes"]["node-3"] is False
    assert v["nodes"]["node-1"] and v["nodes"]["node-2"]


def test_two_nodes_down_no_quorum(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    for i in (1, 2):
        ledger.nodes[i].db_path.write_bytes(b"garbage" * 50)
    assert ledger.get_block_for_event("DEC-0001") is None          # 1/3 is not a majority
    with pytest.raises(LedgerError):
        ledger.append_event("DEC-0002", H("b"), H("2"))


def test_duplicate_event_rejected(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    with pytest.raises(LedgerError):
        ledger.append_event("DEC-0001", H("a"), H("1"))


def test_lagging_node_reported_behind(ledger):
    ledger.append_event("DEC-0001", H("a"), H("1"))
    ledger.nodes[0].db_path.unlink(); ledger.nodes[0]._init_db()    # node restored empty
    ledger.append_event("DEC-0002", H("b"), H("2"))                 # nodes 2,3 carry on
    v = ledger.verify_chain()
    assert v["nodes"]["node-1"] is False and "BEHIND" in v["details"]["node-1"]
