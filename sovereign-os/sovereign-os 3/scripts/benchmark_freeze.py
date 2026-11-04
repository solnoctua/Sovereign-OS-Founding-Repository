"""Builder 1 benchmark freeze tooling (docs/engineering/builder-1/BENCHMARK-PLAN.md section 5).

Usage guide: docs/engineering/builder-1/FREEZE-TOOL.md. Standard library and the `git` executable only.

    prepare    --tasks TASK_PLAN --tool-commit SHA --protocol-commit SHA --agent NAME [--agent NAME ...] --out PLAN
    bundle     --repo REPO --plan PLAN --task ID --bundles DIR
    manifest   --plan PLAN --inputs DIR --bundles DIR --out MANIFEST
    workspace  --manifest MANIFEST --inputs DIR --bundles DIR --task ID --arm A|B|N [--context FILE] --out DIR
    verify     --manifest MANIFEST --inputs DIR --bundles DIR [--workspace DIR --task ID --arm A|B|N] [--record FILE]

Exit codes: 0 success; 1 a verification check failed, so the start state is not valid; 2 invalid input or usage
(nothing was checked or written); 3 an operating failure (Git missing, failing or too slow). Messages name tasks,
roles, fields and the files the user supplied. They never print file contents.

The commitment graph is acyclic: the manifest commits to the input files and the bundles; nothing commits to the
manifest except its SHA-256, published separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "engineering" / "builder-1"
TASK_PLAN_SCHEMA = "sovereign.devcontext.benchmark-tasks.v3"
PLAN_SCHEMA = "sovereign.devcontext.freeze-plan.v1"
MANIFEST_SCHEMA = "sovereign.devcontext.benchmark-freeze.v1"
RUN_SCHEMA = "sovereign.devcontext.benchmark-run.v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
ROLES = ("statement", "handoff_a", "gold_sheet", "hidden_tests", "evaluator_instructions")
PRIVATE_ROLES = ("gold_sheet", "hidden_tests", "evaluator_instructions")
REF_PREFIX = "refs/heads/devcontext-freeze/"   # under refs/heads, so that a plain clone fetches them
BOOTSTRAP = ".devcontext"
ARM_FILES = {"A": ("task.md", "handoff.md"), "B": ("task.md", "context.md"), "N": ("task.md",)}
MAX_HEADER_BYTES, MAX_LINE_BYTES, MAX_HEADER_LINES = 1 << 20, 4096, 10000
MAX_JSON_BYTES = 16 << 20         # a task plan, freeze plan or manifest
MAX_CONTEXT_BYTES = 262144        # arm B's context: a package's Markdown, at most the largest max_output_bytes
TIMEOUT = 300
# The only local configuration `git clone` writes, on any platform. Any other key could run a program (a filter
# driver, `core.fsmonitor`) or change what `git status` reports (`core.worktree`, an include), so it is refused.
WORKSPACE_CONFIG = {"core.repositoryformatversion", "core.filemode", "core.bare", "core.logallrefupdates",
                    "core.ignorecase", "core.precomposeunicode", "core.symlinks"}


class InputError(Exception):
    """Invalid input or usage: exit 2."""


class OperatingError(Exception):
    """Git missing, failing or too slow: exit 3."""


class BundleError(Exception):
    """A malformed or unsupported bundle."""


# --- Git -------------------------------------------------------------------------------------------------------------

def git(repo, *args, data=None, check=True, local_bundle=False):
    """Git with every transport disabled, except the local `file` transport that cloning a bundle file needs."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
               GIT_ALLOW_PROTOCOL="file" if local_bundle else "", GIT_NO_REPLACE_OBJECTS="1", LC_ALL="C")
    try:
        result = subprocess.run(["git", "-C", str(repo), "--no-pager", "-c", "protocol.allow=never",
                                 "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false", *args],
                                input=data, capture_output=True, env=env, check=False, timeout=TIMEOUT)
    except FileNotFoundError as error:
        raise OperatingError("git is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise OperatingError(f"git {args[0]} did not finish within {TIMEOUT} seconds") from error
    if check and result.returncode:
        raise OperatingError(f"git {args[0]} failed")
    return result


def shown(text):
    """A path or key for a message: printable, so that a crafted name cannot drive the terminal."""
    return text if text.isprintable() else text.encode("unicode_escape").decode("ascii")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# --- schemas (the keyword subset that tests/test_builder1_spec.py also implements) -----------------------------------

def load_schema(name):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _is_type(value, name):
    return {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool), "null": value is None}[name]


def schema_errors(value, schema, root, where="$"):
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].removeprefix("#/$defs/")]
    found = []
    if "const" in schema and value != schema["const"]:
        found.append(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{where}: not an allowed value")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, t) for t in types):
            return found + [f"{where}: must be {' or '.join(types)}"]
    if isinstance(value, dict):
        props = schema.get("properties", {})
        found += [f"{where}: missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            found += [f"{where}: unexpected field {k}" for k in value if k not in props]
        for key, sub in value.items():
            if key in props:
                found += schema_errors(sub, props[key], root, f"{where}.{key}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            found.append(f"{where}: {len(value)} entries, outside the allowed range")
        if "items" in schema:
            for i, sub in enumerate(value):
                found += schema_errors(sub, schema["items"], root, f"{where}[{i}]")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            found.append(f"{where}: length {len(value)} is outside the allowed range")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            found.append(f"{where}: has the wrong form")
    elif _is_type(value, "number"):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            found.append(f"{where}: {value} is out of range")
    return found


def read_file(path, what, limit):
    """The bytes of a regular file the user named, within a size limit."""
    path = Path(path)
    if not path.is_file():
        raise InputError(f"{what} {path} is not an existing file")
    if path.stat().st_size > limit:
        raise InputError(f"{what} {path} is larger than {limit:,} bytes")
    try:
        return path.read_bytes()
    except OSError as error:
        raise InputError(f"{what} {path} cannot be read") from error


def read_json(path, what):
    data = read_file(path, what, MAX_JSON_BYTES)
    try:
        return json.loads(data)
    except (UnicodeDecodeError, ValueError) as error:
        raise InputError(f"{what} {path} is not valid JSON") from error


def validate(value, schema_file, expected, what):
    if not isinstance(value, dict):
        raise InputError(f"{what}: must be a JSON object")
    if value.get("schema") != expected:
        raise InputError(f"{what}: unsupported schema version (expected {expected})")
    schema = load_schema(schema_file)
    problems = schema_errors(value, schema, schema)
    if problems:
        raise InputError(f"{what}: " + "; ".join(problems[:10]))


def unique(values, what):
    seen = set()
    for value in values:
        if value in seen:
            raise InputError(f"{what} {value} appears more than once")
        seen.add(value)


# --- step 3-4: the freeze plan --------------------------------------------------------------------------------------

def prepare(task_plan, tool_commit, protocol_commit, agents, selection_version):
    """Derive a freeze plan from the published task plan. Unpinned tasks are listed, never invented."""
    tasks, not_pinned = [], []
    for task in task_plan["tasks"]:
        pins = task["inputs"]
        if pins["target"] is None or task["environment"] is None:
            not_pinned.append({"id": task["id"], "pin_when": task["pin_when"] or "not pinned"})
            continue
        tid = task["id"]
        tasks.append({"id": tid, "set": task["set"], "held_out": False, "target": pins["target"],
                      "candidate": pins["candidate"], "must_be_absent": task["environment"]["must_be_absent"],
                      "bundle": f"{tid}.bundle",
                      "inputs": {"statement": f"{tid}/statement.md", "handoff_a": f"{tid}/handoff_a.md",
                                 "gold_sheet": f"{tid}/gold_sheet.json",
                                 "hidden_tests": None if task["stage"] == "planning" else f"{tid}/hidden_tests.py",
                                 "evaluator_instructions": f"{tid}/evaluator_instructions.md"}})
    return {"schema": PLAN_SCHEMA,
            "note": "Derived by scripts/benchmark_freeze.py prepare from docs/engineering/builder-1/benchmark-tasks.json. "
                    "The independent party writes the input files, may change the bindings, and adds held-out tasks "
                    "before running manifest.",
            "tool": {"commit": tool_commit, "selection_version": selection_version},
            "protocol_commit": protocol_commit, "agents": sorted(agents), "tasks": tasks, "not_pinned": not_pinned}


def check_plan(plan, inputs_dir=None, bundles_dir=None):
    if isinstance(plan, dict) and isinstance(plan.get("tasks"), list):
        for task in plan["tasks"]:
            if isinstance(task, dict) and task.get("target", "") is None:
                raise InputError(f"{task.get('id', '?')}: not pinned; set its target commit, or remove it from the "
                                 "freeze plan")
    validate(plan, "freeze-plan.schema.json", PLAN_SCHEMA, "freeze plan")
    unique(plan["agents"], "agent")
    unique([t["id"] for t in plan["tasks"]], "task")
    for task in plan["tasks"]:
        tid = task["id"]
        if task["target"] in task["must_be_absent"] or (task["candidate"] and task["candidate"] in task["must_be_absent"]):
            raise InputError(f"{tid}: a pinned commit is also listed as must_be_absent")
        if inputs_dir is not None:
            for role, name in task["inputs"].items():
                if name is not None:
                    input_path(inputs_dir, name, f"{tid}: input {role}")
        if bundles_dir is not None and not (Path(bundles_dir) / task["bundle"]).is_file():
            raise InputError(f"{tid}: bundle file {task['bundle']} is missing")


def input_path(inputs_dir, name, what):
    """A binding must name a regular file inside the inputs directory."""
    base = Path(inputs_dir).resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.is_file():
        raise InputError(f"{what} ({name}) is not a file inside the inputs directory")
    return path


# --- step 5: the isolated source bundle -----------------------------------------------------------------------------

def make_bundle(repo, commits, out):
    """Bundle exactly the history of the pinned commits, under temporary branch refs that are deleted again."""
    commits = list(dict.fromkeys(commits))
    if not commits or not all(SHA.match(c) for c in commits):
        raise InputError("pin full 40-character commit SHAs")
    probe = git(repo, "rev-parse", "--is-shallow-repository", check=False)
    if probe.returncode:
        raise InputError(f"--repo {repo} is not a Git repository")
    if probe.stdout.strip() == b"true":
        raise InputError(f"--repo {repo} is a shallow clone; bundle from a full clone")
    for commit in commits:
        if git(repo, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode:
            raise InputError(f"commit {commit[:12]} is not in {repo}")
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
    """(prerequisites, {ref: sha}) from a bundle header: bounded, and refusing EOF before the terminator."""
    try:
        handle = open(path, "rb")
    except OSError as error:
        raise BundleError("bundle cannot be read") from error
    with handle:
        signature = handle.readline(MAX_LINE_BYTES + 1)
        if signature not in (b"# v2 git bundle\n", b"# v3 git bundle\n"):
            raise BundleError("missing or unsupported bundle signature")
        total, lines, prerequisites, heads, capabilities = len(signature), 0, [], {}, []
        while True:
            raw = handle.readline(MAX_LINE_BYTES + 1)
            if raw == b"":
                raise BundleError("bundle header ends before its terminating blank line")
            total, lines = total + len(raw), lines + 1
            if len(raw) > MAX_LINE_BYTES or not raw.endswith(b"\n"):
                raise BundleError("bundle header line is too long or truncated")
            if total > MAX_HEADER_BYTES or lines > MAX_HEADER_LINES:
                raise BundleError("bundle header is too large")
            if raw == b"\n":
                break
            try:
                line = raw[:-1].decode("utf-8")
            except UnicodeDecodeError as error:
                raise BundleError("bundle header is not UTF-8") from error
            if line.startswith("@"):
                if signature != b"# v3 git bundle\n" or heads or prerequisites:
                    raise BundleError("misplaced bundle capability line")
                capabilities.append(line[1:])
            elif line.startswith("-"):
                sha = line[1:].split(" ", 1)[0]
                if not SHA.match(sha):
                    raise BundleError("malformed prerequisite line")
                prerequisites.append(sha)
            else:
                parts = line.split(" ", 1)
                if len(parts) != 2 or not SHA.match(parts[0]) or not parts[1].startswith("refs/") or parts[1] in heads:
                    raise BundleError("malformed reference line")
                heads[parts[1]] = parts[0]
        if any(c.startswith("object-format=") and c != "object-format=sha1" for c in capabilities):
            raise BundleError("unsupported object format")
        if not heads:
            raise BundleError("bundle has no references")
    return prerequisites, heads


def object_set(repo):
    out = git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").stdout.decode().split()
    return set(out)


def reachable_set(repo):
    out = git(repo, "rev-list", "--objects", "--all").stdout.decode().splitlines()
    return {line.split(" ", 1)[0] for line in out if line}


def blobs_with_contents(repo):
    """Yield (sha, data) for every blob in the repository, in one git process."""
    out = git(repo, "cat-file", "--batch-all-objects", "--batch").stdout
    pos = 0
    while pos < len(out):
        end = out.index(b"\n", pos)
        sha, kind, size = out[pos:end].split()
        start = end + 1
        data = out[start:start + int(size)]
        pos = start + int(size) + 1
        if kind == b"blob":
            yield sha.decode(), data


# --- step 8: the detached manifest ----------------------------------------------------------------------------------

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


def make_manifest(plan, inputs_dir, bundles_dir):
    check_plan(plan, inputs_dir, bundles_dir)
    tasks = []
    for task in plan["tasks"]:
        entry = {"id": task["id"], "set": task["set"], "held_out": task["held_out"], "target": task["target"],
                 "candidate": task["candidate"], "must_be_absent": list(task["must_be_absent"]), "inputs": []}
        for role in ROLES:
            name = task["inputs"].get(role)
            if name is not None:
                data = input_path(inputs_dir, name, f"{task['id']}: input {role}").read_bytes()
                entry["inputs"].append({"role": role, "file": name, "sha256": hashlib.sha256(data).hexdigest(),
                                        "bytes": len(data)})
        bundle = Path(bundles_dir) / task["bundle"]
        try:
            prerequisites, heads = bundle_heads(bundle)
        except BundleError as error:
            raise InputError(f"{task['id']}: {error}") from error
        pins = sorted({c for c in (task["target"], task["candidate"]) if c})
        if prerequisites or sorted(set(heads.values())) != pins:
            raise InputError(f"{task['id']}: bundle {task['bundle']} does not hold exactly the pinned commits")
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone.git"
            git(tmp, "clone", "--mirror", "--quiet", str(bundle.resolve()), str(clone), local_bundle=True)
            objects = len(object_set(clone))
        entry["bundle"] = {"file": task["bundle"], "sha256": sha256_file(bundle), "bytes": bundle.stat().st_size,
                           "refs": pins, "objects": objects}
        tasks.append(entry)
    digest = inputs_digest(tasks)
    return {"schema": MANIFEST_SCHEMA,
            "protocol": {"commit": plan["protocol_commit"], "plan": "docs/engineering/builder-1/BENCHMARK-PLAN.md"},
            "tool": plan["tool"], "agents": sorted(plan["agents"]), "tasks": tasks, "inputs_digest": digest,
            "assignment": assignment(digest, tasks, plan["agents"])}


# --- verification ---------------------------------------------------------------------------------------------------

def load_manifest(path):
    data = read_file(path, "manifest", MAX_JSON_BYTES)
    try:
        manifest = json.loads(data)
    except (UnicodeDecodeError, ValueError) as error:
        raise InputError(f"manifest {path} is not valid JSON") from error
    validate(manifest, "benchmark-freeze.schema.json", MANIFEST_SCHEMA, "manifest")
    unique(manifest["agents"], "agent")
    unique([t["id"] for t in manifest["tasks"]], "task")
    return manifest, data


def check_manifest(manifest, inputs_dir, bundles_dir, manifest_bytes):
    failures = []
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    input_blobs = {}
    for task in manifest["tasks"]:
        tid = task["id"]
        roles = [i["role"] for i in task["inputs"]]
        for needed in ("statement", "handoff_a", "gold_sheet"):
            if needed not in roles:
                failures.append(f"{tid}: no frozen {needed}")
        if len(set(roles)) != len(roles):
            failures.append(f"{tid}: an input role appears twice")
        for item in task["inputs"]:
            try:
                path = input_path(inputs_dir, item["file"], f"{tid}: input {item['role']}")
            except InputError:
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
    if sha256_file(path) != bundle["sha256"] or path.stat().st_size != bundle["bytes"]:
        return [f"{tid}: bundle changed after it was frozen"]
    try:
        prerequisites, heads = bundle_heads(path)
    except BundleError as error:
        return [f"{tid}: {error}"]
    failures = []
    if prerequisites:
        failures.append(f"{tid}: bundle needs prerequisite commits, so its history is incomplete")
    pinned = sorted({c for c in (task["target"], task["candidate"]) if c})
    if sorted(set(heads.values())) != pinned or sorted(bundle["refs"]) != pinned:
        failures.append(f"{tid}: bundle refs are not exactly the pinned commits")
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone.git"
        if git(tmp, "clone", "--mirror", "--quiet", str(path.resolve()), str(clone), check=False,
               local_bundle=True).returncode:
            return failures + [f"{tid}: bundle cannot be cloned"]
        present = object_set(clone)
        if len(present) != bundle["objects"]:
            failures.append(f"{tid}: bundle object count does not match the manifest")
        if present != reachable_set(clone):
            failures.append(f"{tid}: bundle holds objects not reachable from its refs")
        for later in task["must_be_absent"]:
            if later in present:
                failures.append(f"{tid}: later commit {later[:12]} is present")
        for blob, label in input_blobs.items():
            if blob in present:
                failures.append(f"{tid}: frozen input ({label}) is stored as a Git object")
        if manifest_blob in present:
            failures.append(f"{tid}: the manifest is stored as a Git object")
        for sha, data in blobs_with_contents(clone):
            if data[:1] == b"{" and b'"inputs_digest"' in data:
                try:
                    parsed = json.loads(data)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and parsed.get("schema") == MANIFEST_SCHEMA:
                    failures.append(f"{tid}: a freeze manifest is inside the source history")
        for commit in pinned:
            if commit not in present:
                failures.append(f"{tid}: pinned commit {commit[:12]} is missing")
        if task["candidate"] and task["target"] in present and task["candidate"] in present:
            bases = git(clone, "merge-base", "--all", task["target"], task["candidate"], check=False).stdout.split()
            if len(bases) != 1:
                failures.append(f"{tid}: target and candidate have no unique merge base")
    return failures


def task_entry(manifest, task_id):
    task = next((t for t in manifest["tasks"] if t["id"] == task_id), None)
    if task is None:
        raise InputError(f"task {task_id} is not in the manifest")
    return task


def input_bytes(manifest, inputs_dir, task, role):
    item = next((i for i in task["inputs"] if i["role"] == role), None)
    return None if item is None else input_path(inputs_dir, item["file"], f"{task['id']}: input {role}").read_bytes()


def check_workspace(manifest, inputs_dir, bundles_dir, task_id, arm, workspace):
    """The start state of one run: what must be present, and what must be absent. Any failure invalidates the run."""
    task = task_entry(manifest, task_id)
    workspace = Path(workspace)
    if not workspace.is_dir():
        return ["workspace: not a directory"]
    if git(workspace, "rev-parse", "--git-dir", check=False).returncode:
        return ["workspace: not a Git repository"]
    if git(workspace, "rev-parse", "--is-bare-repository").stdout.strip() == b"true":
        return ["workspace: a bare repository; a run needs a work tree checked out at the target"]
    top = git(workspace, "rev-parse", "--show-toplevel").stdout.decode().strip()
    if Path(top).resolve() != workspace.resolve():
        return ["workspace: not the top level of its work tree"]
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
    untrusted = []                      # anything here could run a program or bend `git status`, so it is not run
    keys = git(workspace, "config", "--local", "--no-includes", "--list", "--name-only", "-z", check=False)
    if keys.returncode:
        untrusted.append("workspace: the repository configuration cannot be read")
    for key in sorted({k.decode("utf-8", "replace").lower() for k in keys.stdout.split(b"\0") if k}):
        if key not in WORKSPACE_CONFIG:
            untrusted.append(f"workspace: unexpected repository configuration {shown(key)}")
    for extra in sorted(p.name for p in (git_dir / "info").glob("*") if p.name not in ("exclude", "grafts")):
        untrusted.append(f"workspace: unexpected Git file info/{shown(extra)}")
    failures += untrusted
    head = git(workspace, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False)
    if head.returncode:
        failures.append("workspace: HEAD is unborn; nothing is checked out")
    elif head.stdout.decode().strip() != task["target"]:
        failures.append("workspace: HEAD is not the task's target commit")
    branch = git(workspace, "symbolic-ref", "--quiet", "HEAD", check=False).stdout.decode().strip()
    if branch != "refs/heads/work":
        failures.append("workspace: HEAD is not on the branch work")
    expected = {"refs/heads/work": task["target"]}
    if task["candidate"]:
        expected["refs/heads/candidate"] = task["candidate"]
    refs = dict(line.split(" ", 1)[::-1] for line in
                git(workspace, "for-each-ref", "--format=%(objectname) %(refname)").stdout.decode().splitlines())
    if refs != expected:
        failures.append("workspace: refs are not exactly the expected work (and candidate) branches")
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone.git"
        bundle = Path(bundles_dir) / task["bundle"]["file"]
        if git(tmp, "clone", "--mirror", "--quiet", str(bundle.resolve()), str(clone), check=False,
               local_bundle=True).returncode:
            return failures + ["workspace: the task's bundle cannot be cloned"]
        allowed = object_set(clone)
    present = object_set(workspace)
    if allowed - present:
        failures.append(f"workspace: {len(allowed - present)} Git object(s) of the task's bundle are missing")
    if present - allowed:
        failures.append(f"workspace: {len(present - allowed)} Git object(s) not in the task's bundle")
    for later in task["must_be_absent"]:
        if later in present:
            failures.append(f"workspace: later commit {later[:12]} is present")
    if untrusted:
        return failures + ["workspace: the work tree was not inspected, because its Git configuration is not a "
                           "fresh clone's"] + private_file_failures(manifest, workspace)
    result = git(workspace, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all",
                 "--ignored=traditional", check=False)
    if result.returncode:
        return failures + ["workspace: Git cannot read the work tree's state; the repository is damaged"]
    status = result.stdout
    allowed_files = {f"{BOOTSTRAP}/{name}" for name in ARM_FILES[arm]}
    seen_bootstrap = set()
    for entry in filter(None, status.split(b"\0")):
        code, path = entry[:2].decode(), entry[3:].decode("utf-8", "replace")
        if code in ("??", "!!"):
            if path in allowed_files:
                seen_bootstrap.add(path)
            else:
                failures.append(f"workspace: unapproved untracked file {shown(path)}")
            continue
        if code[0] != " ":
            failures.append(f"workspace: staged change to {shown(path)}")
        if code[1] != " ":
            failures.append(f"workspace: tracked file {shown(path)} differs from the target commit")
    for name in ARM_FILES[arm]:
        path = workspace / BOOTSTRAP / name
        if f"{BOOTSTRAP}/{name}" not in seen_bootstrap or not path.is_file():
            failures.append(f"workspace: required bootstrap file {BOOTSTRAP}/{name} is missing")
            continue
        data = path.read_bytes()
        frozen = {"task.md": input_bytes(manifest, inputs_dir, task, "statement"),
                  "handoff.md": input_bytes(manifest, inputs_dir, task, "handoff_a")}.get(name)
        if name in ("task.md", "handoff.md") and data != frozen:
            failures.append(f"workspace: {BOOTSTRAP}/{name} is not the frozen input")
        if name == "context.md" and (not data.strip() or task["target"].encode() not in data):
            failures.append(f"workspace: {BOOTSTRAP}/context.md does not name the task's target commit")
    return failures + private_file_failures(manifest, workspace)


def private_file_failures(manifest, workspace):
    """Every regular file in the workspace, `.git` included, against the private inputs' hashes.

    Git never lists a path with a `.git` component, so a nested `.git` is refused outright, and a symbolic link
    inside the repository's own `.git` is refused because the walk does not follow it."""
    private = {i["sha256"]: i["role"] for t in manifest["tasks"] for i in t["inputs"] if i["role"] in PRIVATE_ROLES}
    failures = []
    for root, dirs, files in os.walk(workspace):
        here = Path(root)
        relative = here.relative_to(workspace)
        dirs.sort()
        inside_git = relative.parts[:1] == (".git",)
        for name in sorted(dirs + files):
            path = here / name
            where = shown((relative / name).as_posix())
            if name == ".git" and here != workspace:
                failures.append(f"workspace: nested Git directory or file {where}")
            if inside_git and path.is_symlink():
                failures.append(f"workspace: symbolic link {where} inside the Git directory")
        for name in sorted(files):
            path, where = here / name, shown((relative / name).as_posix())
            try:
                if not stat.S_ISREG(path.stat().st_mode):         # follows a file link: a linked private file counts
                    continue
                digest = sha256_file(path)
            except OSError:
                if path.is_symlink() and not path.exists():
                    continue                                       # a dangling link holds no bytes
                failures.append(f"workspace: {where} cannot be read")
                continue
            if digest in private:
                failures.append(f"workspace: private input {private[digest]} is present at {where}")
    return failures


def run_record(manifest, manifest_bytes, task_id, arm, workspace, inputs_dir):
    task = task_entry(manifest, task_id)
    context = {"A": "handoff.md", "B": "context.md"}.get(arm)
    data = (Path(workspace) / BOOTSTRAP / context).read_bytes() if context else None
    fingerprint = re.search(rb"sha256:[0-9a-f]{64}", data) if arm == "B" else None
    gold = next(i["sha256"] for i in task["inputs"] if i["role"] == "gold_sheet")
    record = {"schema": RUN_SCHEMA, "record_kind": "task_run",
              "record_id": f"{task_id}-{arm}-{hashlib.sha256(manifest_bytes).hexdigest()[:12]}-start",
              "freeze": {"manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "valid": True},
              "task": {"id": task_id, "set": task["set"], "held_out": task["held_out"]}, "arm": arm,
              "environment": {"bundle_sha256": task["bundle"]["sha256"], "object_sets_equal": True,
                              "must_be_absent_verified": True, "preflight_passed": True},
              "context": {"sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
                          "bytes": len(data) if data is not None else None,
                          "fingerprint": fingerprint.group(0).decode() if fingerprint else None,
                          "tool_commit": manifest["tool"]["commit"] if arm == "B" else None,
                          "selection_version": manifest["tool"]["selection_version"] if arm == "B" else None,
                          "preparation_minutes": None, "edited": None},
              "gold_sheet_sha256": gold, "context_scores": None, "run": None,
              "notes": ["Start record written by scripts/benchmark_freeze.py verify; the run's measures are pending."]}
    schema = load_schema("benchmark-run.schema.json")
    problems = schema_errors(record, schema, schema)
    if problems:
        raise OperatingError("the start record does not validate: " + "; ".join(problems[:3]))
    return record


# --- the isolated workspace -----------------------------------------------------------------------------------------

def make_workspace(manifest, inputs_dir, bundles_dir, task_id, arm, context, out):
    task = task_entry(manifest, task_id)
    out = Path(out)
    if os.path.lexists(out):                      # a dangling symbolic link counts as existing
        raise InputError(f"--out {out} exists")
    if not out.parent.is_dir():
        raise InputError(f"the parent directory of --out {out} does not exist")
    if arm == "B" and context is None:
        raise InputError("arm B needs --context, the generated package's Markdown")
    if arm != "B" and context is not None:
        raise InputError(f"arm {arm} takes no --context")
    context_bytes = read_file(context, "--context", MAX_CONTEXT_BYTES) if arm == "B" else None
    try:
        build_workspace(manifest, inputs_dir, bundles_dir, task, arm, context_bytes, out)
    except BaseException:
        if out.exists():                          # it did not exist before: remove the partial workspace
            shutil.rmtree(out)
        raise


def build_workspace(manifest, inputs_dir, bundles_dir, task, arm, context_bytes, out):
    bundle = Path(bundles_dir) / task["bundle"]["file"]
    git(out.parent, "clone", "--no-checkout", "--quiet", str(bundle.resolve()), str(out), local_bundle=True)
    if git(out, "ls-tree", "--name-only", task["target"], BOOTSTRAP).stdout.strip():
        raise InputError(f"the target commit tracks {BOOTSTRAP}, where the bootstrap files go")
    git(out, "checkout", "--quiet", "-B", "work", task["target"])
    if task["candidate"]:
        git(out, "branch", "candidate", task["candidate"])
    git(out, "remote", "remove", "origin")
    for ref in git(out, "for-each-ref", "--format=%(refname)").stdout.decode().splitlines():
        if ref not in ("refs/heads/work", "refs/heads/candidate"):
            git(out, "update-ref", "-d", ref)
    (out / BOOTSTRAP).mkdir()
    (out / BOOTSTRAP / "task.md").write_bytes(input_bytes(manifest, inputs_dir, task, "statement"))
    if arm == "A":
        (out / BOOTSTRAP / "handoff.md").write_bytes(input_bytes(manifest, inputs_dir, task, "handoff_a"))
    if arm == "B":
        (out / BOOTSTRAP / "context.md").write_bytes(context_bytes)
    exclude = Path(git(out, "rev-parse", "--absolute-git-dir").stdout.decode().strip()) / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    with open(exclude, "a", encoding="utf-8") as handle:
        handle.write(f"/{BOOTSTRAP}/\n")


# --- command line ---------------------------------------------------------------------------------------------------

def parse(argv):
    parser = argparse.ArgumentParser(prog="benchmark_freeze.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="derive a freeze plan from the published task plan")
    p.add_argument("--tasks", required=True)
    p.add_argument("--tool-commit", required=True)
    p.add_argument("--protocol-commit", required=True)
    p.add_argument("--selection-version", default="devcontext-selection-3")
    p.add_argument("--agent", action="append", required=True)
    p.add_argument("--out", required=True)
    b = sub.add_parser("bundle", help="bundle a planned task's pinned commits")
    for flag in ("--repo", "--plan", "--task", "--bundles"):
        b.add_argument(flag, required=True)
    m = sub.add_parser("manifest", help="write the detached freeze manifest")
    for flag in ("--plan", "--inputs", "--bundles", "--out"):
        m.add_argument(flag, required=True)
    w = sub.add_parser("workspace", help="build one run's isolated workspace")
    for flag in ("--manifest", "--inputs", "--bundles", "--task", "--out"):
        w.add_argument(flag, required=True)
    w.add_argument("--arm", required=True, choices=sorted(ARM_FILES))
    w.add_argument("--context")
    v = sub.add_parser("verify", help="verify the manifest, inputs, bundles and, optionally, a workspace")
    for flag in ("--manifest", "--inputs", "--bundles"):
        v.add_argument(flag, required=True)
    v.add_argument("--workspace")
    v.add_argument("--task")
    v.add_argument("--arm", choices=sorted(ARM_FILES))
    v.add_argument("--record")
    try:
        return parser.parse_args(argv)
    except SystemExit as stop:
        if stop.code in (0, None):
            raise                                     # --help
        raise InputError("invalid arguments; see --help") from None


def write_new(path, data, flag="--out"):
    try:
        with open(path, "xb") as handle:
            handle.write(data)
    except FileExistsError as error:
        raise InputError(f"{flag} {path} exists") from error
    except OSError as error:
        raise InputError(f"cannot write {flag} {path}") from error


def existing_dirs(args, *flags):
    for flag in flags:
        value = getattr(args, flag)
        if not Path(value).is_dir():
            raise InputError(f"--{flag} {value} is not an existing directory")


def run(argv):
    args = parse(argv)
    if args.command == "prepare":
        if not all(SHA.match(x) for x in (args.tool_commit, args.protocol_commit)):
            raise InputError("--tool-commit and --protocol-commit must be full 40-character SHAs")
        task_plan = read_json(args.tasks, "task plan")
        validate(task_plan, "benchmark-tasks.schema.json", TASK_PLAN_SCHEMA, "task plan")
        plan = prepare(task_plan, args.tool_commit, args.protocol_commit, args.agent, args.selection_version)
        check_plan(plan)
        write_new(args.out, (json.dumps(plan, indent=2) + "\n").encode())
        for entry in plan["not_pinned"]:
            print(f"{entry['id']}: not pinned ({entry['pin_when']}); left out of the freeze plan", file=sys.stderr)
        print(f"freeze plan: {len(plan['tasks'])} task(s)")
        return 0
    if args.command == "bundle":
        plan = read_json(args.plan, "freeze plan")
        check_plan(plan)
        task = next((t for t in plan["tasks"] if t["id"] == args.task), None)
        if task is None:
            raise InputError(f"task {args.task} is not in the freeze plan")
        existing_dirs(args, "bundles")
        out = Path(args.bundles) / task["bundle"]
        if out.exists():
            raise InputError(f"bundle {out} exists")
        make_bundle(args.repo, [c for c in (task["target"], task["candidate"]) if c], out)
        print(sha256_file(out))
        return 0
    if args.command == "manifest":
        plan = read_json(args.plan, "freeze plan")
        existing_dirs(args, "inputs", "bundles")
        manifest = make_manifest(plan, args.inputs, args.bundles)
        data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        write_new(args.out, data)
        print(hashlib.sha256(data).hexdigest())
        return 0
    manifest, data = load_manifest(args.manifest)
    existing_dirs(args, "inputs", "bundles")
    if args.command == "workspace":
        failures = check_manifest(manifest, args.inputs, args.bundles, data)
        if failures:
            for failure in failures:
                print(failure)
            return 1
        make_workspace(manifest, args.inputs, args.bundles, args.task, args.arm, args.context, args.out)
        print(f"workspace {args.out}: task {args.task}, arm {args.arm}")
        return 0
    if args.workspace and not (args.task and args.arm):
        raise InputError("--workspace needs --task and --arm")
    if args.record and not args.workspace:
        raise InputError("--record needs --workspace")
    failures = check_manifest(manifest, args.inputs, args.bundles, data)
    if args.workspace:
        failures += check_workspace(manifest, args.inputs, args.bundles, args.task, args.arm, args.workspace)
    for failure in failures:
        print(failure)
    if failures:
        return 1
    if args.record:
        record = run_record(manifest, data, args.task, args.arm, args.workspace, args.inputs)
        write_new(args.record, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(), "--record")
    print(f"verified: manifest {hashlib.sha256(data).hexdigest()}")
    return 0


def main(argv=None):
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except OperatingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
