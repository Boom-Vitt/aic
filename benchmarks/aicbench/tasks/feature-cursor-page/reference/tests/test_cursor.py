import unittest

from pages.cursor import page


class CursorTests(unittest.TestCase):
    def test_first_page_sets_next_cursor(self):
        result = page([0, 1, 2, 3, 4], limit=2)
        self.assertEqual(result["items"], [0, 1])
        self.assertIsNotNone(result["next_cursor"])


if __name__ == "__main__":
    unittest.main()
