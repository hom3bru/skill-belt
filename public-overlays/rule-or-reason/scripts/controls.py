"""Save deliberately broken copies and their failing-test receipts in a research folder.

Usage: python -B scripts/controls.py ABSOLUTE_OUTPUT_DIR
Never edits this package. Existing output directories are refused.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import demo
import study


def run(output):
    root = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    allowed = Path.cwd().resolve()
    if not output.is_relative_to(allowed) or output.is_relative_to(root) or output.exists():
        raise SystemExit("Use a new directory within the current working directory and outside the skill package")
    output.mkdir(parents=True)
    results = []
    _, _, _, _, _, source, plan = demo.fixture()
    # Five deliberately broken operation-map copies, each checked by the CLI.
    for name, check in (("human-gate", "human_gate"), ("retry-cap", "retry_cap"),
                        ("required-input", "required_input"), ("witness-owner", "witness_owner"),
                        ("unmapped", "unmapped_obligation")):
        broken = copy.deepcopy(plan)
        if name == "human-gate": broken["operations"][0]["kind"] = "rule"
        if name == "retry-cap": broken["operations"][1]["max_retries"] = None
        if name == "required-input": broken["operations"][1]["requires"].append("missing-variable")
        if name == "witness-owner": broken["operations"][1]["witness_entity"] = "wrong-entity"
        if name == "unmapped": broken["operations"].pop(0)
        path = output / (name + ".json")
        path.write_text(json.dumps({"source": source, "plan": broken}, indent=2), encoding="utf-8")
        command = [sys.executable, "-B", str(root / "scripts/study.py"), "obligations", "--request", str(path)]
        p = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        result = json.loads(p.stdout)
        detected = p.returncode == 0 and not result["passed"] and check in {x["check"] for x in result["issues"]}
        (output / (name + "-receipt.json")).write_text(json.dumps({"command": command, "returncode": p.returncode,
                                                                 "result": result, "detected": detected}, indent=2))
        results.append({"control": name, "detected": detected})

    mutants = [
        ("skip-obligations", "scripts/study.py", '"passed": not issues', '"passed": True',
         "test_study.StudyTests.test_obligations_block_supported_verdict"),
        ("accept-conflict", "scripts/study.py", 'if row.get("conflict") is True:', 'if False:',
         "test_study.StudyTests.test_conflicts_missing_state_and_bad_evidence_fail_closed"),
        ("lose-fallback-cost", "scripts/study.py", 'b = 0 if accepted else left.get(key, {}).get(metric)', 'b = 0',
         "test_study.StudyTests.test_full_flow_accounting_and_ordinary_hybrid"),
        ("leak-holdout", "scripts/study.py", 'threshold, "development", policy["label_sources"]', 'threshold, None, policy["label_sources"]',
         "test_study.StudyTests.test_sweep_uses_only_development"),
        ("allow-self-labels", "scripts/study.py", 'return source in allowed and source != "teacher" and independent is True and case.get("label_arm_id") not in arm_ids', 'return True',
         "test_study.StudyTests.test_provenance_excludes_self_labels"),
        ("allow-nonblind", "scripts/study.py", 'answers["blind"] is True and answers["key_disclosed"] is False', 'True',
         "test_study.StudyTests.test_nonblind_adjudication_rejected"),
        ("allow-packet-tamper", "scripts/study.py", 'packet.get("key_commitment") == digest(secret) and key.get("packet_sha256") == digest(packet)', 'True',
         "test_study.StudyTests.test_adjudication_tampering_and_incompleteness"),
        ("omit-agreement-sample", "scripts/study.py", 'rng.sample(same, agreements)', '[]',
         "test_study.StudyTests.test_blinded_disagreements_and_seeded_agreements"),
        ("ignore-shared-errors", "scripts/study.py", 'agreement_errors += int(', 'agreement_errors += 0 * int(',
         "test_study.StudyTests.test_shared_error_estimated_from_agreements"),
        ("ignore-policy-seal", "scripts/study.py", 'require(digest(expected) == digest(seal),', 'require(True,',
         "test_study.StudyTests.test_threshold_policy_and_artifact_seals"),
        ("omit-case-content-seal", "scripts/study.py", '"case_content_sha256": digest(case_set)', '"case_content_sha256": "unchecked"',
         "test_study.StudyTests.test_changed_case_content_cannot_reuse_seal"),
        ("wilson-zero-width", "scripts/study.py", 'half = z * math.sqrt(', 'half = 0 * z * math.sqrt(',
         "test_study.StudyTests.test_wilson_published_example"),
        ("newcombe-uninformative", "scripts/study.py", 'return [max(-1., p - q - lower), min(1., p - q + upper)]', 'return [-1., 1.]',
         "test_study.StudyTests.test_newcombe_published_paired_example"),
        ("mcnemar-always-one", "scripts/study.py", 'return min(1., 2 * math.exp(peak) * math.fsum(math.exp(x - peak) for x in logs))', 'return 1.',
         "test_study.StudyTests.test_exact_mcnemar_and_extremes"),
        ("lose-negative-correlation", "scripts/study.py", 'rho = adjusted / denominator if denominator else 0.', 'rho = max(0., adjusted / denominator) if denominator else 0.',
         "test_study.StudyTests.test_newcombe_original_table_negative_correlation_and_boundaries"),
        ("ignore-quality-cap", "scripts/study.py", 'if passed:', 'if True:',
         "test_study.StudyTests.test_utility_and_negation_controls"),
        ("all-five-convert", "assets/discovery/ledger.json", '"recommendation":"exclude disabled path"', '"recommendation":"test selective rule"',
         "test_templates.TemplateTests.test_discovery_distinguishes_five_paths"),
        ("invent-missing-state-savings", "assets/discovery/ledger.json", '"recommendation":"insufficient evidence","savings":null', '"recommendation":"insufficient evidence","savings":10',
         "test_templates.TemplateTests.test_discovery_distinguishes_five_paths"),
        ("stale-policy-asset", "assets/lifetime.json", '"policy":"policy-v1", "interpreter"', '"interpreter"',
         "test_templates.TemplateTests.test_lifetime_closure_invalidates_only_dependent_assets"),
        ("stale-interpreter-asset", "assets/lifetime.json", ', "interpreter":"python-example-v1"}', '}',
         "test_templates.TemplateTests.test_lifetime_closure_invalidates_only_dependent_assets"),
        ("stale-source-asset", "assets/lifetime.json", '"source":"source-v1", "serializer":"json-v1"}', '"serializer":"json-v1"}',
         "test_templates.TemplateTests.test_lifetime_closure_invalidates_only_dependent_assets"),
        ("clamp-loss-to-zero", "assets/lifetime.json", '"net":-30', '"net":0',
         "test_templates.TemplateTests.test_economics_allows_loss_and_unknowns"),
        ("complete-partial-effect", "assets/lifetime.json", '"status":"partial"', '"status":"complete"',
         "test_templates.TemplateTests.test_partial_effect_not_replayed_or_completed"),
    ]
    for name, relative, old, new, test in mutants:
        destination = output / name
        shutil.copytree(root, destination, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        path = destination / relative
        before = path.read_text(encoding="utf-8")
        if old not in before:
            raise RuntimeError("mutation anchor missing: " + name)
        after = before.replace(old, new, 1)
        path.write_text(after, encoding="utf-8")
        command = [sys.executable, "-B", "-m", "unittest", test]
        p = subprocess.run(command, cwd=destination / "tests", capture_output=True, text=True, encoding="utf-8")
        text = p.stdout + p.stderr
        # An assertion must fail, not just a syntax/import/runtime error.
        detected = p.returncode != 0 and "FAIL:" in text
        (destination / "test-receipt.txt").write_text(text, encoding="utf-8")
        receipt = {"control": name, "path": relative, "test": test, "command": command,
                   "returncode": p.returncode, "detected": detected,
                   "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
                   "after_sha256": hashlib.sha256(after.encode()).hexdigest()}
        (destination / "mutation-receipt.json").write_text(json.dumps(receipt, indent=2))
        results.append(receipt)
        print(name, "DETECTED" if detected else "NOT DETECTED", flush=True)
    (output / "summary.json").write_text(json.dumps(results, indent=2))
    if not all(r["detected"] for r in results):
        raise SystemExit("undetected control; inspect saved receipts")
    print(f"Detected {len(results)}/{len(results)} broken-copy controls")


if __name__ == "__main__":
    run(sys.argv[1])
