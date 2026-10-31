"""Run the Node suites (CLI, host, context) and print combined counts as JSON. Standard library only.

Each suite reports every test as "ok N" or "not ok N" and ends with "# N tests, F failed (name)".
A suite that exits without a matching summary line stopped part-way, so it counts as a failure
even if every test it printed passed: tests it never reached must not pass silently.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ((ROOT / "bin", "carrier-pigeon.test.mjs"), (ROOT / "host", "carrier-pigeon-host.test.mjs"), (ROOT / "bin", "cp-context.test.mjs"))
SUMMARY = re.compile(r"^# (\d+) tests, (\d+) failed", re.M)


def main():
    total = passed = failed = 0
    for cwd, script in SUITES:
        result = subprocess.run(["node", script], cwd=cwd, capture_output=True, text=True, timeout=900)
        out = result.stdout + result.stderr
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
