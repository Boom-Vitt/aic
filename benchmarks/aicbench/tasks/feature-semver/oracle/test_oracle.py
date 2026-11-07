"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from versions.label import display_label
from versions.semver import compare_versions, higher, parse_version


class Oracle(unittest.TestCase):
    def test_semver_contract(self):
        self.assertEqual(display_label("1.2.3"), "v1.2.3")
        self.assertEqual(parse_version("1.10.0"), (1, 10, 0))
        self.assertEqual(compare_versions("1.10.0", "1.9.0"), 1)
        self.assertEqual(compare_versions("1.0.0", "1.0.0"), 0)
        self.assertEqual(higher("1.10.0", "1.9.0"), "1.10.0")
        self.assertEqual(higher("1.0.0", "1.0.0"), "1.0.0")
        for text in ("01.2.3", "1.2", "v1.2.3", "1.2.3-rc"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_version(text)

    def test_added_unit_tests_pass(self):
        import subprocess
        import sys
        path = WORKSPACE / "tests" / "test_semver.py"
        self.assertTrue(path.is_file(), "add tests/test_semver.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('1.10.0', text)
        self.assertIn("self.assert", text)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "tests.test_semver"],
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
