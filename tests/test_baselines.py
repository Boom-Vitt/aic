"""Key-free baseline adapters. No network fetch and no model call."""
from datetime import date
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
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
    execute_arms,
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
        "installed",
    ),
    "ecc": (
        "affaan-m/ECC",
        "d2ef2680594f9a17526a6e1a2e18b3d242c5d17b",
        "326146379f01bb137c0a5d3c54770c1aa31076705c8b88a7f6b26a460f6221b2",
        "Copyright (c) 2026 Affaan Mustafa",
        "installed",
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
        "installed",
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
            self.assertIn(entry["install_status"], {"documented", "unverified-install"})
            self.assertTrue(entry["install_commands"])
            self.assertEqual(entry["official_comparison"], entry["install_status"] == "documented")
        self.assertEqual(arms["superpowers"]["install_status"], "unverified-install")
        self.assertEqual(arms["superpowers"]["install_commands"][0][:3], ["/plugin", "marketplace", "add"])
        self.assertEqual(arms["ecc"]["install_commands"][0][:4], ["npx", "--yes", "ecc-universal@2.2.3", "setup"])
        self.assertEqual(arms["gstack"]["install_commands"], [["./setup"]])
        self.assertEqual(arms["aic"]["install_commands"], [["claude", "--plugin-dir", "{checkout}"]])
        self.assertEqual(arms["agent-skills"]["install_commands"], [["claude", "--plugin-dir", "{checkout}"]])
        self.assertEqual(arms["planning-with-files"]["install_commands"], [["claude", "--plugin-dir", "{checkout}"]])
        self.assertEqual(arms["plain-claude-code"]["install_status"], "none")
        self.assertEqual(arms["plain-claude-code"]["install_commands"], [])
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
        entry = next(item for item in load_registry()["arms"] if item["id"] == "agent-skills")
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
            self.assertEqual(manifest["name"], "agent-skills")
            self.assertTrue(manifest["stub"])

    def test_plain_and_aic_commands_share_model_budget_and_seed_inputs(self):
        mount = Path("/tmp/aic-baseline-shipped-plugin")
        plain = agent_argv(
            "claude", prompt="Task id: example\n", model="claude-sonnet-5-5", max_turns=30, mount="none", mount_path=None,
        )
        treated = agent_argv(
            "claude",
            prompt="Task id: example\n",
            model="claude-sonnet-5-5",
            max_turns=30,
            mount="plugin-dir",
            mount_path=mount,
        )
        installed = agent_argv(
            "claude",
            prompt="Task id: example\n",
            model="claude-sonnet-5-5",
            max_turns=30,
            mount="installed",
            mount_path=mount,
        )
        tools = "Read,Edit,Write,Bash,AskUserQuestion"
        self.assertEqual(plain[plain.index("--model") + 1], treated[treated.index("--model") + 1])
        self.assertEqual(plain[plain.index("--allowedTools") + 1], tools)
        self.assertEqual(treated[treated.index("--allowedTools") + 1], tools)
        self.assertEqual(installed[installed.index("--allowedTools") + 1], tools)
        self.assertEqual(plain[plain.index("--max-turns") + 1], "30")
        self.assertNotIn("--plugin-dir", plain)
        self.assertNotIn("--add-dir", plain)
        self.assertNotIn("--plugin-dir", installed)
        self.assertNotIn("--add-dir", installed)
        self.assertEqual(treated[treated.index("--plugin-dir") + 1], str(mount))
        self.assertNotIn(str(ROOT), treated)
        self.assertNotIn(KEY, plain + treated + installed)


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
        self.assertEqual(report["sandbox"], "none")
        self.assertFalse(report["official"])
        self.assertIsNone(report["network"])
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
            self.assertEqual(receipt["sandbox"], "none")
            self.assertFalse(receipt["sandboxed"])
            self.assertEqual(receipt["install_status"], entry["install_status"])
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
        self.assertEqual(seen[0][0][seen[0][0].index("--sandbox") + 1], "container")
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
        self.assertIn("Official baseline results refuse sandbox", benchmarks)
        self.assertIn("unverified-install", benchmarks)
        self.assertIn("api.anthropic.com:443", benchmarks)
        self.assertIn("registry.npmjs.org:443", benchmarks)

    def test_run_benchmarks_sh_model_flag_reaches_the_live_cli(self):
        import benchmarks.baselines.adapter as adapter

        seen = []

        def baseline(argv, environ=None):
            seen.append(list(argv))
            code = adapter.main(list(argv), environ={"PATH": (environ or {}).get("PATH", "")})
            self.assertEqual(code, 3)
            return 0

        code = self.runner.main(
            ["--baselines"],
            compare_runner=lambda *_args, **_kwargs: 0,
            aicbench_runner=lambda *_args, **_kwargs: 0,
            baseline_runner=baseline,
            results_root=Path(self.temp.name),
            today=date(2026, 11, 8),
        )
        self.assertEqual(code, 0, seen)
        output = Path(seen[0][seen[0].index("--output") + 1])
        self.assertEqual(seen[0], self.runner.baseline_live_argv({"model": "claude-sonnet-5-5"}, output))
        direct = subprocess.run(
            [sys.executable, "-m", "benchmarks.baselines", *self.runner.baseline_live_argv(
                {"model": "claude-sonnet-5-5"}, Path(self.temp.name) / "live.json",
            )],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(direct.returncode, 3, direct.stderr)
        self.assertIn("ANTHROPIC_API_KEY", direct.stderr)
        self.assertNotIn("unrecognized arguments", direct.stderr)
        refused = subprocess.run(
            [sys.executable, "-m", "benchmarks.baselines", "live", "--sandbox", "none", "--model", "claude-sonnet-5-5"],
            cwd=ROOT,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": str(ROOT),
                "ANTHROPIC_API_KEY": KEY,
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("official baseline results refuse sandbox none", refused.stderr)
        self.assertFalse((Path(self.temp.name) / "live.json").exists())


class MountClosureTests(unittest.TestCase):
    def test_no_arm_mount_reaches_oracles_references_or_answers(self):
        from benchmarks.aicbench.grading import outside_repository_temp
        from benchmarks.aicbench.sandbox import container_command
        from benchmarks.baselines.adapter import NETWORK, assert_mount_closed, stand_in_mount

        binary = Path("/usr/bin/true")
        if not binary.is_file():
            binary = Path("/bin/true")
        self.assertEqual(NETWORK["agent"]["allow"], ["api.anthropic.com:443"])
        self.assertFalse(NETWORK["install"]["secrets"])
        self.assertEqual(NETWORK["agent"]["secrets"], ["ANTHROPIC_API_KEY"])
        for host in ("github.com:443", "codeload.github.com:443", "registry.npmjs.org:443", "bun.sh:443"):
            self.assertIn(host, NETWORK["install"]["allow"])
        self.assertNotIn("github.com:443", NETWORK["agent"]["allow"])
        self.assertNotIn("registry.npmjs.org:443", NETWORK["agent"]["allow"])
        forbidden = [
            (ROOT / "benchmarks" / "aicbench" / "tasks").resolve(),
            (ROOT / "benchmarks" / "routing" / "heldout-v2.json").resolve(),
            (ROOT / "benchmarks" / "routing" / "heldout-v2-answers.json").resolve(),
        ]
        with tempfile.TemporaryDirectory(prefix="aic-mount-", dir=outside_repository_temp()) as temporary:
            base = Path(temporary)
            for entry in load_registry()["arms"]:
                home = base / entry["id"] / "home"
                config = base / entry["id"] / "config"
                checkout = base / entry["id"] / "checkout"
                workspace = base / entry["id"] / "workspace"
                home.mkdir(parents=True)
                config.mkdir()
                workspace.mkdir()
                mount, path = stand_in_mount(entry, checkout, home)
                mounts = [home, workspace]
                if path is not None:
                    mounts.append(path)
                if checkout.exists():
                    mounts.append(checkout)
                for candidate in mounts:
                    assert_mount_closed(candidate)
                    for child in candidate.rglob("*"):
                        resolved = child.resolve()
                        for banned in forbidden:
                            self.assertFalse(
                                resolved == banned or banned in resolved.parents,
                                f"{entry['id']} mount reaches {banned}",
                            )
                        self.assertNotEqual(resolved, ROOT.resolve())
                        self.assertNotIn(ROOT.resolve(), resolved.parents)
                command = container_command(
                    [str(binary), "--version"],
                    workspace=workspace,
                    skill_root=path if mount == "plugin-dir" else None,
                    home=home,
                    config=config,
                    binary=binary,
                    repo=ROOT,
                )
                blob = "\n".join(str(item) for item in command)
                self.assertNotIn("--unshare-net", command)
                sandboxed = container_command(
                    [str(binary), "--version"],
                    workspace=workspace,
                    skill_root=path if mount == "plugin-dir" else None,
                    home=home,
                    config=config,
                    binary=binary,
                    repo=ROOT,
                    unshare_net=True,
                )
                self.assertIn("--unshare-net", sandboxed)
                self.assertNotIn(str(ROOT.resolve()), blob)
                self.assertNotIn("heldout-v2-answers.json", blob)
                self.assertNotIn(str(forbidden[0]), blob)
                if entry["id"] == "aic":
                    self.assertEqual(mount, "plugin-dir")
                    self.assertNotEqual(path.resolve(), ROOT.resolve())
                    names = {item.relative_to(path).as_posix() for item in path.rglob("*") if item.is_file()}
                    self.assertIn("skills/aic/SKILL.md", names)
                    self.assertIn(".claude-plugin/plugin.json", names)
                    self.assertNotIn("benchmarks/routing/heldout-v2-answers.json", names)
                    self.assertFalse(any(name.startswith("benchmarks/") or "/oracle/" in f"/{name}/" for name in names))
                    self.assertFalse(any(name.split("/")[-2:] == ["reference", "orders.py"] for name in names))

    @unittest.skipUnless(shutil.which("bwrap"), "bubblewrap is not installed")
    def test_container_hides_the_repository_and_can_init_git(self):
        from benchmarks.aicbench.grading import outside_repository_temp
        from benchmarks.baselines.adapter import _child_env, _require_bwrap, _run_in_container
        from benchmarks.baselines.proxy import PhaseProxies

        class _Task:
            reference = ROOT
            remove = []

        parent = {"PATH": os.environ.get("PATH", "")}
        bwrap = _require_bwrap(parent)
        oracle = next((ROOT / "benchmarks" / "aicbench" / "tasks").rglob("test_oracle.py"))
        answers = ROOT / "benchmarks" / "routing" / "heldout-v2-answers.json"
        host_home = Path.home()
        with tempfile.TemporaryDirectory(prefix="aic-bwrap-", dir=outside_repository_temp()) as temporary:
            base = Path(temporary)
            home = base / "home"
            config = base / "config"
            scratch = base / "scratch"
            workspace = base / "workspace"
            for path in (home, config, scratch, workspace):
                path.mkdir()

            def fake_connect(_host, _port):
                left, right = socket.socketpair()
                right.close()
                return left

            proxies = PhaseProxies(base / "egress", fake_connect)
            self.addCleanup(proxies.close)
            common = dict(
                home=home, config=config, skill_root=None, parent=parent, timeout=30,
                task=_Task(), seed=0, bwrap=bwrap, proxies=proxies,
            )
            init = _run_in_container(
                ["git", "init", str(scratch / "repo")],
                workspace=scratch,
                key=KEY,
                phase="install",
                **common,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertTrue((scratch / "repo" / ".git").is_dir())
            self.assertNotIn(KEY, init.args)
            connect_probe = (
                "connect() {\n"
                "  host=$1\n"
                "  exec 3<>/dev/tcp/127.0.0.1/3128\n"
                "  printf 'CONNECT %s:443 HTTP/1.1\\r\\nHost: %s:443\\r\\n\\r\\n' \"$host\" \"$host\" >&3\n"
                "  IFS= read -r status <&3\n"
                "  exec 3<&-\n"
                "  printf '%s\\n' \"$status\"\n"
                "}\n"
            )
            install_probe = scratch / "install-probe.sh"
            install_probe.write_text(
                "#!/bin/bash\n"
                + connect_probe
                + "if test -n \"$ANTHROPIC_API_KEY\"; then echo key-yes; else echo key-no; fi\n"
                + "connect github.com\nconnect example.com\nconnect api.anthropic.com\n",
                encoding="utf-8",
            )
            installed = _run_in_container(
                ["/bin/bash", str(install_probe)],
                workspace=scratch,
                key=KEY,
                phase="install",
                **common,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            install_lines = [line.strip() for line in installed.stdout.splitlines()]
            self.assertEqual(install_lines[0], "key-no")
            self.assertIn("200", install_lines[1])
            self.assertIn("403", install_lines[2])
            self.assertIn("403", install_lines[3])
            self.assertNotIn(KEY, installed.args)
            probe = workspace / "probe.sh"
            probe.write_text(
                "#!/bin/bash\n"
                f"if test -f {shlex.quote(str(oracle))}; then echo oracle-yes; else echo oracle-no; fi\n"
                f"if test -f {shlex.quote(str(answers))}; then echo answers-yes; else echo answers-no; fi\n"
                f"if test -e {shlex.quote(str(ROOT))}; then echo repo-yes; else echo repo-no; fi\n"
                f"if test -e {shlex.quote(str(host_home))}; then echo home-yes; else echo home-no; fi\n"
                "printf '%s\\n' \"$HOME\"\n"
                "if test -n \"$ANTHROPIC_API_KEY\"; then echo key-yes; else echo key-no; fi\n"
                + connect_probe
                + "connect example.com\nconnect github.com\nconnect api.anthropic.com\n",
                encoding="utf-8",
            )
            seen = _run_in_container(
                ["/bin/bash", str(probe)],
                workspace=workspace,
                key=KEY,
                phase="agent",
                **common,
            )
            self.assertEqual(seen.returncode, 0, seen.stderr)
            lines = [line.strip() for line in seen.stdout.splitlines()]
            self.assertEqual(lines[:4], ["oracle-no", "answers-no", "repo-no", "home-no"])
            self.assertEqual(lines[4], str(home))
            self.assertEqual(lines[5], "key-yes")
            self.assertIn("403", lines[6])
            self.assertIn("403", lines[7])
            self.assertIn("200", lines[8])
            self.assertNotIn(KEY, seen.args)


class EgressProxyTests(unittest.TestCase):
    def test_proxy_allow_list_is_offline_and_install_env_has_no_key(self):
        from benchmarks.baselines.adapter import AdapterError, _child_env, _run_in_container
        from benchmarks.baselines.proxy import AGENT_ALLOW, INSTALL_ALLOW, EgressProxy, permitted

        self.assertTrue(permitted("api.anthropic.com", 443, AGENT_ALLOW))
        self.assertFalse(permitted("example.com", 443, AGENT_ALLOW))
        self.assertFalse(permitted("github.com", 443, AGENT_ALLOW))
        self.assertFalse(permitted("api.anthropic.com", 80, AGENT_ALLOW))
        self.assertFalse(permitted("1.1.1.1", 443, AGENT_ALLOW))
        self.assertTrue(permitted("github.com", 443, INSTALL_ALLOW))
        self.assertTrue(permitted("codeload.github.com", 443, INSTALL_ALLOW))
        self.assertTrue(permitted("registry.npmjs.org", 443, INSTALL_ALLOW))
        self.assertTrue(permitted("bun.sh", 443, INSTALL_ALLOW))
        self.assertFalse(permitted("example.com", 443, INSTALL_ALLOW))
        self.assertFalse(permitted("api.anthropic.com", 443, INSTALL_ALLOW))

        class _Task:
            reference = ROOT
            remove = []

        install_env = _child_env(
            {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": KEY},
            task=_Task(), seed=0, home=Path("/tmp/aic-egress-home"), stub=False, key=KEY, phase="install",
        )
        self.assertNotIn("ANTHROPIC_API_KEY", install_env)
        self.assertNotIn(KEY, "\n".join(install_env.values()))
        self.assertEqual(install_env["HTTPS_PROXY"], "http://127.0.0.1:3128")
        agent_env = _child_env(
            {"PATH": "/usr/bin"},
            task=_Task(), seed=0, home=Path("/tmp/aic-egress-home"), stub=False, key=KEY, phase="agent",
        )
        self.assertEqual(agent_env["ANTHROPIC_API_KEY"], KEY)

        dialed = []

        def fake_connect(host, port):
            dialed.append((host, port))
            left, right = socket.socketpair()
            right.close()
            return left

        with tempfile.TemporaryDirectory(prefix="aic-proxy-") as temporary:
            proxy = EgressProxy(AGENT_ALLOW, fake_connect)
            socket_path = proxy.start(Path(temporary))
            self.addCleanup(proxy.close)

            def status(host):
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.connect(str(socket_path))
                client.sendall(
                    f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode("ascii")
                )
                data = b""
                while b"\r\n" not in data:
                    chunk = client.recv(200)
                    if not chunk:
                        break
                    data += chunk
                client.close()
                return data.split(b"\r\n", 1)[0].decode("ascii")

            self.assertIn("403", status("example.com"))
            self.assertIn("403", status("github.com"))
            self.assertIn("200", status("api.anthropic.com"))
            self.assertEqual(dialed, [("api.anthropic.com", 443)])

        with self.assertRaises(AdapterError) as caught:
            _run_in_container(
                ["/bin/true"],
                workspace=Path("/tmp"),
                home=Path("/tmp"),
                config=Path("/tmp"),
                skill_root=None,
                parent={"PATH": "/usr/bin"},
                timeout=5,
                task=_Task(),
                seed=0,
                key=KEY,
                bwrap="bwrap",
                phase="agent",
                proxies=None,
            )
        self.assertIn("egress proxy", str(caught.exception))

    @unittest.skipUnless(shutil.which("bwrap") and Path("/usr/bin/python3").exists(), "bubblewrap or system python is not installed")
    def test_execute_arms_runs_install_then_agent_through_the_proxy(self):
        import benchmarks.baselines.adapter as adapter
        import benchmarks.baselines.proxy as proxy
        from benchmarks.aicbench.grading import outside_repository_temp

        registry = load_registry()
        phases = []
        agent_commands = []

        def fake_dial(host, port):
            left, right = socket.socketpair()
            right.close()
            return left

        def simulate_install(argv):
            if "rev-parse" in argv:
                dest = Path(argv[argv.index("-C") + 1])
                commit = next(
                    item["commit"] for item in registry["arms"] if item.get("commit") and item["id"] in dest.parts
                )
                return subprocess.CompletedProcess(argv, 0, commit + "\n", "")
            if "init" in argv:
                dest = Path(argv[-1])
                dest.mkdir(parents=True, exist_ok=True)
                if dest.name == "gstack":
                    setup = dest / "setup"
                    setup.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                    setup.chmod(0o755)
            return subprocess.CompletedProcess(argv, 0, "", "")

        real_run = adapter._run_in_container

        def wrapped(argv, **kwargs):
            phase = kwargs["phase"]
            arm_id = kwargs["workspace"].parent.name
            phases.append((arm_id, phase))
            self.assertIsNotNone(kwargs["proxies"])
            if phase == "install":
                install_env = adapter._child_env(
                    {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": KEY},
                    task=task, seed=0, home=kwargs["home"], stub=False, key=KEY, phase="install",
                )
                self.assertNotIn("ANTHROPIC_API_KEY", install_env)
                self.assertNotIn(KEY, "\n".join(install_env.values()))
                return simulate_install(argv)
            completed = real_run(argv, **kwargs)
            agent_commands.append(completed.args)
            return completed

        with tempfile.TemporaryDirectory(prefix="aic-claude-", dir=outside_repository_temp()) as temporary:
            claude = Path(temporary) / "claude"
            claude.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$HTTPS_PROXY\"\n"
                "if test -n \"$ANTHROPIC_API_KEY\"; then echo key-yes; else echo key-no; fi\n"
                "printf '%s\\n' '{\"total_cost_usd\":0}'\n",
                encoding="utf-8",
            )
            claude.chmod(0o755)
            task = adapter._task(adapter.PLUMBING_TASK)
            original_license = adapter.assert_license
            original_dial = proxy._dial
            adapter.assert_license = lambda entry, dest: None
            adapter._run_in_container = wrapped
            proxy._dial = fake_dial
            try:
                report = execute_arms(
                    registry,
                    task,
                    binary=str(claude),
                    parent_env={"PATH": os.environ.get("PATH", ""), "ANTHROPIC_API_KEY": KEY},
                    materialize=stand_in_mount,
                    kind="baseline-live",
                    invokes_model=True,
                    key=KEY,
                    sandbox="container",
                )
            finally:
                adapter.assert_license = original_license
                adapter._run_in_container = real_run
                proxy._dial = original_dial

        official = [item["id"] for item in registry["arms"] if item["official_comparison"]]
        self.assertEqual([item["arm"] for item in report["receipts"]], [item["id"] for item in registry["arms"]])
        for arm_id in official:
            arm_phases = [phase for seen_arm, phase in phases if seen_arm == arm_id]
            self.assertEqual(arm_phases[-1], "agent", arm_phases)
            if any(item["id"] == arm_id and item["kind"] == "git" for item in registry["arms"]):
                self.assertEqual(arm_phases[0], "install", arm_phases)
                self.assertLess(arm_phases.index("install"), arm_phases.index("agent"))
            else:
                self.assertEqual(arm_phases, ["agent"])
        self.assertNotIn("superpowers", [arm for arm, _phase in phases])
        self.assertGreaterEqual(len(agent_commands), len(official))
        for command in agent_commands:
            flat = [str(item) for item in command]
            self.assertIn("--unshare-net", flat)
            self.assertTrue(any(item.endswith("proxy.sock") for item in flat))
            self.assertNotIn(KEY, flat)
        self.assertEqual(report["sandbox"], "container")
        self.assertEqual(report["network"]["agent"]["allow"], ["api.anthropic.com:443"])
        self.assertFalse(report["network"]["install"]["secrets"])
        self.assertIn("registry.npmjs.org:443", report["network"]["install"]["allow"])
        self.assertNotIn("github.com:443", report["network"]["agent"]["allow"])
        for receipt in report["receipts"]:
            self.assertEqual(receipt["sandbox"], "container")
            self.assertEqual(receipt["network"]["agent"]["allow"], ["api.anthropic.com:443"])
            self.assertFalse(receipt["network"]["install"]["secrets"])
            self.assertIsNone(receipt["public_benchmark_scores"])
            if receipt["excluded"]:
                self.assertEqual(receipt["arm"], "superpowers")
                continue
            self.assertIsNotNone(receipt["exit_code"])
            self.assertTrue(receipt["sandboxed"])
            self.assertFalse(receipt["invalid"])
            self.assertNotIn("egress proxy", receipt["harness_error"] or "")


class ModeBitTests(unittest.TestCase):
    def test_stub_agent_stays_executable(self):
        path = ROOT / "benchmarks" / "aicbench" / "stub" / "agent.py"
        self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
