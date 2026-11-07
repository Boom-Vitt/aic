"""Bound recommendation work before inspecting an approved project's filesystem."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/aic/scripts"))
from aiclib.routing import validate_plan
from aiclib.safety import AICError
from test_routing import parallel_recommendation, recommendation


class RoutingResourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixtures = ROOT / ".work"
        fixtures.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="security-routing-", dir=fixtures)
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "project"
        self.project.mkdir()
        (self.project / "src").mkdir()
        (self.project / "tests").mkdir()
        (self.project / "src/app.py").write_text("PRIVATE_PROJECT_CONTENT\n", encoding="utf-8")

    def parallel_plan(self, *sizes):
        plan = parallel_recommendation()
        plan["independent_subtasks"] = [
            {
                "goal": f"Review independent slice {branch}.",
                "allowed_paths": [f"slice-{branch}-{index:03d}.py" for index in range(size)],
                "acceptance": [f"Report evidence for slice {branch}."],
            }
            for branch, size in enumerate(sizes)
        ]
        return plan

    def assert_rejected_before_filesystem(self, plan):
        # A resource-invalid request must not need even project metadata to fail.
        # These are external I/O guards, not replacements for validation results.
        with patch.object(Path, "stat", side_effect=AssertionError("Unexpected filesystem metadata access.")), patch.object(
            Path, "lstat", side_effect=AssertionError("Unexpected filesystem metadata access.")
        ), patch.object(Path, "open", side_effect=AssertionError("Unexpected filesystem content access.")):
            with self.assertRaises(AICError):
                validate_plan(plan, project=self.project)

    def test_audit_two_disjoint_256_path_branches_are_rejected(self):
        plan = self.parallel_plan(256, 256)
        before = copy.deepcopy(plan)
        with self.assertRaises(AICError):
            validate_plan(plan)
        self.assertEqual(plan, before)

    def test_audit_oversized_plan_is_rejected_before_project_io(self):
        self.assert_rejected_before_filesystem(self.parallel_plan(256, 256))

    def test_seventeen_disjoint_branches_are_rejected_before_project_io(self):
        self.assert_rejected_before_filesystem(self.parallel_plan(*([1] * 17)))

    def test_sixteen_disjoint_branches_remain_valid(self):
        plan = self.parallel_plan(*([1] * 16))
        self.assertEqual(validate_plan(plan, project=self.project), plan)

    def test_path_budget_is_aggregate_across_evidence_scope_and_branches(self):
        plan = self.parallel_plan(43, 43)
        plan["scope"] = {
            "read": [f"read-{index:03d}.py" for index in range(85)],
            "write": [f"write-{index:03d}.py" for index in range(85)],
        }
        # One existing evidence path + 170 scope entries + 86 branch entries.
        self.assertEqual(
            len(plan["evidence"]) + sum(map(len, plan["scope"].values()))
            + sum(len(branch["allowed_paths"]) for branch in plan["independent_subtasks"]),
            257,
        )
        self.assert_rejected_before_filesystem(plan)

    def test_project_bound_work_budget_counts_lexical_and_physical_checks(self):
        # 91 * 91 lexical pairs fit alone, but both isolation passes need 16,562.
        plan = self.parallel_plan(91, 91)
        self.assertEqual(validate_plan(plan), plan)
        self.assert_rejected_before_filesystem(plan)

    def test_unbound_work_budget_counts_all_branch_pairs(self):
        plan = self.parallel_plan(85, 85, 85)
        plan["evidence"] = []
        plan["scope"] = {"read": [], "write": []}
        # 255 total paths, but three Cartesian products need 21,675 comparisons.
        with self.assertRaises(AICError):
            validate_plan(plan)

    def test_excessive_path_depth_is_rejected_before_project_io(self):
        plan = self.parallel_plan(1, 1)
        plan["independent_subtasks"][0]["allowed_paths"] = ["/".join(["nested"] * 33)]
        for project_bound in (False, True):
            with self.subTest(project_bound=project_bound):
                if project_bound:
                    self.assert_rejected_before_filesystem(plan)
                else:
                    with self.assertRaises(AICError):
                        validate_plan(plan)

    def test_thirty_two_component_path_remains_valid(self):
        plan = self.parallel_plan(1, 1)
        plan["independent_subtasks"][0]["allowed_paths"] = ["/".join(["nested"] * 32)]
        self.assertEqual(validate_plan(plan, project=self.project), plan)

    def test_excessive_utf8_path_bytes_are_rejected_before_project_io(self):
        # Every component fits ordinary filesystem name limits; only the whole
        # relative path exceeds the recommendation's UTF-8 byte budget.
        path = "/".join(["é" * 100] * 5) + "x" * 21
        self.assertEqual(len(path.encode("utf-8")), 1025)
        plan = recommendation()
        plan["scope"]["write"] = [path]
        for project_bound in (False, True):
            with self.subTest(project_bound=project_bound):
                if project_bound:
                    self.assert_rejected_before_filesystem(plan)
                else:
                    with self.assertRaises(AICError):
                        validate_plan(plan)

    def test_one_thousand_twenty_four_utf8_path_bytes_remain_valid(self):
        path = "/".join(["é" * 100] * 5) + "x" * 20
        self.assertEqual(len(path.encode("utf-8")), 1024)
        plan = recommendation()
        plan["scope"]["write"] = [path]
        # The lexical ceiling does not promise that a rooted path fits the
        # host's PATH_MAX. Keep genuine filesystem inspection errors fail-closed.
        self.assertEqual(validate_plan(plan), plan)

    def test_payload_budget_rejects_valid_ascii_and_multibyte_text_before_io(self):
        for text in ("x" * 65_536, "é" * 32_768):
            with self.subTest(text_bytes=len(text.encode("utf-8"))):
                plan = recommendation()
                plan["task"] = text
                self.assertGreater(
                    len(json.dumps(plan, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
                    65_536,
                )
                self.assert_rejected_before_filesystem(plan)

    def test_large_valid_text_container_is_rejected_before_project_io(self):
        plan = recommendation()
        plan["acceptance"] = ["Check the bounded result."] * 4096
        self.assert_rejected_before_filesystem(plan)

    def test_deep_structure_is_controlled_rejection_before_project_io(self):
        plan = self.parallel_plan(1, 1)
        nested = "Not a schema-valid acceptance item."
        for _ in range(12):
            nested = [nested]
        plan["independent_subtasks"][1]["acceptance"] = nested
        self.assert_rejected_before_filesystem(plan)

    def test_recursive_structure_is_controlled_rejection_before_project_io(self):
        plan = recommendation()
        plan["scope"]["read"] = [plan]
        self.assert_rejected_before_filesystem(plan)

    def test_unsupported_values_are_controlled_rejection_before_project_io(self):
        for value in (object(), {"not", "JSON"}, float("nan"), float("inf")):
            with self.subTest(value_type=type(value).__name__):
                plan = recommendation()
                plan["scope"]["write"] = [value]
                self.assert_rejected_before_filesystem(plan)

    def test_small_valid_parallel_plan_is_preserved_and_detached(self):
        plan = self.parallel_plan(3, 4)
        before = copy.deepcopy(plan)
        result = validate_plan(plan, project=self.project)
        self.assertEqual(result, before)
        self.assertEqual(plan, before)
        result["independent_subtasks"][0]["allowed_paths"].append("returned-copy-only.py")
        result["evidence"][0]["observation"] = "Returned copy changed."
        self.assertEqual(plan, before)

    def test_acceptable_work_boundary_preserves_late_physical_alias_rejection(self):
        # 90 * 91 * 2 = 16,380 checks: under the work budget without truncation.
        plan = self.parallel_plan(90, 91)
        # Evidence (1), scope (74) and branch paths (181) total exactly 256.
        plan["scope"] = {
            "read": [f"read-{index:03d}.py" for index in range(37)],
            "write": [f"write-{index:03d}.py" for index in range(37)],
        }
        self.assertEqual(validate_plan(plan, project=self.project), plan)
        first = self.project / plan["independent_subtasks"][0]["allowed_paths"][-1]
        alias = self.project / plan["independent_subtasks"][1]["allowed_paths"][-1]
        first.write_text("PRIVATE_ALIAS_CONTENT\n", encoding="utf-8")
        try:
            alias.hardlink_to(first)
        except OSError as exc:
            self.skipTest(f"This filesystem does not support fixture hard links: {exc.__class__.__name__}.")
        # Lexical scopes remain disjoint; the last pair shares actual identity.
        self.assertEqual(validate_plan(plan), plan)
        with self.assertRaises(AICError):
            validate_plan(plan, project=self.project)


if __name__ == "__main__":
    unittest.main()
