"""Key-free baseline adapters. No network fetch and no model call."""
from datetime import date
import hashlib
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.baselines.adapter import (
    STAND_IN_MARK,
    AdapterError,
    agent_argv,
    assert_license,
    assert_outside_repo,
    fetch_and_verify,
    git_fetch_commands,
    load_registry,
    stand_in_mount,
)
from benchmarks.aicbench.runner import EXIT_USAGE, main as aicbench_main

PINS = {
    "superpowers": (
        "obra/superpowers",
        "22f0b463e7a5e579904dd6211a520321035526f7",
        "a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400",
        "Copyright (c) 2025 Jesse Vincent",
        "plugin-dir",
    ),
    "ecc": (
        "affaan-m/ECC",
        "d2ef2680594f9a17526a6e1a2e18b3d242c5d17b",
        "326146379f01bb137c0a5d3c54770c1aa31076705c8b88a7f6b26a460f6221b2",
        "Copyright (c) 2026 Affaan Mustafa",
        "plugin-dir",
    ),
    "agent-skills": (
        "addyosmani/agent-skills",
        "301b02b12bff98e4688e6984af6556802322bbde",
        "6f202f8bd568cd730dbb2b0d1f8e243bc74c2fa1f64dbce9b2c7ea08bd5c9fd7",
        "Copyright (c) 2025 Addy Osmani",
        "plugin-dir",
    ),
    "planning-with-files": (
        "OthmanAdi/planning-with-files",
        "2362ca385ad74f061aa0e7b73f56543a4b7e6df2",
        "4f2e5ecfaa4e0833621cfe54c0bdc2f60f086c0925540d7bdc713517eafb3c84",
        "Copyright (c) 2026 Ahmad Adi",
        "plugin-dir",
    ),
    "gstack": (
        "garrytan/gstack",
        "23f9d07ce9e802ac148a8a353228f201655fc5b8",
        "e56fbb5b3d95756f3fa1cfefa24732ec79f18ece1ad08a4e79e00df57e8b198c",
        "Copyright (c) 2026 Garry Tan",
        "add-dir",
    ),
}
KEY = "sk-ant-baseline-sentinel"
BUDGET = {"max_turns": 30, "timeout_sec": 600, "max_usd": None}


def _load_runner():
    spec = importlib.util.spec_from_file_location("baseline_benchrun", ROOT / "scripts" / "benchmarks" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegistryTests(unittest.TestCase):
    def test_registry_locks_the_observed_commits_and_license_hashes(self):
        registry = load_registry()
        self.assertIsNone(registry["public_benchmark_scores"])
        self.assertFalse(registry["vendored"])
        self.assertEqual(registry["model"], "claude-sonnet-5-5")
        self.assertEqual(registry["seed"], 0)
        self.assertFalse(registry["seed_sent_to_provider"])
        self.assertEqual(registry["budget"], BUDGET)
        arms = {item["id"]: item for item in registry["arms"]}
        self.assertEqual(list(arms), ["plain-claude-code", "aic", *PINS])
        self.assertEqual(arms["plain-claude-code"]["mount"], "none")
        self.assertIsNone(arms["plain-claude-code"]["license_spdx"])
        self.assertEqual(arms["aic"]["license_spdx"], "Apache-2.0")
        self.assertEqual(arms["aic"]["plugin_name"], "aic")
        for arm_id, (repository, commit, digest, notice, mount) in PINS.items():
            entry = arms[arm_id]
            self.assertEqual(entry["repository"], repository)
            self.assertEqual(entry["url"], f"https://github.com/{repository}")
            self.assertEqual(entry["commit"], commit)
            self.assertEqual(entry["license_sha256"], digest)
            self.assertEqual(entry["copyright_notice"], notice)
            self.assertEqual(entry["license_spdx"], "MIT")
            self.assertEqual(entry["mount"], mount)
            self.assertTrue(entry["fetches"])
        self.assertFalse((ROOT / "benchmarks" / "baselines" / "vendor").exists())
        self.assertEqual(list((ROOT / "benchmarks" / "baselines").rglob("LICENSE*")), [])

    def test_fetch_commands_use_the_pinned_commit_and_no_shell(self):
        registry = load_registry()
        for entry in registry["arms"]:
            if entry["kind"] != "git":
                continue
            dest = Path("/tmp/aic-baseline-example")
            commands = git_fetch_commands(entry["repository"], entry["commit"], dest)
            self.assertEqual(len(commands), 4)
            flat = [item for command in commands for item in command]
            self.assertIn(entry["commit"], flat)
            self.assertIn(f"https://github.com/{entry['repository']}.git", flat)
            self.assertNotIn(KEY, flat)
            for command in commands:
                self.assertIsInstance(command, list)
                self.assertNotIn("shell", command)
                self.assertTrue(all("\x00" not in item and "\n" not in item for item in command))

    def test_a_different_license_file_does_not_count_as_the_pin(self):
        entry = next(item for item in load_registry()["arms"] if item["id"] == "superpowers")
        (ROOT / ".work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as temporary:
            dest = Path(temporary) / "checkout"
            dest.mkdir()
            body = "MIT License\n\nCopyright (c) 2025 Jesse Vincent\n"
            (dest / "LICENSE").write_text(body, encoding="utf-8")
            plugin = dest / ".claude-plugin"
            plugin.mkdir()
            (plugin / "plugin.json").write_text(json.dumps({"name": "superpowers"}), encoding="utf-8")
            pinned = dict(entry)
            pinned["license_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
            assert_license(pinned, dest)
            pinned["license_sha256"] = "0" * 64
            with self.assertRaises(AdapterError) as caught:
                assert_license(pinned, dest)
            self.assertIn("sha256", str(caught.exception))
            (dest / "LICENSE").write_text(STAND_IN_MARK + "\n" + body, encoding="utf-8")
            pinned["license_sha256"] = hashlib.sha256((dest / "LICENSE").read_bytes()).hexdigest()
            with self.assertRaises(AdapterError):
                assert_license(pinned, dest)

    def test_fetch_verifier_rejects_the_wrong_license_without_an_agent(self):
        entry = next(item for item in load_registry()["arms"] if item["id"] == "gstack")
        with tempfile.TemporaryDirectory(prefix="aic-baseline-fetch-") as temporary:
            dest = Path(temporary) / "gstack"
            launched = []

            def runner(argv, **kwargs):
                launched.append(argv)
                if "init" in argv:
                    Path(argv[-1]).mkdir(parents=True, exist_ok=True)
                if "fetch" in argv:
                    (dest / "LICENSE").write_text("changed license\n", encoding="utf-8")
                    (dest / "SKILL.md").write_text("---\nname: gstack\n---\n\nupstream\n", encoding="utf-8")
                if "rev-parse" in argv:
                    return subprocess.CompletedProcess(argv, 0, entry["commit"] + "\n", "")
                return subprocess.CompletedProcess(argv, 0, "", "")

            with self.assertRaises(AdapterError) as caught:
                fetch_and_verify(entry, dest, runner)
            self.assertIn("sha256", str(caught.exception))
            self.assertTrue(launched)
            self.assertTrue(all(command[0] == "git" for command in launched))

    def test_stand_in_is_not_upstream_text_and_stays_outside_the_repo(self):
        entry = next(item for item in load_registry()["arms"] if item["id"] == "ecc")
        with self.assertRaises(AdapterError):
            assert_outside_repo(ROOT / "benchmarks" / "baselines" / "checkout")
        with tempfile.TemporaryDirectory(prefix="aic-baseline-standin-") as temporary:
            dest = Path(temporary) / "ecc"
            mount, path = stand_in_mount(entry, dest)
            self.assertEqual(mount, "plugin-dir")
            self.assertEqual(path, dest)
            license_text = (dest / "LICENSE").read_text(encoding="utf-8")
            self.assertIn(STAND_IN_MARK, license_text)
            self.assertNotIn(entry["copyright_notice"], license_text)
            self.assertNotIn("Permission is hereby granted", license_text)
            manifest = json.loads((dest / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], "ecc")
            self.assertTrue(manifest["stub"])

    def test_plain_and_aic_commands_share_model_budget_and_seed_inputs(self):
        plain = agent_argv(
            "claude", prompt="Task id: example\n", model="claude-sonnet-5-5", max_turns=30, mount="none", mount_path=None,
        )
        treated = agent_argv(
            "claude",
            prompt="Task id: example\n",
            model="claude-sonnet-5-5",
            max_turns=30,
            mount="plugin-dir",
            mount_path=ROOT,
        )
        self.assertEqual(plain[plain.index("--model") + 1], treated[treated.index("--model") + 1])
        self.assertEqual(plain[plain.index("--max-turns") + 1], "30")
        self.assertNotIn("--plugin-dir", plain)
        self.assertNotIn("--add-dir", plain)
        self.assertEqual(treated[treated.index("--plugin-dir") + 1], str(ROOT))
        self.assertNotIn(KEY, plain + treated)


class StubProofTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.oracle = next(
            path for path in (ROOT / "benchmarks" / "aicbench" / "tasks" / "bugfix-ledger-signs" / "oracle").iterdir()
        ).read_bytes()

    def tearDown(self):
        oracle = ROOT / "benchmarks" / "aicbench" / "tasks" / "bugfix-ledger-signs" / "oracle" / "test_oracle.py"
        if oracle.read_bytes() != self.oracle:
            oracle.write_bytes(self.oracle)

    def test_every_adapter_records_a_stub_receipt_without_a_key_or_a_score(self):
        output = self.base / "receipts.json"
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = KEY
        code = aicbench_main(["--baseline-stub", "--output", str(output)], env)
        self.assertEqual(code, 0, output.read_text(encoding="utf-8") if output.exists() else "no report")
        text = output.read_text(encoding="utf-8")
        self.assertNotIn(KEY, text)
        report = json.loads(text)
        self.assertEqual(report["kind"], "baseline-stub")
        self.assertFalse(report["invokes_model"])
        self.assertFalse(report["measured"])
        self.assertFalse(report["official"])
        self.assertIsNone(report["public_benchmark_scores"])
        self.assertEqual(report["model"], "claude-sonnet-5-5")
        self.assertEqual(report["seed"], 0)
        self.assertEqual(report["budget"], BUDGET)
        self.assertEqual(report["sample_size"], 1)
        self.assertEqual(report["task"], "bugfix-ledger-signs")
        registry = load_registry()
        self.assertEqual([item["arm"] for item in report["receipts"]], [item["id"] for item in registry["arms"]])
        prompts = set()
        for entry, receipt in zip(registry["arms"], report["receipts"], strict=True):
            self.assertEqual(receipt["arm"], entry["id"])
            self.assertEqual(receipt["model"], registry["model"])
            self.assertEqual(receipt["seed"], registry["seed"])
            self.assertEqual(receipt["budget"], BUDGET)
            self.assertEqual(receipt["cost_usd"], "0")
            self.assertIsInstance(receipt["wall_time_seconds"], (int, float))
            self.assertGreaterEqual(receipt["wall_time_seconds"], 0)
            self.assertIs(receipt["passed"], True)
            self.assertIsNone(receipt["public_benchmark_scores"])
            self.assertFalse(receipt["invokes_model"])
            self.assertFalse(receipt["fetched"])
            self.assertEqual(receipt["mount"], entry["mount"])
            self.assertEqual(receipt["license_spdx"], entry.get("license_spdx"))
            self.assertEqual(receipt["commit"], entry.get("commit"))
            self.assertEqual(receipt["repository"], entry.get("repository"))
            prompts.add(receipt["prompt_sha256"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(
            (ROOT / "benchmarks" / "aicbench" / "tasks" / "bugfix-ledger-signs" / "oracle" / "test_oracle.py").read_bytes(),
            self.oracle,
        )
        refused = aicbench_main(["--baseline-stub", "--official", "--output", str(self.base / "no.json")], env)
        self.assertEqual(refused, EXIT_USAGE)
        self.assertFalse((self.base / "no.json").exists())

    def test_module_stub_command_matches_the_runner(self):
        output = self.base / "module.json"
        spec = importlib.util.spec_from_file_location("baselines_main_mod", ROOT / "benchmarks" / "baselines" / "adapter.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        code = module.main(["stub", "--output", str(output)], environ={"PATH": os.environ.get("PATH", ""), "ANTHROPIC_API_KEY": KEY})
        self.assertEqual(code, 0, output.read_text(encoding="utf-8") if output.exists() else "no report")
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertIsNone(report["public_benchmark_scores"])
        self.assertEqual(len(report["receipts"]), len(PINS) + 2)
        self.assertNotIn(KEY, output.read_text(encoding="utf-8"))


class CommandTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.runner = _load_runner()
        self.previous = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = KEY
        self.addCleanup(self._restore)

    def _restore(self):
        if self.previous is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self.previous

    def test_dry_run_lists_the_arms_and_does_not_fetch(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        missing = subprocess.run(
            [str(ROOT / "scripts" / "run-benchmarks.sh"), "--baselines", "--dry-run"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(missing.returncode, 3, missing.stderr)
        env["ANTHROPIC_API_KEY"] = KEY
        held = subprocess.run(
            [str(ROOT / "scripts" / "run-benchmarks.sh"), "--baselines", "--dry-run"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(held.returncode, 0, held.stderr)
        estimate = json.loads(held.stdout)
        self.assertIsNone(estimate["public_benchmark_scores"])
        self.assertIn("baselines", estimate["unpriced"])
        component = next(item for item in estimate["components"] if item["name"] == "baselines")
        self.assertEqual(component["arms"], ["plain-claude-code", "aic", *PINS])
        self.assertFalse(component["priced"])
        self.assertFalse((ROOT / "results").exists())

    def test_baselines_flag_passes_the_shared_model_without_the_key(self):
        seen = []

        def baseline(argv, environ=None):
            seen.append((list(argv), environ.get("ANTHROPIC_API_KEY") if environ else None))
            self.assertNotIn(KEY, argv)
            return 0

        code = self.runner.main(
            ["--baselines", "--dry-run"],
            client=lambda _body: (_ for _ in ()).throw(AssertionError("model")),
            aicbench_runner=lambda argv, environ=None: (_ for _ in ()).throw(AssertionError("aicbench")),
            baseline_runner=baseline,
            results_root=Path(self.temp.name),
        )
        self.assertEqual(code, 0)
        self.assertEqual(seen, [])
        code = self.runner.main(
            ["--baselines"],
            client=lambda _body: json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"}),
            aicbench_runner=lambda argv, environ=None: 0,
            baseline_runner=baseline,
            results_root=Path(self.temp.name),
            today=date(2026, 11, 8),
        )
        self.assertEqual(code, 0)
        self.assertEqual(seen[0][0][0], "live")
        self.assertEqual(seen[0][0][seen[0][0].index("--model") + 1], "claude-sonnet-5-5")
        self.assertIn("receipts/baselines.json", seen[0][0][seen[0][0].index("--output") + 1])
        self.assertEqual(seen[0][1], KEY)

    def test_missing_key_still_exits_before_a_model(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        code = self.runner.main(["--baselines"], baseline_runner=lambda argv, environ=None: (_ for _ in ()).throw(AssertionError("ran")))
        self.assertEqual(code, 3)

    def test_workflow_defaults_baselines_off(self):
        text = (ROOT / ".github" / "workflows" / "benchmarks.yml").read_text(encoding="utf-8")
        self.assertIn("baselines:", text)
        self.assertIn("default: false", text)
        self.assertIn('"$BENCH_BASELINES" = "true"', text)
        self.assertEqual(text.count("secrets.ANTHROPIC_API_KEY"), 1)
        self.assertNotIn("pull_request", text)

    def test_docs_name_the_command_and_claim_no_score(self):
        benchmarks = (ROOT / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("No public benchmark score is claimed.", benchmarks)
        self.assertIn("./scripts/run-benchmarks.sh --baselines", benchmarks)
        self.assertIn("python3 -m benchmarks.aicbench --baseline-stub", benchmarks)
        self.assertNotIn("%", benchmarks)
        self.assertIn("Rows: none.", roadmap)
        self.assertIn("| Date | Suite | Sample size | Model | Budget | Seed | Arm | Pass rate | Cost | Time | Raw results |", roadmap)
        self.assertIn("https://github.com/Boom-Vitt/aic/pull/31", roadmap)
        for arm_id in PINS:
            self.assertIn(f"`{arm_id}`", benchmarks)
            self.assertIn(PINS[arm_id][1], benchmarks)
        self.assertIn("Issue [#4](https://github.com/Boom-Vitt/aic/issues/4)", roadmap)


class ModeBitTests(unittest.TestCase):
    def test_stub_agent_stays_executable(self):
        path = ROOT / "benchmarks" / "aicbench" / "stub" / "agent.py"
        self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
