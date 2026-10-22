"""Issue #6: hidden-rowid replacement and evidence-empty authority (ADR-0003 storage contract).

Invariant under test: no SQL statement issued on an ordinary connection to the vault, in any
combination of `foreign_keys` and `recursive_triggers`, can delete, replace or re-key a canonical
row of `records`, `tombstones`, `claims`, `claim_sources`, `claim_tombstones` or `claim_events`
without the corresponding storage guard firing. Every attack below must leave the canonical state
exactly as it was, whether SQLite rejects the statement or a trigger ignores it.

Founder-accepted invariant (2026-10-22): a MemoryClaim with missing, invalid, corrupted or
insufficiently verified required evidence is never authoritative, including when it has no
evidence links at all.

Out of scope, as ADR-0003 states: a process that can change the schema (DROP TRIGGER,
writable_schema) or rewrite the vault file. The zero-source tests below use such a process only
to simulate corruption, then check that derivation never treats the result as authoritative.
"""
import sqlite3

import pytest

from sovereign import claims as rules
from sovereign import context
from sovereign.store import Vault

T = "2026-10-22T00:00:00+00:00"
CANONICAL = {
    "records": "id", "tombstones": "id", "claims": "id",
    "claim_sources": "claim_id, record_id", "claim_tombstones": "id", "claim_events": "seq",
}
ROWID_FREE = ("records", "tombstones", "claims", "claim_sources", "claim_tombstones")


@pytest.fixture(params=[(True, False), (False, False), (True, True), (False, True)],
                ids=["fk_on", "fk_off", "fk_on_recursive", "fk_off_recursive"])
def pragmas(request):
    return request.param


@pytest.fixture
def vault(tmp_path):
    """A populated synthetic vault. The first and second row of every canonical table exist."""
    v = Vault(str(tmp_path / "vault.db"))
    r1 = v.add("First synthetic record, cited by an approved claim")
    r2 = v.add("Second synthetic record, cited by a proposed claim")
    c1 = v.add_claim("Approved interpretation of the first record", [r1["id"]])
    v.transition_claim(c1["id"], "approved", expected_status="proposed")
    v.add_claim("Proposed interpretation of the second record", [r2["id"]])
    for text in ("Third synthetic record, forgotten", "Fourth synthetic record, forgotten"):
        v.delete(v.add(text)["id"])
    for text in ("Claim to forget A", "Claim to forget B"):
        v.delete_claim(v.add_claim(text, [r1["id"]])["id"])
    v.ids = {"r1": r1["id"], "r2": r2["id"], "c1": c1["id"]}
    return v


def connect(v, pragmas):
    """An ordinary connection to the vault file, in the given pragma configuration."""
    fk, recursive = pragmas
    db = sqlite3.connect(v.path, isolation_level=None)
    db.execute(f"PRAGMA foreign_keys={'ON' if fk else 'OFF'}")
    db.execute(f"PRAGMA recursive_triggers={'ON' if recursive else 'OFF'}")
    return db


def snapshot(v):
    db = sqlite3.connect(v.path)
    try:
        return {t: db.execute(f"SELECT * FROM {t} ORDER BY {key}").fetchall() for t, key in CANONICAL.items()}
    finally:
        db.close()


def rowid_attacks(ids):
    """(name, setup statements, attack statement). Rowid 1 and 2 are the first two rows of each table."""
    cols = {
        "records": ("id,content,source,sensitivity,status,created_at", f"'atk-r','forged','manual','private','active','{T}'"),
        "tombstones": ("id,deleted_at", f"'atk-t','{T}'"),
        "claims": ("id,text,origin,status,created_at", f"'atk-c','forged','human','proposed','{T}'"),
        "claim_sources": ("claim_id,record_id,evidence_sha256", f"'atk-c','{ids['r2']}',NULL"),
        "claim_tombstones": ("id,deleted_at", f"'atk-ct','{T}'"),
        # A lifecycle-legal transition of the approved claim, so only the history guard can stop it.
        "claim_events": ("claim_id,from_status,to_status,actor,at", f"'{ids['c1']}','approved','contested','human','{T}'"),
    }
    # A raw proposed claim without history may own new links (lifecycle-legal); idempotent across attacks.
    setup = {"claim_sources": [f"INSERT INTO claims(id,text,origin,status,created_at) SELECT 'atk-c','forged','human','proposed','{T}' "
                               "WHERE NOT EXISTS (SELECT 1 FROM claims WHERE id='atk-c')"]}
    attacks = []
    for table, (names, values) in cols.items():
        pre = setup.get(table, [])
        for alias in ("rowid", "_rowid_", "oid"):
            attacks.append((f"{table}:insert_or_replace_{alias}", pre,
                            f"INSERT OR REPLACE INTO {table}({alias},{names}) VALUES(1,{values})"))
        attacks.append((f"{table}:replace_rowid", pre, f"REPLACE INTO {table}(rowid,{names}) VALUES(1,{values})"))
        attacks.append((f"{table}:update_or_replace_set_rowid", pre, f"UPDATE OR REPLACE {table} SET rowid=1 WHERE rowid=2"))
        attacks.append((f"{table}:update_or_replace_set_oid", pre, f"UPDATE OR REPLACE {table} SET oid=1 WHERE oid=2"))
    return attacks


def primary_key_attacks(v):
    """Replacement by primary key: these were already guarded; kept so the matrix is complete."""
    db = sqlite3.connect(v.path)
    row = lambda sql: db.execute(sql).fetchone()
    rec, tomb = row("SELECT id FROM records LIMIT 1")[0], row("SELECT id FROM tombstones LIMIT 1")[0]
    claim, ctomb = row("SELECT id FROM claims LIMIT 1")[0], row("SELECT id FROM claim_tombstones LIMIT 1")[0]
    link = row("SELECT claim_id, record_id FROM claim_sources LIMIT 1")
    seq = row("SELECT seq FROM claim_events LIMIT 1")[0]
    db.close()
    return [
        ("records:pk_replace", [], f"INSERT OR REPLACE INTO records(id,content,sensitivity,status,created_at) VALUES('{rec}','forged','private','active','{T}')"),
        ("records:update_or_replace_pk", [], f"UPDATE OR REPLACE records SET id='{rec}' WHERE id<>'{rec}'"),
        ("tombstones:pk_replace", [], f"INSERT OR REPLACE INTO tombstones(id,deleted_at) VALUES('{tomb}','forged')"),
        ("claims:pk_replace", [], f"INSERT OR REPLACE INTO claims(id,text,origin,status,created_at) VALUES('{claim}','forged','human','proposed','{T}')"),
        ("claims:update_or_replace_pk", [], f"UPDATE OR REPLACE claims SET id='{claim}' WHERE id<>'{claim}'"),
        ("claim_sources:pk_replace", [], f"INSERT OR REPLACE INTO claim_sources(claim_id,record_id) VALUES('{link[0]}','{link[1]}')"),
        ("claim_tombstones:pk_replace", [], f"INSERT OR REPLACE INTO claim_tombstones(id,deleted_at) VALUES('{ctomb}','forged')"),
        ("claim_events:seq_replace", [], f"INSERT OR REPLACE INTO claim_events(seq,claim_id,from_status,to_status,actor,at) VALUES({seq},'{v.ids['c1']}','approved','contested','human','{T}')"),
        ("claim_events:update_or_replace_seq", [], f"UPDATE OR REPLACE claim_events SET seq={seq} WHERE seq<>{seq}"),
    ]


def run_attack(v, pragmas, setup, attack):
    db = connect(v, pragmas)
    try:
        for statement in setup:
            db.execute(statement)
        before = snapshot(v)
        try:
            db.execute(attack)
        except sqlite3.DatabaseError:
            pass   # rejected by SQLite or by a guard: either is acceptable; the state check decides
    finally:
        db.close()
    return before, snapshot(v)


def test_hidden_rowid_replacement_never_changes_canonical_state(vault, pragmas):
    changed = []
    for name, setup, attack in rowid_attacks(vault.ids):
        before, after = run_attack(vault, pragmas, setup, attack)
        if before != after:
            changed.append(name)
    assert changed == [], f"canonical state changed by: {changed}"


def test_primary_key_replacement_never_changes_canonical_state(vault, pragmas):
    changed = []
    for name, setup, attack in primary_key_attacks(vault):
        before, after = run_attack(vault, pragmas, setup, attack)
        if before != after:
            changed.append(name)
    assert changed == [], f"canonical state changed by: {changed}"


def test_canonical_tables_have_no_hidden_rowid(vault):
    db = sqlite3.connect(vault.path)
    try:
        for table in ROWID_FREE:
            sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            assert sql.rstrip().upper().endswith("WITHOUT ROWID"), table
            with pytest.raises(sqlite3.OperationalError):
                db.execute(f"SELECT rowid FROM {table}")
        # claim_events keeps INTEGER PRIMARY KEY AUTOINCREMENT: its rowid is `seq`, guarded by claim_events_no_replace.
        assert db.execute("SELECT count(*) FROM claim_events WHERE rowid <> seq").fetchone()[0] == 0
    finally:
        db.close()


def test_legitimate_lifecycle_still_works_after_attacks(vault, pragmas):
    for _, setup, attack in rowid_attacks(vault.ids):
        run_attack(vault, pragmas, setup, attack)
    r = vault.add("A new synthetic record after the attacks")
    fix = vault.add("A corrected synthetic record", supersedes_id=r["id"])
    c = vault.add_claim("A new claim", [fix["id"]])
    vault.transition_claim(c["id"], "approved", expected_status="proposed")
    vault.supersede_claim(c["id"], "A superseding claim", [fix["id"]], expected_status="approved")
    assert vault.delete(fix["id"])["claims_forgotten"] == 2
    restored = Vault(vault.path.replace("vault.db", "restored.db"))
    restored.restore_trusted(vault.export())
    strip = lambda e: {k: e[k] for k in ("records", "tombstones", "claims", "claim_tombstones")}
    assert strip(restored.export()) == strip(vault.export())


# --- Evidence-empty and corrupted-evidence authority -------------------------------------------

def test_a_claim_with_no_evidence_is_never_supported():
    assert rules.support_of([]) == "orphaned"
    assert not rules.is_authoritative("approved", rules.support_of([]), "committed")


def corrupt(v, sql):
    """Simulate corruption by a process that controls the schema (outside the K1 threat model)."""
    db = sqlite3.connect(v.path, isolation_level=None)
    try:
        db.execute("DROP TRIGGER claim_sources_fixed_delete")
        db.execute("DROP TRIGGER claim_sources_fixed_update")
        db.execute(sql)
    finally:
        db.close()


@pytest.mark.parametrize("damage", ["remove_all_links", "null_hash", "wrong_hash"])
def test_corrupted_or_missing_evidence_links_never_yield_authority(vault, damage):
    c1 = vault.ids["c1"]
    sql = {"remove_all_links": f"DELETE FROM claim_sources WHERE claim_id='{c1}'",
           "null_hash": f"UPDATE claim_sources SET evidence_sha256=NULL WHERE claim_id='{c1}'",
           "wrong_hash": f"UPDATE claim_sources SET evidence_sha256='{'0' * 64}' WHERE claim_id='{c1}'"}[damage]
    corrupt(vault, sql)
    claim = next(c for c in vault.list_claims() if c["id"] == c1)
    assert claim["status"] == "approved"
    assert claim["support"] == "orphaned"
    assert claim["authoritative"] is False


def test_evidence_empty_approved_claim_is_excluded_from_every_context(vault):
    c1 = vault.ids["c1"]
    corrupt(vault, f"DELETE FROM claim_sources WHERE claim_id='{c1}'")
    for provider in ("local", "kimi"):
        bundle = context.compile_context(vault, "approved interpretation first record", provider, [])
        assert c1 not in [i.candidate.id for i in bundle.included]
        excluded = {e.candidate.id: e for e in bundle.excluded}
        assert "orphaned" in excluded[c1].reasons
        assert excluded[c1].candidate.sensitivity == "sensitive"


def test_evidence_empty_claim_cannot_be_reapproved(vault):
    c1 = vault.ids["c1"]
    vault.transition_claim(c1, "contested", expected_status="approved")
    corrupt(vault, f"DELETE FROM claim_sources WHERE claim_id='{c1}'")
    with pytest.raises(rules.TransitionError, match="orphaned"):
        vault.transition_claim(c1, "approved", expected_status="contested")
