# test-scg-7f6
import unittest

from export import to_csv


class PlainRowTests(unittest.TestCase):
    def test_values_are_joined_by_commas(self):
        self.assertEqual(to_csv([["a", "b", 3]]), "a,b,3")

    def test_rows_are_joined_by_crlf(self):
        self.assertEqual(to_csv([["a"], ["b"]]), "a\r\nb")

    def test_no_rows_give_empty_text(self):
        self.assertEqual(to_csv([]), "")


@unittest.skip("enable once finance confirms the CSV dialect")
class QuotingTests(unittest.TestCase):
    def test_a_field_with_a_comma_is_quoted(self):
        self.assertEqual(to_csv([["Smith, Jane", 5]]), '"Smith, Jane",5')

    def test_a_quote_inside_a_field_is_doubled(self):
        self.assertEqual(to_csv([['say "hi"']]), '"say ""hi"""')

    def test_a_plain_field_is_not_quoted(self):
        self.assertEqual(to_csv([["plain"]]), "plain")
