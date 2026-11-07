"""Paired routing comparison with a mocked Messages client. No network."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.routing.compare import (  # noqa: E402
    API_HOST,
    API_PATH,
    Settings,
    compare_pack,
    main,
    mcnemar_exact,
    message_body,
    post_messages,
)
from benchmarks.routing.score import ScoreError, load_pack, score_decisions  # noqa: E402


KEY = "sentinel-key-do-not-leak"
WHEN = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def tiny_pack(path: Path) -> None:
    body = {
        "schema_version": 3,
        "cases": [
            {
                "id": f"case-{index}",
                "request": f"Request text {index}.",
                "expected_workflow": "answer",
                "expected_template": "direct",
                "expected_topology": "solo",
            }
            for index in range(4)
        ],
    }
    path.write_text(json.dumps(body), encoding="utf-8")


def settings(**overrides: object) -> Settings:
    values = {
        "model": "test-model",
        "temperature": 0.0,
        "max_tokens": 1024,
        "seed": 0,
        "timeout": 60.0,
        "date": "2026-11-07",
    }
    values.update(overrides)
    return Settings(**values)


class CompareTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_prompt_math_for_mcnemar_uses_exact_rationals(self):
        self.assertIsNone(mcnemar_exact(0, 0)["p"])
        self.assertIsNone(mcnemar_exact(0, 0)["p_numerator"])
        tied = mcnemar_exact(5, 5)
        self.assertEqual((tied["p_numerator"], tied["p_denominator"]), (1, 1))
        skewed = mcnemar_exact(0, 10)
        self.assertEqual((skewed["p_numerator"], skewed["p_denominator"]), (1, 512))
        self.assertEqual(skewed["n_discordant"], 10)

    def test_missing_key_exits_3_and_does_not_call_the_client(self):
        called = {"count": 0}

        def client(_body: dict) -> str:
            called["count"] += 1
            raise AssertionError("client was called without a key")

        output = self.base / "out"
        for label, env in (
            ("unset", {}),
            ("empty", {"ANTHROPIC_API_KEY": ""}),
            ("blank", {"ANTHROPIC_API_KEY": " \n\t"}),
        ):
            with self.subTest(label=label):
                with redirect_stderr(io.StringIO()):
                    code = main(
                        ["--model", "test-model", "--output", str(output)],
                        client=client,
                        environ=env,
                        clock=lambda: WHEN,
                    )
                self.assertEqual(code, 3)
                self.assertEqual(called["count"], 0)
                self.assertFalse(output.exists())

    def test_help_does_not_require_a_key_or_a_client(self):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.routing.compare", "--help"],
            cwd=ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "ANTHROPIC_API_KEY": ""},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--model", result.stdout)
        self.assertIn("--temperature", result.stdout)
        self.assertNotIn(KEY, result.stdout + result.stderr)

    def test_mocked_arms_share_settings_and_only_the_aic_arm_gets_the_skill(self):
        scenarios = self.base / "pack.json"
        tiny_pack(scenarios)
        pack = load_pack(scenarios)
        seen: list[dict] = []

        def client(body: dict) -> str:
            seen.append(json.loads(json.dumps(body)))
            user = body["messages"][0]["content"]
            ident = user.split('id must be "', 1)[1].split('"', 1)[0]
            aic = "skills/aic/SKILL.md" in body["system"]
            if aic or ident == "case-0":
                payload = {"workflow": "answer", "template": "direct", "topology": "solo"}
            else:
                payload = {"workflow": "research", "template": "direct", "topology": "solo"}
            return json.dumps({"id": ident, **payload})

        report, files = compare_pack(pack, settings=settings(temperature=0.2, max_tokens=320, seed=7), client=client, transport="injected")
        self.assertEqual(len(seen), 8)
        self.assertTrue(report["invokes_model"])
        self.assertFalse(report["calls_api"])
        self.assertEqual(report["transport"], "injected")
        self.assertEqual(report["model"], "test-model")
        self.assertEqual(report["date"], "2026-11-07")
        self.assertEqual(report["temperature"], 0.2)
        self.assertEqual(report["max_tokens"], 320)
        self.assertEqual(report["seed"], 7)
        self.assertFalse(report["seed_sent"])
        self.assertEqual(report["model_calls"], 8)
        self.assertNotIn(KEY, json.dumps(report))
        self.assertNotIn("expected_workflow", json.dumps([body["messages"] for body in seen]))
        no_skill_users = []
        aic_users = []
        for body in seen:
            self.assertEqual(set(body), {"max_tokens", "messages", "model", "system", "temperature"})
            self.assertEqual(body["model"], "test-model")
            self.assertEqual(body["temperature"], 0.2)
            self.assertEqual(body["max_tokens"], 320)
            self.assertNotIn("seed", body)
            self.assertNotIn(KEY, json.dumps(body))
            user = body["messages"][0]["content"]
            if "skills/aic/SKILL.md" in body["system"]:
                aic_users.append(user)
                self.assertIn("# skills/aic/SKILL.md", body["system"])
                self.assertIn("Task classification and recommendation contract", body["system"])
                self.assertIn("skills/aic/references/routing.md", body["system"])
            else:
                no_skill_users.append(user)
                self.assertNotIn("skills/aic/SKILL.md", body["system"])
                self.assertNotIn("Task classification and recommendation contract", body["system"])
        self.assertEqual(no_skill_users, aic_users)
        self.assertEqual(report["context"]["no-skill"], ["closed-catalog"])
        self.assertIn("skills/aic/SKILL.md", report["context"]["aic"])
        self.assertIn("skills/aic/references/workflows.md", report["context"]["aic"])
        self.assertNotIn("skills/aic/references/research-updates/2026-11-06.md", report["context"]["aic"])
        paired = report["paired"]["exact"]
        self.assertEqual(paired["both_correct"], 1)
        self.assertEqual(paired["baseline_only_correct"], 0)
        self.assertEqual(paired["aic_only_correct"], 3)
        self.assertEqual(paired["difference"]["k_delta"], 3)
        self.assertEqual(paired["difference"]["n"], 4)
        self.assertTrue(abs(paired["difference"]["rate_delta"] - 0.75) < 1e-12)
        self.assertEqual(
            (paired["mcnemar_exact"]["p_numerator"], paired["mcnemar_exact"]["p_denominator"]),
            (1, 4),
        )
        self.assertEqual(report["paired"]["template"]["mcnemar_exact"]["p"], None)
        no_skill_rows = [json.loads(line) for line in files["no-skill.jsonl"].splitlines()]
        rescored = score_decisions(pack, no_skill_rows, source="decisions")
        self.assertEqual(report["arms"]["no-skill"]["score"]["metrics"], rescored["metrics"])
        self.assertFalse(report["arms"]["no-skill"]["skill_loaded"])
        self.assertTrue(report["arms"]["aic"]["skill_loaded"])

    def test_unparseable_text_is_an_abstention_and_a_tied_arm_has_no_probability(self):
        scenarios = self.base / "pack.json"
        tiny_pack(scenarios)
        pack = load_pack(scenarios)

        def client(body: dict) -> str:
            if "skills/aic/SKILL.md" in body["system"]:
                return "not json at all"
            return json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"})

        report, _files = compare_pack(pack, settings=settings(), client=client, transport="injected")
        self.assertEqual(report["arms"]["aic"]["score"]["metrics"]["exact"]["accuracy"]["k"], 0)
        self.assertEqual(report["arms"]["no-skill"]["score"]["metrics"]["exact"]["accuracy"]["k"], 4)
        self.assertEqual(report["paired"]["exact"]["difference"]["k_delta"], -4)
        self.assertEqual(report["paired"]["exact"]["mcnemar_exact"]["n_discordant"], 4)
        tied = compare_pack(
            pack,
            settings=settings(),
            client=lambda _body: json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"}),
            transport="injected",
        )[0]
        self.assertEqual(tied["paired"]["exact"]["difference"]["k_delta"], 0)
        self.assertIsNone(tied["paired"]["exact"]["mcnemar_exact"]["p"])

    def test_cli_writes_both_decision_files_without_opening_a_socket(self):
        scenarios = self.base / "pack.json"
        tiny_pack(scenarios)
        output = self.base / "comparison"
        calls = {"count": 0}

        def client(body: dict) -> str:
            calls["count"] += 1
            self.assertNotIn(KEY, json.dumps(body))
            return json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"})

        class Blocked(socket.socket):
            def __init__(self, *args, **kwargs):
                raise RuntimeError("compare opened a socket")

        original = socket.socket
        socket.socket = Blocked
        stdout = io.StringIO()
        try:
            with redirect_stdout(stdout):
                code = main(
                    ["--model", "test-model", "--output", str(output), "--scenarios", str(scenarios), "--temperature", "0", "--seed", "3"],
                    client=client,
                    environ={"ANTHROPIC_API_KEY": KEY, "PYTHONDONTWRITEBYTECODE": "1"},
                    clock=lambda: WHEN,
                )
        finally:
            socket.socket = original
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertEqual(calls["count"], 8)
        report = json.loads((output / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["invokes_model"], True)
        self.assertEqual(report["transport"], "injected")
        self.assertEqual(report["seed"], 3)
        self.assertFalse(report["seed_sent"])
        self.assertEqual(report["date"], "2026-11-07")
        self.assertNotIn(KEY, (output / "report.json").read_text(encoding="utf-8"))
        self.assertNotIn(KEY, (output / "no-skill.jsonl").read_text(encoding="utf-8"))
        self.assertNotIn(KEY, (output / "aic.jsonl").read_text(encoding="utf-8"))
        self.assertTrue((output / "no-skill.jsonl").is_file())
        self.assertTrue((output / "aic.jsonl").is_file())

    def test_https_client_posts_only_to_anthropic_and_keeps_the_key_out_of_the_body(self):
        seen = {}

        class Response:
            status = 200

            def read(self, _limit: int) -> bytes:
                return json.dumps(
                    {"content": [{"type": "text", "text": "{\"workflow\":\"answer\",\"template\":\"direct\",\"topology\":\"solo\"}"}]}
                ).encode("utf-8")

        class Connection:
            def __init__(self, host: str, timeout: float):
                seen["host"] = host
                seen["timeout"] = timeout

            def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
                seen["calls"] = seen.get("calls", 0) + 1
                seen["method"] = method
                seen["path"] = path
                seen["body"] = body
                seen["headers"] = headers

            def getresponse(self):
                return Response()

            def close(self):
                seen["closed"] = True

        body = message_body(system="catalog", user="Request text.", model="test-model", temperature=0.0, max_tokens=128)
        payload = post_messages(body, key=KEY, timeout=5.0, connection_factory=Connection)
        self.assertEqual(seen["host"], API_HOST)
        self.assertEqual(seen["path"], API_PATH)
        self.assertEqual(seen["calls"], 1)
        self.assertEqual(seen["headers"]["x-api-key"], KEY)
        self.assertEqual(seen["headers"]["anthropic-version"], "2023-06-01")
        self.assertNotIn(KEY.encode("utf-8"), seen["body"])
        self.assertNotIn(b"seed", seen["body"])
        decoded = json.loads(seen["body"].decode("utf-8"))
        self.assertEqual(decoded["model"], "test-model")
        self.assertEqual(decoded["temperature"], 0.0)
        self.assertEqual(decoded["max_tokens"], 128)
        self.assertEqual(payload["content"][0]["type"], "text")
        self.assertTrue(seen["closed"])

        class Redirected(Response):
            status = 302

            def read(self, _limit: int) -> bytes:
                return f"go to https://evil.example/{KEY}".encode("utf-8")

        class RedirectConnection(Connection):
            def getresponse(self):
                return Redirected()

        with self.assertRaises(Exception) as raised:
            post_messages(body, key=KEY, timeout=5.0, connection_factory=RedirectConnection)
        self.assertIn("HTTP 302", str(raised.exception))
        self.assertNotIn(KEY, str(raised.exception))
        self.assertEqual(seen["calls"], 2)

    def test_real_fixture_project_prompt_withholds_gold_and_matches_across_arms(self):
        pack = load_pack(ROOT / "tests" / "fixtures" / "routing-scenarios.json")
        seen: list[dict] = []

        def client(body: dict) -> str:
            seen.append(body)
            user = body["messages"][0]["content"]
            if "stages" in user:
                return json.dumps({"stages": []})
            return json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"})

        report, _files = compare_pack(pack, settings=settings(), client=client, transport="injected")
        self.assertEqual(report["model_calls"], 56)
        users: dict[str, list[str]] = {"no-skill": [], "aic": []}
        for index, body in enumerate(seen):
            arm = "aic" if "skills/aic/SKILL.md" in body["system"] else "no-skill"
            users[arm].append(body["messages"][0]["content"])
            self.assertEqual(body["model"], "test-model")
            self.assertNotIn("expected_workflow", body["messages"][0]["content"])
            self.assertNotIn("required_milestones", body["messages"][0]["content"])
        self.assertEqual(users["no-skill"], users["aic"])
        project_prompt = users["no-skill"][-1]
        self.assertIn("shared-contract", project_prompt)
        self.assertNotIn("independent discovery", project_prompt.split("Request:\n", 1)[0])
        self.assertEqual(index, 55)

    def test_api_failure_writes_no_directory(self):
        scenarios = self.base / "pack.json"
        tiny_pack(scenarios)
        output = self.base / "partial"

        def client(_body: dict) -> str:
            raise ScoreError("Anthropic API returned HTTP 500.", 1)

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(
                ["--model", "test-model", "--output", str(output), "--scenarios", str(scenarios)],
                client=client,
                environ={"ANTHROPIC_API_KEY": KEY},
                clock=lambda: WHEN,
            )
        self.assertEqual(code, 1)
        self.assertIn("HTTP 500", stderr.getvalue())
        self.assertNotIn(KEY, stderr.getvalue())
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
