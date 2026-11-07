"""SWE-bench Lite runner contracts. These checks do not call Claude, Docker, or Hugging Face."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout

from benchmarks.swe_bench.constants import (
    AIC_SKILL_COMMAND,
    DATASET_CARD_LICENSE_FIELD,
    DATASET_ID,
    DATASET_REVISION,
    EXPECTED_TEST_INSTANCES,
    HARNESS_COMMIT,
    HARNESS_LICENSE,
    HARNESS_REQUIREMENT,
    MISSING_KEY_MESSAGE,
    REPO_ROOT,
    SMOKE_INSTANCES,
)
from benchmarks.swe_bench.contract import (
    ContractError,
    api_key_present,
    assert_not_vendored,
    child_env,
    claude_command,
    conditions_for,
    dataset_export_command,
    final_exit,
    git_materialize_commands,
    issue_prompt,
    lexical_absolute,
    missing_commands,
    official_count_line,
    open_nofollow,
    prediction_record,
    prepare_output,
    redact,
    reject_score_only_smoke,
    require_instance_id,
    score_command,
    select_instances,
    validate_test_split,
)
from benchmarks.swe_bench.live import main

ROOT = Path(__file__).resolve().parents[1]


def _instances(count, **extra):
    rows = []
    for index in range(count):
        row = {
            "instance_id": f"repo__name-{index:04d}",
            "repo": "example/example",
            "base_commit": "a" * 40,
            "problem_statement": f"issue {index}",
        }
        row.update(extra)
        rows.append(row)
    return rows


class SWEBenchContractTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_missing_key_exits_3_and_records_nothing(self):
        output = self.base / "not-created"
        for env in ({}, {"ANTHROPIC_API_KEY": ""}, {"ANTHROPIC_API_KEY": " \n\t"}):
            with self.subTest(env=env):
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = main(["--output", str(output), "--smoke", "--not-a-flag"], env=env)
                self.assertEqual(code, 3)
                self.assertFalse(output.exists())
                self.assertIn(MISSING_KEY_MESSAGE, stderr.getvalue())
                self.assertNotIn("resolved_instances", stderr.getvalue())
                self.assertFalse(api_key_present(env))

    def test_help_without_a_key_does_not_create_output(self):
        output = self.base / "help-output"
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--help"], env={})
        self.assertEqual(caught.exception.code, 0)
        self.assertFalse(output.exists())

    def test_cli_without_a_key_exits_3_and_writes_no_directory(self):
        output = self.base / "cli-output"
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.swe_bench", "--output", str(output), "--smoke"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(output.exists())
        self.assertIn("No SWE-bench predictions or scores were recorded.", result.stderr)
        self.assertNotIn("resolved_instances", result.stdout + result.stderr)

    def test_smoke_subset_is_the_first_ten_sorted_ids_of_a_complete_split(self):
        rows = _instances(EXPECTED_TEST_INSTANCES)
        rows[0]["patch"] = "GOLD_CANARY_PATCH"
        rows[0]["test_patch"] = "GOLD_TEST_PATCH"
        rows[0]["FAIL_TO_PASS"] = "GOLD_TESTS"
        rows.reverse()
        public = validate_test_split(rows)
        self.assertNotIn("patch", public[0])
        self.assertNotIn("GOLD_CANARY_PATCH", json.dumps(public))
        chosen = select_instances(public, smoke=True)
        self.assertEqual(len(chosen), SMOKE_INSTANCES)
        self.assertEqual(SMOKE_INSTANCES, 10)
        self.assertEqual(
            [row["instance_id"] for row in chosen],
            [f"repo__name-{index:04d}" for index in range(10)],
        )
        self.assertEqual(len(select_instances(public, smoke=False)), EXPECTED_TEST_INSTANCES)
        with self.assertRaises(ContractError):
            validate_test_split(_instances(EXPECTED_TEST_INSTANCES - 1))

    def test_prompts_and_claude_commands_keep_the_arms_distinct(self):
        statement = "The widget drops the last row."
        baseline = issue_prompt(statement, use_aic=False)
        with_aic = issue_prompt(statement, use_aic=True)
        self.assertNotIn(AIC_SKILL_COMMAND, baseline)
        self.assertIn(AIC_SKILL_COMMAND, with_aic)
        self.assertIn("----- BEGIN ISSUE -----\n" + statement, baseline)
        self.assertIn("----- BEGIN ISSUE -----\n" + statement, with_aic)
        self.assertNotIn("GOLD_CANARY_PATCH", baseline + with_aic)
        bare = claude_command(prompt=baseline, plugin_dir=None, model=None, max_turns=30, max_budget_usd=None)
        plugged = claude_command(
            prompt=with_aic,
            plugin_dir=REPO_ROOT,
            model=None,
            max_turns=30,
            max_budget_usd=None,
        )
        self.assertEqual(bare[0], "claude")
        self.assertIn("--bare", bare)
        self.assertNotIn("--plugin-dir", bare)
        self.assertNotIn("--dangerously-skip-permissions", bare)
        self.assertEqual(bare[bare.index("-p") + 1], baseline)
        self.assertIn("Bash(curl *)", bare)
        self.assertNotIn("WebFetch", bare)
        self.assertEqual(plugged[plugged.index("--plugin-dir") + 1], str(REPO_ROOT))
        self.assertTrue((REPO_ROOT / ".claude-plugin" / "plugin.json").is_file())
        self.assertEqual(conditions_for("both"), ("baseline", "aic"))

    def test_predictions_and_score_command_use_the_pinned_harness(self):
        record = prediction_record("repo__name-0001", "", "baseline")
        other = prediction_record("repo__name-0001", "diff --git a/a b/a\n", "aic")
        self.assertEqual(set(record), {"instance_id", "model_patch", "model_name_or_path"})
        self.assertEqual(record["model_patch"], "")
        self.assertEqual(record["model_name_or_path"], "claude-code-baseline")
        self.assertEqual(other["model_name_or_path"], "claude-code-aic")
        command = score_command(
            Path("/tmp/harness-venv/bin/python"),
            Path("/tmp/predictions.jsonl"),
            "baseline",
            ["repo__name-0001"],
            1,
        )
        self.assertEqual(command[:3], ["/tmp/harness-venv/bin/python", "-m", "swebench.harness.run_evaluation"])
        self.assertIn(DATASET_ID, command)
        self.assertIn("--split", command)
        self.assertNotIn("--modal", command)
        self.assertIn(HARNESS_COMMIT, HARNESS_REQUIREMENT)
        self.assertNotIn("@main", HARNESS_REQUIREMENT)
        self.assertTrue(HARNESS_REQUIREMENT.startswith("swebench @ git+https://github.com/SWE-bench/SWE-bench.git@"))
        export = dataset_export_command(Path("/usr/bin/python3"))
        self.assertEqual(export[3:6], [DATASET_ID, DATASET_REVISION, "test"])
        self.assertIn("problem_statement", export[2])
        self.assertNotIn("test_patch", export[2])
        self.assertNotIn("FAIL_TO_PASS", export[2])
        self.assertIn('+ "\\n"', export[2])

    def test_child_environment_receives_the_api_key_only_for_claude(self):
        parent = {
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "secret-key",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
            "LANG": "C.UTF-8",
        }
        harness = child_env(parent, home=Path("/tmp/home"), hf_home=Path("/tmp/hf"), api_key=None)
        claude = child_env(parent, home=Path("/tmp/home"), hf_home=Path("/tmp/hf"), api_key="secret-key")
        self.assertNotIn("ANTHROPIC_API_KEY", harness)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", harness)
        self.assertEqual(harness["PATH"], "/usr/bin")
        self.assertEqual(claude["ANTHROPIC_API_KEY"], "secret-key")
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", claude)
        self.assertEqual(redact("saw secret-key in output", "secret-key"), "saw [redacted] in output")
        self.assertEqual(harness["HOME"], "/tmp/home")

    def test_official_counts_are_copied_only_as_integers(self):
        self.assertEqual(
            official_count_line({"resolved_instances": 2, "total_instances": 10}),
            "resolved_instances=2 total_instances=10",
        )
        self.assertIsNone(official_count_line({"schema_version": 2}))
        with self.assertRaises(ContractError):
            official_count_line({"resolved_instances": True, "total_instances": 10})
        self.assertEqual(final_exit(0, [0, 0]), 0)
        self.assertEqual(final_exit(0, [2]), 1)
        self.assertEqual(final_exit(3, [0]), 1)

    def test_output_cannot_vendor_the_dataset_or_follow_a_symlink(self):
        inside = lexical_absolute(Path(".work/../benchmarks/out"), REPO_ROOT)
        with self.assertRaises(ContractError):
            assert_not_vendored(inside, REPO_ROOT)
        allowed = lexical_absolute(Path(".work/swe-bench-lite"), REPO_ROOT)
        assert_not_vendored(allowed, REPO_ROOT)
        assert_not_vendored(lexical_absolute(Path("/tmp/swe-bench-lite"), Path("/")), REPO_ROOT)
        target = self.base / "target"
        target.mkdir()
        link = self.base / "linked-output"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ContractError):
            prepare_output(link, score_only=False)
        real = self.base / "predictions.jsonl"
        real.write_text("{}\n", encoding="utf-8")
        alias = self.base / "predictions-link"
        alias.symlink_to(real)
        with self.assertRaises(OSError):
            open_nofollow(alias, append=True)
        with self.assertRaises(ContractError):
            git_materialize_commands("example/example;rm -rf /", "a" * 40, self.base / "repo")
        commands = git_materialize_commands("example/example", "b" * 40, self.base / "repo")
        self.assertTrue(all(";" not in part for command in commands for part in command))
        self.assertIn("core.hooksPath=/dev/null", commands[0])
        with self.assertRaises(ContractError):
            require_instance_id("owner/name with spaces")
        self.assertEqual(missing_commands({"git", "docker"}, score_only=True), [])
        self.assertEqual(missing_commands({"git", "docker"}, score_only=False), ["claude"])
        with self.assertRaises(ContractError):
            reject_score_only_smoke(True, True)

    def test_readme_records_the_checked_terms_and_pins(self):
        text = (ROOT / "benchmarks/swe_bench/README.md").read_text(encoding="utf-8")
        self.assertEqual(DATASET_ID, "SWE-bench/SWE-bench_Lite")
        self.assertEqual(DATASET_REVISION, "b0dde1093fe417d83b7184254edf8199c1f0dff5")
        self.assertEqual(HARNESS_COMMIT, "02e7a74ffd0b707aab73d203fe87bdc7c76afc8e")
        self.assertEqual(HARNESS_LICENSE, "MIT")
        self.assertIsNone(DATASET_CARD_LICENSE_FIELD)
        for phrase in (
            DATASET_ID,
            DATASET_REVISION,
            HARNESS_COMMIT,
            "MIT",
            "Carlos E Jimenez",
            "gated: false",
            "no `license` key",
            "Does not vendor the parquet",
            "python -m benchmarks.swe_bench --output .work/swe-bench-lite --smoke",
            "exits **3**",
            "November 7, 2026",
        ):
            self.assertIn(phrase, text)
