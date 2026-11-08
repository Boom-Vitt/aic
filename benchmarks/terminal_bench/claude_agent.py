"""Claude Code agent for the pinned Terminal-Bench revision.

Terminal-Bench imports this class with ``--agent-import-path``. The install
phase has no API key. The agent phase runs on the host, behind the egress
proxy, and is the only process that receives the key. The task container does
not receive ``agent-env.sh``, the key, or a copy of an installed third-party
arm. This module imports Terminal-Bench, so it is loaded only when that
checkout is on ``PYTHONPATH``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from benchmarks.baselines.adapter import AdapterError, load_registry
from benchmarks.budget import format_max_usd, install_environment
from benchmarks.terminal_bench.phases import execute_registry_phase
from terminal_bench.agents.base_agent import AgentResult
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.agents.installed_agents.claude_code.claude_code_agent import (
    ClaudeCodeAgent,
)


def _secret() -> str:
    value = os.environ.get("ANTHROPIC_API_KEY", "")
    return value if isinstance(value, str) else ""


class RegistryClaudeAgent(ClaudeCodeAgent):
    """One registered arm. The dollar cap and turn cap come from the shared budget."""

    def __init__(
        self,
        model_name: str | None = None,
        arm_id: str = "plain-claude-code",
        mount: str = "none",
        plugin_dir: str | None = None,
        home_dir: str | None = None,
        max_turns: int = 30,
        max_budget_usd: object = None,
        seed: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(model_name=model_name, **kwargs)
        self._arm_id = arm_id if isinstance(arm_id, str) else ""
        self._mount = mount if isinstance(mount, str) else ""
        self._plugin_dir = plugin_dir if isinstance(plugin_dir, str) and plugin_dir else None
        self._home_dir = home_dir if isinstance(home_dir, str) and home_dir else None
        self._max_turns = max_turns
        self._max_budget_usd = max_budget_usd
        self._seed = seed
        self._logging_dir: Path | None = None

    @staticmethod
    def name() -> str:
        return "registry-claude"

    @property
    def _env(self) -> dict[str, str]:
        """Install environment. It has no API key; the agent phase reads the key file."""
        return install_environment(self._model_name)

    def _budget_problem(self) -> str | None:
        try:
            registry = load_registry()
            spend = format_max_usd(self._max_budget_usd)
            turns = int(self._max_turns)
        except (TypeError, ValueError) as exc:
            return str(exc)
        except Exception as exc:
            return str(exc)
        budget = registry["budget"]
        if spend != format_max_usd(budget["max_usd"]) or turns != budget["max_turns"]:
            return "agent budget does not match the shared stop."
        if self._seed != registry["seed"]:
            return "agent seed does not match the registry."
        model = (self._model_name or "").removeprefix("anthropic/")
        if model != registry["model"]:
            return "agent model does not match the registry."
        if self._arm_id == "aic" and self._mount != "plugin-dir":
            return "the aic arm must use a plugin directory."
        return None

    def _write_marker(self, *, loaded: bool, plugin_name: str | None, detail: str | None) -> None:
        logging_dir = self._logging_dir
        if logging_dir is None:
            return
        logging_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "arm": self._arm_id,
            "detail": detail,
            "install_has_api_key": False,
            "loaded": loaded and plugin_name == "aic" and self._arm_id == "aic",
            "max_budget_usd": None,
            "max_turns": self._max_turns,
            "model": (self._model_name or "").removeprefix("anthropic/"),
            "plugin_name": plugin_name,
            "seed": self._seed,
        }
        try:
            payload["max_budget_usd"] = format_max_usd(self._max_budget_usd)
            payload["max_turns"] = int(self._max_turns)
        except Exception:
            payload["max_budget_usd"] = None
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        secret = _secret()
        key_file = os.environ.get("AIC_SUITE_KEY_FILE", "")
        if key_file and Path(key_file).is_file() and not Path(key_file).is_symlink():
            try:
                secret = Path(key_file).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                secret = secret
        if secret and secret in text:
            return
        (logging_dir / "arm-load.json").write_text(text, encoding="utf-8")

    def perform_task(self, instruction: str, session, logging_dir: Path | None = None) -> AgentResult:
        self._logging_dir = logging_dir
        problem = self._budget_problem()
        if problem:
            self._write_marker(loaded=False, plugin_name=None, detail=problem)
            return AgentResult(
                total_input_tokens=0,
                total_output_tokens=0,
                failure_mode=FailureMode.UNKNOWN_AGENT_ERROR,
            )
        try:
            outcome = execute_registry_phase(
                instruction=instruction,
                model=self._model_name or "",
                max_turns=int(self._max_turns),
                max_usd=format_max_usd(self._max_budget_usd),
                plugin_dir=self._plugin_dir,
                home_dir=self._home_dir,
                mount=self._mount,
                arm_id=self._arm_id,
                session=session,
                environ=dict(os.environ),
                seed=int(self._seed),
                timeout=int(load_registry()["budget"]["timeout_sec"]),
            )
        except (AdapterError, OSError, ValueError) as exc:
            self._write_marker(loaded=False, plugin_name=None, detail=str(exc))
            return AgentResult(
                total_input_tokens=0,
                total_output_tokens=0,
                failure_mode=FailureMode.UNKNOWN_AGENT_ERROR,
            )
        self._write_marker(
            loaded=bool(outcome["loaded"]),
            plugin_name=outcome.get("plugin_name"),
            detail=None,
        )
        return AgentResult(total_input_tokens=0, total_output_tokens=0)
