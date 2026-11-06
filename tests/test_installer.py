import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/aic/scripts"))
from aiclib import installer
from aiclib.safety import AICError


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="installer-", dir=ROOT / ".work")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.home = self.base / "home"
        self.project.mkdir()
        self.home.mkdir()
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("---\nname: aic\n---\nUse scripts/aic.py.\n", encoding="utf-8")
        (self.source / "scripts").mkdir()
        (self.source / "scripts/aic.py").write_text("print('self-contained')\n", encoding="utf-8")
        self.target = self.project / ".agents/skills/aic"

    def snapshot(self, path):
        return {
            item.relative_to(path).as_posix(): (item.read_bytes(), item.stat().st_mtime_ns, item.stat().st_ino)
            for item in path.rglob("*") if item.is_file() and not item.is_symlink()
        }

    def manifest(self):
        return json.loads((self.target / ".aic-install.json").read_text(encoding="utf-8"))

    def write_manifest(self, value):
        (self.target / ".aic-install.json").write_text(json.dumps(value), encoding="utf-8")

    def assert_operations_refuse_without_changes(self):
        before = self.snapshot(self.target)
        for operation in (lambda: installer.install(self.source, self.target), lambda: installer.uninstall(self.target)):
            with self.assertRaises(AICError):
                operation()
            self.assertEqual(self.snapshot(self.target), before)

    def test_native_named_targets_use_documented_project_and_user_roots(self):
        mappings = {
            "claude-code": (".claude/skills", ".claude/skills"),
            "codex": (".agents/skills", ".agents/skills"),
            "omp": (".omp/skills", ".omp/agent/skills"),
            "pi": (".pi/skills", ".pi/agent/skills"),
        }
        for agent, (project_path, user_path) in mappings.items():
            with self.subTest(agent=agent):
                self.assertEqual(installer.destination(agent, "project", project=self.project), self.project / project_path / "aic")
                self.assertEqual(installer.destination(agent, "user", home=self.home), self.home / user_path / "aic")

    def test_registry_extension_entries_are_available_without_code_changes(self):
        registry = self.base / "harnesses.json"
        registry.write_text(json.dumps({
            "schema_version": 1,
            "agents": [{"id": "extension-agent", "name": "Extension Agent", "project": ".extension/skills", "user": ".config/extension/skills", "source": "https://example.org/official/skills", "status": "documented"}],
        }), encoding="utf-8")
        with mock.patch.object(installer, "_REGISTRY_PATH", registry):
            self.assertEqual(installer.destination("extension-agent", "project", project=self.project), self.project / ".extension/skills/aic")
            self.assertEqual(installer.destination("extension-agent", "user", home=self.home), self.home / ".config/extension/skills/aic")

    def test_opencode_config_root_is_trusted_adapter_data_and_installable(self):
        target = installer.destination("opencode", "user", home=self.home)
        self.assertEqual(target, self.home / ".config/opencode/skills/aic")
        self.assertEqual(installer.install(self.source, target)["status"], "installed")
        self.assertTrue((target / "SKILL.md").is_file())
        self.assertEqual(installer.uninstall(target)["status"], "uninstalled")
        self.assertTrue(target.parent.is_dir())

    def test_generic_requires_explicit_skill_parent_and_never_changes_it_during_resolution(self):
        explicit = self.project / "custom/skills"
        self.assertEqual(installer.destination("generic", "project", destination=explicit), explicit / "aic")
        self.assertFalse(explicit.exists())
        with self.assertRaises(AICError):
            installer.destination("generic", "project", project=self.project)
        with self.assertRaises(AICError):
            installer.destination("codex", "project", project=self.project, destination=explicit)

    def test_unknown_agent_unsupported_scope_and_missing_project_error(self):
        for agent, scope, options in (
            ("not-a-harness", "project", {"project": self.project}),
            ("deepseek", "project", {"project": self.project}),
            ("codex", "global", {"home": self.home}),
            ("codex", "project", {}),
            ("generic", "machine", {"destination": self.project}),
        ):
            with self.subTest(agent=agent, scope=scope), self.assertRaises(AICError):
                installer.destination(agent, scope, **options)
        registry = self.base / "limited.json"
        registry.write_text(json.dumps({"schema_version": 1, "agents": [{"id": "limited", "name": "Limited", "project": ".limited/skills", "user": None, "source": "https://example.org/skills", "status": "documented"}]}), encoding="utf-8")
        with mock.patch.object(installer, "_REGISTRY_PATH", registry), self.assertRaises(AICError):
            installer.destination("limited", "user", home=self.home)

    def test_source_is_copied_with_hash_ownership_and_can_be_removed_independently(self):
        result = installer.install(self.source, self.target)
        self.assertEqual(result, {"status": "installed", "path": str(self.target)})
        manifest = self.manifest()
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["package"], "aic")
        self.assertEqual(manifest["files"]["scripts/aic.py"], hashlib.sha256((self.source / "scripts/aic.py").read_bytes()).hexdigest())
        self.assertEqual((self.target / "scripts/aic.py").read_bytes(), (self.source / "scripts/aic.py").read_bytes())
        (self.source / "scripts/aic.py").unlink()
        self.assertTrue((self.target / "scripts/aic.py").is_file())
        sibling = self.target.parent / "unrelated.txt"
        sibling.write_text("preserve", encoding="utf-8")
        self.assertEqual(installer.uninstall(self.target), {"status": "uninstalled", "path": str(self.target)})
        self.assertFalse(self.target.exists())
        self.assertEqual(sibling.read_text(encoding="utf-8"), "preserve")
        self.assertTrue(self.target.parent.is_dir())

    def test_identical_install_is_no_write_idempotent(self):
        installer.install(self.source, self.target)
        before = self.snapshot(self.target)
        parent_stat = self.target.parent.stat().st_mtime_ns
        target_stat = self.target.stat().st_mtime_ns
        self.assertEqual(installer.install(self.source, self.target)["status"], "unchanged")
        self.assertEqual(self.snapshot(self.target), before)
        self.assertEqual(self.target.stat().st_mtime_ns, target_stat)
        self.assertEqual(self.target.parent.stat().st_mtime_ns, parent_stat)

    def test_upgrade_replaces_only_intact_owned_install_and_records_new_hashes(self):
        installer.install(self.source, self.target)
        (self.source / "scripts/aic.py").unlink()
        (self.source / "references").mkdir()
        (self.source / "references/workflow.txt").write_text("new release", encoding="utf-8")
        (self.source / "SKILL.md").write_text("New self-contained release.\n", encoding="utf-8")
        self.assertEqual(installer.install(self.source, self.target)["status"], "upgraded")
        self.assertFalse((self.target / "scripts/aic.py").exists())
        self.assertEqual((self.target / "references/workflow.txt").read_text(encoding="utf-8"), "new release")
        self.assertEqual(set(self.manifest()["files"]), {"SKILL.md", "references/workflow.txt"})
        self.assertEqual(installer.uninstall(self.target)["status"], "uninstalled")

    def test_unmanaged_and_modified_installs_are_preserved(self):
        self.target.mkdir(parents=True)
        (self.target / "SKILL.md").write_text("User-owned skill", encoding="utf-8")
        self.assert_operations_refuse_without_changes()
        (self.target / "SKILL.md").unlink()
        self.target.rmdir()
        installer.install(self.source, self.target)
        (self.target / "SKILL.md").write_text("Owner edits", encoding="utf-8")
        self.assert_operations_refuse_without_changes()

    def test_missing_managed_file_and_extra_file_or_empty_directory_are_preserved(self):
        installer.install(self.source, self.target)
        extra = self.target / "owner-notes.txt"
        extra.write_text("Keep me", encoding="utf-8")
        self.assert_operations_refuse_without_changes()
        extra.unlink()
        empty = self.target / "owner-directory"
        empty.mkdir()
        self.assert_operations_refuse_without_changes()
        self.assertTrue(empty.is_dir())
        empty.rmdir()
        (self.target / "scripts/aic.py").unlink()
        self.assert_operations_refuse_without_changes()

    def test_malformed_traversal_and_noncanonical_manifests_are_preserved(self):
        installer.install(self.source, self.target)
        original = self.manifest()
        digest = original["files"]["SKILL.md"]
        malformed = [
            [],
            {**original, "schema_version": True},
            {**original, "schema_version": 2},
            {**original, "package": "other"},
            {**original, "unexpected": "value"},
            {**original, "files": {}},
            {**original, "files": {"../outside.txt": digest}},
            {**original, "files": {"/outside.txt": digest}},
            {**original, "files": {"scripts\\outside.txt": digest}},
            {**original, "files": {"scripts/../outside.txt": digest}},
            {**original, "files": {"./SKILL.md": digest}},
            {**original, "files": {"SKILL.md": "not-a-hash"}},
            {**original, "directories": ["../outside"]},
        ]
        outside = self.base / "outside.txt"
        outside.write_text("Outside ownership", encoding="utf-8")
        for value in malformed:
            with self.subTest(manifest=value):
                self.write_manifest(value)
                self.assert_operations_refuse_without_changes()
                self.assertEqual(outside.read_text(encoding="utf-8"), "Outside ownership")
        (self.target / ".aic-install.json").write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        self.assert_operations_refuse_without_changes()

    def test_symlink_target_parent_and_managed_files_are_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "owner.txt").write_text("Keep", encoding="utf-8")
        linked = self.project / "linked"
        linked.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(AICError):
            installer.destination("generic", "project", destination=linked)
        with self.assertRaises(AICError):
            installer.install(self.source, linked / "aic")
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(outside, target_is_directory=True)
        for operation in (lambda: installer.install(self.source, self.target), lambda: installer.uninstall(self.target)):
            with self.assertRaises(AICError):
                operation()
        self.target.unlink()
        installer.install(self.source, self.target)
        managed = self.target / "scripts/aic.py"
        managed.unlink()
        managed.symlink_to(outside / "owner.txt")
        self.assert_operations_refuse_without_changes()
        self.assertTrue(managed.is_symlink())
        self.assertEqual((outside / "owner.txt").read_text(encoding="utf-8"), "Keep")

    def test_dangling_symlink_and_symlink_manifest_are_refused(self):
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(self.base / "missing", target_is_directory=True)
        with self.assertRaises(AICError):
            installer.install(self.source, self.target)
        self.assertTrue(self.target.is_symlink())
        self.target.unlink()
        installer.install(self.source, self.target)
        manifest = self.target / ".aic-install.json"
        saved = self.base / "manifest-copy.json"
        saved.write_bytes(manifest.read_bytes())
        manifest.unlink()
        manifest.symlink_to(saved)
        self.assert_operations_refuse_without_changes()
        self.assertTrue(manifest.is_symlink())

    def test_lexical_escape_paths_are_refused_before_mutation(self):
        for path in (str(self.project) + "/../outside", str(self.project) + "/nested/../../outside"):
            with self.subTest(path=path), self.assertRaises(AICError):
                installer.destination("generic", "project", destination=path)
        with self.assertRaises(AICError):
            installer.install(self.source, str(self.project) + "/../aic")
        self.assertFalse((self.base / "aic").exists())

    def test_runtime_state_bytecode_and_source_symlinks_are_not_copied(self):
        for relative in ("scripts/__pycache__/cached.pyc", "scripts/loose.pyc", ".aic/memory/note.json", ".work/state.json", ".pytest_cache/state"):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("runtime-only", encoding="utf-8")
        installer.install(self.source, self.target)
        self.assertEqual(set(self.manifest()["files"]), {"SKILL.md", "scripts/aic.py"})
        self.assertFalse((self.target / "scripts/__pycache__").exists())
        self.assertFalse((self.target / ".aic").exists())
        (self.source / "linked.txt").symlink_to(self.base / "missing")
        before = self.snapshot(self.target)
        with self.assertRaises(AICError):
            installer.install(self.source, self.target)
        self.assertEqual(self.snapshot(self.target), before)

    def test_registry_escape_and_symlink_discovery_roots_are_refused(self):
        registry = self.base / "bad-registry.json"
        for value in ("../outside", "/outside", ".config/../../outside", "skills\\outside"):
            registry.write_text(json.dumps({"schema_version": 1, "agents": [{"id": "unsafe", "name": "Unsafe", "project": value, "user": None, "source": "https://example.org/skills", "status": "documented"}]}), encoding="utf-8")
            with self.subTest(value=value), mock.patch.object(installer, "_REGISTRY_PATH", registry), self.assertRaises(AICError):
                installer.destination("unsafe", "project", project=self.project)
        outside = self.base / "external-config"
        outside.mkdir()
        (self.home / ".config").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(AICError):
            installer.destination("opencode", "user", home=self.home)
        self.assertEqual(list(outside.iterdir()), [])

    def test_staging_failure_preserves_previous_release(self):
        installer.install(self.source, self.target)
        before = self.snapshot(self.target)
        (self.source / "SKILL.md").write_text("Upgrade", encoding="utf-8")
        with mock.patch.object(installer.shutil, "copyfileobj", side_effect=OSError("simulated copy failure")), self.assertRaises(AICError):
            installer.install(self.source, self.target)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertEqual(sorted(item.name for item in self.target.parent.iterdir()), ["aic"])

    def test_replacement_failure_rolls_back_intact_previous_release(self):
        installer.install(self.source, self.target)
        before = self.snapshot(self.target)
        (self.source / "SKILL.md").write_text("Upgrade", encoding="utf-8")
        original_rename = installer.os.rename

        def fail_new_release(source, destination, **kwargs):
            if Path(source).name.startswith(".aic-stage-"):
                raise OSError("simulated atomic replacement failure")
            return original_rename(source, destination, **kwargs)

        with mock.patch.object(installer.os, "rename", side_effect=fail_new_release), self.assertRaises(AICError):
            installer.install(self.source, self.target)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertEqual(sorted(item.name for item in self.target.parent.iterdir()), ["aic"])

    def test_invalid_source_and_relative_mutation_paths_have_no_effect(self):
        (self.source / "SKILL.md").unlink()
        with self.assertRaises(AICError):
            installer.install(self.source, self.target)
        self.assertFalse(self.target.parent.exists())
        with self.assertRaises(AICError):
            installer.install(self.source, Path("relative/aic"))
        with self.assertRaises(AICError):
            installer.uninstall(Path("relative/aic"))

    def test_default_user_home_is_resolved_without_writes(self):
        with mock.patch.object(installer.Path, "home", return_value=self.home):
            target = installer.destination("codex", "user")
        self.assertEqual(target, self.home / ".agents/skills/aic")
        self.assertEqual(list(self.home.iterdir()), [])

    def prepare_ancestor_swap(self):
        outside = self.base / "unrelated"
        outside.mkdir()
        (outside / "aic").mkdir()
        (outside / "aic/sentinel.txt").write_text("Never delete unrelated data", encoding="utf-8")
        moved = self.base / "original-skills"
        original_rename = installer.os.rename

        def swap():
            original_rename(self.target.parent, moved)
            self.target.parent.symlink_to(outside, target_is_directory=True)

        return outside, moved, swap

    def test_uninstall_ancestor_swap_after_validation_cannot_redirect_deletion(self):
        installer.install(self.source, self.target)
        outside, moved, swap = self.prepare_ancestor_swap()
        original_remove = installer._remove_directory

        def swap_before_removal(parent, name, descriptor, manifest=None):
            swap()
            return original_remove(parent, name, descriptor, manifest)

        with mock.patch.object(installer, "_remove_directory", side_effect=swap_before_removal):
            self.assertEqual(installer.uninstall(self.target)["status"], "uninstalled")
        self.assertEqual((outside / "aic/sentinel.txt").read_text(encoding="utf-8"), "Never delete unrelated data")
        self.assertFalse((moved / "aic").exists())
        self.assertTrue((outside / "aic").is_dir())

    def test_upgrade_ancestor_swap_cannot_redirect_replacement_or_backup_deletion(self):
        installer.install(self.source, self.target)
        (self.source / "SKILL.md").write_text("Upgraded release", encoding="utf-8")
        outside, moved, swap = self.prepare_ancestor_swap()
        original_rename = installer.os.rename
        swapped = False

        def swap_before_backup(source, destination, **kwargs):
            nonlocal swapped
            if source == "aic" and not swapped:
                swapped = True
                swap()
            return original_rename(source, destination, **kwargs)

        with mock.patch.object(installer.os, "rename", side_effect=swap_before_backup):
            self.assertEqual(installer.install(self.source, self.target)["status"], "upgraded")
        self.assertTrue(swapped)
        self.assertEqual((outside / "aic/sentinel.txt").read_text(encoding="utf-8"), "Never delete unrelated data")
        self.assertEqual((moved / "aic/SKILL.md").read_text(encoding="utf-8"), "Upgraded release")
        self.assertEqual(sorted(path.name for path in moved.iterdir()), ["aic"])

    def test_failed_upgrade_rollback_is_anchored_despite_ancestor_swap(self):
        installer.install(self.source, self.target)
        before = self.snapshot(self.target)
        (self.source / "SKILL.md").write_text("Upgraded release", encoding="utf-8")
        outside, moved, swap = self.prepare_ancestor_swap()
        original_rename = installer.os.rename

        def fail_and_swap(source, destination, **kwargs):
            if Path(source).name.startswith(".aic-stage-"):
                swap()
                raise OSError("simulated replacement failure with ancestor swap")
            return original_rename(source, destination, **kwargs)

        with mock.patch.object(installer.os, "rename", side_effect=fail_and_swap), self.assertRaises(AICError):
            installer.install(self.source, self.target)
        self.assertEqual((outside / "aic/sentinel.txt").read_text(encoding="utf-8"), "Never delete unrelated data")
        self.assertEqual(self.snapshot(moved / "aic"), before)
        self.assertEqual(sorted(path.name for path in moved.iterdir()), ["aic"])

    def test_mutation_fails_closed_without_required_descriptor_primitives(self):
        with mock.patch.object(installer, "_SAFE_MUTATION_PRIMITIVES", False):
            with self.assertRaises(AICError):
                installer.install(self.source, self.target)
            with self.assertRaises(AICError):
                installer.uninstall(self.target)
        self.assertFalse(self.target.parent.exists())


if __name__ == "__main__":
    unittest.main()
