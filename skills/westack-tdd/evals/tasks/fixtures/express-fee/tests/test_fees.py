# tdd-fixture: existing tests (house style)
import unittest

from shipping.fees import RATE_PER_KG, base_fee, shipping_fee


class FeeTests(unittest.TestCase):
    def test_base_fee_scales_with_weight(self):
        self.assertEqual(base_fee(4), round(4 * RATE_PER_KG, 2))

    def test_standard_shipping_is_the_base_fee(self):
        self.assertEqual(shipping_fee(4), base_fee(4))


if __name__ == "__main__":
    unittest.main()
