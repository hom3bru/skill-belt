"""westack-tdd controls: write broken copies of the code under test from a mutation spec, and judge saved
test-runner outputs (a red run, or the broken-copy controls) against a green reference run.

  python controls.py plan SPEC --out NEW_FOLDER [--min-variants 2] [--max-files 5000]
  python controls.py judge --reference GREEN_RAW --run LABEL=RAW [--run ...] [--min-kills 2]
                           [--assertion-only] [--core WESTACK_CORE_FOLDER]

plan reads SPEC (JSON, format westack-tdd-controls-1):
  {"format": "westack-tdd-controls-1", "claim": "...", "root": "<folder to copy, relative to SPEC>",
   "command": "<the exact test command, recorded, never run>", "exclude": ["<name>", ...],
   "mutations": [{"id": "rate", "kind": "constant", "file": "<path under root>", "find": "<exact text>",
                  "replace": "<text>", "occurrence": 1}]}
Kinds: constant, argument, boundary, branch, side-effect, return, validation, error, other. Every mutation is
checked before anything is written: its file lies under root, its find text occurs (exactly once, or the
named occurrence), it changes something, and no two mutations make the same copy. Then each mutation gets
its own copy of root under NEW_FOLDER/<id>/ (skipping .git and caches, and any exclude names), with only that
one edit, and NEW_FOLDER/plan.json records the hashes and diffs. NEW_FOLDER must not exist and must lie
outside root. Exit 0 written, 1 refused (nothing written), 64 usage or unreadable spec.

judge parses each saved output with the westack core's scripts/checks.py (found beside this skill, or at
--core) and compares it with the reference, which must be a complete run with passes and no failures. Per run:
  killed           every reference test was selected and one or more failed on an assertion;
  killed-by-error  the only failures are errors (unittest ERROR, pytest ERROR): check the traceback reaches
                   the mutated line; --assertion-only stops these counting (use it for a red run);
  survived         every selected test passed: a gap in the test, or an equivalent mutant to argue in writing;
  blocked          unrecognised or incomplete output, zero tests, a different selection, a test newly
                   skipped, a flaky result, or a module that failed to import or collect.
Verdict: gap (exit 1) when anything survived; inconclusive (2) when anything is blocked or fewer than
--min-kills runs killed; supported (0) otherwise; no-reference or blocked (2) when the reference or the
parser is unusable; 64 usage.

Standard library only. It never runs a test, a command or git, and calls no network: the agent runs the
command in each copy and saves the raw output. plan writes only inside NEW_FOLDER; judge writes nothing.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import sys

FORMAT = "westack-tdd-controls-1"
KINDS = ("constant", "argument", "boundary", "branch", "side-effect", "return", "validation", "error", "other")
SKIP = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox"}
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__)/|(^|/)test_[^/]+$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$")
ERROR_STATUSES = {"ERROR"}


class Usage(Exception):
    pass


def _emit(report):
    sys.stdout.write(json.dumps(report, indent=2) + "\n")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ plan
def _load_spec(path):
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Usage("cannot read the spec: %s" % exc)
    if not isinstance(data, dict):
        raise Usage("the spec must be a JSON object")
    return data


def _files_under(root, skip):
    count = 0
    for _, folders, names in os.walk(root):
        folders[:] = [f for f in folders if f not in skip]
        count += sum(1 for n in names if n not in skip and not n.endswith((".pyc", ".pyo")))
    return count


def _locate(data, find, occurrence):
    """Byte offset of the chosen occurrence of `find`, the number found, and an error or None."""
    starts, at = [], data.find(find)
    while at != -1:
        starts.append(at)
        at = data.find(find, at + 1)
    if not starts:
        return None, 0, "not found"
    if occurrence is None:
        if len(starts) > 1:
            return None, len(starts), "found %d times: name an occurrence (1-%d)" % (len(starts), len(starts))
        return starts[0], 1, None
    if occurrence > len(starts):
        return None, len(starts), "occurrence %d asked for, found %d" % (occurrence, len(starts))
    return starts[occurrence - 1], len(starts), None


def plan(spec_path, out, min_variants, max_files):
    spec = _load_spec(spec_path)
    errors, warnings = [], []
    if spec.get("format") != FORMAT:
        errors.append("format must be %s" % FORMAT)
    for key in ("claim", "root", "command"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            errors.append("%s must be a non-empty string" % key)
    mutations = spec.get("mutations")
    if not isinstance(mutations, list) or not all(isinstance(m, dict) for m in mutations):
        errors.append("mutations must be a list of objects")
        mutations = []
    exclude = spec.get("exclude", [])
    if not isinstance(exclude, list) or not all(isinstance(x, str) and x for x in exclude):
        errors.append("exclude must be a list of names")
        exclude = []
    skip = SKIP | set(exclude)
    root = (pathlib.Path(spec_path).resolve().parent / str(spec.get("root") or "")).resolve()
    out = pathlib.Path(out).resolve()
    if errors:
        return {"format": FORMAT, "kind": "plan", "status": "refused", "errors": errors, "warnings": warnings}, 1
    if not root.is_dir():
        errors.append("root is not a folder: %s" % root)
    if out.exists():
        errors.append("the output folder exists; give a new one: %s" % out)
    if out == root or out.is_relative_to(root):
        errors.append("the output folder is inside the root; put broken copies outside the work: %s" % out)
    if len(mutations) < min_variants:
        errors.append("a claim needs at least %d broken copies (found %d); --min-variants lowers it only when "
                      "another control, such as the pre-fix red run, already counts" % (min_variants, len(mutations)))
    variants, seen_ids, outputs = [], set(), {}
    originals = {}
    for index, item in enumerate(mutations):
        label = "mutation %d (%s)" % (index + 1, item.get("id"))
        mid, kind, rel = item.get("id"), item.get("kind"), item.get("file")
        find, replace, occurrence = item.get("find"), item.get("replace"), item.get("occurrence")
        if not isinstance(mid, str) or not ID.fullmatch(mid):
            errors.append("%s: id must be lower-case letters, digits and hyphens" % label)
            continue
        if mid in seen_ids:
            errors.append("%s: duplicate id" % label)
            continue
        seen_ids.add(mid)
        if kind not in KINDS:
            errors.append("%s: kind must be one of %s" % (label, ", ".join(KINDS)))
        if not isinstance(find, str) or not find or not isinstance(replace, str):
            errors.append("%s: find (non-empty) and replace must be strings" % label)
            continue
        if occurrence is not None and (not isinstance(occurrence, int) or isinstance(occurrence, bool)
                                       or occurrence < 1):
            errors.append("%s: occurrence must be a positive integer" % label)
            continue
        if not isinstance(rel, str) or not rel.strip():
            errors.append("%s: file must be a path under root" % label)
            continue
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            errors.append("%s: file is outside the root: %s" % (label, rel))
            continue
        if not target.is_file():
            errors.append("%s: file not found under root: %s" % (label, rel))
            continue
        if find == replace:
            errors.append("%s: replace equals find, so it changes nothing" % label)
            continue
        data = originals.setdefault(target, target.read_bytes())
        needle = find.encode("utf-8")
        at, count, problem = _locate(data, needle, occurrence)
        if problem:
            hint = ""
            if count == 0 and b"\r\n" in data and "\n" in find and "\r\n" not in find:
                hint = "; the file uses CRLF line endings: write \\r\\n in find"
            errors.append("%s: %r in %s: %s%s" % (label, find, rel, problem, hint))
            continue
        mutated = data[:at] + replace.encode("utf-8") + data[at + len(needle):]
        if mutated == data:
            errors.append("%s: the edit changes nothing" % label)
            continue
        key = (target, _sha(mutated))
        if key in outputs:
            errors.append("%s: makes a copy identical to %s; each broken copy must differ" % (label, outputs[key]))
            continue
        outputs[key] = mid
        rel_posix = target.relative_to(root).as_posix()
        if TEST_PATH.search(rel_posix):
            warnings.append("%s mutates a test file (%s): a broken copy breaks the code under test, not the test"
                            % (mid, rel_posix))
        old_text = data.decode("utf-8", errors="replace").splitlines(keepends=True)
        new_text = mutated.decode("utf-8", errors="replace").splitlines(keepends=True)
        variants.append({"id": mid, "kind": kind, "file": rel_posix, "line": data[:at].count(b"\n") + 1,
                         "occurrence": occurrence or 1, "original_sha256": _sha(data), "mutated_sha256": key[1],
                         "path": str(out / mid),
                         "diff": "".join(difflib.unified_diff(old_text, new_text, "a/" + rel_posix, "b/" + rel_posix)),
                         "_bytes": mutated, "_target": target})
    if not errors and root.is_dir():
        files = _files_under(root, skip)
        if files > max_files:
            errors.append("root holds %d files, over --max-files %d: narrow root, add exclude names, or use the "
                          "core's disposable worktree recipe" % (files, max_files))
    kinds = {v["kind"] for v in variants}
    if len(variants) >= 2 and len(kinds) == 1:
        warnings.append("every mutation is of one kind (%s): prefer different kinds, such as a boundary and a "
                        "missing side effect" % kinds.pop())
    report = {"format": FORMAT, "kind": "plan", "claim": spec.get("claim"), "command": spec.get("command"),
              "root": str(root), "out": str(out), "errors": errors, "warnings": warnings}
    if errors:
        report.update(status="refused", variants=[])
        return report, 1
    out.mkdir(parents=True)
    ignore = shutil.ignore_patterns(*sorted(skip), "*.pyc", "*.pyo")
    for variant in variants:
        copy = out / variant["id"]
        shutil.copytree(root, copy, ignore=ignore, symlinks=True)
        written = copy / variant["_target"].relative_to(root)
        written.write_bytes(variant.pop("_bytes"))
        variant.pop("_target")
        if _sha(written.read_bytes()) != variant["mutated_sha256"]:
            raise RuntimeError("the broken copy did not land as planned: %s" % written)
    report.update(status="written", variants=variants,
                  note="nothing was run: run the command from each variant's path with the same selection as the "
                       "green run, save each raw output, then judge them")
    (out / "plan.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report, 0


# ------------------------------------------------------------------ judge
def _checks(core):
    folder = pathlib.Path(core) if core else pathlib.Path(__file__).resolve().parents[2] / "westack"
    path = (folder / "scripts" / "checks.py").resolve()
    if not path.is_file():
        return None, path
    key = "westack_tdd_checks_" + _sha(str(path).encode("utf-8"))[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return module, path


def _load_failed(name):
    return name.endswith(" (collection)") or "_FailedTest" in name


def _classify(parsed, reference_names):
    tests = parsed["tests"]
    names = {t["name"] for t in tests}
    if parsed["runner"] == "unknown" or not tests:
        return "blocked", "no tests parsed: zero executed is never a kill", []
    broken = sorted(t["name"] for t in tests if _load_failed(t["name"]))
    if broken:
        return "blocked", "a module failed to import or collect (%s): the copy broke loading, not behaviour" \
            % ", ".join(broken[:5]), []
    if not parsed["complete"]:
        return "blocked", "incomplete run: " + "; ".join(parsed.get("warnings") or ["counts disagree"]), []
    if names != reference_names:
        missing, extra = sorted(reference_names - names), sorted(names - reference_names)
        return "blocked", "a different selection from the reference (missing %s; extra %s): rerun the same " \
            "command" % (missing[:5] or "none", extra[:5] or "none"), []
    if any(t.get("flaky") for t in tests):
        return "blocked", "a test both passed and failed in this output: flaky, so it settles nothing", []
    if any(t["status"] == "skipped" for t in tests):
        return "blocked", "a test the reference ran is skipped here", []
    failed = [t for t in tests if t["status"] == "failed"]
    if not failed:
        return "survived", "every selected test passed against this copy", []
    names_failed = sorted(t["name"] for t in failed)
    if all(t.get("raw_status") in ERROR_STATUSES for t in failed):
        return "killed-by-error", "only errors, no assertion failed: check the traceback reaches the changed " \
            "line", names_failed
    return "killed", "a selected test failed", names_failed


def judge(reference, runs, min_kills, assertion_only, core):
    report = {"format": FORMAT, "kind": "judge", "reference": str(reference), "runs": [], "reasons": []}
    labels, paths = set(), {str(pathlib.Path(reference).resolve())}
    pairs = []
    for item in runs:
        label, sep, raw = item.partition("=")
        if not sep or not label or not raw:
            raise Usage("--run takes LABEL=PATH, found %r" % item)
        if label in labels:
            raise Usage("label used twice: %s" % label)
        labels.add(label)
        resolved = str(pathlib.Path(raw).resolve())
        if resolved in paths:
            report.update(verdict="inconclusive", exit_code=2)
            report["reasons"].append("the same output file is named twice (%s): each run needs its own output" % raw)
            return report
        paths.add(resolved)
        pairs.append((label, raw))
    if not pairs:
        raise Usage("give at least one --run LABEL=PATH")
    checks, where = _checks(core)
    if checks is None:
        report.update(verdict="blocked", exit_code=2)
        report["reasons"].append("the westack core's checks.py was not found at %s: parse the outputs by hand" % where)
        return report
    try:
        ref = checks.load(reference)
    except Exception as exc:  # the core raises its own usage error type
        raise Usage(str(exc))
    report["parser"] = str(where)
    counts = ref["counts"]
    problems = []
    if ref["runner"] == "unknown" or not ref["tests"]:
        problems.append("no tests parsed")
    elif not ref["complete"]:
        problems.append("incomplete: " + "; ".join(ref.get("warnings") or []))
    if counts["failed"]:
        problems.append("%d failing tests: the reference must be green" % counts["failed"])
    if not counts["passed"]:
        problems.append("nothing passed")
    if any(_load_failed(t["name"]) for t in ref["tests"]):
        problems.append("a module failed to load")
    report["reference_counts"] = counts
    if problems:
        report.update(verdict="no-reference", exit_code=2)
        report["reasons"].append("the reference is not a usable green run: " + "; ".join(problems))
        return report
    reference_names = {t["name"] for t in ref["tests"]}
    for label, raw in pairs:
        try:
            parsed = checks.load(raw)
        except Exception as exc:
            raise Usage(str(exc))
        outcome, reason, failed = _classify(parsed, reference_names)
        report["runs"].append({"label": label, "source": str(raw), "source_sha256": parsed.get("source_sha256"),
                               "runner": parsed["runner"], "counts": parsed["counts"], "outcome": outcome,
                               "reason": reason, "failed_tests": failed[:20]})
    outcomes = [r["outcome"] for r in report["runs"]]
    counted = {"killed"} if assertion_only else {"killed", "killed-by-error"}
    kills = sum(o in counted for o in outcomes)
    report["kills"] = kills
    if "survived" in outcomes:
        report.update(verdict="gap", exit_code=1)
        report["reasons"].append("a copy survived: strengthen the test, or argue in writing that the mutant is "
                                 "equivalent (reachability, whether the value is used, the inputs tried)")
    elif "blocked" in outcomes:
        report.update(verdict="inconclusive", exit_code=2)
        report["reasons"].append("a run is blocked, so it shows nothing about the test")
    elif kills < min_kills:
        report.update(verdict="inconclusive", exit_code=2)
        report["reasons"].append("%d run(s) killed%s; the claim needs %d" % (
            kills, " on an assertion" if assertion_only else "", min_kills))
    else:
        report.update(verdict="supported", exit_code=0)
    report["claim"] = "judged saved outputs only; ran nothing, so it is only as true as those outputs"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.error = lambda message: (_ for _ in ()).throw(Usage(message))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("spec")
    p.add_argument("--out", required=True)
    p.add_argument("--min-variants", type=int, default=2)
    p.add_argument("--max-files", type=int, default=5000)
    j = sub.add_parser("judge")
    j.add_argument("--reference", required=True)
    j.add_argument("--run", action="append", default=[])
    j.add_argument("--min-kills", type=int, default=2)
    j.add_argument("--assertion-only", action="store_true")
    j.add_argument("--core")
    try:
        args = parser.parse_args(argv)
        if args.command == "plan":
            if args.min_variants < 1 or args.max_files < 1:
                raise Usage("--min-variants and --max-files must be at least 1")
            report, code = plan(args.spec, args.out, args.min_variants, args.max_files)
        else:
            if args.min_kills < 1:
                raise Usage("--min-kills must be at least 1")
            report = judge(args.reference, args.run, args.min_kills, args.assertion_only, args.core)
            code = report.pop("exit_code")
            report["exit_code"] = code
    except Usage as exc:
        _emit({"format": FORMAT, "status": "usage", "errors": [str(exc)]})
        return 64
    _emit(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
