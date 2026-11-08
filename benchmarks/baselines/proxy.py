"""Allow-list HTTP CONNECT proxy for a network-unshared baseline container.

The proxy listens on a Unix socket on the host. Bubblewrap starts with
``--unshare-net`` and bind-mounts that socket. A small forwarder inside the
container accepts ``127.0.0.1:3128`` and splices those bytes to the socket, so
``HTTPS_PROXY`` can stay a normal loopback URL. Direct connections have no
route. The proxy dials a target only after the phase allow-list matches.
"""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import select
import socket
import threading
from typing import Callable

Dial = Callable[[str, int], socket.socket]

PROXY_PORT = 3128
PROXY_URL = f"http://127.0.0.1:{PROXY_PORT}"
AGENT_HOST = "api.anthropic.com"
# Git fetch uses github.com. Archive downloads use codeload.github.com.
# Bun's installer downloads release zips from GitHub, which redirects to the
# release asset hosts, and its package installs use registry.npmjs.org.
# bun.sh is the documented download origin for the Bun binary.
INSTALL_HOSTS = frozenset({
    "github.com",
    "codeload.github.com",
    "registry.npmjs.org",
    "bun.sh",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
})
INSTALL_ALLOW = frozenset((host, 443) for host in INSTALL_HOSTS)
AGENT_ALLOW = frozenset({(AGENT_HOST, 443)})

FORWARDER_SOURCE = """\
import select
import socket
import subprocess
import sys
import threading


def relay(left, right):
    sockets = [left, right]
    for item in sockets:
        item.setblocking(False)
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                return
            for current in readable:
                other = right if current is left else left
                try:
                    data = current.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                try:
                    other.sendall(data)
                except OSError:
                    return
    finally:
        for item in (left, right):
            try:
                item.close()
            except OSError:
                pass


def serve(listener, sock_path, stop):
    while not stop.is_set():
        readable, _, _ = select.select([listener], [], [], 0.2)
        if not readable:
            continue
        try:
            client, _address = listener.accept()
        except OSError:
            return
        try:
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.connect(sock_path)
        except OSError:
            client.close()
            continue
        threading.Thread(target=relay, args=(client, upstream), daemon=True).start()


def main():
    sock_path = sys.argv[1]
    port = int(sys.argv[2])
    if sys.argv[3] != "--":
        return 2
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen(64)
    stop = threading.Event()
    threading.Thread(target=serve, args=(listener, sock_path, stop), daemon=True).start()
    completed = subprocess.run(sys.argv[4:])
    stop.set()
    listener.close()
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
"""


def network_policy() -> dict:
    """Policy recorded on live receipts. Install carries no secrets."""
    return {
        "enforcement": (
            "bwrap --unshare-net and a host HTTP CONNECT proxy. "
            "The container reaches the proxy at 127.0.0.1:3128 through a bound Unix socket. "
            "Other destinations have no route."
        ),
        "install": {
            "allow": [f"{host}:443" for host in sorted(INSTALL_HOSTS)],
            "secrets": False,
        },
        "agent": {
            "allow": [f"{AGENT_HOST}:443"],
            "secrets": ["ANTHROPIC_API_KEY"],
        },
    }


def system_python() -> str:
    """Distro Python under /usr, whose libraries the sandbox already mounts."""
    candidate = Path("/usr/bin/python3")
    if not candidate.is_file() and not candidate.is_symlink():
        raise OSError("system python3 is not available for the egress forwarder")
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise OSError("system python3 cannot be resolved") from exc
    text = str(resolved)
    if not text.startswith("/usr/") or not resolved.is_file():
        raise OSError("system python3 is outside /usr")
    return text


def write_forwarder(directory: Path) -> Path:
    path = directory / ".aic-egress-forward.py"
    path.write_text(FORWARDER_SOURCE, encoding="utf-8")
    os.chmod(path, 0o755)
    return path


def _dial(host: str, port: int) -> socket.socket:
    return socket.create_connection((host, port), timeout=20)


def permitted(host: str, port: int, allowed: frozenset[tuple[str, int]]) -> bool:
    if port != 443 or not host or host != host.lower():
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return (host, port) in allowed
    return False


def _parse_connect(header: bytes) -> tuple[str, int] | None:
    line = header.split(b"\r\n", 1)[0].decode("ascii", "replace").strip()
    parts = line.split(" ")
    if len(parts) < 2 or parts[0].upper() != "CONNECT":
        return None
    target = parts[1]
    if target.startswith("[") or target.count(":") != 1:
        return None
    host, port_text = target.split(":", 1)
    if not port_text.isdigit():
        return None
    host = host.lower().rstrip(".")
    if not host or any(character in host for character in " /\\@%"):
        return None
    return host, int(port_text)


def _read_header(client: socket.socket) -> bytes:
    client.settimeout(10)
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = client.recv(4096)
        if not chunk:
            break
        data += chunk
        if len(data) > 16384:
            break
    return data


def _relay(left: socket.socket, right: socket.socket) -> None:
    sockets = [left, right]
    for item in sockets:
        item.setblocking(False)
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                return
            for current in readable:
                other = right if current is left else left
                try:
                    data = current.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                try:
                    other.sendall(data)
                except OSError:
                    return
    finally:
        for item in (left, right):
            try:
                item.close()
            except OSError:
                pass


class EgressProxy:
    """One allow-list. ``connect`` is the upstream dial, replaced in tests."""

    def __init__(self, allowed: frozenset[tuple[str, int]], connect: Dial | None = None) -> None:
        self.allowed = allowed
        self.connect = connect or _dial
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "proxy.sock"
        if path.exists() or path.is_symlink():
            path.unlink()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(path))
        os.chmod(path, 0o600)
        sock.listen(32)
        sock.settimeout(0.2)
        self._socket = sock
        self._thread = threading.Thread(target=self._serve, name="aic-egress-proxy", daemon=True)
        self._thread.start()
        return path

    def close(self) -> None:
        self._stop.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _serve(self) -> None:
        sock = self._socket
        if sock is None:
            return
        while not self._stop.is_set():
            try:
                client, _address = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket) -> None:
        upstream: socket.socket | None = None
        try:
            header = _read_header(client)
            target = _parse_connect(header)
            if target is None or not permitted(target[0], target[1], self.allowed):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            upstream = self.connect(target[0], target[1])
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            _relay(client, upstream)
            upstream = None
            client = None  # relay closes both
        except OSError:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass
            if client is not None:
                try:
                    client.close()
                except OSError:
                    pass


class PhaseProxies:
    """Install and agent proxies for one live run."""

    def __init__(self, root: Path, connect: Dial | None = None) -> None:
        self.install = EgressProxy(INSTALL_ALLOW, connect)
        self.agent = EgressProxy(AGENT_ALLOW, connect)
        self.install_socket = self.install.start(root / "install")
        self.agent_socket = self.agent.start(root / "agent")

    def socket_for(self, phase: str) -> Path:
        if phase == "install":
            return self.install_socket
        if phase == "agent":
            return self.agent_socket
        raise ValueError(phase)

    def close(self) -> None:
        self.install.close()
        self.agent.close()
