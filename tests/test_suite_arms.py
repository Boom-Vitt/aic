"""Key-free proof that Terminal-Bench and SWE-bench Lite load the official arms."""
import json
import os
import shutil
from datetime import date
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.budget import agent_env_script, claude_shell, dollar_stop, install_environment
from benchmarks.terminal_bench.phases import dispatch_task_command
from benchmarks.suite_arms import (
    OFFICIAL_IDS,
    apply_harness_marker,
    prepare_live_official_arms,
    prepare_stand_in_arms,
)
from benchmarks.baselines.adapter import AdapterError


KEY = "suite-arm-sentinel"
TERMINAL_REVISION = "d28711d0da2675d0bb1d56de45ae5df6082438a3"
SWE_REVISION = "02e7a74ffd0b707aab73d203fe87bdc7c76afc8e"


def _load_runner():
    import importlib.util

    spec = importlib.util.spec_from_file_location("suite_benchrun", ROOT / "scripts" / "benchmarks" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedStopTests(unittest.TestCase):
    def test_the_stop_uses_pinned_prices_turns_and_timeout(self):
        stop = dollar_stop(
            max_turns=30,
            timeout_sec=600,
            max_tokens=1024,
            input_usd_per_million=2,
            output_usd_per_million=10,
        )
        self.assertEqual(stop["input_token_allowance"], 18000)
        self.assertEqual(stop["output_token_allowance"], 30720)
        self.assertEqual(stop["exact_usd_millionths"], 343200)
        self.assertEqual(stop["max_usd"], "0.35")

    def test_install_environment_has_no_api_key_and_the_shell_command_omits_it(self):
        env = install_environment("anthropic/claude-sonnet-5-5")
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertEqual(env["ANTHROPIC_MODEL"], "claude-sonnet-5-5")
        script = agent_env_script(KEY)
        command = ". /installed-agent/agent-env.sh && " + claude_shell(
            "Fix the task.",
            model="claude-sonnet-5-5",
            max_turns=30,
            max_usd="0.35",
            plugin_dir="/tmp/aic-plugin",
        )
        self.assertIn(KEY, script)
        self.assertNotIn(KEY, command)
        self.assertIn("--max-budget-usd", command)
        self.assertIn("--plugin-dir", command)
        self.assertNotIn("--seed", command)
        with self.assertRaises(ValueError):
            agent_env_script("   ")
        refused = []

        def execute(argv):
            refused.append(argv)
            return 0, "", ""

        response = dispatch_task_command(json.dumps(["-lc", f"echo {KEY}"]).encode(), KEY, execute)
        self.assertEqual(response, b"refused\n")
        self.assertEqual(refused, [])


class SuiteStubTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_stub_command_loads_only_the_aic_plugin_and_needs_no_key(self):
        output = self.base / "stub.json"
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.suite_arms", "stub", "--output", str(output)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertFalse(report["invokes_model"])
        self.assertFalse(report["fetched"])
        self.assertFalse(report["harness_invoked"])
        self.assertFalse(report["official"])
        self.assertIsNone(report["public_benchmark_scores"])
        self.assertFalse(report["score_includes_treatment"])
        self.assertEqual(report["budget"], {"max_turns": 30, "timeout_sec": 600, "max_usd": 0.35})
        self.assertEqual(report["excluded_arms"], ["superpowers"])
        self.assertEqual(report["revisions"]["terminal-bench"], TERMINAL_REVISION)
        self.assertEqual(report["revisions"]["swe-bench-lite"], SWE_REVISION)
        self.assertEqual([item["arm"] for item in report["arms"]], list(OFFICIAL_IDS))
        treated = [item["arm"] for item in report["arms"] if item["aic_treatment"] is True]
        self.assertEqual(treated, ["aic"])
        for item in report["arms"]:
            self.assertEqual(item["model"], "claude-sonnet-5-5")
            self.assertEqual(item["seed"], 0)
            self.assertFalse(item["seed_sent_to_provider"])
            self.assertEqual(item["budget"]["max_usd"], 0.35)
            self.assertIsNone(item["public_benchmark_scores"])
            self.assertFalse(item["harness_loaded_aic"])
            self.assertNotIn("--seed", item["swe_bench_command"])
            joined = " ".join(item["swe_bench_command"] + item["terminal_bench_command"])
            self.assertNotIn(str(ROOT), joined)
            if item["arm"] == "plain-claude-code":
                self.assertNotIn("--plugin-dir", item["swe_bench_command"])
            if item["arm"] == "aic":
                self.assertEqual(item["observer_plugin_name"], "aic")
                self.assertIn("--plugin-dir", item["swe_bench_command"])
        self.assertNotIn("superpowers", [item["arm"] for item in report["arms"]])

    def test_stand_in_aic_mount_is_the_shipped_tree(self):
        prepared = prepare_stand_in_arms()
        self.addCleanup(prepared.close)
        aic = next(item for item in prepared.arms if item["id"] == "aic")
        mount = Path(aic["mount_path"])
        self.assertTrue((mount / "skills" / "aic" / "SKILL.md").is_file())
        self.assertTrue((mount / "src" / "aic_quickstart").is_dir())
        self.assertTrue((mount / ".claude-plugin" / "plugin.json").is_file())
        self.assertFalse((mount / "benchmarks").exists())
        self.assertFalse((mount / "benchmarks" / "routing" / "heldout-v2.json").exists())
        manifest = json.loads((mount / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "aic")
        self.assertNotEqual(mount.resolve(), ROOT.resolve())

    def test_live_prepare_refuses_a_missing_proxy_and_a_bad_key(self):
        empty = self.base / "bin"
        empty.mkdir()
        with self.assertRaises(AdapterError) as missing_proxy:
            prepare_live_official_arms({"PATH": str(empty), "ANTHROPIC_API_KEY": KEY})
        self.assertIn("bubblewrap", str(missing_proxy.exception).lower())
        self.assertEqual(missing_proxy.exception.code, 1)
        for value in ("", "   ", "key with space"):
            with self.assertRaises(AdapterError) as missing_key:
                prepare_live_official_arms({"PATH": str(empty), "ANTHROPIC_API_KEY": value})
            self.assertEqual(missing_key.exception.code, 3)

    def test_a_harness_marker_is_the_only_way_the_harness_flag_turns_true(self):
        output = self.base / "job"
        output.mkdir()
        record = {"arm": "aic", "observer_loaded_aic": True, "harness_loaded_aic": False, "aic_treatment": True}
        apply_harness_marker(record, output)
        self.assertFalse(record["harness_loaded_aic"])
        (output / "arm-load.json").write_text(
            json.dumps({
                "arm": "aic",
                "loaded": True,
                "plugin_name": "aic",
                "install_has_api_key": False,
            }),
            encoding="utf-8",
        )
        apply_harness_marker(record, output)
        self.assertTrue(record["harness_loaded_aic"])
        plain = {"arm": "plain-claude-code", "observer_loaded_aic": False, "harness_loaded_aic": False, "aic_treatment": False}
        apply_harness_marker(plain, output)
        self.assertFalse(plain["harness_loaded_aic"])
        self.assertFalse(plain["aic_treatment"])


class SuiteRunnerTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.results = Path(self.temp.name)
        self.runner = _load_runner()
        self.previous = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = KEY
        self.addCleanup(self._restore)

    def _restore(self):
        if self.previous is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self.previous

    def _run(self, argv, **kwargs):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = self.runner.main(
                argv,
                client=kwargs.get("client", lambda _body: json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"})),
                aicbench_runner=kwargs.get("aicbench_runner", lambda argv, environ=None: 0),
                harness_runner=kwargs.get("harness_runner"),
                today=date(2026, 11, 8),
                results_root=self.results,
                revision_reader=kwargs.get("revision_reader"),
                arm_preparer=kwargs.get("arm_preparer"),
                compare_runner=kwargs.get("compare_runner"),
                suite_runtime_factory=kwargs.get("suite_runtime_factory"),
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_checkout_predictions_or_key_exit_3_before_a_model(self):
        called = {"compare": 0, "prepare": 0}

        def compare(argv, client=None, environ=None, clock=None):
            called["compare"] += 1
            return 0

        def prepare(_env):
            called["prepare"] += 1
            raise AssertionError("prepare ran")

        os.environ.pop("ANTHROPIC_API_KEY", None)
        code, _out, err = self._run(["--terminal-bench"], compare_runner=compare, arm_preparer=prepare)
        self.assertEqual(code, 3, err)
        self.assertEqual(called, {"compare": 0, "prepare": 0})
        os.environ["ANTHROPIC_API_KEY"] = "bad key"
        code, _out, err = self._run(["--terminal-bench"], compare_runner=compare, arm_preparer=prepare)
        self.assertEqual(code, 3, err)
        os.environ["ANTHROPIC_API_KEY"] = KEY
        checkout = self.base = self.results / "checkout"
        checkout.mkdir()
        code, _out, err = self._run(
            ["--terminal-bench", "--terminal-bench-checkout", str(checkout)],
            compare_runner=compare,
            arm_preparer=prepare,
            revision_reader=lambda _path: "0" * 40,
        )
        self.assertEqual(code, 3, err)
        self.assertIn("pinned revision", err)
        self.assertEqual(called["compare"], 0)
        self.assertEqual(called["prepare"], 0)
        bundle = self.results / "results"
        if bundle.exists():
            shutil.rmtree(bundle)
        code, _out, err = self._run(
            ["--swe-bench-lite", "--swe-bench-lite-checkout", str(checkout)],
            compare_runner=compare,
            arm_preparer=prepare,
            revision_reader=lambda _path: SWE_REVISION,
        )
        self.assertEqual(code, 3, err)
        self.assertIn("predictions", err)
        self.assertEqual(called["prepare"], 0)

    def test_fake_harness_records_the_shared_budget_and_an_honest_treatment_flag(self):
        checkout = self.results / "pinned"
        checkout.mkdir()
        predictions = self.results / "predictions.jsonl"
        predictions.write_text(json.dumps({"instance_id": "repo__name-0001"}) + "\n", encoding="utf-8")
        commands = []

        def harness(argv, cwd, env, timeout):
            commands.append((list(argv), dict(env)))
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertFalse(any(KEY in value for value in env.values()))
            self.assertNotIn(KEY, argv)
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        sock_root = self.results

        class Runtime:
            def __init__(self):
                self.calls = []

            def child_env(self):
                return {
                    "AIC_SUITE_AGENT_SOCK": str(sock_root / "agent.sock"),
                    "AIC_SUITE_BWRAP": "/usr/bin/bwrap",
                    "AIC_SUITE_INSTALL_SOCK": str(sock_root / "install.sock"),
                    "AIC_SUITE_KEY_FILE": str(sock_root / "secret"),
                }

            def run(self, argv, **kwargs):
                self.calls.append((list(argv), dict(kwargs)))
                return subprocess.CompletedProcess(argv, 0, "", "")

            def close(self):
                return

        runtime = Runtime()

        def both(path):
            text = str(path)
            if text.endswith("tb"):
                return TERMINAL_REVISION
            if text.endswith("swe"):
                return SWE_REVISION
            raise AssertionError(text)

        terminal = self.results / "tb"
        swe = self.results / "swe"
        terminal.mkdir()
        swe.mkdir()
        code, output, err = self._run(
            [
                "--terminal-bench",
                "--terminal-bench-checkout",
                str(terminal),
                "--swe-bench-lite",
                "--swe-bench-lite-checkout",
                str(swe),
                "--swe-bench-lite-predictions",
                str(predictions),
            ],
            harness_runner=harness,
            revision_reader=both,
            arm_preparer=lambda _env: prepare_stand_in_arms(),
            suite_runtime_factory=lambda _parent, _root, connect=None: runtime,
        )
        self.assertEqual(code, 0, err + output)
        estimate = json.loads(output)
        self.assertEqual(estimate["shared_max_usd"], "0.35")
        self.assertEqual(estimate["shared_budget"]["max_usd"], 0.35)
        for name in ("terminal-bench", "swe-bench-lite"):
            component = next(item for item in estimate["components"] if item["name"] == name)
            self.assertFalse(component["priced"])
            self.assertIsNone(component["token_budget"])
            self.assertEqual(component["arms"], list(OFFICIAL_IDS))
            self.assertEqual(component["max_usd"], "0.35")
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        bundle = self.results / "results" / f"2026-11-08-{sha}"
        terminal_receipt = json.loads((bundle / "receipts" / "terminal-bench.json").read_text(encoding="utf-8"))
        swe_receipt = json.loads((bundle / "receipts" / "swe-bench-lite.json").read_text(encoding="utf-8"))
        self.assertIsNone(terminal_receipt["public_benchmark_scores"])
        self.assertIsNone(swe_receipt["public_benchmark_scores"])
        self.assertFalse(terminal_receipt["score_includes_treatment"])
        self.assertFalse(swe_receipt["evaluation_aic_treatment"])
        self.assertFalse(swe_receipt["harness_loaded_aic"])
        self.assertTrue(terminal_receipt["aic_treatment"])
        self.assertFalse(terminal_receipt["harness_loaded_aic"])
        self.assertEqual(terminal_receipt["budget"]["max_usd"], 0.35)
        self.assertEqual([item["arm"] for item in terminal_receipt["arms"]], list(OFFICIAL_IDS))
        self.assertEqual(
            [item["arm"] for item in terminal_receipt["arms"] if item["aic_treatment"]],
            ["aic"],
        )
        self.assertEqual(len(commands), len(OFFICIAL_IDS) + 1)
        terminal_commands = [argv for argv, _env in commands if "terminal_bench.cli.tb.main" in argv]
        terminal_envs = [env for argv, env in commands if "terminal_bench.cli.tb.main" in argv]
        eval_envs = [env for argv, env in commands if "swebench.harness.run_evaluation" in argv]
        self.assertEqual(len(terminal_commands), len(OFFICIAL_IDS))
        for argv in terminal_commands:
            self.assertIn("benchmarks.terminal_bench.claude_agent:RegistryClaudeAgent", argv)
            self.assertNotIn("--agent", argv)
            self.assertEqual(argv[argv.index("--model") + 1], "anthropic/claude-sonnet-5-5")
            self.assertEqual(argv[argv.index("--global-agent-timeout-sec") + 1], "600")
            self.assertIn("max_budget_usd=0.35", argv)
            self.assertIn("max_turns=30", argv)
            self.assertIn("seed=0", argv)
            self.assertNotIn(KEY, argv)
        aic_command = next(item for item in terminal_commands if "arm_id=aic" in item)
        plain_command = next(item for item in terminal_commands if "arm_id=plain-claude-code" in item)
        self.assertTrue(any(item.startswith("plugin_dir=") for item in aic_command))
        self.assertFalse(any(item.startswith("plugin_dir=") for item in plain_command))
        self.assertNotIn("arm_id=superpowers", " ".join(" ".join(argv) for argv, _env in commands))
        blob = terminal_receipt_text = (bundle / "receipts" / "terminal-bench.json").read_text(encoding="utf-8")
        self.assertNotIn(KEY, blob)
        self.assertNotIn(KEY, (bundle / "receipts" / "swe-bench-lite.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(terminal_receipt_text)
        self.assertEqual(terminal_receipt["network"]["agent"]["allow"], ["api.anthropic.com:443"])
        self.assertFalse(terminal_receipt["network"]["install"]["secrets"])
        self.assertEqual(swe_receipt["network"]["agent"]["allow"], ["api.anthropic.com:443"])
        self.assertEqual(swe_receipt["sandbox"], "container")
        self.assertEqual(len(runtime.calls), len(OFFICIAL_IDS))
        self.assertEqual(swe_receipt["agent_exit_codes"], [0] * len(OFFICIAL_IDS))
        for argv, kwargs in runtime.calls:
            self.assertEqual(kwargs["phase"], "agent")
            self.assertEqual(kwargs["key"], KEY)
            self.assertNotIn(KEY, argv)
            self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "0.35")
            self.assertEqual(argv[argv.index("--max-turns") + 1], "30")
        self.assertEqual(len(terminal_envs), len(OFFICIAL_IDS))
        for env in terminal_envs:
            self.assertIn("AIC_SUITE_AGENT_SOCK", env)
            self.assertNotIn("api.anthropic.com", env["AIC_SUITE_AGENT_SOCK"])
        self.assertEqual(len(eval_envs), 1)
        self.assertNotIn("AIC_SUITE_KEY_FILE", eval_envs[0])

    def test_the_default_opener_refuses_before_the_harness(self):
        checkout = self.results / "tb-refuse"
        checkout.mkdir()

        def opener(parent, root, connect=None):
            raise AdapterError("official suite results refuse to run without the egress proxy.", 1)

        original = self.runner.open_suite_runtime
        self.runner.open_suite_runtime = opener
        try:
            code, _out, err = self._run(
                ["--terminal-bench", "--terminal-bench-checkout", str(checkout)],
                revision_reader=lambda _path: TERMINAL_REVISION,
                harness_runner=lambda *_args: (_ for _ in ()).throw(AssertionError("harness started")),
                arm_preparer=lambda _env: (_ for _ in ()).throw(AssertionError("prepare started")),
            )
        finally:
            self.runner.open_suite_runtime = original
        self.assertEqual(code, 1, err)
        self.assertIn("egress proxy", err)


if __name__ == "__main__":
    unittest.main()
