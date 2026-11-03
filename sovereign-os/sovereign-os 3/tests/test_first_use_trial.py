"""WP-4 first-use trial: the seed is non-sensitive, imports cleanly, and the dry-run numbers are pinned.

The pinned recall is a regression record, not a quality claim: t1-t5 share vocabulary with the seed
(one author wrote both), and the paraphrase probes p1-p3 show what ordinary wording finds today.
"""
import pytest

from evaluation.first_use import trial


def recall(rows):
    return {r["id"]: (len(r["recalled"]), len(r["recalled"]) + len(r["missed"])) for r in rows}


@pytest.fixture
def vault(tmp_path):
    v, result = trial.load(tmp_path / "trial.db")
    assert result == {"imported": 14, "records_skipped": 0, "claims_imported_as_proposed": 5, "claims_skipped": 0}
    return v


def test_seed_is_public_project_knowledge_pointing_back_to_git():
    data = trial.seed()
    assert data["records"] and all(r["source"].startswith("git:") for r in data["records"])
    assert all(r["sensitivity"] == "private" for r in data["records"])   # project notes; nothing sensitive
    assert all(c["status"] == "proposed" for c in data["claims"])        # the founder decides, not the seed


def test_imported_claims_are_unverified_proposals(vault):
    claims = vault.list_claims()
    assert len(claims) == 5 and {c["status"] for c in claims} == {"proposed"} and {c["origin"] for c in claims} == {"imported"}


def test_dry_run_numbers_are_pinned(vault):
    before = recall(trial.measure(vault))
    assert before == {"t1": (1, 1), "t2": (2, 2), "t3": (2, 2), "t4": (2, 2), "t5": (2, 2),
                      "p1": (0, 2), "p2": (1, 2), "p3": (0, 2)}
    assert trial.approve_all_proposals(vault) == 5
    after = trial.measure(vault)
    assert recall(after) == before                                     # approvals add memory, not evidence recall
    assert sum(r["approved_memory"] for r in after if r["id"].startswith("t")) == 6


def test_loader_refuses_existing_files_and_git_working_trees(tmp_path):
    existing = tmp_path / "exists.db"
    existing.write_bytes(b"")
    with pytest.raises(FileExistsError):
        trial.load(existing)
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="Git working tree"):
        trial.load(tmp_path / "repo" / "trial.db")
