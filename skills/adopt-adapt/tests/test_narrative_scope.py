"""R8: record completion and recipient evidence must match the stated scope."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from test_aa import aa, fixture


class NarrativeScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_initialized_record_reports_inputs_only(self):
        run = self.root / 'queued'
        record = aa.init_run(run, ['owned source'], ['target'])
        result = aa.record_status(record, run)
        self.assertEqual(result['scope'], 'inputs-only')
        self.assertEqual(result['ready_pairs'], 0)
        self.assertEqual(result['pairs'][0]['state'], 'QUEUED')
        self.assertFalse(result['semantic_truth_certified'])

    def test_ready_record_status_does_not_certify_narrative_truth(self):
        run, record = fixture(self.root)
        result = aa.record_status(record, run)
        self.assertEqual(result['scope'], 'ready-records')
        self.assertEqual(result['ready_pairs'], 1)
        self.assertFalse(result['semantic_truth_certified'])

    def test_wrong_recipient_cannot_supply_doubt_evidence(self):
        run, record = fixture(self.root, two_recipients=True)
        foreign = next(e['id'] for e in record['evidence'] if e['subject'] == 'target2')
        record['items'][0]['ledger']['doubt']['evidence'].append(foreign)
        self.assertIn('another recipient', ' '.join(aa.validate(record, run)))

    def test_overlap_claims_must_describe_this_recipient(self):
        run, record = fixture(self.root, two_recipients=True)
        record['items'][0]['ledger']['coverage']['overlap_claims'] = ['c3']
        self.assertIn('overlap claim', ' '.join(aa.validate(record, run)))

    def test_own_recipient_evidence_remains_usable(self):
        run, record = fixture(self.root, two_recipients=True)
        self.assertEqual(aa.validate(record, run), [])
        result = aa.record_status(record, run)
        self.assertEqual(result['ready_pairs'], 2)

    def test_status_cli_does_not_upgrade_initialized_inputs(self):
        run = self.root / 'queued-cli'
        aa.init_run(run, ['owned source'], ['target'])
        result = subprocess.run([sys.executable, '-B', aa.__file__, 'status', str(run / 'run.json')], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual(status['scope'], 'inputs-only')
        self.assertEqual(status['pairs'][0]['state'], 'QUEUED')

    def test_saved_blocked_state_is_not_labeled_input_only(self):
        run = self.root / 'blocked'
        record = aa.init_run(run, ['owned source'], ['target'])
        record['items'][0].update(state='BLOCKED', transitions=['QUEUED', 'RESEARCHING', 'BLOCKED'], reason='Required source file unavailable')
        status = aa.record_status(record, run)
        self.assertEqual(status['scope'], 'incomplete-records')
        self.assertEqual(status['pairs'][0]['state'], 'BLOCKED')
        self.assertEqual(status['ready_pairs'], 0)

    def test_partial_batch_reports_ready_and_blocked_states_separately(self):
        run, record = fixture(self.root, two_recipients=True)
        record['items'][1].update(state='BLOCKED', transitions=['QUEUED', 'RESEARCHING', 'READY', 'RESEARCHING', 'BLOCKED'], reason='New required evidence unavailable')
        record['items'][1].pop('decision')
        status = aa.record_status(record, run)
        self.assertEqual(status['scope'], 'mixed-records')
        self.assertEqual(status['ready_pairs'], 1)
        self.assertEqual([p['state'] for p in status['pairs']], ['READY', 'BLOCKED'])


if __name__ == '__main__':
    unittest.main()
