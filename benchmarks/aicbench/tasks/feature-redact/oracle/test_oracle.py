"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from logs.format import format_event
from logs.redact import redact


class Oracle(unittest.TestCase):
    def test_redaction_contract(self):
        self.assertEqual(format_event("login", "ok"), "login: ok")
        self.assertEqual(redact("abcdef", ["abc", "abcdef"]), "[REDACTED]")
        self.assertEqual(redact("a abc a", ["abc"]), "a [REDACTED] a")
        self.assertEqual(redact("ABC", ["abc"]), "ABC")
        self.assertEqual(redact("x", [""]), "x")
        self.assertEqual(redact("", ["x"]), "")
        with self.assertRaises(TypeError):
            redact("x", [1])

    def test_added_unit_tests_pass(self):
        import subprocess
        import sys
        path = WORKSPACE / "tests" / "test_redact.py"
        self.assertTrue(path.is_file(), "add tests/test_redact.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('[REDACTED]', text)
        self.assertIn("self.assert", text)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "tests.test_redact"],
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
