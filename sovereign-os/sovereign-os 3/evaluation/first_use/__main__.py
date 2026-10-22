"""python -m evaluation.first_use --dry-run | --vault PATH"""
import argparse
import tempfile
from pathlib import Path

from evaluation.first_use import trial


def table(rows: list[dict]) -> str:
    lines = ["| Question | Expected recalled | Missed | Other evidence included | Approved memory | Cloud plan items |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        total = len(r["recalled"]) + len(r["missed"])
        lines.append(f"| {r['id']} {r['question']} | {len(r['recalled'])}/{total} | {', '.join(r['missed']) or '-'} "
                     f"| {len(r['noise'])} | {r['approved_memory']} | {r['cloud_items']} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="measure the five questions on a temporary vault")
    group.add_argument("--vault", help="create a NEW trial vault file at this path (outside any Git tree)")
    args = parser.parse_args()
    if args.vault:
        vault, result = trial.load(args.vault)
        print(f"Trial vault created: {vault.path}\nImport: {result}")
        print(f"Run it:  SOVEREIGN_DB_PATH='{vault.path}' python -m sovereign   (then open http://127.0.0.1:8765)")
        return
    with tempfile.TemporaryDirectory() as d:
        vault, result = trial.load(Path(d) / "trial.db")
        print(f"Import: {result}\n\nBefore approvals (claims are unverified proposals):\n{table(trial.measure(vault))}")
        print(f"\nAfter approving all {trial.approve_all_proposals(vault)} proposals:\n{table(trial.measure(vault))}")


if __name__ == "__main__":
    main()
