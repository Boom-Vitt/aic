import unittest

from versions.semver import higher


class SemverTests(unittest.TestCase):
    def test_numeric_minor_order(self):
        self.assertEqual(higher("1.10.0", "1.9.0"), "1.10.0")


if __name__ == "__main__":
    unittest.main()
