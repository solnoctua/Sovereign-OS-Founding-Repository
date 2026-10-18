import sqlite3

from fastapi.testclient import TestClient
import pytest
from sovereign.app import create_app
from sovereign import providers
from sovereign.claims import TRANSITIONS, TransitionError, check_transition, validate_history
from sovereign.store import SCHEMA_VERSION, Vault

CONFIRM = {"confirm": True}

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "vault.db")))

def create(client, text="Invented note: the garden project starts in May", sensitivity="private"):
    resp=client.post("/api/memories",json={"content":text,"sensitivity":sensitivity})
    assert resp.status_code==201, resp.text
    return resp.json()

def claim(client, source_ids, text="The garden project starts in May", **extra):
    resp=client.post("/api/claims",json={"text":text,"source_ids":source_ids,**extra})
    assert resp.status_code==201, resp.text
    return resp.json()

def act(client, claim_id, action, expect=200, **body):
    resp=client.post(f"/api/claims/{claim_id}/{action}",json={**CONFIRM,**body})
    assert resp.status_code==expect, resp.text
    return resp.json()

def claims(client, **params):
    return {c["id"]: c for c in client.get("/api/claims",params=params).json()["claims"]}

def statuses(c):
    return [(e["from_status"],e["to_status"],e["actor"]) for e in c["history"]]

# 1. AI/inferred claims default to proposed, with provenance

def test_model_claim_defaults_to_proposed_with_provenance(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    assert c["status"]=="proposed" and not c["authoritative"] and c["support"]=="supported"
    assert c["origin"]=="model" and c["created_at"] and c["supersedes_id"] is None
    assert c["source_ids"]==[rec["id"]]
    assert c["sources"]==[{"id":rec["id"],"state":"active","content":rec["content"],"sensitivity":"private"}]
    assert statuses(c)==[(None,"proposed","model")]
    assert claim(client,[rec["id"]])["origin"]=="human"
    # Evidence is unchanged by deriving a claim from it.
    assert client.get("/api/memories").json()["records"]==[rec]

@pytest.mark.parametrize("smuggled",[{"status":"approved"},{"status":"contested"},{"history":[]},
                                     {"authoritative":True},{"supersedes_id":"x"}])
def test_create_cannot_set_authority(client,smuggled):
    rec=create(client)
    resp=client.post("/api/claims",json={"text":"x","source_ids":[rec["id"]],"origin":"model",**smuggled})
    assert resp.status_code==422
    assert claims(client)=={}

# 2. Proposed claims are not authoritative

def test_only_approved_supported_claims_are_authoritative(client):
    rec=create(client)
    p=claim(client,[rec["id"]],origin="model")
    c=claim(client,[rec["id"]],"contested one")
    act(client,c["id"],"contest",note="Conflicts with my calendar")
    a=claim(client,[rec["id"]],"approved one")
    act(client,a["id"],"approve")
    now=claims(client)
    assert {k:v["authoritative"] for k,v in now.items()}=={p["id"]:False,c["id"]:False,a["id"]:True}
    assert list(claims(client,status="approved"))==[a["id"]]
    assert list(claims(client,status="proposed"))==[p["id"]]
    assert client.get("/api/claims",params={"status":"bogus"}).status_code==422

# 3/4. Explicit, recorded approval and rejection

def test_explicit_approval_is_recorded(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    for body in ({},{"confirm":False},{"confirm":"yes"}):
        assert client.post(f"/api/claims/{c['id']}/approve",json=body).status_code==422
    assert claims(client)[c["id"]]["status"]=="proposed"
    approved=act(client,c["id"],"approve",note="Matches the source")
    assert approved["status"]=="approved" and approved["authoritative"]
    assert statuses(approved)==[(None,"proposed","model"),("proposed","approved","human")]
    assert approved["history"][1]["note"]=="Matches the source" and approved["history"][1]["at"]

def test_explicit_rejection_is_recorded(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    rejected=act(client,c["id"],"reject",note="Misreads the note")
    assert rejected["status"]=="rejected" and not rejected["authoritative"]
    assert statuses(rejected)[-1]==("proposed","rejected","human")

def test_decisions_reject_cross_origin_and_non_json(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    assert client.post(f"/api/claims/{c['id']}/approve",json=CONFIRM,headers={"Origin":"https://attacker.invalid"}).status_code==403
    assert client.post(f"/api/claims/{c['id']}/approve",content="confirm=true",
                       headers={"Content-Type":"application/x-www-form-urlencoded"}).status_code==415
    assert claims(client)[c["id"]]["status"]=="proposed"

def test_unknown_claim_is_404(client):
    for action in ("approve","reject","contest"):
        act(client,"nonexistent",action,expect=404)
    rec=create(client)
    act(client,"nonexistent","supersede",expect=404,text="t",source_ids=[rec["id"]])
    assert client.delete("/api/claims/nonexistent").status_code==404

# 5. Rejected claims cannot silently reactivate

def test_rejected_claim_is_terminal(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    act(client,c["id"],"reject")
    for action in ("approve","contest","reject"):
        act(client,c["id"],action,expect=409)
    act(client,c["id"],"supersede",expect=409,text="Reworded",source_ids=[rec["id"]])
    final=claims(client)[c["id"]]
    assert final["status"]=="rejected" and len(final["history"])==2 and len(claims(client))==1

def test_storage_layer_blocks_reactivation_and_unrecorded_changes(tmp_path):
    vault=Vault(str(tmp_path / "v.db"))
    rec=vault.add("Invented note")
    c=vault.add_claim("Claim",[rec["id"]],"model")
    db=sqlite3.connect(vault.path)
    with pytest.raises(sqlite3.IntegrityError, match="recorded"):
        db.execute("UPDATE claims SET status='approved' WHERE id=?",(c["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="proposed"):
        db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES ('x','t','model','approved','now')")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("UPDATE claims SET text='edited' WHERE id=?",(c["id"],))
    with pytest.raises(sqlite3.IntegrityError):  # a model may never be the actor of a decision
        db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES (?,?,?,?,?)",
                   (c["id"],"proposed","approved","model","now"))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE claim_events SET note='rewritten'")
    db.close()
    vault.transition_claim(c["id"],"rejected")
    db=sqlite3.connect(vault.path)
    db.execute("INSERT INTO claim_events(claim_id,from_status,to_status,actor,at) VALUES (?,?,?,?,?)",
               (c["id"],"rejected","approved","human","now"))
    with pytest.raises(sqlite3.IntegrityError, match="final"):
        db.execute("UPDATE claims SET status='approved' WHERE id=?",(c["id"],))
    db.close()

def test_transition_table_is_closed():
    for terminal in ("rejected","superseded"):
        assert TRANSITIONS[terminal]==frozenset()
    with pytest.raises(TransitionError):
        check_transition("approved","rejected")   # must be contested first
    with pytest.raises(TransitionError):
        check_transition("proposed","approved","orphaned")

# 6. Contested and superseded preserve provenance

def test_contest_then_resolve(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"approve")
    act(client,c["id"],"reject",expect=409)  # approved -> rejected needs contest first
    contested=act(client,c["id"],"contest",note="My diary says June")
    assert contested["status"]=="contested" and not contested["authoritative"]
    act(client,c["id"],"contest",expect=409)
    resolved=act(client,c["id"],"approve",note="Checked: May is right")
    assert resolved["authoritative"]
    assert statuses(resolved)==[(None,"proposed","human"),("proposed","approved","human"),
                                ("approved","contested","human"),("contested","approved","human")]
    other=claim(client,[rec["id"]],"Other")
    act(client,other["id"],"contest")
    assert act(client,other["id"],"reject")["status"]=="rejected"

def test_supersede_creates_linked_proposed_replacement(client):
    old_rec=create(client)
    c=claim(client,[old_rec["id"]],origin="model")
    act(client,c["id"],"approve")
    new_rec=create(client,"Invented note: the garden project starts in June")
    result=act(client,c["id"],"supersede",text="The garden project starts in June",
               source_ids=[new_rec["id"]],note="Plans changed")
    old,new=result["superseded"],result["replacement"]
    assert old["status"]=="superseded" and not old["authoritative"] and old["superseded_by"]==new["id"]
    assert old["text"]=="The garden project starts in May" and old["source_ids"]==[old_rec["id"]]
    assert statuses(old)[-1]==("approved","superseded","human") and old["history"][-1]["note"]=="Plans changed"
    assert new["status"]=="proposed" and not new["authoritative"]   # correction still needs approval
    assert new["supersedes_id"]==c["id"] and new["origin"]=="human" and new["source_ids"]==[new_rec["id"]]
    for action in ("approve","contest","reject"):
        act(client,c["id"],action,expect=409)
    act(client,c["id"],"supersede",expect=409,text="again",source_ids=[new_rec["id"]])

def test_failed_supersede_changes_nothing(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"supersede",expect=422,text="t",source_ids=["nonexistent"])
    assert claims(client)[c["id"]]["status"]=="proposed" and len(claims(client))==1

def test_source_correction_makes_claim_stale(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"approve")
    fixed=client.post(f"/api/memories/{rec['id']}/correct",json={"content":"Invented note: starts in June"}).json()
    stale=claims(client)[c["id"]]
    assert stale["status"]=="approved" and stale["support"]=="stale" and not stale["authoritative"]
    assert stale["sources"][0]["state"]=="superseded"
    other=claim(client,[fixed["id"]],"x")
    client.post(f"/api/memories/{fixed['id']}/correct",json={"content":"Invented note: July"})
    act(client,other["id"],"approve",expect=409)
    assert client.post("/api/claims",json={"text":"t","source_ids":[rec["id"]]}).status_code==422

# Invalid source IDs fail safely

@pytest.mark.parametrize("source_ids",[[],["nonexistent"],["dup","dup"],["ok","nonexistent"],[f"id{i}" for i in range(9)]])
def test_invalid_source_ids_fail_safely(client,source_ids):
    rec=create(client)
    ids=[rec["id"] if s in ("dup","ok") else s for s in source_ids]
    assert client.post("/api/claims",json={"text":"Unsupported","source_ids":ids}).status_code==422
    assert claims(client)=={}

# 7. Source deletion policy: dependent claims are orphaned (never authoritative), not deleted

def test_source_deletion_orphans_dependent_claims(client):
    keep,gone=create(client,"Invented note A"),create(client,"Invented note B")
    approved=claim(client,[keep["id"],gone["id"]],"A and B")
    act(client,approved["id"],"approve")
    pending=claim(client,[gone["id"]],"B only",origin="model")
    unrelated=claim(client,[keep["id"]],"A only")
    assert client.delete(f"/api/memories/{gone['id']}").status_code==200
    now=claims(client)
    orphan=now[approved["id"]]
    assert orphan["support"]=="orphaned" and orphan["status"]=="approved" and not orphan["authoritative"]
    assert {s["id"]:(s["state"],s["content"]) for s in orphan["sources"]}=={
        keep["id"]:("active","Invented note A"),gone["id"]:("deleted",None)}
    assert now[pending["id"]]["support"]=="orphaned"
    act(client,pending["id"],"approve",expect=409)
    assert now[unrelated["id"]]["support"]=="supported"
    # A claim can be deleted explicitly; it leaves a tombstone.
    assert client.delete(f"/api/claims/{pending['id']}").status_code==200
    assert pending["id"] not in claims(client)

# 8. Export/import preserves claim state and provenance

def lifecycle_fixture(client):
    a,b=create(client,"Invented note A"),create(client,"Invented note B")
    approved=claim(client,[a["id"]],"A claim"); act(client,approved["id"],"approve",note="ok")
    proposed=claim(client,[b["id"]],"B claim",origin="model")
    rejected=claim(client,[a["id"]],"Rejected",origin="model"); act(client,rejected["id"],"reject")
    contested=claim(client,[a["id"]],"Contested"); act(client,contested["id"],"contest",note="unsure")
    replaced=act(client,approved["id"],"supersede",text="A claim v2",source_ids=[a["id"]])["replacement"]
    return a,b,{"approved_then_superseded":approved,"proposed":proposed,"rejected":rejected,
                "contested":contested,"replacement":replaced}

def test_export_restore_preserves_state_and_history(client,tmp_path):
    a,b,made=lifecycle_fixture(client)
    before=claims(client)
    snapshot=client.get("/api/export").json()
    assert snapshot["schema"]=="sovereign.v0.records.2" and len(snapshot["claims"])==5
    second=TestClient(create_app(str(tmp_path / "new.db")))
    assert second.post("/api/import",json=snapshot).json()=={
        "imported":2,"claims_imported":5,"approved_claims_restored":0,"claims_skipped_existing":0}
    after=claims(second)
    assert after==before   # status, origin, sources, history (incl. timestamps/notes), supersession links
    assert after[made["replacement"]["id"]]["supersedes_id"]==made["approved_then_superseded"]["id"]
    # Idempotent re-import.
    assert second.post("/api/import",json=snapshot).json()["claims_skipped_existing"]==5
    assert claims(second)==before

def test_restore_does_not_resurrect_evidence_or_claims(client,tmp_path):
    a,b,made=lifecycle_fixture(client)
    snapshot=client.get("/api/export").json()
    second=TestClient(create_app(str(tmp_path / "new.db")))
    second.post("/api/import",json=snapshot)
    second.delete(f"/api/memories/{b['id']}")
    second.delete(f"/api/claims/{made['rejected']['id']}")
    result=second.post("/api/import",json=snapshot).json()
    assert result["imported"]==0 and result["claims_imported"]==0
    assert [r["id"] for r in second.get("/api/memories").json()["records"]]==[a["id"]]
    now=claims(second)
    assert made["rejected"]["id"] not in now
    assert now[made["proposed"]["id"]]["support"]=="orphaned"
    # A fresh vault importing evidence tombstones alongside claims: claims arrive orphaned.
    third=TestClient(create_app(str(tmp_path / "third.db")))
    third.post("/api/import",json=second.get("/api/export").json())
    assert claims(third)[made["proposed"]["id"]]["sources"][0]["state"]=="deleted"

def test_import_cannot_change_existing_decision(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    act(client,c["id"],"reject")
    snapshot=client.get("/api/export").json()
    forged=snapshot["claims"][0]
    forged={**forged,"status":"approved","history":forged["history"][:1]+[
        {"from_status":"proposed","to_status":"approved","actor":"human","note":None,"at":"2026-10-18T00:00:00+00:00"}]}
    assert client.post("/api/import",json={**snapshot,"claims":[forged]}).json()["claims_skipped_existing"]==1
    assert claims(client)[c["id"]]["status"]=="rejected"

def bad_history(claim):
    h=claim["history"]
    return [
        {"status":"approved","history":h[:1]},                                          # status without decision
        {"status":"approved","history":h},                                              # proposed history, approved status
        {"status":"approved","history":[{**h[0],"to_status":"approved"}]},             # created approved
        {"status":"approved","history":h[:1]+[{"from_status":"proposed","to_status":"approved","actor":"model","note":None,"at":"t"}]},
        {"status":"approved","history":h[:1]+[{"from_status":"rejected","to_status":"approved","actor":"human","note":None,"at":"t"}]},
        {"status":"approved","history":h[:1]+[
            {"from_status":"proposed","to_status":"rejected","actor":"human","note":None,"at":"t"},
            {"from_status":"rejected","to_status":"approved","actor":"human","note":None,"at":"t"}]},  # reactivation
        {"history":[{**h[0],"actor":"human"}]},                                         # origin/creator mismatch
        {"history":[]},{"status":"active"},{"origin":"system"},{"source_ids":[]},{"text":""},
    ]

def test_import_rejects_illegal_histories_atomically(client,tmp_path):
    rec=create(client)
    claim(client,[rec["id"]],origin="model")
    snapshot=client.get("/api/export").json()
    for bad in bad_history(snapshot["claims"][0]):
        target=TestClient(create_app(str(tmp_path / f"t{id(bad)}.db")))
        resp=target.post("/api/import",json={**snapshot,"claims":[{**snapshot["claims"][0],**bad}]})
        assert resp.status_code==422, bad
        assert target.get("/api/memories").json()["records"]==[] and claims(target)=={}

def test_validate_history_accepts_legal_lifecycle():
    t="2026-10-18T00:00:00+00:00"
    validate_history([{"from_status":None,"to_status":"proposed","actor":"model","at":t},
                      {"from_status":"proposed","to_status":"contested","actor":"human","at":t},
                      {"from_status":"contested","to_status":"superseded","actor":"human","at":t}],"model","superseded")

def test_v1_export_still_imports(client,tmp_path):
    rec=create(client)
    target=TestClient(create_app(str(tmp_path / "t.db")))
    assert target.post("/api/import",json={"schema":"sovereign.v0.records.1","records":[rec],"tombstones":[]}).json()["imported"]==1

# Migration of existing vaults

BASE_SQL="""
CREATE TABLE records (id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
  sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private','sensitive')), status TEXT NOT NULL CHECK(status IN ('active','superseded')),
  created_at TEXT NOT NULL, supersedes_id TEXT);
CREATE TABLE tombstones (id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
CREATE INDEX ix_records_status ON records(status,created_at);
INSERT INTO records VALUES ('r1','Invented old note','manual','private','superseded','2026-10-01T00:00:00+00:00',NULL);
INSERT INTO records VALUES ('r2','Invented corrected note','manual','private','active','2026-10-02T00:00:00+00:00','r1');
INSERT INTO tombstones VALUES ('r0','2026-10-03T00:00:00+00:00');
"""

def base_vault(path):
    db=sqlite3.connect(path); db.executescript(BASE_SQL); db.close()
    return path

def test_existing_vault_migrates_without_touching_evidence(tmp_path):
    path=base_vault(str(tmp_path / "old.db"))
    db=sqlite3.connect(path); before=(db.execute("SELECT * FROM records ORDER BY id").fetchall(),
                                      db.execute("SELECT * FROM tombstones").fetchall()); db.close()
    vault=Vault(path)
    db=sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0]==SCHEMA_VERSION
    assert (db.execute("SELECT * FROM records ORDER BY id").fetchall(),db.execute("SELECT * FROM tombstones").fetchall())==before
    db.close()
    assert [r["id"] for r in vault.search()]==["r2"] and vault.list_claims()==[]
    c=vault.add_claim("Derived",["r2"],"model")
    Vault(path)   # re-opening is idempotent
    assert vault.list_claims()[0]["id"]==c["id"]

def test_migration_rolls_back_on_failure(tmp_path,monkeypatch):
    path=base_vault(str(tmp_path / "old.db"))
    import sovereign.store as store
    monkeypatch.setattr(store,"CLAIMS_SCHEMA",store.CLAIMS_SCHEMA+"\nCREATE TABLE records (x);")  # forced failure
    with pytest.raises(sqlite3.OperationalError):
        Vault(path)
    db=sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0]==0
    assert db.execute("SELECT name FROM sqlite_master WHERE name='claims'").fetchone() is None
    assert db.execute("SELECT count(*) FROM records").fetchone()[0]==2
    db.close()
    monkeypatch.undo()
    assert [r["id"] for r in Vault(path).search()]==["r2"]

def test_newer_and_prerelease_vaults_are_refused(tmp_path):
    newer=str(tmp_path / "newer.db")
    db=sqlite3.connect(newer); db.execute(f"PRAGMA user_version={SCHEMA_VERSION+1}"); db.close()
    with pytest.raises(RuntimeError, match="newer"):
        Vault(newer)
    draft=base_vault(str(tmp_path / "draft.db"))
    db=sqlite3.connect(draft); db.execute("CREATE TABLE claims (id TEXT)"); db.close()
    with pytest.raises(RuntimeError, match="pre-release"):
        Vault(draft)

# 10. Cloud disclosure boundaries are not weakened

def test_claims_are_never_sent_to_cloud(client,monkeypatch):
    rec=create(client)
    c=claim(client,[rec["id"]],"Claim text that must stay local")
    act(client,c["id"],"approve")
    seen=[]
    monkeypatch.setattr(providers,"available",lambda:[{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda p,m:seen.append(m) or "ok")
    # A claim ID is not a source record and cannot be used as cloud context.
    assert client.post("/api/ask",json={"question":"Q","provider":"kimi","source_ids":[c["id"]],"approve_cloud_disclosure":True}).status_code==422
    ok=client.post("/api/ask",json={"question":"Q","provider":"kimi","source_ids":[rec["id"]],"approve_cloud_disclosure":True})
    assert ok.status_code==200 and len(seen)==1 and "Claim text" not in str(seen)

def test_cloud_restrictions_intact_with_approved_claims(client,monkeypatch):
    secret=create(client,"Invented sensitive note","sensitive")
    c=claim(client,[secret["id"]],"Derived from sensitive")
    act(client,c["id"],"approve")
    seen=[]
    monkeypatch.setattr(providers,"available",lambda:[{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda p,m:seen.append(m) or "ok")
    payload={"question":"Q","provider":"kimi","source_ids":[secret["id"]]}
    assert client.post("/api/ask",json=payload).status_code==403
    assert client.post("/api/ask",json={**payload,"approve_cloud_disclosure":True}).status_code==403
    assert not seen
