"""Consumer-visible gates for publication, grounding and independent review."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maintenance.contracts import Candidate, SourceDocument
from maintenance import policy


def candidate(key='paper-v1'):
    text = 'Synthetic source: an evaluated planning process helped one bounded task. The experiment did not compare equal costs. No publication reuse permission is stated.'
    doc = SourceDocument('https://arxiv.org/html/2610.00001v1', text, hashlib.sha256(text.encode()).hexdigest(), True, '2026-11-06T00:00:00+00:00')
    return Candidate(key, doc.url, 'A synthetic source', ('Example Researcher',), '2026-11-05', '2026-11-05', 'preprint', (doc,), 'arXiv')


def research(key='paper-v1'):
    return dict(schema_version=1, records=[dict(candidate_key=key, summary='A narrow experiment examined how planning was allocated.',
        methods=['A fixed task set was used to compare planning arrangements.'], findings=['One observed setting favored more preparation.'],
        limitations=['Unequal resources prevent a general efficiency conclusion.'],
        license=dict(status='unverified', identifier='unknown', evidence_url=candidate().url, observation='No explicit reuse grant was found in the supplied packet.'),
        relevant_templates=['explore-build'], adoption_task='Assess whether an approved representative task has a discovery bottleneck.', reference_only=True)], manual_tasks=[], rejected=[])


def review():
    return dict(schema_version=1, head_sha='a' * 40, source_digest='b' * 64, verdict='approve',
        assessments=[dict(candidate_key='paper-v1', grounding='The limited claims match the supplied controlled example.', rights='Unknown content rights remain explicit and reference-only.', originality='The short factual note does not reproduce the source passage.', scope='The artifact is evidence, not a change to an agent procedure.', verdict='approve')], findings=[])


class MaintainerPolicyTests(unittest.TestCase):
    def test_missing_methods_or_forged_sources_cannot_be_published(self):
        original = candidate()
        for bad in (replace(original, documents=()), replace(original, documents=(replace(original.documents[0], complete=False),)), replace(original, documents=(replace(original.documents[0], text='tampered'),))):
            with self.subTest(candidate=bad), self.assertRaises(policy.PolicyError):
                policy.validate_research(research(), [bad], {'explore-build'})
        payload = research()
        payload['records'][0]['license']['evidence_url'] = 'https://unprovided.example/rights'
        with self.assertRaises(policy.PolicyError):
            policy.validate_research(payload, [original], {'explore-build'})

    def test_output_cannot_invent_candidate_authority_or_template(self):
        for change in ('candidate', 'authority', 'template', 'missing'):
            payload = research()
            if change == 'candidate':
                payload['records'][0]['candidate_key'] = 'invented'
            elif change == 'authority':
                payload['records'][0]['approved_to_execute'] = True
            elif change == 'template':
                payload['records'][0]['relevant_templates'] = ['invented-team']
            else:
                payload['records'] = []
            with self.subTest(change=change), self.assertRaises(policy.PolicyError):
                policy.validate_research(payload, [candidate()], {'explore-build'})

    def test_unknown_permission_or_copying_cannot_be_laundered_into_approval(self):
        for change in ('rights', 'reference', 'copy'):
            payload = research()
            if change == 'rights':
                payload['records'][0]['license']['status'] = 'verified'
            elif change == 'reference':
                payload['records'][0]['reference_only'] = False
            else:
                payload['records'][0]['summary'] = candidate().documents[0].text
            with self.subTest(change=change), self.assertRaises(policy.PolicyError):
                policy.validate_research(payload, [candidate()], {'explore-build'})

    def test_public_issue_and_rights_fields_reject_copied_source_expression(self):
        for field in ('adoption_task', 'observation', 'identifier', 'manual_reason'):
            payload = research()
            copied = candidate().documents[0].text
            if field == 'manual_reason':
                payload['records'] = []
                payload['manual_tasks'] = [dict(candidate_key='paper-v1', reason=copied)]
            elif field == 'adoption_task':
                payload['records'][0][field] = copied
            else:
                payload['records'][0]['license'][field] = copied
            with self.subTest(field=field), self.assertRaises(policy.PolicyError):
                policy.validate_research(payload, [candidate()], {'explore-build'})

    def test_review_comments_do_not_redistribute_source_expression(self):
        for field in ('grounding', 'rights', 'originality', 'scope', 'finding'):
            payload = review()
            copied = candidate().documents[0].text
            if field == 'finding':
                payload['findings'] = [dict(candidate_key='paper-v1', severity='warning', message=copied, source_url=candidate().url)]
            else:
                payload['assessments'][0][field] = copied
            with self.subTest(field=field), self.assertRaises(policy.PolicyError):
                policy.validate_review(payload, head_sha='a' * 40, bundle_digest='b' * 64, records=research()['records'], candidates=[candidate()])

    def test_copying_a_different_supplied_source_cannot_escape_the_gate(self):
        text = 'Another synthetic study measured different architectural constraints in a deliberately separate corpus with enough distinct words to identify copied expression.'
        original = candidate('paper-v2')
        second = replace(original, documents=(replace(original.documents[0], text=text, sha256=hashlib.sha256(text.encode()).hexdigest()),))
        payload = research()
        payload['records'][0]['adoption_task'] = text
        payload['rejected'] = [dict(candidate_key='paper-v2', reason='This separate experiment is not applicable to the selected task.')]
        with self.assertRaises(policy.PolicyError):
            policy.validate_research(payload, [candidate(), second], {'explore-build'})

    def test_unverified_reference_only_record_is_allowed_without_a_copying_grant(self):
        result = policy.validate_research(research(), [candidate()], {'explore-build'})
        self.assertEqual(result['records'][0]['license']['status'], 'unverified')
        self.assertIs(result['records'][0]['reference_only'], True)
        self.assertEqual(research()['records'][0]['license']['status'], 'unverified')

    def test_a_rejected_or_manual_candidate_is_not_forced_into_a_daily_record(self):
        payload = dict(schema_version=1, records=[], manual_tasks=[dict(candidate_key='paper-v1', reason='The available scientific evidence needs a human decision.')], rejected=[])
        result = policy.validate_research(payload, [candidate()], {'explore-build'})
        with self.assertRaises(policy.PolicyError):
            policy.render_records('2026-11-06', result['records'], [candidate()])

    def test_review_is_bound_to_head_sources_and_complete_record_coverage(self):
        for change in ('head', 'source', 'coverage', 'contradiction'):
            payload = review()
            if change == 'head':
                payload['head_sha'] = 'c' * 40
            elif change == 'source':
                payload['source_digest'] = 'c' * 64
            elif change == 'coverage':
                payload['assessments'] = []
            else:
                payload['findings'] = [dict(candidate_key='paper-v1', severity='blocker', message='The source does not support the asserted comparison.', source_url=candidate().url)]
            with self.subTest(change=change), self.assertRaises(policy.PolicyError):
                policy.validate_review(payload, head_sha='a' * 40, bundle_digest='b' * 64, records=research()['records'], candidates=[candidate()])

    def test_unhashable_review_identities_are_clean_rejections(self):
        for key in ([], {}):
            payload = review()
            payload['assessments'][0]['candidate_key'] = key
            with self.subTest(key=key), self.assertRaises(policy.PolicyError):
                policy.validate_review(payload, head_sha='a' * 40, bundle_digest='b' * 64, records=research()['records'], candidates=[candidate()])

    def test_unprovided_body_links_and_markup_fragments_cannot_publish(self):
        payload = research()
        payload['records'][0]['summary'] = 'A proposed comparison is described at https://unprovided.example/method.'
        with self.assertRaises(policy.PolicyError):
            policy.validate_research(payload, [candidate()], {'explore-build'})
        payload = research()
        payload['records'][0]['license']['evidence_url'] = candidate().url + '#) [outside](https://unprovided.example)'
        with self.assertRaises(policy.PolicyError):
            policy.validate_research(payload, [candidate()], {'explore-build'})

    def test_research_factual_lists_enforce_item_count_and_text_boundaries(self):
        for field in ('methods', 'findings', 'limitations'):
            for count, length in ((4, 700), (5, 700), (4, 701)):
                payload = research()
                payload['records'][0][field] = ['x' * length] * count
                with self.subTest(field=field, count=count, length=length):
                    if count > 4 or length > 700:
                        with self.assertRaises(policy.PolicyError):
                            policy.validate_research(payload, [candidate()], {'explore-build'})
                    else:
                        self.assertEqual(policy.validate_research(payload, [candidate()], {'explore-build'}), payload)

    def test_research_text_boundaries_preserve_original_source_bound_values(self):
        for field, maximum in (('summary', 1600), ('identifier', 160), ('observation', 900), ('adoption_task', 1000)):
            for extra in (0, 1):
                payload = research()
                target = payload['records'][0]
                if field in ('identifier', 'observation'):
                    target = target['license']
                target[field] = 'x' * (maximum + extra)
                with self.subTest(field=field, extra=extra):
                    if extra:
                        with self.assertRaises(policy.PolicyError):
                            policy.validate_research(payload, [candidate()], {'explore-build'})
                    else:
                        self.assertEqual(policy.validate_research(payload, [candidate()], {'explore-build'}), payload)

    def test_disposition_and_template_boundaries(self):
        for section in ('manual_tasks', 'rejected'):
            for extra in (0, 1):
                payload = dict(schema_version=1, records=[], manual_tasks=[], rejected=[])
                payload[section] = [dict(candidate_key='paper-v1', reason='x' * (1400 + extra))]
                with self.subTest(section=section, extra=extra):
                    if extra:
                        with self.assertRaises(policy.PolicyError):
                            policy.validate_research(payload, [candidate()], {'explore-build'})
                    else:
                        self.assertEqual(policy.validate_research(payload, [candidate()], {'explore-build'}), payload)
        for count in (3, 4):
            payload = research()
            payload['records'][0]['relevant_templates'] = [f'template-{i}' for i in range(count)]
            with self.subTest(templates=count):
                if count > 3:
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_research(payload, [candidate()], set(payload['records'][0]['relevant_templates']))
                else:
                    self.assertEqual(policy.validate_research(payload, [candidate()], set(payload['records'][0]['relevant_templates'])), payload)

    def test_review_text_boundaries_preserve_exact_head_and_source_binding(self):
        for field in ('grounding', 'rights', 'originality', 'scope', 'message'):
            for extra in (0, 1):
                payload = review()
                payload['source_digest'] = policy.source_digest([candidate()])
                if field == 'message':
                    payload['findings'] = [dict(candidate_key='paper-v1', severity='warning', message='x' * (1400 + extra), source_url=candidate().url)]
                else:
                    payload['assessments'][0][field] = 'x' * (1400 + extra)
                with self.subTest(field=field, extra=extra):
                    arguments = dict(head_sha='a' * 40, bundle_digest=policy.source_digest([candidate()]), records=research()['records'], candidates=[candidate()])
                    if extra:
                        with self.assertRaises(policy.PolicyError):
                            policy.validate_review(payload, **arguments)
                    else:
                        self.assertEqual(policy.validate_review(payload, **arguments), payload)
                        for binding in ('head_sha', 'bundle_digest'):
                            with self.assertRaises(policy.PolicyError):
                                policy.validate_review(payload, **dict(arguments, **{binding: 'c' * 64}))

    def test_evidence_url_boundaries_require_the_supplied_source(self):
        for extra in (0, 1):
            url = 'https://arxiv.org/' + 'x' * (2048 - len('https://arxiv.org/') + extra)
            original = candidate()
            source = replace(original, url=url, documents=(replace(original.documents[0], url=url),))
            payload = research()
            payload['records'][0]['license']['evidence_url'] = url
            assessment = review()
            assessment['source_digest'] = policy.source_digest([source])
            assessment['findings'] = [dict(candidate_key=source.key, severity='warning', message='A narrow evidence caveat remains.', source_url=url)]
            with self.subTest(extra=extra):
                if extra:
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_research(payload, [source], {'explore-build'})
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_review(assessment, head_sha=assessment['head_sha'], bundle_digest=assessment['source_digest'], records=payload['records'], candidates=[source])
                else:
                    self.assertEqual(policy.validate_research(payload, [source], {'explore-build'}), payload)
                    self.assertEqual(policy.validate_review(assessment, head_sha=assessment['head_sha'], bundle_digest=assessment['source_digest'], records=payload['records'], candidates=[source]), assessment)
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_research(payload, [original], {'explore-build'})
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_review(assessment, head_sha=assessment['head_sha'], bundle_digest=assessment['source_digest'], records=payload['records'], candidates=[original])

    def test_url_fragment_boundaries_do_not_authorize_other_sources(self):
        for length in (160, 161):
            payload = research()
            payload['records'][0]['license']['evidence_url'] += '#' + 'x' * length
            with self.subTest(length=length):
                if length > 160:
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_research(payload, [candidate()], {'explore-build'})
                else:
                    self.assertEqual(policy.validate_research(payload, [candidate()], {'explore-build'}), payload)

    def test_candidate_count_boundaries_require_one_disposition_per_source(self):
        for count in (3, 4):
            sources = [candidate(f'paper-{index}') for index in range(count)]
            payload = dict(schema_version=1, records=[], manual_tasks=[],
                           rejected=[dict(candidate_key=source.key, reason='This task is outside the selected research scope.') for source in sources])
            with self.subTest(count=count):
                if count > 3:
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_research(payload, sources, {'explore-build'})
                else:
                    self.assertEqual(policy.validate_research(payload, sources, {'explore-build'}), payload)
                    payload['rejected'].append(dict(payload['rejected'][0]))
                    with self.assertRaises(policy.PolicyError):
                        policy.validate_research(payload, sources, {'explore-build'})

    def test_record_only_lane_rejects_changes_to_existing_or_other_files(self):
        target = policy.record_path('2026-11-06')
        self.assertTrue(policy.record_only_files([dict(filename=target, status='added')], '2026-11-06'))
        for files in ([dict(filename=target, status='modified')], [dict(filename=target, status='added'), dict(filename='skills/aic/SKILL.md', status='modified')], [dict(filename='skills/aic/references/templates.md', status='added')], [dict(filename=target, status='added', previous_filename='README.md')]):
            with self.subTest(files=files):
                self.assertFalse(policy.record_only_files(files, '2026-11-06'))

    def test_dates_do_not_accept_path_traversal_or_non_calendar_values(self):
        for day in ('../../escape', '2026-02-30', '２０２６-１１-０６', '2026-11-06/other'):
            with self.subTest(day=day), self.assertRaises(policy.PolicyError):
                policy.record_path(day)
        self.assertEqual(policy.day_key(datetime(2026, 11, 6, tzinfo=timezone.utc)), '2026-11-06')
        with self.assertRaises(policy.PolicyError):
            policy.day_key(datetime(2026, 11, 6))


if __name__ == '__main__':
    unittest.main()
