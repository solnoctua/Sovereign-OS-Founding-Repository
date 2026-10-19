import os
import tempfile

# `sovereign.app` builds a module-level app on import; keep it away from the
# repository's ./data vault so a test run never migrates or writes to it.
os.environ.setdefault("SOVEREIGN_DB_PATH", os.path.join(tempfile.mkdtemp(prefix="sovereign-test-"), "vault.db"))
