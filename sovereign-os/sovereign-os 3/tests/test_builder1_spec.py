"""Consistency checks for the Builder 1 specification (docs/engineering/builder-1/, PROPOSED, revision 3; Issue #22).

No implementation exists. These tests keep the specification's own artifacts honest:

- the example output validates against the schema, its fingerprint covers `package` and never `observations`
  (SPEC.md §8, F-10), and it respects the whole-output bound and the per-field limits, JSON and Markdown (§6, F-7);
- every citation, blob, symbol span, class and status line of the example is exact at the pinned commit, and every
  obligation is recomputed from Git and found satisfied (§2, §5.3, §5.4, F-4, F-5, F-6);
- the example passes the whole-output disclosure check (§9, F-2), and its rendering keeps data inside fences (§7.4, F-3);
- the facts the specification states about the baseline hold (AT-8, AT-9, §5.3 rule 8, decision scope);
- the benchmark task plan is executable against Git and holds no hashes (BENCHMARK-PLAN.md, F-8, F-11);
- the collection formats accept a record in which nothing was measured and reject invented values (F-9, F-11).

Standard library only. The schema validator below implements exactly the keywords the schemas use and fails if a
schema uses any other.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SPEC_DIR = PROJECT / "docs" / "engineering" / "builder-1"
SCHEMAS = ("context-package.schema.json", "benchmark-run.schema.json", "gold-sheet.schema.json",
           "benchmark-freeze.schema.json")
SUPPORTED = {"$schema", "$id", "title", "description", "type", "additionalProperties", "required", "properties",
             "$defs", "$ref", "const", "enum", "pattern", "minLength", "maxLength", "minimum", "maximum", "minItems",
             "maxItems", "items"}
SHA = re.compile(r"^[0-9a-f]{40}$")
ISSUE = re.compile(r"(?:(?<=^)|(?<=[\s(\[]))#(\d+)(?![\w-])")
CREDENTIAL = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
                        r"|(?<![A-Za-z0-9])(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|sk-|AKIA|xox[abpr]-)[A-Za-z0-9_-]{16,}"
                        r"|(?i:(?:password|secret|token)\s*[:=]\s*['\"][^'\"]+['\"])")
GOVERNANCE = {"AGENTS.md", "CLAUDE.md", "ARCHITECTURE.md", "ROADMAP.md", "docs/SECURITY-GATE.md", "docs/DEVELOPMENT.md"}
KEYWORDS = ("proposed", "accepted", "approved", "confirmed", "superseded", "rejected", "deprecated")


def load(name):
    return json.loads((SPEC_DIR / name).read_text(encoding="utf-8"))


def spec_text():
    return (SPEC_DIR / "SPEC.md").read_text(encoding="utf-8")


# --- a minimal JSON Schema validator for exactly the keywords in SUPPORTED -------------------------------------------

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
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool), "null": value is None}[name]


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
    elif is_type(value, "number"):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            found.append(f"{where}: {value} out of range")
    return found


# --- the rules of SPEC.md, restated independently ---------------------------------------------------------------------

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def fingerprint(output):
    """SPEC.md §8: the SHA-256 of the canonical JSON of `package` only."""
    return "sha256:" + hashlib.sha256(canonical(output["package"])).hexdigest()


def stopwords():
    line = next(l for l in spec_text().splitlines() if "**Stopwords (V1, 63 words):**" in l)
    words = [w.strip(" .") for w in line.split(":**", 1)[1].split(",")]
    assert len(words) == 63 == len(set(words))
    return words


def terms(text, words):
    """SPEC.md §5.1: non-ASCII becomes a space, then A-Z is lowercased and the text split on other characters."""
    ascii_text = "".join(c if ord(c) < 128 else " " for c in text).lower()
    return sorted({w for w in re.split(r"[^a-z0-9]+", ascii_text) if len(w) >= 3 and w not in words})


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


def status_keyword(line):
    """SPEC.md §2.3: the first of KEYWORDS to occur in the status line, after emphasis marks are removed."""
    phrase = re.sub(r"[*_`]", "", line).split("Status:", 1)[1].lower() if line else ""
    found = [(phrase.find(k), k) for k in KEYWORDS if k in phrase]
    return min(found)[1] if found else None


def cut512(text):
    data = text.encode("utf-8")
    return (text, False) if len(data) <= 512 else (data[:512].decode("utf-8", errors="ignore"), True)


def register_rows(lines):
    """(section, line number, text) for each body row of each table under a `## ` heading."""
    rows, section = [], None
    separator = re.compile(r"^\|\s*:?-{3,}")
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            section = line[3:].split(" (")[0].strip()
        elif line.startswith("|") and not separator.match(line) and not (i < len(lines) and separator.match(lines[i])):
            rows.append((section, i, line))
    return rows


def names(text, label):
    return re.search(rf"(?<![\w-]){re.escape(label)}(?![\w-])", text) is not None


def classify(rel, lines, line_no, path=None):
    """SPEC.md §5.3's class rules for a path relative to the project root (None outside it)."""
    if rel is None:
        return "governance_doc" if path in ("AGENTS.md", "CLAUDE.md") else "other"
    if rel == "CONSTITUTION.md":
        return "constitution_candidate"
    if rel == "docs/FOUNDER-DECISIONS.md":
        section = next((s for s, i, _ in register_rows(lines) if i == line_no), None)
        if section is None:
            return "governance_doc"                      # rule 2: text outside the table rows
        return "binding_decision" if section == "Approved" else "proposed_or_historical"
    if rel is not None and rel.startswith("docs/adr/"):
        return "adr"
    if rel is not None and re.fullmatch(r"docs/reviews/[^/]+-findings\.json", rel):
        return "recorded_findings"
    if rel is not None and rel.startswith("docs/reviews/"):
        return "builder_record"
    if rel == "docs/architecture/systems-registry.toml":
        return "registry_fact"
    if rel in GOVERNANCE or (rel is not None and re.fullmatch(r"docs/engineering/[^/]+\.md", rel)):
        return "governance_doc"
    if rel is not None and rel.endswith(".md"):
        found = status_line(lines)
        words = re.findall(r"[a-z]+", re.sub(r"[*_`]", "", found).split("Status:", 1)[1].lower()) if found else []
        if words[:1] == ["proposed"]:
            return "proposed_or_historical"
    if rel is not None and rel.startswith(("src/", "evaluation/")):
        return "source"
    if rel is not None and rel.startswith("tests/"):
        return "test"
    return "other"


def authority_order(build_plan_text):
    """SPEC.md §2.1, or None when the line (or the file) is absent."""
    if build_plan_text is None:
        return None
    line = next((l for l in build_plan_text.splitlines() if l.startswith("**Authority order:**")), None)
    if line is None:
        return None
    return [part.strip() for part in line[len("**Authority order:**"):].split(". ", 1)[0].split(" → ")]


# --- Git access (read-only) -------------------------------------------------------------------------------------------

def git(*args, data=None):
    return subprocess.run(["git", "--no-replace-objects", *args], cwd=PROJECT, input=data, capture_output=True,
                          check=False)


def require_objects(*shas):
    if git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("not a Git checkout")
    missing = [s for s in shas if git("cat-file", "-e", f"{s}^{{commit}}").returncode != 0]
    if missing and git("rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        pytest.skip(f"shallow clone without {missing}")
    assert not missing, f"pinned commits not found: {missing}"


def show(commit, path):
    result = git("show", f"{commit}:{path}")
    return result.stdout.decode("utf-8") if result.returncode == 0 else None


def blob_lines(blob):
    return git("cat-file", "blob", blob).stdout.decode("utf-8").split("\n")


def tree_blobs(commit, prefix):
    out = git("ls-tree", "-r", "-z", "--full-tree", commit).stdout.split(b"\0")
    entries = [e.split(b"\t", 1) for e in out if e]
    return {p.decode(): m.split()[2].decode() for m, p in entries
            if m.split()[0] in (b"100644", b"100755") and p.decode().startswith(prefix)}


def read_blobs(blobs):
    out = git("cat-file", "--batch", data=("\n".join(blobs) + "\n").encode()).stdout
    result, pos = {}, 0
    for blob in blobs:
        end = out.index(b"\n", pos)
        size = int(out[pos:end].split()[2])
        result[blob] = out[end + 1:end + 1 + size]
        pos = end + 2 + size
    return result


# --- the example output -----------------------------------------------------------------------------------------------

def example():
    return load("context-package.example.json")


def rendering():
    return (SPEC_DIR / "context-package.example.md").read_text(encoding="utf-8")


def test_schemas_use_only_keywords_this_validator_implements():
    for name in SCHEMAS:
        assert keywords(load(name), set()) <= SUPPORTED, name


def test_example_output_validates_and_the_validator_is_not_vacuous():
    schema, out = load("context-package.schema.json"), example()
    assert errors(out, schema, schema) == []
    broken = copy.deepcopy(out)
    broken["package"]["items"][0]["class"] = "reviewer_said_closed"
    broken["package"]["coverage"]["complete"] = False
    broken["observations"]["preflight"] = "skipped"
    broken["package"]["generator"]["selection_version"] = "devcontext-selection-2"
    broken["package"]["findings"].append({"source": "R1", "id": "F-7", "severity": "P1", "confidence": "confirmed",
                                          "status": "fixed", "independent_disposition": "accepted",
                                          "attribution": "reviewer-owned", "mandatory": False, "truncated": False})
    broken["unexpected"] = True
    assert len(errors(broken, schema, schema)) == 6


def test_fingerprint_covers_the_package_and_never_the_observations():
    """F-10: clean, dirty and bare clones of the same inputs give one fingerprint."""
    out = example()
    assert out["fingerprint"] == fingerprint(out)
    for change in ({"working_tree": "dirty"}, {"working_tree": "none", "repository_kind": "bare"},
                   {"git_version": "git version 9.9.9", "python_version": "3.12", "replace_refs_ignored": 3}):
        local = copy.deepcopy(out)
        local["observations"].update(change)
        assert fingerprint(local) == out["fingerprint"]
    edited = copy.deepcopy(out)
    edited["package"]["items"][0]["excerpt"] += " "
    assert fingerprint(edited) != out["fingerprint"]
    assert not {"working_tree", "repository_kind", "git_version", "python_version"} & set(
        json.dumps(out["package"]).split('"'))


def test_example_respects_the_output_bound_and_the_per_field_limits():
    """F-7: the whole serialized output, JSON and Markdown, is bounded, not only the excerpts."""
    out = example()
    package, parameters = out["package"], out["package"]["parameters"]
    assert len(canonical(out)) <= parameters["max_output_bytes"]
    assert len(rendering().encode("utf-8")) <= parameters["max_output_bytes"]
    sizes = [len(i["excerpt"].encode("utf-8")) for i in package["items"]]
    mandatory = [n for n, i in zip(sizes, package["items"]) if i["role"] != "optional"]
    core = [n for n, i in zip(sizes, package["items"]) if i["role"] == "core"]
    assert package["usage"] == {"excerpt_bytes": sum(sizes), "items": len(sizes), "mandatory_bytes": sum(mandatory),
                                "core_bytes": sum(core)}
    assert sum(sizes) <= parameters["max_output_bytes"] - parameters["reserve_bytes"]
    assert sum(core) <= parameters["core_bytes"] and len(sizes) <= parameters["max_items"]
    assert all(n <= parameters["max_item_bytes"] for n, i in zip(sizes, package["items"]) if i["role"] == "optional")
    for source in package["sources"]:
        assert len(source["path"].encode("utf-8")) <= 512
        assert source["status_line"] is None or len(source["status_line"].encode("utf-8")) <= 512
    assert len(package["task"]["text"]) <= 2000 and len(package["task"]["terms"]) <= 64
    assert len(package["task"]["anchors"]) <= 32 and len(package["missing"]) <= 40
    assert sum(len(t["names"]) for t in package["tests"]) <= 60
    assert [i["id"] for i in package["items"]] == [f"S{n}" for n in range(1, len(package["items"]) + 1)]
    roles = [i["role"] for i in package["items"]]
    assert roles == sorted(roles, key=["core", "required", "optional"].index)
    cited = [i["source"] for i in package["items"]] + [s for o in package["obligations"] for s in o["sources"]] + \
        [f["source"] for f in package["findings"]] + [t["source"] for t in package["tests"]] + \
        [s["source"] for c in package["conflicts"] for s in c["sides"]]
    first_use = list(dict.fromkeys(cited))
    assert [s["id"] for s in package["sources"]] == first_use == [f"R{n}" for n in range(1, len(first_use) + 1)]


def test_example_passes_the_whole_output_disclosure_check_and_the_check_is_not_vacuous():
    """F-2: the patterns run over the whole serialized output; a token after `_` is still found."""
    out = example()
    assert not CREDENTIAL.search(canonical(out).decode("ascii")) and not CREDENTIAL.search(rendering())
    fake = "ghp_" + "SYNTHETICFAKE0123456789abcd"
    planted = copy.deepcopy(out)
    planted["package"]["tests"][0]["names"].append(f"test_{fake}_is_rejected")
    assert CREDENTIAL.search(canonical(planted).decode("ascii"))
    assert not re.search(r"\bghp_[A-Za-z0-9]{20,}", f"test_{fake}_is_rejected")   # revision 1's pattern missed it
    assert not CREDENTIAL.search("risk-management-framework")                      # no match inside a word


def test_example_terms_and_stopword_hash_follow_section_5_1():
    words = stopwords()
    digest = hashlib.sha256(("\n".join(sorted(words)) + "\n").encode("utf-8")).hexdigest()
    package = example()["package"]
    assert package["generator"]["stopwords_sha256"] == digest and digest in spec_text()
    assert package["task"]["terms"] == terms(package["task"]["text"], words) and package["task"]["terms_omitted"] == 0
    assert terms("Kelvin K and café utf-8", words) == ["caf", "kelvin", "utf"]   # non-ASCII is a separator
    for anchor in package["task"]["anchors"]:
        assert anchor["value"] in package["task"]["text"]


def definitions(lines):
    """Qualified name -> [first line, last line] for top-level definitions and direct class members (SPEC.md §5.3)."""
    tree = ast.parse("\n".join(lines), feature_version=(3, 11))
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = [min([node.lineno] + [d.lineno for d in node.decorator_list]), node.end_lineno]
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        out[f"{node.name}.{member.name}"] = [
                            min([member.lineno] + [d.lineno for d in member.decorator_list]), member.end_lineno]
    return out


def test_example_citations_symbols_classes_and_obligations_are_exact_at_the_pinned_commit():
    """F-4, F-5 and F-6: exact excerpts and spans, classes by §5.3, and every obligation recomputed from Git."""
    package = example()["package"]
    target, root = package["inputs"]["target"], package["inputs"]["project_root"]
    commit = target["commit"]
    require_objects(commit)
    assert git("rev-parse", f"{commit}^{{tree}}").stdout.decode().strip() == target["tree"]
    sources = {s["id"]: s for s in package["sources"]}
    items = {i["id"]: i for i in package["items"]}
    lines_of = {}
    for source in package["sources"]:
        assert source["commit"] == commit
        assert git("rev-parse", f"{commit}:{source['path']}").stdout.decode().strip() == source["blob"], source["path"]
        lines = blob_lines(source["blob"])
        lines_of[source["id"]] = lines[:-1] if lines and lines[-1] == "" else lines
        found = status_line(lines_of[source["id"]]) if source["path"].endswith(".md") else None
        expected = cut512(found) if found is not None else (None, False)
        assert (source["status_line"], source["status_line_truncated"]) == expected, source["path"]
    rel = lambda path: path[len(root) + 1:] if path.startswith(root + "/") else None
    for item in package["items"]:
        source, lines = sources[item["source"]], lines_of[item["source"]]
        first, last = item["lines"]
        assert item["excerpt"] == "\n".join(lines[first - 1:last]), item["id"]
        assert item["span"][0] <= first <= last <= item["span"][1], item["id"]
        assert item["class"] == classify(rel(source["path"]), lines, first, source["path"]), item["id"]
        if item["symbol"] and source["path"].endswith(".py"):
            assert definitions(lines)[item["symbol"]] == item["span"], item["id"]
        elif item["symbol"] and source["path"].endswith(".md"):
            assert re.fullmatch(r"#{1,6} " + re.escape(item["symbol"]), lines[item["span"][0] - 1]), item["id"]
        elif item["symbol"]:
            assert lines[item["span"][0] - 1].strip() == item["symbol"], item["id"]
        assert (item["role"] == "optional") == (item["tier"] is not None) == (not item["obligations"]), item["id"]
    path_of = {s["id"]: s["path"] for s in package["sources"]}
    assert package["coverage"]["complete"] is True
    assert package["coverage"]["obligations"] == len(package["obligations"])
    task_kinds = {"adr", "symbol", "span", "path", "finding", "candidate"}
    assert package["coverage"]["task_obligations"] == sum(o["kind"] in task_kinds for o in package["obligations"])
    for obligation in package["obligations"]:
        held = [items[i] for i in obligation["items"]]
        assert all(obligation["id"] in i["obligations"] for i in held), obligation["id"]
        kind = obligation["kind"]
        if kind == "agents":
            agents = lines_of[held[0]["source"]]
            start = agents.index("## Read before consequential work") + 1
            end = next(n for n in range(start + 1, len(agents) + 1) if agents[n - 1].startswith("## ")) - 1
            assert path_of[held[0]["source"]] == f"{root}/AGENTS.md"
            assert sorted(n for i in held for n in range(i["lines"][0], i["lines"][1] + 1)) == list(range(start, end))
        elif kind == "security_gate":
            gate = lines_of[held[0]["source"]]
            assert [i["lines"][0] for i in held] == [next(n for n, l in enumerate(gate, 1) if "Current status:" in l)]
        elif kind == "authority_order":
            assert package["authority_order"]["item"] == held[0]["id"]
            assert held[0]["excerpt"].startswith("**Authority order:**")
            assert package["authority_order"]["order"] == authority_order(held[0]["excerpt"])
        elif kind == "symbol":
            name = obligation["anchor"].removesuffix("()")
            spans = {tuple(i["span"]) for i in held}
            assert len(spans) == 1 and all(i["symbol"].split(".")[-1] == name.split(".")[-1] for i in held)
            first, last = next(iter(spans))
            covered = sorted(n for i in held for n in range(i["lines"][0], i["lines"][1] + 1))
            assert covered == list(range(first, last + 1)), obligation["id"]       # every window, nothing more
            assert definitions(lines_of[held[0]["source"]])[held[0]["symbol"]] == [first, last]
        elif kind == "path":
            [sid] = obligation["sources"]
            outline = sources[sid]["outline"]
            expected = [[q, a, b] for q, (a, b) in definitions(lines_of[sid]).items()]
            assert outline == {"entries": expected[:200], "omitted": max(0, len(expected) - 200)}
            assert path_of[sid].endswith(obligation["anchor"])
        elif kind == "adr":
            [sid] = obligation["sources"]
            label = obligation["anchor"]
            assert re.search(rf"/docs/adr/{label[4:]}-[^/]+\.md$", path_of[sid])
            register = lines_of[held[0]["source"]]
            named = [n for _, n, row in register_rows(register) if names(row, label)]
            assert [i["lines"][0] for i in held] == named and named
        elif kind == "codeowners":
            owners = lines_of[held[0]["source"]]
            rules = [n for n, l in enumerate(owners, 1) if l.strip() and not l.lstrip().startswith("#")]
            assert set(i["lines"][0] for i in held) <= set(rules) and held
        else:
            raise AssertionError(f"unexpected obligation kind in the example: {kind}")
    windows = [i for i in package["items"] if i["symbol"] == "Vault._forget_plan"]
    first, last = windows[0]["span"]
    assert len("\n".join(lines_of[windows[0]["source"]][first - 1:last]).encode()) > package["parameters"]["max_item_bytes"]
    assert len(windows) == 2 and all(a["lines"][1] + 1 == b["lines"][0] for a, b in zip(windows, windows[1:]))
    for test in package["tests"]:
        defined = {n.name for n in ast.parse("\n".join(lines_of[test["source"]])).body if hasattr(n, "name")}
        wanted = set(package["task"]["terms"])
        assert all(name.split(".")[0] in defined and set(terms(name.replace("_", " "), stopwords())) & wanted
                   for name in test["names"])
    for conflict in package["conflicts"]:
        assert conflict["kind"] == "decision_status" and "is approved" not in conflict["summary"]
        status_side, *row_sides = conflict["sides"]
        adr_lines = lines_of[status_side["source"]]
        assert adr_lines[status_side["lines"][0] - 1] == status_line(adr_lines)
        assert status_keyword(status_line(adr_lines)) == "proposed"
        adr = "ADR-" + re.search(r"/docs/adr/(\d{4})-", path_of[status_side["source"]]).group(1)
        register = lines_of[row_sides[0]["source"]]
        named = [n for section, n, row in register_rows(register) if section == "Approved" and names(row, adr)]
        assert [s["lines"] for s in row_sides] == [[n, n] for n in named]
    assert {m["reason"] for m in package["missing"]} >= {"outside_v1_scope"}


MARKED = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def display(value):
    """SPEC.md §7.4: control and format characters, and trailing spaces and tabs, are shown as markers."""
    value = MARKED.sub(lambda m: f"⟪U+{ord(m.group(0)):04X}⟫", value)
    return re.sub(r"[ \t]+$", lambda m: "".join(f"⟪U+{ord(c):04X}⟫" for c in m.group(0)), value, flags=re.M)


def test_example_rendering_is_inert_and_every_derived_value_is_fenced():
    """F-3: fences of at least three backticks, longer than any inner run; data only inside fences."""
    text, package = rendering(), example()["package"]
    outside, inside, fence = [], [], None
    for line in text.split("\n"):
        marker = re.match(r"^(`{3,})(text)?$", line)
        if fence is None and marker and marker.group(2):
            fence = marker.group(1)
        elif fence is not None and line == fence:
            fence = None
        elif fence is not None:
            inside.append(line)
            assert not re.search("`{%d,}" % len(fence), line)
        else:
            assert not line.startswith("`"), line           # no malformed or stray fence outside a block
            outside.append(line)
    assert fence is None
    body = "\n".join(inside)
    for item in package["items"]:
        assert display(item["excerpt"]) in body, item["id"]
    assert display(package["task"]["text"]) in body
    assert not re.search(r"[ \t]$", text, re.M)                  # trailing whitespace is shown as a marker
    loose = "\n".join(outside)
    for item in package["items"]:
        for line in item["excerpt"].split("\n"):
            if len(line.strip()) >= 12:
                assert line not in loose, (item["id"], line)
    for source in package["sources"]:
        assert source["path"] not in loose
    assert "COMPLETE" in loose and "not a claim that it holds everything the task needs" in loose


def test_example_authority_order_follows_section_2_1_and_is_null_when_absent():
    """F-8: the order is extracted when the line exists and is null, never invented, when it does not."""
    package = example()["package"]
    commit, root = package["inputs"]["target"]["commit"], package["inputs"]["project_root"]
    t1 = next(t for t in load("benchmark-tasks.json")["tasks"] if t["id"] == "T1")["inputs"]["target"]
    require_objects(commit, t1)
    plan = f"{root}/docs/engineering/BUILD-AND-INTEGRATION-PLAN.md"
    assert package["authority_order"]["order"] == authority_order(show(commit, plan))
    assert authority_order(show(t1, plan)) is None


# --- facts the specification states about its baseline ----------------------------------------------------------------

BASELINE = "99f302637d95f3d78cdd26a9f75d7a8ca336be99"
ROOT = "sovereign-os/sovereign-os 3"


def test_baseline_status_conflicts_and_decision_scope_are_as_stated():
    """AT-8 and §2.3: `decision_status` conflicts for exactly ADR-0003 and ADR-0004; row scope is kept."""
    require_objects(BASELINE)
    register = show(BASELINE, f"{ROOT}/docs/FOUNDER-DECISIONS.md").split("\n")
    rows = register_rows(register)
    conflicts = []
    for path, blob in sorted(tree_blobs(BASELINE, f"{ROOT}/docs/adr/").items()):
        number = re.search(r"/docs/adr/(\d{4})-[^/]+\.md$", path)
        if not number or number.group(1) == "0000":
            continue
        adr, keyword = f"ADR-{number.group(1)}", status_keyword(status_line(blob_lines(blob)))
        sections = {section for section, _, row in rows if names(row, adr)}
        if keyword == "proposed" and "Approved" in sections or \
                keyword in ("accepted", "approved", "confirmed") and sections and \
                sections <= {"Proposed", "Rejected options"}:
            conflicts.append(adr)
    assert conflicts == ["ADR-0003", "ADR-0004"]
    adr5 = [row for section, _, row in rows if section == "Approved" and names(row, "ADR-0005")]
    assert any("D1–D14 approved" in row and "D15 deferred" in row for row in adr5)
    assert any(section == "Proposed" and "ADR-0004 amendment" in row for section, i, row in rows if i == 34)


def test_baseline_issue_anchor_and_proposed_document_rules_are_as_stated():
    """AT-9 and §5.2 rule 8, at the baseline."""
    require_objects(BASELINE)
    blobs = tree_blobs(BASELINE, ROOT + "/")
    data, texts = read_blobs(sorted(set(blobs.values()))), {}
    for path, blob in blobs.items():
        try:
            texts[path] = data[blob].decode("utf-8")
        except UnicodeDecodeError:
            continue
    hits = []
    for path, text in sorted(texts.items()):
        for number, line in enumerate(text.split("\n"), 1):
            clean = re.sub(r"\]\([^)]*\)", lambda m: "]" + " " * (len(m.group(0)) - 1),
                           re.sub(r"https?://\S+", lambda m: " " * len(m.group(0)), line))
            if any(m.group(1) == "15" for m in ISSUE.finditer(clean)):
                hits.append(f"{path[len(ROOT) + 1:]}:{number}")
    assert hits == ["docs/adr/0006-rowid-free-canonical-tables.md:60", "docs/architecture/systems-registry.toml:57",
                    "docs/reviews/2026-10-22-pr10-audit-remediation.md:116"]
    proposed = sorted(path[len(ROOT) + 1:] for path, text in texts.items() if path.endswith(".md") and
                      classify(path[len(ROOT) + 1:], text.split("\n"), 1) == "proposed_or_historical")
    assert proposed == ["docs/second-brain/OBSIDIAN-PROJECTION.md", "docs/second-brain/SECOND-BRAIN-VALIDATION.md"]


# --- the benchmark ------------------------------------------------------------------------------------------------------

def test_benchmark_task_plan_is_executable_and_holds_no_hashes():
    """F-8 and F-11: pinned inputs behave as the plan says; hashes live only in the detached freeze manifest."""
    plan = load("benchmark-tasks.json")
    assert plan["schema"] == "sovereign.devcontext.benchmark-tasks.v3" and plan["status"].startswith("planned")
    assert not re.search(r'"[a-z_]*sha256[a-z_]*"|[0-9a-f]{64}', json.dumps(plan)), "the task plan holds no hashes"
    tasks = {t["id"]: t for t in plan["tasks"]}
    assert list(tasks) == ["T1", "T2", "T3", "T4"]
    sets = plan["sets"]
    assert sets["calibration"]["tasks"] == ["T1", "T2"]
    assert not sets["calibration"]["evidence_of_gain"] and not sets["pilot"]["evidence_of_gain"]
    assert sets["pilot"]["size"] == sum(sets["pilot"]["mix"].values()) == 6
    assert sets["main"]["min_size"] >= 12 and sets["main"]["min_held_out"] >= 4 and sets["main"]["forward"] == ["T3", "T4"]
    limit = int(re.search(r"\| 1–([\d,]+) characters of UTF-8", spec_text()).group(1).replace(",", ""))
    assert plan["task_statement_max_chars"] == limit == 2000
    root = plan["project_root"]
    for task in tasks.values():
        assert (task["inputs"]["target"] is None) == (task["pin_when"] is not None)
        refs = [*task["inputs"].values(), *((task["reference_outcome"] or {}).get("commits", {}).values())]
        refs += [*(task["environment"] or {}).get("bundle_refs", []), *(task["environment"] or {}).get("must_be_absent", [])]
        assert all(SHA.match(ref) for ref in filter(None, refs)), refs
    pinned = [ref for t in tasks.values() if t["environment"] for ref in t["environment"]["bundle_refs"]]
    require_objects(*pinned)
    for task in (t for t in tasks.values() if t["environment"]):
        target, candidate = task["inputs"]["target"], task["inputs"]["candidate"]
        assert task["environment"]["bundle_refs"] == [r for r in (target, candidate) if r]
        for later in task["environment"]["must_be_absent"]:
            if git("cat-file", "-e", f"{later}^{{commit}}").returncode == 0:
                for ref in task["environment"]["bundle_refs"]:
                    assert git("merge-base", "--is-ancestor", later, ref).returncode == 1, (task["id"], later)
        expected = task["expected"]
        for path in expected["present_at_target"]:
            assert git("cat-file", "-e", f"{target}:{root}/{path}").returncode == 0, (task["id"], path)
        for path in expected["absent_at_target"]:
            assert git("cat-file", "-e", f"{target}:{root}/{path}").returncode != 0, (task["id"], path)
        build = authority_order(show(target, f"{root}/docs/engineering/BUILD-AND-INTEGRATION-PLAN.md"))
        assert (build is None) == (expected["authority_order"] is None)
        if candidate is None:
            continue
        bases = git("merge-base", "--all", target, candidate).stdout.decode().split()
        assert bases == [task["inputs"]["expected_merge_base"]]
        changed = git("diff-tree", "-r", "-z", "--no-renames", "--name-only", bases[0], candidate).stdout
        changed = [p.decode()[len(root) + 1:] for p in changed.split(b"\0") if p]
        assert changed == expected["candidate_changed_paths"]
        drifted = git("diff-tree", "-r", "-z", "--no-renames", "--name-only", bases[0], target).stdout
        drifted = {p.decode()[len(root) + 1:] for p in drifted.split(b"\0") if p}
        assert sorted(drifted & set(changed)) == expected["both_changed_paths"]
        for path in expected["present_at_candidate_only"]:
            assert git("cat-file", "-e", f"{candidate}:{root}/{path}").returncode == 0, path
            assert path in expected["absent_at_target"]


def null_record(kind):
    """A synthetic record in which nothing was measured: every measure null, every list empty."""
    count = lambda *keys: {k: None for k in keys}
    record = {"schema": "sovereign.devcontext.benchmark-run.v1", "record_kind": kind, "record_id": f"synthetic-{kind}",
              "freeze": {"manifest_sha256": None, "valid": False},
              "task": {"id": "T1", "set": "calibration", "held_out": False}, "arm": "B",
              "environment": count("bundle_sha256", "object_sets_equal", "must_be_absent_verified", "preflight_passed"),
              "context": count("sha256", "bytes", "fingerprint", "tool_commit", "selection_version",
                               "preparation_minutes", "edited"),
              "gold_sheet_sha256": None, "context_scores": None, "run": None, "notes": ["synthetic: nothing measured"]}
    if kind == "context_score":
        record["context_scores"] = {
            "scorer": {"name": "independent scorer", "independent_of_builder": True, "second_scorer": None},
            "critical": count("present_correct", "gold"), "security_authority": count("present_correct", "gold"),
            "statements": count("supported", "contradicted", "unverifiable"), "quotations": count("exact", "cited"),
            "asserted_authority_errors": None, "negative_fact_violations": None,
            "contradictions": count("surfaced", "gold"), "freshness": count("correct", "stale", "absent"),
            "irrelevant_bytes": None, "context_bytes": None, "input_tokens_reported": None, "reproducible": None,
            "security_failures": []}
    else:
        record["run"] = {
            "agent": {"name": "codex", "model": "unrecorded", "version": "unrecorded", "settings": "", "fresh_session": True,
                      "memory_disabled": True, "network": "provider_only"},
            "order": {"position": 1, "seed": "unset"}, "replicate": 1,
            "budget": {**count("max_tokens", "max_minutes", "max_cost_usd"), "max_revision_loops": 3},
            "stages": [{"stage": "agent_work", "started": None, "ended": None, "minutes": None}],
            "outcome": {"accepted": False, "within_budget": False, "elapsed_minutes": None, "ci_first_submission": "not_run",
                        "hidden_tests": "not_run", "revision_loops": 0, "p1_p2_defects": None, "security_defects": None,
                        "post_merge_defects": None, "founder_review_minutes": None,
                        "diff": count("lines_added", "lines_removed", "churn", "necessary_lines"),
                        "attributable_findings": None},
            "usage": {**count("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"),
                      "source": "unavailable"},
            "costs": {"metered_provider_usd": None, "tool_charges_usd": None,
                      "subscription_billing": "reported separately, never apportioned to runs"},
            "review": {"reviewer": "independent reviewer", "independent": True, "blind_to_arm": True,
                       "verdict": "NOT REVIEWED", "findings_artifact": None},
            "security_failures": [], "failure": "synthetic: not run"}
    return record


def test_collection_formats_accept_unmeasured_records_and_reject_invented_values():
    """F-9 and F-11: records hold end-to-end measures with nulls for what was not measured, and refuse what is not
    allowed; a gold sheet commits to nothing downstream of it; a freeze manifest validates."""
    run_schema, gold_schema, freeze_schema = (load(n) for n in ("benchmark-run.schema.json", "gold-sheet.schema.json",
                                                                 "benchmark-freeze.schema.json"))
    for kind in ("context_score", "task_run"):
        assert errors(null_record(kind), run_schema, run_schema) == [], kind
    broken = null_record("task_run")
    broken["run"]["costs"]["subscription_billing"] = "apportioned"
    broken["run"]["review"]["independent"] = False
    broken["run"]["agent"]["memory_disabled"] = False
    broken["run"]["outcome"]["elapsed_minutes"] = -1
    broken["run"]["stages"][0]["stage"] = "self_review"
    broken["freeze"].pop("valid")
    assert len(errors(broken, run_schema, run_schema)) == 6
    scored = null_record("context_score")
    scored["context_scores"]["scorer"]["independent_of_builder"] = False
    scored["context_scores"]["security_failures"] = ["none"]
    assert len(errors(scored, run_schema, run_schema)) == 2
    gold = {"schema": "sovereign.devcontext.gold-sheet.v1", "task": "T1",
            "author": {"role": "independent_reviewer", "name": "synthetic", "independent_of_builder": True},
            "commits": {"target": BASELINE, "candidate": None},
            "facts": [{"id": "G1", "class": "negative_fact", "statement": "ADR-0003 is approved as a whole.",
                       "critical": True, "citations": [{"commit": BASELINE, "path": f"{ROOT}/docs/FOUNDER-DECISIONS.md",
                                                        "lines": [10, 10]}]}]}
    assert errors(gold, gold_schema, gold_schema) == []
    gold["author"]["role"] = "builder"
    gold["manifest_sha256"] = "0" * 64                     # revision 2's cyclic field is no longer allowed
    assert len(errors(gold, gold_schema, gold_schema)) == 2
    sha, digest = "1" * 40, "2" * 64
    manifest = {"schema": "sovereign.devcontext.benchmark-freeze.v1",
                "protocol": {"commit": sha, "plan": "docs/engineering/builder-1/BENCHMARK-PLAN.md"},
                "tool": {"commit": sha, "selection_version": "devcontext-selection-3"}, "agents": ["codex"],
                "tasks": [{"id": "T1", "set": "calibration", "held_out": False, "target": sha, "candidate": None,
                           "must_be_absent": [], "inputs": [{"role": "statement", "file": "T1/s.md", "sha256": digest,
                                                             "bytes": 10}],
                           "bundle": {"file": "T1.bundle", "sha256": digest, "bytes": 100, "refs": [sha]}}],
                "inputs_digest": digest, "assignment": [{"task": "T1", "agent": "codex", "first_arm": "A"}]}
    assert errors(manifest, freeze_schema, freeze_schema) == []
    manifest["tasks"][0]["inputs"][0]["role"] = "manifest_hash"
    assert len(errors(manifest, freeze_schema, freeze_schema)) == 1


def test_spec_versions_and_companion_files_agree():
    schema, spec = load("context-package.schema.json"), spec_text()
    version = schema["$defs"]["package"]["properties"]["generator"]["properties"]["selection_version"]["const"]
    assert f"`selection_version` is `{version}`" in spec
    for name in ("BENCHMARK-PLAN.md", *SCHEMAS, "context-package.example.json", "context-package.example.md",
                 "benchmark-tasks.json"):
        assert f"]({name})" in spec and (SPEC_DIR / name).is_file(), name
    for record in ("2026-11-03-pr24-builder-response.md", "2026-11-03-pr24-round2-builder-response.md"):
        assert (PROJECT / "docs" / "reviews" / record).is_file(), record
    assert (PROJECT / "scripts" / "benchmark_freeze.py").is_file()
