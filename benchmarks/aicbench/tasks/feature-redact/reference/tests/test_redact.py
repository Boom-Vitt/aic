import unittest

from logs.redact import redact


class RedactTests(unittest.TestCase):
    def test_longer_secret_wins(self):
        self.assertEqual(redact("abcdef", ["abc", "abcdef"]), "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
