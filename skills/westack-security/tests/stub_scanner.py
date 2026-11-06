"""A stand-in for gitleaks and Betterleaks in the tests: no real scanner is installed or run (SC-27).

  python stub_scanner.py dir|git FOLDER [--exit-code N] [--redact[=PERCENT]] [--validation] [--report-path FILE] [--partial]
                                        [--config FILE] [--ignore-gitleaks-allow]

It reproduces only the behaviour westack-security relies on, as the 2026-10-30 security brief cites it (sections 3f and
3g): exit 1 by default for findings and for a failed or partial scan, a findings exit code set by --exit-code, an error
after a partial scan that still writes an empty report and logs "no leaks found in partial scan", the summary line
"leaks found: N" or "no leaks found", and whole secrets in the log and report unless --redact is passed. `dir` reads
FOLDER/tree (the working tree); `git` reads FOLDER/history (blobs of earlier commits). The seeded fake key matches
FAKEKEY_ followed by twenty letters or digits.

The scanned project's own files (SC-38), as Betterleaks 1.9.0 treats them (cmd/root.go:38-44, :93, :232-248, :464-469):
without --config it loads FOLDER/.betterleaks.toml, else FOLDER/.gitleaks.toml, and drops a finding whose secret matches
an [allowlist] regexes entry or whose path matches a paths entry; a --config file that cannot be read stops the run
(exit 1); FOLDER/.betterleaksignore, else FOLDER/.gitleaksignore, is always read, and a line equal to a finding's
fingerprint drops it (the stub's fingerprint is "<path under FOLDER>:fake-key:<line>"); a "gitleaks:allow" or
"betterleaks:allow" comment on the finding's line drops it unless --ignore-gitleaks-allow is passed.
"""
import json
import pathlib
import re
import sys

try:
    import tomllib
except ImportError:  # Python before 3.11: a config is then read as empty
    tomllib = None

SEEDED = re.compile(r"FAKEKEY_[A-Za-z0-9]{20}")
INLINE_ALLOW = re.compile(r"(?:gitleaks|betterleaks):allow")


def _first(folder, names):
    return next((folder / name for name in names if (folder / name).is_file()), None)


def _allowlist(path):
    if path is None or tomllib is None:
        return [], []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    table = data.get("allowlist") or {}
    return [re.compile(p) for p in table.get("regexes") or []], [re.compile(p) for p in table.get("paths") or []]


def main(argv):
    if len(argv) < 2 or argv[0] not in ("dir", "git"):
        print("usage: stub_scanner.py dir|git FOLDER [flags]", file=sys.stderr)
        return 126
    mode, folder, flags = argv[0], pathlib.Path(argv[1]), argv[2:]
    exit_code, redact, report, config = 1, 0, None, None
    for n, flag in enumerate(flags):
        if flag == "--exit-code":
            exit_code = int(flags[n + 1])
        elif flag == "--redact":
            redact = 100
        elif flag.startswith("--redact="):
            redact = int(flag.split("=", 1)[1])
        elif flag == "--report-path":
            report = pathlib.Path(flags[n + 1])
        elif flag == "--config":
            config = pathlib.Path(flags[n + 1])
    if config is not None and not config.is_file():
        print("FTL unable to load config, err: no such file %s" % config)
        return 1
    regexes, paths = _allowlist(config if config is not None else _first(folder, (".betterleaks.toml", ".gitleaks.toml")))
    ignore_file = _first(folder, (".betterleaksignore", ".gitleaksignore"))
    ignored = set(ignore_file.read_text(encoding="utf-8").split()) if ignore_file else set()
    honour_inline = "--ignore-gitleaks-allow" not in flags
    root = folder / ("tree" if mode == "dir" else "history")
    files = sorted(p for p in root.rglob("*") if p.is_file())
    findings = []
    for number, path in enumerate(files):
        if "--partial" in flags and number == 1:
            if report:
                report.write_text("[]", encoding="utf-8")
            print("ERR failed to scan %s: stub read error" % path.name)
            print("WRN no leaks found in partial scan")
            return 1
        relative = path.relative_to(folder).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in SEEDED.finditer(line):
                if (any(r.search(match.group(0)) for r in regexes) or any(r.search(relative) for r in paths)
                        or "%s:fake-key:%d" % (relative, line_number) in ignored
                        or (honour_inline and INLINE_ALLOW.search(line))):
                    continue
                secret = match.group(0) if not redact else "REDACTED"
                findings.append({"RuleID": "fake-key", "File": relative, "Line": line_number, "Secret": secret})
                print("Finding: %s  File: %s  RuleID: fake-key" % (secret, relative))
    if report:
        report.write_text(json.dumps(findings), encoding="utf-8")
    print("INF scanned %d files" % len(files))
    if findings:
        print("WRN leaks found: %d" % len(findings))
        return exit_code
    print("INF no leaks found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
