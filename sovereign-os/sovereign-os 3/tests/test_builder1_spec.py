"""Consistency checks for the Builder 1 specification (docs/engineering/builder-1/, PROPOSED; Issue #22).

No implementation exists. These tests keep the specification's own artifacts honest: the example package validates
against the schema, its fingerprint and usage follow SPEC.md §6 and §8, its terms follow §5.1, its authority order
follows §2.1, and every citation and excerpt is exact at the pinned commit. Standard library only; the schema
validator below implements exactly the keywords the schema uses and fails if the schema uses any other.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SPEC_DIR = PROJECT / "docs" / "engineering" / "builder-1"
SUPPORTED = {"$schema", "$id", "title", "description", "type", "additionalProperties", "required", "properties",
             "$defs", "$ref", "const", "enum", "pattern", "minLength", "maxLength", "minimum", "maximum", "minItems",
             "maxItems", "items"}
SHA = re.compile(r"^[0-9a-f]{40}$")


def load(name):
    return json.loads((SPEC_DIR / name).read_text(encoding="utf-8"))


def keywords(node, found):
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            if key in ("properties", "$defs"):
                for sub in value.values():
                    keywords(sub, found)
            elif key in ("items", "additionalProperties") and isinstance(value, dict):
                keywords(value, found)
    return found


def is_type(value, name):
    return {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool), "boolean": isinstance(value, bool),
            "null": value is None}[name]


def errors(value, schema, root, where="$"):
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].removeprefix("#/$defs/")]
    found = []
    if "const" in schema and value != schema["const"]:
        found.append(f"{where}: not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{where}: {value!r} not in enum")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(is_type(value, t) for t in types):
            return found + [f"{where}: not {types}"]
    if isinstance(value, dict):
        props = schema.get("properties", {})
        found += [f"{where}: missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            found += [f"{where}: unexpected {k}" for k in value if k not in props]
        for key, sub in value.items():
            if key in props:
                found += errors(sub, props[key], root, f"{where}.{key}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            found.append(f"{where}: {len(value)} items")
        if "items" in schema:
            for i, sub in enumerate(value):
                found += errors(sub, schema["items"], root, f"{where}[{i}]")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            found.append(f"{where}: length {len(value)}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            found.append(f"{where}: does not match {schema['pattern']}")
    elif is_type(value, "integer"):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            found.append(f"{where}: {value} out of range")
    return found


def fingerprint(package):
    body = {k: v for k, v in package.items() if k != "fingerprint"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def stopwords():
    spec = (SPEC_DIR / "SPEC.md").read_text(encoding="utf-8")
    line = next(l for l in spec.splitlines() if "**Stopwords (V1, 63 words):**" in l)
    words = [w.strip(" .") for w in line.split(":**", 1)[1].split(",")]
    assert len(words) == 63 == len(set(words))
    return words, spec


def test_schema_uses_only_keywords_this_validator_implements():
    assert keywords(load("context-package.schema.json"), set()) <= SUPPORTED


def test_example_package_validates_and_the_validator_is_not_vacuous():
    schema, example = load("context-package.schema.json"), load("context-package.example.json")
    assert errors(example, schema, schema) == []
    broken = copy.deepcopy(example)
    broken["items"][0]["class"] = "reviewer_said_closed"
    broken["conflicts"][0]["resolution"] = "reconciled"
    broken["unexpected"] = True
    assert len(errors(broken, schema, schema)) == 3


def test_example_fingerprint_usage_and_ids_follow_the_spec():
    example = load("context-package.example.json")
    assert example["fingerprint"] == fingerprint(example)
    assert example["usage"]["used_bytes"] == sum(len(i["excerpt"].encode("utf-8")) for i in example["items"])
    assert example["usage"]["items"] == len(example["items"])
    assert example["usage"]["used_bytes"] <= example["parameters"]["max_bytes"]
    assert all(len(i["excerpt"].encode("utf-8")) <= example["parameters"]["max_item_bytes"] for i in example["items"])
    assert [i["id"] for i in example["items"]] == [f"S{n}" for n in range(1, len(example["items"]) + 1)]


def test_example_terms_and_stopword_hash_follow_section_5_1():
    words, spec = stopwords()
    digest = hashlib.sha256(("\n".join(sorted(words)) + "\n").encode("utf-8")).hexdigest()
    example = load("context-package.example.json")
    assert example["generator"]["stopwords_sha256"] == digest and digest in spec
    expected = sorted({w for w in re.split(r"[^a-z0-9]+", example["task"]["text"].lower())
                       if len(w) >= 3 and w not in words})
    assert example["task"]["terms"] == expected


def git(*args):
    return subprocess.run(["git", "--no-replace-objects", *args], cwd=PROJECT, capture_output=True, check=False)


def require_objects(*shas):
    if git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("not a Git checkout")
    missing = [s for s in shas if git("cat-file", "-e", f"{s}^{{commit}}").returncode != 0]
    if missing and git("rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        pytest.skip(f"shallow clone without {missing}")
    assert not missing, f"pinned commits not found: {missing}"


def blob_lines(blob):
    return git("cat-file", "blob", blob).stdout.decode("utf-8").split("\n")


def status_line(lines):
    """SPEC.md §2.2: the first of the first 10 lines starting with `Status:` once a leading `- ` and emphasis marks
    are removed; case-sensitive; never inside a leading YAML front-matter block."""
    head = lines[:10]
    if head and head[0].strip() == "---":
        end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), len(lines))
        head = lines[end + 1:10]
    for line in head:
        if re.sub(r"[*_`]", "", line[2:] if line.startswith("- ") else line).startswith("Status:"):
            return line
    return None


def test_example_citations_and_excerpts_are_exact_at_the_pinned_commit():
    example = load("context-package.example.json")
    commit = example["repository"]["commit"]
    require_objects(commit)
    assert git("rev-parse", f"{commit}^{{tree}}").stdout.decode().strip() == example["repository"]["tree"]
    citations = [i["citation"] for i in example["items"]] + [s for c in example["conflicts"] for s in c["sides"]]
    for c in citations + [{"path": t["path"], "blob": t["blob"], "lines": [1, 1]} for t in example["tests"]]:
        assert git("rev-parse", f"{commit}:{c['path']}").stdout.decode().strip() == c["blob"], c["path"]
    for item in example["items"]:
        first, last = item["citation"]["lines"]
        lines = blob_lines(item["citation"]["blob"])
        assert item["excerpt"] == "\n".join(lines[first - 1:last]), item["id"]
        expected = status_line(lines) if item["citation"]["path"].endswith(".md") else None
        assert item["status_text"] == expected, item["id"]
    for test in example["tests"]:
        source = "\n".join(blob_lines(test["blob"]))
        assert all(re.search(rf"^def {name}\(", source, re.M) for name in test["names"])


def test_example_authority_order_follows_section_2_1():
    example = load("context-package.example.json")
    commit = example["repository"]["commit"]
    require_objects(commit)
    plan = f"{example['repository']['project_root']}/docs/engineering/BUILD-AND-INTEGRATION-PLAN.md"
    line = next(l for l in git("show", f"{commit}:{plan}").stdout.decode().splitlines()
                if l.startswith("**Authority order:**"))
    text = line[len("**Authority order:**"):].split(". ", 1)[0]
    assert example["authority_order"] == [part.strip() for part in text.split(" → ")]


def test_benchmark_tasks_are_pinned_and_planned_only():
    tasks = load("benchmark-tasks.json")
    assert tasks["status"].startswith("planned") and [t["id"] for t in tasks["tasks"]] == ["T1", "T2", "T3"]
    starts = []
    for task in tasks["tasks"]:
        assert (task["start_commit"] is None) == (task["pin_when"] is not None)
        assert task["manual_handoff"] is None and task["gold_set_sha256"] is None   # nothing frozen yet
        refs = [task["start_commit"], *(task["range"] or {}).values(), *task.get("other_inputs", {}).values(),
                *((task["reference_outcome"] or {}).get("commits", {}).values())]
        assert all(SHA.match(ref) for ref in filter(None, refs)), refs
        starts += filter(None, [task["start_commit"]])
    # Start commits are on main. Other pinned commits may live on PR or rehearsal branches, so only their form is
    # checked here; the benchmark's freeze step (BENCHMARK-PLAN.md §5) verifies them in the run environment.
    require_objects(*starts)
    spec = (SPEC_DIR / "SPEC.md").read_text(encoding="utf-8")
    assert load("context-package.schema.json")["properties"]["generator"]["properties"]["selection_version"][
        "const"] in spec
