import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/aic/scripts"))
from aiclib.inspection import inspect_project
from aiclib.safety import AICError


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()

    def write_file(self, name, content="sample\n"):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_inventory_is_deterministic_metadata_and_filename_signals_only(self):
        self.write_file("src/app.py", "PRIVATE_SOURCE_MARKER\n")
        self.write_file("tests/test_app.py", "PRIVATE_TEST_MARKER\n")
        self.write_file("package.json", '{"scripts":{"postinstall":"DO_NOT_EXECUTE"}}')
        self.write_file("pyproject.toml", "[project]\nname = 'sample'\n")
        first = inspect_project(self.project)
        second = inspect_project(self.project)
        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(first["project"], str(self.project))
        self.assertEqual([entry["path"] for entry in first["files"]], ["package.json", "pyproject.toml", "src/app.py", "tests/test_app.py"])
        for entry in first["files"]:
            self.assertEqual(set(entry), {"path", "size_bytes"})
            self.assertEqual(entry["size_bytes"], (self.project / entry["path"]).stat().st_size)
        self.assertIn("Python", first["stacks"])
        self.assertIn("JavaScript/TypeScript", first["stacks"])
        self.assertIn({"path": "pyproject.toml", "stack": "Python"}, first["manifests"])
        self.assertIn("tests/test_app.py", first["test_signals"])
        self.assertFalse(first["truncated"])
        self.assertEqual(first["truncation_reasons"], [])
        encoded = json.dumps(first)
        for marker in ("PRIVATE_SOURCE_MARKER", "PRIVATE_TEST_MARKER", "DO_NOT_EXECUTE"):
            self.assertNotIn(marker, encoded)

    def test_inspection_does_not_open_contents_write_or_start_processes(self):
        self.write_file("setup.py", "raise RuntimeError('MANIFEST_MUST_NOT_RUN')\n")
        self.write_file("src/app.py", "SOURCE_CONTENT_MUST_NOT_BE_READ\n")
        before = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*"))
        with patch("builtins.open", side_effect=AssertionError("Content access is forbidden.")), patch.object(Path, "open", side_effect=AssertionError("Content access is forbidden.")), patch("os.open", side_effect=AssertionError("No descriptor may be opened.")), patch("subprocess.Popen", side_effect=AssertionError("No process is permitted.")), patch("subprocess.run", side_effect=AssertionError("No command is permitted.")), patch.object(Path, "mkdir", side_effect=AssertionError("No directory may be created.")):
            result = inspect_project(self.project)
        self.assertEqual(before, sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*")))
        self.assertEqual([entry["path"] for entry in result["files"]], ["setup.py", "src/app.py"])
        self.assertIn("Python", result["stacks"])

    def test_sensitive_hidden_dependency_and_build_trees_are_not_disclosed(self):
        excluded = (
            ".env", ".env.production", "src/.env.local", "credentials.json", "private.key", "cert.pem",
            ".git/config", ".ssh/id_rsa", ".aws/config", ".aic/memory/note.json", ".work/private.txt",
            "node_modules/pkg/index.js", ".venv/lib/package.py", "dist/app.js", "build/output.py",
            "target/release/app", "vendor/pkg/source.rb", "coverage/report.json", ".cache/data.txt",
        )
        for name in excluded:
            self.write_file(name, "SENSITIVE_CONTENT_MARKER")
        self.write_file("src/public.py", "public\n")
        result = inspect_project(self.project)
        self.assertEqual([entry["path"] for entry in result["files"]], ["src/public.py"])
        self.assertFalse(result["truncated"])
        encoded = json.dumps(result)
        self.assertNotIn("SENSITIVE_CONTENT_MARKER", encoded)
        for name in excluded:
            self.assertNotIn(name, [entry["path"] for entry in result["files"]])

    def test_external_internal_broken_and_directory_symlinks_are_skipped(self):
        outside = self.base / "outside"
        outside.mkdir()
        external = outside / "external-private.py"
        external.write_text("EXTERNAL_FILE_CONTENT_MUST_STAY_PRIVATE", encoding="utf-8")
        self.write_file("src/public.py", "public\n")
        (self.project / "external-file.py").symlink_to(external)
        (self.project / "external-tree").symlink_to(outside, target_is_directory=True)
        (self.project / "alias.py").symlink_to(self.project / "src/public.py")
        (self.project / "broken.py").symlink_to(outside / "missing.py")
        (self.project / "loop").symlink_to(self.project, target_is_directory=True)
        result = inspect_project(self.project)
        self.assertEqual([entry["path"] for entry in result["files"]], ["src/public.py"])
        self.assertNotIn("external-private.py", json.dumps(result))
        self.assertNotIn("EXTERNAL_FILE_CONTENT_MUST_STAY_PRIVATE", json.dumps(result))
        self.assertEqual(external.read_text(encoding="utf-8"), "EXTERNAL_FILE_CONTENT_MUST_STAY_PRIVATE")
        root_alias = self.base / "alias-project"
        root_alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(AICError):
            inspect_project(root_alias)

    def test_file_limit_reports_actual_truncation_and_stable_selection(self):
        for name in ("c.py", "a.py", "b.py"):
            self.write_file(name)
        result = inspect_project(self.project, max_files=2)
        with os.scandir(self.project) as entries:
            expected = sorted(next(entries).name for _ in range(2))
        self.assertEqual([entry["path"] for entry in result["files"]], expected)
        self.assertTrue(result["truncated"])
        self.assertIn("max_files", result["truncation_reasons"])
        self.assertEqual(result, inspect_project(self.project, max_files=2))
        exact = inspect_project(self.project, max_files=3)
        self.assertEqual(len(exact["files"]), 3)
        self.assertFalse(exact["truncated"])

    def test_depth_limit_keeps_root_files_and_reports_pruned_subtrees(self):
        self.write_file("root.py")
        self.write_file("src/app.py")
        self.write_file("src/nested/module.py")
        shallow = inspect_project(self.project, max_depth=0)
        self.assertEqual([entry["path"] for entry in shallow["files"]], ["root.py"])
        self.assertTrue(shallow["truncated"])
        self.assertIn("max_depth", shallow["truncation_reasons"])
        middle = inspect_project(self.project, max_depth=1)
        self.assertEqual([entry["path"] for entry in middle["files"]], ["root.py", "src/app.py"])
        complete = inspect_project(self.project, max_depth=2)
        self.assertFalse(complete["truncated"])
        self.assertEqual(len(complete["files"]), 3)

    def test_many_empty_directories_cannot_bypass_the_scan_budget(self):
        for index in range(30):
            (self.project / f"directory-{index:02d}").mkdir()
        result = inspect_project(self.project, max_files=1)
        self.assertEqual(result["files"], [])
        self.assertTrue(result["truncated"])
        self.assertIn("max_directories", result["truncation_reasons"])
        self.assertLessEqual(result["inspected_directories"], result["limits"]["max_directories"])

    def test_wide_stream_consumption_and_metadata_are_globally_bounded(self):
        project = self.project
        for excluded in (False, True):
            with self.subTest(excluded=excluded):
                class CountingEntries:
                    consumed = 0
                    metadata_calls = 0
                    closed = False

                    def __enter__(self):
                        return self

                    def __exit__(self, *_args):
                        self.closed = True

                    def __iter__(self):
                        return self

                    def __next__(self):
                        if self.consumed >= 1000:
                            raise AssertionError("The inventory consumed an unbounded sibling stream.")
                        self.consumed += 1
                        prefix = ".env-private-" if excluded else "directory-"
                        name = f"{prefix}{self.consumed}"
                        return SimpleNamespace(
                            name=name, path=str(project / name), stat=self.metadata,
                            is_dir=lambda **_kwargs: True, is_symlink=lambda: False,
                        )

                    def metadata(self, *, follow_symlinks):
                        if follow_symlinks:
                            raise AssertionError("Symlinks must never be followed.")
                        self.metadata_calls += 1
                        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_size=0)

                entries = CountingEntries()
                with patch("aiclib.inspection.os.scandir", return_value=entries) as scan:
                    result = inspect_project(self.project, max_files=1, max_depth=0)
                self.assertEqual(entries.consumed, result["limits"]["max_entries"])
                self.assertEqual(result["inspected_entries"], entries.consumed)
                self.assertLessEqual(entries.consumed, 16)
                self.assertEqual(entries.metadata_calls, 0 if excluded else entries.consumed)
                self.assertEqual(result["files"], [])
                self.assertTrue(result["truncated"])
                self.assertIn("max_entries", result["truncation_reasons"])
                self.assertTrue(entries.closed)
                scan.assert_called_once_with(self.project)

    def test_empty_project_is_complete_and_has_no_invented_stack_or_tests(self):
        result = inspect_project(self.project)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["manifests"], [])
        self.assertEqual(result["stacks"], [])
        self.assertEqual(result["test_signals"], [])
        self.assertFalse(result["truncated"])

    def test_bounds_require_integers_not_booleans_and_reject_unbounded_requests(self):
        for value in (True, False, 0, -1, 1.5, "2", None, 10**9):
            with self.subTest(max_files=value), self.assertRaises(AICError):
                inspect_project(self.project, max_files=value)
        for value in (True, False, -1, 1.5, "2", None, 10**9):
            with self.subTest(max_depth=value), self.assertRaises(AICError):
                inspect_project(self.project, max_depth=value)
        self.assertFalse(inspect_project(self.project, max_depth=0)["truncated"])

    def test_nonexistent_and_file_roots_are_rejected(self):
        with self.assertRaises(AICError):
            inspect_project(self.project / "missing")
        file_path = self.write_file("file.py")
        with self.assertRaises(AICError):
            inspect_project(file_path)

    def test_special_files_are_not_opened_or_reported_as_source(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("Named pipes are unavailable on this platform.")
        os.mkfifo(self.project / "pipe.py")
        self.write_file("public.py")
        result = inspect_project(self.project)
        self.assertEqual([entry["path"] for entry in result["files"]], ["public.py"])

    def test_unreadable_subtree_is_reported_as_incomplete_without_private_names(self):
        with patch("aiclib.inspection.os.scandir", side_effect=PermissionError("PRIVATE_ERROR_PATH")):
            result = inspect_project(self.project)
        self.assertTrue(result["truncated"])
        self.assertIn("unreadable_paths", result["truncation_reasons"])
        self.assertNotIn("PRIVATE_ERROR_PATH", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
