"""Builder 0 policy invariants (docs/DEVELOPMENT.md, "Containment of coding agents").

These are mechanical tripwires, not security boundaries. They fail CI when a change moves
personal content towards a new network path, bumps the storage schema without documenting it in
an ADR, changes the storage-trigger set silently, or ships a findings file that is not
reviewer-shaped. A failure means "this needs a review and an ADR reference", never "unsafe".
"""
from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

from sovereign import store

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "src" / "sovereign"
NETWORK_IMPORTS = re.compile(r"^\s*(?:import|from)\s+(openai|httpx|requests|urllib|socket|http\.client|aiohttp|websockets)\b", re.M)

# Storage triggers are the ADR-0003 contract. Changing this number requires an ADR reference in the
# change (ADR-0003 migration section or a new ADR) and an independent review of the trigger text.
EXPECTED_TRIGGER_COUNT = 36


def test_only_the_provider_adapter_imports_network_clients():
    offenders = {}
    for path in SRC.rglob("*.py"):
        if path.name == "providers.py":
            continue
        found = NETWORK_IMPORTS.findall(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found
    assert not offenders, f"personal content may leave the process only through providers.py: {offenders}"


def test_app_calls_the_provider_at_exactly_one_site():
    text = (SRC / "app.py").read_text(encoding="utf-8")
    assert text.count("providers.generate(") == 1


def test_schema_version_in_code_is_documented_in_an_adr():
    adrs = (PROJECT / "docs" / "adr").glob("*.md")
    pattern = re.compile(rf"\b{store.SCHEMA_VERSION}\s*=\s*this schema")
    assert any(pattern.search(p.read_text(encoding="utf-8")) for p in adrs), (
        f"store.SCHEMA_VERSION={store.SCHEMA_VERSION} must be documented as '<n> = this schema' in an ADR")


def test_storage_trigger_set_changes_only_with_an_adr_reference():
    with tempfile.TemporaryDirectory() as d:
        store.Vault(str(Path(d) / "v.db"))
        db = sqlite3.connect(str(Path(d) / "v.db"))
        count = db.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]
        db.close()
    assert count == EXPECTED_TRIGGER_COUNT, (
        "the storage trigger set changed; update EXPECTED_TRIGGER_COUNT together with the ADR that justifies it")


def test_findings_example_matches_the_reviewer_owned_shape():
    schema = json.loads((PROJECT / "docs" / "engineering" / "findings.schema.json").read_text(encoding="utf-8"))
    example = json.loads((PROJECT / "docs" / "engineering" / "findings-example.json").read_text(encoding="utf-8"))
    for key in schema["required"]:
        assert key in example, key
    finding_schema = schema["properties"]["findings"]["items"]
    for finding in example["findings"]:
        for key in finding_schema["required"]:
            assert key in finding, (finding.get("id"), key)
        assert finding["confidence"] in finding_schema["properties"]["confidence"]["enum"]
        assert finding["severity"] in finding_schema["properties"]["severity"]["enum"]
        assert finding["evidence"], "a finding without evidence cannot be confirmed"
