import unittest
from unittest import mock

from retry import call_with_retry


class RetryTest(unittest.TestCase):
    def test_func_is_called(self):
        func = mock.Mock(side_effect=[ConnectionError(), "ok"])
        call_with_retry(func, delay=0)
        func.assert_called()
