from fastapi.testclient import TestClient
import pytest
from sovereign.app import create_app
from sovereign import providers

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "vault.db")))

def create(client, text="I will study for math on Friday", sensitivity="private"):
    resp=client.post("/api/memories",json={"content":text,"sensitivity":sensitivity})
    assert resp.status_code==201, resp.text
    return resp.json()

def test_capture_recall_correct_delete(client):
    note=create(client)
    assert client.get("/api/memories",params={"q":"math"}).json()["records"][0]["id"]==note["id"]
    local=client.post("/api/ask",json={"question":"What must I study?","source_ids":[note["id"]],"provider":"local"})
    assert local.status_code==200 and not local.json()["cloud_disclosure"]
    corrected=client.post(f"/api/memories/{note['id']}/correct",json={"content":"I will study mathematics on Saturday"}).json()
    assert client.get("/api/memories",params={"q":"Friday"}).json()["records"]==[]
    assert len(client.get("/api/memories",params={"q":"Saturday"}).json()["records"])==1
    assert client.delete(f"/api/memories/{corrected['id']}").status_code==200
    assert client.get("/api/memories").json()["records"]==[]
    export=client.get("/api/export").json()
    assert len(export["tombstones"])==2
    assert "Friday" not in str(export)

def test_cloud_requires_grant_and_forbids_sensitive(client, monkeypatch):
    note=create(client)
    seen=[]
    monkeypatch.setattr(providers,"available",lambda:[{"id":"local","ready":True},{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda p,m:seen.append((p,m)) or "The answer")
    payload={"question":"Recall my note","provider":"kimi","source_ids":[note["id"]]}
    assert client.post("/api/ask",json=payload).status_code==403
    assert not seen
    # ADR-0004: approval binds to the exact previewed bundle, so approval alone is not enough.
    assert client.post("/api/ask",json={**payload,"approve_cloud_disclosure":True}).status_code==428
    assert not seen
    token=client.post("/api/context/compile",json=payload).json()["context_token"]
    allowed=client.post("/api/ask",json={**payload,"approve_cloud_disclosure":True,"context_token":token})
    assert allowed.status_code==200 and allowed.json()["cloud_disclosure"]
    assert len(seen)==1 and "I will study" in str(seen)
    secret=create(client,"Invented secret for a synthetic test","sensitive")
    denied=client.post("/api/ask",json={**payload,"source_ids":[secret["id"]],"approve_cloud_disclosure":True})
    assert denied.status_code==403 and len(seen)==1

def test_export_restore_and_tombstone_precedence(client,tmp_path):
    rec=create(client,"An invented project meeting")
    snapshot=client.get("/api/export").json()
    second=TestClient(create_app(str(tmp_path / "new.db")))
    assert second.post("/api/import",json=snapshot).json()["imported"]==1
    assert second.get("/api/memories").json()["records"][0]["id"]==rec["id"]
    second.delete(f"/api/memories/{rec['id']}")
    assert second.post("/api/import",json=snapshot).json()["imported"]==0
    assert second.get("/api/memories").json()["records"]==[]

def test_browser_origin_denied(client):
    assert client.post("/api/memories",json={"content":"Test"},headers={"Origin":"https://attacker.invalid"}).status_code==403

def test_requires_exact_selected_records(client,monkeypatch):
    note=create(client)
    monkeypatch.setattr(providers,"available",lambda:[{"id":"kimi","ready":True}])
    monkeypatch.setattr(providers,"generate",lambda *args: "Done")
    response=client.post("/api/ask",json={"provider":"kimi","question":"Q","source_ids":[note["id"],"nonexistent"],"approve_cloud_disclosure":True})
    assert response.status_code==422
