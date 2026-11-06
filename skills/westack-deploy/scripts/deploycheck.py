#!/usr/bin/env python3
"""westack-deploy helper. Standard library only; runs no command.

  python deploycheck.py detect   <repo>                       how this project deploys, from its files
  python deploycheck.py readback <url> [--revision REV] [--text TEXT] [--timeout S]   GET the target once, report checks
  python deploycheck.py validate <record.json>                check a deploy record (westack-deploy-record-1)

`readback` makes one HTTP GET to the URL it is given and nothing else. A read-back that does not show the target healthy
makes the deploy failed; it never reverts anything. Exit codes: 0 ok (readback: every check passed; validate: valid);
1 a readback check failed or the record is invalid; 64 usage or unreadable input.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

FORMAT = "westack-deploy-record-1"
PLATFORMS = ("fly", "render", "vercel", "netlify", "heroku", "railway", "github-actions", "cloudflare", "docker",
             "static", "custom")
ENVIRONMENTS = ("production", "staging", "preview", "local")
OUTCOMES = ("healthy", "failed", "unverified")
MAX_WAIT_MINUTES = 20
DEPLOY_STEP = re.compile(r"fly(?:ctl)? deploy|vercel\b[^\n]*--prod|netlify deploy|firebase deploy|kubectl apply|"
                         r"wrangler (?:deploy|publish)|railway up|render[^\n]*deploy|heroku[^\n]*(?:deploy|release)|"
                         r"actions/deploy-pages|peaceiris/actions-gh-pages|JamesIves/github-pages-deploy-action|"
                         r"aws s3 sync|gcloud (?:app|run) deploy|az webapp", re.I)
STATIC_DIRS = (".", "dist", "build", "public", "site", "_site", "out", "www")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect(repo: Path) -> dict:
    """Platforms named by the project's own files; each with the file that says so."""
    found = []

    def add(platform, evidence, **details):
        found.append(dict({"platform": platform, "evidence": evidence}, **details))

    if (repo / "fly.toml").is_file():
        m = re.search(r'(?m)^\s*app\s*=\s*["\']([^"\']+)["\']', _read(repo / "fly.toml"))
        add("fly", "fly.toml", **({"app": m.group(1), "url": f"https://{m.group(1)}.fly.dev"} if m else {}))
    if (repo / "render.yaml").is_file():
        m = re.search(r"(?m)^\s*-?\s*name:\s*([\w.-]+)", _read(repo / "render.yaml"))
        add("render", "render.yaml", **({"service": m.group(1)} if m else {}))
    for name in ("vercel.json", ".vercel"):
        if (repo / name).exists():
            add("vercel", name)
            break
    if (repo / "netlify.toml").is_file():
        m = re.search(r'(?m)^\s*publish\s*=\s*["\']([^"\']+)["\']', _read(repo / "netlify.toml"))
        add("netlify", "netlify.toml", **({"publish": m.group(1)} if m else {}))
    if (repo / "Procfile").is_file():
        add("heroku", "Procfile")
    for name in ("railway.json", "railway.toml"):
        if (repo / name).is_file():
            add("railway", name)
            break
    workflows = repo / ".github" / "workflows"
    if workflows.is_dir():
        for wf in sorted(list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))):
            m = DEPLOY_STEP.search(_read(wf))
            if m:
                add("github-actions", wf.relative_to(repo).as_posix(), step=m.group(0))
    if (repo / "wrangler.toml").is_file():
        add("cloudflare", "wrangler.toml")
    if (repo / "Dockerfile").is_file():
        add("docker", "Dockerfile", note="an image, not a target: where it runs is still to name")
    for d in STATIC_DIRS:
        if (repo / d / "index.html").is_file():
            add("static", f"{d}/index.html".lstrip("./") if d != "." else "index.html", folder=d)
            break
    return {"repo": str(repo), "platforms": found,
            "note": None if found else "no deploy configuration found: ask how this project deploys (custom)"}


def readback(url: str, revision: Optional[str] = None, text: Optional[str] = None, timeout: float = 10) -> dict:
    """One GET. Checks: a 2xx status, the revision in the body or an X-Revision header, and any expected text."""
    import urllib.error
    import urllib.request
    if not re.match(r"^https?://", url):
        raise ValueError(f"readback needs an http(s) URL, not {url!r}")
    started = time.time()
    status, body, headers, error = None, "", {}, None
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "westack-deploy-readback"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, headers = resp.status, {k.lower(): v for k, v in resp.headers.items()}
            body = resp.read(1 << 20).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status, error = exc.code, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        error = f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"
    checks = [{"name": "status", "passed": isinstance(status, int) and 200 <= status < 300,
               "detail": error or f"HTTP {status}"}]
    if revision:
        seen = revision in body or headers.get("x-revision", "").startswith(revision)
        checks.append({"name": "revision", "passed": seen,
                       "detail": f"{revision} {'found' if seen else 'not found'} in the response"})
    if text:
        checks.append({"name": "text", "passed": text in body, "detail": f"{text!r} {'found' if text in body else 'not found'}"})
    return {"url": url, "status": status, "elapsed_ms": int((time.time() - started) * 1000),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": checks}


def _grant_problems(grant, scope: str, target: str, where: str) -> list:
    g = grant if isinstance(grant, dict) else {}
    out = []
    if not str(g.get("by", "")).strip() or not str(g.get("said", "")).strip():
        out.append(f"{where}: the grant needs who gave it (by) and their words (said)")
    if g.get("scope") != scope:
        out.append(f"{where}: the grant's scope must be {scope}")
    if g.get("target") != target:
        out.append(f"{where}: the grant must name this target ({target!r}), not {g.get('target')!r}")
    return out


def _readback_problems(rb, outcome: str, where: str, steps: list) -> list:
    out = []
    failed_step = [s.get("name") for s in steps if isinstance(s, dict) and s.get("exit") != 0]
    if outcome == "unverified":
        if rb and isinstance(rb.get("status"), int):
            out.append(f"{where}: a read-back with a status is healthy or failed, not unverified")
        return out
    if not isinstance(rb, dict) or not isinstance(rb.get("checks"), list) or not rb["checks"]:
        return out + [f"{where}: {outcome} needs the read-back (url, status, checks)"]
    passed = all(isinstance(c, dict) and c.get("passed") is True for c in rb["checks"])
    ok_status = isinstance(rb.get("status"), int) and 200 <= rb["status"] < 300
    if outcome == "healthy":
        if not ok_status or not passed:
            out.append(f"{where}: a read-back that does not show the target healthy makes it failed")
        if not any(isinstance(c, dict) and c.get("name") == "revision" and c.get("passed") is True for c in rb["checks"]):
            out.append(f"{where}: healthy needs the revision read back: a reachable URL alone does not prove this deploy")
        if failed_step:
            out.append(f"{where}: healthy with failed steps: {', '.join(map(str, failed_step))}")
    return out


def validate(record: dict) -> list:
    if not isinstance(record, dict) or record.get("format") != FORMAT:
        return [f"format must be {FORMAT}"]
    errors = []
    if record.get("platform") not in PLATFORMS:
        errors.append(f"platform is one of {', '.join(PLATFORMS)}")
    target = record.get("target") if isinstance(record.get("target"), dict) else {}
    name = target.get("name")
    if not str(name or "").strip() or target.get("environment") not in ENVIRONMENTS:
        errors.append(f"target needs a name and an environment ({', '.join(ENVIRONMENTS)})")
    if len(str(record.get("revision") or "")) < 7:
        errors.append("revision is the commit or build id deployed (seven or more characters)")
    errors += _grant_problems(record.get("grant"), "deploy", name, "grant")
    steps = record.get("steps")
    if not isinstance(steps, list) or not steps or not all(
            isinstance(s, dict) and str(s.get("name", "")).strip() and isinstance(s.get("exit"), int) for s in steps):
        errors.append("steps lists each step with its name and exit code")
        steps = steps if isinstance(steps, list) else []
    outcome = record.get("outcome")
    if outcome not in OUTCOMES:
        errors.append(f"outcome is one of {', '.join(OUTCOMES)}")
    else:
        errors += _readback_problems(record.get("readback"), outcome, "readback", steps)
        if outcome == "unverified" and not str(record.get("unverified_reason", "")).strip():
            errors.append("unverified needs unverified_reason: what stopped the read-back")
    waited = record.get("waited_minutes", 0)
    if isinstance(waited, (int, float)) and waited > MAX_WAIT_MINUTES and not str(record.get("wait_grant", "")).strip():
        errors.append(f"a wait past {MAX_WAIT_MINUTES} minutes needs the user's yes (wait_grant)")
    rollback = record.get("rollback")
    if rollback is not None:
        rb = rollback if isinstance(rollback, dict) else {}
        errors += _grant_problems(rb.get("grant"), "rollback", name, "rollback")
        if isinstance(rb.get("grant"), dict) and isinstance(record.get("grant"), dict) \
                and rb["grant"].get("said") == record["grant"].get("said"):
            errors.append("rollback: a rollback has its own grant, never the deploy's words reused")
        if rb.get("outcome") not in OUTCOMES:
            errors.append(f"rollback: outcome is one of {', '.join(OUTCOMES)}")
        else:
            errors += _readback_problems(rb.get("readback"), rb["outcome"], "rollback.readback", rb.get("steps") or [])
    return errors


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    usage = __doc__.split("\n\n")[1]
    try:
        if len(argv) == 2 and argv[0] == "detect":
            if not Path(argv[1]).is_dir():
                raise ValueError(f"not a folder: {argv[1]}")
            print(json.dumps(detect(Path(argv[1])), indent=2))
            return 0
        if len(argv) >= 2 and argv[0] == "readback":
            opts, rest = {"--revision": None, "--text": None, "--timeout": "10"}, argv[2:]
            while rest:
                if rest[0] not in opts or len(rest) < 2:
                    raise ValueError(f"unknown option {rest[0]}")
                opts[rest[0]], rest = rest[1], rest[2:]
            result = readback(argv[1], opts["--revision"], opts["--text"], float(opts["--timeout"]))
            print(json.dumps(result, indent=2))
            return 0 if all(c["passed"] for c in result["checks"]) else 1
        if len(argv) == 2 and argv[0] == "validate":
            record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
            errors = validate(record)
            print(json.dumps({"status": "valid" if not errors else "invalid", "errors": errors}, indent=2))
            return 0 if not errors else 1
        raise ValueError("unknown command or wrong arguments")
    except (OSError, ValueError) as exc:
        print(f"deploycheck.py: {exc}\n{usage}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    sys.exit(main())
