import unittest

from greet.messages import goodbye_message, payment_message


class MessageTests(unittest.TestCase):
    def test_payment_message(self):
        self.assertEqual(payment_message(3), "Payment recieved: 3 items")

    def test_goodbye_message(self):
        self.assertEqual(goodbye_message("Ana"), "Thanks, Ana. See you soon.")


if __name__ == "__main__":
    unittest.main()
