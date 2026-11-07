"""Comparison metrics taken only from completed observations.

pass@1 uses the unbiased estimator from Chen et al., "Evaluating Large
Language Models Trained on Code", arXiv:2107.03374. The suite averages that
per-task estimate. It does not invent a pass rate, a token count, or a price.
"""

from __future__ import annotations

import decimal
import math

TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def pass_at_k(n: int, correct: int, k: int) -> float:
    """Return unbiased pass@k for one task with n samples and `correct` successes."""
    if type(n) is not int or type(correct) is not int or type(k) is not int:
        raise ValueError("pass@k requires integers.")
    if k < 1 or n < k or not 0 <= correct <= n:
        raise ValueError("pass@k requires 0 <= correct <= n and 1 <= k <= n.")
    if n - correct < k:
        return 1.0
    return 1.0 - math.comb(n - correct, k) / math.comb(n, k)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def usage_from_payload(payload: dict) -> dict[str, int | None] | None:
    """Read a top-level Claude Code `usage` object. Return None when it is absent or malformed."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    parsed: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        if field not in usage:
            parsed[field] = None
            continue
        value = usage[field]
        if type(value) is not int or value < 0:
            return None
        parsed[field] = value
    if parsed["input_tokens"] is None or parsed["output_tokens"] is None:
        return None
    return parsed


def cost_from_payload(payload: dict) -> decimal.Decimal | None:
    """Read Claude Code's reported `total_cost_usd`. Do not price tokens locally."""
    if "total_cost_usd" not in payload:
        return None
    value = payload["total_cost_usd"]
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        amount = decimal.Decimal(str(value))
    except decimal.InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def sum_usage(samples: list[dict[str, int | None] | None]) -> dict[str, int | None] | None:
    """Sum token fields. Any missing sample or field stays null for that field."""
    if not samples or any(sample is None for sample in samples):
        return None
    totals: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        values = [sample[field] for sample in samples if sample is not None]
        totals[field] = None if any(value is None for value in values) else sum(value or 0 for value in values)
    return totals


def sum_cost(samples: list[decimal.Decimal | None]) -> str | None:
    if not samples or any(sample is None for sample in samples):
        return None
    total = sum((sample for sample in samples if sample is not None), decimal.Decimal(0))
    return format(total, "f")


def cost_text(amount: decimal.Decimal | None) -> str | None:
    if amount is None:
        return None
    return format(amount, "f")
