"""
LedgerService — local, persistent, multi-node hash-chained evidence ledger.

MUST-1 + MUST-2. What this is
-----------------------------
N (default 3) *independent* ledger stores. Each node has

  * its own SQLite file      ``<LEDGER_DIR>/ledger-node<i>.db``  (table ``ledger_blocks``)
  * its own signing key      ``<KEYS_DIR>/ledger-node-<i>.sig.key`` (wrapped, generated ONCE,
                              reloaded on every boot) + ``ledger-node-<i>.sig.pub``
  * its own view of the chain (previous_block_hash, merkle_root, block_hash recomputed
    from ITS OWN data)

``append_event()`` is a two-phase local commit: every node independently *prepares*
(builds + hashes + signs the next block with its own key), the coordinator compares
the resulting block hashes, and only nodes whose hash matches the quorum group
*commit*. ``confirmations`` is ``k/N`` where k = nodes that independently produced the
same block_hash — ``3/3`` only when all three agree.

``verify_chain()`` re-reads every node's DB from disk, recomputes every hash, verifies
every signature with the persistent node public key, then cross-compares block_hash
per height across nodes. Any divergence => ``TAMPER_DETECTED`` and ``nodes:{node-1:false}``;
the remaining nodes stay individually verifiable and the service keeps working on the
>=2/3 majority.

DB-level append-only: CHECK constraints, UNIQUE(block_number|event_id|block_hash) and
BEFORE UPDATE / BEFORE DELETE triggers that ABORT. There is no update/delete method in
this module and no API route for one. (A user who can open the file with raw sqlite3 can
still DROP the triggers — that is exactly what the cross-node comparison + signatures
exist to catch.)

HONEST LIMIT: three files on one host run by one operator are three *replicas*, not
three administrative domains. For "no single admin can alter history" in the strict
sense, put each node file on a different machine/volume under a different custodian
(``SAKSHYA_LEDGER_DIR`` per node process) — the interface here does not change.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from app.core import key_store
from app.core import config as _cfg
from app.crypto.pqc_provider import get_provider

log = logging.getLogger("sakshya.ledger")

GENESIS_HASH = "0" * 64


class LedgerError(RuntimeError):
    """Ledger could not reach quorum / refused an unsafe operation."""


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return _sha256_hex(b"")
    layer = list(hashes)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [_sha256_hex((layer[i] + layer[i + 1]).encode()) for i in range(0, len(layer), 2)]
    return layer[0]


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS ledger_blocks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    block_number        INTEGER NOT NULL UNIQUE CHECK (block_number >= 1),
    event_id            TEXT    NOT NULL UNIQUE CHECK (length(event_id) > 0),
    document_hash       TEXT    NOT NULL CHECK (length(document_hash) = 64),
    event_hash          TEXT    NOT NULL CHECK (length(event_hash) = 64),
    previous_block_hash TEXT    NOT NULL CHECK (length(previous_block_hash) = 64),
    merkle_root         TEXT    NOT NULL CHECK (length(merkle_root) = 64),
    timestamp           REAL    NOT NULL,
    block_hash          TEXT    NOT NULL UNIQUE CHECK (length(block_hash) = 64),
    signature           TEXT    NOT NULL CHECK (length(signature) > 0),
    node_id             TEXT    NOT NULL CHECK (length(node_id) > 0),
    confirmations       INTEGER NOT NULL DEFAULT 1 CHECK (confirmations >= 1),
    CHECK (block_number > 1 OR previous_block_hash = '{GENESIS_HASH}')
);
CREATE TRIGGER IF NOT EXISTS ledger_blocks_no_update
BEFORE UPDATE ON ledger_blocks
BEGIN SELECT RAISE(ABORT, 'ledger_blocks is append-only: UPDATE forbidden'); END;
CREATE TRIGGER IF NOT EXISTS ledger_blocks_no_delete
BEFORE DELETE ON ledger_blocks
BEGIN SELECT RAISE(ABORT, 'ledger_blocks is append-only: DELETE forbidden'); END;
"""

_COLS = ("block_number, event_id, document_hash, event_hash, previous_block_hash, merkle_root, "
         "timestamp, block_hash, signature, node_id, confirmations")


@dataclass
class Block:
    block_number: int
    event_id: str
    document_hash: str
    event_hash: str
    previous_block_hash: str
    merkle_root: str
    timestamp: float
    block_hash: str = ""
    signature: str = ""        # hex; signature over block_hash by THIS node's key
    node_id: str = ""
    confirmations: int = 1     # nodes that independently produced this block_hash

    def compute_hash(self) -> str:
        # node_id / signature / confirmations are deliberately NOT part of the hash so
        # every honest node derives the identical block_hash for identical content.
        payload = {
            "block_number": self.block_number,
            "event_id": self.event_id,
            "document_hash": self.document_hash,
            "event_hash": self.event_hash,
            "previous_block_hash": self.previous_block_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
        }
        return _sha256_hex(json.dumps(payload, sort_keys=True).encode())

    @classmethod
    def from_row(cls, row: tuple) -> "Block":
        return cls(*row[:7], block_hash=row[7], signature=row[8], node_id=row[9], confirmations=row[10])

    def as_dict(self) -> dict:
        return asdict(self)


class _NodeReplica:
    """One ledger node: own SQLite file, own persistent signing key, own chain view."""

    def __init__(self, index: int, base_dir: Path, provider):
        self.node_id = f"node-{index}"
        self.key_owner = f"ledger-node-{index}"
        self.db_path = Path(base_dir) / f"ledger-node{index}.db"
        self._provider = provider
        self.init_error: Optional[str] = None
        self._priv: Optional[bytes] = None
        self.public_key: Optional[bytes] = None

        try:
            self._init_db()
        except sqlite3.DatabaseError as e:
            # A corrupt/unreadable node file must not stop the other nodes from booting.
            self.init_error = f"UNREADABLE: {e}"
            log.error("%s database unusable at boot: %s", self.node_id, e)
        self._load_or_create_key()

    # ---- storage ------------------------------------------------------- #
    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10)
        c.execute("PRAGMA recursive_triggers = ON")   # INSERT OR REPLACE must still fire DELETE guard
        c.execute("PRAGMA synchronous = FULL")
        return c

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as c:
            c.executescript(SCHEMA)
            c.commit()

    def _height_on_disk(self) -> int:
        try:
            with closing(self._connect()) as c:
                return c.execute("SELECT COUNT(*) FROM ledger_blocks").fetchone()[0]
        except sqlite3.DatabaseError:
            return -1

    def _load_or_create_key(self) -> None:
        have_priv = key_store.has_private_key(self.key_owner, "sig")
        try:
            pub = key_store.load_public_key(self.key_owner, "sig")
        except FileNotFoundError:
            pub = None
        if have_priv and pub:
            self._priv = key_store.load_private_key(self.key_owner, "sig")
            self.public_key = pub
            return
        if have_priv != bool(pub):
            raise LedgerError(f"{self.node_id}: key files inconsistent (private={have_priv}, public={bool(pub)})")
        # No key yet. Minting a fresh key for a node that already holds signed blocks would
        # silently invalidate them — refuse.
        if self._height_on_disk() > 0:
            raise LedgerError(f"{self.node_id}: ledger has blocks but its signing key is missing; refusing to mint a new key")
        kp = self._provider.generate_sig_keypair()
        key_store.store_private_key(self.key_owner, "sig", kp.private_key)
        key_store.store_public_key(self.key_owner, "sig", kp.public_key)
        self._priv, self.public_key = kp.private_key, kp.public_key
        log.info("%s: generated persistent signing key (%s)", self.node_id, self.key_owner)

    # ---- reads --------------------------------------------------------- #
    def read_all(self) -> list[Block]:
        if self.init_error:
            raise sqlite3.DatabaseError(self.init_error)
        with closing(self._connect()) as c:
            rows = c.execute(f"SELECT {_COLS} FROM ledger_blocks ORDER BY block_number").fetchall()
        return [Block.from_row(r) for r in rows]

    def tip(self) -> Optional[Block]:
        if self.init_error:
            raise sqlite3.DatabaseError(self.init_error)
        with closing(self._connect()) as c:
            row = c.execute(f"SELECT {_COLS} FROM ledger_blocks ORDER BY block_number DESC LIMIT 1").fetchone()
        return Block.from_row(row) if row else None

    def get_by_event(self, event_id: str) -> Optional[Block]:
        if self.init_error:
            raise sqlite3.DatabaseError(self.init_error)
        with closing(self._connect()) as c:
            row = c.execute(f"SELECT {_COLS} FROM ledger_blocks WHERE event_id = ?", (event_id,)).fetchone()
        return Block.from_row(row) if row else None

    def block_is_authentic(self, b: Block) -> bool:
        """Self-contained check of ONE block: hash recomputes + this node's signature verifies."""
        if b.compute_hash() != b.block_hash or b.node_id != self.node_id:
            return False
        try:
            return self._provider.verify(self.public_key, b.block_hash.encode(), bytes.fromhex(b.signature))
        except Exception:
            return False

    # ---- two-phase append ---------------------------------------------- #
    def prepare(self, event_id: str, document_hash: str, event_hash: str, timestamp: float) -> Block:
        """Build + sign the next block from THIS node's own data. Nothing is written."""
        blocks = self.read_all()
        if any(b.event_id == event_id for b in blocks):
            raise LedgerError(f"event {event_id} is already on the ledger")
        prev = blocks[-1].block_hash if blocks else GENESIS_HASH
        block = Block(
            block_number=len(blocks) + 1,
            event_id=event_id,
            document_hash=document_hash,
            event_hash=event_hash,
            previous_block_hash=prev,
            merkle_root=_merkle_root([b.event_hash for b in blocks] + [event_hash]),
            timestamp=timestamp,
            node_id=self.node_id,
        )
        block.block_hash = block.compute_hash()
        block.signature = self._provider.sign(self._priv, block.block_hash.encode()).hex()
        return block

    def commit(self, block: Block, confirmations: int) -> None:
        with closing(self._connect()) as c:
            c.execute(
                f"INSERT INTO ledger_blocks ({_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (block.block_number, block.event_id, block.document_hash, block.event_hash,
                 block.previous_block_hash, block.merkle_root, block.timestamp, block.block_hash,
                 block.signature, block.node_id, confirmations),
            )
            c.commit()

    # ---- full self-verification ---------------------------------------- #
    def verify_own(self) -> tuple[bool, str, Optional[list[Block]]]:
        """Re-read from disk; recompute every hash; verify every signature."""
        try:
            blocks = self.read_all()
        except sqlite3.DatabaseError as e:
            return False, f"UNREADABLE: {e}", None
        prev = GENESIS_HASH
        for i, b in enumerate(blocks, start=1):
            if b.block_number != i:
                return False, f"BLOCK_NUMBER_GAP@{i}", blocks
            if b.previous_block_hash != prev:
                return False, f"BROKEN_LINK@{i}", blocks
            if b.compute_hash() != b.block_hash:
                return False, f"HASH_MISMATCH@{i}", blocks
            if b.node_id != self.node_id:
                return False, f"NODE_ID_MISMATCH@{i}", blocks
            try:
                sig_ok = self._provider.verify(self.public_key, b.block_hash.encode(), bytes.fromhex(b.signature))
            except Exception:
                sig_ok = False
            if not sig_ok:
                return False, f"BAD_SIGNATURE@{i}", blocks
            prev = b.block_hash
        if blocks and blocks[-1].merkle_root != _merkle_root([b.event_hash for b in blocks]):
            return False, f"BAD_MERKLE@{len(blocks)}", blocks
        return True, "OK", blocks


class LedgerService:
    """Coordinates N independent node replicas (majority-quorum semantics)."""

    def __init__(self, node_count: int = 3, base_dir: Path | str | None = None, provider=None):
        if node_count < 1:
            raise ValueError("node_count must be >= 1")
        provider = provider or get_provider()
        base = Path(base_dir) if base_dir is not None else Path(_cfg.LEDGER_DIR)
        self.node_count = node_count
        self.quorum = node_count // 2 + 1
        self.nodes = [_NodeReplica(i + 1, base, provider) for i in range(node_count)]
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    def append_event(self, event_id: str, document_hash: str, event_hash: str) -> dict:
        with self._lock:
            ts = time.time()

            # --- 0. who is healthy and in sync? (cheap tip check, not a full verify) ----
            tips: dict[str, tuple[int, str]] = {}
            for n in self.nodes:
                try:
                    t = n.tip()
                    if t is not None and not n.block_is_authentic(t):
                        continue
                    tips[n.node_id] = (t.block_number, t.block_hash) if t else (0, GENESIS_HASH)
                except Exception as e:  # unreadable node -> skipped, others carry on
                    log.warning("%s skipped for append: %s", n.node_id, e)
            if not tips:
                raise LedgerError("no ledger node is available")
            tip_votes = Counter(tips.values())
            majority_tip, votes = tip_votes.most_common(1)[0]
            if votes < self.quorum:
                raise LedgerError(f"ledger nodes disagree on the chain tip; no quorum ({votes}/{self.node_count})")
            participants = [n for n in self.nodes if tips.get(n.node_id) == majority_tip]

            # --- 1. PREPARE: each node independently builds + signs the next block ------
            prepared: dict[str, Block] = {}
            for n in participants:
                try:
                    prepared[n.node_id] = n.prepare(event_id, document_hash, event_hash, ts)
                except LedgerError:
                    raise
                except Exception as e:
                    log.warning("%s failed to prepare block: %s", n.node_id, e)
            if not prepared:
                raise LedgerError("no ledger node could prepare the block")
            hash_votes = Counter(b.block_hash for b in prepared.values())
            agreed_hash, agree = hash_votes.most_common(1)[0]
            if agree < self.quorum:
                raise LedgerError(f"nodes computed different block hashes; no quorum ({agree}/{self.node_count})")

            # --- 2. COMMIT: only nodes whose independently computed hash matches --------
            committed: list[str] = []
            first: Optional[Block] = None
            for n in participants:
                b = prepared.get(n.node_id)
                if b is None or b.block_hash != agreed_hash:
                    continue
                try:
                    n.commit(b, confirmations=agree)
                    committed.append(n.node_id)
                    first = first or b
                except Exception as e:
                    log.error("%s failed to commit block %s: %s", n.node_id, b.block_number, e)
            if len(committed) < self.quorum or first is None:
                raise LedgerError(f"block committed on only {len(committed)}/{self.node_count} nodes (< quorum)")

            return {
                "block_number": first.block_number,
                "block_hash": first.block_hash,
                "previous_block_hash": first.previous_block_hash,
                "merkle_root": first.merkle_root,
                "confirmations": f"{len(committed)}/{self.node_count}",
                "status": "VERIFIED" if len(committed) == self.node_count else "PARTIAL",
                "nodes": {n.node_id: (n.node_id in committed) for n in self.nodes},
            }

    # ------------------------------------------------------------------ #
    def _collect(self) -> tuple[dict, list[dict]]:
        """Fresh verification straight from disk. Returns (verify_result, consensus_blocks)."""
        per_node: dict[str, tuple[bool, str, Optional[list[Block]]]] = {}
        for n in self.nodes:
            try:
                per_node[n.node_id] = n.verify_own()
            except Exception as e:  # e.g. key/DB vanished mid-run
                per_node[n.node_id] = (False, f"ERROR: {e}", None)

        # Only self-consistent chains get a vote on what the consensus chain is.
        voters = {nid: blocks for nid, (ok, _r, blocks) in per_node.items() if ok and blocks is not None}
        max_h = max((len(b) for b in voters.values()), default=0)
        consensus: list[tuple[str, int]] = []           # (block_hash, votes) per height
        for h in range(1, max_h + 1):
            votes = Counter(b[h - 1].block_hash for b in voters.values() if len(b) >= h)
            top_hash, top_n = votes.most_common(1)[0]
            if top_n < self.quorum:
                break
            consensus.append((top_hash, top_n))
        height = len(consensus)

        nodes_ok: dict[str, bool] = {}
        details: dict[str, str] = {}
        node_heights: dict[str, Optional[int]] = {}
        for n in self.nodes:
            ok, reason, blocks = per_node[n.node_id]
            node_heights[n.node_id] = len(blocks) if blocks is not None else None
            if not ok:
                nodes_ok[n.node_id], details[n.node_id] = False, reason
                continue
            assert blocks is not None
            div = next((i + 1 for i, b in enumerate(blocks)
                        if i >= height or b.block_hash != consensus[i][0]), None)
            if div is not None and div <= len(blocks):
                if div > height:
                    nodes_ok[n.node_id], details[n.node_id] = False, f"AHEAD_OF_CONSENSUS@{div}"
                else:
                    nodes_ok[n.node_id], details[n.node_id] = False, f"DIVERGES_FROM_MAJORITY@{div}"
            elif len(blocks) < height:
                nodes_ok[n.node_id], details[n.node_id] = False, f"BEHIND ({len(blocks)}/{height})"
            else:
                nodes_ok[n.node_id], details[n.node_id] = True, "OK"

        n_ok = sum(nodes_ok.values())
        result = {
            "status": "VERIFIED" if n_ok == self.node_count else "TAMPER_DETECTED",
            "nodes": nodes_ok,
            "height": height,
            "quorum_ok": n_ok >= self.quorum,
            "confirmations": f"{n_ok}/{self.node_count}",
            "details": details,
            "node_heights": node_heights,
        }

        blocks_out: list[dict] = []
        for h, (bh, votes) in enumerate(consensus, start=1):
            src = next(b[h - 1] for b in voters.values() if len(b) >= h and b[h - 1].block_hash == bh)
            d = src.as_dict()
            d["confirmations"] = f"{votes}/{self.node_count}"
            d["status"] = "VERIFIED" if votes == self.node_count else "PARTIAL"
            blocks_out.append(d)
        return result, blocks_out

    def verify_chain(self) -> dict:
        return self._collect()[0]

    def snapshot(self) -> dict:
        """verify_chain() result plus the consensus block list, from ONE fresh disk read."""
        result, blocks = self._collect()
        return {"verify": result, "blocks": blocks}

    def list_blocks(self) -> list[dict]:
        return self._collect()[1]

    # ------------------------------------------------------------------ #
    def get_block_for_event(self, event_id: str) -> Optional[dict]:
        """The block for ``event_id`` ONLY if >= quorum nodes independently hold the same,
        individually-authentic (hash recomputes + node signature verifies) block."""
        found: dict[str, list[Block]] = {}
        for n in self.nodes:
            try:
                b = n.get_by_event(event_id)
            except Exception:
                continue
            if b is not None and n.block_is_authentic(b):
                found.setdefault(b.block_hash, []).append(b)
        if not found:
            return None
        _hash, group = max(found.items(), key=lambda kv: len(kv[1]))
        if len(group) < self.quorum:
            return None
        out = group[0].as_dict()
        out["nodes_agreeing"] = len(group)
        out["nodes_total"] = self.node_count
        return out
