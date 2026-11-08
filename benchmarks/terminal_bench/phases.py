"""Terminal-Bench agent phase.

The API key stays in the host agent phase, behind the egress proxy. The task
container receives neither the key nor a copy of an installed third-party arm.
Bash commands that the agent issues are forwarded only when the payload does
not contain the key, and the container environment has no API key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import tempfile
import threading

from benchmarks.aicbench.grading import GradeError, outside_repository_temp
from benchmarks.baselines.adapter import AdapterError
from benchmarks.budget import claude_shell
from benchmarks.suite_runtime import PROXY_REFUSAL, attach_suite_runtime, read_key_file


_MAX_COPY = 1_000_000
_CONTAINER_ENV = {
    "HOME": "/root",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
}


def contains_secret(path: Path, secret: str) -> bool:
    if not secret or not path.exists():
        return False
    files = [path] if path.is_file() else list(path.rglob("*"))
    for child in files:
        if child.is_symlink() or not child.is_file():
            continue
        try:
            if child.stat().st_size > _MAX_COPY:
                return True
            blob = child.read_bytes()
        except OSError:
            return True
        if secret.encode() in blob:
            return True
    return False


def dispatch_task_command(data: bytes, key: str, execute) -> bytes:
    """Run a container command. A payload that contains the key is refused."""
    if key and key.encode() in data:
        return b"refused\n"
    try:
        argv = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return b"refused\n"
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or "\x00" in item for item in argv):
        return b"refused\n"
    if key and any(key in item for item in argv):
        return b"refused\n"
    code, out, err = execute(list(argv))
    text = f"{code}\n{out}{err}"
    if key and key in text:
        return b"refused\n"
    return text.encode()[:100_000]


class TaskBridge:
    """Unix socket the sandboxed bash wrapper uses. The executor sees no API key."""

    def __init__(self, sock_path: Path, key: str, execute) -> None:
        self.key = key
        self.execute = execute
        if sock_path.exists() or sock_path.is_symlink():
            sock_path.unlink()
        sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(sock_path))
        os.chmod(sock_path, 0o600)
        self._sock.listen(16)
        self._sock.settimeout(0.2)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="aic-task-bridge", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                client, _address = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket) -> None:
        try:
            data = b""
            while len(data) <= _MAX_COPY:
                chunk = client.recv(65536)
                if not chunk:
                    break
                data += chunk
            client.sendall(dispatch_task_command(data, self.key, self.execute))
        except OSError:
            return
        finally:
            try:
                client.close()
            except OSError:
                pass


def write_bash_wrapper(directory: Path, sock_path: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "bash"
    path.write_text(
        "#!/usr/bin/python3\n"
        "import json, socket, sys\n"
        f"sock_path = {str(sock_path)!r}\n"
        "client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "client.connect(sock_path)\n"
        "client.sendall(json.dumps(sys.argv[1:]).encode())\n"
        "client.shutdown(socket.SHUT_WR)\n"
        "data = b''\n"
        "while True:\n"
        "    chunk = client.recv(65536)\n"
        "    if not chunk:\n"
        "        break\n"
        "    data += chunk\n"
        "sys.stdout.buffer.write(data)\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)
    return path


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


def _outside(prefix: str) -> Path:
    try:
        parent = outside_repository_temp()
    except GradeError as exc:
        raise AdapterError(str(exc), 1) from exc
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def container_execute(session, argv: list[str]) -> tuple[int, str, str]:
    """Run argv in the task container. The environment has no API key."""
    env = dict(_CONTAINER_ENV)
    container = getattr(session, "container", None)
    if container is not None and hasattr(container, "exec_run"):
        result = container.exec_run(["/bin/bash", *argv], environment=env)
        code = int(getattr(result, "exit_code", 1) or 0)
        output = getattr(result, "output", b"")
        text = output.decode("utf-8", "replace") if isinstance(output, bytes) else str(output or "")
        return code, text, ""
    recorded = getattr(session, "commands", None)
    if isinstance(recorded, list):
        recorded.append((list(argv), env))
    return 0, "", ""


def execute_registry_phase(
    *,
    instruction: str,
    model: str,
    max_turns: int,
    max_usd: str,
    plugin_dir: str | None,
    home_dir: str | None,
    mount: str,
    arm_id: str,
    session,
    environ: dict[str, str],
    seed: int,
    timeout: int,
    runtime=None,
    launch=None,
) -> dict:
    """Run Claude in the agent sandbox. Copy nothing that holds the key into the container."""
    key_path = environ.get("AIC_SUITE_KEY_FILE", "")
    key = read_key_file(Path(key_path)) if key_path else ""
    if not key:
        raise AdapterError(PROXY_REFUSAL, 1)
    attached = runtime if runtime is not None else attach_suite_runtime(environ)
    plugin = Path(plugin_dir) if plugin_dir else None
    home = Path(home_dir) if home_dir else None
    plugin_name = None
    if mount == "plugin-dir":
        if plugin is None or contains_secret(plugin, key):
            raise AdapterError("refusing to mount a plugin that contains the API key.", 1)
        plugin_name = _plugin_name(plugin)
        if plugin_name is None:
            raise AdapterError("plugin directory has no plugin name.", 1)
    elif mount == "installed":
        if home is None or contains_secret(home, key):
            raise AdapterError("refusing to mount a home directory that contains the API key.", 1)
    elif mount != "none":
        raise AdapterError(f"unsupported suite mount: {mount}.", 2)
    work = _outside("aic-tb-agent-")
    try:
        home_path = home if home is not None else work / "home"
        config = work / "config"
        workspace = work / "workspace"
        bridge_dir = workspace / "bridge"
        wrapper_dir = workspace / "bin"
        for path in (home_path, config, workspace, bridge_dir, wrapper_dir):
            path.mkdir(parents=True, exist_ok=True)
        command = claude_shell(
            instruction,
            model=model,
            max_turns=int(max_turns),
            max_usd=max_usd,
            plugin_dir=str(plugin) if plugin is not None else None,
        )
        argv = shlex.split(command)
        if any(key in part for part in argv) or "agent-env.sh" in command:
            raise AdapterError("refusing to put the API key in the task command.", 1)
        sock_path = bridge_dir / "bridge.sock"
        wrapper = write_bash_wrapper(wrapper_dir, sock_path)
        if key in wrapper.read_text(encoding="utf-8"):
            raise AdapterError("refusing to put the API key in the task bridge.", 1)

        def execute(task_argv: list[str]) -> tuple[int, str, str]:
            if any(key in item for item in task_argv):
                return 1, "", "refused"
            if session is None:
                return 0, "", ""
            return container_execute(session, task_argv)

        bridge = TaskBridge(sock_path, key, execute)
        try:
            attached.run(
                argv,
                phase="agent",
                key=key,
                workspace=workspace,
                home=home_path,
                config=config,
                skill_root=plugin,
                timeout=timeout,
                seed=seed,
                extra_binds=((str(wrapper), "/bin/bash"), (str(bridge_dir), str(bridge_dir))),
                path_prefix=wrapper_dir,
                launch=launch,
            )
        finally:
            bridge.close()
        return {
            "install_has_api_key": False,
            "loaded": arm_id == "aic" and plugin_name == "aic",
            "plugin_name": plugin_name,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)
