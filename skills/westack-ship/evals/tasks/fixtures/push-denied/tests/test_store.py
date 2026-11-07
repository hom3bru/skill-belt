# notes-test-2b9
import unittest

from notes.store import Store


class StoreTests(unittest.TestCase):
    def test_notes_keep_their_order(self):
        store = Store()
        store.add("b")
        store.add("a")
        self.assertEqual([t for t, _ in store.notes], ["b", "a"])

    def test_search_finds_a_word_in_the_title(self):
        store = Store()
        store.add("Shopping list")
        store.add("Trip plan")
        self.assertEqual(store.search("LIST"), ["Shopping list"])


if __name__ == "__main__":
    unittest.main()
