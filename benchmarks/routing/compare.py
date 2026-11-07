"""Compare a no-skill arm with an AIC arm on one routing pack.

The default pack is the dev fixture. Pass ``--pack`` to score another file,
including the release pack ``benchmarks/routing/heldout-v2.json``.

Both arms share one model id, temperature, max_tokens, timeout, and output
schema. The no-skill arm sees the request and the closed catalog. The AIC arm
sees that same text plus ``skills/aic/SKILL.md`` and the relative files it
links. Gold labels stay out of both prompts.

The Anthropic Messages API is called only when ``ANTHROPIC_API_KEY`` is set.
A missing or blank key exits 3 and writes nothing. Tests pass a client; the
default client is plain HTTPS to ``api.anthropic.com`` and does not follow
redirects.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import http.client
import json
import math
import os
from pathlib import Path
import re
import sys

from benchmarks.routing.baseline import load_catalog
from benchmarks.routing.score import (
    EXIT_REFUSED,
    EXIT_USAGE,
    MAX_ID,
    MAX_ITEMS,
    MAX_LABEL,
    MAX_TEXT,
    ScoreError,
    add_pack_arguments,
    load_pack,
    read_text,
    render_report,
    repo_root,
    score_decisions,
    selected_pack_path,
    write_exclusive,
)


EXIT_API = 1
API_HOST = "api.anthropic.com"
API_PATH = "/v1/messages"
API_VERSION = "2023-06-01"
MAX_RESPONSE_BYTES = 1_048_576
ARM_NO_SKILL = "no-skill"
ARM_AIC = "aic"
MISSING_KEY_MESSAGE = (
    "ANTHROPIC_API_KEY is unset or blank. "
    "No routing comparison was started and no decisions were written."
)
_LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
NOTES = (
    "Both arms used the same model, temperature, max_tokens, timeout, and output schema.",
    "The no-skill arm received the request and the closed catalog. The AIC arm received that same text plus the skill files listed in context.",
    "Gold labels were not copied into either prompt.",
    "The Messages API has no seed parameter. The recorded seed was not sent.",
    "Paired counts and the exact McNemar test use flat cases only. The project case stays in the per-arm score.",
    "A zero discordant count has no McNemar probability.",
    "This receipt describes the run that wrote it. It is not a checked-in leaderboard.",
)


MessageClient = Callable[[Mapping[str, object]], str]


@dataclass(frozen=True)
class Settings:
    model: str
    temperature: float
    max_tokens: int
    seed: int
    timeout: float
    date: str


@dataclass(frozen=True)
class Item:
    id: str
    user: str
    project: bool


def credential_present(environ: Mapping[str, str]) -> bool:
    value = environ.get("ANTHROPIC_API_KEY")
    return isinstance(value, str) and value.strip() != ""


def help_requested(argv: list[str]) -> bool:
    return any(argument in ("-h", "--help") for argument in argv)


def utc_date(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ScoreError("comparison clock must be timezone-aware")
    return moment.astimezone(timezone.utc).date().isoformat()


def message_body(*, system: str, user: str, model: str, temperature: float, max_tokens: int) -> dict[str, object]:
    """JSON body for one Messages API call. The API key is not a field."""
    return {
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
        "model": model,
        "system": system,
        "temperature": temperature,
    }


def post_messages(
    body: Mapping[str, object],
    *,
    key: str,
    timeout: float,
    connection_factory: Callable[..., http.client.HTTPConnection] = http.client.HTTPSConnection,
) -> dict[str, object]:
    """POST one message to the Anthropic API. Redirects are not followed."""
    if not isinstance(key, str) or not key.strip():
        raise ScoreError(MISSING_KEY_MESSAGE, EXIT_REFUSED)
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if key.encode("utf-8") in payload:
        raise ScoreError("refusing to send the API key in the request body", EXIT_USAGE)
    connection = connection_factory(API_HOST, timeout=timeout)
    try:
        connection.request(
            "POST",
            API_PATH,
            body=payload,
            headers={
                "accept": "application/json",
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
                "x-api-key": key,
            },
        )
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        status = response.status
    finally:
        connection.close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ScoreError("model response exceeds the size limit", EXIT_API)
    detail = ""
    try:
        detail = raw.decode("utf-8")
    except UnicodeError:
        detail = ""
    if key and key in detail:
        detail = detail.replace(key, "[redacted]")
    if status != 200:
        raise ScoreError(f"Anthropic API returned HTTP {status}.", EXIT_API)
    try:
        parsed = json.loads(detail)
    except json.JSONDecodeError as exc:
        raise ScoreError("Anthropic API returned a non-JSON body.", EXIT_API) from exc
    if type(parsed) is not dict:
        raise ScoreError("Anthropic API returned a non-object body.", EXIT_API)
    return parsed


def text_from_response(payload: Mapping[str, object]) -> str:
    content = payload.get("content")
    if type(content) is not list:
        return ""
    parts: list[str] = []
    for block in content:
        if type(block) is dict and block.get("type") == "text" and type(block.get("text")) is str:
            parts.append(block["text"])
    return "".join(parts)


def https_client(key: str, timeout: float) -> MessageClient:
    def send(body: Mapping[str, object]) -> str:
        try:
            payload = post_messages(body, key=key, timeout=timeout)
        except OSError as exc:
            raise ScoreError("Anthropic API request failed.", EXIT_API) from exc
        return text_from_response(payload)

    return send


def skill_documents(root: Path) -> tuple[tuple[str, str], ...]:
    """Return ``(relative path, text)`` for SKILL.md and the relative files it links."""
    skill_root = root / "skills" / "aic"
    skill_path = skill_root / "SKILL.md"
    skill_text = read_text(skill_path)
    documents = [("skills/aic/SKILL.md", skill_text)]
    seen = {skill_path}
    for match in _LINK.finditer(skill_text):
        target = match.group(1).split("#", 1)[0].strip()
        if not target or "://" in target or target.startswith("#"):
            continue
        parts = Path(target).parts
        if not parts or target.startswith("/") or ".." in parts:
            raise ScoreError(f"skill link escapes the skill directory: {target}")
        path = skill_root.joinpath(*parts)
        if path in seen:
            continue
        seen.add(path)
        documents.append((f"skills/aic/{target}", read_text(path)))
    return tuple(documents)


def shared_system(catalog: Mapping[str, tuple[str, ...]]) -> str:
    return (
        "Choose one workflow, one template, and one topology from this closed catalog. "
        f"workflow: {', '.join(catalog['workflows'])}. "
        f"template: {', '.join(catalog['templates'])}. "
        f"topology: {', '.join(catalog['topologies'])}. "
        "Return one JSON object and no other text. Do not execute the request."
    )


def aic_system(catalog: Mapping[str, tuple[str, ...]], documents: tuple[tuple[str, str], ...]) -> str:
    blocks = [shared_system(catalog), "AIC skill context:"]
    for path, text in documents:
        blocks.append(f"# {path}\n\n{text}")
    return "\n\n".join(blocks)


def _items(pack: object) -> list[Item]:
    items = [
        Item(
            id=case.id,
            project=False,
            user=(
                "Return one JSON object with keys id, workflow, template, and topology. "
                f'id must be "{case.id}". '
                "workflow, template, and topology must be catalog ids.\n\n"
                f"Request:\n{case.request}"
            ),
        )
        for case in pack.cases
    ]
    project = pack.project
    if project is not None:
        stage_ids = ", ".join(stage.id for stage in project.stages)
        items.append(
            Item(
                id=project.id,
                project=True,
                user=(
                    "Return one JSON object with keys id, stages, milestones, and invariants. "
                    f'id must be "{project.id}". '
                    "Each stage object has keys id, workflow, template, and topology. "
                    f"Use each of these stage ids once: {stage_ids}. "
                    "milestones and invariants are lists of strings. "
                    "workflow, template, and topology must be catalog ids.\n\n"
                    f"Request:\n{project.request}"
                ),
            )
        )
    return items


def parse_model_object(text: str) -> dict | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
    if type(value) is dict:
        return value
    decoder = json.JSONDecoder()
    attempts = 0
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        attempts += 1
        if attempts > 32:
            return None
        try:
            found, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if type(found) is dict:
            return found
    return None


def _usable(value: object, *, limit: int) -> str | None:
    if type(value) is not str or value == "" or value != value.strip():
        return None
    if len(value) > limit or any(ord(character) < 32 for character in value):
        return None
    return value


def _label(parsed: Mapping[str, object], field: str) -> str | None:
    sources: list[Mapping[str, object]] = [parsed]
    for key in ("decision", "plan", "recommendation", "structured_output"):
        nested = parsed.get(key)
        if type(nested) is dict:
            sources.append(nested)
    found: list[str] = []
    for source in sources:
        if field not in source or source[field] is None:
            continue
        cleaned = _usable(source[field], limit=MAX_LABEL)
        if cleaned is not None:
            found.append(cleaned)
    distinct = set(found)
    if len(distinct) != 1:
        return None
    return found[0]


def normalize_decision(item: Item, parsed: Mapping[str, object] | None, *, stage_ids: set[str]) -> dict[str, object]:
    """Keep a model object only where it is a scorable decision. Unusable text is an abstention."""
    row: dict[str, object] = {"id": item.id}
    if parsed is None:
        return row
    if not item.project:
        for field in ("workflow", "template", "topology"):
            cleaned = _label(parsed, field)
            if cleaned is not None:
                row[field] = cleaned
        return row
    raw_stages = parsed.get("stages")
    stages: list[dict[str, object]] = []
    seen: set[str] = set()
    if type(raw_stages) is list:
        for raw in raw_stages[:MAX_ITEMS]:
            if type(raw) is not dict:
                continue
            ident = _usable(raw.get("id"), limit=MAX_ID)
            if ident is None or ident not in stage_ids or ident in seen:
                continue
            seen.add(ident)
            stage: dict[str, object] = {"id": ident}
            for field in ("workflow", "template", "topology"):
                cleaned = _usable(raw.get(field), limit=MAX_LABEL)
                if cleaned is not None:
                    stage[field] = cleaned
            stages.append(stage)
    if stages:
        row["stages"] = stages
    for key in ("milestones", "invariants"):
        raw_list = parsed.get(key)
        if type(raw_list) is not list or len(raw_list) > MAX_ITEMS:
            continue
        values = []
        for entry in raw_list:
            cleaned = _usable(entry, limit=MAX_TEXT)
            if cleaned is not None and cleaned not in values:
                values.append(cleaned)
        if values:
            row[key] = values
    return row


def mcnemar_exact(baseline_only: int, aic_only: int) -> dict[str, object]:
    """Two-sided exact McNemar test. ``p`` is null when there is no discordant pair."""
    if type(baseline_only) is not int or type(aic_only) is not int:
        raise ScoreError("McNemar counts must be integers")
    if baseline_only < 0 or aic_only < 0:
        raise ScoreError("McNemar counts must be non-negative")
    discordant = baseline_only + aic_only
    if discordant == 0:
        return {
            "aic_only_correct": 0,
            "baseline_only_correct": 0,
            "n_discordant": 0,
            "p": None,
            "p_denominator": None,
            "p_numerator": None,
        }
    observed = math.comb(discordant, baseline_only)
    total = 0
    for index in range(discordant + 1):
        ways = math.comb(discordant, index)
        if ways <= observed:
            total += ways
    fraction = Fraction(total, 2**discordant)
    return {
        "aic_only_correct": aic_only,
        "baseline_only_correct": baseline_only,
        "n_discordant": discordant,
        "p": float(fraction),
        "p_denominator": fraction.denominator,
        "p_numerator": fraction.numerator,
    }


def paired_outcome(baseline_flags: list[bool], aic_flags: list[bool]) -> dict[str, object]:
    if len(baseline_flags) != len(aic_flags):
        raise ScoreError("paired arms have different case counts")
    both = baseline_only = aic_only = neither = 0
    for left, right in zip(baseline_flags, aic_flags, strict=True):
        if left and right:
            both += 1
        elif left:
            baseline_only += 1
        elif right:
            aic_only += 1
        else:
            neither += 1
    total = len(baseline_flags)
    k_baseline = both + baseline_only
    k_aic = both + aic_only
    return {
        "aic_only_correct": aic_only,
        "baseline_only_correct": baseline_only,
        "both_correct": both,
        "both_wrong": neither,
        "difference": {
            "k_aic": k_aic,
            "k_baseline": k_baseline,
            "k_delta": k_aic - k_baseline,
            "n": total,
            "rate_delta": None if total == 0 else (k_aic - k_baseline) / total,
        },
        "mcnemar_exact": mcnemar_exact(baseline_only, aic_only),
        "n": total,
    }


def _flags(report: Mapping[str, object], field: str) -> list[bool]:
    cases = report.get("cases")
    if type(cases) is not list:
        raise ScoreError("arm score is missing cases")
    flags: list[bool] = []
    for row in cases:
        if type(row) is not dict:
            raise ScoreError("arm score case is not an object")
        correct = row.get("correct")
        if type(correct) is not dict or type(correct.get(field)) is not bool:
            raise ScoreError(f"arm score is missing {field} correctness")
        flags.append(correct[field])
    return flags


def _jsonl(rows: list[dict[str, object]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _publish(directory: Path, files: dict[str, str]) -> None:
    if directory.exists() or directory.is_symlink():
        raise ScoreError(f"refusing to overwrite {directory}", EXIT_USAGE)
    try:
        directory.mkdir()
    except OSError as exc:
        raise ScoreError(f"cannot create {directory}", EXIT_USAGE) from exc
    written: list[Path] = []
    try:
        for name, text in files.items():
            target = directory / name
            write_exclusive(target, text)
            written.append(target)
    except ScoreError:
        for target in written:
            try:
                os.unlink(target)
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
        raise


def compare_pack(
    pack: object,
    *,
    settings: Settings,
    client: MessageClient,
    transport: str,
    catalog: Mapping[str, tuple[str, ...]] | None = None,
    documents: tuple[tuple[str, str], ...] | None = None,
) -> tuple[dict[str, object], dict[str, str]]:
    loaded = documents if documents is not None else skill_documents(repo_root())
    labels = catalog if catalog is not None else load_catalog(repo_root())
    items = _items(pack)
    no_skill = shared_system(labels)
    with_skill = aic_system(labels, loaded)
    if not with_skill.startswith(no_skill) or with_skill == no_skill:
        raise ScoreError("AIC context did not add the skill text")
    stage_ids = {stage.id for stage in pack.project.stages} if pack.project is not None else set()
    calls = 0

    def collect(system: str) -> list[dict[str, object]]:
        nonlocal calls
        rows: list[dict[str, object]] = []
        for item in items:
            body = message_body(
                system=system,
                user=item.user,
                model=settings.model,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
            try:
                text = client(body)
            except ScoreError:
                raise
            except Exception as exc:
                raise ScoreError("model client failed", EXIT_API) from exc
            calls += 1
            if type(text) is not str:
                raise ScoreError("model client returned a non-string", EXIT_API)
            rows.append(normalize_decision(item, parse_model_object(text), stage_ids=stage_ids))
        return rows

    no_skill_rows = collect(no_skill)
    aic_rows = collect(with_skill)
    no_skill_score = score_decisions(pack, no_skill_rows, source="decisions")
    aic_score = score_decisions(pack, aic_rows, source="decisions")
    if [row["id"] for row in no_skill_score["cases"]] != [row["id"] for row in aic_score["cases"]]:
        raise ScoreError("arm case ids diverged")
    paired = {
        field: paired_outcome(_flags(no_skill_score, field), _flags(aic_score, field))
        for field in ("exact", "workflow", "template", "topology")
    }
    report = {
        "arms": {
            ARM_AIC: {"decisions": "aic.jsonl", "score": aic_score, "skill_loaded": True},
            ARM_NO_SKILL: {"decisions": "no-skill.jsonl", "score": no_skill_score, "skill_loaded": False},
        },
        "calls_api": transport == "anthropic-https",
        "context": {
            ARM_AIC: ["closed-catalog", *[path for path, _text in loaded]],
            ARM_NO_SKILL: ["closed-catalog"],
        },
        "date": settings.date,
        "invokes_model": True,
        "kind": "routing-comparison",
        "max_tokens": settings.max_tokens,
        "model": settings.model,
        "model_calls": calls,
        "notes": list(NOTES),
        "paired": paired,
        "population": "flat-cases",
        "scenarios_file": pack.path,
        "schema_version": 1,
        "seed": settings.seed,
        "seed_sent": False,
        "temperature": settings.temperature,
        "timeout_sec": settings.timeout,
        "transport": transport,
    }
    files = {
        "aic.jsonl": _jsonl(aic_rows),
        "no-skill.jsonl": _jsonl(no_skill_rows),
        "report.json": render_report(report),
    }
    return report, files


def _finite_unit(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ScoreError(f"{label} must be a finite number from 0 through 1")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ScoreError(f"{label} must be from 0 through 1")
    return number


def _positive_int(value: int, label: str, *, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= upper:
        raise ScoreError(f"{label} must be an integer from 1 through {upper}")
    return value


def _seed(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2_147_483_647:
        raise ScoreError("seed must be an integer from 0 through 2147483647")
    return value


def _model_id(value: str, key: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip() or any(character.isspace() or ord(character) < 32 for character in value):
        raise ScoreError("model id must be one token")
    if len(value) > 200:
        raise ScoreError("model id is too long")
    if value == key:
        raise ScoreError("model id must not be the API key")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks.routing.compare",
        description=(
            "Run the no-skill and AIC routing arms with one model setting. "
            "Exits 3 when ANTHROPIC_API_KEY is missing or blank."
        ),
    )
    parser.add_argument("--model", help="Model id sent to both arms. Required.")
    parser.add_argument("--output", type=Path, help="New directory for both decision files and the receipt.")
    add_pack_arguments(parser)
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature sent to both arms. Default: 0.")
    parser.add_argument("--max-tokens", type=int, default=1024, help="max_tokens sent to both arms. Default: 1024.")
    parser.add_argument("--seed", type=int, default=0, help="Recorded run seed. The Messages API does not accept it.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-call HTTPS timeout in seconds. Default: 60.")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    client: MessageClient | None = None,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if help_requested(arguments):
        parser.parse_args(arguments)
    env = os.environ if environ is None else environ
    if not credential_present(env):
        print(MISSING_KEY_MESSAGE, file=sys.stderr)
        return EXIT_REFUSED
    args = parser.parse_args(arguments)
    if args.model is None or args.output is None:
        print("A comparison requires --model and --output.", file=sys.stderr)
        return EXIT_USAGE
    key = str(env.get("ANTHROPIC_API_KEY", "")).strip()
    try:
        if isinstance(args.timeout, bool) or not isinstance(args.timeout, (int, float)) or not math.isfinite(float(args.timeout)):
            raise ScoreError("timeout must be a finite number of seconds")
        timeout = float(args.timeout)
        if not 1.0 <= timeout <= 120.0:
            raise ScoreError("timeout must be from 1 through 120 seconds")
        settings = Settings(
            model=_model_id(args.model, key),
            temperature=_finite_unit(args.temperature, "temperature"),
            max_tokens=_positive_int(args.max_tokens, "max_tokens", upper=8192),
            seed=_seed(args.seed),
            timeout=timeout,
            date=utc_date((clock or (lambda: datetime.now(timezone.utc)))()),
        )
        pack = load_pack(selected_pack_path(args.scenarios, args.pack))
        transport = "injected" if client is not None else "anthropic-https"
        sender = client if client is not None else https_client(key, settings.timeout)
        report, files = compare_pack(pack, settings=settings, client=sender, transport=transport)
        _publish(args.output, files)
    except ScoreError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    print(render_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
