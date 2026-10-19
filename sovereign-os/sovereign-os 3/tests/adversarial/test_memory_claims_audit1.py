"""Adversarial regression suite for MemoryClaim authority (Codex audit of c847f9d, blockers 1-6).

Each test attacks one invariant through hostile input, raw SQL, import/restore,
deletion or concurrency, and asserts that authority never increases.
"""
import copy
import sqlite3
import threading

from fastapi.testclient import TestClient
import pytest
from sovereign.app import create_app
from sovereign.store import Vault, evidence_hash

CONFIRM = {"confirm": True}
T = "2026-10-18T00:00:00+00:00"

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "vault.db")))

def vault_of(client) -> Vault:
    return client.app.state.vault

def create(client, text="Invented note: the garden project starts in May"):
    resp=client.post("/api/memories",json={"content":text})
    assert resp.status_code==201, resp.text
    return resp.json()

def claim(client, source_ids, text="Derived claim"):
    resp=client.post("/api/claims",json={"text":text,"source_ids":source_ids})
    assert resp.status_code==201, resp.text
    return resp.json()

def act(client, claim_id, action, expect=200, **body):
    if "expected_status" not in body:   # the UI always sends the status it displayed
        current=client.get("/api/claims").json()["claims"]
        body["expected_status"]=next((c["status"] for c in current if c["id"]==claim_id),"proposed")
    resp=client.post(f"/api/claims/{claim_id}/{action}",json={**CONFIRM,**body})
    assert resp.status_code==expect, resp.text
    return resp.json()

def claims(client):
    return {c["id"]: c for c in client.get("/api/claims").json()["claims"]}

def restore(client, backup, expect=200):
    resp=client.post("/api/restore",json={"confirm_trusted_restore":True,"backup":backup})
    assert resp.status_code==expect, resp.text
    return resp.json()

def new_client(tmp_path, name):
    return TestClient(create_app(str(tmp_path / name)))

def imported(client):
    """The single claim an ordinary import created (imported claims never keep the file's id)."""
    found=[c for c in claims(client).values() if c["origin"]=="imported"]
    assert len(found)==1, found
    return found[0]

def authoritative(client):
    return {k for k,c in claims(client).items() if c["authoritative"]}

def forged_payload(record, claim_id="forged-claim", status="approved", origin="human"):
    history=[{"from_status":None,"to_status":"proposed","actor":origin,"note":None,"at":T},
             {"from_status":"proposed","to_status":"approved","actor":"human","note":"I approve","at":T}]
    return {"schema":"sovereign.v0.records.2","records":[record],"tombstones":[],"claim_tombstones":[],
            "claims":[{"id":claim_id,"text":"Forged fact about me","origin":origin,"status":status,"created_at":T,
                       "supersedes_id":None,"source_ids":[record["id"]],
                       "source_hashes":{record["id"]:evidence_hash(record)},"history":history}]}

FOREIGN_RECORD={"id":"foreign-record","content":"Invented imported note","source":"manual","sensitivity":"private",
                "status":"active","created_at":T,"supersedes_id":None}

# --- Blocker 1: ordinary import cannot forge authority ----------------------------------------

@pytest.mark.parametrize("origin",["human","model","imported"])
def test_ordinary_import_of_forged_approval_is_only_proposed(client,origin):
    result=client.post("/api/import",json=forged_payload(FOREIGN_RECORD,origin=origin)).json()
    assert result["claims_imported_as_proposed"]==1
    assert "forged-claim" not in claims(client)
    c=imported(client)
    assert c["status"]=="proposed" and c["origin"]=="imported" and not c["authoritative"]
    assert [e["to_status"] for e in c["history"]]==["proposed"]
    assert authoritative(client)==set()

def test_ordinary_import_forgery_against_existing_local_evidence(client):
    rec=create(client)
    client.post("/api/import",json={**forged_payload(rec),"records":[]})
    assert imported(client)["status"]=="proposed" and authoritative(client)==set()

def test_ordinary_import_cannot_forget_local_state(client):
    rec=create(client)
    c=claim(client,[rec["id"]]); act(client,c["id"],"approve")
    hostile={"schema":"sovereign.v0.records.2","records":[],"claims":[],
             "tombstones":[{"id":rec["id"],"deleted_at":T}],"claim_tombstones":[{"id":c["id"],"deleted_at":T}]}
    assert client.post("/api/import",json=hostile).status_code==200
    assert authoritative(client)=={c["id"]} and client.get("/api/memories").json()["records"]==[rec]
    # And it did not plant tombstones that would block a later legitimate restore.
    assert client.get("/api/export").json()["claim_tombstones"]==[]

def test_ordinary_import_cannot_reach_trusted_restore(client):
    payload=forged_payload(FOREIGN_RECORD)
    assert client.post("/api/import",json={"confirm_trusted_restore":True,"backup":payload}).status_code==422
    assert claims(client)=={}

@pytest.mark.parametrize("body",[lambda p:p, lambda p:{"backup":p}, lambda p:{"confirm_trusted_restore":"yes","backup":p},
                                 lambda p:{"confirm_trusted_restore":True,"backup":p,"extra":1}])
def test_trusted_restore_requires_explicit_confirmation(client,body):
    assert client.post("/api/restore",json=body(forged_payload(FOREIGN_RECORD))).status_code==422
    assert claims(client)=={}

@pytest.mark.parametrize("mutate",[
    lambda c:c.update(history=c["history"][:1]),                                             # approved without decision
    lambda c:c["history"].__setitem__(1,{**c["history"][1],"actor":"model"}),                # model approval
    lambda c:c.update(history=[{**c["history"][0],"to_status":"approved"}]),                # born approved
    lambda c:c["history"].insert(1,{"from_status":"proposed","to_status":"rejected","actor":"human","note":None,"at":T})
             or c["history"].__setitem__(2,{**c["history"][2],"from_status":"rejected"}),   # rejected -> approved
    lambda c:c["history"][0].update(actor="human") or c.update(origin="model"),             # creator != origin
])
def test_trusted_restore_rejects_illegal_histories_atomically(client,mutate):
    payload=forged_payload(FOREIGN_RECORD)
    mutate(payload["claims"][0])
    restore(client,payload,expect=422)
    assert claims(client)=={} and client.get("/api/memories").json()["records"]==[]

# --- Blocker 2: claim tombstones dominate live claims -----------------------------------------

def cross_vault(client,tmp_path):
    rec=create(client)
    c=claim(client,[rec["id"]]); act(client,c["id"],"approve")
    old_a=client.get("/api/export").json()
    b=new_client(tmp_path,"b.db"); restore(b,old_a)
    assert c["id"] in claims(b)
    b.delete(f"/api/claims/{c['id']}")
    return rec,c,old_a,b.get("/api/export").json()

def test_cross_vault_claim_deletion_propagates(client,tmp_path):
    rec,c,old_a,b_snapshot=cross_vault(client,tmp_path)
    assert restore(client,b_snapshot)["claims_forgotten"]==1
    assert c["id"] not in claims(client)
    for _ in range(3):   # repeated restore of either snapshot never resurrects
        restore(client,old_a); restore(client,b_snapshot)
        client.post("/api/import",json=old_a)
        assert c["id"] not in claims(client)

@pytest.mark.parametrize("order",[("old","new"),("new","old"),("old","new","old")])
def test_restore_ordering_cannot_resurrect(client,tmp_path,order):
    rec,c,old_a,b_snapshot=cross_vault(client,tmp_path)
    fresh=new_client(tmp_path,"fresh.db")
    for which in order:
        restore(fresh,old_a if which=="old" else b_snapshot)
    assert c["id"] not in claims(fresh)
    assert c["id"] in {t["id"] for t in fresh.get("/api/export").json()["claim_tombstones"]}

def test_cross_vault_record_forget_propagates_to_dependent_claims(client,tmp_path):
    rec=create(client)
    c=claim(client,[rec["id"]],"Restates the note"); act(client,c["id"],"approve")
    old_a=client.get("/api/export").json()
    b=new_client(tmp_path,"b.db"); restore(b,old_a)
    b.delete(f"/api/memories/{rec['id']}")
    restore(client,b.get("/api/export").json())
    assert client.get("/api/memories").json()["records"]==[] and claims(client)=={}
    restore(client,old_a); client.post("/api/import",json=old_a)
    assert client.get("/api/memories").json()["records"]==[] and claims(client)=={}

# --- Blocker 3: forget removes derived personal information ----------------------------------

def test_forget_export_restore_replay(client,tmp_path):
    rec=create(client,"Invented secret: the surprise party is on the 12th")
    c=claim(client,[rec["id"]],"Party on the 12th"); act(client,c["id"],"approve",note="12th confirmed")
    old=client.get("/api/export").json()
    result=client.delete(f"/api/memories/{rec['id']}").json()
    assert result["claims_forgotten"]==1
    after=client.get("/api/export").json()
    assert "12th" not in str(after) and "surprise" not in str(after)
    fresh=new_client(tmp_path,"fresh.db"); restore(fresh,after)
    assert claims(fresh)=={} and fresh.get("/api/memories").json()["records"]==[]
    for replay in (lambda: restore(client,old), lambda: client.post("/api/import",json=old)):
        replay()
        assert claims(client)=={} and client.get("/api/memories").json()["records"]==[]
        assert "12th" not in str(client.get("/api/export").json())

def test_forgotten_claim_text_is_not_left_in_active_db_file(client):
    rec=create(client,"Invented note")
    claim(client,[rec["id"]],"ZQX-unique-derived-phrase")
    client.delete(f"/api/memories/{rec['id']}")
    with open(vault_of(client).path,"rb") as fh:
        assert b"ZQX-unique-derived-phrase" not in fh.read()   # secure_delete; WAL/backups not covered

# --- Blocker 4: SQLite enforces lifecycle/history invariants ----------------------------------

@pytest.fixture(params=["fk_on","fk_off"])
def raw(request,tmp_path):
    """A vault with one proposed and one rejected claim, plus a raw connection to attack it."""
    vault=Vault(str(tmp_path / "raw.db"))
    rec=vault.add("Invented note")
    proposed=vault.add_claim("Proposed claim",[rec["id"]],"model")
    rejected=vault.add_claim("Rejected claim",[rec["id"]],"human")
    vault.transition_claim(rejected["id"],"rejected")
    db=sqlite3.connect(vault.path,isolation_level=None)
    db.execute(f"PRAGMA foreign_keys={'ON' if request.param=='fk_on' else 'OFF'}")
    yield vault,db,rec,proposed["id"],rejected["id"]
    db.close()

def snapshot_state(vault):
    return [(c["id"],c["status"],c["text"],c["source_ids"],c["source_hashes"],c["history"]) for c in vault.list_claims()]

RAW_ATTACKS={
    "insert_approved_claim": "INSERT INTO claims(id,text,origin,status,created_at) VALUES ('x','t','human','approved','{T}')",
    "illegal_transition_from_rejected": "INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{R}','rejected','approved','human','{T}')",
    "from_status_mismatch": "INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{P}','contested','approved','human','{T}')",
    "model_actor_transition": "INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{P}','proposed','approved','model','{T}')",
    "imported_actor_transition": "INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{P}','proposed','approved','imported','{T}')",
    "second_creation_event": "INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{P}',NULL,'proposed','model','{T}')",
    "event_for_unknown_claim": "INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('nope','proposed','approved','human','{T}')",
    "update_status_without_event": "UPDATE claims SET status='approved' WHERE id='{P}'",
    "reactivate_rejected_by_update": "UPDATE claims SET status='proposed' WHERE id='{R}'",
    "mutate_text": "UPDATE claims SET text='Edited' WHERE id='{P}'",
    "mutate_origin": "UPDATE claims SET origin='human' WHERE id='{P}'",
    "mutate_created_at": "UPDATE claims SET created_at='2000-01-01' WHERE id='{P}'",
    "mutate_supersedes": "UPDATE claims SET supersedes_id='{R}' WHERE id='{P}'",
    "delete_history_event": "DELETE FROM claim_events WHERE claim_id='{R}' AND to_status='rejected'",
    "update_history_event": "UPDATE claim_events SET to_status='approved' WHERE claim_id='{R}' AND to_status='rejected'",
    "delete_claim_without_tombstone": "DELETE FROM claims WHERE id='{R}'",
    "delete_source_link": "DELETE FROM claim_sources WHERE claim_id='{P}'",
    "insert_source_link": "INSERT INTO claim_sources(claim_id,record_id) VALUES ('{P}','other')",
    "replace_source_link": "UPDATE claim_sources SET record_id='other' WHERE claim_id='{P}'",
    "rewrite_evidence_hash": "UPDATE claim_sources SET evidence_sha256=NULL WHERE claim_id='{P}'",
    "delete_claim_tombstone": "DELETE FROM claim_tombstones",
    "delete_record_tombstone": "DELETE FROM tombstones",
    "mutate_evidence_content": "UPDATE records SET content='Rewritten evidence' WHERE id='{E}'",
}

@pytest.mark.parametrize("name",sorted(RAW_ATTACKS))
def test_raw_sql_cannot_break_lifecycle(raw,name):
    vault,db,rec,p,r=raw
    # Give the tombstone attacks something to delete.
    vault.delete_claim(vault.add_claim("Forgotten",[rec["id"]],"human")["id"])
    vault.delete(vault.add("Forgotten evidence")["id"])
    for target in (p,r):
        assert db.execute("SELECT count(*) FROM claims WHERE id=?",(target,)).fetchone()[0]==1
    assert db.execute("SELECT count(*) FROM tombstones").fetchone()[0]==db.execute("SELECT count(*) FROM claim_tombstones").fetchone()[0]==1
    before=snapshot_state(vault)
    sql=RAW_ATTACKS[name].format(T=T,P=p,R=r,E=rec["id"])
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)
    assert snapshot_state(vault)==before
    assert not any(c["authoritative"] for c in vault.list_claims())

def test_raw_sql_cannot_reuse_forgotten_ids(raw):
    vault,db,rec,p,r=raw
    vault.delete_claim(p)
    with pytest.raises(sqlite3.IntegrityError, match="forgotten"):
        db.execute(f"INSERT INTO claims(id,text,origin,status,created_at) VALUES ('{p}','Back','human','proposed','{T}')")
    vault.delete(rec["id"])
    with pytest.raises(sqlite3.IntegrityError, match="forgotten"):
        db.execute(f"INSERT INTO records(id,content,sensitivity,status,created_at) VALUES ('{rec['id']}','Back','private','active','{T}')")

def test_raw_sql_cannot_reactivate_superseded_or_unsupersede_evidence(raw):
    vault,db,rec,p,r=raw
    newer=vault.add("Invented note v2")
    vault.supersede_claim(p,"Replacement",[newer["id"]])
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{p}','superseded','approved','human','{T}')")
    vault.add("Invented note v3",supersedes_id=newer["id"])
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"UPDATE records SET status='active' WHERE id='{newer['id']}'")

def test_raw_tombstone_insert_forgets_cleanly(raw):
    vault,db,rec,p,r=raw
    db.execute(f"INSERT INTO claim_tombstones(id,deleted_at) VALUES ('{p}','{T}')")
    assert p not in {c["id"] for c in vault.list_claims()}
    for table in ("claim_events","claim_sources"):
        assert db.execute(f"SELECT count(*) FROM {table} WHERE claim_id=?",(p,)).fetchone()[0]==0

def test_raw_sql_legal_transition_is_applied_by_event_only(raw):
    """Documented limit: a legal, human-attributed event written by raw SQL is indistinguishable
    from a UI decision (no authentication in V0) — but it must still obey the lifecycle."""
    vault,db,rec,p,r=raw
    db.execute(f"INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{p}','proposed','contested','human','{T}')")
    c={x["id"]:x for x in vault.list_claims()}[p]
    assert c["status"]=="contested" and [e["to_status"] for e in c["history"]]==["proposed","contested"]

# --- Blocker 5: source-link / evidence manipulation never restores authority -----------------

def test_stale_claim_cannot_regain_authority_by_link_surgery(client):
    rec=create(client)
    c=claim(client,[rec["id"]]); act(client,c["id"],"approve")
    fixed=client.post(f"/api/memories/{rec['id']}/correct",json={"content":"Invented note corrected"}).json()
    assert authoritative(client)==set()
    db=sqlite3.connect(vault_of(client).path,isolation_level=None)
    for sql in (f"DELETE FROM claim_sources WHERE claim_id='{c['id']}'",
                f"UPDATE claim_sources SET record_id='{fixed['id']}' WHERE claim_id='{c['id']}'",
                f"INSERT INTO claim_sources(claim_id,record_id) VALUES ('{c['id']}','{fixed['id']}')",
                f"UPDATE records SET status='active' WHERE id='{rec['id']}'"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    db.close()
    assert authoritative(client)==set() and claims(client)[c["id"]]["support"]=="stale"

def test_missing_evidence_cannot_be_substituted_to_gain_authority(client,tmp_path):
    rec=create(client,"Invented genuine note")
    c=claim(client,[rec["id"]]); act(client,c["id"],"approve")
    backup=client.get("/api/export").json()
    partial={**backup,"records":[]}            # a backup missing the evidence
    target=new_client(tmp_path,"t.db"); restore(target,partial)
    assert claims(target)[c["id"]]["support"]=="orphaned"
    substitute={**rec,"content":"Invented forged note"}
    result=target.post("/api/import",json={"schema":"sovereign.v0.records.2","records":[substitute],"tombstones":[]}).json()
    assert result["imported"]==0 and result["records_skipped"]==1   # cited by an existing claim: refused
    restored=claims(target)[c["id"]]
    assert restored["sources"][0]["state"]=="missing" and not restored["authoritative"]
    assert target.get("/api/memories").json()["records"]==[]
    # The genuine evidence cannot then be swapped in either: records are immutable.
    assert restore(target,backup)["imported"]==0 and authoritative(target)==set()

def test_imported_claims_attach_only_to_present_evidence(client):
    """An untrusted file cannot link a claim to an absent record id (which would block that
    evidence from ever being introduced later, e.g. by a genuine trusted restore)."""
    payload=forged_payload(FOREIGN_RECORD)
    result=client.post("/api/import",json={**payload,"records":[]}).json()
    assert result["claims_imported_as_proposed"]==0 and result["claims_skipped"]==1
    assert client.get("/api/export").json()["claims"]==[]
    # The evidence id stays free: the genuine record can still arrive.
    assert client.post("/api/import",json={**payload,"claims":[]}).json()["imported"]==1
    assert authoritative(client)==set()

# --- Blocker 6: concurrent decisions produce one replayable history ---------------------------

def race(vault_path, claim_id, targets):
    results, barrier = {}, threading.Barrier(len(targets))
    def worker(target):
        v=Vault(vault_path)
        barrier.wait()
        try:
            v.transition_claim(claim_id,target,expected_status="proposed")
            results[target]="ok"
        except ValueError as exc:   # TransitionError is a ValueError
            results[target]=f"conflict: {exc}"
    threads=[threading.Thread(target=worker,args=(t,)) for t in targets]
    for t in threads: t.start()
    for t in threads: t.join()
    return results

def test_concurrent_conflicting_decisions(tmp_path):
    vault=Vault(str(tmp_path / "race.db"))
    rec=vault.add("Invented note")
    for i in range(40):
        c=vault.add_claim(f"Claim {i}",[rec["id"]],"model")
        results=race(vault.path,c["id"],["approved","rejected"])
        assert sorted(v=="ok" for v in results.values())==[False,True], results
        final={x["id"]:x for x in vault.list_claims()}[c["id"]]
        winner=next(t for t,v in results.items() if v=="ok")
        assert final["status"]==winner and [e["to_status"] for e in final["history"]]==["proposed",winner]
    replay=Vault(str(tmp_path / "replay.db"))
    assert replay.restore_trusted(vault.export())["claims_restored"]==40

def test_concurrent_decision_without_expected_status_still_serialises(tmp_path):
    vault=Vault(str(tmp_path / "race.db"))
    rec=vault.add("Invented note")
    for i in range(20):
        c=vault.add_claim(f"Claim {i}",[rec["id"]],"model")
        results, barrier = {}, threading.Barrier(2)
        def worker(target):
            v=Vault(vault.path); barrier.wait()
            try:
                v.transition_claim(c["id"],target); results[target]="ok"
            except ValueError:
                results[target]="conflict"
        threads=[threading.Thread(target=worker,args=(t,)) for t in ("approved","contested")]
        for t in threads: t.start()
        for t in threads: t.join()
        history=[e["to_status"] for e in {x["id"]:x for x in vault.list_claims()}[c["id"]]["history"]]
        # Either both apply in a legal serial order, or one conflicts; never a contradictory history.
        assert history in (["proposed","approved","contested"],["proposed","contested","approved"],
                           ["proposed","approved"],["proposed","contested"])
    Vault(str(tmp_path / "replay.db")).restore_trusted(vault.export())

def test_storage_compare_and_set_rejects_stale_writer(tmp_path):
    """Two writers both observed `proposed`; the trigger lets only the first commit."""
    vault=Vault(str(tmp_path / "cas.db"))
    rec=vault.add("Invented note")
    c=vault.add_claim("Claim",[rec["id"]],"model")
    a=sqlite3.connect(vault.path,isolation_level=None); b=sqlite3.connect(vault.path,isolation_level=None)
    assert a.execute("SELECT status FROM claims").fetchone()[0]==b.execute("SELECT status FROM claims").fetchone()[0]=="proposed"
    a.execute(f"INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{c['id']}','proposed','approved','human','{T}')")
    with pytest.raises(sqlite3.IntegrityError, match="stale"):
        b.execute(f"INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES ('{c['id']}','proposed','rejected','human','{T}')")
    a.close(); b.close()
    assert [e["to_status"] for e in vault.list_claims()[0]["history"]]==["proposed","approved"]

def test_concurrent_api_conflict_returns_409(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"approve",expected_status="proposed")
    act(client,c["id"],"reject",expect=409,expected_status="proposed")
    act(client,c["id"],"supersede",expect=409,expected_status="proposed",text="x",source_ids=[rec["id"]])
    assert [e["to_status"] for e in claims(client)[c["id"]]["history"]]==["proposed","approved"]

def test_api_decisions_require_expected_status(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    for action in ("approve","reject","contest"):
        assert client.post(f"/api/claims/{c['id']}/{action}",json=CONFIRM).status_code==422
    assert client.post(f"/api/claims/{c['id']}/supersede",json={**CONFIRM,"text":"t","source_ids":[rec["id"]]}).status_code==422
    assert claims(client)[c["id"]]["status"]=="proposed"

def test_concurrent_http_decisions_exactly_one_wins(tmp_path):
    path=str(tmp_path / "http.db")
    seed=TestClient(create_app(path))
    rec=create(seed)
    # Two app instances over one vault (like two server processes). Apps are built up front:
    # FastAPI/pydantic app construction is not thread-safe and is not what this test races.
    servers={a:TestClient(create_app(path)) for a in ("approve","reject")}
    for i in range(25):
        c=claim(seed,[rec["id"]],f"Claim {i}")
        results, barrier = {}, threading.Barrier(2)
        def worker(action):
            barrier.wait()
            results[action]=servers[action].post(f"/api/claims/{c['id']}/{action}",
                                                 json={**CONFIRM,"expected_status":"proposed"}).status_code
        threads=[threading.Thread(target=worker,args=(a,)) for a in ("approve","reject")]
        for t in threads: t.start()
        for t in threads: t.join()
        assert sorted(results.values())==[200,409], results
        assert len(claims(seed)[c["id"]]["history"])==2
    assert Vault(str(tmp_path / "replay.db")).restore_trusted(seed.app.state.vault.export())["claims_restored"]==25
