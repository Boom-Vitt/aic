import unittest

from textkit.slug import slugify


class SlugTests(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_collapses_repeated_separators(self):
        self.assertEqual(slugify("A--B"), "a-b")


if __name__ == "__main__":
    unittest.main()
