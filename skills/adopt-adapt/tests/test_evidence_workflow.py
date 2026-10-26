"""R7: strong outcome claims, honest coverage and complete compact reports."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_aa import aa, fixture


def execution_module():
    spec = importlib.util.spec_from_file_location('execution_fixture_module', Path(aa.__file__).with_name('execution.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def attach_execution(run, record, claim, counts=None):
    """Run owned checks; their receipt supports only this synthetic fixture."""
    requested = counts or {'total': 3, 'skipped': 0, 'failed': 0}
    total = requested['total'] if type(requested.get('total')) is int and requested['total'] > 0 else 3
    skipped = requested['skipped'] if type(requested.get('skipped')) is int and 0 <= requested['skipped'] < total else 0
    work = run / 'owned-verification' / f'p{total}-s{skipped}'
    work.mkdir(parents=True, exist_ok=True)
    inputs = work / 'input.json'
    inputs.write_text('[0, 1, 2]\n', encoding='utf-8')
    script = work / 'check.py'
    script.write_text(
        'import json\nfrom pathlib import Path\n'
        'values = json.loads(Path("input.json").read_text())\n'
        'checks = []\n'
        f'for i in range({total}):\n'
        f'    skip = i < {skipped}\n'
        '    value = values[i % len(values)]\n'
        '    checks.append({"id": "p" + str(i), "kind": "positive", "status": "skip" if skip else ("pass" if int(str(value)) == value else "fail"), "detail": "Owned decimal roundtrip", **({"reason": "Explicit unit-fixture skip"} if skip else {})})\n'
        'checks.append({"id": "wrong-value", "kind": "negative-control", "status": "pass" if int("1") != 2 else "fail", "detail": "Planted wrong expected value is rejected"})\n'
        'print(json.dumps({"checks": checks}))\n', encoding='utf-8')
    execution = execution_module()
    evidence = execution.execute(run, [sys.executable, '-B', str(script)], work, [script], [inputs], 'Owned regression fixture authorized by this test', 10, [], subject='s1', revision=record['sources'][0]['revision'])
    evidence['read_scope'] = 'Captured owned run and deliberately wrong-value control; entire receipt reviewed'
    if not any(e['id'] == evidence['id'] for e in record['evidence']):
        record['evidence'].append(evidence)
    claim['execution'] = evidence['id']
    if 'evidence' in claim and evidence['id'] not in claim['evidence']:
        claim['evidence'].append(evidence['id'])
    if 'provenance' in claim:
        receipt = execution.verify_evidence(evidence, run)
        claim['provenance'] = {**claim['provenance'], 'tool': 'owned Python fixture', 'version': sys.version.split()[0], 'sha256': receipt['tool']['sha256']}
    return evidence


class EvidenceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run, self.record = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_source_prose_cannot_support_executed_outcome(self):
        claim = self.record['claims'][0]
        claim.update(kind='verified_outcome', text='Entire engine ran successfully', review='It did')
        self.assertIn('execution evidence', ' '.join(aa.validate(self.record, self.run)))

    def test_unexecuted_outcome_can_remain_a_research_unknown(self):
        self.record['claims'].append({'id': 'planned', 'subject': 's1', 'kind': 'verified_outcome', 'text': 'Runtime result remains unknown', 'status': 'unvalidated', 'scope': 'owned fixture', 'limitations': 'Not run', 'evidence': []})
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_owned_execution_satisfies_outcome_without_signature_service(self):
        claim = self.record['claims'][0]
        claim.update(kind='verified_outcome', text='Owned decimal checks rejected a wrong expected value', review='Read positive observations and the wrong-value control in the captured stdout')
        attach_execution(self.run, self.record, claim)
        self.assertEqual(aa.validate(self.record, self.run), [])

    def test_execution_cannot_be_borrowed_from_another_revision(self):
        claim = self.record['claims'][0]
        claim['kind'] = 'verified_outcome'
        evidence = attach_execution(self.run, self.record, claim)
        evidence['revision'] = 'another-version'
        self.assertIn('revision mismatch', ' '.join(aa.validate(self.record, self.run)))

    def test_declared_counts_cannot_replace_captured_execution(self):
        from test_re_methods import claim
        row = claim()
        self.record['items'][0]['ledger']['re_claims'] = [row]
        self.assertIn('execution evidence', ' '.join(aa.validate(self.record, self.run)))
        attach_execution(self.run, self.record, row)
        self.assertEqual(aa.validate(self.record, self.run), [])
        row['assertions'] = 123
        self.assertIn('captured', ' '.join(aa.validate(self.record, self.run)))

    def test_partial_subsystem_coverage_is_valid_and_visible(self):
        e = self.record['evidence'][0]['id']
        self.record['items'][0]['ledger']['coverage']['subsystems'] = [
            {'id': 'entry', 'scope': 'documented entry only', 'mapped': 'complete', 'inspected': 'partial', 'exercised': 'not-run', 'evidence': [e], 'execution': [], 'limitations': 'No runtime; other providers unknown'},
            {'id': 'providers', 'scope': 'provider implementations unavailable', 'mapped': 'unknown', 'inspected': 'unknown', 'exercised': 'not-run', 'evidence': [], 'execution': [], 'limitations': 'No provider source supplied'},
        ]
        self.assertEqual(aa.validate(self.record, self.run), [])
        output = aa.render(self.record, self.run)
        for term in ('Subsystem entry', 'inspected=partial', 'exercised=not-run', 'No provider source supplied'):
            self.assertIn(term, output)

    def test_passing_re_claim_cannot_cite_an_unread_receipt(self):
        from test_re_methods import claim
        row = claim()
        evidence = attach_execution(self.run, self.record, row)
        self.record['items'][0]['ledger']['re_claims'] = [row]
        evidence['read_scope'] = 'unread'
        self.assertIn('unread execution evidence', ' '.join(aa.validate(self.record, self.run)))

    def test_mapping_alone_cannot_be_recorded_as_exercised(self):
        self.record['items'][0]['ledger']['coverage']['subsystems'] = [{'id': 'entry', 'scope': 'selected entry', 'mapped': 'complete', 'inspected': 'complete', 'exercised': 'complete', 'evidence': [self.record['evidence'][0]['id']], 'execution': [], 'limitations': 'Selected path only'}]
        self.assertIn('execution evidence', ' '.join(aa.validate(self.record, self.run)))

    def test_shared_donor_rendered_once_and_both_target_reviews_retained(self):
        multi = self.root / 'multi'; multi.mkdir()
        run, record = fixture(multi, two_recipients=True)
        donor = 'UNIQUE_SHARED_DONOR_MAP'
        for item in record['items']:
            item['ledger']['map']['content'] = donor
        record['items'][1]['ledger']['gates']['policy'] = 'UNIQUE_SECOND_RECIPIENT_POLICY'
        output = aa.render(record, run)
        self.assertEqual(output.count(donor), 1)
        for item in record['items']:
            self.assertLess(output.index(donor), output.index('aa:verdict:' + item['id']))
            self.assertLess(output.index('aa:ledger:' + item['id']), output.index('aa:verdict:' + item['id']))
        self.assertLess(output.index('UNIQUE_SECOND_RECIPIENT_POLICY'), output.index('aa:verdict:q2'))
        self.assertIn('CONFLICT', output)
        self.assertTrue(aa.check_output(record, run, output))

    def test_different_coverage_is_not_lost_during_compaction(self):
        multi = self.root / 'multi'; multi.mkdir()
        run, record = fixture(multi, two_recipients=True)
        record['items'][1]['ledger']['coverage']['blind_spots'] = ['UNIQUE_UNREAD_SECOND_PATH']
        output = aa.render(record, run)
        self.assertIn('UNIQUE_UNREAD_SECOND_PATH', output)
        self.assertLess(output.index('UNIQUE_UNREAD_SECOND_PATH'), output.index('aa:verdict:q2'))

    def test_recipient_gate_resolution_remains_visible_before_verdict(self):
        item = self.record['items'][0]
        item['ledger']['gates']['flags'] = [{'code': 'SUPPLY-CHAIN-RISK', 'scope': 'mechanism', 'status': 'unresolved', 'resolution': 'UNIQUE_RECIPIENT_PREREQUISITE'}]
        self.assertEqual(aa.validate(self.record, self.run), [])
        output = aa.render(self.record, self.run)
        self.assertLess(output.index('UNIQUE_RECIPIENT_PREREQUISITE'), output.index('aa:verdict:q1'))
        self.assertIn('Paid policy: preserved', output)
        self.assertIn('Recipient wired: unknown', output)


if __name__ == '__main__':
    unittest.main()
