"""The held-out routing pack stays a legal scoring target.

Expected labels are the fixture's own fields. This module does not read a
request and choose a workflow. A host that follows the skill is scored against
these labels in a separate run. That run needs a model, which this test does
not call.
"""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/aic/scripts"))
from aiclib.routing import validate_plan


FIXTURE = ROOT / "tests" / "fixtures" / "routing-scenarios.json"


def plan_from_labels(case):
    """Build a schema-3 recommendation from declared labels only."""

    topology = case["expected_topology"]
    plan = {
        "schema_version": 3,
        "task": "Held-out label check. The request text is not an input to this plan.",
        "workflow": case["expected_workflow"],
        "template": case["expected_template"],
        "topology": topology,
        "risk": "low",
        "reasons": ["The fixture declares this family and topology. This test does not infer them."],
        "evidence": [],
        "scope": {"read": [], "write": []},
        "acceptance": ["The original acceptance criteria remain the ones in the request."],
        "independent_subtasks": [],
        "next_action": "recommend",
        "approval_required": True,
    }
    if topology == "parallel":
        plan["independent_subtasks"] = [
            {
                "goal": "First independently checkable branch.",
                "allowed_paths": ["branch-a"],
                "acceptance": ["The first branch has its own check."],
            },
            {
                "goal": "Second independently checkable branch.",
                "allowed_paths": ["branch-b"],
                "acceptance": ["The second branch has its own check."],
            },
        ]
    return plan


class RoutingScenarioPackTests(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_pack_withholds_labels_and_keeps_twenty_seven_cases(self):
        self.assertEqual(self.pack["schema_version"], 3)
        self.assertEqual(len(self.pack["cases"]), 27)
        self.assertEqual(len(self.pack["project_case"]["stages"]), 6)
        limits = self.pack["limits"]
        self.assertIn("withheld from fresh host-AI inputs", limits)
        self.assertIn("never a production keyword classifier", limits)

    def test_every_declared_label_is_a_valid_recommendation(self):
        seen = []
        for case in self.pack["cases"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["request"].strip())
                plan = plan_from_labels(case)
                self.assertNotIn(case["request"], json.dumps(plan))
                checked = validate_plan(plan)
                self.assertEqual(checked["workflow"], case["expected_workflow"])
                self.assertEqual(checked["template"], case["expected_template"])
                self.assertEqual(checked["topology"], case["expected_topology"])
                self.assertEqual(checked["next_action"], "recommend")
                self.assertIs(checked["approval_required"], True)
                seen.append((case["expected_workflow"], case["expected_template"], case["expected_topology"]))
        self.assertIn(("implementation", "direct", "solo"), seen)
        self.assertIn(("implementation", "adaptive-controller", "parallel"), seen)
        self.assertIn(("review", "coordinated-delivery", "parallel"), seen)
        self.assertIn(("research", "direct", "solo"), seen)

    def test_project_stages_use_legal_labels_without_reading_the_request(self):
        project = self.pack["project_case"]
        self.assertTrue(project["request"].strip())
        for stage in project["stages"]:
            with self.subTest(stage=stage["id"]):
                plan = plan_from_labels(stage)
                self.assertNotIn(project["request"], json.dumps(plan))
                checked = validate_plan(plan)
                self.assertEqual(checked["workflow"], stage["expected_workflow"])
                self.assertEqual(checked["template"], stage["expected_template"])
                self.assertEqual(checked["topology"], stage["expected_topology"])


if __name__ == "__main__":
    unittest.main()
