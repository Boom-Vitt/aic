"""Changed-surface records: same check before and after, and no command execution."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/aic/scripts"))
from aiclib.safety import AICError
from aiclib.surface import validate_surface

CLI = ROOT / "scripts" / "aic.py"


def record(**overrides):
    value = {
        "schema_version": 1,
        "kind": "aic-changed-surface",
        "task": "Empty names are still accepted.",
        "outcome": "passed",
        "checks": [
            {
                "command": "python -m unittest tests.test_form",
                "phase": "before",
                "observed": "AssertionError: empty name was accepted",
                "exit_code": 1,
            },
            {
                "command": "python -m unittest tests.test_form",
                "phase": "after",
                "observed": "OK",
                "exit_code": 0,
            },
        ],
        "not_run": [],
    }
    value.update(overrides)
    return value


class SurfaceTests(unittest.TestCase):
    def test_passed_keeps_the_same_command_and_its_exit_codes(self):
        accepted = validate_surface(record())
        self.assertEqual(accepted["outcome"], "passed")
        self.assertEqual(accepted["checks"][0]["command"], accepted["checks"][1]["command"])
        self.assertEqual([item["exit_code"] for item in accepted["checks"]], [1, 0])
        accepted["outcome"] = "failed"
        self.assertEqual(validate_surface(record())["outcome"], "passed")

    def test_passed_accepts_any_recorded_exit_pair_for_the_same_command(self):
        for before, after in ((1, 0), (0, 0), (0, 1), (2, 3)):
            value = record()
            value["checks"][0]["exit_code"] = before
            value["checks"][1]["exit_code"] = after
            with self.subTest(before=before, after=after):
                accepted = validate_surface(value)
                self.assertEqual([item["exit_code"] for item in accepted["checks"]], [before, after])

    def test_passed_without_the_rerun_is_rejected(self):
        value = record()
        value["checks"] = [value["checks"][0]]
        with self.assertRaises(AICError) as caught:
            validate_surface(value)
        self.assertIn("same command", str(caught.exception))
        different = record()
        different["checks"][1]["command"] = "python -m unittest tests.test_other"
        with self.assertRaises(AICError):
            validate_surface(different)

    def test_passed_rejects_a_shown_check_that_was_not_rerun(self):
        value = record()
        value["checks"].append({
            "command": "python -m unittest tests.test_other",
            "phase": "before",
            "observed": "OK",
            "exit_code": 0,
        })
        with self.assertRaises(AICError) as caught:
            validate_surface(value)
        self.assertIn("same command", str(caught.exception))

    def test_passed_with_a_skipped_check_is_rejected_and_blocked_is_not(self):
        with self.assertRaises(AICError):
            validate_surface(record(not_run=["lint"]))
        blocked = validate_surface(record(outcome="blocked", checks=[], not_run=["the check could not be started"]))
        self.assertEqual(blocked["outcome"], "blocked")
        self.assertEqual(blocked["checks"], [])
        partial = validate_surface(record(
            outcome="partial",
            checks=[record()["checks"][1]],
            not_run=["a second route"],
        ))
        self.assertEqual(partial["outcome"], "partial")

    def test_commands_that_leave_the_workspace_are_rejected_without_running(self):
        marker = ROOT / ".work" / "surface-must-not-be-created"
        if marker.exists():
            marker.unlink()
        command = f"python -c \"open({str(marker)!r}, 'w').write('x')\""
        value = record()
        value["checks"][0]["command"] = command
        value["checks"][1]["command"] = command
        validate_surface(value)
        self.assertFalse(marker.exists())
        for command in (
            "python -m unittest ../outside.py",
            "/usr/bin/python -m unittest tests.test_form",
        ):
            value = record()
            value["checks"][0]["command"] = command
            value["checks"][1]["command"] = command
            with self.subTest(command=command):
                with self.assertRaises(AICError):
                    validate_surface(value)

    def test_cli_accepts_a_record_and_rejects_a_passed_claim_without_a_rerun(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as directory:
            base = Path(directory)
            good = base / "good.json"
            good.write_text(json.dumps(record()), encoding="utf-8")
            bad = base / "bad.json"
            incomplete = record()
            incomplete["checks"] = incomplete["checks"][:1]
            bad.write_text(json.dumps(incomplete), encoding="utf-8")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            accepted = subprocess.run(
                [sys.executable, "-B", str(CLI), "check-surface", str(good)],
                cwd=base, env=env, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(json.loads(accepted.stdout)["outcome"], "passed")
            self.assertNotIn("change_kind", json.loads(accepted.stdout))
            rejected = subprocess.run(
                [sys.executable, "-B", str(CLI), "check-surface", str(bad)],
                cwd=base, env=env, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("same command", rejected.stderr)
            self.assertNotIn("Traceback", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
