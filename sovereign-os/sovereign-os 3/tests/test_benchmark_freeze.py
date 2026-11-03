"""The Builder 1 benchmark freeze sequence (BENCHMARK-PLAN.md section 5), run end to end on synthetic artifacts.

Each test builds a disposable source repository, prepares synthetic inputs as the independent party would, bundles the
pinned commit, writes the detached manifest, and runs `scripts/benchmark_freeze.py` against it. The failure cases show
that each check of section 5.3 actually refuses what it claims to refuse. No real data; standard library and git only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "benchmark_freeze.py"
spec = importlib.util.spec_from_file_location("benchmark_freeze", SCRIPT)
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)

if shutil.which("git") is None:
    pytest.skip("git is not installed", allow_module_level=True)

ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, "GIT_CONFIG_NOSYSTEM": "1",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "synthetic", "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
       "GIT_COMMITTER_NAME": "synthetic", "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
       "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def run(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True, check=True).stdout.decode().strip()


def commit(repo, name, text, message):
    (repo / name).write_text(text, encoding="utf-8")
    run(repo, "add", name)
    run(repo, "commit", "-q", "-m", message)
    return run(repo, "rev-parse", "HEAD")


@pytest.fixture
def frozen(tmp_path):
    """Steps 3 to 9 of section 5 on one synthetic calibration task."""
    repo = tmp_path / "source repo"
    repo.mkdir()
    run(repo, "init", "-q")
    start = commit(repo, "store.py", "def forget(record):\n    return record\n", "start")
    later = commit(repo, "store.py", "def forget(record):\n    return None\n", "the later fix (outcome)")
    inputs = tmp_path / "private inputs"
    (inputs / "T1").mkdir(parents=True)
    files = {"statement": "Make forget() return None.\n", "handoff_a": "Task: make forget() return None.\n",
             "gold_sheet": json.dumps({"facts": ["forget returns None"]}) + "\n",
             "hidden_tests": "def test_forget():\n    assert forget(1) is None\n",
             "evaluator_instructions": "Accept when the hidden test passes.\n"}
    for role, text in files.items():
        (inputs / "T1" / f"{role}.txt").write_text(text, encoding="utf-8")
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    freeze.make_bundle(repo, [start], bundles / "T1.bundle")
    plan = {"selection_version": "devcontext-selection-3", "agents": ["codex", "claude-code"],
            "tasks": [{"id": "T1", "set": "calibration", "target": start, "candidate": None, "must_be_absent": [later],
                       "bundle": "T1.bundle", "inputs": {role: f"T1/{role}.txt" for role in files}}]}
    manifest = freeze.make_manifest(plan, inputs, bundles, "1" * 40, "2" * 40)
    path = tmp_path / "freeze-manifest.json"
    path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    workspace = tmp_path / "agent workspace"
    run(tmp_path, "clone", "-q", "--no-checkout", str(bundles / "T1.bundle"), str(workspace))
    run(workspace, "checkout", "-q", "--detach", start)
    run(workspace, "remote", "remove", "origin")
    assert run(workspace, "rev-parse", "HEAD") == start and (workspace / "store.py").is_file()
    return {"repo": repo, "start": start, "later": later, "inputs": inputs, "bundles": bundles, "manifest": path,
            "workspace": workspace, "plan": plan, "tmp": tmp_path}


def verify(f, workspace=True):
    data = f["manifest"].read_bytes()
    manifest = json.loads(data)
    failures = freeze.check_manifest(manifest, f["inputs"], f["bundles"], data)
    if workspace:
        failures += freeze.check_workspace(manifest, f["bundles"], "T1", f["workspace"])
    return failures


def test_the_full_freeze_sequence_verifies_and_the_commitments_are_acyclic(frozen):
    assert verify(frozen) == []
    manifest = json.loads(frozen["manifest"].read_bytes())
    task = manifest["tasks"][0]
    assert task["bundle"]["refs"] == [frozen["start"]] and len(manifest["assignment"]) == 2
    published = hashlib.sha256(frozen["manifest"].read_bytes()).hexdigest()
    for item in task["inputs"]:                           # inputs commit to nothing downstream of them
        assert published.encode() not in (frozen["inputs"] / item["file"]).read_bytes()
    assert published.encode() not in (frozen["bundles"] / "T1.bundle").read_bytes()


def test_the_cli_verifies_and_reports_failures_with_exit_1(frozen):
    args = [sys.executable, str(SCRIPT), "verify", "--manifest", str(frozen["manifest"]), "--inputs",
            str(frozen["inputs"]), "--bundles", str(frozen["bundles"]), "--workspace", str(frozen["workspace"]),
            "--task", "T1"]
    ok = subprocess.run(args, capture_output=True, text=True, env=ENV)
    assert ok.returncode == 0 and ok.stdout.startswith("verified: manifest ")
    (frozen["inputs"] / "T1" / "gold_sheet.txt").write_text("{}\n", encoding="utf-8")
    bad = subprocess.run(args, capture_output=True, text=True, env=ENV)
    assert bad.returncode == 1 and "T1: input gold_sheet changed after it was frozen" in bad.stdout


def test_a_frozen_input_cannot_change_silently(frozen):
    path = frozen["inputs"] / "T1" / "statement.txt"
    path.write_bytes(path.read_bytes() + b" ")
    assert verify(frozen, workspace=False) == ["T1: input statement changed after it was frozen"]


def test_a_missing_input_fails(frozen):
    (frozen["inputs"] / "T1" / "hidden_tests.txt").unlink()
    assert verify(frozen, workspace=False) == ["T1: input hidden_tests is missing"]


def test_a_bundle_holding_a_later_commit_fails(frozen):
    freeze.make_bundle(frozen["repo"], [frozen["later"]], frozen["tmp"] / "leaky.bundle")
    shutil.copy(frozen["tmp"] / "leaky.bundle", frozen["bundles"] / "T1.bundle")
    manifest = json.loads(frozen["manifest"].read_bytes())
    manifest["tasks"][0]["bundle"].update(sha256=freeze.sha256_file(frozen["bundles"] / "T1.bundle"),
                                          bytes=(frozen["bundles"] / "T1.bundle").stat().st_size)
    frozen["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    failures = verify(frozen, workspace=False)
    assert "T1: bundle refs are not exactly the pinned commits" in failures
    assert f"T1: later commit {frozen['later'][:12]} is present" in failures


def test_an_incomplete_bundle_fails(frozen):
    refs = "refs/heads/devcontext-freeze/x"
    run(frozen["repo"], "update-ref", refs, frozen["later"])
    run(frozen["repo"], "bundle", "create", str(frozen["tmp"] / "thin.bundle"), f"{frozen['start']}..{refs}")
    prerequisites, heads = freeze.bundle_heads(frozen["tmp"] / "thin.bundle")
    assert prerequisites == [frozen["start"]]


def test_a_manifest_committed_into_the_source_history_fails(frozen):
    leaked = {"schema": freeze.MANIFEST_SCHEMA, "inputs_digest": "0" * 64, "tasks": []}
    start = commit(frozen["repo"], "freeze-manifest.json", json.dumps(leaked), "commit a manifest (revision 2's design)")
    plan = frozen["plan"]
    plan["tasks"][0]["target"] = start
    (frozen["bundles"] / "T1.bundle").unlink()
    freeze.make_bundle(frozen["repo"], [start], frozen["bundles"] / "T1.bundle")
    manifest = freeze.make_manifest(plan, frozen["inputs"], frozen["bundles"], "1" * 40, "2" * 40)
    frozen["manifest"].write_bytes(json.dumps(manifest).encode())
    assert "T1: a freeze manifest is inside the source history" in verify(frozen, workspace=False)


def test_an_input_stored_in_the_source_history_fails(frozen):
    hidden = (frozen["inputs"] / "T1" / "hidden_tests.txt").read_text(encoding="utf-8")
    start = commit(frozen["repo"], "test_hidden.py", hidden, "hidden test leaked into the source")
    plan = frozen["plan"]
    plan["tasks"][0]["target"] = start
    (frozen["bundles"] / "T1.bundle").unlink()
    freeze.make_bundle(frozen["repo"], [start], frozen["bundles"] / "T1.bundle")
    frozen["manifest"].write_bytes(json.dumps(freeze.make_manifest(plan, frozen["inputs"], frozen["bundles"],
                                                                   "1" * 40, "2" * 40)).encode())
    assert "T1: frozen input (T1 hidden_tests) is stored as a Git object" in verify(frozen, workspace=False)


def test_the_arm_assignment_cannot_be_chosen_after_the_freeze(frozen):
    manifest = json.loads(frozen["manifest"].read_bytes())
    first = manifest["assignment"][0]
    first["first_arm"] = "B" if first["first_arm"] == "A" else "A"
    frozen["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    assert verify(frozen, workspace=False) == ["manifest: the arm assignment does not follow from the frozen inputs"]


def test_an_unreachable_later_object_in_the_workspace_invalidates_the_run(frozen):
    subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=frozen["workspace"], env=ENV, input=b"future\n",
                   check=True, capture_output=True)
    assert verify(frozen) == ["workspace: 1 Git object(s) not in the task's bundle"]


def test_a_later_commit_fetched_into_the_workspace_invalidates_the_run(frozen):
    run(frozen["workspace"], "fetch", "-q", str(frozen["repo"]), frozen["later"])
    failures = verify(frozen)
    assert f"workspace: later commit {frozen['later'][:12]} is present" in failures


def test_hidden_tests_or_gold_sheets_in_the_workspace_invalidate_the_run(frozen):
    shutil.copy(frozen["inputs"] / "T1" / "hidden_tests.txt", frozen["workspace"] / "notes.txt")
    shutil.copy(frozen["inputs"] / "T1" / "gold_sheet.txt", frozen["workspace"] / "gold.json")
    assert sorted(verify(frozen)) == ["workspace: a gold_sheet file is present", "workspace: a hidden_tests file is present"]


def test_untrusted_git_state_in_the_workspace_invalidates_the_run(frozen):
    info = frozen["workspace"] / ".git" / "objects" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "alternates").write_text(str(frozen["repo"] / ".git" / "objects") + "\n", encoding="utf-8")
    run(frozen["workspace"], "remote", "add", "origin", str(frozen["repo"]))
    failures = verify(frozen)
    assert "workspace: objects/info/alternates exists" in failures and "workspace: has a remote" in failures
