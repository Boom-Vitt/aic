import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/aic/scripts"))
from aiclib.safety import AICError, canonical_json, checked_root, relative_path, safe_path


class SafetyTests(unittest.TestCase):
    def test_traversal_and_sensitive_targets_are_rejected(self):
        for value in ("../outside", "/outside", "a/../../outside", "a\\..\\outside", ".env", "src/.env.prod", ".ssh/id_rsa", "credentials.json"):
            with self.subTest(value=value), self.assertRaises(AICError):
                relative_path(value)
        self.assertEqual(relative_path("src/app.py"), Path("src/app.py"))

    def test_symlink_cannot_escape_read_or_write_scope(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as raw:
            base = Path(raw)
            project = base / "project"
            outside = base / "outside"
            project.mkdir()
            outside.mkdir()
            (outside / "private.txt").write_text("outside", encoding="utf-8")
            (project / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(AICError):
                safe_path(project, "linked/private.txt", must_exist=True)
            with self.assertRaises(AICError):
                checked_root(project / "linked")
            self.assertEqual((outside / "private.txt").read_text(), "outside")

    def test_root_and_evidence_paths_are_contained(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as raw:
            root = checked_root(raw)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("print('sample')\n")
            self.assertEqual(safe_path(root, "src/app.py", must_exist=True), root / "src/app.py")
            with self.assertRaises(AICError):
                safe_path(root, "missing", must_exist=True)
            self.assertEqual(safe_path(root, ".", allow_dot=True), root)

    def test_digest_input_is_order_independent_json(self):
        first = canonical_json({"b": [2, 3], "a": 1})
        second = canonical_json({"a": 1, "b": [2, 3]})
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first), {"a": 1, "b": [2, 3]})


if __name__ == "__main__":
    unittest.main()
