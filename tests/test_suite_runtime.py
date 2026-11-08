"""Key-free proof of the official suite egress gate.

These tests do not call a model, fetch a repository, or start Docker.
"""
import base64
from contextlib import redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

from benchmarks.aicbench.grading import outside_repository_temp
from benchmarks.baselines.adapter import AdapterError
from benchmarks.baselines.proxy import AGENT_ALLOW, INSTALL_ALLOW, PhaseProxies, permitted
from benchmarks.suite_runtime import (
    AttachedRuntime,
    harness_env,
    open_suite_runtime,
    run_phase,
    system_python,
)
from benchmarks.swe_bench.live import generate_condition, main
from benchmarks.terminal_bench.phases import (
    NETWORK_REFUSAL,
    TaskBridge,
    container_execute,
    contains_secret,
    dispatch_task_command,
    execute_registry_phase,
    isolate_task_container,
    task_container_is_isolated,
)


ROOT = Path(__file__).resolve().parents[1]
KEY = "suite-runtime-sentinel"
TRUE = "/bin/true" if Path("/bin/true").is_file() else "/usr/bin/true"


def _instances():
    return [{
        "instance_id": "repo__name-0001",
        "repo": "example/example",
        "base_commit": "a" * 40,
        "problem_statement": "The widget drops the last row.",
    }]


class SuiteRuntimeTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="aic-suite-runtime-", dir=outside_repository_temp())
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_official_runs_refuse_without_bubblewrap_or_the_proxy(self):
        empty = self.base / "empty-path"
        empty.mkdir()
        root = self.base / "runtime"
        root.mkdir()
        with self.assertRaises(AdapterError) as caught:
            open_suite_runtime({"PATH": str(empty), "ANTHROPIC_API_KEY": KEY}, root)
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("bubblewrap", str(caught.exception).lower())
        self.assertIn("egress proxy", str(caught.exception))
        self.assertFalse((root / "secret" / "agent-key").exists())
        output = self.base / "swe-output"
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(
                ["--output", str(output), "--smoke"],
                env={"ANTHROPIC_API_KEY": KEY, "PATH": str(empty)},
            )
        self.assertEqual(code, 1, stderr.getvalue())
        self.assertIn("egress proxy", stderr.getvalue())
        self.assertFalse(output.exists())

    def test_harness_environment_and_task_bridge_do_not_carry_the_key(self):
        env = harness_env(
            {"PATH": "/usr/bin", "ANTHROPIC_API_KEY": KEY, "LANG": "C.UTF-8"},
            {
                "AIC_SUITE_AGENT_SOCK": "/tmp/aic-agent.sock",
                "AIC_SUITE_INSTALL_SOCK": "/tmp/aic-install.sock",
            },
            KEY,
        )
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn(KEY, "\n".join(env.values()))
        self.assertEqual(env["AIC_SUITE_AGENT_SOCK"], "/tmp/aic-agent.sock")
        with self.assertRaises(AdapterError):
            harness_env({"PATH": "/usr/bin"}, {"AIC_SUITE_KEY_FILE": f"/tmp/{KEY}"}, KEY)

        seen = []

        def execute(argv):
            seen.append(list(argv))
            self.assertNotIn(KEY, "\n".join(argv))
            return 0, "ok", ""

        self.assertEqual(dispatch_task_command(json.dumps(["-lc", "pwd"]).encode(), KEY, execute), b"0\nok")
        self.assertEqual(seen, [["-lc", "pwd"]])
        self.assertEqual(
            dispatch_task_command(json.dumps(["-lc", f"echo {KEY}"]).encode(), KEY, execute),
            b"refused\n",
        )
        self.assertEqual(seen, [["-lc", "pwd"]])

        sock = self.base / "bridge.sock"
        bridge = TaskBridge(sock, KEY, execute)
        self.addCleanup(bridge.close)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(sock))
        client.sendall(json.dumps(["-lc", "true"]).encode())
        client.shutdown(socket.SHUT_WR)
        self.assertTrue(client.recv(100).startswith(b"0\n"))
        client.close()
        self.assertEqual(seen[-1], ["-lc", "true"])

    def test_install_phase_has_no_key_and_agent_phase_allows_only_anthropic(self):
        self.assertTrue(permitted("api.anthropic.com", 443, AGENT_ALLOW))
        self.assertFalse(permitted("github.com", 443, AGENT_ALLOW))
        self.assertFalse(permitted("api.anthropic.com", 443, INSTALL_ALLOW))
        self.assertTrue(permitted("registry.npmjs.org", 443, INSTALL_ALLOW))
        self.assertTrue(permitted("bun.sh", 443, INSTALL_ALLOW))
        try:
            system_python()
        except OSError as exc:
            self.skipTest(str(exc))

        dialed = []

        def fake_connect(host, port):
            dialed.append((host, port))
            left, right = socket.socketpair()
            right.close()
            return left

        proxies = PhaseProxies(self.base / "egress", fake_connect)
        self.addCleanup(proxies.close)
        home = self.base / "home"
        config = self.base / "config"
        workspace = self.base / "workspace"
        for path in (home, config, workspace):
            path.mkdir()
        captured = {}

        def launch(argv, **kwargs):
            captured["argv"] = list(argv)
            captured["env"] = dict(kwargs["env"])
            return subprocess.CompletedProcess(argv, 0, "", "")

        common = dict(
            parent={"PATH": os.environ.get("PATH", "")},
            bwrap="/usr/bin/bwrap",
            proxies=proxies,
            workspace=workspace,
            home=home,
            config=config,
            skill_root=None,
            timeout=5,
            seed=0,
            launch=launch,
        )
        installed = run_phase(argv=[TRUE], phase="install", key=KEY, **common)
        self.assertEqual(installed.returncode, 0)
        self.assertNotIn("ANTHROPIC_API_KEY", captured["env"])
        self.assertNotIn(KEY, "\n".join(captured["env"].values()))
        self.assertIn("--unshare-net", captured["argv"])
        self.assertIn(str(proxies.install_socket), captured["argv"])
        self.assertNotIn(str(proxies.agent_socket), captured["argv"])
        self.assertNotIn(KEY, captured["argv"])

        run_phase(argv=[TRUE], phase="agent", key=KEY, **common)
        self.assertEqual(captured["env"]["ANTHROPIC_API_KEY"], KEY)
        self.assertEqual(captured["env"]["HTTPS_PROXY"], "http://127.0.0.1:3128")
        self.assertIn("--unshare-net", captured["argv"])
        self.assertIn(str(proxies.agent_socket), captured["argv"])
        self.assertNotIn(str(proxies.install_socket), captured["argv"])
        self.assertNotIn(KEY, captured["argv"])
        self.assertNotIn(str(self.base / "secret"), "\n".join(captured["argv"]))

        def status(sock, host):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(str(sock))
            client.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode())
            data = b""
            while b"\r\n" not in data:
                chunk = client.recv(200)
                if not chunk:
                    break
                data += chunk
            client.close()
            return data.split(b"\r\n", 1)[0].decode()

        self.assertIn("403", status(proxies.agent_socket, "github.com"))
        self.assertIn("403", status(proxies.agent_socket, "example.com"))
        self.assertIn("200", status(proxies.agent_socket, "api.anthropic.com"))
        self.assertEqual(dialed, [("api.anthropic.com", 443)])
        self.assertIn("200", status(proxies.install_socket, "github.com"))
        self.assertIn("403", status(proxies.install_socket, "api.anthropic.com"))
        with self.assertRaises(AdapterError) as missing:
            run_phase(argv=[TRUE], phase="agent", key=KEY, proxies=None, **{
                item: common[item] for item in common if item != "proxies"
            })
        self.assertIn("egress proxy", str(missing.exception))

    def test_terminal_agent_phase_keeps_the_key_out_of_the_container(self):
        try:
            system_python()
        except OSError as exc:
            self.skipTest(str(exc))
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        claude.chmod(0o755)
        key_file = self.base / "agent-key"
        key_file.write_text(KEY, encoding="utf-8")
        os.chmod(key_file, 0o600)
        proxies = PhaseProxies(self.base / "phase-egress", lambda host, port: socket.socketpair()[0])
        self.addCleanup(proxies.close)
        bwrap = self.base / "bwrap"
        bwrap.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        bwrap.chmod(0o755)
        attached = AttachedRuntime(
            {"PATH": str(bin_dir), "LANG": "C.UTF-8"},
            str(bwrap),
            proxies.install_socket,
            proxies.agent_socket,
        )
        captured = {}

        def launch(argv, **kwargs):
            captured["argv"] = [str(item) for item in argv]
            captured["env"] = dict(kwargs["env"])
            bash_index = captured["argv"].index("/bin/bash")
            captured["wrapper"] = Path(captured["argv"][bash_index - 1]).read_text(encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "", "")

        class Session:
            def __init__(self):
                self.copies = []
                self.commands = []

            def copy_to_container(self, *args, **kwargs):
                self.copies.append((args, kwargs))

            container = None

        session = Session()
        outcome = execute_registry_phase(
            instruction="Fix the task.",
            model="claude-sonnet-5-5",
            max_turns=30,
            max_usd="0.35",
            plugin_dir=None,
            home_dir=None,
            mount="none",
            arm_id="plain-claude-code",
            session=session,
            environ={"AIC_SUITE_KEY_FILE": str(key_file)},
            seed=0,
            timeout=5,
            runtime=attached,
            launch=launch,
        )
        self.assertFalse(outcome["install_has_api_key"])
        self.assertFalse(outcome["loaded"])
        self.assertEqual(session.copies, [])
        self.assertEqual(session.commands, [])
        self.assertEqual(captured["env"]["ANTHROPIC_API_KEY"], KEY)
        self.assertNotIn(KEY, captured["argv"])
        self.assertNotIn("agent-env.sh", captured["argv"])
        self.assertNotIn(str(key_file), captured["argv"])
        self.assertIn("--unshare-net", captured["argv"])
        self.assertIn(str(proxies.agent_socket), captured["argv"])
        self.assertNotIn(str(proxies.install_socket), captured["argv"])
        self.assertIn("/bin/bash", captured["argv"])
        self.assertIn("--max-budget-usd", captured["argv"])
        self.assertNotIn(KEY, captured["wrapper"])

        poisoned = self.base / "plugin"
        (poisoned / ".claude-plugin").mkdir(parents=True)
        (poisoned / ".claude-plugin" / "plugin.json").write_text('{"name":"aic"}\n', encoding="utf-8")
        (poisoned / "secret.txt").write_text(KEY, encoding="utf-8")
        self.assertTrue(contains_secret(poisoned, KEY))
        with self.assertRaises(AdapterError):
            execute_registry_phase(
                instruction="Fix the task.",
                model="claude-sonnet-5-5",
                max_turns=30,
                max_usd="0.35",
                plugin_dir=str(poisoned),
                home_dir=None,
                mount="plugin-dir",
                arm_id="aic",
                session=session,
                environ={"AIC_SUITE_KEY_FILE": str(key_file)},
                seed=0,
                timeout=5,
                runtime=attached,
                launch=launch,
            )
        self.assertEqual(session.copies, [])

    def test_swe_generation_puts_the_key_only_in_the_agent_phase(self):
        calls = []

        class Runtime:
            def run(self, argv, **kwargs):
                calls.append((list(argv), kwargs["phase"], kwargs.get("key")))
                return subprocess.CompletedProcess(argv, 0, "", "")

        output = self.base / "swe"
        output.mkdir()
        failures = generate_condition(
            "baseline",
            _instances(),
            output,
            self.base / "cache",
            {"PATH": "/usr/bin"},
            KEY,
            Runtime(),
            plugin_dir=None,
            model="claude-sonnet-5-5",
            max_turns=30,
            max_budget_usd="0.35",
            timeout=5,
        )
        phases = [phase for _argv, phase, _key in calls]
        self.assertIn("install", phases)
        self.assertIn("agent", phases)
        self.assertLess(phases.index("install"), phases.index("agent"))
        for argv, phase, key in calls:
            self.assertNotIn(KEY, argv)
            if phase == "install":
                self.assertIsNone(key)
                self.assertEqual(argv[0], "git")
            if phase == "agent":
                self.assertEqual(key, KEY)
                self.assertEqual(argv[0], "claude")
                self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "0.35")
                self.assertNotIn("--plugin-dir", argv)
        self.assertEqual(failures, 0)


class TaskContainer:
    """In-memory docker container. Disconnect clears attachments and leaves the create-time mode."""

    def __init__(self, mode="bridge", networks=None, internal=(), disconnects=True):
        self.mode = mode
        self.networks = {"bridge": {"NetworkID": "bridge-id"}} if networks is None else dict(networks)
        self._internal = set(internal)
        self.disconnects = disconnects
        self.trace = []
        self.execs = []

    @property
    def attrs(self):
        return {
            "HostConfig": {"NetworkMode": self.mode},
            "NetworkSettings": {"Networks": {name: dict(info) for name, info in self.networks.items()}},
        }

    def reload(self):
        self.trace.append("reload")

    def network_is_internal(self, name):
        return name in self._internal

    def disconnect_network(self, name, info):
        self.trace.append("disconnect")
        if self.disconnects:
            self.networks.pop(name, None)

    def exec_run(self, argv, environment=None):
        self.trace.append("exec")
        self.execs.append({
            "argv": list(argv),
            "networks": set(self.networks),
            "mode": self.mode,
        })
        return type("Result", (), {"exit_code": 0, "output": b"ok"})()


class _NetSession:
    def __init__(self, container):
        self.container = container
        self.commands = []

    def copy_to_container(self, *args, **kwargs):
        raise AssertionError("copied into the task container")


class TaskNetworkTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="aic-task-net-", dir=outside_repository_temp())
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.key_file = self.base / "agent-key"
        self.key_file.write_text(KEY, encoding="utf-8")
        os.chmod(self.key_file, 0o600)

    def _phase(self, container, runtime):
        return execute_registry_phase(
            instruction="Fix the task.",
            model="claude-sonnet-5-5",
            max_turns=30,
            max_usd="0.35",
            plugin_dir=None,
            home_dir=None,
            mount="none",
            arm_id="plain-claude-code",
            session=_NetSession(container),
            environ={"AIC_SUITE_KEY_FILE": str(self.key_file)},
            seed=0,
            timeout=5,
            runtime=runtime,
        )

    def test_official_runs_refuse_a_networked_task_container(self):
        for container in (
            TaskContainer(mode="host", networks={}),
            TaskContainer(mode="container:other", networks={}),
            TaskContainer(
                mode="lab",
                networks={"lab": {"NetworkID": "lab", "Internal": True}},
                internal=("lab",),
                disconnects=False,
            ),
            TaskContainer(disconnects=False),
        ):
            launched = []

            class Runtime:
                def run(self, argv, **kwargs):
                    launched.append(list(argv))
                    return subprocess.CompletedProcess(argv, 0, "", "")

            with self.assertRaises(AdapterError) as caught:
                self._phase(container, Runtime())
            self.assertIn("network egress", str(caught.exception))
            self.assertEqual(caught.exception.code, 1)
            self.assertEqual(launched, [])
            self.assertEqual(container.execs, [])
            self.assertNotIn("exec", container.trace)

    def test_forwarded_exec_waits_until_network_removal_is_verified(self):
        container = TaskContainer(mode="bridge")
        seen = {}

        class Runtime:
            def run(self, argv, **kwargs):
                seen["networks"] = set(container.networks)
                seen["trace"] = list(container.trace)
                return subprocess.CompletedProcess(argv, 0, "", "")

        self._phase(container, Runtime())
        self.assertEqual(seen["networks"], set())
        self.assertEqual(seen["trace"], ["reload", "disconnect", "reload"])
        self.assertTrue(task_container_is_isolated(container))
        session = _NetSession(container)
        container_execute(session, ["-lc", "pwd"])
        self.assertEqual(container.execs[0]["networks"], set())
        self.assertLess(container.trace.index("disconnect"), container.trace.index("exec"))
        self.assertEqual(container.trace[-1], "exec")
        stale = TaskContainer(mode="bridge", networks={})
        self.assertTrue(task_container_is_isolated(stale))
        none_only = TaskContainer(mode="none", networks={"none": {"NetworkID": "none"}})
        self.assertTrue(task_container_is_isolated(none_only))
        isolate_task_container(none_only)
        self.assertNotIn("disconnect", none_only.trace)
        internal = TaskContainer(
            mode="lab",
            networks={"lab": {"NetworkID": "lab", "Internal": True}},
            internal=("lab",),
        )
        self.assertFalse(task_container_is_isolated(internal))
        isolate_task_container(internal)
        self.assertIn("disconnect", internal.trace)
        self.assertEqual(internal.networks, {})
        self.assertTrue(task_container_is_isolated(internal))
        stuck_internal = TaskContainer(
            mode="lab",
            networks={"lab": {"NetworkID": "lab", "Internal": True}},
            internal=("lab",),
            disconnects=False,
        )
        with self.assertRaises(AdapterError) as caught:
            isolate_task_container(stuck_internal)
        self.assertEqual(str(caught.exception), NETWORK_REFUSAL)
        self.assertFalse(task_container_is_isolated(stuck_internal))
        with self.assertRaises(AdapterError):
            container_execute(_NetSession(stuck_internal), ["-lc", "pwd"])
        self.assertEqual(stuck_internal.execs, [])

    def test_split_and_encoded_keys_do_not_reach_a_networked_container(self):
        container = TaskContainer(disconnects=False)
        session = _NetSession(container)
        reached = []

        def execute(argv):
            reached.append(list(argv))
            return container_execute(session, argv)

        split = json.dumps(["-lc", KEY[:8], KEY[8:]]).encode()
        encoded = base64.b64encode(KEY.encode()).decode()
        wrapped = json.dumps(["-lc", encoded]).encode()
        self.assertNotIn(KEY.encode(), split)
        self.assertNotIn(KEY, encoded)
        for payload in (split, wrapped):
            with self.assertRaises(AdapterError) as caught:
                dispatch_task_command(payload, KEY, execute)
            self.assertEqual(str(caught.exception), NETWORK_REFUSAL)
        self.assertEqual(len(reached), 2)
        self.assertEqual(container.execs, [])
        contiguous = dispatch_task_command(json.dumps(["-lc", KEY]).encode(), KEY, execute)
        self.assertEqual(contiguous, b"refused\n")
        self.assertEqual(len(reached), 2)
        self.assertEqual(container.execs, [])


if __name__ == "__main__":
    unittest.main()
