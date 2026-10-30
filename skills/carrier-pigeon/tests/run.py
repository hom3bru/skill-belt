"""Run both Node suites (CLI and host) and print combined counts as JSON. Standard library only."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ((ROOT / "bin", "carrier-pigeon.test.mjs"), (ROOT / "host", "carrier-pigeon-host.test.mjs"))


def main():
    total = passed = failed = 0
    for cwd, script in SUITES:
        result = subprocess.run(["node", script], cwd=cwd, capture_output=True, text=True, timeout=600)
        out = result.stdout + result.stderr
        ok = len(re.findall(r"^ok \d+ ", out, re.M))
        bad = len(re.findall(r"^not ok \d+ ", out, re.M))
        if result.returncode and not bad:
            bad = 1
        if ok + bad == 0:
            bad = 1
        sys.stderr.write(out)
        total += ok + bad
        passed += ok
        failed += bad
    print(json.dumps(dict(total=total, passed=passed, failed=failed, skipped=0)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
