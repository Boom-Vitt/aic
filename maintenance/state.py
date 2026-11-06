"""Private durable state: capped runs, one publisher and no blind effect replay."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .policy import MAX_RUNS_PER_DAY, REPO, record_path

OWNER = 'aic-maintainer-v1:' + REPO
TERMINAL = ('complete', 'rejected')


class StateError(RuntimeError):
    pass


def _dump(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if len(text.encode('utf-8')) > 2 * 1024 * 1024:
        raise StateError('Maintenance state payload exceeds its bound.')
    return text


class State:
    def __init__(self, path: Path):
        self.path = Path(path).absolute()
        self.connection = None
        for ancestor in reversed((self.path, *self.path.parents)):
            if ancestor.is_symlink():
                raise StateError('Linked maintenance state paths are refused.')
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = self.path.parent.stat()
        if directory.st_uid != os.getuid() or directory.st_mode & 0o077:
            raise StateError('Maintenance state directory must be private and owned by this user.')
        if self.path.exists():
            metadata = self.path.stat()
            if not self.path.is_file() or metadata.st_nlink != 1 or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                raise StateError('Unmanaged or non-private maintenance state is preserved.')
            probe = None
            try:
                probe = sqlite3.connect('file:' + quote(str(self.path), safe='/') + '?mode=ro', uri=True)
                row = probe.execute('SELECT value FROM meta WHERE name = ?', ('owner',)).fetchone()
                if row is None or row[0] != OWNER:
                    raise StateError('Unmanaged maintenance database is preserved.')
            except sqlite3.Error as exc:
                raise StateError('Unmanaged maintenance database is preserved.') from exc
            finally:
                if probe is not None:
                    probe.close()
        else:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(descriptor)
            connection = sqlite3.connect(self.path)
            try:
                connection.executescript('''
                    CREATE TABLE meta(name TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE calls(day TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('research','review')), job TEXT NOT NULL, status TEXT NOT NULL, result TEXT, PRIMARY KEY(day,role));
                    CREATE TABLE jobs(key TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE effects(job TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, descriptor TEXT NOT NULL, result TEXT, PRIMARY KEY(job,name));
                    CREATE TABLE seen(key TEXT PRIMARY KEY, disposition TEXT NOT NULL);
                ''')
                connection.execute('INSERT INTO meta VALUES(?,?)', ('owner', OWNER))
                connection.commit()
            finally:
                connection.close()
        self.connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA synchronous=FULL')

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    @contextmanager
    def transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.execute('COMMIT')
        except BaseException:
            self.connection.execute('ROLLBACK')
            raise

    @contextmanager
    def exclusive(self):
        path = self.path.parent / 'controller.lock'
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if metadata.st_nlink != 1 or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                raise StateError('Unmanaged publisher lock is preserved.')
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise StateError('Another maintenance publisher is already running.') from exc
            yield
        finally:
            os.close(descriptor)

    def reserve(self, day: str, role: str, job: str):
        record_path(day)
        if role not in ('research', 'review'):
            raise StateError('Unknown unattended role.')
        with self.transaction():
            if self.runs(day) >= MAX_RUNS_PER_DAY or self.connection.execute('SELECT 1 FROM calls WHERE day=? AND role=?', (day, role)).fetchone():
                raise StateError('Daily unattended run allowance is exhausted; reserved and failed runs count.')
            self.connection.execute('INSERT INTO calls VALUES(?,?,?,?,NULL)', (day, role, job, 'reserved'))

    def runs(self, day: str) -> int:
        return self.connection.execute('SELECT count(*) FROM calls WHERE day=?', (day,)).fetchone()[0]

    def finish_run(self, day: str, role: str, job: str, result: object):
        cursor = self.connection.execute('UPDATE calls SET status=?,result=? WHERE day=? AND role=? AND job=? AND status=?', ('complete', _dump(result), day, role, job, 'reserved'))
        if cursor.rowcount != 1:
            raise StateError('Only the exact reserved run can be completed.')

    def run_result(self, job: str, role: str):
        row = self.connection.execute('SELECT result FROM calls WHERE job=? AND role=? AND status=? ORDER BY day DESC LIMIT 1', (job, role, 'complete')).fetchone()
        return json.loads(row[0]) if row is not None else None

    def meta(self, name: str, default=None):
        row = self.connection.execute('SELECT value FROM meta WHERE name=?', (name,)).fetchone()
        return row[0] if row is not None else default

    def set_meta(self, name: str, value: str):
        if name == 'owner':
            raise StateError('State ownership is immutable.')
        self.connection.execute('INSERT INTO meta VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value', (name, value))

    def save_job(self, key: str, status: str, payload: dict):
        encoded = _dump(payload)
        with self.transaction():
            active = self.connection.execute("SELECT key FROM jobs WHERE status NOT IN ('complete','rejected') AND key<>?", (key,)).fetchone()
            if status not in TERMINAL and active is not None:
                raise StateError('Only one integration job may publish at a time.')
            previous = self.connection.execute('SELECT status FROM jobs WHERE key=?', (key,)).fetchone()
            if previous is not None and previous[0] in TERMINAL and status != previous[0]:
                raise StateError('Completed maintenance work cannot be reopened by replay.')
            self.connection.execute('INSERT INTO jobs VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET status=excluded.status,payload=excluded.payload', (key, status, encoded))

    def active_job(self):
        rows = self.connection.execute("SELECT key,status,payload FROM jobs WHERE status NOT IN ('complete','rejected')").fetchall()
        if len(rows) > 1:
            raise StateError('Ambiguous concurrent maintenance jobs require owner inspection.')
        return dict(key=rows[0]['key'], status=rows[0]['status'], data=json.loads(rows[0]['payload'])) if rows else None

    def seen(self) -> set[str]:
        return {row[0] for row in self.connection.execute('SELECT key FROM seen')}

    def mark_seen(self, key: str, disposition: str):
        self.connection.execute('INSERT INTO seen VALUES(?,?) ON CONFLICT(key) DO UPDATE SET disposition=excluded.disposition', (key, disposition))

    def begin_effect(self, job: str, name: str, descriptor: dict):
        try:
            self.connection.execute('INSERT INTO effects VALUES(?,?,?,?,NULL)', (job, name, 'pending', _dump(descriptor)))
        except sqlite3.IntegrityError as exc:
            raise StateError('An external effect already exists; reconcile it without replay.') from exc

    def effect(self, job: str, name: str):
        row = self.connection.execute('SELECT status,descriptor,result FROM effects WHERE job=? AND name=?', (job, name)).fetchone()
        if row is None:
            return None
        return dict(status=row['status'], descriptor=json.loads(row['descriptor']), result=json.loads(row['result']) if row['result'] is not None else None)

    def finish_effect(self, job: str, name: str, result: object):
        cursor = self.connection.execute('UPDATE effects SET status=?,result=? WHERE job=? AND name=? AND status=?', ('complete', _dump(result), job, name, 'pending'))
        if cursor.rowcount != 1:
            raise StateError('Only an exact pending effect can be reconciled.')

    def summary(self, day: str) -> dict:
        active = self.active_job()
        return dict(runs_today=self.runs(day), maximum_runs=MAX_RUNS_PER_DAY, last_discovery=self.meta('last_discovery'), last_outcome=self.meta('last_outcome'),
                    active_job=dict(key=active['key'], status=active['status'], error=active['data'].get('error'), pr=active['data'].get('pr')) if active else None)
