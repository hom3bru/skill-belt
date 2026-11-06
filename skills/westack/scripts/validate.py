"""westack consistency checks (CLI). No task execution, permission grant or truth certification.

Thin command line over record.py (the task-record contract), evidence.py (receipts, controls,
fingerprint, snapshot) and skillmeta.py (front matter and package checks). Every earlier name is
re-exported here, so `import validate` keeps working.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys


def _sibling(name):
    """Load a sibling helper by path under a key unique to this copy of the core."""
    path = pathlib.Path(__file__).resolve().with_name(name + ".py")
    key = "westack_" + name + "_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return module


for _module in (_sibling("evidence"), _sibling("record"), _sibling("skillmeta")):
    globals().update({_name: getattr(_module, _name) for _name in _module.__all__})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    package = sub.add_parser("package")
    package.add_argument("path")
    actions = CONTRACT["$defs"]["action"]["properties"]["kind"]["enum"]
    init = sub.add_parser("init", help="create an incomplete canonical task without executing anything")
    init.add_argument("path")
    init.add_argument("--root", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--repo", help="repository to fingerprint for --patch and read HEAD from")
    init.add_argument("--revision")
    init.add_argument("--scope", required=True)
    init.add_argument("--patch")
    init.add_argument("--author", required=True)
    init.add_argument("--task-id", default="new-task")
    init.add_argument("--task-mode", choices=CONTRACT["$defs"]["task"]["properties"]["mode"]["enum"], default="build")
    init.add_argument("--size", choices=["tiny", "bounded", "cross-cutting"], default="bounded")
    init.add_argument("--allow-path", action="append", required=True)
    init.add_argument("--observe-path", action="append", default=[],
                      help="also fingerprint this path (tests, config) without granting writes")
    init.add_argument("--exclude", action="append", default=[], help="extra name or path to leave out of the fingerprint")
    init.add_argument("--no-default-excludes", action="store_true")
    init.add_argument("--allow-action", action="append", default=[], choices=actions)
    init.add_argument("--forbid-action", action="append", default=[], choices=actions)
    init.add_argument("--non-goal", action="append", default=[])
    task = sub.add_parser("task")
    task.add_argument("path")
    task.add_argument("--root", required=True)
    task.add_argument("--repo", help="recompute patch (and HEAD) from this repository")
    task.add_argument("--path", dest="paths", action="append", default=[],
                      help="fingerprint these paths instead of the record's definition")
    task.add_argument("--revision")
    task.add_argument("--scope")
    task.add_argument("--patch")
    task.add_argument("--previous")
    task.add_argument("--chain", help="folder of numbered versions; check each against its predecessor")
    observed = sub.add_parser("fingerprint", help="print the observed patch fingerprint and Git HEAD")
    observed.add_argument("--repo", required=True)
    observed.add_argument("--path", dest="paths", action="append", default=[])
    observed.add_argument("--root", help="evidence root to exclude when it is inside the repository")
    observed.add_argument("--exclude", action="append", default=None,
                          help="replace the default excludes (repeat for each name or path)")
    copy_file = sub.add_parser("snapshot", help="copy a tested file into <root>/snapshots/<sha256><suffix>")
    copy_file.add_argument("path")
    copy_file.add_argument("--root", required=True)
    advice = sub.add_parser("reconcile", help="diagnostic recommendation for one recorded action")
    advice.add_argument("path")
    advice.add_argument("--root", required=True)
    advice.add_argument("--action", required=True)
    advice.add_argument("--observed", required=True, choices=["applied", "not-applied", "unknown"])
    receipt = sub.add_parser("receipt", help="write the next version with one receipt; computes hashes, runs nothing")
    receipt.add_argument("path")
    receipt.add_argument("--root", required=True)
    receipt.add_argument("--repo", required=True)
    receipt.add_argument("--revision")
    receipt.add_argument("--id", required=True)
    receipt.add_argument("--claim", action="append", required=True,
                         help="acceptance, action, finding or review ID; repeat when one run backs several")
    receipt.add_argument("--type", required=True, choices=CONTRACT["$defs"]["evidence"]["properties"]["type"]["enum"])
    receipt.add_argument("--operation", required=True, help="the exact command or read, as run")
    receipt.add_argument("--environment", required=True)
    receipt.add_argument("--raw", help="raw output file (copied into snapshots/ when outside the evidence root)")
    receipt.add_argument("--artifact", help="tested file (snapshotted when outside the evidence root)")
    receipt.add_argument("--passed", type=int, default=0)
    receipt.add_argument("--failed", type=int, default=0)
    receipt.add_argument("--skipped", type=int, default=0)
    receipt.add_argument("--exit", type=int)
    receipt.add_argument("--expected-exit", type=int)
    receipt.add_argument("--status", choices=["passed", "failed", "inconclusive", "blocked", "not-run"],
                         help="default: failed when a case failed or the exit differs, else passed")
    receipt.add_argument("--patch-before", help="`fingerprint` taken before the check ran; a different patch now voids the receipt")
    receipt.add_argument("--control", help="ID of the failed broken-copy receipt for the same check")
    receipt.add_argument("--coverage")
    receipt.add_argument("--limitation", action="append", default=[])
    receipt.add_argument("--link", action="store_true", help="point named acceptance criteria at this receipt (passed, failed or inconclusive)")
    receipt_options(receipt)
    renew = sub.add_parser("refresh", help="write the next version bound to the observed repository and scope")
    renew.add_argument("path")
    renew.add_argument("--root", required=True)
    renew.add_argument("--repo", required=True)
    renew.add_argument("--revision")
    renew.add_argument("--scope", help="new scope label when the user's authority changed")
    renew.add_argument("--reason")
    renew.add_argument("--grant", action="append", default=[], choices=actions,
                       help="record an action kind the user granted within the current scope")
    renew.add_argument("--relax", action="append", default=[],
                       help="with --scope: make a criterion optional, drop a work unit or review, or 'independent-review'")
    renew.add_argument("--observe-path", action="append", default=[])
    renew.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()
    extra, notes = {}, []
    try:
        if args.mode == "init":
            print(json.dumps(start_task(args), indent=2))
            return 0
        if args.mode == "fingerprint":
            result = observe(args.repo, args.paths, args.root, args.exclude)
            result.pop("entries")
            print(json.dumps(dict(status="passed", **result,
                  claim="observed file-content fingerprint; not a review, test or permission"), indent=2))
            return 0
        if args.mode == "snapshot":
            print(json.dumps(dict(snapshot(args.path, args.root),
                  claim="byte copy for evidence; proves nothing about the file's behaviour"), indent=2))
            return 0
        if args.mode in {"receipt", "refresh"}:
            result = add_receipt(args) if args.mode == "receipt" else refresh(args)
            result["claim"] = "record write only; nothing executed, no permission granted"
            print(json.dumps(result, indent=2))
            return 1 if result["errors"] else 0
        if args.mode == "package":
            errors, extra = check_package(args.path), {"warnings": package_warnings(args.path)}
        elif args.mode == "reconcile":
            record = read_json(args.path)
            malformed = shape(record, CONTRACT["root"])
            # Consistency of the record itself; context binding is the task command's job.
            errors = malformed or check_task(record, args.root,
                                             {k: record[k] for k in ("revision", "scope_id", "patch_id")})
            action = None if malformed else next((a for a in record["actions"] if a["id"] == args.action), None)
            if action is None and not malformed:
                errors.append("unknown action: " + args.action)
            elif action is not None:
                extra = {"action": args.action, "observed": args.observed,
                         "recommendation": reconcile(action, args.observed)}
            extra["claim"] = ("diagnostic only: uses the caller's observation; does not observe the target "
                              "or make a retry safe")
        else:
            if args.chain and args.previous:
                raise ValueError("use --chain or --previous, not both")
            record = read_json(args.path)
            context, errors, notes, observed = task_context(args, record)
            errors += check_task(record, args.root, context,
                                 read_json(args.previous) if args.previous else None, notes)
            if args.chain:
                errors += check_chain(args.chain, args.path, notes, args.root)
            if observed and not shape(record, CONTRACT["root"]):
                root = pathlib.Path(args.root)
                if observed["patch"] != record["patch_id"]:
                    old = load_manifest(root, record["patch_id"])
                    if old is None:
                        notes.append("no stored manifest for the record's patch; refresh stores one")
                    else:
                        extra["changed_files"] = diff_entries(old, observed["entries"])
                base = record.get("fingerprint", {}).get("baseline")
                if record["work_units"] and base:
                    old = load_manifest(root, base)
                    if old is None:
                        notes.append("no stored manifest for the baseline patch; cannot compare against work units")
                    else:
                        changed = diff_entries(old, observed["entries"])
                        files = sorted(set(changed["added"] + changed["modified"] + changed["removed"]))
                        extra["outside_work_units"] = [f for f in files if not any(
                            within(f, unit["allowed_paths"]) for unit in record["work_units"])]
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        errors = ["malformed/unreadable input: " + str(exc)]
    report = {"status": "failed" if errors else "passed",
              "claim": "consistency-only; not truth, host enforcement or model qualification"}
    report.update(extra)
    if notes or args.mode == "task":
        report["notes"] = notes
    report["errors"] = errors
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
