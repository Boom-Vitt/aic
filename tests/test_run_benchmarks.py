"""The pinned comparison prices a ceiling, refuses a missing key, and records receipts."""
import json
import os
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from aicbench.official import sandbox_argv
from aicbench.runner import main as aicbench_main
from benchmarks.client import Completion
from benchmarks.errors import RunError
from benchmarks.routing.compare import load_cases, prompts
from benchmarks.run import load_settings, main


KEY = "present-for-test"
DAY = date(2026, 11, 7)


def cases():
    return load_cases(ROOT / "tests" / "fixtures" / "routing-scenarios.json")


class FakeClient:
    def __init__(self):
        self.calls = []

    def complete(self, *, model, system, user, max_tokens):
        self.calls.append({"model": model, "system": system, "user": user, "max_tokens": max_tokens})
        case = next(item for item in cases() if item["request"] == user)
        body = {
            "task": KEY,
            "workflow": case["expected_workflow"],
            "template": case["expected_template"],
            "topology": case["expected_topology"],
        }
        return Completion(json.dumps(body), 2, 3, {"echo": KEY})


class ExplodingClient:
    def complete(self, **kwargs):
        raise AssertionError("dry-run called the model client")


def fake_sandbox(argv, timeout):
    loaded = "/opt/aic" in argv
    return subprocess.CompletedProcess(argv, 0, json.dumps({"workflow_loaded": loaded}), "")


class ComparisonCommandTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temporary.cleanup)
        self.results = Path(self.temporary.name)
        self.previous = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = KEY
        self.addCleanup(self._restore_key)

    def _restore_key(self):
        if self.previous is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self.previous

    def _run(self, argv, **kwargs):
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = main(
                argv,
                sandbox_runner=kwargs.get("sandbox_runner", fake_sandbox),
                harness_runner=kwargs.get("harness_runner"),
                client=kwargs.get("client", FakeClient()),
                today=kwargs.get("today", DAY),
                results_root=kwargs.get("results_root", self.results),
                revision_reader=kwargs.get("revision_reader"),
            )
        return code, buffer.getvalue()

    def test_missing_or_blank_key_exits_3_before_an_estimate(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        code, output = self._run(["--dry-run"], client=ExplodingClient())
        self.assertEqual(code, 3)
        self.assertEqual(output, "")
        os.environ["ANTHROPIC_API_KEY"] = "   "
        code, output = self._run(["--dry-run"], client=ExplodingClient())
        self.assertEqual(code, 3)
        self.assertEqual(output, "")

    def test_dry_run_prints_the_ceiling_and_writes_nothing(self):
        def explode_sandbox(argv, timeout):
            raise AssertionError("dry-run started bubblewrap")

        code, output = self._run(["--dry-run"], client=ExplodingClient(), sandbox_runner=explode_sandbox)
        self.assertEqual(code, 0, output)
        estimate = json.loads(output)
        settings = load_settings(ROOT)
        parts = [
            f"# {relative}\n{(ROOT / relative).read_text(encoding='utf-8')}"
            for relative in settings["aic_context"]
        ]
        aic_text = "\n\n".join(parts)
        input_tokens = 0
        for case in cases():
            for system, user in prompts(case, aic_text).values():
                self.assertNotIn("expected_workflow", system)
                self.assertEqual(user, case["request"])
                input_tokens += len(system.encode("utf-8")) + len(user.encode("utf-8"))
        output_tokens = len(cases()) * 2 * settings["max_tokens"]
        millionths = input_tokens * settings["pricing"]["input_usd_per_million"]
        millionths += output_tokens * settings["pricing"]["output_usd_per_million"]
        ceiling = f"{millionths // 1_000_000}.{millionths % 1_000_000:06d}"
        self.assertEqual(estimate["input_token_ceiling"], input_tokens)
        self.assertEqual(estimate["output_token_budget"], output_tokens)
        self.assertEqual(estimate["budget_cost_ceiling_usd"], ceiling)
        self.assertEqual(estimate["model"], "claude-sonnet-5-5")
        self.assertIsNone(estimate["public_benchmark_scores"])
        self.assertEqual(estimate["unpriced"], [])
        self.assertFalse((self.results / "results").exists())

    def test_fake_client_writes_a_provenance_bundle_without_the_key(self):
        client = FakeClient()
        code, output = self._run([], client=client)
        self.assertEqual(code, 0, output)
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        bundle = self.results / "results" / f"2026-11-07-{sha}"
        provenance = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))
        routing = json.loads((bundle / "receipts" / "routing.json").read_text(encoding="utf-8"))
        official = json.loads((bundle / "receipts" / "aicbench.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["git_sha"], sha)
        self.assertIsInstance(provenance["worktree_dirty"], bool)
        self.assertEqual(provenance["model"], "claude-sonnet-5-5")
        self.assertEqual(provenance["date"], "2026-11-07")
        self.assertEqual(provenance["seed_sent_to_provider"], False)
        self.assertTrue(provenance["completed"])
        self.assertIsNone(provenance["public_benchmark_scores"])
        self.assertEqual(routing["label_matches"], {"aic": len(cases()), "plain-claude-code": len(cases())})
        self.assertIsNone(routing["public_benchmark_scores"])
        self.assertEqual(routing["command"], "python3 -m benchmarks.routing.compare")
        self.assertEqual(official["command"], "python3 -m aicbench --sandbox container --official")
        self.assertIsNone(official["public_benchmark_scores"])
        self.assertEqual([item["workflow_loaded"] for item in official["runs"]], [False, True])
        self.assertEqual(len(client.calls), len(cases()) * 2)
        self.assertTrue(all(call["model"] == "claude-sonnet-5-5" and call["max_tokens"] == 1024 for call in client.calls))
        self.assertTrue(all("expected_workflow" not in call["system"] and "expected_workflow" not in call["user"] for call in client.calls))
        requests = {case["request"] for case in cases()}
        self.assertTrue(all(call["user"] in requests for call in client.calls))
        project = json.loads((ROOT / "tests" / "fixtures" / "routing-scenarios.json").read_text(encoding="utf-8"))
        self.assertNotIn(project["project_case"]["request"], requests)
        aic_calls = [call for call in client.calls if "skills/aic/references/routing.md" in call["system"]]
        plain_calls = [call for call in client.calls if call not in aic_calls]
        self.assertEqual(len(aic_calls), len(cases()))
        self.assertEqual(len(plain_calls), len(cases()))
        self.assertIn("must be the integer", aic_calls[0]["system"])
        self.assertNotIn("must be the integer", plain_calls[0]["system"])
        raw = json.loads((bundle / "raw" / "routing" / "aic" / "coupled-bug.json").read_text(encoding="utf-8"))
        self.assertNotIn(KEY, raw["text"])
        self.assertIn("[redacted]", raw["text"])
        for path in bundle.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY, path.read_text(encoding="utf-8"))
        again, _output = self._run([], client=FakeClient())
        self.assertEqual(again, 3)

    def test_a_failed_call_is_not_retried(self):
        class StopClient:
            def __init__(self):
                self.calls = 0

            def complete(self, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    raise RunError("stopped", 1)
                return Completion("{}", 1, 1, {})

        client = StopClient()
        code, _output = self._run([], client=client)
        self.assertEqual(code, 1)
        self.assertEqual(client.calls, 2)

    def test_optional_suites_fail_closed_before_the_client(self):
        client = FakeClient()
        code, _output = self._run(["--terminal-bench"], client=client)
        self.assertEqual(code, 3)
        self.assertEqual(client.calls, [])
        blocked = next((self.results / "results").glob("*/receipts/blocked.json"))
        receipt = json.loads(blocked.read_text(encoding="utf-8"))
        self.assertFalse(receipt["executed"])
        self.assertTrue(receipt["stopped_before_model"])
        self.assertIsNone(receipt["public_benchmark_scores"])

    def test_optional_subset_uses_the_pinned_cli_without_putting_the_key_in_argv(self):
        settings = load_settings(ROOT)
        checkout = self.results / "checkout"
        checkout.mkdir()
        predictions = self.results / "predictions.jsonl"
        predictions.write_text('{"instance_id": "repo__name-1", "model_patch": "diff"}\n', encoding="utf-8")
        seen = []

        def reader(path):
            if path == checkout:
                return settings["swe_bench_lite"]["revision"]
            raise AssertionError(path)

        def harness(argv, cwd, env, timeout):
            seen.append((argv, cwd, timeout))
            self.assertNotIn(KEY, argv)
            self.assertEqual(env.get("ANTHROPIC_API_KEY"), KEY)
            return subprocess.CompletedProcess(argv, 0, "harness output", "")

        code, _output = self._run(
            ["--swe-bench-lite", "--swe-bench-lite-checkout", str(checkout), "--swe-bench-lite-predictions", str(predictions)],
            client=FakeClient(),
            harness_runner=harness,
            revision_reader=reader,
        )
        self.assertEqual(code, 0, _output)
        argv, cwd, timeout = seen[0]
        self.assertEqual(cwd, checkout)
        self.assertEqual(timeout, settings["swe_bench_lite"]["wall_clock_sec"])
        self.assertIn("swebench.harness.run_evaluation", argv)
        self.assertIn("repo__name-1", argv)
        self.assertNotIn(KEY, argv)
        receipt = json.loads(next((self.results / "results").glob("*/receipts/swe-bench-lite.json")).read_text(encoding="utf-8"))
        self.assertFalse(receipt["aic_treatment"])
        self.assertIsNone(receipt["public_benchmark_scores"])
        self.assertEqual(receipt["instance_count"], 1)
        estimate = json.loads(_output)
        self.assertIn("swe-bench-lite", estimate["unpriced"])

    def test_terminal_bench_checkout_must_be_a_real_directory_at_the_pin(self):
        settings = load_settings(ROOT)
        real = self.results / "real"
        real.mkdir()
        link = self.results / "link"
        link.symlink_to(real)
        called = []

        def reader(path):
            called.append(path)
            return settings["terminal_bench"]["revision"]

        code, _output = self._run(
            ["--terminal-bench", "--terminal-bench-checkout", str(link)],
            client=ExplodingClient(),
            revision_reader=reader,
        )
        self.assertEqual(code, 3)
        self.assertEqual(called, [])
        other = self.results / "other-root"
        other.mkdir()
        code, _output = self._run(
            ["--terminal-bench", "--terminal-bench-checkout", str(real)],
            client=ExplodingClient(),
            results_root=other,
            revision_reader=lambda _path: "a" * 40,
        )
        self.assertEqual(code, 3)
        blocked = json.loads(next((other / "results").glob("*/receipts/blocked.json")).read_text(encoding="utf-8"))
        self.assertIn("pinned revision", blocked["reason"])

    def test_container_argv_hides_the_skill_and_the_environment_from_the_plain_arm(self):
        probe = ROOT / "benchmarks" / "official"
        skill = ROOT / "skills" / "aic"
        plain = sandbox_argv(probe_dir=probe, skill_dir=None)
        treated = sandbox_argv(probe_dir=probe, skill_dir=skill)
        self.assertEqual(plain[0], "bwrap")
        self.assertIn("--unshare-all", plain)
        self.assertIn("--clearenv", plain)
        self.assertNotIn("/opt/aic", plain)
        self.assertIn("/opt/aic", treated)
        self.assertNotIn(KEY, plain)
        self.assertNotIn(KEY, treated)

    def test_official_cli_accepts_container_and_rejects_a_mixed_command(self):
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = aicbench_main(["--sandbox", "container", "--official"], sandbox_runner=fake_sandbox)
        self.assertEqual(code, 0, buffer.getvalue())
        receipt = json.loads(buffer.getvalue())
        self.assertIsNone(receipt["public_benchmark_scores"])
        self.assertFalse(receipt["invokes_model"])
        mixed = aicbench_main(["run", "--suite", "smoke", "--sandbox", "container", "--official"])
        self.assertEqual(mixed, 2)

    def test_shell_exits_3_without_the_key_and_dry_run_does_not_create_results(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        missing = subprocess.run(
            [str(ROOT / "scripts" / "run-benchmarks.sh"), "--dry-run"],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(missing.returncode, 3, missing.stderr)
        self.assertIn("ANTHROPIC_API_KEY", missing.stderr)
        self.assertNotIn(KEY, missing.stderr)
        env["ANTHROPIC_API_KEY"] = KEY
        dry = subprocess.run(
            [str(ROOT / "scripts" / "run-benchmarks.sh"), "--dry-run"],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(dry.returncode, 0, dry.stderr)
        estimate = json.loads(dry.stdout)
        self.assertEqual(estimate["model"], "claude-sonnet-5-5")
        self.assertIsNone(estimate["public_benchmark_scores"])
        self.assertNotIn(KEY, dry.stdout)
        self.assertFalse((ROOT / "results").exists())

    def test_workflow_is_manual_and_pins_actions(self):
        text = (ROOT / ".github" / "workflows" / "benchmarks.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request", text)
        self.assertNotIn("push:", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("bubblewrap", text)
        self.assertEqual(text.count("secrets.ANTHROPIC_API_KEY"), 1)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", text)
        self.assertIn("actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", text)
        self.assertIn("actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9", text)
        self.assertNotIn("actions/checkout@v", text)
        upload = text.split("Upload the results bundle", 1)[1]
        self.assertNotIn("ANTHROPIC_API_KEY", upload)

    def test_prices_and_subset_limits_stay_the_reviewed_pins(self):
        settings = load_settings(ROOT)
        self.assertEqual(settings["model"], "claude-sonnet-5-5")
        self.assertEqual(settings["pricing"]["input_usd_per_million"], 2)
        self.assertEqual(settings["pricing"]["output_usd_per_million"], 10)
        self.assertEqual(settings["pricing"]["checked"], "2026-11-07")
        self.assertEqual(settings["terminal_bench"]["n_tasks"], 1)
        self.assertEqual(settings["terminal_bench"]["revision"], "d28711d0da2675d0bb1d56de45ae5df6082438a3")
        self.assertEqual(settings["swe_bench_lite"]["max_predictions"], 5)
        self.assertEqual(settings["swe_bench_lite"]["revision"], "02e7a74ffd0b707aab73d203fe87bdc7c76afc8e")
        self.assertIsNone(settings["terminal_bench"]["token_budget"])
        self.assertIsNone(settings["swe_bench_lite"]["token_budget"])

    def test_documented_command_claims_no_public_score(self):
        doc = (ROOT / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8")
        self.assertIn("No public benchmark score is claimed.", doc)
        self.assertIn("./scripts/run-benchmarks.sh", doc)
        self.assertNotIn("%", doc)


class LiveBubblewrapTests(unittest.TestCase):
    def test_official_probe_sees_only_the_aic_mount(self):
        if shutil.which("bwrap") is None:
            self.skipTest("bubblewrap is not installed")
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as temp:
            output = Path(temp) / "official.json"
            completed = subprocess.run(
                [sys.executable, "-m", "aicbench", "--sandbox", "container", "--official", "--output", str(output)],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "scripts"), "ANTHROPIC_API_KEY": KEY},
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0 and "bwrap" in completed.stderr and "unshare" in completed.stderr.lower():
                self.skipTest(completed.stderr.strip())
            self.assertEqual(completed.returncode, 0, completed.stderr)
            text = output.read_text(encoding="utf-8")
            receipt = json.loads(text)
            self.assertIsNone(receipt["public_benchmark_scores"])
            self.assertEqual([item["workflow_loaded"] for item in receipt["runs"]], [False, True])
            self.assertNotIn(KEY, text)
