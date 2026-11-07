"""Score routing decisions against the held-out pack.

Decisions come from a JSONL file written by an agent or harness, or from
``benchmarks.routing.router.route_scenario`` when that function exists.
This module does not infer a workflow from request text.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import errno
import importlib
import json
import math
import os
from pathlib import Path
import stat
import statistics
import sys


EXIT_USAGE = 2
EXIT_REFUSED = 3
MAX_BYTES = 1_048_576
MAX_LINES = 10_000
MAX_ID = 200
MAX_LABEL = 100
MAX_TEXT = 4_000
MAX_ITEMS = 64
FIELDS = ("workflow", "template", "topology")
NESTS = ("decision", "plan", "recommendation", "structured_output")
Z95 = statistics.NormalDist().inv_cdf(0.975)
NO_ROUTER = (
    "This repository does not ship a deterministic task router. "
    "Pass a JSONL decision file. No labels were inferred."
)
NOTES = (
    "Counts come only from the decision file and the held-out fixture.",
    "A missing prediction is incorrect. It is not counted as a precision trial.",
    "Precision, recall, and accuracy are micro-averaged over one gold label per item.",
    "When every item has a prediction, those three proportions are equal.",
    "The Wilson 95 percent interval uses the 0.975 standard-normal quantile. A zero trial count has no interval.",
    "Flat cases and the project case are separate populations.",
    "Request text is not classified and is not copied into this report.",
)


class ScoreError(ValueError):
    def __init__(self, message: str, code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Labels:
    workflow: str | None
    template: str | None
    topology: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {"workflow": self.workflow, "template": self.template, "topology": self.topology}

    def complete(self) -> str | None:
        if self.workflow is None or self.template is None or self.topology is None:
            return None
        return f"{self.workflow}\t{self.template}\t{self.topology}"


@dataclass(frozen=True)
class Case:
    id: str
    request: str
    workflow: str
    template: str
    topology: str

    def gold(self) -> Labels:
        return Labels(self.workflow, self.template, self.topology)


@dataclass(frozen=True)
class Stage:
    id: str
    workflow: str
    template: str
    topology: str

    def gold(self) -> Labels:
        return Labels(self.workflow, self.template, self.topology)


@dataclass(frozen=True)
class ProjectCase:
    id: str
    request: str
    milestones: tuple[str, ...]
    invariants: tuple[str, ...]
    stages: tuple[Stage, ...]


@dataclass(frozen=True)
class Pack:
    path: str
    cases: tuple[Case, ...]
    project: ProjectCase | None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_scenarios_path() -> Path:
    return repo_root() / "tests" / "fixtures" / "routing-scenarios.json"


def binomial_summary(successes: int, trials: int) -> dict[str, object]:
    """Wilson score interval for ``successes`` out of ``trials``.

    ``trials == 0`` has no rate and no interval. The normal quantile is
    ``statistics.NormalDist().inv_cdf(0.975)``. When every trial succeeds or
    none do, the floating-point edge is snapped back to 1 or 0.
    """
    if type(successes) is not int or type(trials) is not int:
        raise ScoreError("binomial counts must be integers")
    if successes < 0 or trials < 0 or successes > trials:
        raise ScoreError("binomial counts are out of range")
    if trials == 0:
        return {"k": 0, "n": 0, "rate": None, "wilson95": None}
    phat = successes / trials
    z2 = Z95 * Z95
    denominator = 1.0 + z2 / trials
    center = phat + z2 / (2.0 * trials)
    margin = Z95 * math.sqrt(phat * (1.0 - phat) / trials + z2 / (4.0 * trials * trials))
    low = (center - margin) / denominator
    high = (center + margin) / denominator
    if successes == 0:
        low = 0.0
    if successes == trials:
        high = 1.0
    low = min(1.0, max(0.0, low))
    high = min(1.0, max(0.0, high))
    return {
        "k": successes,
        "n": trials,
        "rate": phat,
        "wilson95": {"confidence": 0.95, "z": Z95, "low": low, "high": high},
    }


def _refuse_symlink(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise ScoreError(f"refusing a symlinked file: {path}", EXIT_REFUSED)


def read_text(path: Path, *, limit: int = MAX_BYTES) -> str:
    _refuse_symlink(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ScoreError(f"file not found: {path}", EXIT_USAGE) from exc
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EEXIST):
            raise ScoreError(f"refusing a symlinked file: {path}", EXIT_REFUSED) from exc
        raise ScoreError(f"cannot read {path}", EXIT_USAGE) from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ScoreError(f"file must be a regular file: {path}", EXIT_USAGE)
        if info.st_size > limit:
            raise ScoreError(f"file exceeds {limit} bytes: {path}", EXIT_USAGE)
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            block = os.read(descriptor, min(remaining, 1024 * 1024))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        data = b"".join(chunks)
    finally:
        os.close(descriptor)
    if len(data) > limit:
        raise ScoreError(f"file exceeds {limit} bytes: {path}", EXIT_USAGE)
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise ScoreError(f"file is not UTF-8: {path}", EXIT_USAGE) from exc
    if text.startswith("\ufeff"):
        raise ScoreError(f"refusing a byte-order mark: {path}", EXIT_USAGE)
    return text


def write_exclusive(path: Path, text: str) -> None:
    _refuse_symlink(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise ScoreError(f"refusing to overwrite {path}", EXIT_REFUSED) from exc
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EEXIST):
            raise ScoreError(f"refusing to overwrite {path}", EXIT_REFUSED) from exc
        raise ScoreError(f"cannot write {path}", EXIT_USAGE) from exc
    try:
        view = memoryview(text.encode("utf-8"))
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(errno.EIO, "short write")
            view = view[written:]
        os.fsync(descriptor)
    except OSError as exc:
        os.close(descriptor)
        try:
            os.unlink(path)
        except OSError:
            pass
        raise ScoreError(f"cannot write {path}", EXIT_USAGE) from exc
    os.close(descriptor)


def _text(value: object, label: str, *, limit: int) -> str:
    if type(value) is not str or value == "" or value != value.strip():
        raise ScoreError(f"{label} must be a nonempty string")
    if len(value) > limit or any(ord(character) < 32 for character in value):
        raise ScoreError(f"{label} is too long or contains a control character")
    return value


def _object(value: object, label: str) -> dict:
    if type(value) is not dict:
        raise ScoreError(f"{label} must be an object")
    return value


def _strings(value: object, label: str, *, limit: int = MAX_TEXT) -> tuple[str, ...]:
    if type(value) is not list:
        raise ScoreError(f"{label} must be a list of strings")
    if len(value) > MAX_ITEMS:
        raise ScoreError(f"{label} has too many entries")
    items = tuple(_text(item, label, limit=limit) for item in value)
    if len(set(items)) != len(items):
        raise ScoreError(f"{label} contains a duplicate")
    return items


def _labels_from(sources: list[Mapping[str, object]]) -> Labels:
    found: dict[str, str | None] = {}
    for field in FIELDS:
        values: list[str] = []
        for source in sources:
            if field not in source or source[field] is None:
                continue
            values.append(_text(source[field], field, limit=MAX_LABEL))
        distinct = set(values)
        if len(distinct) > 1:
            raise ScoreError(f"conflicting {field} values")
        found[field] = values[0] if values else None
    return Labels(found["workflow"], found["template"], found["topology"])


def _sources(row: Mapping[str, object]) -> list[Mapping[str, object]]:
    sources: list[Mapping[str, object]] = [row]
    for key in NESTS:
        if key not in row:
            continue
        sources.append(_object(row[key], key))
    return sources


def extract_labels(row: Mapping[str, object]) -> Labels:
    return _labels_from(_sources(row))


def _optional_strings(row: Mapping[str, object], key: str) -> tuple[str, ...] | None:
    if key not in row:
        return None
    return _strings(row[key], key)


def load_pack(path: Path) -> Pack:
    try:
        body = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise ScoreError(f"scenarios file is not JSON: {path}", EXIT_USAGE) from exc
    root = _object(body, "scenarios file")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 3:
        raise ScoreError("scenarios schema_version must be 3")
    raw_cases = root.get("cases")
    if type(raw_cases) is not list:
        raise ScoreError("scenarios cases must be a list")
    if len(raw_cases) > MAX_ITEMS * 4:
        raise ScoreError("scenarios case list is too long")
    cases: list[Case] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_cases):
        item = _object(raw, f"cases[{index}]")
        ident = _text(item.get("id"), "case id", limit=MAX_ID)
        if ident in seen:
            raise ScoreError(f"duplicate scenario id: {ident}")
        seen.add(ident)
        cases.append(
            Case(
                id=ident,
                request=_text(item.get("request"), "request", limit=MAX_TEXT),
                workflow=_text(item.get("expected_workflow"), "expected_workflow", limit=MAX_LABEL),
                template=_text(item.get("expected_template"), "expected_template", limit=MAX_LABEL),
                topology=_text(item.get("expected_topology"), "expected_topology", limit=MAX_LABEL),
            )
        )
    project = _project(root.get("project_case"), seen) if "project_case" in root else None
    return Pack(path=str(path), cases=tuple(cases), project=project)


def _project(value: object, case_ids: set[str]) -> ProjectCase:
    item = _object(value, "project_case")
    ident = _text(item.get("id"), "project id", limit=MAX_ID)
    if ident in case_ids:
        raise ScoreError(f"project id repeats a case id: {ident}")
    raw_stages = item.get("stages")
    if type(raw_stages) is not list or not raw_stages:
        raise ScoreError("project_case stages must be a nonempty list")
    if len(raw_stages) > MAX_ITEMS:
        raise ScoreError("project_case has too many stages")
    stages: list[Stage] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_stages):
        stage = _object(raw, f"stages[{index}]")
        stage_id = _text(stage.get("id"), "stage id", limit=MAX_ID)
        if stage_id in seen:
            raise ScoreError(f"duplicate stage id: {stage_id}")
        seen.add(stage_id)
        stages.append(
            Stage(
                id=stage_id,
                workflow=_text(stage.get("expected_workflow"), "expected_workflow", limit=MAX_LABEL),
                template=_text(stage.get("expected_template"), "expected_template", limit=MAX_LABEL),
                topology=_text(stage.get("expected_topology"), "expected_topology", limit=MAX_LABEL),
            )
        )
    return ProjectCase(
        id=ident,
        request=_text(item.get("request"), "request", limit=MAX_TEXT),
        milestones=_strings(item.get("required_milestones"), "required_milestones"),
        invariants=_strings(item.get("required_invariants"), "required_invariants"),
        stages=tuple(stages),
    )


def parse_jsonl(text: str) -> list[dict]:
    if text.startswith("\ufeff"):
        raise ScoreError("refusing a byte-order mark in the decision file")
    rows: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if lineno > MAX_LINES:
            raise ScoreError("decision file has too many lines")
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScoreError(f"decision line {lineno} is not JSON") from exc
        rows.append(_object(value, f"decision line {lineno}"))
    return rows


def _known_ids(pack: Pack) -> set[str]:
    known = {case.id for case in pack.cases}
    if pack.project is not None:
        known.add(pack.project.id)
    return known


def index_decisions(pack: Pack, rows: list[dict]) -> dict[str, dict]:
    known = _known_ids(pack)
    indexed: dict[str, dict] = {}
    for row in rows:
        ident = _text(row.get("id"), "decision id", limit=MAX_ID)
        if ident in indexed:
            raise ScoreError(f"duplicate decision id: {ident}")
        if ident not in known:
            raise ScoreError(f"unknown decision id: {ident}")
        indexed[ident] = row
    return indexed


def _stage_predictions(row: Mapping[str, object] | None, expected: set[str]) -> dict[str, Labels]:
    if row is None or "stages" not in row:
        return {}
    raw = row["stages"]
    if type(raw) is not list:
        raise ScoreError("stages must be a list")
    if len(raw) > MAX_ITEMS:
        raise ScoreError("stages has too many entries")
    found: dict[str, Labels] = {}
    for index, item in enumerate(raw):
        stage = _object(item, f"stages[{index}]")
        ident = _text(stage.get("id"), "stage id", limit=MAX_ID)
        if ident not in expected:
            raise ScoreError(f"unknown stage id: {ident}")
        if ident in found:
            raise ScoreError(f"duplicate stage id: {ident}")
        found[ident] = extract_labels(stage)
    return found


def _correct(gold: Labels, predicted: Labels) -> dict[str, bool]:
    fields = {
        "workflow": predicted.workflow == gold.workflow,
        "template": predicted.template == gold.template,
        "topology": predicted.topology == gold.topology,
    }
    return {"exact": all(fields.values()), **fields}


def _micro(golds: list[str], predictions: list[str | None]) -> dict[str, dict[str, object]]:
    success = 0
    predicted = 0
    for gold, guess in zip(golds, predictions, strict=True):
        if guess is None:
            continue
        predicted += 1
        if guess == gold:
            success += 1
    total = len(golds)
    return {
        "accuracy": binomial_summary(success, total),
        "precision": binomial_summary(success, predicted),
        "recall": binomial_summary(success, total),
    }


def _per_class(golds: list[str], predictions: list[str | None]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label in sorted(set(golds)):
        true_positive = 0
        false_positive = 0
        false_negative = 0
        for gold, guess in zip(golds, predictions, strict=True):
            if gold == label and guess == label:
                true_positive += 1
            elif guess == label and gold != label:
                false_positive += 1
            elif gold == label and guess != label:
                false_negative += 1
        rows.append(
            {
                "fn": false_negative,
                "fp": false_positive,
                "label": label,
                "precision": binomial_summary(true_positive, true_positive + false_positive),
                "recall": binomial_summary(true_positive, true_positive + false_negative),
                "tp": true_positive,
            }
        )
    return rows


def _field_metrics(golds: list[Labels], predictions: list[Labels]) -> dict[str, object]:
    exact_gold = [gold.complete() or "" for gold in golds]
    exact_predicted: list[str | None] = [guess.complete() for guess in predictions]
    if any(item == "" for item in exact_gold):
        raise ScoreError("a gold label is missing")
    metrics: dict[str, object] = {
        "exact": _micro(exact_gold, exact_predicted),
    }
    classes: dict[str, object] = {"exact": _per_class(exact_gold, exact_predicted)}
    for field in FIELDS:
        field_gold = [getattr(gold, field) for gold in golds]
        field_predicted = [getattr(guess, field) for guess in predictions]
        metrics[field] = _micro(field_gold, field_predicted)
        classes[field] = _per_class(field_gold, field_predicted)
    return {"metrics": metrics, "per_class": classes}


def _set_check(required: tuple[str, ...], supplied: tuple[str, ...] | None) -> dict[str, object]:
    if supplied is None:
        return {"correct": False, "extra": [], "missing": list(required)}
    missing = sorted(set(required) - set(supplied))
    extra = sorted(set(supplied) - set(required))
    return {"correct": not missing and not extra, "extra": extra, "missing": missing}


def _case_row(case: Case, predicted: Labels) -> dict[str, object]:
    return {
        "correct": _correct(case.gold(), predicted),
        "expected": case.gold().as_dict(),
        "id": case.id,
        "predicted": predicted.as_dict(),
    }


def score_decisions(pack: Pack, rows: list[dict], *, source: str) -> dict[str, object]:
    if source not in ("decisions", "router"):
        raise ScoreError("unknown decision source")
    indexed = index_decisions(pack, rows)
    predicted_cases: list[Labels] = []
    case_rows: list[dict[str, object]] = []
    for case in pack.cases:
        row = indexed.get(case.id)
        labels = extract_labels(row) if row is not None else Labels(None, None, None)
        predicted_cases.append(labels)
        case_rows.append(_case_row(case, labels))
    flat = _field_metrics([case.gold() for case in pack.cases], predicted_cases)
    return {
        "cases": case_rows,
        "decision_count": len(rows),
        "interval": "wilson-score-95",
        "invokes_model": False,
        "kind": "routing-score",
        "metrics": flat["metrics"],
        "notes": list(NOTES),
        "per_class": flat["per_class"],
        "population": "flat-cases",
        "project_case": _project_report(pack.project, indexed.get(pack.project.id) if pack.project else None),
        "scenarios_file": pack.path,
        "schema_version": 1,
        "source": source,
    }


def _project_report(project: ProjectCase | None, row: dict | None) -> dict[str, object] | None:
    if project is None:
        return None
    expected_ids = {stage.id for stage in project.stages}
    chosen = _stage_predictions(row, expected_ids)
    golds = [stage.gold() for stage in project.stages]
    predictions = [chosen.get(stage.id, Labels(None, None, None)) for stage in project.stages]
    summary = _field_metrics(golds, predictions)
    milestones = _optional_strings(row, "milestones") if row is not None else None
    invariants = _optional_strings(row, "invariants") if row is not None else None
    return {
        "id": project.id,
        "invariants": _set_check(project.invariants, invariants),
        "metrics": summary["metrics"],
        "milestones": _set_check(project.milestones, milestones),
        "per_class": summary["per_class"],
        "present": row is not None,
        "stages": [
            {
                "correct": _correct(stage.gold(), prediction),
                "expected": stage.gold().as_dict(),
                "id": stage.id,
                "predicted": prediction.as_dict(),
            }
            for stage, prediction in zip(project.stages, predictions, strict=True)
        ],
    }


def load_router() -> Callable[[Mapping[str, str]], Mapping[str, object]] | None:
    """Return the repository router, if a later change adds one.

    AIC validates recommendations. It does not ship a task classifier, so
    this returns None unless ``benchmarks.routing.router.route_scenario`` exists.
    """
    try:
        module = importlib.import_module("benchmarks.routing.router")
    except ModuleNotFoundError:
        return None
    except Exception as exc:
        raise ScoreError("deterministic router failed to import") from exc
    route = getattr(module, "route_scenario", None)
    if not callable(route):
        return None
    return route


def decisions_from_router(pack: Pack, route: Callable[[Mapping[str, str]], Mapping[str, object]]) -> list[dict]:
    """Ask a router for labels. The router sees id and request, never the gold fields."""
    exposed_rows: list[tuple[str, str]] = [(case.id, case.request) for case in pack.cases]
    if pack.project is not None:
        exposed_rows.append((pack.project.id, pack.project.request))
    rows: list[dict] = []
    for ident, request in exposed_rows:
        exposed = {"id": ident, "request": request}
        try:
            decision = route(exposed)
        except ScoreError:
            raise
        except Exception as exc:
            raise ScoreError(f"deterministic router failed for {ident}") from exc
        body = _object(decision, f"router decision for {ident}")
        if "id" in body and body["id"] != ident:
            raise ScoreError(f"deterministic router changed the id for {ident}")
        row = {key: value for key, value in body.items() if key != "id"}
        row["id"] = ident
        rows.append(row)
    return rows


def render_report(report: dict[str, object]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks.routing.score",
        description="Score a JSONL routing decision file against the held-out pack. No model is called.",
    )
    parser.add_argument("--decisions", type=Path, help="JSONL decisions, one object per line.")
    parser.add_argument(
        "--from-router",
        action="store_true",
        help="Score benchmarks.routing.router when that module exists. It does not in this repository.",
    )
    parser.add_argument("--scenarios", type=Path, help="Routing pack JSON. Defaults to the held-out fixture.")
    parser.add_argument("--output", type=Path, help="Write the JSON report here. Refuses to overwrite.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.from_router == (args.decisions is not None):
        parser.error("Pass either --decisions FILE or --from-router.")
    try:
        pack = load_pack(args.scenarios if args.scenarios is not None else default_scenarios_path())
        if args.from_router:
            route = load_router()
            if route is None:
                print(NO_ROUTER, file=sys.stderr)
                return EXIT_USAGE
            rows = decisions_from_router(pack, route)
            source = "router"
        else:
            rows = parse_jsonl(read_text(args.decisions))
            source = "decisions"
        report = score_decisions(pack, rows, source=source)
        text = render_report(report)
        if args.output is not None:
            write_exclusive(args.output, text)
    except ScoreError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
