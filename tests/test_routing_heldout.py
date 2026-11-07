"""heldout-v2 stays independent of the dev pack, and its bytes are version-locked.

The label set is the public catalog: six task categories, five families, and the
topologies documented with those families. Digests are the published pack version.
Replacing version 1's bytes without a new pack_version fails this test.
"""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.routing.compare import main as compare_main
from benchmarks.routing.score import ScoreError, load_pack, selected_pack_path


PACK_PATH = ROOT / "benchmarks" / "routing" / "heldout-v2.json"
ANSWERS_PATH = ROOT / "benchmarks" / "routing" / "heldout-v2-answers.json"
PACK_NAME = "benchmarks/routing/heldout-v2.json"
ANSWERS_NAME = "benchmarks/routing/heldout-v2-answers.json"
# Frozen digests. Add the next integer when the bytes change. Do not edit version 1.
FROZEN = {
    1: {
        PACK_NAME: "7cee89c4899c53268a59d98d04acd3bb64fff24eecd9e7777fc664e6be5fb3cf",
        ANSWERS_NAME: "3606c4c397ed015d038ce4ee729959dbb66e0a77faef2f120cf105537e9d76c9",
    }
}
ALLOWED = {
    "direct": {"solo"},
    "explore-build": {"parallel"},
    "coordinated-delivery": {"sequential", "parallel"},
    "independent-review": {"generator-evaluator"},
    "adaptive-controller": {"solo", "sequential", "parallel", "generator-evaluator"},
}
WORKFLOWS = {"answer", "research", "implementation", "debug", "review", "design"}
LOCK_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|$",
    re.MULTILINE,
)
LABEL_TOKEN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
DECIDING_FACT_CASES = (
    "h2-answer-faq-branches",
    "h2-impl-ordered-resume",
    "h2-debug-incident-resume",
    "h2-design-ordered-program",
    "h2-review-program-resume",
)


def label_tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in LABEL_TOKEN.finditer(text)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readme_lock() -> dict[int, dict[str, str]]:
    text = (ROOT / "benchmarks" / "routing" / "README.md").read_text(encoding="utf-8")
    found: dict[int, dict[str, str]] = {}
    for version, name, digest in LOCK_ROW.findall(text):
        found.setdefault(int(version), {})[name] = digest
    return found


class HeldoutPackTests(unittest.TestCase):
    def test_version_lock_rejects_a_byte_change_without_a_version_bump(self):
        pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        answers = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))
        version = pack["pack_version"]
        self.assertEqual(answers["pack_version"], version)
        self.assertIn(version, FROZEN)
        self.assertEqual(sha256(PACK_PATH), FROZEN[version][PACK_NAME])
        self.assertEqual(sha256(ANSWERS_PATH), FROZEN[version][ANSWERS_NAME])
        published = readme_lock()
        self.assertEqual(published[version], FROZEN[version])
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(FROZEN[version][PACK_NAME], root_readme)
        self.assertIn(FROZEN[version][ANSWERS_NAME], root_readme)
        mutated = PACK_PATH.read_bytes() + b"\n"
        self.assertNotEqual(hashlib.sha256(mutated).hexdigest(), FROZEN[version][PACK_NAME])

    def test_release_rule_is_documented_and_the_old_pack_role_is_dev(self):
        routing = (ROOT / "benchmarks" / "routing" / "README.md").read_text(encoding="utf-8")
        benchmarks = (ROOT / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for document in (routing, benchmarks, contributing, (ROOT / "README.md").read_text(encoding="utf-8")):
            self.assertIn("once per release", document)
            self.assertIn("tests/fixtures/routing-scenarios.json", document)
        self.assertIn("doc role is `dev`", routing)
        self.assertIn("doc role `dev`", benchmarks)
        self.assertNotIn("## Held-out routing pack", benchmarks)
        self.assertNotIn("%", benchmarks)

    def test_requests_do_not_contain_their_gold_label_tokens(self):
        pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        answers = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))
        leaks: list[str] = []
        for case in pack["cases"]:
            present = label_tokens(case["request"])
            for field in ("expected_workflow", "expected_template", "expected_topology"):
                if case[field] in present:
                    leaks.append(f"{case['id']} {field}={case[field]}")
        project = pack["project_case"]
        project_tokens = label_tokens(project["request"])
        for stage in project["stages"]:
            for field in ("expected_workflow", "expected_template", "expected_topology"):
                if stage[field] in project_tokens:
                    leaks.append(f"{project['id']} {stage['id']} {field}={stage[field]}")
        self.assertEqual(leaks, [])
        ordered = next(case["request"] for case in pack["cases"] if case["id"] == "h2-research-ordered-memos")
        self.assertNotIn("parallel", label_tokens(ordered))
        by_id = {item["id"]: item for item in answers["cases"]}
        for ident in DECIDING_FACT_CASES:
            self.assertIn("Deciding fact:", by_id[ident]["rationale"])

    def test_cases_use_the_public_catalog_and_answers_justify_every_label(self):
        pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        answers = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(pack["schema_version"], 3)
        self.assertGreaterEqual(len(pack["cases"]), 40)
        self.assertNotIn("rationale", PACK_PATH.read_text(encoding="utf-8"))
        loaded = load_pack(PACK_PATH)
        self.assertEqual(len(loaded.cases), len(pack["cases"]))
        by_id = {item["id"]: item for item in answers["cases"]}
        self.assertEqual(set(by_id), {item["id"] for item in pack["cases"]})
        workflows: dict[str, int] = {}
        templates: dict[str, int] = {}
        topologies: dict[str, int] = {}
        hard = 0
        for case in pack["cases"]:
            answer = by_id[case["id"]]
            self.assertEqual(answer["expected_workflow"], case["expected_workflow"])
            self.assertEqual(answer["expected_template"], case["expected_template"])
            self.assertEqual(answer["expected_topology"], case["expected_topology"])
            self.assertIn(case["expected_template"], answer["rationale"])
            self.assertGreaterEqual(len(answer["rationale"]), 40)
            self.assertIn(case["expected_workflow"], WORKFLOWS)
            self.assertIn(case["expected_topology"], ALLOWED[case["expected_template"]])
            workflows[case["expected_workflow"]] = workflows.get(case["expected_workflow"], 0) + 1
            templates[case["expected_template"]] = templates.get(case["expected_template"], 0) + 1
            topologies[case["expected_topology"]] = topologies.get(case["expected_topology"], 0) + 1
            hard += int(answer["hard_negative"] is True)
        self.assertEqual(set(workflows), WORKFLOWS)
        self.assertLessEqual(max(workflows.values()) - min(workflows.values()), 2)
        self.assertEqual(set(templates), set(ALLOWED))
        self.assertLessEqual(max(templates.values()) - min(templates.values()), 2)
        self.assertEqual(set(topologies), {"solo", "sequential", "parallel", "generator-evaluator"})
        self.assertGreaterEqual(min(topologies.values()), 8)
        self.assertGreaterEqual(hard, 8)
        project = pack["project_case"]
        answered = {stage["id"]: stage for stage in answers["project_case"]["stages"]}
        self.assertEqual(answers["project_case"]["id"], project["id"])
        self.assertGreaterEqual(len(answers["project_case"]["rationale"]), 40)
        self.assertEqual(set(answered), {stage["id"] for stage in project["stages"]})
        for stage in project["stages"]:
            answer = answered[stage["id"]]
            self.assertEqual(answer["expected_workflow"], stage["expected_workflow"])
            self.assertEqual(answer["expected_template"], stage["expected_template"])
            self.assertEqual(answer["expected_topology"], stage["expected_topology"])
            self.assertIn(stage["expected_topology"], ALLOWED[stage["expected_template"]])
            self.assertIn(stage["expected_template"], answer["rationale"])

    def test_score_and_compare_accept_pack(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        rows = [
            {
                "id": case["id"],
                "workflow": case["expected_workflow"],
                "template": case["expected_template"],
                "topology": case["expected_topology"],
            }
            for case in pack["cases"]
        ]
        with tempfile.TemporaryDirectory(dir=ROOT / ".work") as temp:
            base = Path(temp)
            decisions = base / "decisions.jsonl"
            decisions.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            scored = subprocess.run(
                [sys.executable, "-B", "-m", "benchmarks.routing.score", "--decisions", str(decisions), "--pack", str(PACK_PATH)],
                cwd=ROOT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(scored.returncode, 0, scored.stderr)
            report = json.loads(scored.stdout)
            self.assertTrue(report["scenarios_file"].endswith("heldout-v2.json"))
            self.assertEqual(report["metrics"]["exact"]["accuracy"]["k"], len(pack["cases"]))
            self.assertEqual(report["metrics"]["exact"]["accuracy"]["n"], len(pack["cases"]))
            self.assertNotIn("rationale", scored.stdout)
            helped = subprocess.run(
                [sys.executable, "-B", "-m", "benchmarks.routing.score", "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(helped.returncode, 0, helped.stderr)
            self.assertIn("--pack", helped.stdout)
            both = subprocess.run(
                [
                    sys.executable, "-B", "-m", "benchmarks.routing.score",
                    "--decisions", str(decisions), "--pack", str(PACK_PATH), "--scenarios", str(PACK_PATH),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(both.returncode, 2, both.stderr)
            self.assertEqual(both.stdout, "")
            compare_help = subprocess.run(
                [sys.executable, "-B", "-m", "benchmarks.routing.compare", "--help"],
                cwd=ROOT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "ANTHROPIC_API_KEY": ""},
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(compare_help.returncode, 0, compare_help.stderr)
            self.assertIn("--pack", compare_help.stdout)
            tiny = base / "tiny.json"
            tiny.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "cases": [
                            {
                                "id": "only",
                                "request": "Explain one pasted sentence.",
                                "expected_workflow": "answer",
                                "expected_template": "direct",
                                "expected_topology": "solo",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output = base / "comparison"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = compare_main(
                    ["--model", "test-model", "--output", str(output), "--pack", str(tiny)],
                    client=lambda _body: json.dumps({"workflow": "answer", "template": "direct", "topology": "solo"}),
                    environ={"ANTHROPIC_API_KEY": "test-key"},
                    clock=lambda: datetime(2026, 11, 7, tzinfo=timezone.utc),
                )
            self.assertEqual(code, 0, stdout.getvalue())
            receipt = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["scenarios_file"].endswith("tiny.json"))
            self.assertEqual(receipt["model_calls"], 2)
            self.assertEqual(receipt["arms"]["aic"]["score"]["metrics"]["exact"]["accuracy"]["n"], 1)
        with self.assertRaises(ScoreError):
            selected_pack_path(PACK_PATH, PACK_PATH)


if __name__ == "__main__":
    unittest.main()
