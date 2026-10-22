"""SB-2a: the provenance graph, computed on read for local navigation (ADR-0005 §8.1).

Derived, never stored. Built only from links Sovereign already holds canonically:

- SUPPORTED_BY: claim -> record, from `claim_sources`, only where the link verifies: its pinned evidence hash matches
  the record and the record is in a verified state (`claims.VERIFIED_STATES`), so the record is the evidence the
  claim was made from;
- CORRECTS:     record revision -> the revision it corrects, from `records.supersedes_id`;
- SUPERSEDES:   claim -> the claim it replaced, from `claims.supersedes_id`.

Identity is typed throughout (PR #11 audit F-6). Record ids and claim ids are separate namespaces and may coincide,
so every lookup, node, edge endpoint and API path is a (kind, id) pair.

Eligibility comes before capacity (F-5). An endpoint becomes a node only if it is eligible:

- present;
- not forgotten (no tombstone);
- in a recognised state;
- for evidence, linked by a verified link.

Each query applies these conditions before anything is counted. So an absent, forgotten or ineligible endpoint never
becomes a node or an edge, never uses capacity, never sets `truncated` and never appears in any field. `truncated`
means exactly this: an eligible neighbour of an expanded item was left out by the node limit or the byte limit.
The claim's own `support` already says when its evidence is missing or unverified.

Bounded (F-7):

- each neighbour query is index-ordered by id and LIMITed to the remaining capacity plus one;
- text is an excerpt except for the focus;
- only the focus claim carries decision history: its most recent HISTORY_LIMIT events, while the stored
  append-only history is never limited;
- the serialised response never exceeds MAX_RESPONSE_BYTES;
- a read that would exceed WORK_LIMIT ticks of SQLite work fails closed with ProvenanceTooLarge and returns
  nothing partial.

The whole graph is read in one transaction, so it reflects a single snapshot. Status, support and authority are
derived live in that snapshot by the store's own derivation (`Vault._claim`), never read from a copy.

Navigation is not relevance (ADR-0004 decision 3, ADR-0005 R3). The Context Compiler never imports this module, and
nothing here writes, persists or influences a context bundle or disclosure.
"""
from __future__ import annotations

import json
import sqlite3

from . import claims as rules
from .store import MAX_CONTENT, evidence_hash

KINDS = ("claim", "record")
MAX_HOPS = 2          # a selected item plus at most two links outward; never the whole vault
MAX_NODES = 60        # hard bound per response; `truncated` says when an eligible item was left out
HISTORY_LIMIT = 50    # most recent decisions shown for the focus claim; the stored history is never limited
EXCERPT = 400         # characters of text shown for every item except the focus
TIME_CHARS = 64       # timestamps are display-only here; an anomalous legacy value is clipped
MAX_RESPONSE_BYTES = 256 * 1024   # the graph as JSONResponse serialises it, never more
WORK_TICK = 1000      # SQLite VM instructions per progress tick
WORK_LIMIT = 5000     # ticks per read; beyond it the read is interrupted and fails closed

_RECORD_STATES = tuple(sorted(rules.VERIFIED_STATES))
_CLAIM_STATES = tuple(rules.STATUSES)


def _marks(n: int) -> str:
    return "(" + ",".join("?" * n) + ")"


_RECORD_OK = f"r.status IN {_marks(len(_RECORD_STATES))} AND NOT EXISTS (SELECT 1 FROM tombstones t WHERE t.id = r.id)"
_CLAIM_OK = (f"c.status IN {_marks(len(_CLAIM_STATES))} "
             "AND NOT EXISTS (SELECT 1 FROM claim_tombstones t WHERE t.id = c.id)")


class ProvenanceTooLarge(RuntimeError):
    """The neighbourhood cannot be computed within the work or size bound; nothing partial is returned."""


class _Work:
    """SQLite work done by one read, in ticks of WORK_TICK VM instructions."""

    def __init__(self):
        self.ticks = 0

    def tick(self) -> int:
        self.ticks += 1
        return 1 if self.ticks > WORK_LIMIT else 0


def neighborhood(vault, kind: str, item_id: str, hops: int = 1, max_nodes: int = MAX_NODES) -> dict | None:
    """The provenance neighbourhood of one record or claim, or None if no eligible item of that kind has that id."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}.")
    if not 1 <= hops <= MAX_HOPS:
        raise ValueError(f"hops must be between 1 and {MAX_HOPS}.")
    if not 1 <= max_nodes <= MAX_NODES:
        raise ValueError(f"max_nodes must be between 1 and {MAX_NODES}.")
    with vault.connection() as db:   # one read transaction: a single consistent snapshot
        work = _Work()
        db.set_progress_handler(work.tick, WORK_TICK)
        try:
            return _Graph(db, vault, hops, max_nodes).build(kind, item_id)
        except sqlite3.OperationalError:
            if work.ticks > WORK_LIMIT:
                raise ProvenanceTooLarge("This item's links cannot be shown within the provenance work limit.") from None
            raise
        finally:
            db.set_progress_handler(None, WORK_TICK)


def _size(value) -> int:
    """Bytes as FastAPI's JSONResponse renders the value."""
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))


class _Graph:
    def __init__(self, db, vault, hops, max_nodes):
        self.db, self.vault, self.hops, self.max_nodes = db, vault, hops, max_nodes
        self.items: dict[tuple[str, str], dict] = {}     # admitted (kind, id) -> item, in admission order
        self.layer: dict[tuple[str, str], int] = {}
        self.nodes: dict[tuple[str, str], dict] = {}
        self.edges: list[dict] = []
        self.pending: dict[tuple[str, str], list] = {}   # target not yet admitted -> links from admitted items
        self.truncated = False
        self.used = 0

    # --- loading: eligibility is part of every query ---------------------------------------------

    def _load(self, kind, ident, focus=False):
        if kind == "record":
            row = self.db.execute(f"SELECT * FROM records r WHERE r.id = ? AND {_RECORD_OK}",
                                  (ident, *_RECORD_STATES)).fetchone()
            return dict(row) if row else None
        row = self.db.execute(f"SELECT * FROM claims c WHERE c.id = ? AND {_CLAIM_OK}", (ident, *_CLAIM_STATES)).fetchone()
        if row is None:
            return None
        return self.vault._claim(self.db, row, history_limit=HISTORY_LIMIT if focus else 0)

    def _eligible(self, kind, ident) -> bool:
        if kind == "record":
            sql, states = f"SELECT 1 FROM records r WHERE r.id = ? AND {_RECORD_OK}", _RECORD_STATES
        else:
            sql, states = f"SELECT 1 FROM claims c WHERE c.id = ? AND {_CLAIM_OK}", _CLAIM_STATES
        return self.db.execute(sql, (ident, *states)).fetchone() is not None

    @staticmethod
    def _out(kind, item):
        """Links stored on the item itself, as (type, target, evidence state): at most MAX_SOURCES + 1."""
        if kind == "claim":
            for source in item["sources"]:
                if source["state"] in rules.VERIFIED_STATES:     # the evidence the claim was made from
                    yield "SUPPORTED_BY", ("record", source["id"]), source["state"]
            if item["supersedes_id"] is not None:
                yield "SUPERSEDES", ("claim", item["supersedes_id"]), None
        elif item["supersedes_id"] is not None:
            yield "CORRECTS", ("record", item["supersedes_id"]), None

    def _incoming(self, kind, item, limit):
        """Eligible items linking to this one that are not admitted yet: at most `limit` per link type, in id order."""
        admitted = {k: [i for (kk, i) in self.items if kk == k] for k in KINDS}
        if kind == "claim":
            sql = (f"SELECT c.id FROM claims c INDEXED BY ix_claims_supersedes WHERE c.supersedes_id = ? AND {_CLAIM_OK} "
                   f"AND c.id NOT IN {_marks(len(admitted['claim']))} ORDER BY c.id LIMIT ?")
            return [("claim", i) for (i,) in self.db.execute(
                sql, (item["id"], *_CLAIM_STATES, *admitted["claim"], limit))]
        citing = (f"SELECT s.claim_id FROM claim_sources s INDEXED BY ix_claim_sources_record CROSS JOIN claims c "
                  f"ON c.id = s.claim_id WHERE s.record_id = ? AND s.evidence_sha256 = ? AND {_CLAIM_OK} "
                  f"AND s.claim_id NOT IN {_marks(len(admitted['claim']))} ORDER BY s.claim_id LIMIT ?")
        correcting = (f"SELECT r.id FROM records r INDEXED BY ix_records_supersedes WHERE r.supersedes_id = ? "
                      f"AND {_RECORD_OK} AND r.id NOT IN {_marks(len(admitted['record']))} ORDER BY r.id LIMIT ?")
        return ([("claim", i) for (i,) in self.db.execute(
                    citing, (item["id"], evidence_hash(item), *_CLAIM_STATES, *admitted["claim"], limit))]
                + [("record", i) for (i,) in self.db.execute(
                    correcting, (item["id"], *_RECORD_STATES, *admitted["record"], limit))])

    # --- admission: one node and the edges it completes, within the node and byte limits -----------

    def _node(self, k, item, focus):
        kind = k[0]
        text = item["content"] if kind == "record" else item["text"]
        limit = (MAX_CONTENT if kind == "record" else rules.MAX_TEXT) if focus else EXCERPT
        out = {"kind": kind, "id": item["id"], "text": text[:limit], "text_truncated": len(text) > limit,
               "status": item["status"], "created_at": item["created_at"][:TIME_CHARS]}
        if kind == "record":
            out["sensitivity"] = item["sensitivity"]
        else:
            out.update(support=item["support"], authoritative=item["authoritative"], origin=item["origin"])
            if focus:
                out["history"] = [{**e, "note": None if e["note"] is None else e["note"][:rules.MAX_NOTE],
                                   "at": e["at"][:TIME_CHARS]} for e in item["history"]]
                out["history_complete"] = item["history_complete"]
        return out

    def _drawn(self, a, b) -> bool:
        """A link is drawn when at least one end was expanded: the neighbourhood is the expanded items' links."""
        return self.layer[a] < self.hops or self.layer[b] < self.hops

    def _admit(self, k, item, layer, focus=False) -> bool:
        """Admit one item with the edges it completes, unless that would exceed the byte limit."""
        self.layer[k] = layer
        node = self._node(k, item, focus)
        links = [(t, k, target, state) for t, target, state in self._out(k[0], item)]
        completed = [link for link in links if link[2] in self.items]
        completed += [(t, source, k, state) for t, source, state in self.pending.get(k, ())]
        edges = [{"type": t, "from": {"kind": a[0], "id": a[1]}, "to": {"kind": b[0], "id": b[1]},
                  **({"evidence_state": state} if t == "SUPPORTED_BY" else {})}
                 for t, a, b, state in completed if self._drawn(a, b)]
        cost = _size(node) + 1 + sum(_size(e) + 1 for e in edges)
        if not focus and self.used + cost > MAX_RESPONSE_BYTES:
            del self.layer[k]
            return False
        self.used += cost
        self.items[k], self.nodes[k] = item, node
        self.edges.extend(edges)
        self.pending.pop(k, None)
        for t, _, target, state in links:
            if target not in self.items:
                self.pending.setdefault(target, []).append((t, k, state))
        return True

    def build(self, kind, item_id):
        focus = self._load(kind, item_id, focus=True)
        if focus is None:
            return None
        key = (kind, item_id)
        skeleton = {"focus": {"kind": kind, "id": item_id}, "hops": self.hops, "truncated": False, "nodes": [], "edges": []}
        self.used = _size(skeleton)
        self._admit(key, focus, 0, focus=True)
        if self.used > MAX_RESPONSE_BYTES:
            raise ProvenanceTooLarge("This item cannot be shown within the provenance size limit.")
        frontier, full = [key], False
        for layer in range(self.hops):
            following = []
            for k in frontier:
                if full or (self.truncated and len(self.items) >= self.max_nodes):
                    break                  # nothing more can be admitted, so no node or edge can change
                remaining = self.max_nodes - len(self.items)
                incoming = self._incoming(k[0], self.items[k], remaining + 1)
                outgoing = [target for _, target, _ in self._out(k[0], self.items[k])
                            if target not in self.items and self._eligible(*target)]
                for c in sorted(set(incoming) | set(outgoing)):
                    if len(self.items) >= self.max_nodes:
                        self.truncated = True          # an eligible neighbour is left out by the node limit
                        break
                    if not self._admit(c, self._load(*c), layer + 1):
                        self.truncated = full = True   # ... or by the byte limit
                        break
                    following.append(c)
            frontier = following
        return {**skeleton, "truncated": self.truncated,
                "nodes": [self.nodes[k] for k in sorted(self.nodes)],
                "edges": sorted(self.edges, key=lambda e: (e["type"], e["from"]["kind"], e["from"]["id"],
                                                           e["to"]["kind"], e["to"]["id"]))}
