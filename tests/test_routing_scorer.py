"""Consumer checks for the offline routing-pack scorer and no-skill baseline template."""
import json
import math
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "tests" / "fixtures" / "routing-scenarios.json"
KEY = "sentinel-key-do-not-leak"
Z95 = statistics.NormalDist().inv_cdf(0.975)


def wilson(successes: int, trials: int) -> tuple[float, float]:
    """Independent Wilson formula used only to lock the scorer's interval."""
    phat = successes / trials
    z2 = Z95 * Z95
    denom = 1.0 + z2 / trials
    center = phat + z2 / (2.0 * trials)
    margin = Z95 * math.sqrt(phat * (1.0 - phat) / trials + z2 / (4.0 * trials * trials))
    low = max(0.0, (center - margin) / denom)
    high = min(1.0, (center + margin) / denom)
    return low, high


def pack() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def gold_rows(data: dict | None = None) -> list[dict]:
    body = pack() if data is None else data
    rows = [
        {
            "id": case["id"],
            "workflow": case["expected_workflow"],
            "template": case["expected_template"],
            "topology": case["expected_topology"],
        }
        for case in body["cases"]
    ]
    project = body["project_case"]
    rows.append(
        {
            "id": project["id"],
            "stages": [
                {
                    "id": stage["id"],
                    "workflow": stage["expected_workflow"],
                    "template": stage["expected_template"],
                    "topology": stage["expected_topology"],
                }
                for stage in project["stages"]
            ],
            "milestones": list(project["required_milestones"]),
            "invariants": list(project["required_invariants"]),
        }
    )
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


class ScorerCliTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def run_score(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        child = dict(os.environ)
        child.pop("ANTHROPIC_API_KEY", None)
        child["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            child.update(env)
        return subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.routing.score", *args],
            cwd=ROOT,
            env=child,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def run_baseline(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        child = dict(os.environ)
        child.pop("ANTHROPIC_API_KEY", None)
        child["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            child.update(env)
        return subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.routing.baseline", *args],
            cwd=ROOT,
            env=child,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def report_for(self, rows: list[dict], scenarios: Path | None = None) -> dict:
        decisions = self.base / "decisions.jsonl"
        write_jsonl(decisions, rows)
        args = ["--decisions", str(decisions)]
        if scenarios is not None:
            args.extend(["--scenarios", str(scenarios)])
        result = self.run_score(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(KEY, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assert_binomial(self, summary: dict, successes: int, trials: int) -> None:
        self.assertEqual(summary["k"], successes)
        self.assertEqual(summary["n"], trials)
        if trials == 0:
            self.assertIsNone(summary["rate"])
            self.assertIsNone(summary["wilson95"])
            return
        self.assertTrue(math.isclose(summary["rate"], successes / trials))
        low, high = wilson(successes, trials)
        self.assertTrue(math.isclose(summary["wilson95"]["low"], low, abs_tol=1e-12))
        self.assertTrue(math.isclose(summary["wilson95"]["high"], high, abs_tol=1e-12))
        self.assertTrue(math.isclose(summary["wilson95"]["z"], Z95))
        self.assertEqual(summary["wilson95"]["confidence"], 0.95)
        self.assertGreaterEqual(summary["wilson95"]["low"], 0.0)
        self.assertLessEqual(summary["wilson95"]["high"], 1.0)

    def test_help_and_scoring_do_not_require_a_model_key(self):
        helped = self.run_score("--help")
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertIn("--decisions", helped.stdout)
        self.assertIn("--from-router", helped.stdout)
        missing = self.run_score()
        self.assertEqual(missing.returncode, 2)
        self.assertNotIn("Traceback", missing.stderr)

    def test_gold_file_matches_every_flat_case_and_the_project_case(self):
        data = pack()
        report = self.report_for(gold_rows(data))
        self.assertEqual(report["invokes_model"], False)
        self.assertEqual(report["source"], "decisions")
        self.assertEqual([row["id"] for row in report["cases"]], [case["id"] for case in data["cases"]])
        self.assertEqual(len(report["cases"]), 27)
        self.assertTrue(all(row["correct"]["exact"] for row in report["cases"]))
        self.assertNotIn("previously valid date", result_text := json.dumps(report))
        self.assertNotIn("read-only change-summary CLI", result_text)
        for field in ("exact", "workflow", "template", "topology"):
            metrics = report["metrics"][field]
            self.assert_binomial(metrics["accuracy"], 27, 27)
            self.assert_binomial(metrics["precision"], 27, 27)
            self.assert_binomial(metrics["recall"], 27, 27)
            self.assertTrue(math.isclose(metrics["accuracy"]["wilson95"]["low"], 0.8754449702581331, abs_tol=1e-12))
            self.assertEqual(metrics["accuracy"]["wilson95"]["high"], 1.0)
        project = report["project_case"]
        self.assertTrue(project["present"])
        self.assertEqual(len(project["stages"]), 6)
        self.assertTrue(all(stage["correct"]["exact"] for stage in project["stages"]))
        self.assert_binomial(project["metrics"]["exact"]["accuracy"], 6, 6)
        self.assertTrue(project["milestones"]["correct"])
        self.assertTrue(project["invariants"]["correct"])
        self.assertEqual(project["milestones"]["missing"], [])
        self.assertEqual(project["invariants"]["extra"], [])
        again = self.report_for(gold_rows(data))
        self.assertEqual(again, report)

    def test_one_wrong_topology_changes_only_that_field_and_exact_match(self):
        rows = gold_rows()
        target = rows[0]["id"]
        rows[0]["topology"] = "parallel" if rows[0]["topology"] != "parallel" else "solo"
        report = self.report_for(rows)
        first = report["cases"][0]
        self.assertEqual(first["id"], target)
        self.assertFalse(first["correct"]["exact"])
        self.assertFalse(first["correct"]["topology"])
        self.assertTrue(first["correct"]["workflow"])
        self.assertTrue(first["correct"]["template"])
        self.assert_binomial(report["metrics"]["exact"]["accuracy"], 26, 27)
        self.assert_binomial(report["metrics"]["topology"]["accuracy"], 26, 27)
        self.assert_binomial(report["metrics"]["workflow"]["accuracy"], 27, 27)
        self.assertTrue(math.isclose(report["metrics"]["exact"]["accuracy"]["wilson95"]["low"], 0.8171653406642416, abs_tol=1e-12))
        self.assertTrue(math.isclose(report["metrics"]["exact"]["accuracy"]["wilson95"]["high"], 0.993431854019215, abs_tol=1e-12))
        self.assert_binomial(report["project_case"]["metrics"]["exact"]["accuracy"], 6, 6)

    def test_a_missing_case_counts_against_accuracy_and_recall_but_not_precision(self):
        rows = [row for row in gold_rows() if row["id"] != "coupled-bug"]
        report = self.report_for(rows)
        missing = next(row for row in report["cases"] if row["id"] == "coupled-bug")
        self.assertFalse(missing["correct"]["exact"])
        self.assertIsNone(missing["predicted"]["workflow"])
        self.assert_binomial(report["metrics"]["exact"]["accuracy"], 26, 27)
        self.assert_binomial(report["metrics"]["exact"]["recall"], 26, 27)
        self.assert_binomial(report["metrics"]["exact"]["precision"], 26, 26)
        self.assertNotEqual(report["metrics"]["exact"]["precision"]["n"], report["metrics"]["exact"]["accuracy"]["n"])

    def test_abstaining_on_one_field_is_not_a_prediction_for_that_field(self):
        rows = gold_rows()
        rows[4]["workflow"] = None
        report = self.report_for(rows)
        self.assertIsNone(report["cases"][4]["predicted"]["workflow"])
        self.assertFalse(report["cases"][4]["correct"]["workflow"])
        self.assertTrue(report["cases"][4]["correct"]["template"])
        self.assert_binomial(report["metrics"]["workflow"]["accuracy"], 26, 27)
        self.assert_binomial(report["metrics"]["workflow"]["precision"], 26, 26)
        self.assert_binomial(report["metrics"]["template"]["accuracy"], 27, 27)
        self.assert_binomial(report["metrics"]["exact"]["precision"], 26, 26)

    def test_empty_decisions_do_not_invent_a_precision(self):
        report = self.report_for([])
        self.assert_binomial(report["metrics"]["exact"]["accuracy"], 0, 27)
        self.assert_binomial(report["metrics"]["exact"]["recall"], 0, 27)
        self.assert_binomial(report["metrics"]["exact"]["precision"], 0, 0)
        self.assertFalse(report["project_case"]["present"])
        self.assert_binomial(report["project_case"]["metrics"]["exact"]["accuracy"], 0, 6)
        self.assertFalse(report["project_case"]["milestones"]["correct"])
        self.assertGreater(len(report["project_case"]["milestones"]["missing"]), 0)

    def test_zero_trial_wilson_interval_is_null_and_known_points_stay_fixed(self):
        from benchmarks.routing.score import binomial_summary

        empty = binomial_summary(0, 0)
        self.assertIsNone(empty["rate"])
        self.assertIsNone(empty["wilson95"])
        zero = binomial_summary(0, 10)
        three = binomial_summary(3, 10)
        full = binomial_summary(10, 10)
        self.assertEqual(zero["wilson95"]["low"], 0.0)
        self.assertTrue(math.isclose(zero["wilson95"]["high"], 0.27753279986288915, abs_tol=1e-12))
        self.assertTrue(math.isclose(three["wilson95"]["low"], 0.10779126740630104, abs_tol=1e-12))
        self.assertTrue(math.isclose(three["wilson95"]["high"], 0.6032218525388545, abs_tol=1e-12))
        self.assertTrue(math.isclose(full["wilson95"]["low"], 0.7224672001371109, abs_tol=1e-12))
        self.assertEqual(full["wilson95"]["high"], 1.0)
        with self.assertRaises(Exception):
            binomial_summary(True, 1)  # type: ignore[arg-type]
        with self.assertRaises(Exception):
            binomial_summary(2, 1)

    def test_nested_harness_objects_score_when_the_labels_agree(self):
        rows = gold_rows()
        first = rows[0]
        rows[0] = {
            "id": first["id"],
            "recommendation": {
                "workflow": first["workflow"],
                "template": first["template"],
                "topology": first["topology"],
                "schema_version": 3,
            },
        }
        rows[1] = {
            "id": rows[1]["id"],
            "structured_output": {
                "workflow": rows[1]["workflow"],
                "template": rows[1]["template"],
                "topology": rows[1]["topology"],
            },
        }
        report = self.report_for(rows)
        self.assertTrue(report["cases"][0]["correct"]["exact"])
        self.assertTrue(report["cases"][1]["correct"]["exact"])
        self.assert_binomial(report["metrics"]["exact"]["accuracy"], 27, 27)

    def test_bad_decision_files_are_refused_without_a_score(self):
        scenarios = ["--scenarios", str(FIXTURE)]
        duplicate = gold_rows()
        duplicate.append(dict(duplicate[0]))
        conflict = gold_rows()
        conflict[0] = {
            "id": conflict[0]["id"],
            "workflow": conflict[0]["workflow"],
            "template": conflict[0]["template"],
            "topology": conflict[0]["topology"],
            "recommendation": {
                "workflow": "answer",
                "template": conflict[0]["template"],
                "topology": conflict[0]["topology"],
            },
        }
        unknown = gold_rows()
        unknown.append({"id": "not-in-the-pack", "workflow": "answer", "template": "direct", "topology": "solo"})
        cases = {
            "duplicate": (duplicate, 2, "duplicate"),
            "conflict": (conflict, 2, "conflicting"),
            "unknown": (unknown, 2, "unknown"),
        }
        for name, (rows, code, fragment) in cases.items():
            with self.subTest(name=name):
                path = self.base / f"{name}.jsonl"
                write_jsonl(path, rows)
                result = self.run_score("--decisions", str(path), *scenarios)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn(fragment, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(result.stdout, "")
        broken = self.base / "broken.jsonl"
        broken.write_text("{not json}\n", encoding="utf-8")
        result = self.run_score("--decisions", str(broken), *scenarios)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        array = self.base / "array.jsonl"
        array.write_text("[]\n", encoding="utf-8")
        result = self.run_score("--decisions", str(array), *scenarios)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_symlink_and_overwrite_are_refused(self):
        decisions = self.base / "decisions.jsonl"
        write_jsonl(decisions, gold_rows())
        secret = "private-decision-body"
        real = self.base / "real.jsonl"
        real.write_text(secret + "\n", encoding="utf-8")
        link = self.base / "linked.jsonl"
        link.symlink_to(real)
        result = self.run_score("--decisions", str(link))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        output = self.base / "report.json"
        output.write_text("keep\n", encoding="utf-8")
        result = self.run_score("--decisions", str(decisions), "--output", str(output))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep\n")
        self.assertEqual(result.stdout, "")

    def test_custom_pack_locks_a_published_wilson_point_through_the_cli(self):
        scenarios = {
            "schema_version": 3,
            "cases": [
                {
                    "id": f"case-{index}",
                    "request": f"request {index}",
                    "expected_workflow": "answer",
                    "expected_template": "direct",
                    "expected_topology": "solo",
                }
                for index in range(10)
            ],
        }
        path = self.base / "ten.json"
        path.write_text(json.dumps(scenarios), encoding="utf-8")
        rows = [
            {"id": f"case-{index}", "workflow": "research", "template": "direct", "topology": "solo"}
            for index in range(10)
        ]
        report = self.report_for(rows, scenarios=path)
        summary = report["metrics"]["workflow"]["accuracy"]
        self.assert_binomial(summary, 0, 10)
        self.assertEqual(summary["wilson95"]["low"], 0.0)
        self.assertTrue(math.isclose(summary["wilson95"]["high"], 0.27753279986288915, abs_tol=1e-12))
        self.assert_binomial(report["metrics"]["template"]["accuracy"], 10, 10)

    def test_project_stage_and_invariant_misses_stay_out_of_the_flat_denominator(self):
        rows = gold_rows()
        project = rows[-1]
        project["stages"][0]["workflow"] = "answer"
        project["milestones"] = project["milestones"][:-1]
        project["invariants"] = [*project["invariants"], "unrequested extra invariant"]
        report = self.report_for(rows)
        self.assert_binomial(report["metrics"]["exact"]["accuracy"], 27, 27)
        self.assertFalse(report["project_case"]["stages"][0]["correct"]["workflow"])
        self.assert_binomial(report["project_case"]["metrics"]["workflow"]["accuracy"], 5, 6)
        self.assertFalse(report["project_case"]["milestones"]["correct"])
        self.assertFalse(report["project_case"]["invariants"]["correct"])
        self.assertGreater(len(report["project_case"]["milestones"]["missing"]), 0)
        self.assertEqual(report["project_case"]["invariants"]["extra"], ["unrequested extra invariant"])

    def test_router_flag_does_not_infer_labels(self):
        from benchmarks.routing.score import decisions_from_router, load_pack, load_router

        self.assertIsNone(load_router())
        result = self.run_score("--from-router")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("does not ship a deterministic task router", result.stderr)
        self.assertNotIn("rate", result.stdout)
        self.assertEqual(result.stdout, "")
        seen: list[dict] = []

        def route(scenario: dict) -> dict:
            seen.append(dict(scenario))
            self.assertEqual(set(scenario), {"id", "request"})
            return {"workflow": "answer", "template": "direct", "topology": "solo"}

        produced = decisions_from_router(load_pack(FIXTURE), route)
        self.assertEqual(len(produced), 28)
        self.assertTrue(all("expected_workflow" not in row for row in produced))
        self.assertTrue(all(set(item) == {"id", "request"} for item in seen))
        self.assertTrue(all("expected_workflow" not in item for item in seen))

    def test_missing_or_blank_key_exits_3_and_writes_no_baseline_pack(self):
        output = self.base / "prompts.jsonl"
        output.write_text("keep\n", encoding="utf-8")
        for label, key in (("unset", None), ("empty", ""), ("blank", " \n\t")):
            with self.subTest(label=label):
                env = {} if key is None else {"ANTHROPIC_API_KEY": key}
                result = self.run_baseline("--output", str(output), env=env)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("ANTHROPIC_API_KEY is unset or blank.", result.stderr)
                self.assertIn("no prompts were written", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(output.read_text(encoding="utf-8"), "keep\n")

    def test_baseline_help_works_without_a_key(self):
        result = self.run_baseline("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--output", result.stdout)
        self.assertNotIn(KEY, result.stdout + result.stderr)

    def test_baseline_with_a_key_writes_withheld_prompts_and_does_not_call_out(self):
        output = self.base / "prompts.jsonl"
        code = textwrap.dedent(
            """
            import os
            import runpy
            import socket
            import sys

            class Blocked(socket.socket):
                def __init__(self, *args, **kwargs):
                    raise RuntimeError("baseline opened a socket")

            socket.socket = Blocked
            sys.argv = ["benchmarks.routing.baseline", "--output", os.environ["PROMPT_OUT"]]
            runpy.run_module("benchmarks.routing.baseline", run_name="__main__")
            """
        )
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["ANTHROPIC_API_KEY"] = KEY
        env["PROMPT_OUT"] = str(output)
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(KEY, result.stdout + result.stderr)
        self.assertNotIn(KEY, output.read_text(encoding="utf-8"))
        receipt = json.loads(result.stdout)
        self.assertFalse(receipt["invokes_model"])
        self.assertFalse(receipt["calls_api"])
        self.assertFalse(receipt["skill_loaded"])
        self.assertFalse(receipt["executed"])
        self.assertEqual(receipt["arm"], "no-skill-baseline")
        self.assertEqual(receipt["prompt_count"], 28)
        prompts = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(prompts), 28)
        instructions = {row["instruction"] for row in prompts}
        self.assertEqual(len(instructions), 1)
        joined = output.read_text(encoding="utf-8")
        for withheld in (
            "expected_workflow",
            "expected_template",
            "expected_topology",
            "required_milestones",
            "required_invariants",
        ):
            self.assertNotIn(withheld, joined)
        by_id = {row["id"]: row for row in prompts}
        self.assertEqual(set(by_id["coupled-bug"]), {"id", "instruction", "request"})
        self.assertIn("previously valid date", by_id["coupled-bug"]["request"])
        self.assertIn("read-only change-summary CLI", by_id["mixed-project-plan"]["request"])
        self.assertNotIn("stages", by_id["mixed-project-plan"])

    def test_scorer_process_does_not_open_a_socket(self):
        decisions = self.base / "decisions.jsonl"
        write_jsonl(decisions, gold_rows())
        code = textwrap.dedent(
            """
            import os
            import runpy
            import socket
            import sys

            class Blocked(socket.socket):
                def __init__(self, *args, **kwargs):
                    raise RuntimeError("scorer opened a socket")

            socket.socket = Blocked
            sys.argv = ["benchmarks.routing.score", "--decisions", os.environ["DECISIONS"]]
            runpy.run_module("benchmarks.routing.score", run_name="__main__")
            """
        )
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["DECISIONS"] = str(decisions)
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["metrics"]["exact"]["accuracy"]["k"], 27)


if __name__ == "__main__":
    unittest.main()
