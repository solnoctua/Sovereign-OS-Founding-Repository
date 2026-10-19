"""Reproductions of the 708e9de audit findings (blocker groups 1-7), kept as permanent regressions.

Each probe attacks one invariant using only the Vault API and raw SQL, and returns None if the
invariant held or a description of how it broke. 26 of these 27 probes fail against 708e9de.
"""
import sqlite3
import threading
import time

import pytest
from sovereign.store import Vault

T = "2026-10-19T00:00:00+00:00"
PROBES = {}


def probe(name):
    def register(fn):
        PROBES[name] = fn
        return fn
    return register


@pytest.fixture
def fresh(tmp_path):
    counter = iter(range(1_000_000))
    return lambda: Vault(str(tmp_path / f"vault{next(counter)}.db"))


def raw(v, fk=True):
    db = sqlite3.connect(v.path, isolation_level=None)
    db.execute(f"PRAGMA foreign_keys={'ON' if fk else 'OFF'}")
    return db


def by_id(v, cid):
    return {c["id"]: c for c in v.list_claims(limit=200)}.get(cid)


def try_sql(db, sql, args=()):
    try:
        db.execute(sql, args)
        return True
    except sqlite3.Error:
        return False


def approved_claim(v, text="Invented claim"):
    rec = v.add("Invented note")
    c = v.add_claim(text, [rec["id"]], "human")
    v.transition_claim(c["id"], "approved")
    return rec, by_id(v, c["id"])


def corrected_scenario(fresh):
    v = fresh()
    rec, c = approved_claim(v)
    old = v.export()
    v.add("Invented note corrected", supersedes_id=rec["id"])
    return rec, c, old, v.export()


# --- 1. SQL replacement ------------------------------------------------------------------------

for _fk in (True, False):
    @probe(f"1a replace approved claim (fk={_fk})")
    def _(fresh, fk=_fk):
        v = fresh(); rec, c = approved_claim(v); db = raw(v, fk)
        try_sql(db, "INSERT OR REPLACE INTO claims(id,text,origin,status,created_at) VALUES (?,?,?,?,?)",
                (c["id"], "Rewritten", "human", "proposed", T))
        now = by_id(v, c["id"])
        if now is None:
            return "approved claim erased"
        if (now["text"], now["status"], now["history"]) != (c["text"], c["status"], c["history"]):
            return f"claim rewritten: {now['status']} {now['text']!r} history={len(now['history'])}"

    @probe(f"1b replace approval event (fk={_fk})")
    def _(fresh, fk=_fk):
        v = fresh(); rec, c = approved_claim(v); db = raw(v, fk)
        seq = db.execute("SELECT seq FROM claim_events WHERE claim_id=? AND to_status='approved'", (c["id"],)).fetchone()[0]
        try_sql(db, "INSERT OR REPLACE INTO claim_events(seq,claim_id,from_status,to_status,actor,at) VALUES (?,?,?,?,?,?)",
                (seq, c["id"], "approved", "contested", "human", T))
        if by_id(v, c["id"])["history"] != c["history"]:
            return "history rewritten"


@probe("1c recreate rejected claim id")
def _(fresh):
    v = fresh(); rec = v.add("Invented note"); c = v.add_claim("x", [rec["id"]], "model")
    v.transition_claim(c["id"], "rejected"); db = raw(v, False)
    try_sql(db, "REPLACE INTO claims(id,text,origin,status,created_at) VALUES (?,?,?,?,?)", (c["id"], "Back", "human", "proposed", T))
    now = by_id(v, c["id"])
    if now["status"] != "rejected" or now["text"] != "x":
        return f"rejected claim recreated as {now['status']}"


@probe("1d replace claim tombstone")
def _(fresh):
    v = fresh(); rec = v.add("n"); c = v.add_claim("x", [rec["id"]], "human"); v.delete_claim(c["id"]); db = raw(v)
    before = db.execute("SELECT deleted_at FROM claim_tombstones").fetchall()
    try_sql(db, "INSERT OR REPLACE INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (c["id"], "forged"))
    if db.execute("SELECT deleted_at FROM claim_tombstones").fetchall() != before:
        return "tombstone rewritten"


# --- 2. Source replacement ---------------------------------------------------------------------

@probe("2a replace superseded evidence as active")
def _(fresh):
    v = fresh(); rec, c = approved_claim(v); v.add("Invented note v2", supersedes_id=rec["id"]); db = raw(v)
    r = db.execute("SELECT id,content,source,sensitivity,created_at,supersedes_id FROM records WHERE id=?", (rec["id"],)).fetchone()
    try_sql(db, "INSERT OR REPLACE INTO records(id,content,source,sensitivity,status,created_at,supersedes_id) VALUES (?,?,?,?,?,?,?)",
            (r[0], r[1], r[2], r[3], "active", r[4], r[5]))
    if by_id(v, c["id"])["authoritative"]:
        return "stale claim authoritative again"


@probe("2b replace sensitive evidence as private")
def _(fresh):
    v = fresh(); rec = v.add("Invented secret", "sensitive"); db = raw(v)
    try_sql(db, "INSERT OR REPLACE INTO records(id,content,source,sensitivity,status,created_at) VALUES (?,?,?,?,?,?)",
            (rec["id"], rec["content"], "manual", "private", "active", rec["created_at"]))
    if v.get(rec["id"])["sensitivity"] != "sensitive":
        return "sensitive record now private (cloud-disclosable)"


@probe("2c delete+insert evidence with new sensitivity")
def _(fresh):
    v = fresh(); rec = v.add("Invented secret", "sensitive"); db = raw(v)
    try_sql(db, "DELETE FROM records WHERE id=?", (rec["id"],))
    try_sql(db, "INSERT INTO records(id,content,source,sensitivity,status,created_at) VALUES (?,?,?,?,?,?)",
            (rec["id"], rec["content"], "manual", "private", "active", rec["created_at"]))
    got = v.get(rec["id"])
    if got and got["sensitivity"] != "sensitive":
        return "sensitivity rewritten via delete+insert"


@probe("2d reintroduce evidence for orphaned approved claim")
def _(fresh):
    v = fresh(); rec, c = approved_claim(v); snap = v.export()
    w = fresh(); w.restore_trusted({**snap, "records": []}); db = raw(w)
    try_sql(db, "INSERT INTO records(id,content,source,sensitivity,status,created_at) VALUES (?,?,?,?,?,?)",
            (rec["id"], rec["content"], "manual", "private", "active", rec["created_at"]))
    if by_id(w, c["id"])["authoritative"]:
        return "orphaned claim authoritative via reintroduced evidence"


# --- 3. Raw deletion / tombstones --------------------------------------------------------------

@probe("3a raw DELETE of source keeps derived claim")
def _(fresh):
    v = fresh(); rec, c = approved_claim(v, "Derived secret text"); db = raw(v)
    try_sql(db, "DELETE FROM records WHERE id=?", (rec["id"],))
    if v.get(rec["id"]) is None and by_id(v, c["id"]) is not None:
        return "source gone but derived claim text survives"


@probe("3b raw tombstone insert half-forgets")
def _(fresh):
    v = fresh(); rec, c = approved_claim(v, "Derived secret text"); db = raw(v)
    try_sql(db, "INSERT INTO tombstones(id,deleted_at) VALUES (?,?)", (rec["id"], T))
    if db.execute("SELECT 1 FROM tombstones WHERE id=?", (rec["id"],)).fetchone() and (v.get(rec["id"]) or by_id(v, c["id"])):
        return "tombstone written but record/claim still live"


@probe("3c raw-deleted source: export/restore keeps derived text")
def _(fresh):
    v = fresh(); rec, c = approved_claim(v, "Derived secret text"); db = raw(v)
    deleted = try_sql(db, "DELETE FROM records WHERE id=?", (rec["id"],))
    w = fresh(); w.restore_trusted(v.export())
    if deleted and "Derived secret text" in str(w.export()):
        return "derived text of deleted source restored"


@probe("3d raw tombstone forget: export/restore/replay keeps nothing")
def _(fresh):
    v = fresh(); rec, c = approved_claim(v, "Derived secret text"); old = v.export(); db = raw(v, fk=False)
    try_sql(db, "INSERT INTO tombstones(id,deleted_at) VALUES (?,?)", (rec["id"], T))
    w = fresh(); w.restore_trusted(v.export()); v.restore_trusted(old); v.import_untrusted(old)
    for vault in (v, w):
        if "Derived secret text" in str(vault.export()) or "Invented note" in str(vault.export()["records"]):
            return "forgotten source or derived text came back"


# --- 4. Partial restore + ordinary import ------------------------------------------------------

@probe("4a partial restore then ordinary import of old snapshot")
def _(fresh):
    rec, c, old, new = corrected_scenario(fresh); w = fresh(); w.restore_trusted({**new, "records": []})
    w.import_untrusted(old)
    if by_id(w, c["id"])["authoritative"]:
        return "corrected claim authoritative again after import"


@probe("4b restore successor only, import old predecessor")
def _(fresh):
    rec, c, old, new = corrected_scenario(fresh); w = fresh()
    w.restore_trusted({**new, "records": [r for r in new["records"] if r["id"] != rec["id"]]})
    w.import_untrusted(old)
    if by_id(w, c["id"])["authoritative"]:
        return "corrected claim authoritative again"
    if w.get(rec["id"]) is not None:
        return "obsolete evidence re-entered as active"


@probe("4c partial restore then trusted restore of old snapshot")
def _(fresh):
    rec, c, old, new = corrected_scenario(fresh); w = fresh(); w.restore_trusted({**new, "records": []})
    w.restore_trusted(old)
    if by_id(w, c["id"])["authoritative"]:
        return "corrected claim authoritative again after mixed restores"


# --- 5. Export under concurrency ---------------------------------------------------------------

def race_exports(fresh, ops, rounds=40, min_exports=5, max_rounds=1000):
    """Export continuously while `ops` writes; the overlap is made deterministic (see audit2's
    `_race_exports`): the reader opens before the race and writes continue until at least
    `min_exports` exports completed during them."""
    v = fresh(); step = ops(v); exports, lock_timeouts, stop = [], [], threading.Event()
    reader = Vault(v.path)

    def exporter():
        while not stop.is_set():
            try:
                exports.append(reader.export())
            except sqlite3.OperationalError as exc:
                lock_timeouts.append(exc)

    thread = threading.Thread(target=exporter); thread.start()
    try:
        i = 0
        while i < rounds or (len(exports) < min_exports and i < max_rounds):
            step(i)
            time.sleep(0.003 if len(exports) >= min_exports else 0.02)   # paced writes, wider gap until the reader gets in
            i += 1
    finally:
        stop.set(); thread.join()
    if lock_timeouts or len(exports) < min_exports:
        return f"exporter starved ({len(lock_timeouts)} lock timeouts, {len(exports)} exports over {i} rounds)"
    bad = 0
    for e in exports[::max(1, len(exports) // 40)]:
        try:
            fresh().restore_trusted(e)
        except Exception:
            bad += 1
    if bad:
        return f"{bad} sampled exports not restorable"


def ops_decisions(v):
    rec = v.add("Invented note")

    def step(i):
        c = v.add_claim(f"c{i}", [rec["id"]], "human")
        v.transition_claim(c["id"], "approved"); v.transition_claim(c["id"], "contested")
        new = v.supersede_claim(c["id"], f"c{i}b", [rec["id"]])["replacement"]
        v.transition_claim(new["id"], "rejected")
    return step


def ops_forget_correct(v):
    def step(i):
        r = v.add(f"note {i}"); c = v.add_claim(f"claim {i}", [r["id"]], "human"); v.transition_claim(c["id"], "approved")
        r2 = v.add(f"note {i} v2", supersedes_id=r["id"]); v.add_claim(f"claim {i} v2", [r2["id"]], "human")
        if i % 2:
            v.delete(r2["id"])
    return step


for _name, _ops in (("decisions/supersede", ops_decisions), ("forget/correct", ops_forget_correct)):
    @probe(f"5 concurrent export vs {_name}")
    def _(fresh, ops=_ops):
        return race_exports(fresh, ops)


# --- 6. Supersession graphs --------------------------------------------------------------------

@probe("6a claim supersedes itself (raw)")
def _(fresh):
    v = fresh(); v.add("n"); db = raw(v)
    if try_sql(db, "INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES ('s','t','human','proposed',?, 's')", (T,)):
        return "self-superseding claim inserted"


@probe("6b two replacements for one claim (raw)")
def _(fresh):
    v = fresh(); rec = v.add("n"); c = v.add_claim("x", [rec["id"]], "human")
    v.supersede_claim(c["id"], "y", [rec["id"]]); db = raw(v)
    if try_sql(db, "INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES ('second','z','human','proposed',?,?)", (T, c["id"])):
        return "second replacement inserted"


@probe("6c restore payload with claim supersession cycle")
def _(fresh):
    v = fresh(); rec = v.add("n"); v.add_claim("a", [rec["id"]], "human"); v.add_claim("b", [rec["id"]], "human")
    snap = v.export(); x, y = snap["claims"]
    x["supersedes_id"], y["supersedes_id"] = y["id"], x["id"]
    try:
        fresh().restore_trusted(snap)
    except Exception:
        return None
    return "cyclic claim lineage accepted"


@probe("6d record supersedes itself (raw)")
def _(fresh):
    v = fresh(); db = raw(v)
    if try_sql(db, "INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES ('r','c','private','active',?,'r')", (T,)):
        return "self-superseding record inserted"


@probe("6e two successors for one record (raw)")
def _(fresh):
    v = fresh(); r = v.add("n"); v.add("n2", supersedes_id=r["id"]); db = raw(v)
    if try_sql(db, "INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES ('fork','c','private','active',?,?)", (T, r["id"])):
        return "second successor inserted"


def _payload(rows):
    return {"schema": "sovereign.v0.records.2", "records": rows, "tombstones": []}


def _row(id, status, supersedes):
    return {"id": id, "content": f"Invented {id}", "source": "manual", "sensitivity": "private",
            "status": status, "created_at": T, "supersedes_id": supersedes}


@probe("6f import payload with record supersession cycle")
def _(fresh):
    try:
        fresh().import_untrusted(_payload([_row("p", "superseded", "q"), _row("q", "superseded", "p")]))
    except Exception:
        return None
    return "cyclic record lineage imported"


@probe("6g active predecessor with successor (import)")
def _(fresh):
    w = fresh()
    try:
        w.import_untrusted(_payload([_row("p", "active", None), _row("q", "active", "p")]))
    except Exception:
        return None
    if len([r for r in w.search() if r["id"] in ("p", "q")]) == 2:
        return "two active revisions in one lineage"


# --- 7. Long histories -------------------------------------------------------------------------

@probe("7 claim with >100 legitimate events restores")
def _(fresh):
    v = fresh(); rec = v.add("n"); c = v.add_claim("x", [rec["id"]], "human"); v.transition_claim(c["id"], "approved")
    for _ in range(60):
        v.transition_claim(c["id"], "contested"); v.transition_claim(c["id"], "approved")
    try:
        fresh().restore_trusted(v.export())
    except Exception as e:
        return f"export not restorable: {e}"


# Defined last, so every probe above is registered before parametrisation.
@pytest.mark.parametrize("name", list(PROBES))
def test_blocker_probe(name, fresh):
    assert PROBES[name](fresh) is None
