"""Authored handoff contracts; fixture tests do not measure model effectiveness."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_aa import aa, fixture, SCRIPT


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_initialized_run_preserves_queue_and_exact_reason(self):
        run = self.root / 'queued'
        record = aa.init_run(run, ['https://example.test/source'], ['reviewer'])
        index = aa.handoff(record, run)
        pair = index['pairs'][0]
        self.assertEqual(index['scope'], 'inputs-only')
        self.assertEqual((pair['id'], pair['source']['id'], pair['recipient']['id'], pair['state']), ('q1', 's1', 'reviewer', 'QUEUED'))
        self.assertEqual(pair['unresolved'], [{'kind': 'reason', 'text': 'Not yet researched', 'reference': {'path': 'run.json', 'pointer': '/items/0/reason'}}])
        self.assertEqual(pair['next_step']['basis'], {'path': 'run.json', 'pointer': '/items/0/reason'})
        self.assertIsNone(pair['ledger_reference'])
        self.assertFalse(pair['recipient']['live_checked'])
        self.assertFalse(index['semantic_truth_certified'])

    def test_ready_proposal_keeps_prerequisite_and_unimplemented_limit(self):
        run, record = fixture(self.root)
        index = aa.handoff(record, run)
        pair = index['pairs'][0]
        self.assertEqual(pair['state'], 'READY')
        self.assertEqual(pair['ledger_reference'], {'path': 'run.json', 'pointer': '/items/0/ledger'})
        self.assertEqual(pair['next_step']['text'], record['items'][0]['decision']['next_step'])
        self.assertEqual(pair['next_step']['authorization'], 'not-assessed')
        self.assertIn(record['items'][0]['decision']['transfer']['prerequisite'], [issue['text'] for issue in pair['unresolved']])
        self.assertIn('Server contract', [issue['text'] for issue in pair['unresolved']])
        self.assertFalse(index['implementation_verified'])
        self.assertIn('proposal', index['limitations'])
        self.assertEqual(index['resources'], 'unavailable; not recorded by this schema')

    def test_interrupted_second_recipient_keeps_exact_owner_and_pending_evidence(self):
        run, record = fixture(self.root, two_recipients=True)
        pair = record['items'][1]
        pair.update(state='BLOCKED', transitions=['QUEUED', 'RESEARCHING', 'READY', 'RESEARCHING', 'BLOCKED'], reason='Reviewer must inspect target2 retry flag; source appendix not read')
        pair.pop('decision')
        source = run / 'pending.txt'
        source.write_text('Source appendix awaiting inspection', encoding='utf-8')
        pending = aa.capture(run, source, 's1', record['sources'][0]['revision'])
        record['evidence'].append(pending)
        record['claims'].append({'id': 'pending', 'subject': 'target2', 'text': 'Unconfirmed reviewer interpretation', 'kind': 'recipient_opportunity', 'status': 'unvalidated', 'scope': 'retry flag', 'limitations': 'Reviewer inspection pending', 'evidence': [], 'level': 'claimed'})
        index = aa.handoff(record, run)
        target, blocked = index['pairs']
        self.assertEqual(index['scope'], 'mixed-records')
        self.assertEqual(blocked['recipient']['reference'], {'path': 'run.json', 'pointer': '/recipients/1'})
        self.assertEqual(blocked['source']['reference'], {'path': 'run.json', 'pointer': '/sources/0'})
        self.assertEqual(blocked['unresolved'][0]['text'], pair['reason'])
        self.assertEqual(blocked['next_step']['basis']['pointer'], '/items/1/reason')
        self.assertEqual(next(e for e in blocked['evidence'] if e['id'] == pending['id'])['read_scope'], 'unread')
        self.assertEqual(next(c for c in blocked['claims'] if c['id'] == 'pending')['status'], 'unvalidated')
        self.assertNotIn('pending', [c['id'] for c in target['claims']])
        self.assertNotIn('target', [e['subject'] for e in blocked['evidence']])

    def test_unprocessed_cancelled_and_inconclusive_are_not_promoted(self):
        for state, transitions in [('UNPROCESSED', ['QUEUED', 'UNPROCESSED']), ('CANCELLED', ['QUEUED', 'CANCELLED'])]:
            with self.subTest(state=state):
                run = self.root / state
                record = aa.init_run(run, ['source'], ['target'])
                record['items'][0].update(state=state, transitions=transitions, reason='Operator decision pending')
                self.assertEqual(aa.handoff(record, run)['pairs'][0]['state'], state)
        run, record = fixture(self.root)
        record['items'][0]['decision'].update(result='INCONCLUSIVE', whole_tool='INCONCLUSIVE', confidence_level='low')  # INCONCLUSIVE is low confidence
        self.assertEqual(aa.handoff(record, run)['pairs'][0]['state'], 'READY')
        self.assertFalse(aa.handoff(record, run)['implementation_verified'])

    def test_stale_snapshot_rejected_and_historical_replay_labels_limit(self):
        run, record = fixture(self.root)
        (self.root / 'recipient' / 'entry.py').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(aa.Invalid, 'snapshot is stale'):
            aa.handoff(record, run)
        index = aa.handoff(record, run, live=False)
        self.assertEqual(index['freshness'], 'historical replay; present applicability not checked')
        self.assertFalse(index['pairs'][0]['recipient']['live_checked'])

    def test_stale_receipt_bytes_and_unsupported_decisive_claim_rejected(self):
        run, record = fixture(self.root)
        bad = copy.deepcopy(record)
        bad['claims'][0]['status'] = 'unvalidated'
        bad['claims'][0]['level'] = 'claimed'  # an unvalidated claim stays CLAIMED (r16 fourth pass)
        with self.assertRaisesRegex(aa.Invalid, 'unsupported/stale'):
            aa.handoff(bad, run)
        (run / record['evidence'][0]['path']).write_bytes(b'changed capture')
        with self.assertRaisesRegex(aa.Invalid, 'byte/hash mismatch'):
            aa.handoff(record, run)

    def test_disconnected_mapping_and_borrowed_recipient_evidence_fail(self):
        run, record = fixture(self.root, two_recipients=True)
        swapped = copy.deepcopy(record)
        swapped['items'][0]['recipient'], swapped['items'][1]['recipient'] = 'target2', 'target'
        with self.assertRaisesRegex(aa.Invalid, 'queue manifest changed'):
            aa.handoff(swapped, run)
        record['items'][1]['ledger']['coverage']['overlap_claims'] = ['c2']
        with self.assertRaisesRegex(aa.Invalid, 'another recipient'):
            aa.handoff(record, run)

    def test_malformed_record_fails_with_actionable_error(self):
        for value in [None, {}, {'items': None}]:
            with self.subTest(value=value), self.assertRaises(aa.Invalid):
                aa.handoff(value, self.root)

    def test_irrelevant_optional_transfer_does_not_crash_nontransfer_recovery(self):
        run, record = fixture(self.root, two_recipients=True)
        # Existing schema does not require a transfer for DISCARD. Ignore unused
        # non-object optional data rather than treating it as a prerequisite.
        record['items'][1]['decision']['transfer'] = None
        self.assertEqual(aa.validate(record, run), [])
        index = aa.handoff(record, run)
        self.assertFalse(any(issue['kind'] == 'prerequisite' for issue in index['pairs'][1]['unresolved']))

    def test_local_references_cannot_escape_run_or_inject_links(self):
        run, record = fixture(self.root)
        with self.assertRaises(aa.Invalid):
            aa.handoff(record, run, record_name='../outside.json')
        record['evidence'][0]['path'] = '../outside.bin'
        with self.assertRaisesRegex(aa.Invalid, 'inside its root'):
            aa.handoff(record, run)

    def test_projection_is_deterministic_read_only_and_report_unchanged(self):
        run, record = fixture(self.root)
        before_record = copy.deepcopy(record)
        before_files = {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob('*') if p.is_file()}
        report = aa.render(record, run)
        first = aa.handoff(record, run)
        self.assertEqual(first, aa.handoff(record, run))
        self.assertEqual(record, before_record)
        self.assertEqual(before_files, {p.relative_to(run).as_posix(): p.read_bytes() for p in run.rglob('*') if p.is_file()})
        self.assertEqual(aa.render(record, run), report)
        self.assertEqual(first['record_sha256'], aa.digest(aa.canonical(record)))
        for row in first['pairs'][0]['evidence']:
            self.assertTrue((run / row['path']).is_file())

    def test_cli_stdout_and_opt_in_local_file_preserve_record(self):
        run = self.root / 'cli'
        record = aa.init_run(run, ['source'], ['target'])
        command = [sys.executable, '-B', str(SCRIPT), 'handoff', str(run / 'run.json')]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), aa.handoff(record, run))
        result = subprocess.run([*command, '--output', 'handoff.json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        retained = (run / 'handoff.json').read_bytes()
        self.assertEqual(json.loads(retained), aa.handoff(record, run))
        repeat = subprocess.run([*command, '--output', 'handoff.json'], capture_output=True, text=True)
        self.assertNotEqual(repeat.returncode, 0)
        self.assertEqual((run / 'handoff.json').read_bytes(), retained)
        escape = subprocess.run([*command, '--output', '../outside.json'], capture_output=True, text=True)
        self.assertNotEqual(escape.returncode, 0)
        self.assertFalse((self.root / 'outside.json').exists())


if __name__ == '__main__':
    unittest.main()
