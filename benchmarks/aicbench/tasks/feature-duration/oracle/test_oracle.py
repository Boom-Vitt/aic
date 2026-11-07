"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from timekit.duration import parse_duration
from timekit.stamp import format_hhmmss


class Oracle(unittest.TestCase):
    def test_duration_contract(self):
        self.assertEqual(format_hhmmss(3661), "01:01:01")
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("1h30m15s"), 5415)
        self.assertEqual(parse_duration("90s"), 90)
        self.assertEqual(parse_duration("1h"), 3600)
        self.assertEqual(parse_duration("1m"), 60)
        self.assertEqual(parse_duration("0s"), 0)
        for text in ("01h", "1h1h", "1s1h", "", "1", "1h "):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_added_unit_tests_pass(self):
        import subprocess
        import sys
        path = WORKSPACE / "tests" / "test_duration.py"
        self.assertTrue(path.is_file(), "add tests/test_duration.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('1h30m', text)
        self.assertIn("self.assert", text)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "tests.test_duration"],
            cwd=WORKSPACE,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main(argv=["test_oracle"])
