"""The Builder 1 benchmark freeze tool (BENCHMARK-PLAN.md section 5; docs/engineering/builder-1/FREEZE-TOOL.md).

Every documented command is run as a subprocess, with a timeout, on real files: disposable synthetic repositories, and
this repository's pinned calibration commits. The cases cover:

- the documented workflow: prepare, bundle, manifest, workspace, verify and record;
- each invalid input, which exits 2 without a traceback;
- each invalid start state, which `verify` rejects with exit 1;
- each malformed bundle, which is refused without hanging.

No real data. Standard library and git only.
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
SPEC_DIR = PROJECT / "docs" / "engineering" / "builder-1"
spec = importlib.util.spec_from_file_location("benchmark_freeze", SCRIPT)
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)
_spec_tests = importlib.util.spec_from_file_location("builder1_spec_tests", PROJECT / "tests" / "test_builder1_spec.py")
spec_tests = importlib.util.module_from_spec(_spec_tests)
_spec_tests.loader.exec_module(spec_tests)                   # its schema validator is independent of the tool's

if shutil.which("git") is None:
    pytest.skip("git is not installed", allow_module_level=True)

ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, "GIT_CONFIG_NOSYSTEM": "1",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "synthetic", "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
       "GIT_COMMITTER_NAME": "synthetic", "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
       "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
ONE, TWO = "1" * 40, "2" * 40


def cli(*args, timeout=120):
    result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, env=ENV,
                            timeout=timeout, cwd=PROJECT)
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, result.stdout, result.stderr


def run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True, check=check).stdout.decode().strip()


def commit(repo, name, text, message):
    (repo / name).write_text(text, encoding="utf-8")
    run(repo, "add", name)
    run(repo, "commit", "-q", "-m", message)
    return run(repo, "rev-parse", "HEAD")


def task_plan(target, later):
    """A published task plan (benchmark-tasks.json v3) for the synthetic repository: one pinned task, one not."""
    task = {"id": "T1", "set": "calibration", "kind": "bug_or_security", "stage": "implementation",
            "title": "Make forget() return None", "pin_when": None,
            "inputs": {"target": target, "candidate": None, "expected_merge_base": None}, "expected": None,
            "statement": {"source": "synthetic"}, "handoff_a": {"source": "synthetic"},
            "environment": {"bundle_refs": [target], "must_be_absent": [later]},
            "acceptance": "the hidden test passes", "reference_outcome": None}
    later_task = dict(task, id="T3", stage="planning", pin_when="later",
                      inputs={"target": None, "candidate": None, "expected_merge_base": None}, environment=None)
    return {"schema": "sovereign.devcontext.benchmark-tasks.v3", "status": "planned", "hashes": "none",
            "plan": "docs/engineering/builder-1/BENCHMARK-PLAN.md", "project_root": "", "task_statement_max_chars": 2000,
            "sets": {}, "tasks": [task, later_task]}


@pytest.fixture
def setup(tmp_path):
    """The documented workflow up to a verified manifest, all through the command line."""
    repo = tmp_path / "source repo"
    repo.mkdir()
    run(repo, "init", "-q")
    start = commit(repo, "store.py", "def forget(record):\n    return record\n", "start")
    later = commit(repo, "store.py", "def forget(record):\n    return None\n", "the later fix (outcome)")
    run(repo, "checkout", "-q", start)
    tasks = tmp_path / "benchmark-tasks.json"
    tasks.write_text(json.dumps(task_plan(start, later)), encoding="utf-8")
    plan = tmp_path / "freeze-plan.json"
    code, out, err = cli("prepare", "--tasks", tasks, "--tool-commit", ONE, "--protocol-commit", TWO,
                         "--agent", "codex", "--agent", "claude-code", "--out", plan)
    assert code == 0 and "T3: not pinned (later)" in err and "1 task(s)" in out
    inputs = tmp_path / "private inputs"
    (inputs / "T1").mkdir(parents=True)
    files = {"statement.md": "Make forget() return None.\n", "handoff_a.md": "Task: make forget() return None.\n",
             "gold_sheet.json": json.dumps({"facts": ["forget returns None"]}) + "\n",
             "hidden_tests.py": "def test_forget():\n    assert forget(1) is None\n",
             "evaluator_instructions.md": "Accept when the hidden test passes.\n"}
    for name, text in files.items():
        (inputs / "T1" / name).write_text(text, encoding="utf-8")
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    code, out, _ = cli("bundle", "--repo", repo, "--plan", plan, "--task", "T1", "--bundles", bundles)
    assert code == 0 and len(out.strip()) == 64
    manifest = tmp_path / "freeze-manifest.json"
    code, out, _ = cli("manifest", "--plan", plan, "--inputs", inputs, "--bundles", bundles, "--out", manifest)
    assert code == 0 and out.strip() == hashlib.sha256(manifest.read_bytes()).hexdigest()
    return {"tmp": tmp_path, "repo": repo, "start": start, "later": later, "tasks": tasks, "plan": plan,
            "inputs": inputs, "bundles": bundles, "manifest": manifest}


def verify(s, *extra):
    return cli("verify", "--manifest", s["manifest"], "--inputs", s["inputs"], "--bundles", s["bundles"], *extra)


def workspace(s, arm="A", name="run", *extra):
    path = s["tmp"] / name
    code, out, err = cli("workspace", "--manifest", s["manifest"], "--inputs", s["inputs"], "--bundles", s["bundles"],
                         "--task", "T1", "--arm", arm, "--out", path, *extra)
    assert code == 0, err
    return path


def verify_ws(s, path, arm="A"):
    return verify(s, "--workspace", path, "--task", "T1", "--arm", arm)


# --- the documented workflow ------------------------------------------------------------------------------------------

def test_the_documented_workflow_verifies_and_records_a_valid_start(setup):
    assert verify(setup) == (0, f"verified: manifest {hashlib.sha256(setup['manifest'].read_bytes()).hexdigest()}\n", "")
    for arm, extra in (("A", ()), ("N", ())):
        path = workspace(setup, arm, f"run {arm}", *extra)
        record = setup["tmp"] / f"start-{arm}.json"
        code, out, err = verify(setup, "--workspace", path, "--task", "T1", "--arm", arm, "--record", record)
        assert code == 0 and out.startswith("verified: manifest "), (arm, out, err)
        data = json.loads(record.read_text())
        run_schema = json.loads((SPEC_DIR / "benchmark-run.schema.json").read_text(encoding="utf-8"))
        assert spec_tests.errors(data, run_schema, run_schema) == []
        assert data["freeze"] == {"manifest_sha256": hashlib.sha256(setup["manifest"].read_bytes()).hexdigest(),
                                  "valid": True}
        assert data["run"] is None and data["arm"] == arm and data["environment"]["preflight_passed"] is True
    context = setup["tmp"] / "package.md"
    context.write_text(f"Target commit:\n```text\n{setup['start']}\n```\n", encoding="utf-8")
    path = workspace(setup, "B", "run B", "--context", context)
    assert verify_ws(setup, path, "B")[0] == 0


def test_the_checked_in_example_is_exactly_what_prepare_produces(tmp_path):
    out = tmp_path / "freeze-plan.json"
    code, stdout, stderr = cli("prepare", "--tasks", SPEC_DIR / "benchmark-tasks.json", "--tool-commit", ONE,
                               "--protocol-commit", TWO, "--agent", "claude-code", "--agent", "codex", "--out", out)
    assert code == 0 and stdout == "freeze plan: 2 task(s)\n"
    assert "T3: not pinned" in stderr and "T4: not pinned" in stderr
    assert out.read_bytes() == (SPEC_DIR / "freeze-plan.example.json").read_bytes()


def test_the_published_calibration_task_freezes_and_verifies_on_this_repository(tmp_path):
    """T1 of the real task plan: its pinned commit, its later commits absent, through every command."""
    plan = json.loads((SPEC_DIR / "freeze-plan.example.json").read_text())
    t1 = plan["tasks"][0]
    if subprocess.run(["git", "cat-file", "-e", f"{t1['target']}^{{commit}}"], cwd=PROJECT, env=ENV).returncode:
        pytest.skip("the calibration commit is not in this clone (shallow)")
    plan["tasks"] = [t1]
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    inputs, bundles = tmp_path / "inputs", tmp_path / "bundles"
    bundles.mkdir()
    for role, name in t1["inputs"].items():
        if name:
            (inputs / name).parent.mkdir(parents=True, exist_ok=True)
            (inputs / name).write_text(f"synthetic {role} for T1\n", encoding="utf-8")
    assert cli("bundle", "--repo", PROJECT, "--plan", plan_file, "--task", "T1", "--bundles", bundles)[0] == 0
    manifest = tmp_path / "manifest.json"
    assert cli("manifest", "--plan", plan_file, "--inputs", inputs, "--bundles", bundles, "--out", manifest)[0] == 0
    path = tmp_path / "run T1"
    assert cli("workspace", "--manifest", manifest, "--inputs", inputs, "--bundles", bundles, "--task", "T1",
               "--arm", "A", "--out", path)[0] == 0
    code, out, err = cli("verify", "--manifest", manifest, "--inputs", inputs, "--bundles", bundles,
                         "--workspace", path, "--task", "T1", "--arm", "A")
    assert code == 0, out + err
    for later in t1["must_be_absent"]:
        assert subprocess.run(["git", "cat-file", "-e", later], cwd=path, env=ENV).returncode != 0


# --- F-12: invalid inputs exit 2, with no traceback -------------------------------------------------------------------

def edited_plan(s, change):
    plan = json.loads(s["plan"].read_text())
    change(plan)
    path = s["tmp"] / f"plan-{len(list(s['tmp'].glob('plan-*')))}.json"
    path.write_text(json.dumps(plan) if not isinstance(plan, str) else plan, encoding="utf-8")
    return path


def manifest_from(s, plan_path):
    out = s["tmp"] / f"manifest-{plan_path.stem}.json"
    return cli("manifest", "--plan", plan_path, "--inputs", s["inputs"], "--bundles", s["bundles"], "--out", out)


@pytest.mark.parametrize("change, message", [
    (lambda p: p["tasks"][0].update(target=None), "T1: not pinned"),
    (lambda p: p["tasks"][0].pop("target"), "missing target"),
    (lambda p: p["tasks"][0]["inputs"].update(statement="../escape.md"), "inputs.statement: has the wrong form"),
    (lambda p: p["tasks"][0]["inputs"].update(statement="T1/absent.md"), "is not a file inside the inputs directory"),
    (lambda p: p["tasks"][0].update(bundle="absent.bundle"), "bundle file absent.bundle is missing"),
    (lambda p: p.update(tasks=[]), "$.tasks: 0 entries"),
    (lambda p: p.update(schema="sovereign.devcontext.freeze-plan.v0"), "unsupported schema version"),
    (lambda p: p.update(agents=[]), "$.agents: 0 entries"),
    (lambda p: p.update(agents=["codex", "codex"]), "agent codex appears more than once"),
    (lambda p: p.update(agents=["Codex Agent"]), "agents[0]: has the wrong form"),
    (lambda p: p["tasks"][0]["must_be_absent"].append(p["tasks"][0]["target"]), "also listed as must_be_absent"),
])
def test_the_manifest_command_refuses_invalid_freeze_plans(setup, change, message):
    code, out, err = manifest_from(setup, edited_plan(setup, change))
    assert code == 2 and message in err and out == "", err


def test_malformed_json_and_symlinked_bindings_are_refused(setup):
    broken = setup["tmp"] / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    assert manifest_from(setup, broken)[:2] == (2, "")
    outside = setup["tmp"] / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (setup["inputs"] / "T1" / "link.md").symlink_to(outside)
    code, _, err = manifest_from(setup, edited_plan(setup, lambda p: p["tasks"][0]["inputs"].update(statement="T1/link.md")))
    assert code == 2 and "not a file inside the inputs directory" in err


def test_prepare_refuses_an_invalid_task_plan_and_bad_commits(setup):
    bad = setup["tmp"] / "bad-tasks.json"
    bad.write_text(json.dumps({"schema": "sovereign.devcontext.benchmark-tasks.v2", "tasks": []}), encoding="utf-8")
    code, _, err = cli("prepare", "--tasks", bad, "--tool-commit", ONE, "--protocol-commit", TWO, "--agent", "codex",
                       "--out", setup["tmp"] / "x.json")
    assert code == 2 and "unsupported schema version" in err
    code, _, err = cli("prepare", "--tasks", setup["tasks"], "--tool-commit", "abc", "--protocol-commit", TWO,
                       "--agent", "codex", "--out", setup["tmp"] / "y.json")
    assert code == 2 and "full 40-character SHAs" in err
    assert cli("manifest")[0] == 2 and cli("--help")[0] == 0


def test_bundle_refuses_a_missing_directory_a_non_repository_and_a_shallow_clone(setup):
    """Found by the round-3 whole-workflow run: a missing --bundles directory exited 3 with "git bundle failed"."""
    s = setup
    args = ("--plan", s["plan"], "--task", "T1")
    code, _, err = cli("bundle", "--repo", s["repo"], *args, "--bundles", s["tmp"] / "no such directory")
    assert code == 2 and "is not an existing directory" in err
    fresh = s["tmp"] / "fresh bundles"
    fresh.mkdir()
    code, _, err = cli("bundle", "--repo", s["tmp"] / "private inputs", *args, "--bundles", fresh)
    assert code == 2 and "is not a Git repository" in err
    shallow = s["tmp"] / "shallow"
    run(s["tmp"], "clone", "-q", "--depth", "1", f"file://{s['repo']}", str(shallow))
    code, _, err = cli("bundle", "--repo", shallow, *args, "--bundles", fresh)
    assert code == 2 and "shallow clone" in err
    assert list(fresh.iterdir()) == []
    code, _, err = cli("bundle", "--repo", s["repo"], *args, "--bundles", s["bundles"])
    assert code == 2 and "exists" in err


# --- F-13: invalid start states fail verification (exit 1), valid ones pass ------------------------------------------

def assert_rejected(s, path, *messages, arm="A"):
    record = Path(f"{path}.refused-start.json")
    code, out, err = verify(s, "--workspace", path, "--task", "T1", "--arm", arm, "--record", record)
    assert code == 1, out + err
    for message in messages:
        assert message in out, out
    assert "verified" not in out and not record.exists()          # a refused start never writes a record


def test_an_empty_repository_is_rejected(setup):
    empty = setup["tmp"] / "empty"
    empty.mkdir()
    run(empty, "init", "-q")
    assert_rejected(setup, empty, "HEAD is unborn", "Git object(s) of the task's bundle are missing")


def test_an_unborn_head_with_the_right_objects_is_rejected(setup):
    path = setup["tmp"] / "unborn"
    path.mkdir()
    run(path, "init", "-q")
    subprocess.run(["git", "fetch", "-q", str(setup["bundles"] / "T1.bundle"), "refs/heads/*:refs/heads/*"], cwd=path,
                   env=ENV, check=True, capture_output=True)
    assert_rejected(setup, path, "HEAD is unborn")


def test_a_wrong_checkout_commit_is_rejected(setup):
    path = workspace(setup)
    commit(path, "store.py", "def forget(record):\n    return None\n", "the agent's own commit")
    assert_rejected(setup, path, "HEAD is not the task's target commit", "not in the task's bundle")


def test_a_workspace_from_another_task_misses_the_pinned_commit(setup):
    other = setup["tmp"] / "other repo"
    other.mkdir()
    run(other, "init", "-q")
    commit(other, "x.py", "x = 1\n", "unrelated")
    path = setup["tmp"] / "wrong source"
    run(setup["tmp"], "clone", "-q", str(other), str(path))
    run(path, "remote", "remove", "origin")
    assert_rejected(setup, path, "HEAD is not the task's target commit",
                    "Git object(s) of the task's bundle are missing")


def test_a_missing_required_object_is_rejected(setup):
    path = workspace(setup)
    objects = path / ".git" / "objects"
    packs = list((objects / "pack").glob("*.pack"))
    for pack in packs:
        moved = setup["tmp"] / pack.name
        pack.rename(moved)
        pack.with_suffix(".idx").unlink()
        subprocess.run(["git", "unpack-objects", "-q"], cwd=path, env=ENV, input=moved.read_bytes(), check=True)
    blob = run(path, "rev-parse", f"{setup['start']}:store.py")
    (objects / blob[:2] / blob[2:]).unlink()
    assert_rejected(setup, path, "1 Git object(s) of the task's bundle are missing")


def test_dirty_staged_and_untracked_sources_are_rejected(setup):
    dirty = workspace(setup, name="dirty")
    (dirty / "store.py").write_text("def forget(record):\n    return None\n", encoding="utf-8")   # the later outcome
    assert_rejected(setup, dirty, "tracked file store.py differs from the target commit")
    staged = workspace(setup, name="staged")
    (staged / "store.py").write_text("x = 1\n", encoding="utf-8")
    run(staged, "add", "store.py")
    assert_rejected(setup, staged, "staged change to store.py")
    untracked = workspace(setup, name="untracked")
    (untracked / "helper.py").write_text("x = 1\n", encoding="utf-8")
    assert_rejected(setup, untracked, "unapproved untracked file helper.py")


def test_an_outcome_bearing_or_private_fixture_is_rejected(setup):
    path = workspace(setup)
    (path / "tests").mkdir()
    shutil.copy(setup["inputs"] / "T1" / "hidden_tests.py", path / "tests" / "test_hidden.py")
    shutil.copy(setup["inputs"] / "T1" / "gold_sheet.json", path / ".devcontext" / "gold.json")
    assert_rejected(setup, path, "private input hidden_tests is present at tests/test_hidden.py",
                    "private input gold_sheet is present at .devcontext/gold.json",
                    "unapproved untracked file tests/test_hidden.py", "unapproved untracked file .devcontext/gold.json")


def test_private_files_hidden_where_git_never_looks_are_rejected(setup):
    """Found in the round-3 self-review: the scan skipped every `.git` directory, and Git lists no path inside one."""
    gold = setup["inputs"] / "T1" / "gold_sheet.json"
    nested = workspace(setup, name="nested")
    (nested / "docs" / ".git").mkdir(parents=True)
    shutil.copy(gold, nested / "docs" / ".git" / "notes.json")
    assert_rejected(setup, nested, "nested Git directory or file docs/.git",
                    "private input gold_sheet is present at docs/.git/notes.json")
    inside = workspace(setup, name="inside")
    shutil.copy(setup["inputs"] / "T1" / "evaluator_instructions.md", inside / ".git" / "NOTES")
    assert_rejected(setup, inside, "private input evaluator_instructions is present at .git/NOTES")
    linked = workspace(setup, name="linked")
    (linked / ".git" / "private").symlink_to(setup["inputs"], target_is_directory=True)
    assert_rejected(setup, linked, "symbolic link .git/private inside the Git directory")
    assert verify_ws(setup, workspace(setup, name="clean"))[0] == 0


def test_missing_or_altered_bootstrap_context_is_rejected(setup):
    missing = workspace(setup, name="missing")
    (missing / ".devcontext" / "handoff.md").unlink()
    assert_rejected(setup, missing, "required bootstrap file .devcontext/handoff.md is missing")
    altered = workspace(setup, name="altered")
    (altered / ".devcontext" / "task.md").write_text("A different task.\n", encoding="utf-8")
    assert_rejected(setup, altered, ".devcontext/task.md is not the frozen input")
    wrong_arm = workspace(setup, arm="N", name="wrong arm")
    assert_rejected(setup, wrong_arm, "required bootstrap file .devcontext/handoff.md is missing")


def test_later_objects_reachable_or_not_are_rejected(setup):
    fetched = workspace(setup, name="fetched")
    subprocess.run(["git", "fetch", "-q", str(setup["repo"]), setup["later"]], cwd=fetched, env=ENV, check=True,
                   capture_output=True)
    assert_rejected(setup, fetched, f"later commit {setup['later'][:12]} is present", "not in the task's bundle")
    loose = workspace(setup, name="loose")
    subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=loose, env=ENV, input=b"future\n", check=True,
                   capture_output=True)
    assert_rejected(setup, loose, "1 Git object(s) not in the task's bundle")


def test_untrusted_git_state_and_bare_repositories_are_rejected(setup):
    path = workspace(setup)
    info = path / ".git" / "objects" / "info"
    (info / "alternates").write_text(str(setup["repo"] / ".git" / "objects") + "\n", encoding="utf-8")
    run(path, "remote", "add", "origin", str(setup["repo"]))
    run(path, "tag", "extra", setup["start"])
    assert_rejected(setup, path, "objects/info/alternates exists", "has a remote",
                    "refs are not exactly the expected work")
    bare = setup["tmp"] / "bare.git"
    run(setup["tmp"], "clone", "-q", "--bare", str(setup["bundles"] / "T1.bundle"), str(bare))
    assert_rejected(setup, bare, "a bare repository")


def test_workspace_configuration_cannot_run_programs_or_bend_the_status(setup):
    """Found in the round-3 self-review: a clean filter in the workspace's own config ran during verify, which passed."""
    marker = setup["tmp"] / "the filter ran"
    filtered = workspace(setup, name="filtered")
    (filtered / ".git" / "info" / "attributes").write_text("* filter=planted\n", encoding="utf-8")
    run(filtered, "config", "filter.planted.clean", f"touch '{marker}'; cat")
    os.utime(filtered / "store.py", (1, 1))                     # stale stat data: Git would re-read the file
    assert_rejected(setup, filtered, "unexpected repository configuration filter.planted.clean",
                    "unexpected Git file info/attributes", "the work tree was not inspected")
    assert not marker.exists()
    elsewhere = workspace(setup, name="elsewhere")
    run(elsewhere, "config", "core.worktree", str(workspace(setup, name="clean copy")))
    assert_rejected(setup, elsewhere, "not the top level of its work tree")      # refused before its config is read
    included = workspace(setup, name="included")
    run(included, "config", "include.path", str(setup["tmp"] / "extra.config"))
    assert_rejected(setup, included, "unexpected repository configuration include.path")
    assert verify_ws(setup, workspace(setup, name="clean"))[0] == 0


def test_workspace_and_verify_refuse_bad_arguments_without_leaving_anything_behind(setup, tmp_path):
    """Found in the round-3 self-review: a missing --context raised a traceback and left a partial workspace."""
    s, out = setup, setup["tmp"] / "never built"
    args = ("workspace", "--manifest", s["manifest"], "--inputs", s["inputs"], "--bundles", s["bundles"], "--task", "T1")
    code, _, err = cli(*args, "--arm", "B", "--context", tmp_path / "absent.md", "--out", out)
    assert code == 2 and "--context" in err and "is not an existing file" in err and not out.exists()
    big = tmp_path / "big.md"
    with open(big, "wb") as handle:
        handle.truncate(262145)
    code, _, err = cli(*args, "--arm", "B", "--context", big, "--out", out)
    assert code == 2 and "larger than 262,144 bytes" in err and not out.exists()
    (s["tmp"] / "dangling").symlink_to(s["tmp"] / "nowhere")
    code, _, err = cli(*args, "--arm", "A", "--out", s["tmp"] / "dangling")
    assert code == 2 and "exists" in err
    code, _, err = cli("verify", "--manifest", s["manifest"], "--inputs", tmp_path / "absent", "--bundles", s["bundles"])
    assert code == 2 and "--inputs" in err and "is not an existing directory" in err
    huge = tmp_path / "huge.json"
    with open(huge, "wb") as handle:
        handle.truncate((16 << 20) + 1)
    code, _, err = cli("verify", "--manifest", huge, "--inputs", s["inputs"], "--bundles", s["bundles"])
    assert code == 2 and "larger than 16,777,216 bytes" in err
    path = workspace(s)
    record = s["tmp"] / "start.json"
    assert verify(s, "--workspace", path, "--task", "T1", "--arm", "A", "--record", record)[0] == 0
    code, _, err = verify(s, "--workspace", path, "--task", "T1", "--arm", "A", "--record", record)
    assert code == 2 and f"--record {record} exists" in err


def test_a_target_that_tracks_the_bootstrap_directory_is_refused_cleanly(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(repo, "init", "-q")
    (repo / ".devcontext").mkdir()
    target = commit(repo, ".devcontext/task.md", "planted\n", "tracks the bootstrap directory")
    later = commit(repo, "x.py", "x = 1\n", "later")
    tasks, plan, inputs, bundles = (tmp_path / "tasks.json", tmp_path / "plan.json", tmp_path / "inputs",
                                    tmp_path / "bundles")
    tasks.write_text(json.dumps(task_plan(target, later)), encoding="utf-8")
    assert cli("prepare", "--tasks", tasks, "--tool-commit", ONE, "--protocol-commit", TWO, "--agent", "codex",
               "--out", plan)[0] == 0
    (inputs / "T1").mkdir(parents=True)
    for name in ("statement.md", "handoff_a.md", "gold_sheet.json", "hidden_tests.py", "evaluator_instructions.md"):
        (inputs / "T1" / name).write_text(f"synthetic {name}\n", encoding="utf-8")
    bundles.mkdir()
    assert cli("bundle", "--repo", repo, "--plan", plan, "--task", "T1", "--bundles", bundles)[0] == 0
    manifest = tmp_path / "manifest.json"
    assert cli("manifest", "--plan", plan, "--inputs", inputs, "--bundles", bundles, "--out", manifest)[0] == 0
    out = tmp_path / "run"
    code, _, err = cli("workspace", "--manifest", manifest, "--inputs", inputs, "--bundles", bundles, "--task", "T1",
                       "--arm", "A", "--out", out)
    assert code == 2 and "tracks .devcontext" in err and not out.exists()


def test_crafted_names_cannot_drive_the_terminal(setup):
    path = workspace(setup)
    (path / "a\x1b[2Jb.py").write_text("x\n", encoding="utf-8")
    code, out, _ = verify_ws(setup, path)
    assert code == 1 and "\x1b" not in out and "unapproved untracked file a\\x1b[2Jb.py" in out


def test_invalid_or_empty_manifests_cannot_be_verified(setup):
    manifest = json.loads(setup["manifest"].read_text())
    for change, message in ((lambda m: m.update(tasks=[], agents=[]), "$.tasks: 0 entries"),
                            (lambda m: m.update(schema="something-else"), "unsupported schema version"),
                            (lambda m: m["tasks"][0]["bundle"].pop("objects"), "missing objects")):
        broken = json.loads(json.dumps(manifest))
        change(broken)
        setup["manifest"].write_text(json.dumps(broken), encoding="utf-8")
        code, out, err = verify(setup)
        assert code == 2 and message in err and "verified" not in out, err


def test_a_changed_input_or_bundle_after_the_freeze_fails(setup):
    statement = setup["inputs"] / "T1" / "statement.md"
    statement.write_bytes(statement.read_bytes() + b" ")
    assert verify(setup)[:2] == (1, "T1: input statement changed after it was frozen\n")
    statement.write_bytes(statement.read_bytes()[:-1])
    bundle = setup["bundles"] / "T1.bundle"
    bundle.write_bytes(bundle.read_bytes() + b"\0")
    assert verify(setup)[:2] == (1, "T1: bundle changed after it was frozen\n")


def test_a_manifest_or_input_inside_the_source_history_fails(setup, tmp_path):
    leaked = {"schema": freeze.MANIFEST_SCHEMA, "inputs_digest": "0" * 64, "tasks": []}
    start = commit(setup["repo"], "freeze-manifest.json", json.dumps(leaked), "commit a manifest (revision 2's design)")
    hidden = (setup["inputs"] / "T1" / "hidden_tests.py").read_text(encoding="utf-8")
    start = commit(setup["repo"], "test_hidden.py", hidden, "and a hidden test")
    plan = edited_plan(setup, lambda p: p["tasks"][0].update(target=start, bundle="leaky.bundle"))
    assert cli("bundle", "--repo", setup["repo"], "--plan", plan, "--task", "T1", "--bundles", setup["bundles"])[0] == 0
    manifest = setup["tmp"] / "leaky-manifest.json"
    assert cli("manifest", "--plan", plan, "--inputs", setup["inputs"], "--bundles", setup["bundles"], "--out", manifest)[0] == 0
    code, out, _ = cli("verify", "--manifest", manifest, "--inputs", setup["inputs"], "--bundles", setup["bundles"])
    assert code == 1 and "T1: a freeze manifest is inside the source history" in out
    assert "T1: frozen input (T1 hidden_tests) is stored as a Git object" in out


def test_the_arm_assignment_cannot_be_chosen_after_the_freeze(setup):
    manifest = json.loads(setup["manifest"].read_text())
    first = manifest["assignment"][0]
    first["first_arm"] = "B" if first["first_arm"] == "A" else "A"
    setup["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    assert verify(setup)[:2] == (1, "manifest: the arm assignment does not follow from the frozen inputs\n")


# --- F-14: malformed bundles are refused, and parsing always terminates ----------------------------------------------

HEAD = "a" * 40


PARSE = """import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("freeze", sys.argv[1])
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)
try:
    print(json.dumps(freeze.bundle_heads(sys.argv[2])))
except freeze.BundleError as error:
    print(f"BundleError: {error}")
    sys.exit(1)
"""


def parse_header(path):
    """The header parser in a child process with a time limit, so that a regressed loop fails instead of hanging."""
    result = subprocess.run([sys.executable, "-c", PARSE, str(SCRIPT), str(path)], capture_output=True, text=True,
                            timeout=30)
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, result.stdout


@pytest.mark.parametrize("name, data, message", [
    ("empty", b"", "missing or unsupported bundle signature"),
    ("signature only (16 bytes)", b"# v2 git bundle\n", "ends before its terminating blank line"),
    ("missing terminator", b"# v2 git bundle\n" + f"{HEAD} refs/heads/x\n".encode(), "ends before its terminating"),
    ("unsupported version", b"# v4 git bundle\n\n", "missing or unsupported bundle signature"),
    ("over-long line", b"# v2 git bundle\n" + b"a" * 5000 + b"\n\n", "too long or truncated"),
    ("oversized header", b"# v2 git bundle\n" + b"".join(f"{HEAD} refs/heads/b{i}\n".encode() for i in range(20000))
     + b"\n", "too large"),
    ("invalid encoding", b"# v2 git bundle\n" + HEAD.encode() + b" refs/heads/\xff\n\n", "not UTF-8"),
    ("truncated reference", b"# v2 git bundle\nabc refs/heads/x\n\n", "malformed reference line"),
    ("malformed prerequisite", b"# v2 git bundle\n-xyz\n\n", "malformed prerequisite line"),
    ("capability in v2", b"# v2 git bundle\n@object-format=sha1\n\n", "misplaced bundle capability"),
    ("unsupported object format", b"# v3 git bundle\n@object-format=sha256\n" + f"{HEAD} refs/heads/x\n".encode() + b"\n",
     "unsupported object format"),
    ("no references", b"# v2 git bundle\n\n", "no references"),
])
def test_malformed_bundle_headers_are_refused(tmp_path, name, data, message):
    path = tmp_path / "x.bundle"
    path.write_bytes(data)
    code, out = parse_header(path)
    assert code == 1 and out.startswith("BundleError: ") and message in out, (name, out)


def test_a_valid_bundle_header_parses(setup):
    code, out = parse_header(setup["bundles"] / "T1.bundle")
    assert code == 0
    prerequisites, heads = json.loads(out)
    assert prerequisites == [] and heads == {f"refs/heads/devcontext-freeze/{setup['start']}": setup["start"]}


def test_the_truncated_16_byte_bundle_is_refused_by_the_command_without_hanging(setup):
    bundle = setup["bundles"] / "T1.bundle"
    bundle.write_bytes(b"# v2 git bundle\n")
    code, out, err = cli("manifest", "--plan", setup["plan"], "--inputs", setup["inputs"], "--bundles", setup["bundles"],
                         "--out", setup["tmp"] / "m2.json", timeout=30)
    assert code == 2 and "ends before its terminating blank line" in err
    # verify reaches the header only when the bundle's hash and size are the frozen ones: re-freeze them by hand.
    manifest = json.loads(setup["manifest"].read_text(encoding="utf-8"))
    manifest["tasks"][0]["bundle"].update(sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(), bytes=16)
    edited = setup["tmp"] / "m16.json"
    edited.write_text(json.dumps(manifest), encoding="utf-8")
    code, out, _ = cli("verify", "--manifest", edited, "--inputs", setup["inputs"], "--bundles", setup["bundles"],
                       timeout=30)
    assert code == 1 and "T1: bundle header ends before its terminating blank line" in out and "verified" not in out
