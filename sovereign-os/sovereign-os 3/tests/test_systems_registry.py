"""The operational systems registry is machine-readable and internally consistent.

It records boundaries; it does not enforce them. These checks keep it honest: every entry has
every field, statuses and trust classes come from the defined vocabularies, only authority-core
components may write canonical state, nothing with personal content claims unknown egress, and
anything deferred or rejected cannot be described as implemented.

It must also agree with the code in the same tree (Codex audit F-9, 2026-10-22): the schema version, every stated
limit, the known integrity gaps (each probed), and whether each entry's code exists. CI runs on a pull
request's merge commit, so a PR that changes one of these facts without updating the registry fails.
"""
import importlib
import sqlite3
import tempfile
from pathlib import Path
import tomllib

PROJECT = Path(__file__).resolve().parents[1]
REGISTRY = PROJECT / "docs" / "architecture" / "systems-registry.toml"
CANONICAL_TABLES = ("records", "tombstones", "claims", "claim_sources", "claim_tombstones")
FIELDS = {"id", "role", "status", "trust_class", "canonical_write", "personal_data", "credentials", "egress",
          "persistent_state", "upstream", "version_or_commit", "license", "boundary", "exit_test", "documentation"}
STATUSES = {"implemented", "approved", "evaluating", "deferred", "rejected"}
TRUST = {"authority-core", "trusted-service", "restricted", "external"}
PERSONAL = {"none", "metadata", "content"}


def load():
    with REGISTRY.open("rb") as fh:
        return tomllib.load(fh)


def test_registry_parses_and_has_entries():
    data = load()
    assert data["schema_version"] == 1
    assert len(data["system"]) >= 5


def test_every_entry_is_complete_and_uses_defined_vocabularies():
    for entry in load()["system"]:
        missing = FIELDS - set(entry)
        assert not missing, f"{entry.get('id')} missing {sorted(missing)}"
        assert entry["status"] in STATUSES, entry["id"]
        assert entry["trust_class"] in TRUST, entry["id"]
        assert entry["personal_data"].split(" ")[0] in PERSONAL, entry["id"]
        assert isinstance(entry["canonical_write"], bool), entry["id"]


def test_ids_are_unique():
    ids = [e["id"] for e in load()["system"]]
    assert len(ids) == len(set(ids))


def test_only_authority_core_writes_canonical_state():
    for entry in load()["system"]:
        if entry["canonical_write"]:
            assert entry["trust_class"] == "authority-core", entry["id"]


def test_restricted_and_external_components_declare_egress_and_never_write():
    for entry in load()["system"]:
        if entry["trust_class"] in {"restricted", "external"}:
            assert not entry["canonical_write"], entry["id"]
            assert entry["egress"].strip(), entry["id"]


def test_deferred_or_rejected_entries_are_not_described_as_built():
    for entry in load()["system"]:
        if entry["status"] in {"deferred", "rejected"}:
            assert "not built" in entry["upstream"] or "none" in entry["version_or_commit"], entry["id"]


def test_implemented_entries_name_their_code_and_documentation():
    for entry in load()["system"]:
        if entry["status"] == "implemented":
            assert entry["upstream"] and entry["documentation"], entry["id"]


def _hidden_rowid() -> bool:
    """Issue #6: a canonical table still has a hidden rowid, so a rowid REPLACE can bypass its triggers."""
    from sovereign.store import Vault
    with tempfile.TemporaryDirectory() as d:
        db = sqlite3.connect(Vault(f"{d}/probe.db").path)
        try:
            sql = dict(db.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'"))
        finally:
            db.close()
    return any("WITHOUT ROWID" not in sql[table].upper() for table in CANONICAL_TABLES)


def _zero_source_authority() -> bool:
    """A claim with no evidence links derives as supported, so it can be authoritative."""
    from sovereign import claims
    return claims.support_of([]) == "supported"


GAP_PROBES = {"issue-6-hidden-rowid": _hidden_rowid, "zero-source-authority": _zero_source_authority}


def test_schema_version_matches_the_code():
    from sovereign import store
    assert load()["code_facts"]["schema_user_version"] == store.SCHEMA_VERSION


def test_every_stated_limit_matches_the_code():
    for name, stated in load()["code_facts"]["limits"].items():
        module, *attributes = name.split(".")
        value = importlib.import_module(f"sovereign.{module}")
        for attribute in attributes:
            value = getattr(value, attribute)
        assert value == stated, (name, value, stated)


def test_known_gaps_are_exactly_the_gaps_the_code_still_has():
    listed = set(load()["code_facts"]["known_gaps"])
    assert listed <= set(GAP_PROBES), f"no probe for {sorted(listed - set(GAP_PROBES))}"
    present = {gap for gap, probe in GAP_PROBES.items() if probe()}
    assert listed == present, f"registry lists {sorted(listed)}; the code has {sorted(present)}"


def test_status_agrees_with_whether_the_code_exists():
    for entry in load()["system"]:
        exists = [(PROJECT / path).exists() for path in entry.get("code", [])]
        if entry["status"] == "implemented":
            assert all(exists), entry["id"]
        else:
            assert not any(exists), f"{entry['id']} has code in this tree but is marked {entry['status']}"
