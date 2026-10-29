"""Reject tracked runtime vault files and credential-like paths.

This checks tracked paths, not file contents or Git history.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import subprocess
import sys


def forbidden(path: str) -> bool:
    p = PurePosixPath(path)
    name = p.name.lower()
    if any(part in {"__pycache__", ".pytest_cache", ".venv"} for part in p.parts):
        return True
    if name in {".env", ".ds_store"} or (name.startswith(".env.") and name != ".env.example"):
        return True
    if name.endswith((".pyc", ".pyo", ".pem", ".key", ".p12", ".pfx")):
        return True
    if any(name.endswith(ext) or ext + "-" in name
           for ext in (".db", ".sqlite", ".sqlite3")):
        return True
    if any(part in {"private-exports", "private-backups", "vault-backups"} for part in p.parts):
        return True
    return False


def main() -> int:
    paths = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    tracked = [raw.decode("utf-8", errors="surrogateescape") for raw in paths if raw]
    bad = [path for path in tracked if forbidden(path)]
    if bad:
        print("Tracked runtime or credential-like files are forbidden:", file=sys.stderr)
        for path in bad:
            print(f"  {path}", file=sys.stderr)
        print("Untrack them; review Git history if private data was committed.", file=sys.stderr)
        return 1
    print(f"Repository hygiene: {len(tracked)} tracked paths checked; no forbidden paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
