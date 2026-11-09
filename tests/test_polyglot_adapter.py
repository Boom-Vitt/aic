"""Aider polyglot fetches pinned Exercism tracks and does not vendor them."""
import importlib.util
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.baselines.adapter import AdapterError
from benchmarks.polyglot.adapter import (
    COPYRIGHT,
    DECOY_MARKER,
    FIXTURE_SLUG,
    LICENSE_SHA,
    MISSING_KEY,
    fetch_track,
    load_pins,
    main,
    planned_exercises,
    prepare_workspace,
    score_exercise,
    write_fixture,
)


LICENSE_SHA_OBSERVED = "e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df"
COMMITS = {
    "cpp": "9d47dff5f64f9244699b82cfcdf68ed72edd289f",
    "go": "54da18da1bf36b9c03cdad48d592fb28101ac08f",
    "java": "be2d006c30c50e0154231dd987d5a3b5526c0427",
    "javascript": "43dd0939ec1e1bdb3a69852b0512928b9c4ef996",
    "python": "479f11b44b02337b0413e805b948491c2179615a",
    "rust": "523fff27328e9b85085cd7eb7bd6ac36af730433",
}
DATES = {
    "cpp": "2026-11-08",
    "go": "2026-11-08",
    "java": "2026-11-08",
    "javascript": "2026-11-08",
    "python": "2026-11-07",
    "rust": "2026-11-08",
}


class PolyglotPinTests(unittest.TestCase):
    def test_reviewed_tracks_are_mit_and_the_unlicensed_mirror_is_excluded(self):
        pins = load_pins()
        self.assertEqual(pins["checked"], "2026-11-09")
        self.assertFalse(pins["vendored"])
        self.assertIsNone(pins["public_benchmark_scores"])
        self.assertEqual(pins["max_exercises"], 1)
        self.assertEqual(LICENSE_SHA, LICENSE_SHA_OBSERVED)
        mirror, aider = pins["sources"]
        self.assertEqual(mirror["commit"], "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f")
        self.assertEqual(mirror["commit_date"], "2024-12-22")
        self.assertIsNone(mirror["license_spdx"])
        self.assertIsNone(mirror["license_path"])
        self.assertFalse(mirror["included"])
        self.assertIn("No root license file", mirror["reason"])
        self.assertEqual(aider["license_spdx"], "Apache-2.0")
        self.assertEqual(aider["commit"], "5dc9490bb35f9729ef2c95d00a19ccd30c26339c")
        self.assertEqual(aider["commit_date"], "2026-05-22")
        self.assertFalse(aider["included"])
        self.assertEqual([track["id"] for track in pins["tracks"]], list(COMMITS))
        names = []
        for track in pins["tracks"]:
            self.assertTrue(track["included"])
            self.assertEqual(track["license_spdx"], "MIT")
            self.assertEqual(track["license_path"], "LICENSE")
            self.assertEqual(track["license_sha256"], LICENSE_SHA_OBSERVED)
            self.assertEqual(track["copyright_notice"], COPYRIGHT)
            self.assertEqual(track["commit"], COMMITS[track["id"]])
            self.assertEqual(track["commit_date"], DATES[track["id"]])
            self.assertEqual(track["repository"], f"exercism/{track['id']}")
            names.extend((track["id"], slug) for slug in track["exercises"])
        self.assertEqual(len(names), 225)
        self.assertEqual(len(set(names)), 225)
        selected = planned_exercises(pins)
        self.assertEqual([(track["id"], slug) for track, slug in selected], [("cpp", "all-your-base")])

    def test_docs_record_the_same_commits_and_do_not_claim_a_score(self):
        benchmarks = (ROOT / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertNotIn("%", benchmarks)
        self.assertIn(LICENSE_SHA_OBSERVED, benchmarks)
        self.assertIn("7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f", benchmarks)
        self.assertIn("No root license file", benchmarks)
        for track, commit in COMMITS.items():
            self.assertIn(commit, benchmarks)
            self.assertIn(f"exercism/{track}", benchmarks)
        self.assertIn("2026-11-09", benchmarks)
        self.assertNotIn("Leave Aider polyglot unwired until", roadmap)
        self.assertIn("heldout-v2", roadmap)
        self.assertIn("| Date | Suite |", roadmap)
        history = roadmap.split("## Score history", 1)[1]
        self.assertIn("Rows: none.", history)
        self.assertNotIn("all-your-base", history)


class PolyglotFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aic-polyglot-test-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_fetch_checks_the_license_and_leaves_the_repository_untouched(self):
        source = self.root / "source"
        track = write_fixture(source)
        dest = self.root / "checkout"
        fetch_track(track, dest, FIXTURE_SLUG, url=str(source))
        self.assertEqual(
            subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip(),
            track["commit"],
        )
        self.assertFalse((dest / "exercises" / "practice" / "decoy").exists())
        workspace = self.root / "work"
        prepare_workspace(dest, FIXTURE_SLUG, workspace)
        self.assertTrue((workspace / "sum_digits_test.py").is_file())
        self.assertFalse((workspace / ".meta").exists())
        self.assertNotIn(DECOY_MARKER, "\n".join(path.read_text(encoding="utf-8") for path in workspace.rglob("*") if path.is_file()))
        failed = score_exercise(workspace, track["test_commands"])
        self.assertFalse(failed["passed"])
        (workspace / "sum_digits.py").write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
        passed = score_exercise(workspace, track["test_commands"])
        self.assertTrue(passed["passed"])
        self.assertGreaterEqual(passed["wall_time_seconds"], 0)
        self.assertFalse(any(ROOT.rglob("sum_digits.py")))

    def test_a_mismatched_license_is_not_kept(self):
        source = self.root / "source"
        track = write_fixture(source)
        track["license_sha256"] = "0" * 64
        dest = self.root / "bad"
        with self.assertRaises(AdapterError):
            fetch_track(track, dest, FIXTURE_SLUG, url=str(source))
        self.assertFalse(dest.exists())

    def test_a_checkout_inside_the_repository_is_refused(self):
        source = self.root / "source"
        track = write_fixture(source)
        dest = ROOT / ".work" / "polyglot-should-not-exist"
        with self.assertRaises(AdapterError):
            fetch_track(track, dest, FIXTURE_SLUG, url=str(source))
        self.assertFalse(dest.exists())


class PolyglotStubTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.previous = os.environ.pop("ANTHROPIC_API_KEY", None)
        self.addCleanup(self._restore)

    def _restore(self):
        if self.previous is not None:
            os.environ["ANTHROPIC_API_KEY"] = self.previous

    def test_stub_fetches_scores_and_wires_the_sandbox_without_a_model(self):
        output = Path(self.temp.name) / "stub.json"
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.polyglot", "stub", "--output", str(output)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertTrue(report["fetched"])
        self.assertFalse(report["upstream_fetched"])
        self.assertFalse(report["invokes_model"])
        self.assertFalse(report["official"])
        self.assertIsNone(report["public_benchmark_scores"])
        self.assertEqual(report["pass_rate"], "6/6")
        self.assertEqual(report["passed_cases"], 6)
        self.assertEqual(report["attempted_cases"], 6)
        self.assertEqual(report["cost_usd"], "0")
        self.assertGreaterEqual(report["wall_time_seconds"], 0)
        self.assertEqual(report["budget"], {"max_turns": 30, "timeout_sec": 600, "max_usd": 0.35})
        self.assertEqual(report["seed"], 0)
        self.assertFalse(report["seed_sent_to_provider"])
        self.assertEqual(report["sandbox"], "none")
        self.assertEqual(report["excluded_arms"], ["superpowers"])
        self.assertEqual(report["upstream_selection"], [{
            "commit": COMMITS["cpp"],
            "exercise": "all-your-base",
            "track": "cpp",
        }])
        wiring = report["sandbox_wiring"]
        self.assertTrue(wiring["install_unshare_net"])
        self.assertTrue(wiring["agent_unshare_net"])
        self.assertTrue(wiring["score_unshare_net"])
        self.assertTrue(wiring["agent_uses_forwarder"])
        self.assertTrue(wiring["agent_env_has_key"])
        self.assertFalse(wiring["install_env_has_key"])
        self.assertFalse(wiring["agent_command_has_key"])
        self.assertFalse(wiring["repository_mounted"])
        self.assertFalse(wiring["seed_sent_to_provider"])
        self.assertEqual(wiring["network"]["agent"]["allow"], ["api.anthropic.com:443"])
        self.assertIs(wiring["network"]["install"]["secrets"], False)
        treated = [item["arm"] for item in report["arms"] if item["aic_treatment"] is True]
        self.assertEqual(treated, ["aic"])
        for arm in report["arms"]:
            self.assertEqual(arm["cost_usd"], "0")
            self.assertTrue(arm["passed"])
            self.assertEqual(arm["pass_rate"], "1/1")
            self.assertFalse(arm["invokes_model"])
            self.assertIsNone(arm["public_benchmark_scores"])
            self.assertFalse(arm["seed_sent_to_provider"])
        blob = output.read_text(encoding="utf-8")
        self.assertNotIn("heldout-v2", blob)
        self.assertNotIn(DECOY_MARKER, blob)
        self.assertFalse(any(ROOT.rglob("sum_digits.py")))


class PolyglotLiveTests(unittest.TestCase):
    def test_live_without_a_key_exits_3_before_fetch(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        output = Path("/tmp") / "aic-polyglot-live-should-not-exist.json"
        if output.exists():
            output.unlink()
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(["live", "--output", str(output)], environ=env)
        self.assertEqual(code, 3)
        self.assertIn("ANTHROPIC_API_KEY", stderr.getvalue())
        self.assertFalse(output.exists())

    def test_live_without_bubblewrap_does_not_fetch(self):
        env = {"PATH": "/nonexistent", "ANTHROPIC_API_KEY": "polyglot-test-key", "HOME": "/tmp"}
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(["live"], environ=env)
        self.assertEqual(code, 1)
        self.assertIn("bubblewrap", stderr.getvalue())
        self.assertNotIn(MISSING_KEY, stderr.getvalue())


class PolyglotEstimateTests(unittest.TestCase):
    def test_dry_run_lists_polyglot_without_calling_it(self):
        spec = importlib.util.spec_from_file_location("polyglot_benchrun", ROOT / "scripts" / "benchmarks" / "run.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "polyglot-test-key"
        self.addCleanup(self._restore, previous)
        called = []

        def explode(argv=None, environ=None):
            called.append(argv)
            raise AssertionError("dry-run fetched polyglot")

        stdout = StringIO()
        with redirect_stdout(stdout), redirect_stderr(StringIO()):
            code = module.main(
                ["--dry-run", "--aider-polyglot"],
                client=lambda _body: (_ for _ in ()).throw(AssertionError("model")),
                aicbench_runner=lambda argv, environ=None: 0,
                today=date(2026, 11, 9),
                results_root=Path(tempfile.mkdtemp(dir="/tmp")),
                polyglot_runner=explode,
            )
        self.assertEqual(code, 0)
        self.assertEqual(called, [])
        estimate = json.loads(stdout.getvalue())
        self.assertIn("aider-polyglot", estimate["unpriced"])
        self.assertIsNone(estimate["public_benchmark_scores"])
        self.assertEqual(estimate["shared_max_usd"], "0.35")

    def _restore(self, previous):
        if previous is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = previous
