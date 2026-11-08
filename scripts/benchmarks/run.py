"""One command for the pinned AIC-versus-baseline comparison.

Dry-run prints the token-budget ceiling and does not call a model. A missing
API key exits 3 before that estimate. The dev pack is the default. heldout-v2
is the release pack. Optional suites are unpriced because their pinned CLIs
have no token budget. aicbench's own report records Claude Code's cost.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from benchmarks.aicbench.runner import main as aicbench_main
from benchmarks.baselines.adapter import AdapterError, load_registry
from benchmarks.baselines.adapter import main as baselines_main
from benchmarks.routing.baseline import load_catalog
from benchmarks.routing.compare import _items, aic_system, main as compare_main, message_body, shared_system, skill_documents
from benchmarks.routing.score import ScoreError, load_pack


class RunError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def require_key() -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or any(character.isspace() or ord(character) < 32 for character in key):
        raise RunError("ANTHROPIC_API_KEY is required.", 3)


ROOT = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"[0-9a-f]{40}")
_CLIP = 1_048_576


def _integer(value: object, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise RunError(f"{label} must be an integer from {low} to {high}.", 2)
    return value


def load_settings(root: Path) -> dict:
    settings = load_json(root / "benchmarks" / "pinned.json")
    if settings.get("schema_version") != 1:
        raise RunError("pinned settings schema_version must be 1.", 2)
    if not isinstance(settings.get("model"), str) or not settings["model"]:
        raise RunError("pinned model id is required.", 2)
    packs = settings.get("routing_packs")
    if not isinstance(packs, dict) or set(packs) != {"dev", "heldout-v2"}:
        raise RunError("pinned routing packs must be dev and heldout-v2.", 2)
    if settings.get("default_routing_pack") != "dev":
        raise RunError("the default routing pack must be dev.", 2)
    for name, relative in packs.items():
        if not isinstance(relative, str) or not relative or relative.startswith("/") or ".." in relative.split("/"):
            raise RunError(f"routing pack path is not relative: {name}", 2)
    limit = _integer(settings.get("max_tokens_limit"), "max_tokens_limit", 1, 4096)
    _integer(settings.get("max_tokens"), "max_tokens", 1, limit)
    pricing = settings.get("pricing")
    if not isinstance(pricing, dict):
        raise RunError("pinned pricing is required.", 2)
    _integer(pricing.get("input_usd_per_million"), "input price", 0, 1000)
    _integer(pricing.get("output_usd_per_million"), "output price", 0, 1000)
    if not isinstance(pricing.get("url"), str) or not pricing["url"].startswith("https://"):
        raise RunError("pinned pricing url must be https.", 2)
    terminal = settings.get("terminal_bench")
    swe = settings.get("swe_bench_lite")
    if not isinstance(terminal, dict) or not isinstance(swe, dict):
        raise RunError("optional suite pins are required.", 2)
    if _integer(terminal.get("n_tasks"), "terminal-bench n_tasks", 1, 1) != 1:
        raise RunError("terminal-bench subset is pinned to 1 task.", 2)
    _integer(terminal.get("n_attempts"), "terminal-bench n_attempts", 1, 1)
    _integer(terminal.get("wall_clock_sec"), "terminal-bench wall clock", 1, 7200)
    _integer(swe.get("max_predictions"), "swe-bench lite max_predictions", 1, 5)
    _integer(swe.get("max_workers"), "swe-bench lite max_workers", 1, 1)
    _integer(swe.get("harness_timeout_sec"), "swe-bench lite harness timeout", 1, 1800)
    _integer(swe.get("wall_clock_sec"), "swe-bench lite wall clock", 1, 7200)
    if terminal.get("token_budget") is not None or swe.get("token_budget") is not None:
        raise RunError("optional suites stay unpriced until their CLI grows a token budget.", 2)
    _integer(settings.get("temperature"), "temperature", 0, 0)
    _integer(settings.get("probe_timeout_sec"), "probe timeout", 1, 120)
    return settings


def load_json(path: Path) -> dict:
    if path.is_symlink():
        raise RunError(f"refusing a symlinked file: {path}", 3)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunError(f"unreadable JSON: {path}", 1) from exc
    if not isinstance(value, dict):
        raise RunError(f"JSON object required: {path}", 1)
    return value


def _usd(input_tokens: int, output_tokens: int, input_rate: int, output_rate: int) -> str:
    millionths = input_tokens * input_rate + output_tokens * output_rate
    return f"{millionths // 1_000_000}.{millionths % 1_000_000:06d}"


def resolve_pack(root: Path, settings: dict, name: str) -> Path:
    relative = settings["routing_packs"].get(name)
    if not isinstance(relative, str):
        raise RunError("routing pack must be dev or heldout-v2.", 2)
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise RunError(f"routing pack {name} is not a real file: {relative}", 2)
    return path


def pack_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_ids() -> list[str]:
    try:
        registry = load_registry()
    except AdapterError as exc:
        raise RunError(str(exc), exc.code) from exc
    return [item["id"] for item in registry["arms"]]


def estimate_for(settings: dict, pack, *, terminal: bool, swe: bool, baselines: bool = False) -> dict:
    pricing = settings["pricing"]
    input_rate = pricing["input_usd_per_million"]
    output_rate = pricing["output_usd_per_million"]
    root = ROOT
    labels = load_catalog(root)
    documents = skill_documents(root)
    systems = (shared_system(labels), aic_system(labels, documents))
    items = _items(pack)
    input_tokens = 0
    for system in systems:
        for item in items:
            body = message_body(
                system=system,
                user=item.user,
                model=settings["model"],
                temperature=float(settings["temperature"]),
                max_tokens=settings["max_tokens"],
            )
            input_tokens += len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    calls = len(items) * 2
    output_tokens = calls * settings["max_tokens"]
    components = [
        {
            "name": "routing",
            "priced": True,
            "calls": calls,
            "input_token_ceiling": input_tokens,
            "output_token_budget": output_tokens,
            "budget_cost_ceiling_usd": _usd(input_tokens, output_tokens, input_rate, output_rate),
        },
        {
            "name": "aicbench",
            "priced": False,
            "token_budget": None,
            "command": "python3 -m benchmarks.aicbench --sandbox container --official",
        },
    ]
    unpriced = ["aicbench"]
    if terminal:
        unpriced.append("terminal-bench")
        components.append({"name": "terminal-bench", "priced": False, "token_budget": None})
    if swe:
        unpriced.append("swe-bench-lite")
        components.append({"name": "swe-bench-lite", "priced": False, "token_budget": None})
    if baselines:
        unpriced.append("baselines")
        components.append({
            "name": "baselines",
            "priced": False,
            "token_budget": None,
            "arms": _baseline_ids(),
            "note": "A live run fetches each git arm at its pinned commit. A dry run does not fetch.",
        })
    return {
        "model": settings["model"],
        "input_token_ceiling": input_tokens,
        "output_token_budget": output_tokens,
        "budget_cost_ceiling_usd": _usd(input_tokens, output_tokens, input_rate, output_rate),
        "input_usd_per_million": input_rate,
        "output_usd_per_million": output_rate,
        "pricing_url": pricing["url"],
        "pricing_checked": pricing["checked"],
        "components": components,
        "unpriced": unpriced,
        "public_benchmark_scores": None,
        "note": (
            "Input uses one token per UTF-8 byte of the JSON body benchmarks.routing.compare would send. "
            "Output uses the pinned max_tokens cap on every routing call. "
            "aicbench is unpriced here because its report uses Claude Code's own cost field. "
            "This is a ceiling, not an invoice."
        ),
    }


def _git_state(root: Path) -> tuple[str, bool]:
    sha_run = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False, capture_output=True, text=True,
    )
    sha = sha_run.stdout.strip()
    if sha_run.returncode != 0 or _SHA.fullmatch(sha) is None:
        raise RunError("git SHA is unavailable.", 1)
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=False, capture_output=True, text=True,
    )
    if status.returncode != 0:
        raise RunError("git status is unavailable.", 1)
    return sha, bool(status.stdout.strip())


def _write_json(path: Path, payload: dict) -> None:
    if path.exists() or path.is_symlink():
        raise RunError(f"refusing to overwrite {path}", 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bundle(root: Path, day: str, sha: str) -> Path:
    results = root / "results"
    if results.is_symlink() or (results.exists() and not results.is_dir()):
        raise RunError("refusing a results path that is not a real directory.", 3)
    target = results / f"{day}-{sha}"
    if target.exists() or target.is_symlink():
        raise RunError(f"refusing to overwrite {target}", 3)
    results.mkdir(exist_ok=True)
    target.mkdir()
    return target


def _checkout_sha(path: Path) -> str:
    if path.is_symlink() or not path.is_dir():
        raise RunError(f"checkout is missing: {path}", 3)
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False, capture_output=True, text=True,
    )
    observed = completed.stdout.strip()
    if completed.returncode != 0 or _SHA.fullmatch(observed) is None:
        raise RunError(f"checkout is not a git repository: {path}", 3)
    return observed


def _prediction_ids(path: Path, limit: int) -> list[str]:
    if path.is_symlink() or not path.is_file():
        raise RunError("SWE-bench Lite predictions file is missing.", 3)
    if path.stat().st_size > _CLIP:
        raise RunError("SWE-bench Lite predictions file is larger than 1 MiB.", 3)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RunError("SWE-bench Lite predictions file is unreadable.", 3) from exc
    ids = []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunError("SWE-bench Lite predictions must be JSONL.", 3) from exc
        if not isinstance(item, dict) or not isinstance(item.get("instance_id"), str):
            raise RunError("each SWE-bench Lite prediction needs an instance_id.", 3)
        instance_id = item["instance_id"]
        if re.fullmatch(r"[A-Za-z0-9._-]{1,200}", instance_id) is None:
            raise RunError("SWE-bench Lite instance id is not a safe token.", 3)
        ids.append(instance_id)
    if not ids or len(ids) > limit:
        raise RunError("SWE-bench Lite predictions must contain 1 to the pinned maximum rows.", 3)
    return ids


def _clip(text: str, secret: str) -> str:
    cleaned = text.replace(secret, "[redacted]") if secret else text
    if len(cleaned) <= _CLIP:
        return cleaned
    return cleaned[:_CLIP] + "\n[truncated]\n"


def _harness(argv: list[str], cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=cwd, env=env, check=False, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return subprocess.CompletedProcess(argv, 124, stdout, stderr or "wall clock exceeded")
    except OSError as exc:
        raise RunError(f"optional harness failed to start: {exc.strerror}", 1) from exc


def _terminal_argv(settings: dict, output: Path, run_id: str) -> list[str]:
    pin = settings["terminal_bench"]
    return [
        sys.executable, "-m", "terminal_bench.cli.tb.main", "run",
        "--dataset", pin["dataset"],
        "--agent", pin["agent"],
        "--model", f"anthropic/{settings['model']}",
        "--n-tasks", str(pin["n_tasks"]),
        "--n-attempts", str(pin["n_attempts"]),
        "--output-path", str(output),
        "--run-id", run_id,
    ]


def _swe_argv(settings: dict, predictions: Path, instance_ids: list[str], run_id: str) -> list[str]:
    pin = settings["swe_bench_lite"]
    return [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", pin["dataset_name"],
        "--split", pin["split"],
        "--predictions_path", str(predictions),
        "--instance_ids", *instance_ids,
        "--max_workers", str(pin["max_workers"]),
        "--timeout", str(pin["harness_timeout_sec"]),
        "--run_id", run_id,
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run-benchmarks")
    parser.add_argument("--routing-pack", choices=("dev", "heldout-v2"), default="dev")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--terminal-bench", action="store_true")
    parser.add_argument("--terminal-bench-checkout", type=Path)
    parser.add_argument("--swe-bench-lite", action="store_true")
    parser.add_argument("--swe-bench-lite-checkout", type=Path)
    parser.add_argument("--swe-bench-lite-predictions", type=Path)
    parser.add_argument(
        "--baselines",
        action="store_true",
        help="Also run every registered baseline arm under the pinned model, budget, and seed.",
    )
    return parser


def _require_revision(path: Path | None, revision: str, reader, missing: str) -> None:
    if path is None or path.is_symlink() or not path.is_dir():
        raise RunError(missing, 3)
    if reader(path) != revision:
        raise RunError("checkout is not the pinned revision.", 3)


def execute(
    args: argparse.Namespace,
    *,
    root: Path = ROOT,
    client=None,
    sandbox_runner=None,
    harness_runner=None,
    today: date | None = None,
    results_root: Path | None = None,
    revision_reader=None,
    compare_runner=None,
    aicbench_runner=None,
    baseline_runner=None,
) -> int:
    require_key()
    if args.terminal_bench_checkout and not args.terminal_bench:
        raise RunError("--terminal-bench-checkout requires --terminal-bench.", 2)
    if (args.swe_bench_lite_checkout or args.swe_bench_lite_predictions) and not args.swe_bench_lite:
        raise RunError("SWE-bench Lite paths require --swe-bench-lite.", 2)
    settings = load_settings(root)
    pack_path = resolve_pack(root, settings, args.routing_pack)
    digest = pack_sha256(pack_path)
    pack = load_pack(pack_path)
    estimate = estimate_for(
        settings, pack, terminal=args.terminal_bench, swe=args.swe_bench_lite, baselines=args.baselines,
    )
    estimate["routing_pack"] = args.routing_pack
    estimate["routing_pack_sha256"] = digest
    print(json.dumps(estimate, indent=2, sort_keys=True), flush=True)
    if args.dry_run:
        return 0
    secret = os.environ.get("ANTHROPIC_API_KEY", "")
    sha, dirty = _git_state(root)
    day = (today or datetime.now(timezone.utc).date()).isoformat()
    bundle = _bundle(results_root or root, day, sha)
    provenance = {
        "git_sha": sha,
        "worktree_dirty": dirty,
        "date": day,
        "model": settings["model"],
        "seed": settings["seed"],
        "seed_sent_to_provider": settings["seed_sent_to_provider"],
        "routing_pack": args.routing_pack,
        "routing_pack_path": settings["routing_packs"][args.routing_pack],
        "routing_pack_sha256": digest,
        "settings": settings,
        "commands": [
            "python3 -m benchmarks.routing.compare --pack " + settings["routing_packs"][args.routing_pack],
            "python3 -m benchmarks.aicbench --sandbox container --official",
        ],
        "completed": False,
        "public_benchmark_scores": None,
    }
    if args.terminal_bench:
        provenance["commands"].append("terminal-bench subset")
    if args.swe_bench_lite:
        provenance["commands"].append("swe-bench-lite subset")
    if args.baselines:
        provenance["commands"].append("python3 -m benchmarks.baselines live")
    _write_json(bundle / "provenance.json", provenance)
    _write_json(bundle / "estimate.json", estimate)
    reader = revision_reader or _checkout_sha
    try:
        if args.terminal_bench:
            _require_revision(
                args.terminal_bench_checkout, settings["terminal_bench"]["revision"], reader,
                "terminal-bench requires --terminal-bench-checkout at the pinned revision.",
            )
        if args.swe_bench_lite:
            if args.swe_bench_lite_predictions is None:
                raise RunError("swe-bench-lite requires a pinned checkout and a predictions file.", 3)
            _require_revision(
                args.swe_bench_lite_checkout, settings["swe_bench_lite"]["revision"], reader,
                "swe-bench-lite requires a pinned checkout and a predictions file.",
            )
            _prediction_ids(args.swe_bench_lite_predictions, settings["swe_bench_lite"]["max_predictions"])
    except RunError as exc:
        _write_json(bundle / "receipts" / "blocked.json", {
            "executed": False,
            "stopped_before_model": True,
            "public_benchmark_scores": None,
            "reason": str(exc),
        })
        raise
    (bundle / "raw").mkdir()
    compare_argv = [
        "--model", settings["model"],
        "--output", str(bundle / "raw" / "routing"),
        "--pack", str(pack_path),
        "--max-tokens", str(settings["max_tokens"]),
        "--seed", str(settings["seed"]),
        "--temperature", str(settings["temperature"]),
        "--timeout", "60",
    ]
    if secret and secret in compare_argv:
        raise RunError("refusing to put the API key on a command line.", 1)
    compare_call = compare_runner or compare_main
    captured = StringIO()
    with redirect_stdout(captured):
        compare_code = compare_call(compare_argv, client=client, environ=os.environ)
    (bundle / "raw" / "routing-stdout.txt").write_text(_clip(captured.getvalue(), secret), encoding="utf-8")
    if compare_code != 0:
        return compare_code
    aicbench_call = aicbench_runner or aicbench_main
    aicbench_argv = [
        "--sandbox", "container",
        "--official",
        "--model", settings["model"],
        "--output", str(bundle / "receipts" / "aicbench.json"),
    ]
    if secret and secret in aicbench_argv:
        raise RunError("refusing to put the API key on a command line.", 1)
    aicbench_code = aicbench_call(aicbench_argv, environ=os.environ)
    if aicbench_code != 0:
        return aicbench_code
    if args.baselines:
        baseline_argv = [
            "live",
            "--model", settings["model"],
            "--output", str(bundle / "receipts" / "baselines.json"),
            "--task", "bugfix-ledger-signs",
        ]
        if secret and secret in baseline_argv:
            raise RunError("refusing to put the API key on a command line.", 1)
        baseline_call = baseline_runner or baselines_main
        baseline_code = baseline_call(baseline_argv, environ=os.environ)
        if baseline_code != 0:
            return baseline_code
    runner = harness_runner or _harness
    run_id = f"aic-{day}-{sha[:12]}"
    if args.terminal_bench:
        output = bundle / "raw" / "terminal-bench"
        output.mkdir(parents=True)
        argv = _terminal_argv(settings, output, run_id)
        if secret and secret in argv:
            raise RunError("refusing to put the API key on a command line.", 1)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(args.terminal_bench_checkout) + os.pathsep + env.get("PYTHONPATH", "")
        completed = runner(argv, args.terminal_bench_checkout, env, settings["terminal_bench"]["wall_clock_sec"])
        receipt = {
            "executed": completed.returncode == 0,
            "exit_code": completed.returncode,
            "aic_treatment": False,
            "public_benchmark_scores": None,
            "command": argv,
            "revision": settings["terminal_bench"]["revision"],
        }
        _write_json(bundle / "receipts" / "terminal-bench.json", receipt)
        (output / "stdout.txt").write_text(_clip(completed.stdout or "", secret), encoding="utf-8")
        (output / "stderr.txt").write_text(_clip(completed.stderr or "", secret), encoding="utf-8")
        if completed.returncode != 0:
            return 1
    if args.swe_bench_lite:
        predictions = args.swe_bench_lite_predictions
        ids = _prediction_ids(predictions, settings["swe_bench_lite"]["max_predictions"])
        argv = _swe_argv(settings, predictions, ids, run_id)
        if secret and secret in argv:
            raise RunError("refusing to put the API key on a command line.", 1)
        output = bundle / "raw" / "swe-bench-lite"
        output.mkdir(parents=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(args.swe_bench_lite_checkout) + os.pathsep + env.get("PYTHONPATH", "")
        completed = runner(argv, args.swe_bench_lite_checkout, env, settings["swe_bench_lite"]["wall_clock_sec"])
        receipt = {
            "executed": completed.returncode == 0,
            "exit_code": completed.returncode,
            "aic_treatment": False,
            "instance_count": len(ids),
            "public_benchmark_scores": None,
            "command": argv,
            "revision": settings["swe_bench_lite"]["revision"],
        }
        _write_json(bundle / "receipts" / "swe-bench-lite.json", receipt)
        (output / "stdout.txt").write_text(_clip(completed.stdout or "", secret), encoding="utf-8")
        (output / "stderr.txt").write_text(_clip(completed.stderr or "", secret), encoding="utf-8")
        if completed.returncode != 0:
            return 1
    provenance["completed"] = True
    (bundle / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return 0


def main(
    argv: list[str] | None = None,
    *,
    client=None,
    sandbox_runner=None,
    harness_runner=None,
    today: date | None = None,
    results_root: Path | None = None,
    revision_reader=None,
    compare_runner=None,
    aicbench_runner=None,
    baseline_runner=None,
) -> int:
    args = _parser().parse_args(argv)
    try:
        return execute(
            args,
            client=client,
            harness_runner=harness_runner,
            today=today,
            results_root=results_root,
            revision_reader=revision_reader,
            compare_runner=compare_runner,
            aicbench_runner=aicbench_runner,
            baseline_runner=baseline_runner,
        )
    except (RunError, ScoreError) as exc:
        print(str(exc), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
