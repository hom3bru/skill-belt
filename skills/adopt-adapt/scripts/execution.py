"""Explicit local command execution with content-addressed diagnostic receipts.

This is a receipt helper, not an OS sandbox or an attestation service. Call it
only from a separately authorized workflow; ordinary research/validation paths
must never invoke commands through this module.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone

MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_STDOUT_PARSE_BYTES = 1024 * 1024
MAX_CHECKS = 10000
MAX_TIMEOUT = 3600
SHA256 = re.compile(r"[0-9a-f]{64}")


class Invalid(ValueError):
    """Invalid execution arguments or inconsistent stored receipt."""


def _load_aa():
    path = Path(__file__).with_name("aa.py")
    spec = importlib.util.spec_from_file_location("adopt_adapt_execution_aa", path)
    if spec is None or spec.loader is None:
        raise Invalid("could not load local aa.py utilities")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aa = _load_aa()


def _require(condition, message):
    if not condition:
        raise Invalid(message)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _absolute_path(value):
    if not isinstance(value, str):
        return False
    path = Path(value)
    return path.is_absolute() and ".." not in path.parts and str(path) == value


def _live_hash(value, label):
    path = Path(value)
    resolved = path.resolve(strict=True)
    _require(resolved == path, f"{label} path now resolves through a link or alias: {path}")
    return _sha(path)


def _sha(path):
    path = Path(path)
    _require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()), f"linked file is not allowed: {path}")
    _require(path.is_file(), f"expected a regular file: {path}")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _declared(paths, label):
    _require(isinstance(paths, list), f"{label} must be a list")
    result = []
    seen = set()
    for item in paths:
        original = Path(item)
        _require(not original.is_symlink() and not (hasattr(original, "is_junction") and original.is_junction()), f"{label} must not be a link")
        path = original.resolve(strict=True)
        _require(path.is_file(), f"{label} must name regular files")
        _require(str(path) not in seen, f"duplicate {label} path: {path}")
        seen.add(str(path))
        result.append({"path": str(path), "sha256": _sha(path)})
    return result


def _read_checks(stdout: bytes):
    """Parse one strict JSON object, returning (rows, error)."""
    if len(stdout) > MAX_STDOUT_PARSE_BYTES:
        return [], f"stdout exceeds {MAX_STDOUT_PARSE_BYTES} byte parse limit"
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(stdout.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        return [], f"malformed stdout JSON: {error}"
    if not isinstance(value, dict) or set(value) - {"checks", "schema_version"} or "checks" not in value:
        return [], "stdout must be exactly an object containing checks (and optional schema_version)"
    if "schema_version" in value and (type(value["schema_version"]) is not int or value["schema_version"] != 1):
        return [], "schema_version must be integer 1"
    rows = value["checks"]
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CHECKS:
        return [], f"checks must contain 1..{MAX_CHECKS} rows"
    seen = set()
    normalized = []
    for index, row in enumerate(rows):
        label = f"checks[{index}]"
        if not isinstance(row, dict):
            return [], f"{label} must be an object"
        required = {"id", "kind", "status", "detail"}
        if set(row) not in (required, required | {"reason"}):
            return [], f"{label} needs id, kind, status, detail; only skip rows may also have reason"
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in required):
            return [], f"{label} fields id, kind, status and detail must be nonempty strings"
        if row["id"] in seen:
            return [], f"duplicate check id: {row['id']}"
        seen.add(row["id"])
        if row["kind"] not in {"positive", "negative-control"}:
            return [], f"{label}.kind must be positive or negative-control"
        if row["status"] not in {"pass", "fail", "skip"}:
            return [], f"{label}.status must be pass, fail or skip"
        if row["status"] == "skip":
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                return [], f"{label} skip requires a nonempty reason"
        elif "reason" in row:
            return [], f"{label} reason is only allowed for skip rows"
        normalized.append(dict(row))
    return normalized, None


def _derived(rows, timed_out, exit_code, parse_error, execution_issue=None):
    positives = [row for row in rows if row["kind"] == "positive"]
    total = len(positives)
    skipped = sum(row["status"] == "skip" for row in positives)
    failed = sum(row["status"] == "fail" for row in positives)
    assertions = sum(row["status"] == "pass" for row in positives)
    controls = sum(row["kind"] == "negative-control" and row["status"] == "pass" for row in rows)
    reasons = []
    if timed_out:
        reasons.append("timeout")
    if exit_code != 0:
        reasons.append(f"exit code {exit_code}")
    if parse_error:
        reasons.append(parse_error)
    if execution_issue:
        reasons.append(execution_issue)
    if not positives:
        reasons.append("no positive checks")
    elif skipped == total:
        reasons.append("all positive checks skipped")
    if failed:
        reasons.append(f"{failed} failed check(s)")
    if any(row["kind"] == "negative-control" and row["status"] != "pass" for row in rows):
        reasons.append("negative-control skipped or failed")
    if controls == 0:
        reasons.append("no passing negative-control")
    if assertions == 0:
        reasons.append("no passing positive assertion")
    counts = {"total": total, "skipped": skipped, "failed": failed}
    eligible = not reasons
    return counts, assertions, controls, eligible, "eligible" if eligible else "; ".join(reasons)


def _execution_issue(tool, harnesses, inputs, logs):
    issues = []
    if tool.get("sha256") != tool.get("sha256_after"):
        issues.append("executable changed during execution")
    for label, rows in (("harness", harnesses), ("input", inputs)):
        for row in rows:
            if row.get("sha256") != row.get("sha256_after"):
                issues.append(f"declared {label} changed during execution: {row.get('path')}")
    for row in logs:
        if not row.get("reader_complete"):
            issues.append("output pipe did not close promptly; descendant process may remain")
            break
        if row.get("reader_error"):
            issues.append("output pipe read error")
            break
    return "; ".join(issues) or None


class _PipeDrain:
    """Drain a subprocess pipe while retaining only a bounded prefix."""

    def __init__(self, pipe):
        self.pipe = pipe
        self.data = bytearray()
        self.total = 0
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        try:
            while True:
                block = self.pipe.read(64 * 1024)
                if not block:
                    break
                self.total += len(block)
                remaining = MAX_LOG_BYTES - len(self.data)
                if remaining > 0:
                    self.data.extend(block[:remaining])
        except OSError as error:
            self.error = str(error)
        finally:
            try:
                self.pipe.close()
            except OSError:
                pass


def _capture_bytes(run_root, data, subject, revision):
    run_root = Path(run_root).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".execution-", dir=run_root)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        return aa.capture(run_root, name, subject, revision)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _public_capture(capture):
    return {key: capture[key] for key in ("id", "path", "sha256", "bytes")}


def execute(run_dir, command: list[str], cwd, harnesses: list[Path], inputs: list[Path], authorization: str,
            timeout: int, env_keys: list[str] | None = None, subject: str = "fixture", revision: str = "owned"):
    """Run an explicitly authorized local command and return captured evidence.

    The command is never invoked through a shell. This helper does not sandbox
    the process or authenticate its ancestry, network behavior, or semantic claim.
    """
    _require(isinstance(command, list) and command and all(isinstance(x, str) and x for x in command), "command must be a nonempty list of nonempty strings")
    _require(isinstance(authorization, str) and authorization.strip() and len(authorization) <= 2000, "authorization must be nonempty text of at most 2000 characters")
    _require(type(timeout) is int and 1 <= timeout <= MAX_TIMEOUT, f"timeout must be an integer from 1 to {MAX_TIMEOUT} seconds")
    if env_keys is None:
        env_keys = []
    _require(isinstance(env_keys, list) and all(isinstance(x, str) and x and "=" not in x for x in env_keys), "env_keys must be environment variable names")
    _require(len(env_keys) == len(set(env_keys)), "env_keys repeats a name")
    _require(isinstance(subject, str) and subject.strip() and isinstance(revision, str) and revision.strip(), "subject and revision must be nonempty")
    workdir = Path(cwd).resolve(strict=True)
    _require(workdir.is_dir(), "cwd must be an existing directory")
    before_harnesses = _declared(list(harnesses), "harnesses")
    before_inputs = _declared(list(inputs), "inputs")
    current_env = os.environ
    # Keep only Windows runtime essentials and explicitly authorized caller keys.
    child_env = {key: current_env[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in current_env}
    child_env.update({key: current_env[key] for key in env_keys if key in current_env})
    resolved = shutil.which(command[0], path=child_env.get("PATH", os.defpath))
    if resolved is None and Path(command[0]).is_file():
        resolved = command[0]
    _require(resolved is not None, f"could not resolve executable: {command[0]}")
    tool_path = Path(resolved).resolve(strict=True)
    tool_hash = _sha(tool_path)
    started = _now()
    invocation = [str(tool_path), *command[1:]]
    proc = subprocess.Popen(invocation, cwd=workdir, env=child_env, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=(os.name != "nt"), creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0))
    out = _PipeDrain(proc.stdout)
    err = _PipeDrain(proc.stderr)
    out.start(); err.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except (OSError, ProcessLookupError):
            pass
        proc.wait()
    out.thread.join(timeout=2)
    err.thread.join(timeout=2)
    # A still-open descendant pipe is outside the helper's process-ancestry guarantees.
    stdout, stderr = bytes(out.data), bytes(err.data)
    exit_code = proc.returncode
    finished = _now()
    after_harnesses = _declared(list(harnesses), "harnesses")
    after_inputs = _declared(list(inputs), "inputs")
    for before, after, label in ((before_harnesses, after_harnesses, "harness"), (before_inputs, after_inputs, "input")):
        for old, new in zip(before, after):
            new["sha256_after"] = new["sha256"]
            new["sha256"] = old["sha256"]
        _require(len(before) == len(after), f"{label} declaration changed during execution")
    tool_hash_after = _sha(tool_path)
    rows, parse_error = _read_checks(stdout)
    if out.total > len(stdout):
        parse_error = f"stdout log truncated at {MAX_LOG_BYTES} bytes"
        rows = []
    logs = []
    for stream, data, drain in (("stdout", stdout, out), ("stderr", stderr, err)):
        captured = _capture_bytes(run_dir, data, f"execution-{stream}", revision)
        logs.append({**_public_capture(captured), "stream": stream, "total_bytes": drain.total,
                     "truncated": drain.total > len(data), "reader_error": drain.error,
                     "reader_complete": not drain.thread.is_alive()})
    tool = {"path": str(tool_path), "sha256": tool_hash, "sha256_after": tool_hash_after}
    execution_issue = _execution_issue(tool, after_harnesses, after_inputs, logs)
    counts, assertions, controls, eligible, reason = _derived(rows, timed_out, exit_code, parse_error, execution_issue)
    receipt = {
        "schema_version": 1,
        "artifact_kind": "execution",
        "subject": subject,
        "revision": revision,
        "command": invocation,
        "requested_command": list(command),
        "authorization": authorization.strip(),
        "cwd": str(workdir),
        "started_at": started,
        "finished_at": finished,
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "tool": tool,
        "harnesses": after_harnesses,
        "inputs": after_inputs,
        "logs": logs,
        "checks": rows,
        "parse_error": parse_error,
        "execution_issue": execution_issue,
        "run_counts": counts,
        "assertions": assertions,
        "negative_controls": controls,
        "eligible": eligible,
        "reason": reason,
        "limits": ["Local receipt only; not an OS sandbox or proof of process ancestry/remote authenticity.",
                   "Semantic scope and oracle independence still require review.",
                   "On Windows, timeout kills the direct process; descendants are not guaranteed to stop."],
    }
    receipt_bytes = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    evidence_capture = _capture_bytes(run_dir, receipt_bytes, subject, revision)
    return {"artifact_kind": "execution", **evidence_capture}


def _load_captured(root, item):
    _require(isinstance(item, dict) and isinstance(item.get("path"), str), "capture reference needs path")
    _require(isinstance(item.get("sha256"), str) and SHA256.fullmatch(item["sha256"]), "capture reference needs a lowercase SHA-256")
    _require(type(item.get("bytes")) is int and item["bytes"] >= 0, "capture reference needs a nonnegative byte count")
    _require(item["path"] == f"artifacts/{item['sha256']}.bin", "capture path is not content-addressed")
    path = aa.contained(root, item["path"])
    data = path.read_bytes()
    _require(hashlib.sha256(data).hexdigest() == item.get("sha256"), f"captured bytes hash mismatch: {item['path']}")
    _require(len(data) == item.get("bytes"), f"captured bytes length mismatch: {item['path']}")
    return data


def verify_evidence(evidence, root, live=True):
    """Verify captured bytes and recompute every claim derived from stdout."""
    _require(isinstance(evidence, dict) and evidence.get("artifact_kind") == "execution", "evidence must be an execution artifact")
    raw_receipt = _load_captured(root, evidence)
    try:
        receipt = json.loads(raw_receipt.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Invalid(f"captured execution receipt is malformed: {error}") from error
    fields = {"schema_version", "artifact_kind", "subject", "revision", "command", "requested_command", "authorization", "cwd",
              "started_at", "finished_at", "timeout_seconds", "timed_out", "exit_code", "tool", "harnesses",
              "inputs", "logs", "checks", "parse_error", "execution_issue", "run_counts", "assertions",
              "negative_controls", "eligible", "reason", "limits"}
    _require(isinstance(receipt, dict) and set(receipt) == fields and type(receipt.get("schema_version")) is int and receipt["schema_version"] == 1 and receipt.get("artifact_kind") == "execution", "unsupported or malformed execution receipt")
    _require(isinstance(receipt.get("subject"), str) and receipt["subject"].strip() and isinstance(receipt.get("revision"), str) and receipt["revision"].strip(), "receipt needs subject and revision")
    _require(evidence.get("subject") == receipt["subject"] and evidence.get("revision") == receipt["revision"], "outer evidence subject/revision differ from receipt")
    _require(evidence.get("path") == f"artifacts/{evidence.get('sha256')}.bin" and evidence.get("path") == f"artifacts/{hashlib.sha256(raw_receipt).hexdigest()}.bin", "execution receipt path is not content-addressed")
    expected_id = "e" + hashlib.sha256(aa.canonical([receipt["subject"], receipt["revision"], evidence["sha256"]])).hexdigest()[:20]
    _require(evidence.get("id") == expected_id, "execution evidence ID does not bind subject, revision and receipt bytes")
    _require(isinstance(receipt.get("command"), list) and receipt["command"] and all(isinstance(x, str) and x for x in receipt["command"]), "receipt command must be nonempty argument strings")
    _require(isinstance(receipt.get("requested_command"), list) and receipt["requested_command"] and all(isinstance(x, str) and x for x in receipt["requested_command"]), "receipt requested command must be nonempty argument strings")
    _require(isinstance(receipt.get("authorization"), str) and receipt["authorization"].strip(), "receipt authorization is required")
    _require(_absolute_path(receipt.get("cwd")), "receipt cwd must be a normalized absolute path")
    _require(isinstance(receipt.get("started_at"), str) and isinstance(receipt.get("finished_at"), str), "receipt needs start and finish timestamps")
    try:
        started_at = datetime.fromisoformat(receipt["started_at"])
        finished_at = datetime.fromisoformat(receipt["finished_at"])
    except ValueError as error:
        raise Invalid("receipt timestamps must be ISO-8601") from error
    _require(started_at.tzinfo is not None and finished_at.tzinfo is not None and finished_at >= started_at, "receipt timestamps must be ordered and timezone-aware")
    _require(type(receipt.get("timeout_seconds")) is int and 1 <= receipt["timeout_seconds"] <= MAX_TIMEOUT, "receipt timeout_seconds is invalid")
    _require(type(receipt.get("timed_out")) is bool and type(receipt.get("exit_code")) is int, "receipt timeout and exit code types are invalid")
    _require(receipt.get("parse_error") is None or isinstance(receipt.get("parse_error"), str), "parse_error must be text or null")
    _require(receipt.get("execution_issue") is None or isinstance(receipt.get("execution_issue"), str), "execution_issue must be text or null")
    _require(isinstance(receipt.get("limits"), list) and all(isinstance(x, str) and x.strip() for x in receipt["limits"]), "receipt limits must be nonempty text rows")
    _require(isinstance(receipt.get("logs"), list) and len(receipt["logs"]) == 2 and all(isinstance(x, dict) for x in receipt["logs"]) and {x.get("stream") for x in receipt["logs"]} == {"stdout", "stderr"}, "receipt needs exactly one stdout and one stderr log")
    log_data = {}
    for log in receipt["logs"]:
        log_fields = {"id", "path", "sha256", "bytes", "stream", "total_bytes", "truncated", "reader_error", "reader_complete"}
        _require(isinstance(log, dict) and set(log) == log_fields and log.get("stream") in {"stdout", "stderr"}, "malformed execution log entry")
        _require(type(log.get("total_bytes")) is int and log["total_bytes"] >= log.get("bytes", 0), "invalid log byte counts")
        _require(type(log.get("truncated")) is bool and type(log.get("reader_complete")) is bool, "log state fields must be booleans")
        _require(log.get("reader_error") is None or isinstance(log.get("reader_error"), str), "invalid log reader error")
        data = _load_captured(root, log)
        expected_log_id = "e" + hashlib.sha256(aa.canonical([f"execution-{log['stream']}", receipt["revision"], log["sha256"]])).hexdigest()[:20]
        _require(log.get("id") == expected_log_id, "log capture identity mismatch")
        _require(log["truncated"] is (log["total_bytes"] > len(data)), "log truncation flag mismatch")
        log_data[log["stream"]] = data
    checks, parse_error = _read_checks(log_data["stdout"])
    if any(x.get("stream") == "stdout" and x.get("truncated") for x in receipt["logs"]):
        checks, parse_error = [], "stdout log truncated"
    if receipt.get("parse_error"):
        # Runner-side bounded-output conditions are part of the record; ordinary parser errors recompute exactly.
        if receipt["parse_error"] == "stdout log truncated" or receipt["parse_error"].startswith("stdout log truncated"):
            checks, parse_error = [], receipt["parse_error"]
    _require(receipt.get("checks") == checks and receipt.get("parse_error") == parse_error, "stored checks or parse error differ from raw stdout")
    counts, assertions, controls, eligible, reason = _derived(checks, receipt["timed_out"], receipt["exit_code"], parse_error, receipt.get("execution_issue"))
    _require(receipt.get("run_counts") == counts and receipt.get("assertions") == assertions and receipt.get("negative_controls") == controls, "stored totals differ from raw check rows")
    _require(receipt.get("eligible") is eligible and receipt.get("reason") == reason, "stored eligibility differs from execution results")
    tool = receipt.get("tool")
    _require(isinstance(tool, dict) and set(tool) == {"path", "sha256", "sha256_after"} and _absolute_path(tool.get("path")) and isinstance(tool.get("sha256"), str) and SHA256.fullmatch(tool["sha256"]) and isinstance(tool.get("sha256_after"), str) and SHA256.fullmatch(tool["sha256_after"]), "receipt tool identity is invalid")
    _require(receipt["command"][0] == tool["path"] and receipt["command"][1:] == receipt["requested_command"][1:], "resolved command does not match tool identity and requested arguments")
    for label in ("harnesses", "inputs"):
        files = receipt.get(label)
        _require(isinstance(files, list), f"receipt {label} must be a list")
        for row in files:
            _require(isinstance(row, dict) and set(row) == {"path", "sha256", "sha256_after"} and _absolute_path(row.get("path")) and isinstance(row.get("sha256"), str) and SHA256.fullmatch(row["sha256"]) and isinstance(row.get("sha256_after"), str) and SHA256.fullmatch(row["sha256_after"]), f"invalid {label} hash record")
            if live:
                _require(_live_hash(row["path"], label) == row["sha256_after"], f"live {label} changed since execution: {row['path']}")
    expected_issue = _execution_issue(tool, receipt["harnesses"], receipt["inputs"], receipt["logs"])
    _require(receipt.get("execution_issue") == expected_issue, "execution issue summary differs from recorded hashes and logs")
    if live:
        _require(_live_hash(tool["path"], "executable") == tool["sha256_after"], "live executable changed since execution")
        _require(tool["sha256"] == tool["sha256_after"], "executable changed during execution")
        for row in receipt["harnesses"] + receipt["inputs"]:
            _require(row["sha256"] == row["sha256_after"], f"declared file changed during execution: {row['path']}")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--harness", action="append", default=[])
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--env-key", action="append", default=[])
    parser.add_argument("--subject", default="fixture")
    parser.add_argument("--revision", default="owned")
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--" not in arguments:
        parser.error("the authorized command must follow --")
    separator = arguments.index("--")
    args = parser.parse_args(arguments[:separator])
    command = arguments[separator + 1:]
    try:
        evidence = execute(args.run_dir, command, args.cwd, [Path(x) for x in args.harness],
                           [Path(x) for x in args.input], args.authorization, args.timeout,
                           args.env_key, args.subject, args.revision)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0 if verify_evidence(evidence, args.run_dir)["eligible"] else 1
    except (Invalid, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
