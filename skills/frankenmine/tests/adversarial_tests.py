"""Regression probes for demonstrated record and archive boundary failures.

All filesystem mutations stay in the caller's disposable results directory.
Only this package's authored helper and packager are executed.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import frankenmine as fm


PACKAGE = Path(__file__).resolve().parents[1]


def run_tests(test, fixture, runroot, scratch):
    """Register tests with the existing runner's immediate callback."""
    probe_root = scratch / "adversarial"
    probe_root.mkdir()

    def blocked(mutate, expected):
        record = copy.deepcopy(fixture)
        mutate(record)
        errors = fm.check(record, runroot)
        assert any(expected in item for item in errors), (expected, errors)
        return errors

    mutations = [
        ("rights evidence must identify the selected donor",
         lambda r: r["candidates"][0]["rights"].update(evidence=["ev-math"]),
         "rights lack matching donor"),
        ("discovery must identify the selected donor",
         lambda r: r["candidates"][0].update(discovery=["math-target-led"]),
         "matching donor discovery"),
        ("source language cannot bypass the semantic bridge",
         lambda r: r["candidates"][1].update(source_language="Python", deltas=[]),
         "source language not declared"),
        ("selected target language must match the product brief",
         lambda r: r["brief"].update(target_language="Java"),
         "target language disagrees"),
        ("selected component must record its retained closure",
         lambda r: r["candidates"][0].update(closure=[]),
         "selected closure"),
        ("negative-control detection cannot substitute for product acceptance",
         lambda r: r["candidates"][0].update(acceptance="control-math"),
         "acceptance must test"),
        ("unresolved design blocker prevents readiness",
         lambda r: r.update(unresolved=["Selected checkpoint recovery corrupts the ledger"]),
         "unresolved items remain"),
    ]
    for name, mutate, expected in mutations:
        test(name, lambda m=mutate, e=expected: blocked(m, e))

    raw_failure = runroot / "adversarial-failure.txt"
    raw_failure.write_text("Authored regression probe: one required case failed.\n", encoding="utf-8")

    def fail_test(record, ident):
        target = next(item for item in record["tests"] if item["id"] == ident)
        target["status"] = "fail"
        record["receipts"].append(dict(
            id="receipt-adversarial-" + ident, test=ident,
            command="authored regression probe; deliberately failed case",
            environment="disposable synthetic validator test", raw_output=raw_failure.name,
            raw_sha256=fm.digest(raw_failure.read_bytes()), exit_code=1,
            cases=1, passed=0, failed=1, skipped=0, control_detected=False))

    def failed_required(kind):
        record = copy.deepcopy(fixture)
        if kind == "acceptance":
            ident = record["candidates"][0]["acceptance"]
        elif kind == "control":
            ident = record["candidates"][0]["negative_control"]
        else:
            # An extra product oracle isolates the semantic/interaction gate
            # from the candidates' already-required acceptance tests.
            ident = "adversarial-" + kind + "-oracle"
            extra = copy.deepcopy(record["tests"][0])
            extra.update(id=ident, status="not-run")
            record["tests"].append(extra)
            if kind == "delta":
                delta = next(item for item in record["candidates"][1]["deltas"]
                             if item["status"] != "not-applicable")
                delta["test"] = ident
            else:
                record["interactions"][0]["test"] = ident
        fail_test(record, ident)
        errors = fm.check(record, runroot)
        assert any(kind in item and "required test is fail" in item for item in errors), errors
        assert not any("receipt" in item for item in errors), errors
        return errors

    for kind in ("acceptance", "control", "delta", "interaction"):
        test("failed required " + kind + " oracle blocks design readiness",
             lambda k=kind: failed_required(k))

    for status in ("skipped", "blocked"):
        test("required acceptance cannot be " + status + " at readiness",
             lambda s=status: blocked(lambda r: r["tests"][0].update(status=s),
                                      "required test is " + s))

    def unselected_runtime(record):
        record["mode"] = "implementation"
        record["decision"].update(choice="minimal-fresh")
        record["interactions"] = []
        for item in record["candidates"]:
            item.update(phase="deferred", route="defer")
        record["candidates"][0]["implementation"] = "tested"

    test("unselected candidates cannot claim tested behavior without passing evidence",
         lambda: blocked(unselected_runtime, "runtime promotion without passed"))

    def unselected_test_purpose():
        record = copy.deepcopy(fixture)
        unselected_runtime(record)
        candidate = record["candidates"][0]
        candidate["acceptance"] = "control-math"
        raw = runroot / "adversarial-control-receipt.txt"
        raw.write_text("Synthetic validator input: control detected in one case.\n", encoding="utf-8")
        for ident in (candidate["acceptance"], candidate["negative_control"]):
            target = next(item for item in record["tests"] if item["id"] == ident)
            target["status"] = "pass"
            # These are explicitly synthetic receipt fields used to challenge
            # consistency rules; they are not actual product observations.
            record["receipts"].append(dict(
                id="receipt-adversarial-passed-" + ident, test=ident,
                command="synthetic validator positive-control fields",
                environment="authored fixture, not product execution",
                raw_output=raw.name, raw_sha256=fm.digest(raw.read_bytes()),
                exit_code=0, cases=1, passed=1, failed=0, skipped=0, control_detected=True))
        errors = fm.check(record, runroot)
        assert any("acceptance must test" in item for item in errors), errors
        assert not any("runtime promotion" in item or "receipt" in item for item in errors), errors
        return errors

    test("unselected tested candidates still need a real acceptance-test purpose",
         unselected_test_purpose)

    def language_case():
        record = copy.deepcopy(fixture)
        record["brief"]["target_language"] = "PYTHON"
        record["candidates"][0].update(source_language="python", target_language="PyThOn")
        record["candidates"][1].update(source_language="JAVASCRIPT", target_language="python")
        errors = fm.check(record, runroot)
        assert not errors, errors
        return "Case differences preserve declared languages and genuine bridge requirements"

    test("language labels are compared without case sensitivity", language_case)

    def observed_author_claim():
        record = copy.deepcopy(fixture)
        record["evidence"][0]["kind"] = "observed"
        record["evidence"][0]["limitations"] = "Author-supplied observation; bytes do not authenticate its observer"
        errors = fm.check(record, runroot)
        assert not errors, errors
        dossier = fm.report(record, errors)
        assert "not semantic proof" in dossier
        assert '"kind": "observed"' in dossier
        return "Observed claim retained as author data with the report's structural-proof limitation"

    test("author observation claims do not imply helper authentication", observed_author_claim)

    def alternative_variants():
        record = copy.deepcopy(fixture)
        variant = copy.deepcopy(record["alternatives"][0])
        variant.update(name="Existing exact arithmetic with external replay ledger",
                       tradeoffs="Adds a storage boundary and operator burden; compare separately from the in-memory option")
        record["alternatives"].append(variant)
        errors = fm.check(record, runroot)
        assert not errors, errors
        return "Additional meaningful best-existing variant does not invalidate the three-way comparison"

    test("alternative categories can contain multiple meaningful variants", alternative_variants)

    def reject_optimized_runner():
        output = probe_root / "must-not-run-optimized"
        result = subprocess.run([sys.executable, "-O", str(PACKAGE / "tests/run_tests.py"),
                                 "--output", str(output)], capture_output=True, text=True, timeout=20)
        assert result.returncode != 0, result
        assert "require assertions" in result.stderr, result.stderr
        assert not output.exists(), "Optimized test process created a misleading results directory"
        return "Optimized Python rejected before producing output or test results"

    test("test runner refuses optimization that disables assertions", reject_optimized_runner)

    def bounded_reads():
        bounded = probe_root / "bounded.bin"
        bounded.write_bytes(b"x" * fm.LIMIT)
        assert len(fm.read_bounded(bounded)) == fm.LIMIT
        with bounded.open("ab") as stream:
            stream.write(b"x")
        try:
            fm.read_bounded(bounded)
        except ValueError as exc:
            assert "limit" in str(exc), exc
        else:
            raise AssertionError("oversize regular file was accepted")
        try:
            fm.read_bounded(probe_root)
        except ValueError as exc:
            assert "regular file" in str(exc), exc
        else:
            raise AssertionError("directory was accepted as evidence bytes")
        return "Exact limit accepted; limit+1 and nonregular input rejected"

    test("evidence reads enforce actual byte bounds and regular-file input", bounded_reads)

    def exponent_overflow():
        path = probe_root / "numbers.json"
        path.write_text('{"number":1e308}', encoding="utf-8")
        assert fm.load_json(path)["number"] == 1e308
        path.write_text('{"number":1e999}', encoding="utf-8")
        try:
            fm.load_json(path)
        except ValueError as exc:
            assert "nonfinite" in str(exc), exc
            return "Finite exponent accepted; overflow rejected before record validation"
        raise AssertionError("overflowing JSON exponent became an infinite float")

    test("JSON exponent overflow cannot introduce nonfinite evidence", exponent_overflow)

    def inert_report():
        record = copy.deepcopy(fixture)
        payload = '[click](https://example.invalid/attack)\n# forged\n<script>alert(1)</script>\n``````\n'
        record["id"] = payload
        record["brief"]["outcome"] = payload
        record["donors"][0]["reason"] = payload
        record["decision"]["rationale"] = payload
        text = fm.report(record, [payload])
        preamble, full = text.split("## Full portable record\n\n", 1)
        assert "<script>" not in preamble
        assert "[click](https://" not in preamble
        assert "\n# forged\n" not in preamble
        lines = full.splitlines()
        opening = lines[0]
        assert opening.endswith("json"), opening
        fence = opening[:-4]
        assert re.fullmatch(r"`{7,}", fence), fence
        assert lines[-1] == fence, lines[-1]
        restored = json.loads("\n".join(lines[1:-1]))
        assert restored == record, "Escaping changed the portable record"
        (probe_root / "inert-report.md").write_text(text, encoding="utf-8")
        return "Summary is inert text; longer code fence preserves the exact JSON record"

    test("donor Markdown and embedded fences remain inert in reports", inert_report)

    copied_package = probe_root / "package-copy"
    package_command = [sys.executable, str(copied_package / "scripts/package.py")]

    def package_cli(*args):
        result = subprocess.run(package_command + list(map(str, args)),
                                capture_output=True, text=True, timeout=30)
        return result, json.loads(result.stdout or result.stderr)

    def ensure_package_copy():
        if not copied_package.exists():
            shutil.copytree(PACKAGE, copied_package,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def archive_integrity_exclusive():
        ensure_package_copy()
        archive_path = probe_root / "authored-package.skill"
        result, info = package_cli("--output", archive_path)
        assert result.returncode == 0 and info["status"] == "pass", (result, info)
        original = archive_path.read_bytes()
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
            manifest = json.loads(archive.read("frankenmine/MANIFEST.json"))
            expected = {"frankenmine/MANIFEST.json"}
            for row in manifest["files"]:
                name = "frankenmine/" + row["path"]
                expected.add(name)
                data = archive.read(name)
                assert len(data) == row["bytes"], name
                assert hashlib.sha256(data).hexdigest() == row["sha256"], name
            assert expected == set(archive.namelist())
        result, info = package_cli("--output", archive_path)
        assert result.returncode != 0 and info["status"] == "fail", (result, info)
        assert archive_path.read_bytes() == original, "Existing archive was changed"
        return "CRC and manifest verified; repeat output creation rejected without replacement"

    test("archive integrity and exclusive output preserve existing delivery", archive_integrity_exclusive)

    def nested_archive():
        ensure_package_copy()
        output = copied_package / "must-not-exist.skill"
        result, info = package_cli("--output", output)
        assert result.returncode != 0 and info["status"] == "fail", (result, info)
        assert any("outside the package root" in item for item in info["errors"]), info
        assert not output.exists(), "Nested archive was created before rejection"
        return "Archive destination inside the package root rejected before creation"

    test("archive output cannot contaminate its own package input", nested_archive)

    def reject_directory_link():
        ensure_package_copy()
        outside = probe_root / "outside-package"
        outside.mkdir()
        sentinel = outside / "private-sentinel.txt"
        sentinel.write_text("Authored sibling sentinel; must never enter a delivery\n", encoding="utf-8")
        link = copied_package / "external-link"
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
            kind = "native Windows junction"
        else:
            link.symlink_to(outside, target_is_directory=True)
            kind = "directory symlink"
        output = probe_root / "must-not-leak.skill"
        result, info = package_cli("--output", output)
        assert result.returncode != 0 and info["status"] == "fail", (result, info)
        assert any("Link/reparse" in item for item in info["errors"]), info
        assert not output.exists(), "Archive was created despite linked external source"
        assert sentinel.read_text(encoding="utf-8").startswith("Authored sibling sentinel")
        # Preserve the disposable link for inspection; never recursively delete
        # an unverified Windows link tree as part of a regression test.
        return kind + " rejected before an external file can be archived"

    test("package collection rejects external directory links before traversal", reject_directory_link)
