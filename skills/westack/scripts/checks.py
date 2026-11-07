"""westack checks: turn saved test-runner output into per-test results and diff a baseline run against
an after-run, so "zero new failures" can be checked by test name.

It never runs a command. The agent runs the suite, saves the raw output, and passes the files here.
Formats: unittest (verbose), pytest (-v, or -rA short summary), TAP including node:test, jest or vitest
JSON (--json / --reporter=json), and the JSON that westack's tests/run.py writes.

  python checks.py parse <raw-output> [--output new.json]
  python checks.py diff <baseline> <after> [--rename OLD=NEW ...] [--output new.json]

A baseline or after file may be raw output or a saved `parse` result. Exit codes: parse 0 recognised,
2 unrecognised or no tests; diff 0 no new failures and nothing missing, 1 new failures, 2 cannot tell
(an incomplete run, missing or newly skipped tests, or changed failure text); 64 usage or input error.
Standard library only; writes only a new --output file (exclusive create).

A failure is pre-existing only if its name and its normalised failure text both match the baseline's
(EV-40). Where the runner output carries the text, `parse` saves it as the test's `signature`: the exception
line for unittest, the message after the id in a pytest summary line, the error block of a TAP failure, the
first failure message of a jest or vitest case. Timestamps, addresses, durations, temporary paths and line
numbers are normalised away, and a message cut at the terminal width still matches its full form. The same
name failing with different text is listed under `changed_failures`, unattributed: neither pre-existing nor
new, so the diff exits 2. A failure whose text one side did not capture is matched by name alone and listed
under `name_only`, so that gap is visible.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys

FORMAT = "westack-checks-1"
LIMIT = 64 * 1024 * 1024
FIXTURES = {"setUpClass", "tearDownClass", "setUpModule", "tearDownModule"}
COMPARE_SIGNATURES = True
NORMALISE = True
CAPTURE_TEXT = True
SIGNATURE_LIMIT = 300
_NOISE = (
    (re.compile(r"\x1b\[[0-9;]*[A-Za-z]"), ""),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<time>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "0xADDR"),
    (re.compile(r"(?:/tmp|/var/folders|/private/var)/\S*|[A-Za-z]:[\\/][^\s'\"]*[\\/]Temp[\\/]\S*"), "<tmp>"),
    (re.compile(r"\btmp[a-z0-9_]{6,}\b"), "<tmp>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|secs|seconds)\b"), "<duration>"),
    (re.compile(r"\bline \d+\b"), "line N"),
)


class UsageError(Exception):
    pass


def _signature(lines):
    """The failure text of one test: its message lines joined, noise normalised, capped; None when empty."""
    if not CAPTURE_TEXT:
        return None
    text = " | ".join(line.strip() for line in lines if line and line.strip())
    if NORMALISE:
        for pattern, replacement in _NOISE:
            text = pattern.sub(replacement, text)
    return " ".join(text.split())[:SIGNATURE_LIMIT] or None


def _same_signature(left, right):
    """Equal text, or one side cut at a terminal width (a trailing ellipsis) and a prefix of the other."""
    if left == right:
        return True
    for short, whole in ((left, right), (right, left)):
        if short.endswith(("...", "…")):
            stem = short.rstrip(".…").rstrip()
            if stem and whole.startswith(stem):
                return True
    return False


def _collect(entries):
    """Merge (name, status, raw[, failure text]) entries into sorted per-test results; any failure wins (flaky
    stays failed). A failed test keeps the first failure text any of its failed entries carried."""
    merged = {}
    for entry in entries:
        name, status, raw = entry[:3]
        text = entry[3] if len(entry) > 3 else None
        item = merged.setdefault(name, {"name": name, "status": status, "raw_status": raw, "occurrences": 0,
                                        "signature": None, "seen": set()})
        item["occurrences"] += 1
        item["seen"].add(status)
        if status == "failed" or (status == "passed" and item["status"] == "skipped"):
            item["status"], item["raw_status"] = status, raw
        if status == "failed" and text and not item["signature"]:
            item["signature"] = text
    tests = []
    for name in sorted(merged):
        item = merged.pop(name)
        item["flaky"] = {"passed", "failed"} <= item.pop("seen")
        if not item["signature"] or item["status"] != "failed":
            item.pop("signature")
        tests.append(item)
    return tests


def _counts(tests):
    return {"parsed": len(tests), "passed": sum(t["status"] == "passed" for t in tests),
            "failed": sum(t["status"] == "failed" for t in tests),
            "skipped": sum(t["status"] == "skipped" for t in tests)}


# ------------------------------------------------------------------ unittest
_UT_HEAD = re.compile(r"^(?P<indent>\s*)(?P<method>[A-Za-z_]\w*) \((?P<id>[A-Za-z_][\w.]*)\)(?P<sub> \(.*?\))?"
                      r"(?: \.\.\. ?(?P<rest>.*))?$")
_UT_RESULT = re.compile(r"(?:^|\.\.\. )(?P<result>ok|FAIL|ERROR|expected failure|unexpected success|skipped(?: .*)?)$")
_UT_BLOCK = re.compile(r"^(FAIL|ERROR): (?P<method>[A-Za-z_]\w*) \((?P<id>[A-Za-z_][\w.]*)\)(?: \(.*\))?$")
_UT_MAP = {"ok": "passed", "FAIL": "failed", "ERROR": "failed", "unexpected success": "failed",
           "expected failure": "skipped"}


def _ut_name(method, ident):
    return ident if ident.rsplit(".", 1)[-1] == method else ident + "." + method


def _ut_status(result):
    return ("skipped" if result.startswith("skipped") else _UT_MAP[result]), result.split(" ")[0]


_UT_SKIP_LINES = ("Traceback (most recent call last):", "During handling of the above exception, another exception "
                  "occurred:", "The above exception was the direct cause of the following exception:")


def _ut_close(report):
    """Sign a failure report: its unindented lines (the exception and its message), not the frames."""
    if report is not None:
        entry, lines = report
        entry[3] = _signature([ln for ln in lines if ln and not ln[0].isspace() and ln not in _UT_SKIP_LINES
                               and not re.match(r"^-{20,}$", ln)])


def parse_unittest(text):
    entries, warnings, pending = [], [], None
    reported = {}
    report = None  # (entry, lines) of the failure report being read
    for line in text.splitlines():
        block = _UT_BLOCK.match(line)
        if report is not None:
            if block or re.match(r"^={20,}$", line) or line.startswith("Ran "):
                _ut_close(report)
                report = None
            else:
                report[1].append(line)
        if block:
            entry = [_ut_name(block["method"], block["id"]), "failed", line.split(":")[0], None]
            entries.append(entry)
            report = (entry, [])
            pending = None
            continue
        head = _UT_HEAD.match(line)
        if head:
            name = _ut_name(head["method"], head["id"])
            rest = (head["rest"] or "").strip()
            result = _UT_RESULT.search(rest) if rest else None
            if result:
                status, raw = _ut_status(result["result"])
                entries.append((name, status, raw))
                pending = None
            elif head["sub"]:
                pending = None
            else:
                pending = name  # result follows on a later line (docstring or printed output)
            continue
        ran = re.match(r"^Ran (\d+) tests? in ", line)
        if ran:
            reported["total"] = int(ran[1])
            pending = None
            continue
        final = re.match(r"^(OK|FAILED)(?: \((.*)\))?$", line)
        if final:
            reported["outcome"] = final[1]
            for part in (final[2] or "").split(", "):
                key, _, value = part.partition("=")
                if value.isdigit():
                    reported[key.replace(" ", "_")] = int(value)
            continue
        if pending:
            result = _UT_RESULT.search(line.strip())
            if result:
                status, raw = _ut_status(result["result"])
                entries.append((pending, status, raw))
                pending = None
    _ut_close(report)
    tests = _collect(entries)
    real = [t for t in tests if t["name"].rsplit(".", 1)[-1] not in FIXTURES]
    complete = "total" in reported and len(real) == reported["total"]
    if "total" not in reported:
        warnings.append("no 'Ran N tests' line: the run may have been cut short")
    elif not complete:
        warnings.append("parsed %d tests but the runner reported %d" % (len(real), reported["total"]))
    return tests, reported, complete, warnings


# ------------------------------------------------------------------ pytest
_PY_VERBOSE = re.compile(r"^(?P<id>\S+?::.+?) (?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b.*$")
_PY_SUMMARY = re.compile(r"^(?P<status>PASSED|FAILED|ERROR|XFAIL|XPASS) (?P<id>\S+?::.+?)(?: - (?P<msg>.*))?$")
_PY_COLLECT = re.compile(r"^ERROR (?P<id>[^\s:]+\.py)(?: - (?P<msg>.*))?$")
_PY_FINAL = re.compile(r"^=*\s*(?P<parts>\d+ [a-z]+(?:, \d+ [a-z]+)*) in [\d.]+s\b")
_PY_MAP = {"PASSED": "passed", "FAILED": "failed", "ERROR": "failed", "SKIPPED": "skipped", "XFAIL": "skipped",
           "XPASS": "passed"}


def parse_pytest(text):
    entries, warnings, reported = [], [], {}
    for line in text.splitlines():
        line = line.rstrip()
        match = _PY_SUMMARY.match(line) or _PY_VERBOSE.match(line)
        if match:
            message = match.groupdict().get("msg")
            entries.append((match["id"].rstrip(), _PY_MAP[match["status"]], match["status"],
                            _signature([message]) if message else None))
            continue
        match = _PY_COLLECT.match(line)
        if match:
            entries.append((match["id"] + " (collection)", "failed", "ERROR",
                            _signature([match["msg"]]) if match["msg"] else None))
            continue
        match = _PY_FINAL.match(line)
        if match:
            for part in match["parts"].split(", "):
                number, word = part.split(" ")
                reported[{"error": "errors", "warning": "warnings"}.get(word, word)] = int(number)
    tests = _collect(entries)
    counted = sum(reported.get(k, 0) for k in ("passed", "failed", "skipped", "xfailed", "xpassed"))
    if not reported:
        warnings.append("no pytest summary line: the run may have been cut short")
        complete = False
    else:
        reported["total"] = counted
        complete = counted <= len(tests) <= counted + reported.get("errors", 0)
        if not complete:
            warnings.append("named %d tests but the summary counts %d; use pytest -v or -rA so every test is named"
                            % (len(tests), counted))
    return tests, reported, complete, warnings


# ------------------------------------------------------------------ TAP (node:test and generic)
_TAP_POINT = re.compile(r"^(?P<indent> *)(?P<ok>not ok|ok)\b(?: (?P<num>\d+))?(?: -)?(?: (?P<desc>.*?))?"
                        r"(?: # (?P<dir>(?i:skip|todo)\b.*))?$")
_TAP_SUBTEST = re.compile(r"^(?P<indent> *)# Subtest: (?P<name>.*)$")
_TAP_COUNT = re.compile(r"^# (tests|suites|pass|fail|cancelled|skipped|todo) (\d+)$")


_TAP_KEY = re.compile(r"^(?P<indent>\s*)(?P<key>error|message|code|expected|actual|failureType):\s?(?P<value>.*)$")


def _tap_text(yaml):
    """The error, message, code, expected and actual values of a TAP diagnostic block, block scalars included."""
    parts, index = [], 0
    while index < len(yaml):
        key = _TAP_KEY.match(yaml[index])
        index += 1
        if not key:
            continue
        value = key["value"].strip()
        if value[:1] in ("|", ">"):
            value, depth = "", len(key["indent"])
            while index < len(yaml) and (not yaml[index].strip() or len(yaml[index]) - len(yaml[index].lstrip()) > depth):
                value += " " + yaml[index].strip()
                index += 1
        parts.append("%s: %s" % (key["key"], value.strip().strip("'\"")))
    return _signature(parts)


def parse_tap(text):
    entries, warnings, reported = [], [], {}
    stack, points = {}, []
    plan, bail, in_yaml = None, False, False
    for line in text.splitlines():
        line = line.rstrip()
        if in_yaml:
            if line.strip() == "...":
                in_yaml = False
                continue
            if not line.strip() or len(line) - len(line.lstrip()) > points[-1]["pad"]:
                points[-1]["yaml"].append(line)
                continue
            in_yaml = False  # a line at the point's own indent is not diagnostics: read it normally
        if line.strip() == "---" and points:
            in_yaml = True
            continue
        sub = _TAP_SUBTEST.match(line)
        if sub:
            level = len(sub["indent"]) // 4
            stack = {k: v for k, v in stack.items() if k < level}
            stack[level] = sub["name"]
            continue
        point = _TAP_POINT.match(line)
        if point:
            level = len(point["indent"]) // 4
            desc = (point["desc"] or "").strip() or ("test " + (point["num"] or "?"))
            name = " > ".join([stack[k] for k in sorted(stack) if k < level] + [desc])
            directive = (point["dir"] or "").lower()
            status = ("skipped" if directive.startswith(("skip", "todo"))
                      else "passed" if point["ok"] == "ok" else "failed")
            parent = bool(points) and points[-1]["level"] > level
            points.append({"level": level, "name": name, "status": status,
                           "raw": point["ok"] + (" # " + directive.split()[0].upper() if directive else ""),
                           "parent": parent, "yaml": [], "pad": len(point["indent"])})
            continue
        count = _TAP_COUNT.match(line)
        if count:
            reported[count[1]] = int(count[2])
            continue
        if re.match(r"^1\.\.(\d+)", line):
            plan = int(line[3:].split()[0]) if plan is None else plan
        if line.startswith("Bail out!"):
            bail = True
    # A suite point closes after its children; keep it only when it failed without a failing child.
    for index, point in enumerate(points):
        text = _tap_text(point["yaml"]) if point["status"] == "failed" else None
        if not point["parent"]:
            entries.append((point["name"], point["status"], point["raw"], text))
            continue
        children = [p for p in points[:index] if p["name"].startswith(point["name"] + " > ")]
        if point["status"] == "failed" and not any(c["status"] == "failed" for c in children):
            entries.append((point["name"], "failed", point["raw"], text))
    tests = _collect(entries)
    leaves = sum(1 for p in points if not p["parent"])
    if "tests" in reported:
        reported["total"] = reported["tests"]
        complete = leaves == reported["tests"]
    elif plan is not None:
        reported["total"] = plan
        complete = sum(1 for p in points if p["level"] == 0) == plan
    else:
        complete = False
        warnings.append("no '# tests N' count or plan line: the run may have been cut short")
    if bail:
        complete = False
        warnings.append("the producer bailed out")
    if not complete and "total" in reported:
        warnings.append("parsed %d tests but the producer reported %d" % (leaves, reported["total"]))
    return tests, reported, complete, warnings


# ------------------------------------------------------------------ JSON (jest, vitest, westack run.py)
_JEST_MAP = {"passed": "passed", "failed": "failed", "pending": "skipped", "skipped": "skipped", "todo": "skipped",
             "disabled": "skipped", "focused": "passed"}


def _jest_text(messages):
    """The first failure message of a case up to its stack frames, or None."""
    first = messages[0] if isinstance(messages, list) and messages else None
    if not isinstance(first, str):
        return None
    lines = []
    for line in first.splitlines():
        if re.match(r"^\s+at ", line):
            break
        lines.append(line)
    return _signature(lines)


def parse_jest(data):
    entries, warnings = [], []
    files = [str(r.get("name", "")).replace("\\", "/") for r in data.get("testResults", [])]
    try:
        base = os.path.commonpath([os.path.dirname(f) for f in files]).replace("\\", "/") if files else ""
    except ValueError:
        base = ""
    asserted = 0
    for result, path in zip(data.get("testResults", []), files):
        short = path[len(base):].lstrip("/") if base and path.startswith(base) else path
        cases = result.get("assertionResults") or []
        for case in cases:
            title = case.get("fullName") or " ".join(list(case.get("ancestorTitles", [])) + [case.get("title", "")])
            raw = case.get("status", "")
            entries.append((short + " > " + title, _JEST_MAP.get(raw, "failed"), raw,
                            _jest_text(case.get("failureMessages"))))
            asserted += 1
        if not cases and result.get("status") == "failed":
            entries.append((short + " (suite)", "failed", "suite failed", _jest_text([result.get("message")])))
    reported = {k: data[k] for k in ("numTotalTests", "numPassedTests", "numFailedTests", "numPendingTests",
                                     "numTodoTests") if isinstance(data.get(k), int)}
    complete = "numTotalTests" in reported and asserted == reported["numTotalTests"]
    if "numTotalTests" in reported:
        reported["total"] = reported["numTotalTests"]
        if not complete:
            warnings.append("parsed %d tests but the report counts %d" % (asserted, reported["total"]))
    return _collect(entries), reported, complete, warnings


def parse_run_json(data):
    mapping = {"passed": "passed", "failed": "failed", "not-run": "skipped", "skipped": "skipped"}
    entries = [(t.get("test") or t.get("name"), mapping.get(t.get("status"), "failed"), t.get("status"))
               for t in data["tests"] if t.get("test") or t.get("name")]
    tests = _collect(entries)
    reported = {"total": data["collected"]} if isinstance(data.get("collected"), int) else {}
    complete = reported.get("total") == len(tests)
    return tests, reported, complete, [] if complete else ["parsed test count differs from the recorded count"]


# ------------------------------------------------------------------ entry points
def parse_text(text):
    """Detect the runner and parse; never raises on content."""
    text = text.lstrip("﻿")
    stripped = text.strip()
    runner, parsed = "unknown", ([], {}, False, ["output not recognised as unittest, pytest, TAP or jest/vitest JSON"])
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("testResults"), list):
            runner, parsed = "jest", parse_jest(data)
        elif isinstance(data, dict) and isinstance(data.get("tests"), list):
            runner, parsed = "westack-run", parse_run_json(data)
    elif re.search(r"(?m)^TAP version|^ *(?:not )?ok \d+", text):
        runner, parsed = "tap", parse_tap(text)
    elif re.search(r"(?m)^\S+::\S.* (?:PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b|^(?:FAILED|PASSED|ERROR) \S+::"
                   r"|^=+ .*\b(?:passed|failed)\b.* in [\d.]+s", text):
        runner, parsed = "pytest", parse_pytest(text)
    elif re.search(r"(?m)^\s*[A-Za-z_]\w* \([\w.]+\)(?: \(.*\))? \.\.\.|^Ran \d+ tests? in ", text):
        runner, parsed = "unittest", parse_unittest(text)
    tests, reported, complete, warnings = parsed
    if runner != "unknown" and not tests:
        complete = False
        warnings = warnings + ["zero tests parsed"]
    return {"format": FORMAT, "kind": "parse", "runner": runner, "tests": tests, "counts": _counts(tests),
            "reported": reported, "complete": bool(complete), "warnings": warnings}


def load(path):
    """A saved parse result, or raw runner output parsed now; both carry the source file's SHA-256."""
    path = pathlib.Path(path)
    if not path.is_file():
        raise UsageError("not a file: " + str(path))
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise UsageError("input exceeds 64 MiB: " + str(path))
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text.lstrip("﻿"))
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("format") == FORMAT and data.get("kind") == "parse":
        return data
    result = parse_text(text)
    result.update(source=str(path), source_sha256=hashlib.sha256(raw).hexdigest())
    return result


def diff(baseline, after, renames=()):
    """Compare two parse results by test name. `renames` maps baseline name prefixes to after-run prefixes."""
    def mapped(name):
        for old, new in renames:
            if name.startswith(old):
                return new + name[len(old):]
        return name
    before, before_text = {}, {}
    renamed = []
    for test in baseline["tests"]:
        name = mapped(test["name"])
        before[name] = test["status"]
        before_text[name] = test.get("signature")
        if name != test["name"]:
            renamed.append({"from": test["name"], "to": name})
    now = {t["name"]: t["status"] for t in after["tests"]}
    now_text = {t["name"]: t.get("signature") for t in after["tests"]}
    preexisting, changed, name_only = [], [], []
    for name in sorted(n for n, s in now.items() if s == "failed" and before.get(n) == "failed"):
        was, is_now = before_text.get(name), now_text.get(name)
        if not COMPARE_SIGNATURES:
            preexisting.append(name)
        elif not was or not is_now:
            preexisting.append(name)
            name_only.append(name)
        elif _same_signature(was, is_now):
            preexisting.append(name)
        else:
            changed.append({"name": name, "before": was, "after": is_now})
    report = {
        "format": FORMAT, "kind": "diff",
        "new_failures": sorted(n for n, s in now.items() if s == "failed" and before.get(n) != "failed"),
        "preexisting_failures": preexisting,
        "changed_failures": changed,
        "name_only": name_only,
        "fixed": sorted(n for n, s in now.items() if s == "passed" and before.get(n) == "failed"),
        "missing": sorted(set(before) - set(now)),
        "added": sorted(set(now) - set(before)),
        "newly_skipped": sorted(n for n, s in now.items() if s == "skipped" and before.get(n) in {"passed", "failed"}),
        "renamed": [r for r in renamed if r["to"] in now],
    }
    reasons = []
    for label, side in (("baseline", baseline), ("after-run", after)):
        if not side["tests"]:
            reasons.append("the " + label + " has no parsed tests")
        elif not side["complete"]:
            reasons.append("the " + label + " is incomplete: " + "; ".join(side["warnings"]))
    if report["missing"]:
        reasons.append("%d baseline tests are missing from the after-run (deleted, renamed or not collected); "
                       "map renames with --rename OLD=NEW" % len(report["missing"]))
    if report["newly_skipped"]:
        reasons.append("%d tests that ran in the baseline are now skipped" % len(report["newly_skipped"]))
    if changed:
        reasons.append("%d tests fail in both runs with different failure text (unattributed: neither pre-existing "
                       "nor new)" % len(changed))
    if report["new_failures"]:
        verdict, code = "new-failures", 1
    elif reasons:
        verdict, code = "inconclusive", 2
    else:
        verdict, code = "no-new-failures", 0
    summary = lambda side: {k: side.get(k) for k in ("runner", "source", "source_sha256", "complete", "counts", "reported")}
    report.update(verdict=verdict, exit_code=code, reasons=reasons, baseline=summary(baseline), after=summary(after),
                  claim="compares saved outputs by test name and failure text; ran nothing, so it is only as true as "
                        "those outputs")
    return report


def emit(result, output):
    text = json.dumps(result, indent=2) + "\n"
    if output:
        try:
            with pathlib.Path(output).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        except FileExistsError:
            raise UsageError("output exists; never replaced: " + str(output))
        except OSError as exc:
            raise UsageError("cannot write output: " + str(exc))
    sys.stdout.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.error = lambda message: (_ for _ in ()).throw(UsageError(message))
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("parse", help="per-test results from saved runner output")
    one.add_argument("source")
    one.add_argument("--output", help="also write the JSON to this new file (exclusive create)")
    two = sub.add_parser("diff", help="baseline against after-run, by test name")
    two.add_argument("baseline")
    two.add_argument("after")
    two.add_argument("--rename", action="append", default=[], metavar="OLD=NEW",
                     help="treat baseline names starting with OLD as starting with NEW (repeatable)")
    two.add_argument("--output")
    for child in (one, two):
        child.error = parser.error
    try:
        args = parser.parse_args(argv)
        if args.command == "parse":
            result = load(args.source)
            emit(result, args.output)
            return 0 if result["runner"] != "unknown" and result["tests"] else 2
        renames = []
        for item in args.rename:
            old, sep, new = item.partition("=")
            if not sep or not old:
                raise UsageError("--rename needs OLD=NEW")
            renames.append((old, new))
        report = diff(load(args.baseline), load(args.after), renames)
        emit(report, args.output)
        return report["exit_code"]
    except UsageError as exc:
        sys.stderr.write("checks.py: " + str(exc) + "\n")
        return 64


if __name__ == "__main__":
    sys.exit(main())
