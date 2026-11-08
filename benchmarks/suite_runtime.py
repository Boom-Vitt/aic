"""Two-phase egress for official Terminal-Bench and SWE-bench Lite runs.

The install phase has no API key. Its allow-list is the GitHub, npm, and Bun
hosts. The agent phase is the only place the key is injected, and that process
can connect only to ``api.anthropic.com:443``. Official runs refuse to start
when bubblewrap or the proxy is missing. The key file is not bind-mounted.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from benchmarks.aicbench.grading import GradeError, outside_repository_temp
from benchmarks.baselines.adapter import (
    ROOT,
    AdapterError,
    _key,
    _require_bwrap,
    _run_in_container,
)
from benchmarks.baselines.proxy import (
    AGENT_ALLOW,
    INSTALL_ALLOW,
    PROXY_URL,
    PhaseProxies,
    network_policy,
    system_python,
)


PROXY_REFUSAL = "official suite results refuse to run without the egress proxy."
SANDBOX_REFUSAL = (
    "Container sandbox requires bubblewrap (bwrap) on PATH. "
    "official suite results refuse to run without the sandbox."
)


class _PhaseTask:
    reference = Path("/tmp")
    remove: list[str] = []


def harness_env(base: dict[str, str], suite_env: dict[str, str], key: str) -> dict[str, str]:
    """Environment for a task harness. The API key is not one of the values."""
    env = {name: value for name, value in base.items() if name != "ANTHROPIC_API_KEY"}
    env.update(suite_env)
    blob = "\n".join(str(value) for value in env.values())
    if key and (key in blob or "ANTHROPIC_API_KEY" in env):
        raise AdapterError("refusing to put the API key in the harness environment.", 1)
    return env


def write_key_file(directory: Path, key: str) -> Path:
    """Write the agent key outside any mount the sandbox bind-mounts."""
    if not key or any(character.isspace() or ord(character) < 32 for character in key):
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "agent-key"
    if path.is_symlink():
        raise AdapterError("refusing to follow a symlinked key file.", 1)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        os.write(fd, key.encode())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    return path


def read_key_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise AdapterError(PROXY_REFUSAL, 1)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AdapterError(PROXY_REFUSAL, 1) from exc
    if not text or any(character.isspace() or ord(character) < 32 for character in text):
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    return text


def runtime_root() -> Path:
    try:
        parent = outside_repository_temp()
    except GradeError as exc:
        raise AdapterError(str(exc), 1) from exc
    return Path(tempfile.mkdtemp(prefix="aic-suite-runtime-", dir=parent))


def _phase_key(phase: str, key: str | None) -> str | None:
    if phase == "install":
        return None
    if phase == "agent":
        if not key:
            raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
        return key
    raise AdapterError(PROXY_REFUSAL, 1)


def run_phase(
    *,
    parent: dict[str, str],
    bwrap: str,
    proxies,
    argv: list[str],
    phase: str,
    key: str | None,
    workspace: Path,
    home: Path,
    config: Path,
    skill_root: Path | None,
    timeout: int,
    seed: int,
    extra_binds: tuple[tuple[str, str], ...] = (),
    path_prefix: Path | None = None,
    launch=None,
):
    """Run one phase. Install never receives the key. Agent is the only phase that does."""
    used = _phase_key(phase, key)
    if used and any(used in part for part in argv):
        raise AdapterError("refusing to put the API key on a command line.", 1)
    if used and path_prefix is not None:
        if used in str(path_prefix):
            raise AdapterError("refusing to put the API key on the agent PATH.", 1)
        files = [path_prefix] if path_prefix.is_file() else list(path_prefix.rglob("*"))
        for child in files:
            if child.is_symlink() or not child.is_file():
                continue
            try:
                blob = child.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                raise AdapterError("refusing an unreadable agent PATH entry.", 1) from None
            if used in blob:
                raise AdapterError("refusing to put the API key on the agent PATH.", 1)
    completed = _run_in_container(
        list(argv),
        workspace=workspace,
        home=home,
        config=config,
        skill_root=skill_root,
        parent=parent,
        timeout=timeout,
        task=_PhaseTask(),
        seed=seed,
        key=used,
        bwrap=bwrap,
        phase=phase,
        proxies=proxies,
        extra_binds=extra_binds,
        path_prefix=path_prefix,
        launch=launch,
    )
    return completed


class SuiteRuntime:
    """Host-side proxies for one official suite run. The caller closes it."""

    def __init__(self, parent: dict[str, str], root: Path, connect=None) -> None:
        self.parent = dict(parent)
        self.root = root
        self.proxies = None
        self.key_file: Path | None = None
        self.bwrap = _require_bwrap(self.parent)
        self.key = _key(self.parent)
        if self.key is None:
            raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
        try:
            system_python()
            self.proxies = PhaseProxies(root / "egress", connect)
            self.install_socket = self.proxies.install_socket
            self.agent_socket = self.proxies.agent_socket
            self.key_file = write_key_file(root / "secret", self.key)
            secret = str(self.key_file.resolve())
            mounted = {str(self.install_socket.parent.resolve()), str(self.agent_socket.parent.resolve())}
            if secret.startswith(tuple(item + os.sep for item in mounted)) or secret in mounted:
                raise AdapterError("refusing to place the API key on a proxy mount.", 1)
            if ROOT.resolve() in self.key_file.resolve().parents:
                raise AdapterError("refusing to write the API key inside the repository.", 1)
        except OSError as exc:
            self.close()
            raise AdapterError(PROXY_REFUSAL, 1) from exc
        except Exception:
            self.close()
            raise

    def child_env(self) -> dict[str, str]:
        return {
            "AIC_SUITE_AGENT_SOCK": str(self.agent_socket),
            "AIC_SUITE_BWRAP": self.bwrap,
            "AIC_SUITE_INSTALL_SOCK": str(self.install_socket),
            "AIC_SUITE_KEY_FILE": str(self.key_file),
        }

    def run(self, argv, **kwargs):
        return run_phase(
            parent=self.parent,
            bwrap=self.bwrap,
            proxies=self.proxies,
            argv=list(argv),
            phase=kwargs["phase"],
            key=kwargs.get("key"),
            workspace=kwargs["workspace"],
            home=kwargs["home"],
            config=kwargs["config"],
            skill_root=kwargs.get("skill_root"),
            timeout=kwargs["timeout"],
            seed=kwargs["seed"],
            extra_binds=kwargs.get("extra_binds", ()),
            path_prefix=kwargs.get("path_prefix"),
            launch=kwargs.get("launch"),
        )

    def close(self) -> None:
        if self.proxies is not None:
            self.proxies.close()
            self.proxies = None
        key_file = self.key_file
        if key_file is not None and key_file.is_file() and not key_file.is_symlink():
            try:
                key_file.unlink()
            except OSError:
                return


class AttachedRuntime:
    """Child view of a runtime the parent already started. It does not own the sockets."""

    def __init__(self, parent: dict[str, str], bwrap: str, install_socket: Path, agent_socket: Path) -> None:
        self.parent = dict(parent)
        self.parent.pop("ANTHROPIC_API_KEY", None)
        self.bwrap = bwrap
        self.install_socket = install_socket
        self.agent_socket = agent_socket
        self.proxies = _AttachedSockets(install_socket, agent_socket)

    def run(self, argv, **kwargs):
        return run_phase(
            parent=self.parent,
            bwrap=self.bwrap,
            proxies=self.proxies,
            argv=list(argv),
            phase=kwargs["phase"],
            key=kwargs.get("key"),
            workspace=kwargs["workspace"],
            home=kwargs["home"],
            config=kwargs["config"],
            skill_root=kwargs.get("skill_root"),
            timeout=kwargs["timeout"],
            seed=kwargs["seed"],
            extra_binds=kwargs.get("extra_binds", ()),
            path_prefix=kwargs.get("path_prefix"),
            launch=kwargs.get("launch"),
        )

    def close(self) -> None:
        return


class _AttachedSockets:
    def __init__(self, install_socket: Path, agent_socket: Path) -> None:
        self.install_socket = install_socket
        self.agent_socket = agent_socket

    def socket_for(self, phase: str) -> Path:
        if phase == "install":
            return self.install_socket
        if phase == "agent":
            return self.agent_socket
        raise ValueError(phase)


def open_suite_runtime(parent: dict[str, str], root: Path, connect=None) -> SuiteRuntime:
    """Start the official proxies. Missing bubblewrap or a proxy is a hard stop."""
    try:
        _require_bwrap(parent)
    except AdapterError as exc:
        raise AdapterError(f"{SANDBOX_REFUSAL} {PROXY_REFUSAL}", exc.code) from exc
    try:
        return SuiteRuntime(parent, root, connect)
    except AdapterError:
        secret = root / "secret" / "agent-key"
        if secret.is_file() and not secret.is_symlink():
            try:
                secret.unlink()
            except OSError:
                pass
        raise


def attach_suite_runtime(env: dict[str, str]) -> AttachedRuntime:
    """Reconnect to the parent proxies. Refuse when the sandbox or either socket is missing."""
    bwrap = env.get("AIC_SUITE_BWRAP", "")
    install = env.get("AIC_SUITE_INSTALL_SOCK", "")
    agent = env.get("AIC_SUITE_AGENT_SOCK", "")
    key_file = env.get("AIC_SUITE_KEY_FILE", "")
    if not bwrap or not install or not agent or not key_file:
        raise AdapterError(PROXY_REFUSAL, 1)
    paths = [Path(bwrap), Path(install), Path(agent), Path(key_file)]
    if any(path.is_symlink() or not path.exists() for path in paths):
        raise AdapterError(PROXY_REFUSAL, 1)
    if not paths[0].is_file():
        raise AdapterError(SANDBOX_REFUSAL, 1)
    parent = {name: value for name, value in env.items() if name != "ANTHROPIC_API_KEY"}
    return AttachedRuntime(parent, bwrap, paths[1], paths[2])


def agent_allow() -> frozenset[tuple[str, int]]:
    return AGENT_ALLOW


def install_allow() -> frozenset[tuple[str, int]]:
    return INSTALL_ALLOW


def proxy_url() -> str:
    return PROXY_URL


def suite_network() -> dict:
    return network_policy()
