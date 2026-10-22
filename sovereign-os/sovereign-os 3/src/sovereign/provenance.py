"""SB-2a: the provenance graph, computed on read for local navigation (ADR-0005 §8.1).

Derived, never stored. Built only from links Sovereign already holds canonically:

- SUPPORTED_BY: claim -> record, from `claim_sources` (with the evidence state the claim's pinned hash yields);
- CORRECTS:     record revision -> the revision it corrects, from `records.supersedes_id`;
- SUPERSEDES:   claim -> the claim it replaced, from `claims.supersedes_id`.

Status, support and authority are read live from the same snapshot by the store's own derivation
(`Vault._claim`), never from a copy. Edges join only items present in the vault: a forgotten item is
absent from every table, so it can contribute no node, edge, title or count, and a link pointing at
an absent item is simply not drawn (a claim's `support` already says when its evidence is missing).

Navigation is not relevance (ADR-0004 decision 3, ADR-0005 R3): the Context Compiler never imports
this module, and nothing here writes, persists or influences a context bundle or disclosure.
"""
from __future__ import annotations

MAX_HOPS = 2      # a selected item plus at most two links outward; never the whole vault
MAX_NODES = 60    # hard bound per response; `truncated` says when it was reached


def neighborhood(vault, item_id: str, hops: int = 1, max_nodes: int = MAX_NODES) -> dict | None:
    """The provenance neighborhood of one record or claim, or None if no such item is present."""
    if not 1 <= hops <= MAX_HOPS:
        raise ValueError(f"hops must be between 1 and {MAX_HOPS}.")
    with vault.connection() as db:   # one read transaction: a single consistent snapshot
        def record(rid):
            row = db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
            return dict(row) if row else None

        def claim(cid):
            row = db.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
            return vault._claim(db, row) if row else None   # the store's own live derivation

        def resolve(kind, ident):
            return record(ident) if kind == "record" else claim(ident)

        focus_kind = "record" if record(item_id) else "claim" if claim(item_id) else None
        if focus_kind is None:
            return None

        nodes: dict[tuple[str, str], dict] = {}
        edges: set[tuple[str, str, str, str]] = set()
        truncated = False
        frontier = [(focus_kind, item_id)]
        nodes[(focus_kind, item_id)] = resolve(focus_kind, item_id)
        for _ in range(hops):
            following = []
            for kind, ident in frontier:
                for edge, (other_kind, other_id) in _links(db, kind, ident, nodes[(kind, ident)]):
                    if (other_kind, other_id) not in nodes:
                        if len(nodes) >= max_nodes:
                            truncated = True
                            continue
                        item = resolve(other_kind, other_id)
                        if item is None:        # absent (forgotten or never present): no node, no edge
                            continue
                        nodes[(other_kind, other_id)] = item
                        following.append((other_kind, other_id))
                    edges.add(edge)
            frontier = following
        return {"focus": {"kind": focus_kind, "id": item_id}, "hops": hops, "truncated": truncated,
                "nodes": [_node(kind, item) for (kind, _), item in sorted(nodes.items())],
                "edges": [_edge(e, nodes) for e in sorted(edges)]}


def _links(db, kind, ident, item):
    """Every stored link touching one item, as (edge, other endpoint). Edges are (type, from, to, kind_from)."""
    if kind == "claim":
        for rid in item["source_ids"]:
            yield ("SUPPORTED_BY", ident, rid, "claim"), ("record", rid)
        if item["supersedes_id"]:
            yield ("SUPERSEDES", ident, item["supersedes_id"], "claim"), ("claim", item["supersedes_id"])
        for (successor,) in db.execute("SELECT id FROM claims WHERE supersedes_id=?", (ident,)):
            yield ("SUPERSEDES", successor, ident, "claim"), ("claim", successor)
    else:
        for (cid,) in db.execute("SELECT claim_id FROM claim_sources WHERE record_id=?", (ident,)):
            yield ("SUPPORTED_BY", cid, ident, "claim"), ("claim", cid)
        if item["supersedes_id"]:
            yield ("CORRECTS", ident, item["supersedes_id"], "record"), ("record", item["supersedes_id"])
        for (successor,) in db.execute("SELECT id FROM records WHERE supersedes_id=?", (ident,)):
            yield ("CORRECTS", successor, ident, "record"), ("record", successor)


def _node(kind: str, item: dict) -> dict:
    if kind == "record":
        return {"kind": "record", "id": item["id"], "text": item["content"], "status": item["status"],
                "sensitivity": item["sensitivity"], "created_at": item["created_at"]}
    return {"kind": "claim", "id": item["id"], "text": item["text"], "status": item["status"],
            "support": item["support"], "authoritative": item["authoritative"], "origin": item["origin"],
            "created_at": item["created_at"], "history": item["history"]}


def _edge(edge: tuple, nodes: dict) -> dict:
    kind, source, target, _ = edge
    out = {"type": kind, "from": source, "to": target}
    if kind == "SUPPORTED_BY":
        claim = nodes.get(("claim", source))
        state = next((s["state"] for s in claim["sources"] if s["id"] == target), None) if claim else None
        out["evidence_state"] = state   # active | superseded | unverified (pinned hash differs)
    return out
