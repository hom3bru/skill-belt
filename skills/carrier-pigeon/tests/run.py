"""Run the Node suites (CLI, tasks, host, context, MCP, hello, co, diagnostics) and print combined counts as JSON. Standard library only.

Each suite reports every test as "ok N" or "not ok N" and ends with "# N tests, F failed (name)".
A suite that exits without a matching summary line stopped part-way, so it counts as a failure
even if every test it printed passed: tests it never reached must not pass silently.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ((ROOT / "bin", "cp-identity.test.mjs"), (ROOT / "bin", "carrier-pigeon.test.mjs"), (ROOT / "bin", "cp-tasks.test.mjs"), (ROOT / "host", "carrier-pigeon-host.test.mjs"), (ROOT / "bin", "cp-context.test.mjs"),
          (ROOT / "bin", "carrier-pigeon-mcp.test.mjs"), (ROOT / "bin", "cp-hello.test.mjs"), (ROOT / "bin", "cp-co.test.mjs"),
          (ROOT / "bin", "cp-diagnostics.test.mjs"), (ROOT / "bin", "cp-build-repo.test.mjs"),
          (ROOT / "bin", "cp-build-runtime.test.mjs"), (ROOT / "bin", "cp-build.test.mjs"),
          (ROOT / "bin", "cp-build-recovery.test.mjs"))
SUMMARY = re.compile(r"^# (\d+) tests, (\d+) failed", re.M)


def main():
    total = passed = failed = 0
    # Focused developer runs may select host fixtures; the required suite must always execute all of them.
    suite_env = dict(os.environ)
    suite_env.pop("CARRIER_PIGEON_TEST_FILTER", None)
    # Run from inside a Claude Code session, test MCP servers would otherwise find that session's inbox and post test mail into it.
    for name in ("CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_SESSION_ID"):
        suite_env.pop(name, None)
    for cwd, script in SUITES:
        result = subprocess.run(["node", script], cwd=cwd, capture_output=True, timeout=900, env=suite_env)
        # Node writes UTF-8. Decode it as such, and pass on only ASCII: a caller that reads this output in its locale (verify.py: cp1252
        # on Windows) must never crash on one stray character in a test name.
        out = (result.stdout + result.stderr).decode("utf-8", "replace").encode("ascii", "backslashreplace").decode("ascii")
        ok = len(re.findall(r"^ok \d+ ", out, re.M))
        bad = len(re.findall(r"^not ok \d+ ", out, re.M))
        summary = SUMMARY.search(out)
        if not summary or int(summary.group(1)) != ok + bad:
            sys.stderr.write(script + ": no matching summary line; the suite stopped early\n")
            bad += 1
        elif result.returncode and not bad:
            bad = 1
        sys.stderr.write(out)
        total += ok + bad
        passed += ok
        failed += bad
    print(json.dumps(dict(total=total, passed=passed, failed=failed, skipped=0)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
