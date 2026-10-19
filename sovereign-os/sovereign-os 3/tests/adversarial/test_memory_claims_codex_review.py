"""Permanent regressions for the Codex PR-review findings on PR #1 (reviews of 36c9bbc and 35ce01b).

1. [P1] Forget preview understated what Forget removes (claims on earlier revisions).
2. [P1] Records accepted by the ADR-0002 restore survived migration but made the vault's own
   backups unrestorable (bounds, lineage anomalies, tombstone ids).
3. [P2] The claim listing was silently capped at 100 with no way to reach older claims.
4. [P1] Storage accepted lineage and tombstone identifiers that restore rejected (review of 35ce01b).

Also pinned, found while fixing these: a preview token that ignored authority changes, and record
or claim ids containing "/" that the API could list but not act on.
"""
import json
import sqlite3
from urllib.parse import quote

from fastapi.testclient import TestClient
import pytest
from sovereign import store
from sovereign.app import create_app
from sovereign.store import Vault

T = "2026-10-01T00:00:00+00:00"
CONFIRM = {"confirm": True}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "vault.db")))


def note(client, text="Invented note"):
    resp = client.post("/api/memories", json={"content": text})
    assert resp.status_code == 201, resp.text
    return resp.json()


def correct(client, record, text):
    resp = client.post(f"/api/memories/{record['id']}/correct", json={"content": text})
    assert resp.status_code == 200, resp.text
    return resp.json()


def claim(client, source_ids, text="Derived claim"):
    resp = client.post("/api/claims", json={"text": text, "source_ids": source_ids})
    assert resp.status_code == 201, resp.text
    return resp.json()


def all_claim_ids(client):
    return {c["id"] for c in client.app.state.vault.list_claims()}


def preview(client, record_id):
    resp = client.get(f"/api/memories/{record_id}/forget-preview")
    assert resp.status_code == 200, resp.text
    return resp.json()


def forget(client, record_id, token=None, expect=200):
    resp = client.delete(f"/api/memories/{record_id}", params={"expected_impact": token} if token else None)
    assert resp.status_code == expect, resp.text
    return resp.json()


def assert_preview_is_exact(client, record_id):
    """The preview, then the operation: same records, same claims, nothing else removed."""
    plan = preview(client, record_id)
    before = all_claim_ids(client)
    result = forget(client, record_id, plan["impact_token"])
    after = all_claim_ids(client)
    assert result["claims_forgotten"] == plan["claims_forgotten"] == len(before - after)
    assert set(result["claim_ids"]) == {c["id"] for c in plan["claims"]} == before - after
    assert result["record_ids"] == [r["id"] for r in plan["records"]]
    assert result["records_forgotten"] == plan["records_forgotten"]
    return plan


# --- 1. Forget preview is server-authoritative and exact --------------------------------------

def test_preview_counts_claims_on_earlier_revisions(client):
    r1 = note(client, "Invented v1")
    on_v1 = [claim(client, [r1["id"]], f"About v1 #{i}")["id"] for i in range(3)]
    r2 = correct(client, r1, "Invented v2")                 # the visible record has 0 direct claims
    direct = [c for c in client.get("/api/claims").json()["claims"] if r2["id"] in c["source_ids"]]
    assert direct == []                                      # what the old UI counted
    plan = assert_preview_is_exact(client, r2["id"])
    assert plan["claims_forgotten"] == 3 and {c["id"] for c in plan["claims"]} == set(on_v1)
    assert plan["records_forgotten"] == 2


def test_preview_over_multiple_historical_revisions(client):
    revisions = [note(client, "Invented v0")]
    expected = set()
    for i in range(1, 6):
        if i % 2:
            expected.add(claim(client, [revisions[-1]["id"]], f"About v{i - 1}")["id"])
        revisions.append(correct(client, revisions[-1], f"Invented v{i}"))
    expected.add(claim(client, [revisions[-1]["id"]], "About latest")["id"])
    plan = assert_preview_is_exact(client, revisions[-1]["id"])
    assert plan["records_forgotten"] == 6 and {c["id"] for c in plan["claims"]} == expected


def test_preview_counts_multi_source_claims_once_and_includes_cross_lineage_claims(client):
    r1 = note(client, "Invented v1")
    other = note(client, "Invented unrelated note")
    both_revisions = claim(client, [r1["id"]], "Cites v1")
    r2 = correct(client, r1, "Invented v2")
    spans = claim(client, [r2["id"], other["id"]], "Cites v2 and an unrelated note")
    plan = assert_preview_is_exact(client, r2["id"])
    assert {c["id"] for c in plan["claims"]} == {both_revisions["id"], spans["id"]}
    assert client.get(f"/api/memories/{other['id']}/forget-preview").status_code == 200   # the other record survives


def test_preview_is_complete_beyond_one_hundred_claims(client):
    r1 = note(client, "Invented v1")
    for i in range(70):
        claim(client, [r1["id"]], f"On v1 #{i}")
    r2 = correct(client, r1, "Invented v2")
    for i in range(65):
        claim(client, [r2["id"]], f"On v2 #{i}")
    plan = assert_preview_is_exact(client, r2["id"])
    assert plan["claims_forgotten"] == 135


def test_forget_refuses_if_its_effect_grew_after_the_preview(client):
    r1 = note(client, "Invented v1")
    claim(client, [r1["id"]], "Before preview")
    plan = preview(client, r1["id"])
    late = claim(client, [r1["id"]], "Added after the preview")
    before = all_claim_ids(client)
    forget(client, r1["id"], plan["impact_token"], expect=409)
    assert all_claim_ids(client) == before and late["id"] in before          # nothing was removed
    assert_preview_is_exact(client, r1["id"])                                # a fresh preview matches


def test_forget_refuses_if_a_listed_claim_gained_authority_after_the_preview(client):
    r1 = note(client)
    c = claim(client, [r1["id"]], "Proposed when previewed")
    plan = preview(client, r1["id"])
    approved = client.post(f"/api/claims/{c['id']}/approve", json={**CONFIRM, "expected_status": "proposed"})
    assert approved.status_code == 200 and approved.json()["authoritative"]
    forget(client, r1["id"], plan["impact_token"], expect=409)     # the user confirmed deleting a proposal
    assert c["id"] in all_claim_ids(client)
    fresh = preview(client, r1["id"])
    assert fresh["claims"][0]["status"] == "approved" and fresh["impact_token"] != plan["impact_token"]


def test_preview_is_read_only_and_404s_for_unknown_records(client):
    r1 = note(client)
    claim(client, [r1["id"]])
    before = client.app.state.vault.export()
    preview(client, r1["id"]); preview(client, r1["id"])
    assert {k: v for k, v in client.app.state.vault.export().items() if k != "exported_at"} == \
           {k: v for k, v in before.items() if k != "exported_at"}
    assert client.get("/api/memories/unknown/forget-preview").status_code == 404
    forget(client, "unknown", expect=404)


def test_forget_without_preview_token_still_works_for_api_callers(client):
    r1 = note(client)
    claim(client, [r1["id"]])
    assert forget(client, r1["id"])["claims_forgotten"] == 1


# --- 2. Every backup produced after migration restores ----------------------------------------

# The ADR-0002 (e82f692) schema and restore loop, verbatim: what that release accepted.
LEGACY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY, content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
        sensitivity TEXT NOT NULL CHECK(sensitivity IN ('private', 'sensitive')),
        status TEXT NOT NULL CHECK(status IN ('active', 'superseded')),
        created_at TEXT NOT NULL, supersedes_id TEXT);
    CREATE TABLE IF NOT EXISTS tombstones (id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_records_status ON records(status,created_at);
"""


def adr0002_restore(path, payload):
    db = sqlite3.connect(path)
    db.executescript(LEGACY_SCHEMA)
    for tomb in payload["tombstones"]:
        db.execute("INSERT OR IGNORE INTO tombstones(id,deleted_at) VALUES (?,?)", (str(tomb["id"]), str(tomb["deleted_at"])))
    for row in payload["records"]:
        rid = str(row["id"])
        if db.execute("SELECT 1 FROM tombstones WHERE id=?", (rid,)).fetchone():
            continue
        assert row["sensitivity"] in ("private", "sensitive") and row["status"] in ("active", "superseded")
        assert len(row["content"]) <= 10000
        db.execute("INSERT OR IGNORE INTO records(id,content,source,sensitivity,status,created_at,supersedes_id) VALUES (?,?,?,?,?,?,?)",
                   (rid, row["content"], row["source"], row["sensitivity"], row["status"], row["created_at"], row.get("supersedes_id")))
    db.execute("DELETE FROM records WHERE id IN (SELECT id FROM tombstones)")
    db.commit()
    db.close()


def legacy(id, content="Invented legacy note", source="manual", status="active", supersedes=None, created=T):
    return {"id": id, "content": content, "source": source, "sensitivity": "private", "status": status,
            "created_at": created, "supersedes_id": supersedes}


LEGACY_EDGE_CASES = [
    legacy("empty-content", content=""),
    legacy("whitespace-content", content="   "),
    legacy("x" * 201),                                    # id beyond the current 200-character bound
    legacy(""),                                           # empty id (str() of an empty value)
    legacy(12345),                                        # numeric id, stored as text
    legacy("long-source", source="s" * 300),
    legacy("empty-source", source=""),
    legacy("numeric-time", created=1696118400),
    legacy("self", supersedes="self"),
    legacy("fork-base"), legacy("fork-a", supersedes="fork-base"), legacy("fork-b", supersedes="fork-base"),
    legacy("cycle-a", status="superseded", supersedes="cycle-b"), legacy("cycle-b", status="superseded", supersedes="cycle-a"),
    legacy("two-active-base"), legacy("two-active-next", supersedes="two-active-base"),
    legacy("dangling", supersedes="never-existed"),
    legacy("long-pointer", supersedes="p" * 300),
    legacy("plain-a"), legacy("plain-b", status="superseded"), legacy("plain-c", supersedes="plain-b"),
]
LEGACY_TOMBSTONES = [{"id": "t" * 250, "deleted_at": T}, {"id": " ", "deleted_at": "not-a-date"}, {"id": 7, "deleted_at": 7}]


@pytest.fixture
def legacy_vault(tmp_path):
    path = str(tmp_path / "adr0002.db")
    adr0002_restore(path, {"records": LEGACY_EDGE_CASES, "tombstones": LEGACY_TOMBSTONES})
    db = sqlite3.connect(path)
    original = (db.execute("SELECT * FROM records ORDER BY id").fetchall(), db.execute("SELECT * FROM tombstones ORDER BY id").fetchall())
    db.close()
    return path, original


def strip(export):
    return {k: export[k] for k in ("records", "tombstones", "claims", "claim_tombstones")}


def test_migrated_legacy_vault_backup_round_trips(legacy_vault, tmp_path):
    path, original = legacy_vault
    migrated = Vault(path)
    db = sqlite3.connect(path)
    columns = "id,content,source,sensitivity,status,created_at,supersedes_id"
    assert db.execute(f"SELECT {columns} FROM records ORDER BY id").fetchall() == original[0]   # nothing lost or reshaped
    assert db.execute("SELECT * FROM tombstones ORDER BY id").fetchall() == original[1]
    db.close()
    backup = migrated.export()
    assert len(backup["records"]) == len(original[0]) and all(r["legacy"] == 1 for r in backup["records"])
    for generation in range(2):                     # old vault -> migrate -> export -> fresh restore, twice over
        fresh = Vault(str(tmp_path / f"fresh{generation}.db"))
        result = fresh.restore_trusted(backup)
        assert result["imported"] == len(original[0]) and result["records_skipped"] == 0
        assert strip(fresh.export()) == strip(backup)
        backup = fresh.export()


def test_migrated_legacy_vault_with_new_work_round_trips(legacy_vault, tmp_path):
    path, _ = legacy_vault
    v = Vault(path)
    c = v.add_claim("Claim on a legacy note", ["plain-a"], "human")
    v.transition_claim(c["id"], "approved")
    newer = v.add("Invented correction of a legacy note", supersedes_id="plain-a")   # new writes obey current rules
    assert newer["legacy"] == 0
    v.add_claim("Claim on the correction", [newer["id"]], "model")
    v.delete("fork-a")                                  # forgetting inside a legacy fork works
    fresh = Vault(str(tmp_path / "fresh.db"))
    fresh.restore_trusted(v.export())
    assert strip(fresh.export()) == strip(v.export())
    assert {x["text"]: x["support"] for x in fresh.list_claims()}["Claim on a legacy note"] == "stale"


def test_legacy_rows_out_of_bounds_reject_new_writes_gracefully(legacy_vault):
    path, _ = legacy_vault
    client = TestClient(create_app(path))
    long_id = "x" * 201
    assert client.post(f"/api/memories/{long_id}/correct", json={"content": "Fix"}).status_code == 422
    assert client.post(f"/api/memories/two-active-base/correct", json={"content": "Fix"}).status_code == 422   # lineage conflict
    assert client.post("/api/claims", json={"text": "t", "source_ids": [long_id]}).status_code == 422
    assert client.post("/api/memories/plain-a/correct", json={"content": "   "}).status_code == 422          # was a 500


def test_legacy_record_with_slash_in_id_stays_forgettable(tmp_path):
    path = str(tmp_path / "adr0002.db")
    adr0002_restore(path, {"records": [legacy("notes/2023/a"), legacy("plain")], "tombstones": []})
    client = TestClient(create_app(path))
    plan = preview(client, "notes/2023/a")
    assert plan["record_id"] == "notes/2023/a" and plan["records_forgotten"] == 1
    assert client.post("/api/memories/notes/2023/a/correct", json={"content": "Fix"}).status_code == 200
    assert client.get("/api/memories/notes%2F2023%2Fa/forget-preview").json()["records_forgotten"] == 1
    corrected = [r for r in client.get("/api/memories").json()["records"] if r["supersedes_id"] == "notes/2023/a"][0]
    assert forget(client, corrected["id"])["record_ids"] == [corrected["id"], "notes/2023/a"]


@pytest.mark.parametrize("target", [str(r["id"]) for r in LEGACY_EDGE_CASES], ids=lambda i: i[:20] or "empty-id")
def test_every_legacy_record_can_be_previewed_and_forgotten_exactly(legacy_vault, target):
    path, _ = legacy_vault
    client = TestClient(create_app(path))
    active = {r["id"] for r in client.app.state.vault.export()["records"] if r["status"] == "active"}
    if target in active and 1 <= len(target) <= 200:
        claim(client, [target], "Claim on a legacy note")
    plan = assert_preview_is_exact(client, quote(target, safe=""))
    assert plan["record_id"] == target and target not in {r["id"] for r in client.app.state.vault.export()["records"]}


def violates_current_rules(row):
    pointer = row["supersedes_id"]
    return (row["content"] == "" or not 1 <= len(row["id"]) <= 200 or not 1 <= len(row["source"]) <= 200
            or (pointer is not None and (pointer == row["id"] or not 1 <= len(pointer) <= 200)))


def test_current_apis_cannot_create_equivalent_malformed_records(legacy_vault, tmp_path):
    path, _ = legacy_vault
    backup = Vault(path).export()
    client = TestClient(create_app(str(tmp_path / "current.db")))
    for content in ("", "   "):
        assert client.post("/api/memories", json={"content": content}).status_code == 422
    # Ordinary import ignores the legacy flag: malformed legacy rows are refused and nothing is written.
    resp = client.post("/api/import", json=backup)
    assert resp.status_code == 422 and "trusted restore" in resp.json()["detail"]
    assert client.app.state.vault.export()["records"] == []
    # Without the flag even a trusted restore applies the current rules, row by row...
    unflagged = {r["id"]: {k: v for k, v in r.items() if k != "legacy"} for r in backup["records"]}
    for n, row in enumerate(unflagged.values()):
        target = Vault(str(tmp_path / f"target{n}.db"))
        payload = {**backup, "records": [row], "tombstones": []}
        if violates_current_rules(row):
            with pytest.raises(ValueError):
                target.restore_trusted(payload)
            assert target.export()["records"] == []
        else:
            target.restore_trusted(payload)
            assert all(r["legacy"] == 0 for r in target.export()["records"])
    # ...and across rows: ADR-0002 lineage anomalies are refused as current state.
    for group in (["fork-base", "fork-a", "fork-b"], ["cycle-a", "cycle-b"], ["two-active-base", "two-active-next"]):
        with pytest.raises(ValueError):
            Vault(str(tmp_path / f"lineage-{group[0]}.db")).restore_trusted(
                {**backup, "records": [unflagged[i] for i in group], "tombstones": []})


def test_ordinary_import_never_creates_legacy_rows(tmp_path):
    v = Vault(str(tmp_path / "v.db"))
    flagged = {**legacy("conforming"), "legacy": 1}
    assert v.import_untrusted({"schema": "sovereign.v0.records.2", "records": [flagged], "tombstones": []})["imported"] == 1
    assert v.export()["records"][0]["legacy"] == 0


def test_storage_keeps_legacy_tier_restorable_and_immutable(tmp_path):
    v = Vault(str(tmp_path / "v.db"))
    db = sqlite3.connect(v.path, isolation_level=None)
    with pytest.raises(sqlite3.IntegrityError):         # current tier: malformed rows are refused
        db.execute("INSERT INTO records(id,content,sensitivity,status,created_at) VALUES ('a','','private','active',?)", (T,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES ('b','c','private','active',?,?)",
                   (T, "p" * 201))
    db.execute("INSERT INTO records(id,content,sensitivity,status,created_at,legacy) VALUES ('c','','private','active',?,1)", (T,))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("UPDATE records SET legacy = 0 WHERE id = 'c'")
    db.close()
    fresh = Vault(str(tmp_path / "fresh.db"))           # whatever storage accepts, trusted restore accepts
    fresh.restore_trusted(v.export())
    assert strip(fresh.export()) == strip(v.export())


# --- 3. Claim listing is complete ------------------------------------------------------------

def page_through(client, **params):
    seen, cursor, pages = [], None, 0
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        body = client.get("/api/claims", params=query).json()
        seen.extend(c["id"] for c in body["claims"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            return seen, pages


@pytest.fixture
def many_claims(client):
    rec = note(client)
    ids = [claim(client, [rec["id"]], f"Claim {i:03d}")["id"] for i in range(230)]
    return rec, ids


@pytest.mark.parametrize("limit", [None, 7, 100, 200])
def test_every_claim_is_reachable_by_paging(client, many_claims, limit):
    rec, ids = many_claims
    seen, pages = page_through(client, **({"limit": limit} if limit else {}))
    assert len(seen) == len(set(seen)) == 230 and set(seen) == set(ids)
    assert seen == [c["id"] for c in client.app.state.vault.list_claims()]           # deterministic order
    assert page_through(client, **({"limit": limit} if limit else {}))[0] == seen    # and repeatable
    assert pages == -(-230 // (limit or 100))


def test_paging_with_identical_timestamps_loses_nothing(tmp_path):
    v = Vault(str(tmp_path / "v.db"))
    rec = v.add("Invented note")
    backup = v.export()
    same_second = [{"id": f"c{i:03d}", "text": f"Claim {i}", "origin": "human", "status": "proposed", "created_at": T,
                    "supersedes_id": None, "source_ids": [rec["id"]], "source_hashes": {},
                    "history": [{"from_status": None, "to_status": "proposed", "actor": "human", "note": None, "at": T}]}
                   for i in range(150)]
    v.restore_trusted({**backup, "claims": same_second})
    seen, cursor = [], None
    while True:
        page = v.claims_page(limit=13, cursor=cursor)
        seen.extend(c["id"] for c in page["claims"])
        if not (cursor := page["next_cursor"]):
            break
    assert len(seen) == len(set(seen)) == 150


def test_paging_under_concurrent_additions_and_deletions(client, many_claims):
    rec, ids = many_claims
    first = client.get("/api/claims").json()
    first_ids = {c["id"] for c in first["claims"]}
    deleted_unseen = [cid for cid in ids if cid not in first_ids][:5]   # not yet seen by this paging
    for cid in deleted_unseen:
        assert client.delete(f"/api/claims/{cid}").status_code == 200
    added = [claim(client, [rec["id"]], f"Late claim {i}")["id"] for i in range(30)]
    seen = [c["id"] for c in first["claims"]]
    cursor = first["next_cursor"]
    while cursor:
        body = client.get("/api/claims", params={"cursor": cursor}).json()
        seen.extend(c["id"] for c in body["claims"])
        cursor = body["next_cursor"]
    assert len(seen) == len(set(seen))                                  # no duplicates
    assert set(ids) - set(deleted_unseen) <= set(seen)                  # every surviving original reached
    assert not set(deleted_unseen) & set(seen)                          # forgotten claims are not shown
    # New claims sort by their own key: before page one, or (same-second timestamp, lower id) after the
    # cursor, where they are shown once. Either way a refresh shows every one of them.
    assert set(added) <= set(page_through(client)[0])


def test_decisions_on_claims_older_than_the_first_page(client, many_claims):
    rec, ids = many_claims
    oldest = page_through(client)[0][-1]                              # last in order: only reachable by paging
    assert oldest not in {c["id"] for c in client.get("/api/claims").json()["claims"]}
    resp = client.post(f"/api/claims/{oldest}/approve", json={**CONFIRM, "expected_status": "proposed"})
    assert resp.status_code == 200 and resp.json()["authoritative"]
    approved, _ = page_through(client, status="approved")
    assert approved == [oldest]
    assert client.delete(f"/api/claims/{ids[1]}").status_code == 200


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"cursor": "not-a-cursor"}, {"cursor": "WzFd"}])
def test_invalid_paging_parameters_are_rejected(client, params):
    assert client.get("/api/claims", params=params).status_code == 422


def restored_claim(cid, record):
    return {"id": cid, "text": f"Claim {cid}", "origin": "human", "status": "proposed", "created_at": T,
            "supersedes_id": None, "source_ids": [record["id"]], "source_hashes": {record["id"]: store.evidence_hash(record)},
            "history": [{"from_status": None, "to_status": "proposed", "actor": "human", "note": None, "at": T}]}


def claim_url(cid, action=""):
    return f"/api/claims/{quote(cid, safe='')}" + (f"/{action}" if action else "")   # as encodeURIComponent


@pytest.mark.parametrize("cid", ["notes/claim-1", "q?x", "h#y", "a/b/approve", "c" * 200])
def test_every_listed_claim_stays_actionable_whatever_its_restored_id(client, cid):
    """Found while fixing the listing: trusted restore accepts any 1-200 character claim id, but the
    claim routes did not match ids containing "/", so such a listed claim could not be acted on."""
    rec = note(client)
    other = cid[:-1] + "2"
    backup = {**client.app.state.vault.export(), "claims": [restored_claim(cid, rec), restored_claim(other, rec)]}
    assert client.post("/api/restore", json={"confirm_trusted_restore": True, "backup": backup}).json()["claims_restored"] == 2
    assert {cid, other} <= set(page_through(client)[0])
    decide = lambda i, action, expected, **extra: client.post(claim_url(i, action), json={**CONFIRM, "expected_status": expected, **extra})
    assert decide(cid, "contest", "proposed", note="Why").status_code == 200
    assert decide(cid, "approve", "contested").json()["authoritative"]
    assert decide(cid, "reject", "approved").json()["status"] == "rejected"
    replaced = decide(other, "supersede", "proposed", text="Corrected", source_ids=[rec["id"]])
    assert replaced.status_code == 200 and replaced.json()["superseded"]["id"] == other
    for gone in (cid, other):
        assert client.delete(claim_url(gone)).status_code == 200
    assert not {cid, other} & set(page_through(client)[0])


# --- 4. [P1] Every stored identifier is bounded exactly as restore validates (review of 35ce01b) -----

BOUNDARY = ["", "a", "a" * 200, "a" * 201, "a" * 300, 12345, b"\x00blob"]


def raw_db(v):
    return sqlite3.connect(v.path, isolation_level=None)


def assert_storage_matches_restore(v, tmp_path, label):
    """Whatever raw SQL got into storage, the same version must restore its export exactly."""
    exported = v.export()
    fresh = Vault(str(tmp_path / f"fresh-{abs(hash(label))}.db"))
    fresh.restore_trusted(exported)
    assert strip(fresh.export()) == strip(exported), label


@pytest.mark.parametrize("legacy_tier", [0, 1])
@pytest.mark.parametrize("column", ["id", "content", "source", "created_at", "supersedes_id"])
@pytest.mark.parametrize("value", BOUNDARY, ids=lambda v: f"{type(v).__name__}{len(v) if hasattr(v, '__len__') else ''}")
def test_raw_record_writes_are_restorable_or_refused(tmp_path, legacy_tier, column, value):
    v = Vault(str(tmp_path / "v.db"))
    row = {"id": "r1", "content": "Invented note", "source": "manual", "created_at": T, "supersedes_id": None}
    row[column] = value
    db = raw_db(v)
    try:
        db.execute("INSERT INTO records(id,content,source,sensitivity,status,created_at,supersedes_id,legacy) VALUES (?,?,?,?,?,?,?,?)",
                   (row["id"], row["content"], row["source"], "private", "active", row["created_at"], row["supersedes_id"], legacy_tier))
    except sqlite3.IntegrityError:
        return                                            # refused by storage: nothing unrestorable was written
    finally:
        db.close()
    assert_storage_matches_restore(v, tmp_path, f"{column}={value!r} legacy={legacy_tier}")


@pytest.mark.parametrize("value", BOUNDARY, ids=lambda v: f"{type(v).__name__}{len(v) if hasattr(v, '__len__') else ''}")
def test_raw_claim_lineage_and_tombstone_writes_are_restorable_or_refused(tmp_path, value):
    v = Vault(str(tmp_path / "v.db"))
    rec = v.add("Invented note")
    db = raw_db(v)
    attempts = {
        "claim supersedes_id": ("INSERT INTO claims(id,text,origin,status,created_at,supersedes_id) VALUES ('c1','t','human','proposed',?,?)", (T, value)),
        "claim id": ("INSERT INTO claims(id,text,origin,status,created_at) VALUES (?,'t','human','proposed',?)", (value, T)),
        "claim tombstone id": ("INSERT INTO claim_tombstones(id,deleted_at) VALUES (?,?)", (value, T)),
        "record tombstone id": ("INSERT INTO tombstones(id,deleted_at) VALUES (?,?)", (value, T)),
        "claim link record_id": None,
    }
    for label, attempt in attempts.items():
        try:
            if attempt is None:
                db.execute("INSERT INTO claims(id,text,origin,status,created_at) VALUES ('c2','t','human','proposed',?)", (T,))
                db.execute("INSERT INTO claim_sources(claim_id,record_id) VALUES ('c2',?)", (value,))
            else:
                db.execute(*attempt)
        except sqlite3.IntegrityError:
            pass
    db.close()
    assert_storage_matches_restore(v, tmp_path, f"value={value!r}")
    assert v.get(rec["id"])


def test_codex_finding_out_of_bounds_lineage_pointer_is_refused(tmp_path):
    """The exact reported case: a lower-level writer stores a current-tier pointer out of bounds."""
    v = Vault(str(tmp_path / "v.db"))
    db = raw_db(v)
    for pointer in ("", "p" * 201):
        with pytest.raises(sqlite3.IntegrityError, match="malformed"):
            db.execute("INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id) VALUES ('r','c','private','active',?,?)",
                       (T, pointer))
    db.close()
    assert_storage_matches_restore(v, tmp_path, "pointer")


def test_legacy_lineage_never_reaches_into_current_evidence(tmp_path):
    """Found while checking the legacy tier: such raw writes would make restore skip current rows."""
    v = Vault(str(tmp_path / "v.db"))
    current = v.add("Invented current note")
    corrected = v.add("Invented note v1")
    v.add("Invented note v2", supersedes_id=corrected["id"])
    db = raw_db(v)
    legacy_insert = "INSERT INTO records(id,content,sensitivity,status,created_at,supersedes_id,legacy) VALUES (?,?,?,?,?,?,1)"
    with pytest.raises(sqlite3.IntegrityError):          # a legacy row superseding a current row
        db.execute(legacy_insert, ("l1", "c", "private", "active", T, current["id"]))
    with pytest.raises(sqlite3.IntegrityError):          # joining a lineage that already has a current correction
        db.execute(legacy_insert, ("l2", "c", "private", "active", T, corrected["id"]))
    db.execute(legacy_insert, ("l3", "c", "private", "active", T, "legacy-only-pointer"))   # legacy-to-legacy is fine
    with pytest.raises(sqlite3.IntegrityError):          # a current row can never appear after its (legacy) correction
        db.execute("INSERT INTO records(id,content,sensitivity,status,created_at) VALUES ('legacy-only-pointer','c','private','active',?)", (T,))
    db.close()
    assert_storage_matches_restore(v, tmp_path, "legacy lineage")
