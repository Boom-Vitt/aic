"""Consumer-visible template/topology compatibility, not AI classification tests."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/aic/scripts'))
from aiclib.routing import validate_plan
from aiclib.safety import AICError


def recommendation(template='direct', topology='solo'):
    value = {
        'schema_version': 3,
        'task': 'Recommend an approved implementation approach without executing it.',
        'workflow': 'implementation',
        'template': template,
        'topology': topology,
        'risk': 'medium',
        'reasons': ['The host selected this structure for the observed dependencies.'],
        'evidence': [],
        'scope': {'read': [], 'write': []},
        'acceptance': ['The original behavior is exercised and its evidence is reported.'],
        'independent_subtasks': [],
        'next_action': 'recommend',
        'approval_required': True,
    }
    if topology == 'parallel':
        value['independent_subtasks'] = [
            {'goal': 'Implement the producer unit.', 'allowed_paths': ['src/producer.py'],
             'acceptance': ['The producer satisfies the agreed public interface.']},
            {'goal': 'Implement an independent utility.', 'allowed_paths': ['src/utility.py'],
             'acceptance': ['The utility satisfies its independently checkable behavior.']},
        ]
    return value


class TemplateContractTests(unittest.TestCase):
    def test_each_selected_workflow_template_is_preserved_without_reclassification(self):
        cases = (
            ('direct', 'solo'),
            ('explore-build', 'parallel'),
            ('coordinated-delivery', 'sequential'),
            ('coordinated-delivery', 'parallel'),
            ('independent-review', 'generator-evaluator'),
            ('adaptive-controller', 'solo'),
            ('adaptive-controller', 'sequential'),
            ('adaptive-controller', 'parallel'),
            ('adaptive-controller', 'generator-evaluator'),
        )
        for template, topology in cases:
            with self.subTest(template=template, topology=topology):
                value = recommendation(template, topology)
                before = copy.deepcopy(value)
                result = validate_plan(value)
                self.assertEqual(result, before)
                result['acceptance'].append('Only the detached return value changes.')
                self.assertEqual(value, before)

    def test_incompatible_template_topology_pairs_are_rejected(self):
        cases = (
            ('direct', 'parallel'),
            ('explore-build', 'solo'),
            ('explore-build', 'sequential'),
            ('coordinated-delivery', 'solo'),
            ('coordinated-delivery', 'generator-evaluator'),
            ('independent-review', 'solo'),
        )
        for template, topology in cases:
            with self.subTest(template=template, topology=topology):
                with self.assertRaises(AICError):
                    validate_plan(recommendation(template, topology))

    def test_unknown_missing_and_nontext_template_choices_are_rejected(self):
        for choice in ('permanent-swarm', '', None, [], {'approved': True}):
            value = recommendation()
            value['template'] = choice
            with self.subTest(choice=choice), self.assertRaises(AICError):
                validate_plan(value)
        value = recommendation()
        del value['template']
        with self.assertRaises(AICError):
            validate_plan(value)

    def test_previous_schema_with_a_valid_template_is_not_silently_accepted(self):
        for version in (1, 2):
            value = recommendation()
            value['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(AICError):
                validate_plan(value)

    def test_retired_template_names_are_rejected_without_aliases(self):
        for template in ('ordered-handoff', 'isolated-build', 'durable-controller',
                         'adaptive-optimization'):
            with self.subTest(template=template), self.assertRaises(AICError):
                validate_plan(recommendation(template, 'sequential'))

    def test_nonparallel_plan_cannot_declare_concurrent_independent_branches(self):
        value = recommendation('coordinated-delivery', 'sequential')
        value['independent_subtasks'] = recommendation('coordinated-delivery', 'parallel')['independent_subtasks']
        with self.assertRaises(AICError):
            validate_plan(value)

    def test_adaptive_template_does_not_bypass_parallel_isolation_or_approval(self):
        value = recommendation('adaptive-controller', 'parallel')
        value['independent_subtasks'][1]['allowed_paths'] = ['src/producer.py']
        with self.assertRaises(AICError):
            validate_plan(value)
        value = recommendation('adaptive-controller', 'sequential')
        value['next_action'] = 'launch'
        value['approval_required'] = False
        with self.assertRaises(AICError):
            validate_plan(value)


if __name__ == '__main__':
    unittest.main()
