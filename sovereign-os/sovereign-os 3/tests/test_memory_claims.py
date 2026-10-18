from fastapi.testclient import TestClient
import pytest
from sovereign.app import create_app
from sovereign import providers

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

def claims(client):
    return {c["id"]: c for c in client.get("/api/claims").json()["claims"]}

def test_claim_defaults_to_proposed_with_provenance(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    assert c["status"]=="proposed" and c["decided_at"] is None and not c["authoritative"]
    assert c["source_ids"]==[rec["id"]] and c["origin"]=="model" and c["created_at"] and c["support"]=="supported"
    assert claim(client,[rec["id"]])["origin"]=="human"
    # The source record is evidence and is unchanged by claim creation.
    assert client.get("/api/memories").json()["records"]==[rec]

@pytest.mark.parametrize("smuggled",[{"status":"approved"},{"decided_at":"2026-01-01T00:00:00+00:00"},{"authoritative":True}])
def test_create_cannot_set_authority(client,smuggled):
    rec=create(client)
    resp=client.post("/api/claims",json={"text":"x","source_ids":[rec["id"]],"origin":"model",**smuggled})
    assert resp.status_code==422
    assert claims(client)=={}

def test_explicit_approve_and_reject(client):
    rec=create(client)
    a,b=claim(client,[rec["id"]]),claim(client,[rec["id"]],"Another reading",origin="model")
    assert client.post(f"/api/claims/{a['id']}/approve",json={}).status_code==422  # confirm required
    assert client.post(f"/api/claims/{a['id']}/approve",json={"confirm":False}).status_code==422
    approved=client.post(f"/api/claims/{a['id']}/approve",json=CONFIRM).json()
    assert approved["status"]=="approved" and approved["decided_at"] and approved["authoritative"]
    rejected=client.post(f"/api/claims/{b['id']}/reject",json=CONFIRM).json()
    assert rejected["status"]=="rejected" and not rejected["authoritative"]
    # Decisions are final in V0: no flip-flopping or re-deciding.
    assert client.post(f"/api/claims/{b['id']}/approve",json=CONFIRM).status_code==409
    assert client.post(f"/api/claims/{a['id']}/reject",json=CONFIRM).status_code==409
    assert client.post("/api/claims/nonexistent/approve",json=CONFIRM).status_code==404

def test_decision_rejects_cross_origin_and_non_json(client):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    assert client.post(f"/api/claims/{c['id']}/approve",json=CONFIRM,headers={"Origin":"https://attacker.invalid"}).status_code==403
    assert client.post(f"/api/claims/{c['id']}/approve",content="confirm=true",headers={"Content-Type":"application/x-www-form-urlencoded"}).status_code==415
    assert claims(client)[c["id"]]["status"]=="proposed"

@pytest.mark.parametrize("source_ids",[[],["nonexistent"],["dup","dup"],[f"id{i}" for i in range(9)]])
def test_invalid_source_ids_fail_safely(client,source_ids):
    rec=create(client)
    ids=[rec["id"] if s=="dup" else s for s in source_ids]
    resp=client.post("/api/claims",json={"text":"Unsupported","source_ids":ids})
    assert resp.status_code==422
    assert claims(client)=={}

def test_mixed_valid_and_missing_source_creates_nothing(client):
    rec=create(client)
    assert client.post("/api/claims",json={"text":"t","source_ids":[rec["id"],"nonexistent"]}).status_code==422
    assert claims(client)=={}

def test_superseded_source_cannot_back_new_claim_and_stales_existing(client):
    rec=create(client)
    c=claim(client,[rec["id"]])
    client.post(f"/api/memories/{rec['id']}/correct",json={"content":"Invented note: the garden project starts in June"})
    assert client.post("/api/claims",json={"text":"t","source_ids":[rec["id"]]}).status_code==422
    stale=claims(client)[c["id"]]
    assert stale["support"]=="stale" and not stale["authoritative"]
    assert client.post(f"/api/claims/{c['id']}/approve",json=CONFIRM).status_code==409

def test_source_deletion_orphans_dependent_claims(client):
    keep,gone=create(client,"Invented note A"),create(client,"Invented note B")
    approved=claim(client,[keep["id"],gone["id"]],"A and B")
    client.post(f"/api/claims/{approved['id']}/approve",json=CONFIRM)
    pending=claim(client,[gone["id"]],"B only",origin="model")
    unrelated=claim(client,[keep["id"]],"A only")
    assert client.delete(f"/api/memories/{gone['id']}").status_code==200
    now=claims(client)
    assert now[approved["id"]]["support"]=="orphaned" and now[approved["id"]]["status"]=="approved"
    assert not now[approved["id"]]["authoritative"]
    assert now[pending["id"]]["support"]=="orphaned"
    assert client.post(f"/api/claims/{pending['id']}/approve",json=CONFIRM).status_code==409
    assert now[unrelated["id"]]["support"]=="supported"
    # Deleting the claim itself tombstones it.
    assert client.delete(f"/api/claims/{pending['id']}").status_code==200
    assert pending["id"] not in claims(client)
    assert client.delete(f"/api/claims/{pending['id']}").status_code==404

def test_export_restore_preserves_authority_without_resurrection(client,tmp_path):
    a,b=create(client,"Invented note A"),create(client,"Invented note B")
    approved=claim(client,[a["id"]],"A claim")
    client.post(f"/api/claims/{approved['id']}/approve",json=CONFIRM)
    proposed=claim(client,[b["id"]],"B claim",origin="model")
    rejected=claim(client,[a["id"]],"Rejected claim",origin="model")
    client.post(f"/api/claims/{rejected['id']}/reject",json=CONFIRM)
    snapshot=client.get("/api/export").json()
    assert snapshot["schema"]=="sovereign.v0.records.2" and len(snapshot["claims"])==3

    second=TestClient(create_app(str(tmp_path / "new.db")))
    result=second.post("/api/import",json=snapshot).json()
    assert result=={"imported":2,"claims_imported":3,"approved_claims_restored":1}
    restored=claims(second)
    assert {k:(v["status"],v["origin"],v["support"]) for k,v in restored.items()}=={
        approved["id"]:("approved","human","supported"),
        proposed["id"]:("proposed","model","supported"),
        rejected["id"]:("rejected","model","supported")}

    # Delete evidence B on the restored vault, then re-import the old snapshot.
    second.delete(f"/api/memories/{b['id']}")
    assert second.post("/api/import",json=snapshot).json()=={"imported":0,"claims_imported":0,"approved_claims_restored":0}
    assert [r["id"] for r in second.get("/api/memories").json()["records"]]==[a["id"]]
    assert claims(second)[proposed["id"]]["support"]=="orphaned"
    # A deleted claim is also not resurrected.
    second.delete(f"/api/claims/{rejected['id']}")
    second.post("/api/import",json=snapshot)
    assert rejected["id"] not in claims(second)

def test_import_cannot_elevate_existing_claim(client,tmp_path):
    rec=create(client)
    c=claim(client,[rec["id"]],origin="model")
    snapshot=client.get("/api/export").json()
    forged=[{**x,"status":"approved","decided_at":"2026-10-18T00:00:00+00:00"} for x in snapshot["claims"]]
    assert client.post("/api/import",json={**snapshot,"claims":forged}).json()["claims_imported"]==0
    assert claims(client)[c["id"]]["status"]=="proposed"

@pytest.mark.parametrize("bad",[{"status":"approved","decided_at":None},{"status":"active"},{"origin":"system"},
                                {"source_ids":[]},{"text":""},{"status":"proposed","decided_at":"2026-10-18T00:00:00+00:00"}])
def test_import_rejects_malformed_claims_atomically(client,tmp_path,bad):
    rec=create(client)
    claim(client,[rec["id"]])
    snapshot=client.get("/api/export").json()
    target=TestClient(create_app(str(tmp_path / "t.db")))
    resp=target.post("/api/import",json={**snapshot,"claims":[{**snapshot["claims"][0],**bad}]})
    assert resp.status_code==422
    assert target.get("/api/memories").json()["records"]==[] and claims(target)=={}

def test_v1_export_still_imports(client,tmp_path):
    rec=create(client)
    v1={"schema":"sovereign.v0.records.1","records":[rec],"tombstones":[]}
    target=TestClient(create_app(str(tmp_path / "t.db")))
    assert target.post("/api/import",json=v1).json()["imported"]==1

def test_claims_are_never_sent_to_cloud(client,monkeypatch):
    rec=create(client)
    c=claim(client,[rec["id"]],"Claim text that must stay local")
    client.post(f"/api/claims/{c['id']}/approve",json=CONFIRM)
    seen=[]
    monkeypatch.setattr(providers,"available",lambda:[{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda p,m:seen.append(m) or "ok")
    # A claim ID is not a source record and cannot be used as cloud context.
    assert client.post("/api/ask",json={"question":"Q","provider":"kimi","source_ids":[c["id"]],"approve_cloud_disclosure":True}).status_code==422
    ok=client.post("/api/ask",json={"question":"Q","provider":"kimi","source_ids":[rec["id"]],"approve_cloud_disclosure":True})
    assert ok.status_code==200 and len(seen)==1 and "Claim text" not in str(seen)

def test_cloud_restrictions_intact_with_claims(client,monkeypatch):
    secret=create(client,"Invented sensitive note","sensitive")
    c=claim(client,[secret["id"]],"Derived from sensitive")
    client.post(f"/api/claims/{c['id']}/approve",json=CONFIRM)
    seen=[]
    monkeypatch.setattr(providers,"available",lambda:[{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda p,m:seen.append(m) or "ok")
    payload={"question":"Q","provider":"kimi","source_ids":[secret["id"]]}
    assert client.post("/api/ask",json=payload).status_code==403
    assert client.post("/api/ask",json={**payload,"approve_cloud_disclosure":True}).status_code==403
    assert not seen
