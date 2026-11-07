"""Owned fixtures for the versioned coverage/measurement contract.

These test checker relationships and false blocks, not donor effectiveness.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys

from test_aa import aa, fixture


def experiment():
    return {
        "state": "proposed",
        "hypothesis": "Stable request identity can avoid duplicate effects after a timeout.",
        "baseline": "The current sender forwards the payload without an identity parameter.",
        "test": "Compare current and stable-identity senders under the same lost-acknowledgement schedule.",
        "criterion": "A repeated logical operation produces one effect if the receiver contract supports it.",
        "reopen": "A supported receiver contract and a discriminating comparison can change the verdict.",
    }


def basis(evidence, reason="proposal"):
    return {
        "reason": reason,
        "unit": "Stable-request-identity mechanism at the inspected sender seam",
        "baseline": "The inspected sender passes payload directly to the client.",
        "benefit": "Avoid duplicate effects after a timeout if receiver semantics permit it.",
        "added": "A small identity parameter and its lifecycle need inspection.",
        "removed": "Potential repeated effects; no runtime improvement has been measured.",
        "alternative": "Reuse the current sender and test the receiver contract first.",
        "evidence": list(evidence),
        "measurements": [],
    }


def v2_fixture(root, two_recipients=False):
    run, record = fixture(root, two_recipients=two_recipients)
    record["schema_version"] = 2
    intake_path = run / "intake.json"
    if intake_path.exists():
        intake = aa.load(intake_path)
    else:
        intake = {
            "schema_version": 1,
            "inputs_sha256": aa.digest(aa.canonical(aa.load(run / "inputs.json"))),
            "artifacts": [],
            "recording": {"state": "pending", "path": "run.json", "sha256": None, "index": None},
            "lineage": [],
        }
    donor_evidence = record["evidence"][0]["id"]
    node = {
        "id": "s1",
        "coverage": {"body": {"state": "read", "surface": "full-text", "evidence": [donor_evidence],
                                  "note": "The complete owned one-line method was read."}},
        "links": [],
        "named_works": [],
        "lookups": [],
        "attempts": [],
        "discovery": "closed",
        "background": {"status": "not-needed", "note": "This complete synthetic method and its relevant seams are supplied."},
        "retrieval": {"available_methods": [], "exhausted": False, "next_step": ""},
    }
    intake["artifacts"] = [node]
    intake["inputs_sha256"] = aa.digest(aa.canonical(aa.load(run / "inputs.json")))
    for item in record["items"]:
        decision = item["decision"]
        decision["basis"] = basis(item["ledger"]["doubt"]["evidence"])
        decision["experiment"] = experiment()
        item["ledger"]["measurements"] = []
        if decision["result"] == "DISCARD":
            decision.update(mechanism_value=1, promising_check="Compare the proposed method on the same failure schedule.")
            decision["basis"]["reason"] = "research-lead"
    aa.save(run / "run.json", record)
    aa.save(intake_path, intake)
    return run, record, intake


def replace_ref(value, old, new):
    if isinstance(value, dict):
        return {key: replace_ref(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_ref(item, old, new) for item in value]
    return new if value == old else value


def recapture_donor(run, record, intake, text, kind="social-post"):
    donor = run.parent / "donor.txt"
    donor.write_text(text, encoding="utf-8")
    source = record["sources"][0]
    source.update(kind=kind, revision=aa.digest(donor.read_bytes()))
    old = record["evidence"][0]["id"]
    new = aa.capture(run, donor, source["id"], source["revision"])
    new["read_scope"] = "Complete supplied fixture source"
    record["evidence"][0] = new
    record = replace_ref(record, old, new["id"])
    intake = replace_ref(intake, old, new["id"])
    return record, intake


def discard(record, reason="net-burden"):
    item = record["items"][0]
    decision = item["decision"]
    decision.update(result="DISCARD", whole_tool="DISCARD", mechanism_value=1,
                    summary="Current evidence must justify the proposed negative judgment.",
                    score=None, score_reason="Bounded mechanism assessment.")
    decision.pop("transfer", None)
    decision.pop("inventory", None)
    decision["basis"]["reason"] = reason
    return decision


def measured_counter(run, record):
    """Execute an owned arithmetic comparison with a bound JSON detail payload."""
    spec = importlib.util.spec_from_file_location("gate_owned_execution", Path(aa.__file__).with_name("execution.py"))
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
    work = run / "owned-counter"
    work.mkdir()
    payload = {
        "metric": "owned-counter-work",
        "unit": "fixture-units",
        "workload": "Three owned arithmetic counters",
        "denominator": "per fixture batch",
        "sample_size": 3,
        "baseline": {"value": 6, "revision": record["recipients"][0]["revision"]},
        "candidate": {"value": 3, "revision": record["sources"][0]["revision"]},
    }
    inputs = work / "comparison.json"
    inputs.write_text(json.dumps(payload), encoding="utf-8")
    harness = work / "counter.py"
    harness.write_text(
        'import json\nfrom pathlib import Path\n'
        'payload = json.loads(Path("comparison.json").read_text())\n'
        'baseline = sum([2, 2, 2])\ncandidate = sum([1, 1, 1])\n'
        'ok = payload["baseline"]["value"] == baseline and payload["candidate"]["value"] == candidate\n'
        'checks = [{"id":"comparison","kind":"positive","status":"pass" if ok else "fail","detail":json.dumps(payload)},'
        '{"id":"wrong-total","kind":"negative-control","status":"pass" if baseline != candidate else "fail","detail":"Different owned totals remain distinguishable"}]\n'
        'print(json.dumps({"checks":checks}))\n', encoding="utf-8")
    evidence = execution.execute(run, [sys.executable, "-B", str(harness)], work, [harness], [inputs],
                                 "Execute the owned gate regression counter fixture", 20, [],
                                 subject="s1", revision=record["sources"][0]["revision"])
    evidence["read_scope"] = "Entire owned arithmetic receipt and control reviewed"
    record["evidence"].append(evidence)
    row = {"id": "m1", "status": "measured", "scope": "Owned arithmetic fixture only; not donor effectiveness.",
           **copy.deepcopy(payload), "receipt": evidence["id"], "check": "comparison"}
    record["items"][0]["ledger"]["measurements"] = [row]
    return row, evidence
