"""Hidden aicbench oracle. AICBENCH_ORACLE grades this workspace without a model."""
import os
from pathlib import Path
import unittest

WORKSPACE = Path(os.environ["AICBENCH_WORKSPACE"])



from pages.cursor import decode_cursor, encode_cursor, page
from pages.window import window


class Oracle(unittest.TestCase):
    def test_cursor_pages(self):
        self.assertEqual(window([1, 2, 3, 4], 2, 2), [3, 4])
        self.assertEqual(decode_cursor(encode_cursor(0)), 0)
        self.assertEqual(decode_cursor(encode_cursor(2)), 2)
        with self.assertRaises(ValueError):
            decode_cursor("!!!")
        with self.assertRaises(ValueError):
            encode_cursor(-1)
        with self.assertRaises(TypeError):
            encode_cursor(True)
        items = [0, 1, 2, 3, 4]
        first = page(items, limit=2)
        self.assertEqual(first["items"], [0, 1])
        self.assertEqual(decode_cursor(first["next_cursor"]), 2)
        second = page(items, limit=2, cursor=first["next_cursor"])
        self.assertEqual(second["items"], [2, 3])
        self.assertEqual(decode_cursor(second["next_cursor"]), 4)
        third = page(items, limit=2, cursor=second["next_cursor"])
        self.assertEqual(third, {"items": [4], "next_cursor": None})
        self.assertEqual(items, [0, 1, 2, 3, 4])
        self.assertEqual(page(items, limit=2, cursor=encode_cursor(9)), {"items": [], "next_cursor": None})
        with self.assertRaises(ValueError):
            page(items, limit=0)
        with self.assertRaises(ValueError):
            page(items, limit=101)

    def test_added_unit_tests_pass(self):
        import subprocess
        import sys
        path = WORKSPACE / "tests" / "test_cursor.py"
        self.assertTrue(path.is_file(), "add tests/test_cursor.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn('next_cursor', text)
        self.assertIn("self.assert", text)
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "tests.test_cursor"],
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
