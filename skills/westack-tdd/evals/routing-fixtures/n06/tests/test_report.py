import unittest

from report import total_by_team


class TotalByTeamTest(unittest.TestCase):
    def test_missing_team_and_hours_do_not_crash(self):
        rows = [{"team": None, "hours": 3}, {"team": "a", "hours": None}]
        self.assertEqual(total_by_team(rows), {"unassigned": 3, "a": 0})
