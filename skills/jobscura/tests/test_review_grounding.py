"""Review regressions for record attribution and independent authority checks."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
grounding = importlib.import_module('grounding')


class GroundingReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def flags(self, evidence, draft):
        source = self.root / 'evidence.txt'
        source.write_text(evidence, encoding='utf-8')
        target = self.root / 'draft.txt'
        target.write_text(draft, encoding='utf-8')
        return [f['kind'] for row in grounding.claims(target, [source])['ledger'] for f in row['flags']]

    def test_leadership_checked_alongside_implementation(self):
        flags = self.flags('Assisted the engineering manager with team planning.\n'
                           'Deployed Kubernetes clusters for the platform.',
                           'Managed a team of 12 engineers and deployed Kubernetes clusters.')
        self.assertTrue(set(flags) & {'authority_unconfirmed', 'authority_escalation', 'authority_unverified'})

    def test_implementation_evidence_does_not_prove_leadership(self):
        for source, draft in (
            ('Migrated CRM records for the sales team project.', 'Led the CRM migration project for the sales team.'),
            ('Configured Salesforce dashboards.', 'Managed Salesforce administration.'),
        ):
            with self.subTest(draft=draft):
                self.assertIn('authority_unconfirmed', self.flags(source, draft))

    def test_city_headers_and_bullets_are_records(self):
        for source, draft in (
            ('Acme Corp, Berlin, Germany\nSenior Data Analyst, 2019 - 2022',
             'Senior Data Analyst at Acme Corp from 2019 to 2022.'),
            ('Harvard University, Cambridge, MA\nMBA, 2015',
             'Earned an MBA from Harvard University in 2015.'),
            ('Acme Corp\nSenior Data Analyst\n2019-2022\n- Built Tableau dashboards for reporting.',
             'Built Tableau dashboards at Acme Corp.'),
            ('Senior Data Analyst | 2019-2022\nAcme Corp',
             'Senior Data Analyst at Acme Corp from 2019 to 2022.'),
        ):
            with self.subTest(source=source):
                self.assertNotIn('combination_unsupported', self.flags(source, draft))

    def test_bullets_do_not_attach_to_following_employer(self):
        source = ('Acme Corp\nSenior Data Analyst\n2019-2022\n'
                  '- Built Tableau dashboards for reporting\nGlobex Ltd\nIntern\n2018')
        self.assertIn('combination_unsupported', self.flags(source, 'Built Tableau dashboards at Globex Ltd.'))

    def test_title_first_records_do_not_cross(self):
        source = 'Senior Data Analyst | 2019-2022\nAcme Corp\nIntern | 2018\nGlobex Ltd'
        self.assertIn('combination_unsupported', self.flags(source, 'Intern, Acme Corp, 2018.'))

    def test_window_queries_reuse_precomputed_atoms(self):
        source = self.root / 'evidence.txt'
        source.write_text('Acme Corp\nSenior Data Analyst\n2019-2022', encoding='utf-8')
        index = grounding.Evidence([source])
        query = grounding.atoms('Senior Data Analyst at Acme Corp in 2019.')
        with patch.object(grounding, 'atoms', side_effect=AssertionError('query reparsed evidence')):
            self.assertTrue(index.paired(query))
            self.assertTrue(index.paired(query))

    def test_leadership_with_action_noun_supports_authorship(self):
        for verb, noun in (('Implemented', 'implementation'), ('Configured', 'configuration'),
                           ('Administered', 'administration'), ('Migrated', 'migration'),
                           ('Deployed', 'deployment'), ('Set up', 'setup')):
            with self.subTest(verb=verb):
                self.assertFalse(any(f.startswith('authority_') for f in self.flags(
                    'Led the Salesforce ' + noun + ' for the sales team.', verb + ' Salesforce.')))
        self.assertIn('authority_unconfirmed', self.flags(
            'Used Salesforce and led training for the implementation team.', 'Implemented Salesforce.'))

    def test_authorship_normalizes_whitespace(self):
        for source, draft in (('Set  up Salesforce.', 'Set up Salesforce.'),
                              ('Used Salesforce daily.', 'Set  up Salesforce.')):
            with self.subTest(source=source):
                flags = self.flags(source, draft)
                if source.startswith('Set'):
                    self.assertNotIn('authority_unconfirmed', flags)
                else:
                    self.assertIn('authority_unconfirmed', flags)


if __name__ == '__main__':
    unittest.main()
