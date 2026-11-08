"""Changed-surface records: exit-code gates, and no command execution."""
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
        "task": "Signed totals disagree with the ledger.",
        "change_kind": "failure",
        "outcome": "passed",
        "checks": [
            {
                "command": "python -m unittest tests.test_totals",
                "phase": "before",
                "observed": "AssertionError: expected 1",
                "exit_code": 1,
            },
            {
                "command": "python -m unittest tests.test_totals",
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
    def test_passed_failure_keeps_the_red_then_green_pair(self):
        accepted = validate_surface(record())
        self.assertEqual(accepted["outcome"], "passed")
        self.assertEqual(accepted["checks"][0]["exit_code"], 1)
        self.assertEqual(accepted["checks"][1]["exit_code"], 0)
        accepted["outcome"] = "failed"
        self.assertEqual(validate_surface(record())["outcome"], "passed")

    def test_passed_failure_without_the_before_run_is_rejected(self):
        value = record()
        value["checks"] = [value["checks"][1]]
        with self.assertRaises(AICError) as caught:
            validate_surface(value)
        self.assertIn("nonzero before", str(caught.exception))

    def test_passed_behavior_uses_the_same_pair_as_a_failure(self):
        accepted = validate_surface(record(change_kind="behavior", task="Add slugify."))
        self.assertEqual(accepted["change_kind"], "behavior")
        value = record(change_kind="behavior", task="Add slugify.")
        value["checks"][0]["exit_code"] = 0
        with self.assertRaises(AICError):
            validate_surface(value)

    def test_passed_refactor_requires_the_same_successful_check(self):
        checks = [
            {"command": "python -m unittest tests.test_billing", "phase": "before", "observed": "OK", "exit_code": 0},
            {"command": "python -m unittest tests.test_billing", "phase": "after", "observed": "OK", "exit_code": 0},
        ]
        accepted = validate_surface(record(change_kind="refactor", task="Split billing.", checks=checks))
        self.assertEqual(accepted["change_kind"], "refactor")
        checks[1]["exit_code"] = 1
        with self.assertRaises(AICError):
            validate_surface(record(change_kind="refactor", task="Split billing.", checks=checks, outcome="passed"))

    def test_passed_docs_rejects_a_check_whose_exit_changed(self):
        checks = [
            {"command": "git diff --exit-code -- src", "phase": "before", "observed": "clean", "exit_code": 0},
            {"command": "git diff --exit-code -- src", "phase": "after", "observed": "src changed", "exit_code": 1},
        ]
        with self.assertRaises(AICError) as caught:
            validate_surface(record(change_kind="docs", task="Document the limiter.", checks=checks))
        self.assertIn("exit code changed", str(caught.exception))
        after_only = [checks[0] | {"phase": "after"}]
        accepted = validate_surface(record(change_kind="docs", task="Document the limiter.", checks=after_only))
        self.assertEqual(accepted["checks"][0]["phase"], "after")

    def test_passed_with_a_skipped_check_is_rejected_and_blocked_is_not(self):
        with self.assertRaises(AICError):
            validate_surface(record(not_run=["lint"]))
        blocked = validate_surface(record(outcome="blocked", checks=[], not_run=["the check could not be started"]))
        self.assertEqual(blocked["outcome"], "blocked")
        self.assertEqual(blocked["checks"], [])

    def test_hidden_grader_paths_and_escapes_are_rejected_without_running(self):
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
            "python -m unittest oracle/test_oracle.py",
            "cat reference/solution.py",
            "python -m unittest ../outside.py",
            "/usr/bin/python -m unittest tests.test_totals",
        ):
            value = record()
            value["checks"][0]["command"] = command
            value["checks"][1]["command"] = command
            with self.subTest(command=command):
                with self.assertRaises(AICError):
                    validate_surface(value)

    def test_cli_accepts_a_record_and_rejects_a_passed_claim_without_a_rerun(self):
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
            rejected = subprocess.run(
                [sys.executable, "-B", str(CLI), "check-surface", str(bad)],
                cwd=base, env=env, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("nonzero before", rejected.stderr)
            self.assertNotIn("Traceback", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
