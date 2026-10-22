"""WP-4 first-use trial: load the seed into a separate project vault, or dry-run the five questions.

The seed is public Sovereign project knowledge with `source` pointers back to Git. It arrives through the
ordinary *untrusted* import, so every claim is an unverified proposal the founder reviews in the UI; the
dry run's second pass simulates those approvals only to show what approved memory adds.
"""
from __future__ import annotations

import json
from pathlib import Path

from sovereign.context import compile_context
from sovereign.store import Vault

HERE = Path(__file__).resolve().parent


def seed() -> dict:
    return json.loads((HERE / "seed.json").read_text("utf-8"))


def questions() -> list[dict]:
    return json.loads((HERE / "queries.json").read_text("utf-8"))["queries"]


def inside_git_tree(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in [path.parent, *path.parent.parents])


def load(path: str | Path) -> tuple[Vault, dict]:
    """Create a new trial vault at `path` from the seed. Refuses existing files and Git working trees."""
    target = Path(path).expanduser().resolve()
    if target.exists():
        raise FileExistsError(f"{target} already exists; choose a new file for the trial vault.")
    if inside_git_tree(target):
        raise ValueError(f"{target} is inside a Git working tree; vaults never live in a repository.")
    vault = Vault(str(target))
    return vault, vault.import_untrusted(seed())


def measure(vault: Vault) -> list[dict]:
    """For each question: which expected records the local context includes, noise, approved memory used,
    and how many private items a cloud plan would offer for approval (no provider is called)."""
    rows = []
    for q in questions():
        local = compile_context(vault, q["question"], "local", [])
        cloud = compile_context(vault, q["question"], "kimi", [])
        included = [i.candidate.id for i in local.included if i.role == "evidence"]
        memory = [i.candidate.content for i in local.included if i.role == "approved_memory"]
        rows.append({"id": q["id"], "question": q["question"],
                     "recalled": [e for e in q["expected"] if e in included],
                     "missed": [e for e in q["expected"] if e not in included],
                     "noise": [i for i in included if i not in q["expected"]],
                     "approved_memory": len(memory), "cloud_items": len(cloud.included)})
    return rows


def approve_all_proposals(vault: Vault) -> int:
    """Simulates the founder approving every seeded proposal (dry run only)."""
    approved = 0
    for claim in vault.list_claims(status="proposed"):
        vault.transition_claim(claim["id"], "approved", note="first-use dry run", expected_status="proposed")
        approved += 1
    return approved
