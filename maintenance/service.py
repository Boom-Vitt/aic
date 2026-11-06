"""Opt-in immutable macOS LaunchAgent, not an always-online scheduler.

install() without activate and uninstall() without approve are non-mutating,
process-free previews (they do not assert publication). All three public functions
accept runner=subprocess.run-compatible injection: argv plus cwd, capture_output,
timeout, check and env keywords; return CompletedProcess with byte stdout/stderr.
An injected runner is a protocol-test seam, not permission to bypass platform,
publication, ownership or explicit approval checks. Only the integration owner
may activate the real service after proof. LaunchAgents require a logged-in user;
sleep, shutdown, logout and network outages prevent work. There is no self-update.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import time

LABEL = 'ai.aic.research-maintainer'
REPO = 'Boom-Vitt/aic'
_SHA = re.compile(r'[0-9a-f]{40}')
_MODULE = re.compile(r'maintenance/[A-Za-z_][A-Za-z_0-9]*\.py')
_REQUIRED = {f'maintenance/{name}.py' for name in (
    '__init__', 'contracts', 'policy', 'state', 'collector', 'github',
    'agents', 'controller', 'service')}
_REQUIRED.update(('maintenance/sources.json', 'scripts/maintain.py',
                  'skills/aic/assets/workflows.json'))
_LAUNCHCTL = '/bin/launchctl'
_LIMIT = 16 * 1024 * 1024
_STOP_SECONDS = 30


class ServiceError(RuntimeError):
    """A failed-closed service boundary; existing artifacts are preserved."""


def _boundary(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
            raise ServiceError('Service operation failed; inspect owned artifacts before retrying.') from exc
    return call


def _path(value: Path) -> Path:
    value = Path(value).expanduser()
    if '..' in value.parts or any('\n' in part or '\r' in part for part in value.parts):
        raise ServiceError('Traversal and multiline paths are refused.')
    return value.absolute()


@contextmanager
def _directory(path: Path, *, create=False, private=False):
    """Walk directory descriptors with O_NOFOLLOW, including every ancestor."""
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if private and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise ServiceError('Owned service directories must be private mode 0700.')
        yield fd
    finally:
        os.close(fd)


def _visible(path: Path, fd: int):
    with _directory(path) as current:
        old, new = os.fstat(fd), os.fstat(current)
        if (old.st_dev, old.st_ino) != (new.st_dev, new.st_ino):
            raise ServiceError('A service directory moved concurrently; refusing mutation.')


def _read(fd: int, name: str) -> bytes:
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(child, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > _LIMIT):
            raise ServiceError('Unmanaged, non-private or special service file is preserved.')
        data = stream.read(_LIMIT + 1)
        after = os.fstat(stream.fileno())
        if len(data) > _LIMIT or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ServiceError('A service file changed during inspection.')
        return data


def _log(fd: int, name: str):
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        info = os.fstat(child)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise ServiceError('Unmanaged or non-private log is preserved.')
    finally:
        os.close(child)


def _write(fd: int, name: str, data: bytes):
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    with os.fdopen(child, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allowed(name: str) -> bool:
    return bool(_MODULE.fullmatch(name)) or name in _REQUIRED


def _command(runner, argv, repository, *, allow_missing=False):
    # Existing subscription-backed authentication stays in the CLI's own store;
    # no token is copied to the plist, snapshot, receipt or error messages.
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_NO_REPLACE_OBJECTS='1', GIT_OPTIONAL_LOCKS='0')
    result = runner(argv, cwd=str(repository), capture_output=True, timeout=60,
                    check=False, env=environment)
    if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
        raise ServiceError('Service runner must return byte output.')
    if len(result.stdout) > _LIMIT or len(result.stderr) > _LIMIT:
        raise ServiceError('Service command output exceeds its bound.')
    if result.returncode:
        if (allow_missing and result.returncode == 113 and
                b'Could not find service "' + LABEL.encode() + b'"' in result.stderr):
            return None
        raise ServiceError(f'Read-only inspection or service command failed: {Path(argv[0]).name}')
    return result.stdout


def _binaries(home: Path, required=('git', 'gh', 'omp')):
    search = ':'.join(map(str, (Path('/opt/homebrew/bin'), Path('/usr/local/bin'),
                               home / '.local/bin', home / '.bun/bin', Path('/usr/bin'), Path('/bin'))))
    found = {}
    for name in required:
        value = shutil.which(name, path=search)
        if not value or not Path(value).is_absolute() or not Path(value).is_file() or not os.access(value, os.X_OK):
            raise ServiceError(f'Required existing executable is unavailable: {name}')
        found[name] = value
    path = ':'.join(dict.fromkeys([str(Path(value).parent) for value in found.values()] + ['/usr/bin', '/bin']))
    return found, path


def _publication(repository, sha, binaries, runner):
    git, gh = binaries['git'], binaries['gh']
    toplevel = _command(runner, [git, 'rev-parse', '--show-toplevel'], repository).decode().strip()
    if toplevel != str(repository):
        raise ServiceError('The service project must be the exact repository checkout root.')
    remote = _command(runner, [git, 'remote', 'get-url', 'origin'], repository).decode().strip()
    if remote not in ('https://github.com/Boom-Vitt/aic.git', 'https://github.com/Boom-Vitt/aic',
                      'git@github.com:Boom-Vitt/aic.git', 'ssh://git@github.com/Boom-Vitt/aic.git'):
        raise ServiceError('Only the approved Boom-Vitt/aic origin is accepted.')
    metadata = json.loads(_command(runner, [gh, 'api', '--hostname', 'github.com', '--method', 'GET', 'repos/' + REPO], repository))
    if not isinstance(metadata, dict) or metadata.get('full_name') != REPO or metadata.get('default_branch') != 'main':
        raise ServiceError('The approved repository and main branch must be verified.')
    head = json.loads(_command(runner, [gh, 'api', '--hostname', 'github.com', '--method', 'GET', f'repos/{REPO}/commits/main'], repository))
    main = head.get('sha') if isinstance(head, dict) else None
    if not isinstance(main, str) or not _SHA.fullmatch(main):
        raise ServiceError('Published main has no complete commit identity.')
    comparison = json.loads(_command(runner, [gh, 'api', '--hostname', 'github.com', '--method', 'GET', f'repos/{REPO}/compare/{sha}...{main}'], repository))
    if (not isinstance(comparison, dict) or comparison.get('status') != ('identical' if main == sha else 'ahead') or
            not isinstance(comparison.get('base_commit'), dict) or
            not isinstance(comparison.get('merge_base_commit'), dict) or
            comparison['base_commit'].get('sha') != sha or
            comparison['merge_base_commit'].get('sha') != sha):
        raise ServiceError('Requested commit is not published and reachable in approved main.')


def _snapshot(repository, sha, git, runner):
    resolved = _command(runner, [git, 'rev-parse', '--verify', sha + '^{commit}'], repository).decode().strip()
    if resolved != sha:
        raise ServiceError('The exact published commit is not present locally.')
    tree = _command(runner, [git, 'ls-tree', '-r', '-z', '--full-tree', sha, '--',
                             'maintenance', 'scripts/maintain.py', 'skills/aic/assets/workflows.json'], repository)
    if not tree.endswith(b'\0'):
        raise ServiceError('Incomplete committed tree inventory.')
    files = {}
    for entry in tree[:-1].split(b'\0'):
        metadata, name = entry.split(b'\t', 1)
        name = name.decode('utf-8')
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or str(relative) != name:
            raise ServiceError('Unsafe committed source path.')
        mode, kind, oid = metadata.decode('ascii').split(' ')
        if not _allowed(name):
            # Non-code maintenance assets are not part of the source allowlist.
            continue
        if mode not in ('100644', '100755') or kind != 'blob' or not _SHA.fullmatch(oid) or name in files:
            raise ServiceError('Snapshot requires unique regular committed source files.')
        data = _command(runner, [git, 'cat-file', 'blob', oid], repository)
        if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != oid:
            raise ServiceError('Committed blob does not match its immutable object identity.')
        files[name] = data
    if not _REQUIRED.issubset(files):
        raise ServiceError('Published commit lacks a complete maintainer snapshot/core files.')
    if sum(map(len, files.values())) > _LIMIT:
        raise ServiceError('Snapshot exceeds its total size bound.')
    manifest = {'version': 1, 'label': LABEL, 'repository': REPO, 'published_sha': sha,
                'files': {name: _digest(data) for name, data in sorted(files.items())}}
    return files, _canonical(manifest)


def _locations(repository, home):
    repository, home = _path(repository), _path(home if home is not None else Path.home())
    with _directory(repository):
        pass
    with _directory(home):
        pass
    root = repository / '.work/maintainer'
    plist = home / 'Library/LaunchAgents' / (LABEL + '.plist')
    return repository, home, root, plist


def _config(repository, root, release, python, path):
    # Isolated mode excludes working-directory/user-site/PYTHONPATH imports;
    # -B prevents mutable __pycache__ files inside the hash-bound snapshot.
    return {'Label': LABEL, 'ProgramArguments': [str(python), '-I', '-B', str(release / 'scripts/maintain.py'),
                                               'run-once', '--project', str(repository), '--publish'],
            'WorkingDirectory': str(repository), 'StartInterval': 900, 'RunAtLoad': True,
            'EnvironmentVariables': {'PATH': path},
            'StandardOutPath': str(root / 'stdout.log'), 'StandardErrorPath': str(root / 'stderr.log'),
            'Umask': 0o077}


def _loaded(repository, runner):
    return _command(runner, [_LAUNCHCTL, 'print', f'gui/{os.getuid()}/{LABEL}'], repository, allow_missing=True)


def _prove_loaded(output, plist, config):
    if output is None:
        return
    text = output.decode('utf-8')
    def field(name):
        matches = re.findall(r'^\s*' + re.escape(name) + r' = (.+)$', text, re.MULTILINE)
        if len(matches) != 1:
            raise ServiceError('Loaded label ownership cannot be proven.')
        return matches[0].strip()
    blocks = re.findall(r'^\s*arguments = \{\n(.*?)^\s*\}', text, re.MULTILINE | re.DOTALL)
    if len(blocks) != 1:
        raise ServiceError('Loaded label arguments cannot be proven.')
    arguments = [line.strip() for line in blocks[0].splitlines() if line.strip()]
    if (field('path') != str(plist) or field('program') != config['ProgramArguments'][0] or
            field('working directory') != config['WorkingDirectory'] or arguments != config['ProgramArguments']):
        raise ServiceError('Existing loaded label is unmanaged or modified; preserving it.')


def _controller_pid(output):
    if output is None:
        return None
    text = output.decode('utf-8')
    states = re.findall(r'^\s*state = (.+)$', text, re.MULTILINE)
    pids = re.findall(r'^\s*pid = (.+)$', text, re.MULTILINE)
    if len(pids) == 1 and re.fullmatch(r'[1-9][0-9]*', pids[0]) and int(pids[0]) <= 2**31 - 1:
        return int(pids[0])
    if not pids and states == ['not running']:
        return None
    raise ServiceError('Controller PID or idle state cannot be proven; preserving the service.')


def _shutdown_record(root, config, *, create=False, pid=None):
    """Persist the exact PID before bootout, so an uncertain retry cannot forget it."""
    name = 'shutdown.json'
    binding = {'version': 1, 'label': LABEL,
               'config_digest': _digest(plistlib.dumps(config, sort_keys=True))}
    with _directory(root, private=True) as fd:
        try:
            raw = _read(fd, name)
        except FileNotFoundError:
            if not create:
                return None
            _visible(root, fd)
            raw = _canonical({**binding, 'pid': pid})
            _write(fd, name, raw)
        record = json.loads(raw)
        if (not isinstance(record, dict) or set(record) != {*binding, 'pid'} or
                any(record.get(key) != value for key, value in binding.items()) or
                not (record['pid'] is None or type(record['pid']) is int and 0 < record['pid'] <= 2**31 - 1) or
                raw != _canonical(record)):
            raise ServiceError('Modified or foreign shutdown evidence is preserved.')
    return record


def _wait_controller(pid):
    if pid is None:
        return
    deadline = time.monotonic() + _STOP_SECONDS
    while True:
        try:
            # Signal zero is read-only. Never send a signal to a cached/reused PID:
            # only launchd's previously proven owned label receives bootout.
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        if time.monotonic() >= deadline:
            raise ServiceError('Owned controller shutdown is unconfirmed; preserving service and shutdown evidence.')
        time.sleep(0.1)


def _receipt(repository, home, sha, python, path):
    return {'version': 1, 'label': LABEL, 'repository': str(repository), 'home': str(home),
            'published_sha': sha, 'python': str(python), 'path': path}


def _inventory(path):
    files, directories = {}, set()
    def visit(fd, prefix=''):
        for name in os.listdir(fd):
            relative = prefix + name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise ServiceError('Non-private release directory is preserved.')
                directories.add(relative)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    visit(child, relative + '/')
                finally:
                    os.close(child)
            else:
                files[relative] = _read(fd, name)
    with _directory(path, private=True) as fd:
        visit(fd)
    return files, directories


def _parents(files):
    return {str(parent) for name in files for parent in PurePosixPath(name).parents if str(parent) != '.'}


def _owned(repository, home, root, plist, runner, git):
    with _directory(root, private=True) as fd:
        raw = _read(fd, 'service.json')
        receipt = json.loads(raw)
        if not isinstance(receipt, dict) or set(receipt) != {'version', 'label', 'repository', 'home', 'published_sha', 'python', 'path'}:
            raise ServiceError('Malformed service ownership receipt is preserved.')
        sha = receipt['published_sha']
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            raise ServiceError('Invalid release identity in ownership receipt.')
        if not isinstance(receipt['python'], str):
            raise ServiceError('Invalid Python identity in ownership receipt.')
        python, path = _path(receipt['python']), receipt['path']
        if not isinstance(path, str) or not path or any(not p.startswith('/') or '..' in Path(p).parts for p in path.split(':')):
            raise ServiceError('Invalid fixed service PATH in ownership receipt.')
        if raw != _canonical(_receipt(repository, home, sha, python, path)):
            raise ServiceError('Modified or foreign ownership receipt is preserved.')
        for log in ('stdout.log', 'stderr.log'):
            _log(fd, log)
    files, manifest = _snapshot(repository, sha, git, runner)
    files = {**files, 'manifest.json': manifest}
    release = root / 'releases' / sha
    actual, directories = _inventory(release)
    if actual != files or directories != _parents(files):
        raise ServiceError('Modified, missing or unexpected release artifacts are preserved.')
    with _directory(root / 'releases', private=True) as fd:
        if set(os.listdir(fd)) != {sha}:
            raise ServiceError('Unmanaged prior releases are preserved; no self-update is allowed.')
    config = _config(repository, root, release, python, path)
    with _directory(plist.parent) as fd:
        if _read(fd, plist.name) != plistlib.dumps(config, sort_keys=True):
            raise ServiceError('Modified or unmanaged LaunchAgent plist is preserved.')
    return receipt, files, release, config


def _present(path):
    """Inspect safely without following a symlink, even for an absent leaf."""
    try:
        with _directory(path.parent) as fd:
            os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            return True
    except FileNotFoundError:
        return False


@_boundary
def install(repository: Path, *, published_sha: str, python: Path, home: Path | None = None,
            activate: bool = False, runner=None) -> dict:
    """Preview without processes; activate only explicitly on macOS after proof."""
    repository, home, root, plist = _locations(repository, home)
    python = _path(python)
    if not isinstance(published_sha, str) or not _SHA.fullmatch(published_sha):
        raise ServiceError('A full lowercase published Git commit SHA is required.')
    release = root / 'releases' / published_sha
    report = {'label': LABEL, 'release': str(release), 'plist': str(plist),
              'published_sha': published_sha, 'publication_verified': False,
              'availability': 'Only while this Mac is awake, online and the user is logged in.'}
    if not activate:
        return {**report, 'status': 'preview'}
    if sys.platform != 'darwin':
        raise ServiceError('LaunchAgent activation is supported only on macOS.')
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ServiceError('An explicit existing Python executable is required.')
    runner = runner or subprocess.run
    binaries, path = _binaries(home)
    _publication(repository, published_sha, binaries, runner)
    files, manifest = _snapshot(repository, published_sha, binaries['git'], runner)
    expected_receipt = _receipt(repository, home, published_sha, python, path)
    if _present(root / 'service.json'):
        receipt, _, _, config = _owned(repository, home, root, plist, runner, binaries['git'])
        if receipt != expected_receipt:
            raise ServiceError('Existing release/configuration differs; no automatic self-update is allowed.')
        if _shutdown_record(root, config) is not None:
            raise ServiceError('Owned removal is pending; inspect shutdown evidence before activation.')
        _prove_loaded(_loaded(repository, runner), plist, config)
        return {**report, 'status': 'unchanged', 'publication_verified': True}
    if _present(plist):
        raise ServiceError('Existing unmanaged LaunchAgent plist is preserved.')
    if _present(root / 'releases'):
        with _directory(root / 'releases', private=True) as fd:
            if os.listdir(fd):
                raise ServiceError('Existing unmanaged releases are preserved.')
    # Inspect absent parents too, before creating any repository/home artifact.
    _present(plist)
    if _loaded(repository, runner) is not None:
        raise ServiceError('Existing loaded label is preserved; only a new owned service may be bootstrapped.')
    config = _config(repository, root, release, python, path)
    with _directory(root, create=True, private=True) as fd:
        _visible(root, fd)
        for log in ('stdout.log', 'stderr.log'):
            try:
                _log(fd, log)
            except FileNotFoundError:
                _write(fd, log, b'')
    with _directory(root / 'releases', create=True, private=True) as fd:
        _visible(root / 'releases', fd)
        os.mkdir(published_sha, 0o700, dir_fd=fd)
    for directory in sorted(_parents(files), key=lambda value: (value.count('/'), value)):
        with _directory(release / directory, create=True, private=True):
            pass
    for name, data in {**files, 'manifest.json': manifest}.items():
        destination = release / name
        with _directory(destination.parent, private=True) as fd:
            _visible(destination.parent, fd)
            _write(fd, destination.name, data)
    with _directory(plist.parent, create=True) as fd:
        _visible(plist.parent, fd)
        _write(fd, plist.name, plistlib.dumps(config, sort_keys=True))
    with _directory(root, private=True) as fd:
        _visible(root, fd)
        _write(fd, 'service.json', _canonical(expected_receipt))
    # Never bootout/restart an existing label, even if a race loaded it meanwhile.
    if _loaded(repository, runner) is not None:
        raise ServiceError('Label appeared concurrently; activation refused without stopping it.')
    _command(runner, [_LAUNCHCTL, 'bootstrap', f'gui/{os.getuid()}', str(plist)], repository)
    output = _loaded(repository, runner)
    if output is None:
        raise ServiceError('Bootstrap did not produce a provably loaded service.')
    _prove_loaded(output, plist, config)
    return {**report, 'status': 'installed', 'publication_verified': True}


@_boundary
def status(repository: Path, *, home: Path | None = None, runner=None) -> dict:
    """Read-only artifact/loaded-label inspection; never starts a job."""
    repository, home, root, plist = _locations(repository, home)
    if not _present(root / 'service.json'):
        if _present(plist):
            raise ServiceError('Unmanaged plist has no service ownership receipt.')
        if sys.platform == 'darwin' and _loaded(repository, runner or subprocess.run) is not None:
            raise ServiceError('Loaded label has no service ownership receipt; preserving it.')
        return {'status': 'not-installed', 'label': LABEL, 'loaded': None}
    runner = runner or subprocess.run
    binaries, _ = _binaries(home, required=('git',))
    receipt, _, release, config = _owned(repository, home, root, plist, runner, binaries['git'])
    loaded = None
    if sys.platform == 'darwin':
        output = _loaded(repository, runner)
        _prove_loaded(output, plist, config)
        loaded = output is not None
    pending = _shutdown_record(root, config) is not None
    return {'status': 'removal-pending' if pending else 'loaded' if loaded else 'installed', 'label': LABEL, 'loaded': loaded,
            'published_sha': receipt['published_sha'], 'release': str(release), 'plist': str(plist)}


@_boundary
def uninstall(repository: Path, *, home: Path | None = None, approve: bool = False, runner=None) -> dict:
    """Explicitly stop/remove only the exact intact owned service; retain logs/state."""
    repository, home, root, plist = _locations(repository, home)
    if not approve:
        return {'status': 'preview', 'label': LABEL, 'plist': str(plist)}
    if sys.platform != 'darwin':
        raise ServiceError('LaunchAgent removal is supported only on macOS.')
    runner = runner or subprocess.run
    binaries, _ = _binaries(home, required=('git',))
    _, files, release, config = _owned(repository, home, root, plist, runner, binaries['git'])
    output = _loaded(repository, runner)
    _prove_loaded(output, plist, config)
    pid = _controller_pid(output)
    pending = _shutdown_record(root, config)
    if pending is not None and output is not None and pending['pid'] != pid:
        if pid is not None:
            raise ServiceError('Loaded controller differs from pending shutdown evidence; preserving it.')
        _wait_controller(pending['pid'])
    if pending is None:
        pending = _shutdown_record(root, config, create=True, pid=pid)
    if output is not None:
        _command(runner, [_LAUNCHCTL, 'bootout', f'gui/{os.getuid()}/{LABEL}'], repository)
        if _loaded(repository, runner) is not None:
            raise ServiceError('Label is still loaded; preserving its files.')
    _wait_controller(pending['pid'])
    if _loaded(repository, runner) is not None or _shutdown_record(root, config) != pending:
        raise ServiceError('Service or shutdown evidence changed; preserving its files.')
    with _directory(plist.parent) as fd:
        _visible(plist.parent, fd)
        if _read(fd, plist.name) != plistlib.dumps(config, sort_keys=True):
            raise ServiceError('Plist changed before removal; preserving it.')
        os.unlink(plist.name, dir_fd=fd)
    for name, data in files.items():
        destination = release / name
        with _directory(destination.parent, private=True) as fd:
            _visible(destination.parent, fd)
            if _read(fd, destination.name) != data:
                raise ServiceError('Release changed before removal; preserving remaining files.')
            os.unlink(destination.name, dir_fd=fd)
    for directory in sorted(_parents(files), key=lambda value: (value.count('/'), value), reverse=True):
        destination = release / directory
        with _directory(destination.parent, private=True) as fd:
            _visible(destination.parent, fd)
            os.rmdir(destination.name, dir_fd=fd)
    with _directory(release.parent, private=True) as fd:
        _visible(release.parent, fd)
        os.rmdir(release.name, dir_fd=fd)
    with _directory(root, private=True) as fd:
        _visible(root, fd)
        expected = _canonical(pending)
        if _read(fd, 'shutdown.json') != expected:
            raise ServiceError('Shutdown evidence changed; preserving it.')
        os.unlink('shutdown.json', dir_fd=fd)
        os.unlink('service.json', dir_fd=fd)
    return {'status': 'uninstalled', 'label': LABEL, 'retained': str(root)}
