import unittest

from services.payments.charge import charge
from services.payments.fakes import FakeProvider


class ChargeTests(unittest.TestCase):
    def test_a_charge_reaches_the_provider(self):
        provider = FakeProvider()
        self.assertEqual(charge(provider, "tok_1", 500)["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
