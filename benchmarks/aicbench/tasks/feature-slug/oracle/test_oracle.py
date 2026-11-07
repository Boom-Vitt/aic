"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from textkit.case import title_case
from textkit.slug import slugify


class Oracle(unittest.TestCase):
    def test_slug_contract(self):
        self.assertEqual(title_case("hello world"), "Hello World")
        self.assertEqual(slugify("Hello, World!"), "hello-world")
        self.assertEqual(slugify("Äpfel & Birnen"), "äpfel-birnen")
        self.assertEqual(slugify("A--B"), "a-b")
        self.assertEqual(slugify("Version 2"), "version-2")
        with self.assertRaises(ValueError):
            slugify("---")
        with self.assertRaises(TypeError):
            slugify(None)

    def test_added_unit_tests_pass(self):
        import subprocess
        import sys
        path = WORKSPACE / "tests" / "test_slug.py"
        self.assertTrue(path.is_file(), "add tests/test_slug.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('hello-world', text)
        self.assertIn("self.assert", text)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "tests.test_slug"],
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
