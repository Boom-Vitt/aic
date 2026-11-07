"""Gate and review freshness for one Orca stream.

A missing gate fails readiness. An approval counts only for the recorded head
and patch id. A later commit is stale and must be reviewed again.
"""
from __future__ import annotations


def assess_readiness(*, head: str, patch_id: str, gate: dict | None, review: dict | None) -> dict:
    if not isinstance(head, str) or not head or not isinstance(patch_id, str) or not patch_id:
        return {'ready': False, 'code': 2, 'reason': 'head and patch id are required.'}
    if not isinstance(gate, dict):
        return {'ready': False, 'code': 1, 'reason': 'missing gate record.'}
    if gate.get('result') != 'pass' or gate.get('head') != head:
        return {'ready': False, 'code': 1, 'reason': 'gate is missing a pass for this head.'}
    if not isinstance(review, dict):
        return {'ready': False, 'code': 3, 'reason': 'missing review record.'}
    if review.get('verdict') != 'APPROVE':
        return {'ready': False, 'code': 3, 'reason': 'review is not an approval.'}
    if review.get('head') != head or review.get('patch_id') != patch_id:
        return {'ready': False, 'code': 5, 'reason': 'review is stale for this head or patch id.'}
    return {'ready': True, 'code': 0, 'reason': 'gate and review match this head.'}
