# test-store-8c1
import unittest

from app import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        store.USERS.clear()
        store.INVOICES.clear()
        store.create_user(1, "Ana Ruiz", "ana@example.com", "1 Main St")

    def test_an_invoice_copies_the_name_and_address_as_issued(self):
        store.add_invoice(1, 4200)
        self.assertEqual(store.invoices_for(1)[0]["address"], "1 Main St")

    def test_a_user_without_invoices_has_none(self):
        self.assertEqual(store.invoices_for(1), [])


if __name__ == "__main__":
    unittest.main()
