"""The pinned comparison selects a routing pack and does not call a model for a dry run."""
import hashlib
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

from benchmarks.routing.compare import _items, aic_system, message_body, shared_system, skill_documents
from benchmarks.routing.baseline import load_catalog
from benchmarks.routing.score import load_pack


def _load_runner():
    spec = importlib.util.spec_from_file_location("benchrun_script", ROOT / "scripts" / "benchmarks" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()
KEY = "present-for-test"
DAY = date(2026, 11, 7)


def fake_messages(body):
    return json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"})


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
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = runner.main(
                argv,
                client=kwargs.get("client", fake_messages),
                aicbench_runner=kwargs.get("aicbench_runner", lambda argv, environ=None: 0),
                harness_runner=kwargs.get("harness_runner"),
                today=kwargs.get("today", DAY),
                results_root=kwargs.get("results_root", self.results),
                revision_reader=kwargs.get("revision_reader"),
                compare_runner=kwargs.get("compare_runner"),
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_or_blank_key_exits_3_before_an_estimate(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        code, output, _err = self._run(["--dry-run"], client=lambda _body: (_ for _ in ()).throw(AssertionError("called")))
        self.assertEqual(code, 3)
        self.assertEqual(output, "")
        os.environ["ANTHROPIC_API_KEY"] = "   "
        code, output, _err = self._run(["--dry-run"])
        self.assertEqual(code, 3)
        self.assertEqual(output, "")

    def test_dry_run_defaults_to_the_dev_pack_and_writes_nothing(self):
        def explode(*_args, **_kwargs):
            raise AssertionError("dry-run called a model")

        code, output, err = self._run(["--dry-run"], client=explode, aicbench_runner=explode)
        self.assertEqual(code, 0, err)
        estimate = json.loads(output)
        settings = runner.load_settings(ROOT)
        pack_path = ROOT / settings["routing_packs"]["dev"]
        pack = load_pack(pack_path)
        labels = load_catalog(ROOT)
        documents = skill_documents(ROOT)
        systems = (shared_system(labels), aic_system(labels, documents))
        input_tokens = 0
        for system in systems:
            for item in _items(pack):
                body = message_body(
                    system=system,
                    user=item.user,
                    model=settings["model"],
                    temperature=float(settings["temperature"]),
                    max_tokens=settings["max_tokens"],
                )
                input_tokens += len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        output_tokens = len(_items(pack)) * 2 * settings["max_tokens"]
        millionths = input_tokens * settings["pricing"]["input_usd_per_million"]
        millionths += output_tokens * settings["pricing"]["output_usd_per_million"]
        ceiling = f"{millionths // 1_000_000}.{millionths % 1_000_000:06d}"
        self.assertEqual(estimate["routing_pack"], "dev")
        self.assertEqual(estimate["routing_pack_sha256"], hashlib.sha256(pack_path.read_bytes()).hexdigest())
        self.assertEqual(estimate["input_token_ceiling"], input_tokens)
        self.assertEqual(estimate["output_token_budget"], output_tokens)
        self.assertEqual(estimate["budget_cost_ceiling_usd"], ceiling)
        self.assertIn("aicbench", estimate["unpriced"])
        self.assertIsNone(estimate["public_benchmark_scores"])
        self.assertFalse((self.results / "results").exists())

    def test_heldout_pack_is_scored_from_the_release_file(self):
        seen = []

        def spy(argv, client=None, environ=None, clock=None):
            seen.append(list(argv))
            return runner.compare_main(argv, client=client, environ=environ, clock=clock)

        code, output, err = self._run(
            ["--routing-pack", "heldout-v2"],
            compare_runner=spy,
            aicbench_runner=lambda argv, environ=None: 0,
        )
        self.assertEqual(code, 0, err + output)
        pack_flag = seen[0][seen[0].index("--pack") + 1]
        pack_path = Path(pack_flag)
        self.assertEqual(pack_path, (ROOT / "benchmarks" / "routing" / "heldout-v2.json").resolve())
        digest = hashlib.sha256(pack_path.read_bytes()).hexdigest()
        estimate = json.loads(output)
        self.assertEqual(estimate["routing_pack"], "heldout-v2")
        self.assertEqual(estimate["routing_pack_sha256"], digest)
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        provenance = json.loads((self.results / "results" / f"2026-11-07-{sha}" / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["routing_pack"], "heldout-v2")
        self.assertEqual(provenance["routing_pack_path"], "benchmarks/routing/heldout-v2.json")
        self.assertEqual(provenance["routing_pack_sha256"], digest)

    def test_fake_client_records_the_dev_pack_digest_and_passes_pack_to_compare(self):
        seen = []

        def spy(argv, client=None, environ=None, clock=None):
            seen.append(list(argv))
            return runner.compare_main(argv, client=client, environ=environ, clock=clock)

        aicbench_calls = []

        def aicbench(argv, environ=None):
            aicbench_calls.append(list(argv))
            self.assertEqual(environ.get("ANTHROPIC_API_KEY"), KEY)
            self.assertNotIn(KEY, argv)
            return 0

        code, output, err = self._run([], compare_runner=spy, aicbench_runner=aicbench)
        self.assertEqual(code, 0, err + output)
        self.assertIn("--pack", seen[0])
        pack_path = Path(seen[0][seen[0].index("--pack") + 1])
        self.assertEqual(pack_path, (ROOT / "tests" / "fixtures" / "routing-scenarios.json").resolve())
        self.assertEqual(aicbench_calls[0][:4], ["--sandbox", "container", "--official", "--model"])
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        bundle = self.results / "results" / f"2026-11-07-{sha}"
        provenance = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["routing_pack"], "dev")
        self.assertEqual(provenance["routing_pack_path"], "tests/fixtures/routing-scenarios.json")
        self.assertEqual(provenance["routing_pack_sha256"], hashlib.sha256(pack_path.read_bytes()).hexdigest())
        self.assertTrue(provenance["completed"])
        self.assertIsNone(provenance["public_benchmark_scores"])
        self.assertEqual(provenance["git_sha"], sha)
        for path in bundle.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY, path.read_text(encoding="utf-8"))

    def test_shell_rejects_a_missing_key_and_dry_runs_heldout_v2(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        missing = subprocess.run(
            [str(ROOT / "scripts" / "run-benchmarks.sh"), "--dry-run"],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(missing.returncode, 3, missing.stderr)
        self.assertIn("ANTHROPIC_API_KEY", missing.stderr)
        env["ANTHROPIC_API_KEY"] = KEY
        heldout = subprocess.run(
            [str(ROOT / "scripts" / "run-benchmarks.sh"), "--routing-pack", "heldout-v2", "--dry-run"],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(heldout.returncode, 0, heldout.stderr)
        estimate = json.loads(heldout.stdout)
        pack_path = ROOT / "benchmarks" / "routing" / "heldout-v2.json"
        self.assertEqual(estimate["routing_pack"], "heldout-v2")
        self.assertEqual(estimate["routing_pack_sha256"], hashlib.sha256(pack_path.read_bytes()).hexdigest())
        self.assertFalse((ROOT / "results").exists())

    def test_workflow_is_manual_read_only_and_defaults_the_pack_to_dev(self):
        text = (ROOT / ".github" / "workflows" / "benchmarks.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request", text)
        self.assertNotIn("push:", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("actions: write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("bubblewrap", text)
        self.assertEqual(text.count("secrets.ANTHROPIC_API_KEY"), 1)
        self.assertIn("routing_pack:", text)
        self.assertIn("default: dev", text)
        self.assertIn("--routing-pack", text)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", text)
        self.assertIn("actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9", text)
        upload = text.split("Upload the results bundle", 1)[1]
        self.assertNotIn("ANTHROPIC_API_KEY", upload)

    def test_documented_command_calls_the_dev_pack_by_its_name(self):
        doc = (ROOT / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8")
        self.assertIn("No public benchmark score is claimed.", doc)
        self.assertIn("doc role `dev`", doc)
        self.assertIn("once per release", doc)
        self.assertNotIn("held-out requests in `tests/fixtures/routing-scenarios.json`", doc)
        self.assertNotIn("%", doc)


class SmokeSandboxTests(unittest.TestCase):
    def test_container_argv_hides_the_skill_from_the_plain_arm(self):
        scripts = str(ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.append(scripts)
        from aicbench.official import sandbox_argv

        probe = ROOT / "benchmarks" / "official"
        skill = ROOT / "skills" / "aic"
        plain = sandbox_argv(probe_dir=probe, skill_dir=None)
        treated = sandbox_argv(probe_dir=probe, skill_dir=skill)
        self.assertIn("--unshare-all", plain)
        self.assertIn("--clearenv", plain)
        self.assertNotIn("/opt/aic", plain)
        self.assertIn("/opt/aic", treated)
