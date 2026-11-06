"""Isolated service protocol contracts; no real launchctl, network or agent runs."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from maintenance import service

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40
MAIN = 'b' * 40
CORE = ('__init__', 'contracts', 'policy', 'state', 'collector', 'github',
        'agents', 'controller', 'service')


class Protocol:
    def __init__(self, repository, home):
        self.repository, self.home = repository, home
        self.files = {f'maintenance/{name}.py': b'# published immutable module\n' for name in CORE}
        self.files.update({'maintenance/sources.json': b'{}\n',
                           'scripts/maintain.py': b'print("published")\n',
                           'skills/aic/assets/workflows.json': b'{}\n'})
        self.remote = 'https://github.com/Boom-Vitt/aic.git'
        self.toplevel = repository
        self.comparison = 'ahead'
        self.loaded = None
        self.calls = []
        self.tree_extra = b''
        self.pid = None

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        name = Path(argv[0]).name
        args = list(argv[1:])
        rc, out, err = 0, b'', b''
        if name == 'git':
            if args[:2] == ['remote', 'get-url']:
                out = self.remote.encode()
            elif args == ['rev-parse', '--show-toplevel']:
                out = str(self.toplevel).encode()
            elif args[0] == 'rev-parse':
                out = SHA.encode()
            elif args[0] == 'ls-tree':
                out = b''.join(b'100644 blob ' + self.oid(data).encode() + b'\t' + path.encode() + b'\0'
                               for path, data in sorted(self.files.items())) + self.tree_extra
            elif args[:2] == ['cat-file', 'blob']:
                out = next(data for data in self.files.values() if self.oid(data) == args[2])
            else:
                raise AssertionError(argv)
        elif name == 'gh':
            endpoint = args[-1]
            if endpoint == 'repos/Boom-Vitt/aic':
                out = json.dumps({'full_name': 'Boom-Vitt/aic', 'default_branch': 'main'}).encode()
            elif endpoint.endswith('/commits/main'):
                out = json.dumps({'sha': MAIN}).encode()
            elif '/compare/' in endpoint:
                out = json.dumps({'status': self.comparison, 'base_commit': {'sha': SHA},
                                  'merge_base_commit': {'sha': SHA}}).encode()
            else:
                raise AssertionError(argv)
        elif name == 'launchctl':
            if args[0] == 'print':
                if self.loaded is None:
                    rc, err = 113, b'Could not find service "ai.aic.research-maintainer" in domain for user gui: 501'
                else:
                    config = self.loaded
                    lines = ['gui/501/ai.aic.research-maintainer = {',
                             f'\tpath = {self.plist}', f'\tprogram = {config["ProgramArguments"][0]}',
                             '\targuments = {', *('\t\t' + a for a in config['ProgramArguments']), '\t}',
                             '\tworking directory = ' + config['WorkingDirectory'],
                             '\tstate = ' + ('running' if self.pid is not None else 'not running'),
                             *([f'\tpid = {self.pid}'] if self.pid is not None else []), '}']
                    out = '\n'.join(lines).encode()
            elif args[0] == 'bootstrap':
                self.plist = args[2]
                self.loaded = plistlib.loads(Path(self.plist).read_bytes())
            elif args[0] == 'bootout':
                self.loaded = None
            else:
                raise AssertionError(argv)
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, rc, out, err)

    @staticmethod
    def oid(data):
        return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


class MaintainerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='service-', dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repository = self.base / 'repository'
        self.home = self.base / 'home'
        self.repository.mkdir()
        self.home.mkdir()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ('gh', 'omp', 'git', 'python3'):
            executable = self.bin / name
            executable.write_text('#!/bin/sh\nexit 99\n')
            executable.chmod(0o700)
        self.python = self.bin / 'python3'
        self.protocol = Protocol(self.repository, self.home)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(service.sys, 'platform', 'darwin').start()
        mock.patch.object(service.shutil, 'which', side_effect=lambda name, **kw: str(self.bin / name)).start()

    @property
    def root(self):
        return self.repository / '.work/maintainer'

    @property
    def plist(self):
        return self.home / 'Library/LaunchAgents/ai.aic.research-maintainer.plist'

    def install(self, **kwargs):
        return service.install(self.repository, published_sha=SHA, python=self.python,
                               home=self.home, runner=self.protocol, **kwargs)

    def snapshot(self):
        return {str(path.relative_to(self.base)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.base.rglob('*') if path.is_file() and not path.is_symlink()}

    def test_preview_has_no_home_repository_or_process_effects(self):
        before = self.snapshot()
        result = self.install()
        self.assertEqual(result['status'], 'preview')
        self.assertFalse(result['publication_verified'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.protocol.calls, [])
        self.assertFalse(self.root.exists())

    def test_install_binds_snapshot_not_working_tree_and_private_plist(self):
        (self.repository / 'maintenance').mkdir()
        (self.repository / 'maintenance/controller.py').write_text('raise RuntimeError("mutable")')
        result = self.install(activate=True)
        release = Path(result['release'])
        self.assertEqual((release / 'maintenance/controller.py').read_bytes(), self.protocol.files['maintenance/controller.py'])
        config = plistlib.loads(self.plist.read_bytes())
        self.assertEqual(config['Label'], 'ai.aic.research-maintainer')
        self.assertEqual(config['StartInterval'], 900)
        self.assertTrue(config['RunAtLoad'])
        self.assertNotIn('KeepAlive', config)
        self.assertEqual(config['ProgramArguments'], [str(self.python), '-I', '-B',
                                                    str(release / 'scripts/maintain.py'), 'run-once',
                                                    '--project', str(self.repository), '--publish'])
        self.assertEqual(config['WorkingDirectory'], str(self.repository))
        self.assertEqual(set(config['EnvironmentVariables']), {'PATH'})
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.plist.stat().st_mode & 0o777, 0o600)
        self.assertEqual((release / 'manifest.json').stat().st_mode & 0o777, 0o600)
        for path in release.rglob('*'):
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertEqual(service.status(self.repository, home=self.home, runner=self.protocol)['status'], 'loaded')

    def test_repeated_intact_install_never_restarts_or_rewrites(self):
        self.install(activate=True)
        before = self.snapshot()
        count = len([c for c in self.protocol.calls if 'bootstrap' in c])
        self.assertEqual(self.install(activate=True)['status'], 'unchanged')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len([c for c in self.protocol.calls if 'bootstrap' in c]), count)

    def test_foreign_and_unpublished_commits_preserve_everything(self):
        for remote, comparison in [('https://github.com/foreign/aic.git', 'ahead'),
                                   ('https://github.com/Boom-Vitt/aic.git', 'diverged'),
                                   ('https://github.com/Boom-Vitt/aic.git', 'behind')]:
            with self.subTest(remote=remote, comparison=comparison):
                self.protocol.remote, self.protocol.comparison = remote, comparison
                before = self.snapshot()
                with self.assertRaises(service.ServiceError):
                    self.install(activate=True)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(any('bootstrap' in c for c in self.protocol.calls))

    def test_invalid_sha_and_platform_refused_without_processes(self):
        with self.assertRaises(service.ServiceError):
            service.install(self.repository, published_sha='HEAD', python=self.python, home=self.home,
                            activate=True, runner=self.protocol)
        with mock.patch.object(service.sys, 'platform', 'linux'):
            with self.assertRaises(service.ServiceError):
                self.install(activate=True)
            with self.assertRaises(service.ServiceError):
                service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.protocol.calls, [])

    def test_missing_core_symlink_and_traversal_tree_refused(self):
        for mutation in ('missing', 'symlink', 'traversal'):
            with self.subTest(mutation=mutation):
                saved = dict(self.protocol.files)
                if mutation == 'missing':
                    del self.protocol.files['maintenance/controller.py']
                else:
                    mode, path = ('120000', 'maintenance/linked.py') if mutation == 'symlink' else ('100644', 'maintenance/../evil.py')
                    self.protocol.tree_extra = f'{mode} blob {SHA}\t{path}\0'.encode()
                with self.assertRaises(service.ServiceError):
                    self.install(activate=True)
                self.assertFalse(self.root.exists())
                self.protocol.files, self.protocol.tree_extra = saved, b''

    def test_unmanaged_plist_and_loaded_label_preserved(self):
        self.plist.parent.mkdir(parents=True)
        self.plist.write_bytes(b'unmanaged')
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        self.assertEqual(self.snapshot(), before)
        self.plist.unlink()
        self.protocol.plist = '/foreign/job.plist'
        self.protocol.loaded = {'ProgramArguments': ['/foreign/python'], 'WorkingDirectory': '/foreign'}
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any('bootout' in c for c in self.protocol.calls))

    def test_modified_release_or_plist_blocks_install_and_uninstall(self):
        result = self.install(activate=True)
        for path in (Path(result['release']) / 'maintenance/controller.py', self.plist):
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            before = self.snapshot()
            with self.assertRaises(service.ServiceError):
                self.install(activate=True)
            with self.assertRaises(service.ServiceError):
                service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(any('bootout' in c for c in self.protocol.calls))
            path.write_bytes(original)

    def test_symlinked_home_and_unmanaged_release_preserved(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (self.home / 'Library').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        self.assertEqual(list(outside.iterdir()), [])
        (self.home / 'Library').unlink()
        target = self.root / 'releases' / SHA
        target.mkdir(parents=True)
        (target / 'unmanaged').write_bytes(b'keep')
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        self.assertEqual(self.snapshot(), before)

    def test_approved_owned_uninstall_stops_only_exact_label_retains_logs_and_state(self):
        self.install(activate=True)
        (self.root / 'state.sqlite3').write_bytes(b'private durable state')
        (self.root / 'state.sqlite3').chmod(0o600)
        before = self.snapshot()
        count = len(self.protocol.calls)
        self.assertEqual(service.uninstall(self.repository, home=self.home, runner=self.protocol)['status'], 'preview')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.protocol.calls), count)
        self.assertEqual(service.uninstall(self.repository, home=self.home, approve=True,
                                           runner=self.protocol)['status'], 'uninstalled')
        self.assertFalse(self.plist.exists())
        self.assertEqual((self.root / 'state.sqlite3').read_bytes(), b'private durable state')
        bootouts = [c for c in self.protocol.calls if 'bootout' in c]
        self.assertEqual(bootouts, [['/bin/launchctl', 'bootout', f'gui/{os.getuid()}/ai.aic.research-maintainer']])

    def test_uninstall_waits_for_owned_controller_exit_after_label_disappears(self):
        self.install(activate=True)
        self.protocol.pid = 987654
        checks = []
        def inspect_pid(pid, sig):
            self.assertIsNone(self.protocol.loaded)
            self.assertTrue(self.plist.exists())
            self.assertTrue((self.root / 'service.json').exists())
            self.assertTrue((self.root / 'shutdown.json').exists())
            checks.append((pid, sig))
            if len(checks) >= 3:
                raise ProcessLookupError
        with mock.patch.object(service.os, 'kill', side_effect=inspect_pid), \
                mock.patch.object(service.time, 'sleep'):
            result = service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(result['status'], 'uninstalled')
        self.assertEqual(checks, [(987654, 0)] * 3)
        self.assertFalse((self.root / 'shutdown.json').exists())

    def test_uncertain_controller_shutdown_preserves_artifacts_and_blocks_retry_until_exit(self):
        self.install(activate=True)
        self.protocol.pid = 987654
        before = self.snapshot()
        with mock.patch.object(service.os, 'kill'), \
                mock.patch.object(service, '_STOP_SECONDS', 0):
            with self.assertRaises(service.ServiceError):
                service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertIsNone(self.protocol.loaded)
        after = self.snapshot()
        self.assertEqual({key: value for key, value in after.items() if not key.endswith('/shutdown.json')}, before)
        self.assertTrue((self.root / 'shutdown.json').exists())
        self.assertEqual((self.root / 'shutdown.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(service.status(self.repository, home=self.home, runner=self.protocol)['status'],
                         'removal-pending')
        with mock.patch.object(service.os, 'kill'), \
                mock.patch.object(service, '_STOP_SECONDS', 0):
            with self.assertRaises(service.ServiceError):
                service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.snapshot(), after)
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        with mock.patch.object(service.os, 'kill', side_effect=ProcessLookupError):
            result = service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(result['status'], 'uninstalled')
        self.assertEqual(len([call for call in self.protocol.calls if 'bootout' in call]), 1)

    def test_pending_removal_can_resume_after_recorded_controller_finished_normally(self):
        self.install(activate=True)
        self.protocol.pid = 987654
        service._shutdown_record(self.root, self.protocol.loaded, create=True, pid=self.protocol.pid)
        self.protocol.pid = None
        with mock.patch.object(service.os, 'kill', side_effect=ProcessLookupError):
            result = service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(result['status'], 'uninstalled')
        self.assertIsNone(self.protocol.loaded)
        self.assertFalse(self.plist.exists())
        self.assertFalse((self.root / 'shutdown.json').exists())

    def test_pending_shutdown_never_stops_a_replacement_controller(self):
        self.install(activate=True)
        self.protocol.pid = 987654
        original_config = dict(self.protocol.loaded)
        with mock.patch.object(service.os, 'kill'), mock.patch.object(service, '_STOP_SECONDS', 0):
            with self.assertRaises(service.ServiceError):
                service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.protocol.loaded = original_config
        self.protocol.pid = 987655
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len([call for call in self.protocol.calls if 'bootout' in call]), 1)

    def test_ambiguous_running_pid_preserves_service_without_stopping_it(self):
        self.install(activate=True)
        def missing_pid(argv, **kwargs):
            result = self.protocol(argv, **kwargs)
            if 'print' in argv:
                result.stdout = result.stdout.replace(b'state = not running', b'state = running')
            return result
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=missing_pid)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any('bootout' in call for call in self.protocol.calls))

    def test_modified_pending_shutdown_evidence_never_stops_or_removes_service(self):
        self.install(activate=True)
        self.protocol.pid = 987654
        config = dict(self.protocol.loaded)
        with mock.patch.object(service.os, 'kill'), mock.patch.object(service, '_STOP_SECONDS', 0):
            with self.assertRaises(service.ServiceError):
                service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        marker = self.root / 'shutdown.json'
        evidence = json.loads(marker.read_bytes())
        evidence['config_digest'] = 'foreign'
        marker.write_bytes(service._canonical(evidence))
        self.protocol.loaded = config
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len([call for call in self.protocol.calls if 'bootout' in call]), 1)

    def test_foreign_loaded_configuration_blocks_owned_stop(self):
        self.install(activate=True)
        self.protocol.loaded['ProgramArguments'] = ['/foreign/python']
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any('bootout' in c for c in self.protocol.calls))

    def test_extra_or_linked_release_files_block_removal(self):
        result = self.install(activate=True)
        extra = Path(result['release']) / 'unexpected'
        extra.symlink_to(self.python)
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertTrue(extra.is_symlink())
        self.assertTrue(self.plist.exists())

    def test_hardlinked_release_and_manifest_tampering_preserve_service(self):
        result = self.install(activate=True)
        release = Path(result['release'])
        source = release / 'maintenance/controller.py'
        os.link(source, self.base / 'hardlink')
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.snapshot(), before)
        (self.base / 'hardlink').unlink()
        manifest = release / 'manifest.json'
        manifest.write_bytes(manifest.read_bytes() + b' ')
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        self.assertEqual(self.snapshot(), before)

    def test_receipt_traversal_and_changed_release_never_bootout(self):
        self.install(activate=True)
        path = self.root / 'service.json'
        receipt = json.loads(path.read_bytes())
        receipt['published_sha'] = '../../foreign'
        path.write_text(json.dumps(receipt))
        before = self.snapshot()
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any('bootout' in c for c in self.protocol.calls))

    def test_unloaded_repeated_install_does_not_restart(self):
        self.install(activate=True)
        self.protocol.loaded = None
        count = len([call for call in self.protocol.calls if 'bootstrap' in call])
        self.assertEqual(self.install(activate=True)['status'], 'unchanged')
        self.assertEqual(len([call for call in self.protocol.calls if 'bootstrap' in call]), count)

    def test_git_blob_mismatch_and_unconfirmed_bootstrap_are_not_success(self):
        def corrupt_blob(argv, **kwargs):
            result = self.protocol(argv, **kwargs)
            if 'cat-file' in argv:
                return subprocess.CompletedProcess(argv, 0, b'corrupt', b'')
            return result
        with self.assertRaises(service.ServiceError):
            service.install(self.repository, published_sha=SHA, python=self.python,
                            home=self.home, activate=True, runner=corrupt_blob)
        self.assertFalse(self.root.exists())
        def missing_bootstrap(argv, **kwargs):
            result = self.protocol(argv, **kwargs)
            if 'bootstrap' in argv:
                self.protocol.loaded = None
            return result
        with self.assertRaises(service.ServiceError):
            service.install(self.repository, published_sha=SHA, python=self.python,
                            home=self.home, activate=True, runner=missing_bootstrap)
        self.assertTrue(self.plist.exists())

    def test_linux_status_is_read_only_and_never_inspects_launchctl(self):
        self.install(activate=True)
        count = len(self.protocol.calls)
        with mock.patch.object(service.sys, 'platform', 'linux'):
            result = service.status(self.repository, home=self.home, runner=self.protocol)
        self.assertEqual(result['status'], 'installed')
        self.assertIsNone(result['loaded'])
        self.assertFalse(any(Path(call[0]).name == 'launchctl' for call in self.protocol.calls[count:]))

    def test_nonroot_checkout_and_receipt_wrong_types_are_refused(self):
        self.protocol.toplevel = self.base
        with self.assertRaises(service.ServiceError):
            self.install(activate=True)
        self.assertFalse(self.root.exists())
        self.protocol.toplevel = self.repository
        self.install(activate=True)
        path = self.root / 'service.json'
        receipt = json.loads(path.read_bytes())
        receipt['python'] = 42
        path.write_text(json.dumps(receipt))
        with self.assertRaises(service.ServiceError):
            service.uninstall(self.repository, home=self.home, approve=True, runner=self.protocol)
        self.assertFalse(any('bootout' in call for call in self.protocol.calls))

    def test_status_never_reports_foreign_loaded_label_as_absent(self):
        self.protocol.plist = '/foreign/job.plist'
        self.protocol.loaded = {'ProgramArguments': ['/foreign/python'], 'WorkingDirectory': '/foreign'}
        with self.assertRaises(service.ServiceError):
            service.status(self.repository, home=self.home, runner=self.protocol)
        self.assertFalse(any('bootout' in call or 'bootstrap' in call for call in self.protocol.calls))
