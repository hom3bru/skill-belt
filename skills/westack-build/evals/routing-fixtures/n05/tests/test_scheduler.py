import unittest

from scheduler import Scheduler


class SchedulerTest(unittest.TestCase):
    def test_jobs_run_in_delay_order(self):
        scheduler = Scheduler()
        scheduler.run_after(0.02, "second")
        scheduler.run_after(0.01, "first")
        scheduler.wait()
        self.assertEqual(scheduler.results, ["first", "second"])
