"""Compare plain and AIC routing on held-out requests.

Expected labels are not part of either prompt. This module calls the supplied
client once per arm and does not retry a failed call.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from benchmarks.client import ModelClient
from benchmarks.errors import RunError


ARMS = ("plain-claude-code", "aic")
_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")
_SCHEMA = """Reply with one JSON object and no other text.
Use schema_version 3.
workflow must be one of: answer, research, implementation, debug, review, design.
template must be one of: direct, explore-build, coordinated-delivery, independent-review, adaptive-controller.
topology must be one of: solo, sequential, parallel, generator-evaluator.
Also include task, risk, reasons, evidence, scope, acceptance, independent_subtasks, next_action, and approval_required.
next_action must be recommend. approval_required must be true.
The user message is the only task. Do not add a score, a label key, or an explanation outside the JSON object.
"""


def load_cases(path: Path) -> list[dict]:
    if path.is_symlink():
        raise RunError(f"refusing a symlinked routing file: {path}", 3)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunError(f"unreadable routing cases: {path}", 1) from exc
    if not isinstance(document, dict) or not isinstance(document.get("cases"), list) or not document["cases"]:
        raise RunError("routing cases must be a nonempty list.", 1)
    seen: set[str] = set()
    cases = []
    for item in document["cases"]:
        if not isinstance(item, dict):
            raise RunError("each routing case must be an object.", 1)
        case_id = item.get("id")
        request = item.get("request")
        if not isinstance(case_id, str) or _CASE_ID.fullmatch(case_id) is None or ".." in case_id:
            raise RunError("routing case id is not a safe file name.", 1)
        if case_id in seen:
            raise RunError(f"duplicate routing case: {case_id}", 1)
        if not isinstance(request, str) or not request.strip():
            raise RunError(f"routing case is missing a request: {case_id}", 1)
        for field in ("expected_workflow", "expected_template", "expected_topology"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise RunError(f"routing case is missing {field}: {case_id}", 1)
        seen.add(case_id)
        cases.append(item)
    return cases


def context_text(root: Path, relative_paths: list[str]) -> str:
    parts = []
    for relative in relative_paths:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RunError(f"AIC context file is missing: {relative}", 1)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RunError(f"AIC context file is unreadable: {relative}", 1) from exc
        parts.append(f"# {relative}\n{text}")
    return "\n\n".join(parts)


def prompts(case: dict, aic_text: str) -> dict[str, tuple[str, str]]:
    """Return arm -> (system, user). The user text is only the held-out request."""
    user = case["request"]
    plain = (_SCHEMA, user)
    treated = (_SCHEMA + "\n" + aic_text, user)
    return {"plain-claude-code": plain, "aic": treated}


def _parsed_labels(text: str) -> dict | None:
    body = text.strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            body = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return value


def _matched(parsed: dict | None, case: dict) -> bool:
    if parsed is None:
        return False
    return all(parsed.get(field) == case[f"expected_{field}"] for field in ("workflow", "template", "topology"))


def compare(
    *,
    client: ModelClient,
    model: str,
    max_tokens: int,
    cases: list[dict],
    aic_text: str,
    raw_dir: Path | None = None,
    redact: str = "",
) -> dict:
    matches = {arm: 0 for arm in ARMS}
    rows = []
    for case in cases:
        arm_prompts = prompts(case, aic_text)
        for arm in ARMS:
            system, user = arm_prompts[arm]
            if "expected_workflow" in system or "expected_workflow" in user:
                raise RunError("refusing to send held-out label keys to the model.", 1)
            completion = client.complete(model=model, system=system, user=user, max_tokens=max_tokens)
            text = completion.text.replace(redact, "[redacted]") if redact else completion.text
            parsed = _parsed_labels(text)
            hit = _matched(parsed, case)
            matches[arm] += int(hit)
            row = {
                "arm": arm,
                "case": case["id"],
                "parsed": parsed is not None,
                "label_match": hit,
                "input_tokens": completion.input_tokens,
                "output_tokens": completion.output_tokens,
                "text": text,
            }
            rows.append(row)
            if raw_dir is not None:
                destination = raw_dir / arm / f"{case['id']}.json"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "suite": "routing",
        "command": "python3 -m benchmarks.routing.compare",
        "executed": True,
        "invokes_model": True,
        "model": model,
        "arms": list(ARMS),
        "cases": len(cases),
        "label_matches": matches,
        "public_benchmark_scores": None,
        "note": "Label matches belong to this receipt. They are not a public benchmark score.",
        "rows": rows,
    }
