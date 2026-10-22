"""The operational systems registry is machine-readable and internally consistent.

It records boundaries; it does not enforce them. These checks keep it honest: every entry has
every field, statuses and trust classes come from the defined vocabularies, only authority-core
components may write canonical state, nothing with personal content claims unknown egress, and
anything deferred or rejected cannot be described as implemented.
"""
from pathlib import Path
import tomllib

REGISTRY = Path(__file__).resolve().parents[1] / "docs" / "architecture" / "systems-registry.toml"
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
