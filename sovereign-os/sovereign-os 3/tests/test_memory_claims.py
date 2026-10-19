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

def claim(client, source_ids, text="The garden project starts in May"):
    resp=client.post("/api/claims",json={"text":text,"source_ids":source_ids})
    assert resp.status_code==201, resp.text
    return resp.json()

def model_claim(client, source_ids, text="Model reading"):
    # Internal path reserved for future model extraction; not reachable from the browser.
    return client.app.state.vault.add_claim(text, source_ids, "model")

def act(client, claim_id, action, expect=200, **body):
    if "expected_status" not in body:   # the UI always sends the status it displayed
        current=client.get("/api/claims").json()["claims"]
        body["expected_status"]=next((c["status"] for c in current if c["id"]==claim_id),"proposed")
    resp=client.post(f"/api/claims/{claim_id}/{action}",json={**CONFIRM,**body})
    assert resp.status_code==expect, resp.text
    return resp.json()

def claims(client, **params):
    return {c["id"]: c for c in client.get("/api/claims",params=params).json()["claims"]}

def restore(client, backup, expect=200):
    resp=client.post("/api/restore",json={"confirm_trusted_restore":True,"backup":backup})
    assert resp.status_code==expect, resp.text
    return resp.json()

def statuses(c):
    return [(e["from_status"],e["to_status"],e["actor"]) for e in c["history"]]

# 1. AI/inferred claims default to proposed, with provenance

def test_model_claim_defaults_to_proposed_with_provenance(client):
    rec=create(client)
    c=model_claim(client,[rec["id"]])
    assert c["status"]=="proposed" and not c["authoritative"] and c["support"]=="supported"
    assert c["origin"]=="model" and c["created_at"] and c["supersedes_id"] is None
    assert c["sources"]==[{"id":rec["id"],"state":"active","content":rec["content"],"sensitivity":"private"}]
    assert statuses(c)==[(None,"proposed","model")]
    assert claim(client,[rec["id"]])["origin"]=="human"
    assert client.get("/api/memories").json()["records"]==[rec]   # evidence unchanged

@pytest.mark.parametrize("smuggled",[{"status":"approved"},{"status":"contested"},{"history":[]},
                                     {"authoritative":True},{"supersedes_id":"x"},{"origin":"model"},{"origin":"human"}])
def test_browser_cannot_set_authority_or_provenance(client,smuggled):
    rec=create(client)
    resp=client.post("/api/claims",json={"text":"x","source_ids":[rec["id"]],**smuggled})
    assert resp.status_code==422
    assert claims(client)=={}

# 2. Proposed claims are not authoritative

def test_only_approved_supported_claims_are_authoritative(client):
    rec=create(client)
    p=model_claim(client,[rec["id"]])
    c=claim(client,[rec["id"]],"contested one"); act(client,c["id"],"contest",note="Conflicts with my calendar")
    a=claim(client,[rec["id"]],"approved one"); act(client,a["id"],"approve")
    assert {k:v["authoritative"] for k,v in claims(client).items()}=={p["id"]:False,c["id"]:False,a["id"]:True}
    assert list(claims(client,status="approved"))==[a["id"]]
    assert client.get("/api/claims",params={"status":"bogus"}).status_code==422

# 3/4. Explicit, recorded approval and rejection

def test_explicit_approval_is_recorded(client):
    rec=create(client)
    c=model_claim(client,[rec["id"]])
    for body in ({},{"confirm":False},{"confirm":"yes"}):
        assert client.post(f"/api/claims/{c['id']}/approve",json=body).status_code==422
    assert claims(client)[c["id"]]["status"]=="proposed"
    approved=act(client,c["id"],"approve",note="Matches the source")
    assert approved["status"]=="approved" and approved["authoritative"]
    assert statuses(approved)==[(None,"proposed","model"),("proposed","approved","human")]
    assert approved["history"][1]["note"]=="Matches the source"

def test_explicit_rejection_and_immediate_revocation(client):
    rec=create(client)
    c=model_claim(client,[rec["id"]])
    assert act(client,c["id"],"reject",note="Misreads the note")["status"]=="rejected"
    a=claim(client,[rec["id"]],"Approved then revoked")
    act(client,a["id"],"approve")
    revoked=act(client,a["id"],"reject",note="Changed my mind")   # no contest step required
    assert revoked["status"]=="rejected" and not revoked["authoritative"]
    assert statuses(revoked)[-1]==("approved","rejected","human")

def test_expected_status_compare_and_set(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"approve",expected_status="proposed")
    act(client,c["id"],"reject",expect=409,expected_status="proposed")   # stale view
    assert claims(client)[c["id"]]["status"]=="approved"

def test_decisions_reject_cross_origin_and_non_json(client):
    rec=create(client)
    c=model_claim(client,[rec["id"]])
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
    c=model_claim(client,[rec["id"]])
    act(client,c["id"],"reject")
    for action in ("approve","contest","reject"):
        act(client,c["id"],action,expect=409)
    act(client,c["id"],"supersede",expect=409,text="Reworded",source_ids=[rec["id"]])
    final=claims(client)[c["id"]]
    assert final["status"]=="rejected" and len(final["history"])==2 and len(claims(client))==1

def test_transition_table():
    assert TRANSITIONS["rejected"]==TRANSITIONS["superseded"]==frozenset()
    check_transition("approved","rejected")
    with pytest.raises(TransitionError):
        check_transition("rejected","approved")
    with pytest.raises(TransitionError):
        check_transition("proposed","approved","orphaned")

# 6. Contested and superseded preserve provenance

def test_contest_then_resolve(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"approve")
    contested=act(client,c["id"],"contest",note="My diary says June")
    assert contested["status"]=="contested" and not contested["authoritative"]
    act(client,c["id"],"contest",expect=409)
    resolved=act(client,c["id"],"approve",note="Checked: May is right")
    assert resolved["authoritative"]
    assert statuses(resolved)==[(None,"proposed","human"),("proposed","approved","human"),
                                ("approved","contested","human"),("contested","approved","human")]

def test_supersede_creates_linked_proposed_replacement(client):
    old_rec=create(client)
    c=model_claim(client,[old_rec["id"]])
    act(client,c["id"],"approve")
    new_rec=create(client,"Invented note: the garden project starts in June")
    result=act(client,c["id"],"supersede",text="The garden project starts in June",source_ids=[new_rec["id"]],note="Plans changed")
    old,new=result["superseded"],result["replacement"]
    assert old["status"]=="superseded" and not old["authoritative"] and old["superseded_by"]==new["id"]
    assert old["text"]=="Model reading" and old["source_ids"]==[old_rec["id"]]
    assert statuses(old)[-1]==("approved","superseded","human")
    assert new["status"]=="proposed" and new["supersedes_id"]==c["id"] and new["origin"]=="human"
    for action in ("approve","contest","reject"):
        act(client,c["id"],action,expect=409)

def test_failed_supersede_changes_nothing(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"supersede",expect=422,text="t",source_ids=["nonexistent"])
    assert claims(client)[c["id"]]["status"]=="proposed" and len(claims(client))==1

def test_source_correction_makes_claim_stale(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    act(client,c["id"],"approve")
    client.post(f"/api/memories/{rec['id']}/correct",json={"content":"Invented note: starts in June"})
    stale=claims(client)[c["id"]]
    assert stale["status"]=="approved" and stale["support"]=="stale" and not stale["authoritative"]
    assert stale["sources"][0]["state"]=="superseded"
    act(client,c["id"],"approve",expect=409)
    assert client.post("/api/claims",json={"text":"t","source_ids":[rec["id"]]}).status_code==422

@pytest.mark.parametrize("source_ids",[[],["nonexistent"],["dup","dup"],["ok","nonexistent"],[f"id{i}" for i in range(9)]])
def test_invalid_source_ids_fail_safely(client,source_ids):
    rec=create(client)
    ids=[rec["id"] if s in ("dup","ok") else s for s in source_ids]
    assert client.post("/api/claims",json={"text":"Unsupported","source_ids":ids}).status_code==422
    assert claims(client)=={}

# 7. Source deletion = forget: dependent claims are forgotten too

def test_forgetting_a_source_forgets_dependent_claims(client):
    keep,gone=create(client,"Invented note A"),create(client,"Invented note B")
    both=claim(client,[keep["id"],gone["id"]],"A and B restated"); act(client,both["id"],"approve")
    only_b=model_claim(client,[gone["id"]],"B restated by model")
    only_a=claim(client,[keep["id"]],"A only")
    result=client.delete(f"/api/memories/{gone['id']}").json()
    assert result["records_forgotten"]==1 and result["claims_forgotten"]==2
    assert list(claims(client))==[only_a["id"]]
    export=client.get("/api/export").json()
    assert "restated" not in str(export) and "Invented note B" not in str(export)
    assert {t["id"] for t in export["claim_tombstones"]}=={both["id"],only_b["id"]}

def test_forgetting_a_corrected_source_forgets_claims_on_earlier_revisions(client):
    rec=create(client)
    c=claim(client,[rec["id"]],"About the first version")
    fixed=client.post(f"/api/memories/{rec['id']}/correct",json={"content":"Invented note v2"}).json()
    assert client.delete(f"/api/memories/{fixed['id']}").json()["claims_forgotten"]==1
    assert claims(client)=={}

def test_deleting_a_claim_forgets_it(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    assert client.delete(f"/api/claims/{c['id']}").status_code==200
    assert claims(client)=={} and client.get("/api/memories").json()["records"]==[rec]

# 8. Export / trusted restore preserves claim state and provenance

def lifecycle_fixture(client):
    a,b=create(client,"Invented note A"),create(client,"Invented note B")
    approved=claim(client,[a["id"]],"A claim"); act(client,approved["id"],"approve",note="ok")
    proposed=model_claim(client,[b["id"]],"B claim")
    rejected=model_claim(client,[a["id"]],"Rejected"); act(client,rejected["id"],"reject")
    contested=claim(client,[a["id"]],"Contested"); act(client,contested["id"],"contest",note="unsure")
    live=claim(client,[b["id"]],"Still approved"); act(client,live["id"],"approve")
    replaced=act(client,approved["id"],"supersede",text="A claim v2",source_ids=[a["id"]])["replacement"]
    return a,b,{"superseded":approved,"proposed":proposed,"rejected":rejected,"contested":contested,
                "approved":live,"replacement":replaced}

def test_trusted_restore_preserves_state_and_history(client,tmp_path):
    a,b,made=lifecycle_fixture(client)
    before=claims(client)
    snapshot=client.get("/api/export").json()
    assert snapshot["schema"]=="sovereign.v0.records.2" and len(snapshot["claims"])==6
    second=TestClient(create_app(str(tmp_path / "new.db")))
    assert restore(second,snapshot)=={"imported":2,"records_skipped":0,"claims_restored":6,"approved_claims_restored":1,
                                      "claims_skipped_existing":0,"claims_skipped_conflict":0,"claims_forgotten":0}
    assert claims(second)==before
    assert restore(second,snapshot)["claims_skipped_existing"]==6
    assert claims(second)==before

def test_restore_requires_explicit_trust(client):
    snapshot=client.get("/api/export").json()
    for body in ({"backup":snapshot},{"confirm_trusted_restore":False,"backup":snapshot},snapshot):
        assert client.post("/api/restore",json=body).status_code==422

def test_ordinary_import_never_grants_authority(client,tmp_path):
    a,b,made=lifecycle_fixture(client)
    snapshot=client.get("/api/export").json()
    second=TestClient(create_app(str(tmp_path / "new.db")))
    result=second.post("/api/import",json=snapshot).json()
    assert result=={"imported":2,"records_skipped":0,"claims_imported_as_proposed":4,"claims_skipped":2}
    now=claims(second)
    # Imported claims get fresh namespaced ids: a file can never occupy a genuine claim's id.
    assert not set(now) & {c["id"] for c in made.values()}
    assert sorted(c["text"] for c in now.values())==sorted(made[k]["text"] for k in ("proposed","contested","approved","replacement"))
    assert all(c["status"]=="proposed" and c["origin"]=="imported" and not c["authoritative"] for c in now.values())
    assert made["rejected"]["id"] not in now and made["superseded"]["id"] not in now
    assert all(statuses(c)==[(None,"proposed","imported")] and "not trusted" in c["history"][0]["note"] for c in now.values())

def test_restore_does_not_resurrect_forgotten_evidence_or_claims(client,tmp_path):
    a,b,made=lifecycle_fixture(client)
    snapshot=client.get("/api/export").json()
    second=TestClient(create_app(str(tmp_path / "new.db")))
    restore(second,snapshot)
    second.delete(f"/api/memories/{b['id']}")
    second.delete(f"/api/claims/{made['contested']['id']}")
    for _ in range(2):
        assert restore(second,snapshot)["claims_restored"]==0
        assert second.post("/api/import",json=snapshot).json()["claims_imported_as_proposed"]==0
    assert [r["id"] for r in second.get("/api/memories").json()["records"]]==[a["id"]]
    now=claims(second)
    assert made["proposed"]["id"] not in now and made["approved"]["id"] not in now and made["contested"]["id"] not in now

def test_v1_export_still_imports(client,tmp_path):
    rec=create(client)
    target=TestClient(create_app(str(tmp_path / "t.db")))
    assert target.post("/api/import",json={"schema":"sovereign.v0.records.1","records":[rec],"tombstones":[]}).json()["imported"]==1

def test_validate_history_accepts_legal_lifecycle():
    t="2026-10-18T00:00:00+00:00"
    validate_history([{"from_status":None,"to_status":"proposed","actor":"model","at":t},
                      {"from_status":"proposed","to_status":"contested","actor":"human","at":t},
                      {"from_status":"contested","to_status":"superseded","actor":"human","at":t}],"model","superseded")

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
    columns="id,content,source,sensitivity,status,created_at,supersedes_id"   # every ADR-0002 column
    db=sqlite3.connect(path); before=(db.execute(f"SELECT {columns} FROM records ORDER BY id").fetchall(),
                                      db.execute("SELECT * FROM tombstones").fetchall()); db.close()
    vault=Vault(path)
    db=sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0]==SCHEMA_VERSION==4
    assert (db.execute(f"SELECT {columns} FROM records ORDER BY id").fetchall(),db.execute("SELECT * FROM tombstones").fetchall())==before
    assert db.execute("SELECT DISTINCT legacy FROM records").fetchall()==[(1,)]   # pre-claims rows are flagged legacy
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
    assert db.execute("SELECT name FROM sqlite_master WHERE name='claims' OR type='trigger'").fetchone() is None
    assert db.execute("SELECT count(*) FROM records").fetchone()[0]==2
    db.close()
    monkeypatch.undo()
    assert [r["id"] for r in Vault(path).search()]==["r2"]

@pytest.mark.parametrize("setup,match",[(f"PRAGMA user_version={SCHEMA_VERSION+1}","newer"),
                                        ("PRAGMA user_version=1","pre-release"),
                                        ("PRAGMA user_version=2","pre-release"),
                                        ("PRAGMA user_version=3","pre-release"),
                                        ("CREATE TABLE claims (id TEXT)","pre-release")])
def test_newer_and_prerelease_vaults_are_refused(tmp_path,setup,match):
    path=base_vault(str(tmp_path / "v.db"))
    db=sqlite3.connect(path); db.execute(setup); db.commit(); db.close()
    with pytest.raises(RuntimeError, match=match):
        Vault(path)

# 10. Cloud disclosure boundaries are not weakened

def test_claims_are_never_sent_to_cloud(client,monkeypatch):
    rec=create(client)
    c=claim(client,[rec["id"]],"Claim text that must stay local")
    act(client,c["id"],"approve")
    seen=[]
    monkeypatch.setattr(providers,"available",lambda:[{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda p,m:seen.append(m) or "ok")
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
