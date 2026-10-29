"""Frozen authored continuation recovery cases; no donor or network execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import traceback

from fixture_builder import make_run, fm, PACKAGE


def run_tests(test, scratch):
    root = scratch / "handoff"
    run = make_run(root)

    def view(record, manifest=None):
        from synthesis_handoff import build_index
        return build_index(record, root / "run.json", fm.check(record, root), manifest)

    def task_a():
        record = copy.deepcopy(run)
        for ident, status in (("queued", "queued"), ("later", "deferred")):
            record["donors"].append(dict(record["donors"][0], id=ident, status=status,
                                          reason="Reopen after persistence requirement"))
        before = fm.encode(record)
        result = view(record)
        assert result == view(record) and fm.encode(record) == before
        assert [x["id"] for x in result["donors"]] == ["game", "math", "queued", "later"]
        assert result["donors"][-1]["reason"] == "Reopen after persistence requirement"
        c = result["contracts"][0]
        assert (c["design"], c["implementation"]) == ("selected", "not-started")
        # The pair's integration test is declared but not run: declared, never verified.
        assert c["integration"]["status"] == "declared" and c["integration"]["test"] == "integrate-game-math"
        assert c["owners"][0]["source"]["pointer"] == "/ownership/0"
        assert c["source"]["pointer"] == "/candidates/0" and c["donor"]["id"] == "game"
        assert result["benefit"] == "not-established-by-helper"
        assert any(x["kind"] == "review" for x in result["pending"])
        return "Exact IDs, deferral, source/owner locators; selection is not implementation"

    def implemented():
        record = copy.deepcopy(run)
        record["mode"] = "implementation"
        record["candidates"][0]["implementation"] = "implemented"
        record["ownership"].append(dict(record["ownership"][0], owner="OtherOwner"))
        record["interactions"][0]["status"] = "conflict"
        control = record["tests"][1]
        control["status"] = "fail"
        raw = root / "failed-control.txt"
        raw.write_text("Disconnected control not detected\n", encoding="utf-8")
        record["receipts"] = [dict(id="receipt-control", test=control["id"], command="authored observation",
            environment="synthetic", raw_output=raw.name, raw_sha256=fm.digest(raw.read_bytes()),
            exit_code=1, cases=1, passed=0, failed=1, skipped=0, control_detected=False)]
        # A passing unrelated baseline cannot supply the missing integration receipt.
        record["tests"].append(dict(record["tests"][0], id="package-like", purpose="baseline", status="pass"))
        record["receipts"].append(dict(record["receipts"][0], id="package-receipt", test="package-like",
            exit_code=0, passed=1, failed=0))
        return record

    def task_b():
        result = view(implemented())
        c = result["contracts"][0]
        assert c["implementation"] == "implemented" and c["verification"] == "unverified"
        # A passing unrelated baseline does not verify integration; the declared pair test is still not run.
        assert c["integration"]["status"] == "declared"
        assert c["tests"][1]["status"] == "fail"
        assert c["tests"][1]["receipts"][0]["raw"]["path"].endswith("failed-control.txt")
        assert result["next"]["kind"] == "ownership"
        assert {x["owner"] for x in result["next"]["owners"]} == {"ReplayTotal", "OtherOwner"}
        assert any(x["kind"] == "interaction" and x["source"]["pointer"] == "/interactions/0"
                   for x in result["pending"])
        return "Implemented artifact, failed control, missing integration and both ownership claims recovered"

    def stale():
        record = implemented()
        (root / "failed-control.txt").write_text("changed after receipt\n", encoding="utf-8")
        result = view(record)
        receipt = result["contracts"][0]["tests"][1]["receipts"][0]
        assert receipt["integrity"] == "invalid" and any("hash mismatch" in x for x in receipt["errors"])
        assert result["status"] == "blocked" and result["temporal_freshness"] == "unknown-no-timestamps"
        return "Changed bytes blocked; temporal freshness never invented"

    def disconnected():
        record = copy.deepcopy(run)
        record["mode"] = "implementation"
        record["candidates"][0]["implementation"] = "tested"
        product = root / "product.py"
        product.write_text("# authored stand-in product file\n", encoding="utf-8")
        artifact = dict(path=product.name, sha256=fm.digest(product.read_bytes()))
        record["artifacts"] = [dict(artifact, origin="authored", candidates=["component-game"])]
        for t in record["tests"]:
            t["status"] = "pass"
            raw = root / (t["id"] + ".txt")
            raw.write_text("Authored receipt-integrity fixture only; no product observation\n" + t["id"] + "\n",
                           encoding="utf-8")
            record["receipts"].append(dict(id="receipt-" + t["id"], test=t["id"], command="authored fixture",
                environment="synthetic", raw_output=raw.name, raw_sha256=fm.digest(raw.read_bytes()),
                exit_code=0, cases=1, passed=1, failed=0, skipped=0,
                control_detected=t["purpose"] == "negative-control", artifacts=[dict(artifact)]))
        assert view(record)["contracts"][0]["verification"] == "recorded-checks-pass"
        broken = copy.deepcopy(record)
        broken["receipts"][0]["test"] = "accept-math"
        assert view(broken)["contracts"][0]["verification"] == "unverified"
        assert view(broken)["status"] == "blocked"
        broken = copy.deepcopy(record)
        broken["candidates"][0]["donor"] = "math"
        assert view(broken)["contracts"][0]["verification"] == "unverified"
        record["candidates"][0]["acceptance"] = "accept-math"
        c = view(record)["contracts"][0]
        assert c["tests"][0]["id"] == "accept-math"
        assert c["tests"][0]["shared_by"] == ["component-game", "component-math"]
        # Shared acceptance is legal in the existing schema: disclose sharing rather
        # than inventing a per-donor semantic ownership contract the record lacks.
        assert c["tests"][0]["receipts"][0]["id"] == "receipt-accept-math"
        manifest = root / "decisions.json"
        manifest.write_text(fm.encode({"decisions": [
            {"id": "game", "source_url": "https://wrong.invalid"},
            {"id": "orphan", "source_url": "https://orphan.invalid"}]}), encoding="utf-8")
        result = view(record, manifest)
        assert [x["join"] for x in result["decisions"]] == ["source-mismatch", "missing-donor", "run-only"]
        assert result["status"] == "blocked"
        assert result["decisions"][1]["id"] == "orphan"
        return "Disconnected manifest and shared/mismatched acceptance do not manufacture per-donor proof"

    def missing_receipt():
        record = implemented()
        record["receipts"][0]["raw_output"] = "absent.txt"
        assert view(record)["contracts"][0]["tests"][1]["receipts"][0]["integrity"] == "invalid"
        record = copy.deepcopy(run)
        record["candidates"][0]["acceptance"] = "absent-test"
        assert view(record)["contracts"][0]["tests"][0]["status"] == "missing"
        return "Missing evidence and references remain unavailable"

    def cli_cases():
        source, output = root / "incomplete.json", root / "index.json"
        source.write_text(fm.encode(fm.skeleton()), encoding="utf-8")
        original = source.read_bytes()
        command = [sys.executable, str(PACKAGE / "scripts/frankenmine.py"), "handoff", str(source), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        assert result.returncode == 2 and output.exists(), (result.stdout, result.stderr)
        index = fm.load_json(output)
        assert index["status"] == "blocked" and index["next"]
        assert source.read_bytes() == original
        assert subprocess.run(command, capture_output=True, timeout=20).returncode == 2
        assert fm.load_json(output) == index
        for number, value in enumerate(({}, dict(run, donors=[run["donors"][0]] * 2))):
            source.write_text(fm.encode(value), encoding="utf-8")
            target = root / ("invalid-" + str(number) + ".json")
            command[-1] = str(target)
            assert subprocess.run(command, capture_output=True, timeout=20).returncode == 2
            assert not target.exists()
        return "Incomplete view useful; malformed/ambiguous records and output replacement refused"

    for name, fn in (("handoff interrupted selection", task_a), ("handoff interrupted implementation", task_b),
                     ("handoff stale receipt", stale), ("handoff disconnected joins", disconnected),
                     ("handoff missing evidence", missing_receipt), ("handoff CLI boundaries", cli_cases)):
        test(name, fn)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("Tests require assertions; remove -O/PYTHONOPTIMIZE")
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    def test(name, fn):
        try:
            results.append(dict(name=name, status="pass", detail=fn()))
        except Exception:
            results.append(dict(name=name, status="fail", raw=traceback.format_exc()))
    run_tests(test, args.output)
    (args.output / "results.json").write_text(fm.encode(results), encoding="utf-8")
    print(fm.encode(results))
    raise SystemExit(any(x["status"] == "fail" for x in results))
