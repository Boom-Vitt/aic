"""Claude Code agent for the pinned Terminal-Bench revision.

Terminal-Bench imports this class with ``--agent-import-path``. The install
phase environment has no API key. The agent phase reads the key from a file
copied into the container, not from a command argument. This module imports
Terminal-Bench, so it is loaded only when that checkout is on ``PYTHONPATH``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from benchmarks.baselines.adapter import load_registry
from benchmarks.budget import agent_env_script, claude_shell, format_max_usd, install_environment
from terminal_bench.agents.base_agent import AgentResult
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.agents.installed_agents.claude_code.claude_code_agent import (
    ClaudeCodeAgent,
)
from terminal_bench.terminal.models import TerminalCommand


_AGENT_PREFIX = ". /installed-agent/agent-env.sh && "
_MAX_COPY_BYTES = 1_000_000


def _secret() -> str:
    value = os.environ.get("ANTHROPIC_API_KEY", "")
    return value if isinstance(value, str) else ""


def _contains_secret(path: Path, secret: str) -> bool:
    if not secret or not path.exists():
        return False
    for child in path.rglob("*"):
        if child.is_symlink() or not child.is_file():
            continue
        try:
            if child.stat().st_size > _MAX_COPY_BYTES:
                return True
            blob = child.read_bytes()
        except OSError:
            return True
        if secret.encode() in blob:
            return True
    return False


def _plugin_name(path: Path) -> str | None:
    manifest = path / ".claude-plugin" / "plugin.json"
    if manifest.is_symlink() or not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    name = payload.get("name") if isinstance(payload, dict) else None
    if not isinstance(name, str) or not name:
        return None
    return name


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
        self._session = None
        self._logging_dir: Path | None = None

    @staticmethod
    def name() -> str:
        return "registry-claude"

    @property
    def _env(self) -> dict[str, str]:
        return install_environment(self._model_name)

    def _budget_problem(self) -> str | None:
        try:
            registry = load_registry()
            spend = format_max_usd(self._max_budget_usd)
        except Exception as exc:
            return str(exc)
        budget = registry["budget"]
        if spend != format_max_usd(budget["max_usd"]) or self._max_turns != budget["max_turns"]:
            return "agent budget does not match the shared stop."
        if self._seed != registry["seed"]:
            return "agent seed does not match the registry."
        model = (self._model_name or "").removeprefix("anthropic/")
        if model != registry["model"]:
            return "agent model does not match the registry."
        if self._arm_id == "aic" and self._mount != "plugin-dir":
            return "the aic arm must use a plugin directory."
        if self._arm_id != "aic" and self._mount == "plugin-dir" and self._plugin_dir:
            name = _plugin_name(Path(self._plugin_dir))
            if name == "aic":
                return "a non-aic arm staged the aic plugin."
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
        except Exception:
            payload["max_budget_usd"] = None
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        secret = _secret()
        if secret and secret in text:
            return
        (logging_dir / "arm-load.json").write_text(text, encoding="utf-8")

    def _copy_key_file(self, session) -> None:
        script = agent_env_script(_secret())
        descriptor, name = tempfile.mkstemp(prefix="aic-agent-env-")
        try:
            os.write(descriptor, script.encode())
            os.close(descriptor)
            descriptor = -1
            os.chmod(name, 0o600)
            session.copy_to_container(
                Path(name),
                container_dir="/installed-agent",
                container_filename="agent-env.sh",
            )
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(name)
            except OSError:
                pass

    def _copy_plugin(self, session) -> str | None:
        if not self._plugin_dir:
            return None
        plugin = Path(self._plugin_dir)
        if plugin.is_symlink() or not plugin.is_dir() or _contains_secret(plugin, _secret()):
            return None
        name = _plugin_name(plugin)
        if name is None:
            return None
        session.copy_to_container(plugin, container_dir="/installed-agent/plugin")
        return name

    def perform_task(self, instruction: str, session, logging_dir: Path | None = None) -> AgentResult:
        self._session = session
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
            return super().perform_task(instruction, session, logging_dir)
        finally:
            self._session = None

    def _run_agent_commands(self, instruction: str) -> list[TerminalCommand]:
        session = self._session
        plugin_name = None
        if session is not None and self._mount == "plugin-dir":
            plugin_name = self._copy_plugin(session)
        if session is not None:
            self._copy_key_file(session)
        loaded = plugin_name == "aic" and self._arm_id == "aic"
        self._write_marker(loaded=loaded, plugin_name=plugin_name, detail=None)
        container_plugin = "/installed-agent/plugin" if plugin_name else None
        command = _AGENT_PREFIX + claude_shell(
            instruction,
            model=self._model_name or "",
            max_turns=int(self._max_turns),
            max_usd=format_max_usd(self._max_budget_usd),
            plugin_dir=container_plugin,
        )
        if self._mount == "installed" and self._home_dir and session is not None:
            home = Path(self._home_dir) / ".claude"
            if home.is_dir() and not home.is_symlink() and not _contains_secret(home, _secret()):
                session.copy_to_container(home, container_dir="/installed-agent/dot-claude")
                command = (
                    'mkdir -p "$HOME/.claude" && '
                    'cp -a /installed-agent/dot-claude/. "$HOME/.claude/" && '
                    + command
                )
        return [
            TerminalCommand(
                command=command,
                min_timeout_sec=0.0,
                max_timeout_sec=float("inf"),
                block=True,
                append_enter=True,
            )
        ]
