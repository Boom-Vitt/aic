"""Offline wall-deadline regressions using only task-owned socketpairs.

Transport factories are importable and pickleable for a spawn-based request
boundary. They replace external I/O, not the request/status/header parser.
"""
import functools
import http.client
import json
import multiprocessing
import os
import signal
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maintenance import collector

URL = "https://www.anthropic.com/engineering/deadline-fixture"
DEADLINE_SECONDS = 1.0
SCHEDULING_TOLERANCE = 2.0
STALL_SECONDS = 6.0
DRIP_INTERVAL = 0.05


def _record(directory, name):
    Path(directory, name + ".json").write_text(
        json.dumps({"pid": os.getpid(), "thread": threading.get_ident()}),
        encoding="utf-8",
    )


def _stalled_getaddrinfo(host, port, *, type, directory):
    """A bounded resolver substitute blocked on local I/O, without DNS traffic."""
    reader, writer = socket.socketpair()
    reader.settimeout(0.1)
    _record(directory, "worker")
    try:
        finish = time.monotonic() + STALL_SECONDS
        while time.monotonic() < finish and not Path(directory, "release").exists():
            try:
                reader.recv(1)
            except socket.timeout:
                continue
        raise socket.gaierror(socket.EAI_AGAIN, "synthetic stalled resolver")
    finally:
        reader.close()
        writer.close()
        _record(directory, "worker-finished")


class StalledDNSHTTPS(collector._PinnedHTTPS):
    """Keep production resolution/connection handling, substituting only DNS."""

    def __init__(self, host, *, timeout, context, directory):
        super().__init__(host, timeout=timeout, context=context)
        self.fixture_directory = directory

    def connect(self):
        resolver = functools.partial(
            _stalled_getaddrinfo, directory=self.fixture_directory
        )
        with patch.object(socket, "getaddrinfo", resolver):
            super().connect()


class LocalHTTPHTTPS(http.client.HTTPSConnection):
    """Use real HTTP parsing over a socketpair, with a bounded local peer."""

    def __init__(self, host, *, timeout, context, directory, phase):
        super().__init__(host, timeout=timeout, context=context)
        self.fixture_directory = directory
        self.phase = phase
        self.peer = None
        self.peer_thread = None
        self.stop_peer = threading.Event()

    def connect(self):
        self.sock, self.peer = socket.socketpair()
        self.sock.settimeout(self.timeout)
        self.peer.settimeout(0.1)
        _record(self.fixture_directory, "worker")
        self.peer_thread = threading.Thread(
            target=self._serve, name="aic-deadline-fixture-peer"
        )
        self.peer_thread.start()

    def _serve(self):
        _record(self.fixture_directory, "peer")
        try:
            request = bytearray()
            stop = time.monotonic() + STALL_SECONDS
            while b"\r\n\r\n" not in request:
                if self.stop_peer.is_set() or time.monotonic() >= stop:
                    return
                try:
                    chunk = self.peer.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    return
                request.extend(chunk)
                if len(request) > 16384:
                    return
            if self.phase == "immediate":
                self.peer.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n"
                    b"Content-Type: text/html\r\nConnection: close\r\n\r\nok"
                )
                return
            if self.phase == "headers":
                self.peer.sendall(b"HTTP/1.1 200 OK\r\nX-Fixture: ")
            else:
                self.peer.sendall(b"HTTP/1.1 200 ")
            _record(self.fixture_directory, "stall-started")
            # Each byte arrives well inside the inactivity timeout. Only an
            # absolute deadline can stop parsing before this finite drip ends.
            for _ in range(int(STALL_SECONDS / DRIP_INTERVAL)):
                if self.stop_peer.wait(DRIP_INTERVAL):
                    return
                if Path(self.fixture_directory, "release").exists():
                    return
                self.peer.sendall(b"x")
            self.peer.sendall(
                b"\r\nContent-Length: 0\r\nContent-Type: text/html\r\n"
                b"Connection: close\r\n\r\n"
            )
        except OSError:
            # Cancellation may close the client's end while the peer sends.
            pass
        finally:
            self.peer.close()
            _record(self.fixture_directory, "peer-finished")

    def close(self):
        self.stop_peer.set()
        super().close()
        if self.peer_thread is not None:
            self.peer_thread.join(1.0)
        _record(self.fixture_directory, "worker-finished")


class CollectorAbsoluteDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="security-collector-", dir=ROOT / ".work"
        )
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self._cleanup_fixture_work)

    def _records(self):
        records = []
        for name in ("worker", "peer"):
            path = self.directory / (name + ".json")
            if path.exists():
                records.append((name, json.loads(path.read_text(encoding="utf-8"))))
        return records

    def _cleanup_fixture_work(self):
        # Release a broken thread-only implementation before removing fixtures.
        # This is test teardown, never the cancellation being tested.
        (self.directory / "release").touch()
        records = self._records()
        local_ids = {
            record["thread"] for _, record in records if record["pid"] == os.getpid()
        }
        for thread in threading.enumerate():
            if thread.ident in local_ids and thread is not threading.current_thread():
                thread.join(2.0)
                self.assertFalse(thread.is_alive(), "fixture thread did not finish")
        pids = {record["pid"] for _, record in records} - {os.getpid()}
        children = {child.pid: child for child in multiprocessing.active_children()}
        for pid in pids:
            child = children.get(pid)
            if child is not None:
                child.terminate()
                child.join(2.0)
                if child.is_alive():
                    child.kill()
                    child.join(2.0)
                self.assertFalse(child.is_alive(), "fixture process did not exit")
            else:
                # Also clean up a subprocess-based implementation, if defective.
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass

    def _assert_reaped(self):
        records = self._records()
        self.assertTrue(records, "synthetic blocking transport was not entered")
        for name, record in records:
            if record["pid"] == os.getpid():
                self.assertTrue(
                    (self.directory / (name + "-finished.json")).exists(),
                    "request returned while synthetic I/O was still running",
                )
                if record["thread"] != threading.get_ident():
                    self.assertFalse(
                        any(t.ident == record["thread"] for t in threading.enumerate()),
                        "request left a transport thread running",
                    )
            else:
                try:
                    os.kill(record["pid"], 0)
                except ProcessLookupError:
                    continue
                self.fail("request left its transport process alive or unreaped")

    def _assert_deadline(self, factory, *, phase=None):
        kwargs = {"directory": str(self.directory)}
        if phase is not None:
            kwargs["phase"] = phase
        transport = functools.partial(factory, **kwargs)
        failure = None
        started = time.monotonic()
        with patch.object(collector, "_PinnedHTTPS", transport):
            try:
                collector._request_once(URL, deadline=started + DEADLINE_SECONDS)
            except collector.CollectionError as exc:
                failure = exc
        elapsed = time.monotonic() - started
        self.assertTrue((self.directory / "worker.json").exists())
        if phase is not None:
            self.assertTrue((self.directory / "stall-started.json").exists())
        self.assertLess(
            elapsed,
            DEADLINE_SECONDS + SCHEDULING_TOLERANCE,
            "absolute source deadline did not cut short the stalled operation",
        )
        self.assertIsInstance(failure, collector.CollectionError)
        self._assert_reaped()

    def test_absolute_deadline_cancels_and_reaps_stalled_dns(self):
        self._assert_deadline(StalledDNSHTTPS)

    def test_absolute_deadline_cancels_and_reaps_dripping_status(self):
        self._assert_deadline(LocalHTTPHTTPS, phase="status")

    def test_absolute_deadline_cancels_and_reaps_dripping_headers(self):
        self._assert_deadline(LocalHTTPHTTPS, phase="headers")

    def test_immediate_local_response_preserves_status_headers_and_body(self):
        transport = functools.partial(
            LocalHTTPHTTPS, directory=str(self.directory), phase="immediate"
        )
        with patch.object(collector, "_PinnedHTTPS", transport):
            status, headers, body = collector._request_once(
                URL, deadline=time.monotonic() + 5.0
            )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "text/html")
        self.assertEqual(body, b"ok")
        self._assert_reaped()


if __name__ == "__main__":
    unittest.main()
