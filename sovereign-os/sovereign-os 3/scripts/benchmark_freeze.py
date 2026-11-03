"""Builder 1 benchmark freeze: isolated source bundles, a detached freeze manifest, and its verification.

This implements the commitment order of docs/engineering/builder-1/BENCHMARK-PLAN.md section 5. The manifest commits to
the input files and to the bundles; nothing commits to the manifest except its SHA-256, which is published separately
(section 5, step 9). So the commitment graph is acyclic by construction, and `verify` checks that it stays so.

    python scripts/benchmark_freeze.py bundle --repo REPO --out FILE COMMIT [COMMIT ...]
    python scripts/benchmark_freeze.py manifest --plan PLAN --inputs DIR --bundles DIR --tool-commit SHA
                                              --protocol-commit SHA --out FILE
    python scripts/benchmark_freeze.py verify --manifest FILE --inputs DIR --bundles DIR
                                            [--workspace DIR --task ID]

`verify` exits 0 when every check passes, and 1 with one line per failed check otherwise. A failed workspace check
invalidates the run that would use that workspace. Standard library and the `git` executable only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MANIFEST_SCHEMA = "sovereign.devcontext.benchmark-freeze.v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
ROLES = ("statement", "handoff_a", "gold_sheet", "hidden_tests", "evaluator_instructions")
PRIVATE_ROLES = ("gold_sheet", "hidden_tests", "evaluator_instructions")
REF_PREFIX = "refs/heads/devcontext-freeze/"   # under refs/heads, so that a plain clone fetches them


def git(repo, *args, data=None, check=True, local_bundle=False):
    """Git with every transport disabled. Cloning a bundle file uses Git's local `file` transport, which only
    `local_bundle=True` allows; no other transport is ever enabled."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
               GIT_ALLOW_PROTOCOL="file" if local_bundle else "", GIT_NO_REPLACE_OBJECTS="1", LC_ALL="C")
    result = subprocess.run(["git", "-C", str(repo), "--no-pager", "-c", "protocol.allow=never",
                             "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false", *args],
                            input=data, capture_output=True, env=env, check=False)
    if check and result.returncode:
        raise RuntimeError(f"git {args[0]} failed")
    return result


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# --- step 5: the isolated source bundle --------------------------------------------------------------------------------

def make_bundle(repo, commits, out):
    """Bundle exactly the history of the pinned commits, under temporary refs that are removed again."""
    commits = list(dict.fromkeys(commits))
    if not commits or not all(SHA.match(c) for c in commits):
        raise ValueError("pin full 40-character commit SHAs")
    refs = [REF_PREFIX + c for c in commits]
    try:
        for ref, commit in zip(refs, commits):
            git(repo, "update-ref", ref, commit)
        git(repo, "bundle", "create", str(Path(out).resolve()), *refs)
    finally:
        for ref in refs:
            git(repo, "update-ref", "-d", ref, check=False)
    return out


def bundle_heads(path):
    """(prerequisites, {ref: sha}) from the bundle header, without needing a repository."""
    prerequisites, heads = [], {}
    with open(path, "rb") as handle:
        signature = handle.readline()
        if signature not in (b"# v2 git bundle\n", b"# v3 git bundle\n"):
            raise ValueError("not a Git bundle")
        for raw in iter(handle.readline, b"\n"):
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("@"):
                continue                                    # v3 capabilities
            if line.startswith("-"):
                prerequisites.append(line[1:].split(" ", 1)[0])
            elif line:
                sha, ref = line.split(" ", 1)
                heads[ref] = sha
    return prerequisites, heads


def object_set(repo):
    out = git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").stdout.decode().split()
    return set(out)


def reachable_set(repo):
    out = git(repo, "rev-list", "--objects", "--all").stdout.decode().splitlines()
    return {line.split(" ", 1)[0] for line in out if line}


# --- steps 4 and 8: hashes and the detached manifest ------------------------------------------------------------------

def inputs_digest(tasks):
    lines = sorted(f"{t['id']} {i['role']} {i['sha256']}" for t in tasks for i in t["inputs"])
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def assignment(digest, tasks, agents):
    """First arm per task and agent, fixed by the frozen inputs: nobody chooses it after seeing them."""
    out = []
    for task in sorted(t["id"] for t in tasks):
        for agent in sorted(agents):
            byte = hashlib.sha256(f"{digest}:{task}:{agent}".encode()).digest()[0]
            out.append({"task": task, "agent": agent, "first_arm": "A" if byte % 2 == 0 else "B"})
    return out


def make_manifest(plan, inputs_dir, bundles_dir, tool_commit, protocol_commit):
    tasks = []
    for task in plan["tasks"]:
        entry = {"id": task["id"], "set": task["set"], "held_out": bool(task.get("held_out")),
                 "target": task["target"], "candidate": task.get("candidate"),
                 "must_be_absent": list(task.get("must_be_absent", [])), "inputs": []}
        for role in ROLES:
            name = task["inputs"].get(role)
            if name is not None:
                data = (Path(inputs_dir) / name).read_bytes()
                entry["inputs"].append({"role": role, "file": name, "sha256": hashlib.sha256(data).hexdigest(),
                                        "bytes": len(data)})
        bundle = Path(bundles_dir) / task["bundle"]
        prerequisites, heads = bundle_heads(bundle)
        entry["bundle"] = {"file": task["bundle"], "sha256": sha256_file(bundle), "bytes": bundle.stat().st_size,
                           "refs": sorted(heads.values())}
        tasks.append(entry)
    digest = inputs_digest(tasks)
    return {"schema": MANIFEST_SCHEMA,
            "protocol": {"commit": protocol_commit, "plan": "docs/engineering/builder-1/BENCHMARK-PLAN.md"},
            "tool": {"commit": tool_commit, "selection_version": plan["selection_version"]},
            "agents": sorted(plan["agents"]), "tasks": tasks, "inputs_digest": digest,
            "assignment": assignment(digest, tasks, plan["agents"])}


# --- verification --------------------------------------------------------------------------------------------------------

def check_manifest(manifest, inputs_dir, bundles_dir, manifest_bytes):
    failures = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        return ["manifest: wrong schema"]
    for key in ("protocol", "tool"):
        if not SHA.match(str(manifest.get(key, {}).get("commit", ""))):
            failures.append(f"manifest: {key}.commit is not a full SHA")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    input_blobs = {}
    for task in manifest["tasks"]:
        tid = task["id"]
        roles = [i["role"] for i in task["inputs"]]
        if "statement" not in roles:
            failures.append(f"{tid}: no frozen task statement")
        if len(set(roles)) != len(roles):
            failures.append(f"{tid}: an input role appears twice")
        for item in task["inputs"]:
            path = Path(inputs_dir) / item["file"]
            if not path.is_file():
                failures.append(f"{tid}: input {item['role']} is missing")
                continue
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["bytes"]:
                failures.append(f"{tid}: input {item['role']} changed after it was frozen")
            if manifest_hash.encode() in data or manifest["inputs_digest"].encode() in data:
                failures.append(f"{tid}: input {item['role']} refers to the manifest (cyclic commitment)")
            input_blobs[blob_id(data)] = f"{tid} {item['role']}"
    if inputs_digest(manifest["tasks"]) != manifest["inputs_digest"]:
        failures.append("manifest: inputs_digest does not match the listed input hashes")
    if assignment(manifest["inputs_digest"], manifest["tasks"], manifest["agents"]) != manifest["assignment"]:
        failures.append("manifest: the arm assignment does not follow from the frozen inputs")
    for task in manifest["tasks"]:
        failures += check_bundle(task, bundles_dir, input_blobs, blob_id(manifest_bytes))
    return failures


def check_bundle(task, bundles_dir, input_blobs, manifest_blob):
    tid, bundle = task["id"], task["bundle"]
    path = Path(bundles_dir) / bundle["file"]
    if not path.is_file():
        return [f"{tid}: bundle is missing"]
    # A plain clone fetches only refs/heads and refs/tags, so a bundle whose refs are elsewhere clones empty and every
    # absence check would pass vacuously. The pinned-commit checks below fail in that case.
    if sha256_file(path) != bundle["sha256"] or path.stat().st_size != bundle["bytes"]:
        return [f"{tid}: bundle changed after it was frozen"]
    failures = []
    prerequisites, heads = bundle_heads(path)
    if prerequisites:
        failures.append(f"{tid}: bundle needs prerequisite commits, so its history is incomplete")
    pinned = [c for c in (task["target"], task.get("candidate")) if c]
    if sorted(heads.values()) != sorted(set(pinned)) or sorted(bundle["refs"]) != sorted(set(pinned)):
        failures.append(f"{tid}: bundle refs are not exactly the pinned commits")
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone.git"
        if git(tmp, "clone", "--mirror", "--quiet", str(path.resolve()), str(clone), check=False,
               local_bundle=True).returncode:
            return failures + [f"{tid}: bundle cannot be cloned"]
        present = object_set(clone)
        if present != reachable_set(clone):
            failures.append(f"{tid}: bundle holds objects not reachable from its refs")
        failures += content_checks(tid, clone, present, task, input_blobs, manifest_blob)
    return failures


def content_checks(tid, repo, present, task, input_blobs, manifest_blob):
    failures = []
    for later in task.get("must_be_absent", []):
        if later in present:
            failures.append(f"{tid}: later commit {later[:12]} is present")
    for blob, label in input_blobs.items():
        if blob in present:
            failures.append(f"{tid}: frozen input ({label}) is stored as a Git object")
    if manifest_blob in present:
        failures.append(f"{tid}: the manifest is stored as a Git object")
    for blob in present:
        kind = git(repo, "cat-file", "-t", blob).stdout.strip()
        if kind != b"blob":
            continue
        data = git(repo, "cat-file", "blob", blob).stdout
        if data[:1] == b"{" and b'"inputs_digest"' in data:
            try:
                parsed = json.loads(data)
            except ValueError:
                continue
            if isinstance(parsed, dict) and parsed.get("schema") == MANIFEST_SCHEMA:
                failures.append(f"{tid}: a freeze manifest is inside the source history")
    for commit in (task["target"], task.get("candidate")):
        if commit and commit not in present:
            failures.append(f"{tid}: pinned commit {commit[:12]} is missing")
    if task.get("candidate") and task["target"] in present and task["candidate"] in present:
        bases = git(repo, "merge-base", "--all", task["target"], task["candidate"], check=False).stdout.split()
        if len(bases) != 1:
            failures.append(f"{tid}: target and candidate have no unique merge base")
    return failures


def check_workspace(manifest, bundles_dir, task_id, workspace):
    """Preflight of an agent's workspace before a run. Any failure invalidates the run."""
    task = next((t for t in manifest["tasks"] if t["id"] == task_id), None)
    if task is None:
        return [f"workspace: unknown task {task_id}"]
    failures = []
    git_dir = Path(git(workspace, "rev-parse", "--absolute-git-dir").stdout.decode().strip())
    if git(workspace, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        failures.append("workspace: shallow")
    for relative in ("objects/info/alternates", "objects/info/http-alternates", "info/grafts"):
        if (git_dir / relative).exists():
            failures.append(f"workspace: {relative} exists")
    if list((git_dir / "objects" / "pack").glob("*.promisor")):
        failures.append("workspace: promisor pack")
    config = git(workspace, "config", "--list", check=False).stdout.decode().lower()
    if "extensions.partialclone" in config or re.search(r"remote\..*\.(promisor|partialclonefilter)=", config):
        failures.append("workspace: partial-clone configuration")
    if git(workspace, "remote").stdout.strip():
        failures.append("workspace: has a remote")
    if git(workspace, "for-each-ref", "refs/replace").stdout.strip():
        failures.append("workspace: replace refs")
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone.git"
        path = Path(bundles_dir) / task["bundle"]["file"]
        git(tmp, "clone", "--mirror", "--quiet", str(path.resolve()), str(clone), local_bundle=True)
        allowed = object_set(clone)
    extra = object_set(workspace) - allowed
    if extra:
        failures.append(f"workspace: {len(extra)} Git object(s) not in the task's bundle")
    for later in task.get("must_be_absent", []):
        if git(workspace, "cat-file", "-e", later, check=False).returncode == 0:
            failures.append(f"workspace: later commit {later[:12]} is present")
    private = {i["sha256"]: i["role"] for t in manifest["tasks"] for i in t["inputs"] if i["role"] in PRIVATE_ROLES}
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            digest = sha256_file(Path(root) / name)
            if digest in private:
                failures.append(f"workspace: a {private[digest]} file is present")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bundle")
    b.add_argument("--repo", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("commits", nargs="+")
    m = sub.add_parser("manifest")
    for flag in ("--plan", "--inputs", "--bundles", "--tool-commit", "--protocol-commit", "--out"):
        m.add_argument(flag, required=True)
    v = sub.add_parser("verify")
    for flag in ("--manifest", "--inputs", "--bundles"):
        v.add_argument(flag, required=True)
    v.add_argument("--workspace")
    v.add_argument("--task")
    args = parser.parse_args(argv)
    if args.command == "bundle":
        if Path(args.out).exists():
            parser.error("--out exists")
        make_bundle(args.repo, args.commits, args.out)
        print(sha256_file(args.out))
        return 0
    if args.command == "manifest":
        if Path(args.out).exists():
            parser.error("--out exists")
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        manifest = make_manifest(plan, args.inputs, args.bundles, args.tool_commit, args.protocol_commit)
        data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        with open(args.out, "xb") as handle:
            handle.write(data)
        print(hashlib.sha256(data).hexdigest())
        return 0
    data = Path(args.manifest).read_bytes()
    manifest = json.loads(data)
    failures = check_manifest(manifest, args.inputs, args.bundles, data)
    if args.workspace:
        if not args.task:
            parser.error("--workspace needs --task")
        failures += check_workspace(manifest, args.bundles, args.task, args.workspace)
    for failure in failures:
        print(failure)
    if not failures:
        print(f"verified: manifest {hashlib.sha256(data).hexdigest()}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
