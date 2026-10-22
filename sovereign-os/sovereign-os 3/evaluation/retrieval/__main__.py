"""`python -m evaluation.retrieval [--check]`: run Benchmark 0003 and write (or verify) its artifacts."""
from __future__ import annotations

import argparse
import sys

from .harness import HERE, evaluate, report, to_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.retrieval", description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify that results.json and report.md are current instead of writing them")
    args = parser.parse_args(argv)
    results = evaluate()
    outputs = {HERE / "results.json": to_json(results), HERE / "report.md": report(results)}
    if args.check:
        stale = [path.name for path, text in outputs.items() if not path.exists() or path.read_text("utf-8") != text]
        if stale:
            print(f"Stale: {', '.join(stale)}. Regenerate with `python -m evaluation.retrieval`.", file=sys.stderr)
            return 1
    else:
        for path, text in outputs.items():
            path.write_text(text, "utf-8")
    for name, r in results["retrievers"].items():
        s = r["summary"]
        print(f"{name:30} R@10 {s['recall_at']['10']:.3f}  MRR {s['mrr']:.3f}  "
              f"governed local {s['local']['governed_recall_items']:>7}  cloud {s['cloud']['governed_recall_items']:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
