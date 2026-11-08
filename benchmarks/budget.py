"""Shared comparison budget.

``max_usd`` is a stop rule. It is not a prediction of what a run will cost
and it is not a public score. Official comparisons refuse a null cap.
"""
from __future__ import annotations

import shlex


ALLOWED_TOOLS = "Read,Edit,Write,Bash,AskUserQuestion"
# One cent is 10_000 millionths of a dollar. Prices are USD per million tokens.
_CENT_MILLIONTHS = 10_000


class BudgetError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BudgetError(f"{label} must be a positive integer.")
    return value


def dollar_stop(
    *,
    max_turns: int,
    timeout_sec: int,
    max_tokens: int,
    input_usd_per_million: int,
    output_usd_per_million: int,
) -> dict[str, object]:
    """Price a token allowance and round the product up to the next cent.

    Input allowance: ``max_turns * timeout_sec`` tokens. That reuses the
    wall-clock stop as one token per second on every turn. It is not a
    measured tokenizer rate.

    Output allowance: ``max_turns * max_tokens`` tokens, the pinned
    completion cap on every turn.

    Both allowances use the pinned base rates. Cache and batch discounts
    are not applied. The sent cap is the ceiling in cents so the stop is
    not below the priced allowance.
    """
    turns = _positive_int(max_turns, "max_turns")
    timeout = _positive_int(timeout_sec, "timeout_sec")
    tokens = _positive_int(max_tokens, "max_tokens")
    input_rate = _positive_int(input_usd_per_million, "input price")
    output_rate = _positive_int(output_usd_per_million, "output price")
    input_tokens = turns * timeout
    output_tokens = turns * tokens
    millionths = input_tokens * input_rate + output_tokens * output_rate
    cents = (millionths + _CENT_MILLIONTHS - 1) // _CENT_MILLIONTHS
    return {
        "input_token_allowance": input_tokens,
        "output_token_allowance": output_tokens,
        "exact_usd_millionths": millionths,
        "max_usd_cents": cents,
        "max_usd": f"{cents // 100}.{cents % 100:02d}",
        "input_usd_per_million": input_rate,
        "output_usd_per_million": output_rate,
        "max_turns": turns,
        "timeout_sec": timeout,
        "max_tokens": tokens,
    }


def format_max_usd(value: object) -> str:
    """Render a positive dollar cap as cents. Null and zero are refused."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BudgetError("max_usd must be a positive number of dollars. Official comparisons do not accept null.")
    cents = int(round(float(value) * 100))
    if cents < 1 or abs(float(value) * 100 - cents) > 1e-6:
        raise BudgetError("max_usd must be a positive number of cents.")
    return f"{cents // 100}.{cents % 100:02d}"


def shared_stop(settings: dict, budget: dict) -> dict[str, object]:
    pricing = settings.get("pricing")
    if not isinstance(pricing, dict):
        raise BudgetError("pinned pricing is required.")
    if not isinstance(budget, dict):
        raise BudgetError("baseline budget is required.")
    return dollar_stop(
        max_turns=budget.get("max_turns"),
        timeout_sec=budget.get("timeout_sec"),
        max_tokens=settings.get("max_tokens"),
        input_usd_per_million=pricing.get("input_usd_per_million"),
        output_usd_per_million=pricing.get("output_usd_per_million"),
    )


def install_environment(model_name: str | None) -> dict[str, str]:
    """Environment for a suite install phase. It has no API key."""
    env = {
        "FORCE_AUTO_BACKGROUND_TASKS": "1",
        "ENABLE_BACKGROUND_TASKS": "1",
    }
    if model_name:
        if not isinstance(model_name, str) or "\x00" in model_name or any(character.isspace() for character in model_name):
            raise BudgetError("model name must be one token.")
        env["ANTHROPIC_MODEL"] = model_name.removeprefix("anthropic/")
    return env


def agent_env_script(key: str) -> str:
    """Shell assignment for the agent phase. Callers copy the file; they do not pass the key as an argument."""
    if not isinstance(key, str) or not key or any(character.isspace() or ord(character) < 32 for character in key):
        raise BudgetError("refusing an empty or whitespace API key.")
    return "export ANTHROPIC_API_KEY=" + shlex.quote(key) + "\n"


def claude_shell(
    instruction: str,
    *,
    model: str,
    max_turns: int,
    max_usd: str,
    plugin_dir: str | None,
    tools: str = ALLOWED_TOOLS,
) -> str:
    """One Claude Code command. The API key is not an argument."""
    if not isinstance(instruction, str) or "\x00" in instruction:
        raise BudgetError("the instruction must be text.")
    if not isinstance(model, str) or not model or model.startswith("-") or any(character.isspace() or character == "\x00" for character in model):
        raise BudgetError("the model must be one token.")
    turns = _positive_int(max_turns, "max_turns")
    spend = format_max_usd(max_usd) if not isinstance(max_usd, str) else max_usd
    if spend != format_max_usd(float(spend)):
        raise BudgetError("max_usd must be a positive number of cents.")
    if tools != ALLOWED_TOOLS:
        raise BudgetError("suite arms share one tool list.")
    argv = [
        "claude",
        "--bare",
        "-p",
        instruction,
        "--output-format",
        "stream-json",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        tools,
        "--max-turns",
        str(turns),
        "--max-budget-usd",
        spend,
        "--model",
        model.removeprefix("anthropic/"),
    ]
    if plugin_dir is not None:
        if not isinstance(plugin_dir, str) or not plugin_dir.startswith("/") or "\x00" in plugin_dir:
            raise BudgetError("plugin directory must be an absolute path.")
        argv.extend(["--plugin-dir", plugin_dir])
    return " ".join(shlex.quote(part) for part in argv)
