import unittest

from sync import Sync


class SyncTest(unittest.TestCase):
    def test_changes_are_applied_in_order(self):
        sync = Sync()
        threads = [sync.push_async(n) for n in range(20)]
        for thread in threads:
            thread.join()
        self.assertEqual(sync.applied, list(range(20)))
