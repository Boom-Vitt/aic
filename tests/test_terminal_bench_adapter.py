"""Offline Terminal-Bench receipt and credential-gate checks. No model calls."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "benchmarks" / "terminal_bench" / "adapter.py"
PIN_PATH = ROOT / "benchmarks" / "terminal_bench" / "pins.json"
TERMINAL_BENCH_COMMIT = "cfc7b6c66f2c731e4b70d92ee71ee5d6d3b55b64"
HARBOR_COMMIT = "2bc1a23bd961de0bec8742940f35ac9070c67815"
KEY = "test-key-should-not-appear-in-argv"

STUB = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

def values(flag):
    found = []
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        if args[index] == flag and index + 1 < len(args):
            found.append(args[index + 1])
            index += 2
        else:
            index += 1
    return found

log = Path(os.environ["AIC_TB_STUB_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("AIC_TB_STUB_MODE") == "fail":
    raise SystemExit(1)
jobs = Path(values("--jobs-dir")[0])
name = values("--job-name")[0]
job = jobs / name
job.mkdir(parents=True)
rewards = json.loads(os.environ["AIC_TB_STUB_REWARDS"])
for task_id in values("--include-task-name"):
    spec = rewards[task_id]
    trial = job / (task_id + "__trial")
    trial.mkdir()
    body = {
        "task_name": task_id,
        "exception_info": None,
        "verifier_result": {"rewards": {}},
    }
    if "reward" in spec:
        body["verifier_result"]["rewards"]["reward"] = spec["reward"]
    if spec.get("exception_type"):
        body["exception_info"] = {"exception_type": spec["exception_type"]}
    (trial / "result.json").write_text(json.dumps(body), encoding="utf-8")
raise SystemExit(int(os.environ.get("AIC_TB_STUB_EXIT", "0")))
"""


def load_adapter():
    spec = importlib.util.spec_from_file_location("terminal_bench_adapter", ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADAPTER = load_adapter()


class TerminalBenchAdapterTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stub = self.base / "stub-harbor"
        self.stub.write_text(STUB, encoding="utf-8")
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)
        self.log = self.base / "stub-log.jsonl"
        self.output = self.base / "receipt.json"
        self.jobs = self.base / "jobs"

    def environment(self, key=None, **extra):
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["AIC_TERMINAL_BENCH_HARBOR"] = str(self.stub)
        env["AIC_TB_STUB_LOG"] = str(self.log)
        if key is not None:
            env["ANTHROPIC_API_KEY"] = key
        env.update(extra)
        return env

    def run_adapter(self, *args, env):
        return subprocess.run(
            [sys.executable, "-B", str(ADAPTER_PATH), *map(str, args)],
            cwd=self.base,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def run_args(self, output=None):
        return [
            "--model", "anthropic/claude-fable-5",
            "--task-id", "pass-task",
            "--task-id", "fail-task",
            "--seed", "0",
            "--seed", "1",
            "--jobs-dir", self.jobs,
            "--output", self.output if output is None else output,
        ]

    def test_pins_match_the_reviewed_apache_commits(self):
        pins = json.loads(PIN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(pins["terminal_bench"]["commit"], TERMINAL_BENCH_COMMIT)
        self.assertEqual(pins["harbor"]["commit"], HARBOR_COMMIT)
        self.assertEqual(pins["terminal_bench"]["license"], "Apache-2.0")
        self.assertEqual(pins["harbor"]["license"], "Apache-2.0")
        self.assertEqual(pins["terminal_bench"]["tasks_path"], "tasks")
        self.assertEqual(pins["checked"], "2026-11-07")

    def test_reward_mapping_is_pass_only_at_one_without_an_exception(self):
        cases = (
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": 1}}, "exception_info": None}, True, 1, None),
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": 1.0}}, "exception_info": None}, True, 1.0, None),
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": 0}}, "exception_info": None}, False, 0, None),
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": 0.5}}, "exception_info": None}, False, 0.5, None),
            ({"task_name": "t", "verifier_result": {"rewards": {}}, "exception_info": None}, False, None, None),
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": 1}}, "exception_info": {"exception_type": "TimeoutError"}}, False, 1, "TimeoutError"),
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": True}}, "exception_info": None}, False, None, None),
            ({"task_name": "t", "verifier_result": {"rewards": {"reward": float("nan")}}, "exception_info": None}, False, None, None),
        )
        for result, passed, reward, error in cases:
            with self.subTest(result=result):
                parsed = ADAPTER.parse_trial(result)
                self.assertEqual(parsed["passed"], passed)
                self.assertEqual(parsed["reward"], reward)
                self.assertEqual(parsed["error"], error)
        with self.assertRaises(ADAPTER.AdapterFailure):
            ADAPTER.parse_trial({"verifier_result": {"rewards": {"reward": 1}}})

    def test_receipt_requires_both_configurations_for_every_task_and_seed(self):
        pins = ADAPTER.load_pins()
        trials = []
        for configuration in ("baseline", "aic"):
            for task_id, passed, reward in (("pass-task", True, 1), ("fail-task", False, 0)):
                trials.append({
                    "configuration": configuration,
                    "task_id": task_id,
                    "seed": 0,
                    "passed": passed,
                    "reward": reward,
                    "error": None,
                    "job_name": f"{configuration}-seed-0",
                })
        receipt = ADAPTER.build_receipt(
            model_id="anthropic/claude-fable-5",
            pins=pins,
            aic_commit="a" * 40,
            aic_worktree_dirty=False,
            task_ids=["pass-task", "fail-task"],
            seeds=[0],
            sandbox="docker",
            n_concurrent=1,
            harbor_invocation="override",
            trials=trials,
        )
        self.assertEqual(ADAPTER.validate_receipt(receipt), [])
        self.assertEqual(receipt["pins"]["terminal_bench"]["commit"], TERMINAL_BENCH_COMMIT)
        self.assertEqual(receipt["pins"]["harbor"]["commit"], HARBOR_COMMIT)
        self.assertEqual(receipt["task_ids"], ["pass-task", "fail-task"])
        self.assertEqual(receipt["seeds"], [0])
        self.assertIsNone(receipt["configurations"]["baseline"]["plugin"])
        self.assertEqual(receipt["configurations"]["baseline"]["skills"], [])
        self.assertEqual(receipt["configurations"]["aic"]["skills"], ["aic"])
        self.assertEqual(receipt["configurations"]["aic"]["plugin"]["name"], "aic")
        broken = json.loads(json.dumps(receipt))
        broken["configurations"]["baseline"]["trials"][0]["passed"] = False
        self.assertTrue(ADAPTER.validate_receipt(broken))
        broken["configurations"]["baseline"]["trials"][0]["passed"] = True
        del broken["configurations"]["aic"]
        self.assertTrue(any("aic" in problem for problem in ADAPTER.validate_receipt(broken)))

    def test_missing_or_blank_key_exits_3_and_records_nothing(self):
        sentinel = self.base / "sentinel.txt"
        sentinel.write_text("keep\n", encoding="utf-8")
        self.output.write_text("previous\n", encoding="utf-8")
        for label, key in (("unset", None), ("empty", ""), ("blank", "  \n")):
            with self.subTest(label=label):
                result = self.run_adapter(*self.run_args(), env=self.environment(key))
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_API_KEY is unset or blank.", result.stderr)
                self.assertIn("no receipt was written.", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.output.read_text(encoding="utf-8"), "previous\n")
                self.assertFalse(self.jobs.exists())
                self.assertFalse(self.log.exists())
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_help_does_not_require_a_key(self):
        result = self.run_adapter("--help", env=self.environment())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--seed", result.stdout)
        self.assertFalse(self.jobs.exists())

    def test_stub_run_writes_a_paired_receipt_without_putting_the_key_on_argv(self):
        env = self.environment(
            KEY,
            AIC_TB_STUB_REWARDS=json.dumps({"pass-task": {"reward": 1}, "fail-task": {"reward": 0}}),
        )
        result = self.run_adapter(*self.run_args(), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(KEY, result.stdout + result.stderr)
        invocations = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(invocations), 4)
        self.assertNotIn(KEY, json.dumps(invocations))
        repo = f"harbor-framework/terminal-bench@{TERMINAL_BENCH_COMMIT}"
        skills = {}
        for args in invocations:
            self.assertEqual(args[args.index("--repo") + 1], repo)
            self.assertEqual(args[args.index("--agent") + 1], "claude-code")
            self.assertEqual(args[args.index("--model") + 1], "anthropic/claude-fable-5")
            self.assertEqual(args[args.index("--path") + 1], "tasks")
            self.assertEqual(args[args.index("--env") + 1], "docker")
            self.assertIn("--yes", args)
            name = args[args.index("--job-name") + 1]
            included = [args[index + 1] for index, token in enumerate(args) if token == "--include-task-name"]
            self.assertEqual(included, ["pass-task", "fail-task"])
            if "--skill" in args:
                skills[name] = Path(args[args.index("--skill") + 1])
            else:
                skills[name] = None
        self.assertIsNone(skills["baseline-seed-0"])
        self.assertIsNone(skills["baseline-seed-1"])
        skill = skills["aic-seed-0"]
        self.assertEqual(skills["aic-seed-1"], skill)
        self.assertEqual((skill / "SKILL.md").read_bytes(), (ROOT / "skills/aic/SKILL.md").read_bytes())
        self.assertEqual((skill / "skills/aic/SKILL.md").read_bytes(), (ROOT / "skills/aic/SKILL.md").read_bytes())
        manifest = json.loads((skill / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "aic")
        receipt = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(ADAPTER.validate_receipt(receipt), [])
        self.assertEqual(receipt["pins"]["harbor"]["invocation"], "override")
        self.assertEqual(receipt["pins"]["aic"]["commit"], subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        ).strip())
        for configuration in ("baseline", "aic"):
            by_key = {(trial["task_id"], trial["seed"]): trial for trial in receipt["configurations"][configuration]["trials"]}
            self.assertEqual(set(by_key), {("pass-task", 0), ("pass-task", 1), ("fail-task", 0), ("fail-task", 1)})
            self.assertTrue(by_key[("pass-task", 0)]["passed"])
            self.assertEqual(by_key[("pass-task", 0)]["reward"], 1)
            self.assertFalse(by_key[("fail-task", 1)]["passed"])
            self.assertEqual(by_key[("fail-task", 1)]["reward"], 0)
        checked = self.run_adapter("--validate-receipt", self.output, env=self.environment())
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").count("\n"), 4)

    def test_incomplete_harbor_run_does_not_write_a_receipt(self):
        env = self.environment(KEY, AIC_TB_STUB_MODE="fail")
        result = self.run_adapter(
            "--model", "anthropic/claude-fable-5",
            "--task-id", "pass-task",
            "--seed", "0",
            "--jobs-dir", self.jobs,
            "--output", self.output,
            env=env,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("No receipt was written.", result.stderr)
        self.assertFalse(self.output.exists())

    def test_failed_tasks_are_still_recorded_when_harbor_exits_nonzero(self):
        env = self.environment(
            KEY,
            AIC_TB_STUB_EXIT="1",
            AIC_TB_STUB_REWARDS=json.dumps({
                "pass-task": {"reward": 1, "exception_type": "TimeoutError"},
            }),
        )
        result = self.run_adapter(
            "--model", "anthropic/claude-fable-5",
            "--task-id", "pass-task",
            "--seed", "0",
            "--jobs-dir", self.jobs,
            "--output", self.output,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(self.output.read_text(encoding="utf-8"))
        trial = receipt["configurations"]["baseline"]["trials"][0]
        self.assertFalse(trial["passed"])
        self.assertEqual(trial["reward"], 1)
        self.assertEqual(trial["error"], "TimeoutError")
        self.assertEqual(receipt["seeds"], [0])

    def test_existing_receipt_is_not_overwritten_or_started(self):
        self.output.write_text("keep\n", encoding="utf-8")
        result = self.run_adapter(*self.run_args(), env=self.environment(KEY))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse(self.log.exists())

    def test_skill_symlink_is_refused(self):
        repo = self.base / "repo"
        skill = repo / "skills" / "aic"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("skill\n", encoding="utf-8")
        (skill / "linked.md").symlink_to(skill / "SKILL.md")
        manifest = repo / ".claude-plugin"
        manifest.mkdir()
        (manifest / "plugin.json").write_text('{"name": "aic"}\n', encoding="utf-8")
        with self.assertRaises(ADAPTER.AdapterFailure) as caught:
            ADAPTER.stage_plugin_and_skill(repo, self.base / "surface")
        self.assertIn("symlink", str(caught.exception).lower())


if __name__ == "__main__":
    unittest.main()
