"""Regression suite for the second audit of MemoryClaim (candidate 708e9de).

Invariant under test: once Sovereign records an epistemic decision, no lower-level storage,
import, deletion, replacement, restore or concurrency operation may silently change its meaning
or authority. Blockers: (1) SQL replacement, (2) source replacement, (3) Forget bypass,
(4) piecemeal authority via partial import/restore, (5) export snapshots under concurrency,
(6) supersession graphs, (7) history/size limits.
"""
import json
import os
import random
import sqlite3
import threading
import time

from fastapi.testclient import TestClient
import pytest
from sovereign import providers, store
from sovereign.app import create_app
from sovereign.claims import TransitionError
from sovereign.store import Vault, evidence_hash

T = "2026-10-19T00:00:00+00:00"
RANK = {"orphaned": 0, "stale": 1, "supported": 2}


@pytest.fixture
def vault(tmp_path):
    return Vault(str(tmp_path / "vault.db"))


@pytest.fixture(params=[(True, False), (False, False), (True, True), (False, True)],
                ids=["fk_on", "fk_off", "fk_on_recursive", "fk_off_recursive"])
def raw_mode(request):
    return request.param


def raw(v, mode=(True, False)):
    """An attacker's direct connection to the vault file, in any pragma configuration."""
    fk, recursive = mode
    db = sqlite3.connect(v.path, isolation_level=None)
    db.execute(f"PRAGMA foreign_keys={'ON' if fk else 'OFF'}")
    db.execute(f"PRAGMA recursive_triggers={'ON' if recursive else 'OFF'}")
    return db


def claims_of(v):
    return {c["id"]: c for c in v.list_claims(limit=200)}


def fresh_like(v, name):
    return Vault(os.path.join(os.path.dirname(v.path), name))


def strip(export):
    return {k: export[k] for k in ("records", "tombstones", "claims", "claim_tombstones")}


def assert_coherent(v, round_trip=True):
    """Structural invariants of a vault, checked directly in SQL, plus export/restore round trip."""
    db = sqlite3.connect(v.path)
    q = lambda sql: db.execute(sql).fetchall()
    try:
        assert q("""SELECT c.id FROM claims c WHERE c.status IS NOT COALESCE(
                    (SELECT to_status FROM claim_events e WHERE e.claim_id=c.id ORDER BY seq DESC LIMIT 1), 'proposed')""") == []
        assert q("SELECT id FROM records WHERE id IN (SELECT id FROM tombstones)") == []
        assert q("SELECT id FROM claims WHERE id IN (SELECT id FROM claim_tombstones)") == []
        assert q("SELECT claim_id FROM claim_sources WHERE record_id IN (SELECT id FROM tombstones)") == []
        assert q("SELECT claim_id FROM claim_sources WHERE claim_id NOT IN (SELECT id FROM claims)") == []
        assert q("SELECT claim_id FROM claim_events WHERE claim_id NOT IN (SELECT id FROM claims)") == []
        for table in ("records", "claims"):
            assert q(f"SELECT supersedes_id FROM {table} WHERE supersedes_id IS NOT NULL GROUP BY supersedes_id HAVING count(*)>1") == []
            assert q(f"""SELECT p.id FROM {table} p JOIN {table} s ON s.supersedes_id=p.id WHERE p.status <> 'superseded'""") == []
            assert q(f"SELECT id FROM {table} WHERE supersedes_id = id") == []
    finally:
        db.close()
    if round_trip:
        exported = v.export()
        copy = fresh_like(v, f"roundtrip-{random.random()}.db")
        copy.restore_trusted(exported)
        assert strip(copy.export()) == strip(exported)


def approved(v, text="Invented derived claim", content="Invented note", sensitivity="private"):
    rec = v.add(content, sensitivity)
    c = v.add_claim(text, [rec["id"]], "human")
    v.transition_claim(c["id"], "approved")
    return rec, claims_of(v)[c["id"]]


def corrected(v):
    """Approved claim C on R1; R1 then corrected to R2 (C stale). Returns R1, R2, C and snapshots."""
    r1, c = approved(v)
    old = v.export()
    r2 = v.add("Invented note, corrected", supersedes_id=r1["id"])
    return r1, r2, c, old, v.export()


# --- Blocker 1: SQL replacement must not rewrite claims or erase history -----------------------

REPLACE_FORMS = {
    "insert_or_replace": "INSERT OR REPLACE INTO {table}({cols}) VALUES ({marks})",
    "replace_into": "REPLACE INTO {table}({cols}) VALUES ({marks})",
    "upsert_update": "INSERT INTO {table}({cols}) VALUES ({marks}) ON CONFLICT DO UPDATE SET {first}=excluded.{first}",
}


def replace_sql(form, table, row):
    cols = ", ".join(row)
    return REPLACE_FORMS[form].format(table=table, cols=cols, marks=", ".join("?" * len(row)), first=list(row)[-1]), tuple(row.values())


@pytest.mark.parametrize("form", sorted(REPLACE_FORMS))
def test_replacement_cannot_rewrite_approved_claim(vault, raw_mode, form):
    rec, c = approved(vault)
    before = claims_of(vault)[c["id"]]
    db = raw(vault, raw_mode)
    sql, args = replace_sql(form, "claims", {"id": c["id"], "text": "Rewritten", "origin": "human", "status": "proposed", "created_at": T})
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, args)
    db.close()
    assert claims_of(vault)[c["id"]] == before and before["authoritative"]
    assert_coherent(vault)


@pytest.mark.parametrize("form", sorted(REPLACE_FORMS))
@pytest.mark.parametrize("which", ["creation", "approval"])
def test_replacement_cannot_erase_history(vault, raw_mode, form, which):
    rec, c = approved(vault)
    before = claims_of(vault)[c["id"]]
    db = raw(vault, raw_mode)
    seq = db.execute("SELECT seq FROM claim_events WHERE claim_id=? AND to_status=?",
                     (c["id"], "proposed" if which == "creation" else "approved")).fetchone()[0]
    sql, args = replace_sql(form, "claim_events", {"seq": seq, "claim_id": c["id"], "from_status": "approved",
                                                   "to_status": "contested", "actor": "human", "at": T})
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, args)
    db.close()
    assert claims_of(vault)[c["id"]]["history"] == before["history"]
    assert_coherent(vault)


@pytest.mark.parametrize("form", sorted(REPLACE_FORMS))
def test_replacement_cannot_change_evidence_links(vault, raw_mode, form):
    rec, c = approved(vault)
    other = vault.add("Other invented note")
    db = raw(vault, raw_mode)
    sql, args = replace_sql(form, "claim_sources", {"claim_id": c["id"], "record_id": rec["id"], "evidence_sha256": evidence_hash(other)})
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, args)
    db.close()
    assert claims_of(vault)[c["id"]]["source_hashes"] == c["source_hashes"]
    assert_coherent(vault)


@pytest.mark.parametrize("state", ["rejected", "superseded", "forgotten"])
@pytest.mark.parametrize("form", ["insert", "insert_or_replace", "replace_into"])
def test_cannot_recreate_claim_id_to_reset_history(vault, raw_mode, state, form):
    rec = vault.add("Invented note")
    c = vault.add_claim("Original", [rec["id"]], "model")
    if state == "rejected":
        vault.transition_claim(c["id"], "rejected")
    elif state == "superseded":
        vault.supersede_claim(c["id"], "Replacement", [rec["id"]])
    else:
        vault.delete_claim(c["id"])
    before = claims_of(vault).get(c["id"])
    db = raw(vault, raw_mode)
    verb = {"insert": "INSERT", "insert_or_replace": "INSERT OR REPLACE", "replace_into": "REPLACE"}[form]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"{verb} INTO claims(id,text,origin,status,created_at) VALUES (?,?,?,?,?)", (c["id"], "Reset", "human", "proposed", T))
    db.close()
    assert claims_of(vault).get(c["id"]) == before
    assert_coherent(vault)


def test_parent_replacement_cannot_cascade_away_links_or_history(vault, raw_mode):
    rec, c = approved(vault)
    db = raw(vault, raw_mode)
    counts = lambda: [db.execute(f"SELECT count(*) FROM {t} WHERE claim_id=?", (c["id"],)).fetchone()[0] for t in ("claim_sources", "claim_events")]
    before = counts()
    for sql in ("INSERT OR REPLACE INTO claims(id,text,origin,status,created_at) VALUES (?,?,?,?,?)",
                "REPLACE INTO claims(id,text,origin,status,created_at) VALUES (?,?,?,?,?)"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql, (c["id"], "x", "human", "proposed", T))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE OR REPLACE claims SET id='other' WHERE id=?", (c["id"],))
    assert counts() == before
    db.close()
    assert_coherent(vault)


@pytest.mark.parametrize("table", ["tombstones", "claim_tombstones"])
def test_replacement_cannot_rewrite_tombstones(vault, raw_mode, table):
    rec = vault.add("Invented note")
    c = vault.add_claim("x", [rec["id"]], "human")
    vault.delete_claim(c["id"])
    vault.delete(rec["id"])
    db = raw(vault, raw_mode)
    before = db.execute(f"SELECT * FROM {table}").fetchall()
    target = c["id"] if table == "claim_tombstones" else rec["id"]
    for verb in ("INSERT", "INSERT OR REPLACE", "REPLACE", "INSERT OR IGNORE"):
        db.execute(f"{verb} INTO {table}(id,deleted_at) VALUES (?,?)", (target, "forged"))
    assert db.execute(f"SELECT * FROM {table}").fetchall() == before
    db.close()


# --- Blocker 2: source replacement must not restore authority or bypass sensitivity ------------

@pytest.mark.parametrize("form", ["insert_or_replace", "replace_into", "upsert_update"])
def test_superseded_evidence_cannot_be_replaced_as_active(vault, raw_mode, form):
    r1, r2, c, old, new = corrected(vault)
    assert claims_of(vault)[c["id"]]["support"] == "stale"
    row = dict(new["records"][[r["id"] for r in new["records"]].index(r1["id"])])
    row["status"] = "active"
    db = raw(vault, raw_mode)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(*replace_sql(form, "records", row))
    db.close()
    now = claims_of(vault)[c["id"]]
    assert now["support"] == "stale" and not now["authoritative"]
    assert_coherent(vault)


@pytest.mark.parametrize("attack", ["insert_or_replace", "delete_then_insert", "forget_then_insert", "update"])
def test_sensitive_evidence_cannot_become_cloud_disclosable(tmp_path, monkeypatch, attack):
    client = TestClient(create_app(str(tmp_path / "vault.db")))
    v = client.app.state.vault
    secret = v.add("Invented sensitive note", "sensitive")
    db = raw(v)
    args = (secret["id"], secret["content"], "manual", "private", "active", secret["created_at"])
    insert = "INSERT INTO records(id,content,source,sensitivity,status,created_at) VALUES (?,?,?,?,?,?)"
    with pytest.raises(sqlite3.IntegrityError):
        if attack == "insert_or_replace":
            db.execute(insert.replace("INSERT", "INSERT OR REPLACE"), args)
        elif attack == "delete_then_insert":
            db.execute("DELETE FROM records WHERE id=?", (secret["id"],))
        elif attack == "forget_then_insert":
            db.execute("INSERT INTO tombstones(id,deleted_at) VALUES (?,?)", (secret["id"], T))
            db.execute(insert, args)
        else:
            db.execute("UPDATE records SET sensitivity='private' WHERE id=?", (secret["id"],))
    db.close()
    seen = []
    monkeypatch.setattr(providers, "available", lambda: [{"id": "kimi", "ready": True}])
    monkeypatch.setattr(providers, "generate", lambda p, m: seen.append(m) or "ok")
    resp = client.post("/api/ask", json={"question": "Q", "provider": "kimi", "source_ids": [secret["id"]], "approve_cloud_disclosure": True})
    assert resp.status_code in (403, 422) and not seen


@pytest.mark.parametrize("field", ["content", "source", "sensitivity", "created_at", "supersedes_id", "id"])
def test_evidence_identity_fields_are_immutable(vault, raw_mode, field):
    rec, c = approved(vault)
    db = raw(vault, raw_mode)
    value = {"sensitivity": "sensitive", "supersedes_id": "elsewhere"}.get(field, "changed")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"UPDATE records SET {field}=? WHERE id=?", (value, rec["id"]))
    db.close()
    assert claims_of(vault)[c["id"]]["authoritative"]


@pytest.mark.parametrize("change", [("status", "active"), ("status", "superseded_no_correction")])
def test_evidence_revision_state_changes_only_by_correction(vault, raw_mode, change):
    r1, r2, c, old, new = corrected(vault)
    db = raw(vault, raw_mode)
    with pytest.raises(sqlite3.IntegrityError):
        if change[1] == "active":
            db.execute("UPDATE records SET status='active' WHERE id=?", (r1["id"],))
        else:
            db.execute("UPDATE records SET status='superseded' WHERE id=?", (r2["id"],))
    db.close()
    assert claims_of(vault)[c["id"]]["support"] == "stale"
    assert_coherent(vault)


def test_orphaned_claim_cannot_be_revived_by_reintroducing_its_evidence(vault, raw_mode):
    rec, c = approved(vault)
    target = fresh_like(vault, "target.db")
    target.restore_trusted({**vault.export(), "records": []})
    assert claims_of(target)[c["id"]]["support"] == "orphaned"
    db = raw(target, raw_mode)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at) VALUES (?,?,?,?,?,?)",
                   (rec["id"], rec["content"], rec["source"], rec["sensitivity"], "active", rec["created_at"]))
    db.close()
    assert not claims_of(target)[c["id"]]["authoritative"]
    assert_coherent(target)


@pytest.mark.parametrize("field,value", [("content", "Invented different note"), ("sensitivity", "sensitive"),
                                         ("source", "elsewhere"), ("created_at", "2001-01-01T00:00:00+00:00")])
def test_claim_is_not_authoritative_against_different_evidence_under_same_id(vault, field, value):
    """E vs E': a restored approval made against E does not transfer to a local E' sharing E's id."""
    rec, c = approved(vault)
    backup = vault.export()
    target = fresh_like(vault, "target.db")
    target.restore_trusted({**backup, "claims": [], "records": [{**backup["records"][0], field: value}]})
    result = target.restore_trusted(backup)
    assert result["claims_restored"] == 1 and result["approved_claims_restored"] == 1
    restored = claims_of(target)[c["id"]]
    assert restored["status"] == "approved" and restored["sources"][0]["state"] == "unverified"
    assert not restored["authoritative"]
    assert_coherent(target)


# --- Blocker 3: raw deletion / tombstones must not bypass Forget --------------------------------

def test_raw_source_delete_is_refused(vault, raw_mode):
    rec, c = approved(vault, "Derived secret text")
    db = raw(vault, raw_mode)
    for sql in ("DELETE FROM records WHERE id=?", "DELETE FROM records WHERE id=? OR 1"):
        with pytest.raises(sqlite3.IntegrityError, match="forgetting"):
            db.execute(sql, (rec["id"],))
    db.close()
    assert vault.get(rec["id"]) and claims_of(vault)[c["id"]]["authoritative"]
    assert_coherent(vault)


def test_raw_tombstone_is_a_complete_forget(vault, raw_mode):
    rec = vault.add("Invented secret: the party is on the 12th")
    a = vault.add_claim("Party on the 12th", [rec["id"]], "human")
    vault.transition_claim(a["id"], "approved", note="12th confirmed")
    b = vault.add_claim("Model reading of the 12th", [rec["id"]], "model")
    keep_rec = vault.add("Unrelated note")
    keep = vault.add_claim("Unrelated claim", [keep_rec["id"]], "human")
    old = vault.export()
    db = raw(vault, raw_mode)
    db.execute("INSERT INTO tombstones(id,deleted_at) VALUES (?,?)", (rec["id"], T))
    assert db.execute("SELECT count(*) FROM records WHERE id=?", (rec["id"],)).fetchone()[0] == 0
    assert {r[0] for r in db.execute("SELECT id FROM claim_tombstones")} == {a["id"], b["id"]}
    for table in ("claim_events", "claim_sources"):
        assert db.execute(f"SELECT count(*) FROM {table} WHERE claim_id IN (?,?)", (a["id"], b["id"])).fetchone()[0] == 0
    db.close()
    assert set(claims_of(vault)) == {keep["id"]}
    after = vault.export()
    replica = fresh_like(vault, "replica.db")
    replica.restore_trusted(after)
    for target in (vault, replica):
        target.restore_trusted(old)
        target.import_untrusted(old)
        text = json.dumps(target.export())
        assert "12th" not in text and set(claims_of(target)) == {keep["id"]}
    assert_coherent(vault)


def test_tombstones_cannot_be_removed_or_rewritten(vault, raw_mode):
    rec = vault.add("Invented note")
    vault.delete(rec["id"])
    db = raw(vault, raw_mode)
    for sql in ("DELETE FROM tombstones", "UPDATE tombstones SET id='other'", "UPDATE tombstones SET deleted_at='x'"):
        with pytest.raises(sqlite3.IntegrityError, match="permanent"):
            db.execute(sql)
    db.close()


def test_claims_cannot_cite_forgotten_evidence(vault, raw_mode):
    rec = vault.add("Invented note")
    vault.delete(rec["id"])
    db = raw(vault, raw_mode)
    db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES ('c','t','human','proposed',?)", (T,))
    with pytest.raises(sqlite3.IntegrityError, match="forgotten"):
        db.execute("INSERT INTO claim_sources(claim_id,record_id) VALUES ('c',?)", (rec["id"],))
    db.close()


def test_forgetting_old_revision_keeps_newer_revision_but_forgets_its_claims(vault):
    """Documented V0 lineage semantics: Forget walks backward (this revision and older)."""
    r1 = vault.add("Invented note v1")
    c1 = vault.add_claim("About v1", [r1["id"]], "human")
    r2 = vault.add("Invented note v2", supersedes_id=r1["id"])
    c2 = vault.add_claim("About v2", [r2["id"]], "human")
    assert vault.delete(r1["id"]) == {"records_forgotten": 1, "claims_forgotten": 1}
    assert set(claims_of(vault)) == {c2["id"]} and vault.get(r2["id"])
    assert vault.delete(r2["id"]) == {"records_forgotten": 1, "claims_forgotten": 1}
    assert claims_of(vault) == {}
    assert_coherent(vault)


# --- Blocker 4: partial import/restore must not rebuild authority piecemeal ---------------------

def test_codex_partial_restore_then_ordinary_import(vault):
    """Exact reported attack: partial restore orphans a corrected claim; importing the old
    snapshot must not bring the obsolete evidence back as active support."""
    r1, r2, c, old, new = corrected(vault)
    target = fresh_like(vault, "target.db")
    target.restore_trusted({**new, "records": []})
    assert claims_of(target)[c["id"]]["support"] == "orphaned"
    result = target.import_untrusted(old)
    assert result["imported"] == 0 and result["records_skipped"] == 1
    assert target.get(r1["id"]) is None and not claims_of(target)[c["id"]]["authoritative"]
    assert_coherent(target)


@pytest.mark.parametrize("variant", ["successor_only", "claims_only_then_full_new", "claims_only_then_trusted_old",
                                     "same_id_different_status", "old_snapshot_after_correction"])
def test_partial_restore_variants_never_raise_authority(vault, variant):
    r1, r2, c, old, new = corrected(vault)
    target = fresh_like(vault, "target.db")
    if variant == "successor_only":
        target.restore_trusted({**new, "records": [r for r in new["records"] if r["id"] != r1["id"]]})
        target.import_untrusted(old)
        target.restore_trusted(old)
    elif variant == "claims_only_then_full_new":
        target.restore_trusted({**new, "records": []})
        target.restore_trusted(new)                       # fail-safe: C stays orphaned, never re-supported
    elif variant == "claims_only_then_trusted_old":
        target.restore_trusted({**new, "records": []})
        target.restore_trusted(old)
    elif variant == "same_id_different_status":
        target.restore_trusted(new)
        target.import_untrusted(old)                      # old copy says r1 active; local says superseded
        target.restore_trusted(old)
        assert next(r for r in target.export()["records"] if r["id"] == r1["id"])["status"] == "superseded"
    else:
        target.restore_trusted({**new, "records": [r for r in new["records"] if r["id"] == r2["id"]], "claims": []})
        target.import_untrusted(old)
        assert target.get(r1["id"]) is None               # a record cannot appear after its correction
    assert c["id"] not in {k for k, x in claims_of(target).items() if x["authoritative"]}
    assert_coherent(target)


def test_import_cannot_change_existing_evidence(vault):
    rec = vault.add("Invented note", "sensitive")
    payload = {"schema": "sovereign.v0.records.2", "tombstones": [],
               "records": [{**rec, "content": "Altered", "sensitivity": "private"}]}
    assert vault.import_untrusted(payload)["records_skipped"] == 1
    assert vault.restore_trusted(payload)["records_skipped"] == 1
    assert vault.get(rec["id"]) == rec


def test_untrusted_import_cannot_correct_local_evidence_but_trusted_restore_can(vault):
    rec, c = approved(vault)
    correction = {"id": "corr", "content": "Invented correction", "source": "manual", "sensitivity": "private",
                  "status": "active", "created_at": T, "supersedes_id": rec["id"]}
    payload = {"schema": "sovereign.v0.records.2", "tombstones": [], "records": [correction]}
    assert vault.import_untrusted(payload)["records_skipped"] == 1
    assert claims_of(vault)[c["id"]]["authoritative"]
    assert vault.restore_trusted(payload)["imported"] == 1          # trusted: may only lower support
    assert claims_of(vault)[c["id"]]["support"] == "stale"
    assert_coherent(vault)


def test_second_correction_of_forgotten_revision_is_skipped_cleanly(vault):
    """Stress-found (seed 90): an old revision is forgotten while its correction survives; a payload
    carrying a *different* correction of that forgotten revision must be skipped, not crash."""
    r1 = vault.add("Invented v1")
    r2 = vault.add("Invented v2", supersedes_id=r1["id"])
    vault.delete(r1["id"])                                    # forget the old revision only
    rival = _record("rival", supersedes=r1["id"])
    payload = {"schema": "sovereign.v0.records.2", "records": [rival], "tombstones": []}
    assert vault.import_untrusted(payload)["records_skipped"] == 1
    assert vault.restore_trusted(payload)["records_skipped"] == 1
    assert vault.get("rival") is None and vault.get(r2["id"])
    assert_coherent(vault)


def test_imported_claim_id_already_replaced_here_is_skipped(vault):
    rec = vault.add("Invented note")
    payload = {"schema": "sovereign.v0.records.2", "records": [], "tombstones": [],
               "claims": [{"id": "file-claim", "text": "Imported", "origin": "human", "status": "proposed",
                           "created_at": T, "supersedes_id": None, "source_ids": [rec["id"]]}]}
    imported_id = vault.import_untrusted(payload) and next(iter(claims_of(vault)))
    vault.supersede_claim(imported_id, "Local revision", [rec["id"]])
    backup = vault.export()
    target = fresh_like(vault, "target.db")
    target.restore_trusted({**backup, "claims": [c for c in backup["claims"] if c["id"] != imported_id]})
    assert target.import_untrusted(payload)["claims_skipped"] == 1   # its replacement is already here
    assert_coherent(target)


def test_trusted_payload_cannot_forget_a_live_local_claim_by_rewriting_its_sources(vault):
    rec = vault.add("Invented note")
    gone = vault.add("Invented forgotten note")
    c = vault.add_claim("Local claim", [rec["id"]], "human")
    vault.delete(gone["id"])
    backup = vault.export()
    forged = [{**x, "source_ids": [gone["id"]], "source_hashes": {gone["id"]: None}} for x in backup["claims"]]
    result = vault.restore_trusted({**backup, "claims": forged})
    assert result["claims_skipped_existing"] == 1 and result["claims_forgotten"] == 0
    assert claims_of(vault)[c["id"]]["source_ids"] == [rec["id"]]
    assert_coherent(vault)


# --- Blocker 5: export snapshots are coherent under concurrency ---------------------------------

def _race_exports(v, operation, rounds, min_exports=5, max_rounds=1000):
    """Run `operation` repeatedly while another thread exports continuously.

    The overlap is made deterministic rather than scheduling-dependent: the reader is opened
    before the race, and writing continues until at least `min_exports` exports have completed
    *during* the writes (bounded by `max_rounds`). Writes are paced (as human-driven writes are)
    and the gap widens only while the reader has not yet got in, because an unpaced writer can
    starve rollback-journal readers. A lock timeout fails the test instead of being swallowed."""
    exports, lock_timeouts, stop = [], [], threading.Event()
    reader = Vault(v.path)

    def exporter():
        while not stop.is_set():
            try:
                exports.append(reader.export())
            except sqlite3.OperationalError as exc:
                lock_timeouts.append(exc)

    thread = threading.Thread(target=exporter)
    thread.start()
    try:
        i = 0
        while i < rounds or (len(exports) < min_exports and i < max_rounds):
            try:
                operation(i)
            except (TransitionError, KeyError, ValueError):   # a lost race is fine; corruption is not
                pass
            time.sleep(0.003 if len(exports) >= min_exports else 0.02)
            i += 1
    finally:
        stop.set()
        thread.join()
    assert not lock_timeouts
    assert len(exports) >= min_exports, f"only {len(exports)} exports overlapped {i} write rounds"
    return exports


@pytest.mark.parametrize("kind", ["decisions", "supersede", "forget", "correct"])
def test_every_concurrent_export_is_a_restorable_snapshot(vault, kind):
    base = vault.add("Invented base note")
    pool = [vault.add_claim(f"Seed {i}", [base["id"]], "human")["id"] for i in range(3)]

    def operation(i):
        if kind == "decisions":
            c = vault.add_claim(f"Claim {i}", [base["id"]], "human")
            vault.transition_claim(c["id"], "approved")
            vault.transition_claim(c["id"], random.choice(["rejected", "contested"]))
        elif kind == "supersede":
            new = vault.supersede_claim(pool[-1], f"Revision {i}", [base["id"]])["replacement"]
            pool.append(new["id"])
            vault.transition_claim(new["id"], "approved")
        elif kind == "forget":
            r = vault.add(f"Invented note {i}")
            for j in range(2):
                vault.transition_claim(vault.add_claim(f"Claim {i}.{j}", [r["id"]], "human")["id"], "approved")
            vault.delete(r["id"])
        else:
            r = vault.add(f"Invented note {i}")
            c = vault.add_claim(f"Claim {i}", [r["id"]], "human")
            vault.transition_claim(c["id"], "approved")
            r2 = vault.add(f"Invented note {i} corrected", supersedes_id=r["id"])
            vault.add(f"Invented note {i} corrected again", supersedes_id=r2["id"])

    exports = _race_exports(vault, operation, rounds=40)
    for n, exported in enumerate(exports[::max(1, len(exports) // 60)]):
        replica = fresh_like(vault, f"replica-{kind}-{n}.db")
        replica.restore_trusted(exported)
        assert strip(replica.export()) == strip(exported)
    assert_coherent(vault)


# --- Blocker 6: supersession graphs --------------------------------------------------------------

RECORD = "INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES (?,?,?,?,?,?)"
CLAIM = "INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES (?,?,?,?,?,?)"


def test_record_lineage_is_linear_and_acyclic(vault, raw_mode):
    r1 = vault.add("Invented v1")
    r2 = vault.add("Invented v2", supersedes_id=r1["id"])
    db = raw(vault, raw_mode)
    for args in (("self", "c", "private", "active", T, "self"),        # self-supersession
                 ("fork", "c", "private", "active", T, r1["id"])):     # second successor
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(RECORD, args)
    # A record cannot appear after its correction, so a cycle can never be closed.
    db.execute(RECORD, ("x", "c", "private", "active", T, "y"))
    with pytest.raises(sqlite3.IntegrityError, match="after its correction"):
        db.execute(RECORD, ("y", "c", "private", "superseded", T, "x"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE records SET supersedes_id=? WHERE id=?", (r2["id"], r1["id"]))
    db.close()
    with pytest.raises(KeyError):
        vault.add("Invented fork", supersedes_id=r1["id"])
    assert_coherent(vault)


def test_claim_lineage_is_linear_and_acyclic(vault, raw_mode):
    rec = vault.add("Invented note")
    a = vault.add_claim("A", [rec["id"]], "human")
    live = vault.add_claim("Live", [rec["id"]], "human")
    vault.transition_claim(live["id"], "approved")
    b = vault.supersede_claim(a["id"], "B", [rec["id"]])["replacement"]
    db = raw(vault, raw_mode)
    for args in (("self", "t", "human", "proposed", T, "self"),            # self-supersession
                 ("second", "t", "human", "proposed", T, a["id"]),         # second replacement
                 ("hijack", "t", "human", "proposed", T, live["id"])):     # predecessor not superseded
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(CLAIM, args)
    db.execute(CLAIM, ("p", "t", "human", "proposed", T, "q"))
    with pytest.raises(sqlite3.IntegrityError, match="supersession"):
        db.execute(CLAIM, ("q", "t", "human", "proposed", T, "p"))         # would close a cycle
    db.close()
    vault.transition_claim(b["id"], "approved")
    with pytest.raises(TransitionError):
        vault.supersede_claim(a["id"], "C", [rec["id"]])                    # superseded is terminal
    assert claims_of(vault)[live["id"]]["authoritative"]
    assert_coherent(vault)


def _record(id, status="active", supersedes=None):
    return {"id": id, "content": f"Invented {id}", "source": "manual", "sensitivity": "private",
            "status": status, "created_at": T, "supersedes_id": supersedes}


@pytest.mark.parametrize("records", [
    [_record("a", supersedes="a")],                                                  # self
    [_record("a", "superseded"), _record("b", supersedes="a"), _record("c", supersedes="a")],  # fork
    [_record("a", "superseded", "b"), _record("b", "superseded", "a")],            # cycle
    [_record("a"), _record("b", supersedes="a")],                                   # active predecessor
    [_record("a"), _record("a")],                                                   # duplicate id
], ids=["self", "fork", "cycle", "active_predecessor", "duplicate"])
def test_malformed_record_lineage_payloads_are_rejected(vault, records):
    payload = {"schema": "sovereign.v0.records.2", "records": records, "tombstones": []}
    for operation in (vault.import_untrusted, vault.restore_trusted):
        with pytest.raises(ValueError):
            operation(payload)
    assert vault.export()["records"] == []


def test_malformed_claim_lineage_payloads_are_rejected(vault):
    rec = vault.add("Invented note")
    a = vault.add_claim("A", [rec["id"]], "human")
    b = vault.add_claim("B", [rec["id"]], "human")
    backup = vault.export()
    target = fresh_like(vault, "target.db")
    by_id = {c["id"]: c for c in backup["claims"]}
    cases = {
        "cycle": [{**by_id[a["id"]], "supersedes_id": b["id"]}, {**by_id[b["id"]], "supersedes_id": a["id"]}],
        "self": [{**by_id[a["id"]], "supersedes_id": a["id"]}, by_id[b["id"]]],
        "live_predecessor": [by_id[a["id"]], {**by_id[b["id"]], "supersedes_id": a["id"]}],
    }
    for name, claims in cases.items():
        with pytest.raises(ValueError):
            target.restore_trusted({**backup, "claims": claims})
        assert target.export()["claims"] == [], name


def test_long_lineages_restore_in_any_payload_order(vault):
    rec = vault.add("Invented v0")
    for i in range(1, 15):
        rec = vault.add(f"Invented v{i}", supersedes_id=rec["id"])
    c = vault.add_claim("Claim v0", [rec["id"]], "human")
    for i in range(1, 15):
        vault.transition_claim(c["id"], "approved")
        c = vault.supersede_claim(c["id"], f"Claim v{i}", [rec["id"]])["replacement"]
    backup = vault.export()
    for order in ("reversed", "shuffled"):
        shuffled = {**backup, "records": list(backup["records"]), "claims": list(backup["claims"])}
        if order == "reversed":
            shuffled["records"].reverse(); shuffled["claims"].reverse()
        else:
            random.Random(7).shuffle(shuffled["records"]); random.Random(7).shuffle(shuffled["claims"])
        target = fresh_like(vault, f"target-{order}.db")
        target.restore_trusted(shuffled)
        assert strip(target.export()) == strip(backup)
    assert_coherent(vault)


# --- Blocker 7: no history ceiling; one explicit size policy ------------------------------------

def test_long_lived_claim_with_hundreds_of_events_round_trips(vault):
    rec = vault.add("Invented note")
    c = vault.add_claim("Long-lived claim", [rec["id"]], "human")
    vault.transition_claim(c["id"], "approved")
    for i in range(130):
        vault.transition_claim(c["id"], "contested", note=f"doubt {i}")
        vault.transition_claim(c["id"], "approved", note=f"confirmed {i}")
    assert len(claims_of(vault)[c["id"]]["history"]) == 262
    assert_coherent(vault)


def test_backups_beyond_old_count_caps_restore(vault):
    records = [_record(f"r{i:05d}") for i in range(10_500)]
    vault.restore_trusted({"schema": "sovereign.v0.records.2", "records": records, "tombstones": []})
    assert_coherent(vault)


def test_size_policy_is_shared_by_export_import_and_restore(tmp_path, monkeypatch):
    client = TestClient(create_app(str(tmp_path / "vault.db")))
    for i in range(20):
        client.post("/api/memories", json={"content": f"Invented note {i} " + "x" * 400})
    backup = client.get("/api/export").json()
    monkeypatch.setattr(store, "MAX_BACKUP_BYTES", 2000)
    assert client.get("/api/export").status_code == 413
    assert client.post("/api/import", json=backup).status_code == 413
    assert client.post("/api/restore", json={"confirm_trusted_restore": True, "backup": backup}).status_code == 413
    chunked = client.post("/api/import", content=iter([json.dumps(backup).encode()]), headers={"Content-Type": "application/json"})
    assert chunked.status_code == 411


# --- Blocker 8 / property: no operation sequence lets import/restore raise authority -------------

def _support(v):
    return {k: (c["status"], RANK[c["support"]], c["authoritative"]) for k, c in claims_of(v).items()}


@pytest.mark.parametrize("seed", range(12))
def test_random_operation_sequences_preserve_authority_and_restorability(tmp_path, seed):
    rnd = random.Random(seed)
    a, b = Vault(str(tmp_path / "a.db")), Vault(str(tmp_path / "b.db"))
    snapshots = []

    def active(v):
        return [r["id"] for r in v.search(limit=100)]

    for step in range(70):
        v = rnd.choice([a, a, b])
        op = rnd.choice(["add", "add", "correct", "forget", "claim", "claim", "decide", "decide", "supersede",
                         "forget_claim", "snapshot", "import", "restore", "partial"])
        try:
            if op == "add":
                v.add(f"Invented note {seed}.{step}", rnd.choice(["private", "sensitive"]))
            elif op == "correct" and active(v):
                v.add(f"Invented correction {seed}.{step}", supersedes_id=rnd.choice(active(v)))
            elif op == "forget":
                ids = [r["id"] for r in v.export()["records"]]
                if ids:
                    v.delete(rnd.choice(ids))
            elif op == "claim" and active(v):
                v.add_claim(f"Claim {seed}.{step}", rnd.sample(active(v), min(len(active(v)), rnd.randint(1, 3))),
                            rnd.choice(["human", "model"]))
            elif op == "decide" and claims_of(v):
                v.transition_claim(rnd.choice(list(claims_of(v))), rnd.choice(["approved", "rejected", "contested"]))
            elif op == "supersede" and claims_of(v) and active(v):
                v.supersede_claim(rnd.choice(list(claims_of(v))), f"Revision {seed}.{step}", [rnd.choice(active(v))])
            elif op == "forget_claim" and claims_of(v):
                v.delete_claim(rnd.choice(list(claims_of(v))))
            elif op == "snapshot":
                snapshots.append(v.export())
            elif op in ("import", "restore", "partial") and snapshots:
                snap = rnd.choice(snapshots)
                if op == "partial":
                    keep = lambda items, p: [x for x in items if rnd.random() < p]
                    snap = {**snap, "records": keep(snap["records"], 0.5), "claims": keep(snap["claims"], 0.7),
                            "tombstones": keep(snap["tombstones"], 0.5), "claim_tombstones": keep(snap["claim_tombstones"], 0.5)}
                before = _support(v)
                (v.import_untrusted if op == "import" else v.restore_trusted)(snap)
                after = _support(v)
                for cid, (status, rank, auth) in before.items():
                    if cid in after:
                        assert after[cid][0] == status, (op, cid)          # import/restore never decides
                        assert after[cid][1] <= rank, (op, cid)            # support never rises
                        assert not (after[cid][2] and not auth), (op, cid)  # authority never appears
        except (TransitionError, KeyError):
            pass
        if step % 10 == 9:
            assert_coherent(v)
    assert_coherent(a)
    assert_coherent(b)
