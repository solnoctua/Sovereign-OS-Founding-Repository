"""Regression checks for the tracked-path hygiene guard."""
from pathlib import Path
import runpy

import pytest


forbidden = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "check_repository_hygiene.py")
)["forbidden"]


@pytest.mark.parametrize("path", [
    "sovereign-os/sovereign-os 3/data/sovereign.db",
    "data/sovereign.db-wal",
    "data/sovereign.db-backup",
    "data/vault.sqlite3-shm",
    "src/sovereign/__pycache__/app.pyc",
    "tests/.pytest_cache/v/cache/lastfailed",
    ".env",
    "nested/.env.local",
    "keys/private.pem",
    "keys/vault.key",
    "private-exports/notes.md",
])
def test_reject_tracked_private_or_generated_path(path):
    assert forbidden(path)


@pytest.mark.parametrize("path", [
    ".env.example",
    "src/sovereign/store.py",
    "docs/second-brain/obsidian-demo-vault/.sovereign-export.json",
    "docs/second-brain/obsidian-demo-vault/Sources/Lantern kickoff note.md",
    "docs/benchmarks/0002-context-compiler-governed-retrieval.md",
])
def test_preserve_versioned_source_and_synthetic_fixtures(path):
    assert not forbidden(path)
