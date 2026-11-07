"""Approved scoped reference notes; neither evidence nor prose grants authority."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from .safety import AICError, canonical_json, checked_root, relative_path, safe_path

_CANDIDATE = {'claim', 'source', 'source_date', 'checked_at', 'scope', 'status'}
_MAX_NOTE_BYTES = 1024 * 1024
_MAX_NOTE_ENTRIES = 256
_MAX_TOTAL_BYTES = 8 * 1024 * 1024


def _bounded_json(value):
    try:
        data = canonical_json(value)
    except (RecursionError, UnicodeError) as exc:
        raise AICError('Memory note cannot be represented safely as JSON.') from exc
    if len(data) > _MAX_NOTE_BYTES:
        raise AICError('Memory notes cannot exceed 1 MiB of canonical JSON.')
    return data


def _read_collection(root):
    folder = safe_path(root, '.aic/memory/notes')
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise AICError('Memory notes state is not a directory.')
    paths = []
    # scandir streams entries on all supported Python versions; Path.iterdir may list eagerly.
    with os.scandir(folder) as entries:
        for entry in entries:
            if len(paths) == _MAX_NOTE_ENTRIES:
                raise AICError('Memory collections cannot exceed 256 note entries.')
            paths.append(Path(entry.path))
    result = []
    total = 0
    for entry in sorted(paths):
        path = safe_path(root, entry.relative_to(root).as_posix(), must_exist=True)
        if not path.is_file() or path.suffix != '.json':
            raise AICError('Unexpected object in owned memory notes.')
        limit = min(_MAX_NOTE_BYTES, _MAX_TOTAL_BYTES - total)
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise AICError('Memory note or collection exceeds its byte budget.')
        total += len(raw)
        result.append((path, raw))
    return result


@contextmanager
def _promotion_lock(root):
    folder = safe_path(root, '.aic/memory')
    folder.mkdir(parents=True, exist_ok=True)
    lock = safe_path(root, '.aic/memory/.promotion-lock')
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise AICError('Memory promotion is already locked; no note was written.') from exc
    try:
        yield
    finally:
        lock.rmdir()


def _text(value):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise AICError('Expected nonempty text without NUL characters.')
    return value


def _reference(value):
    value = _text(value)
    if '://' in value:
        try:
            url = urlsplit(value)
            if (url.scheme != 'https' or not url.hostname or url.username is not None
                    or url.password is not None or url.query or url.fragment
                    or any(c.isspace() for c in value)):
                raise AICError('Evidence URLs require HTTPS without credentials, queries or fragments.')
            url.port
        except ValueError as exc:
            raise AICError('Malformed evidence URL.') from exc
    else:
        relative_path(value)
    return value


def _candidate(value, root=None):
    if not isinstance(value, dict) or len(value) != len(_CANDIDATE) or set(value) != _CANDIDATE:
        raise AICError('Memory requires only claim, source, dates, scope and status; no authorization fields.')
    # Bound flat candidate work before text scans, path checks or JSON allocation.
    size = 0
    for key in _CANDIDATE - {'scope'}:
        text = value[key]
        if not isinstance(text, str):
            raise AICError('Memory candidate fields must contain text.')
        size += len(text)
        if size > _MAX_NOTE_BYTES:
            raise AICError('Memory candidate exceeds the note byte budget.')
    scope = value['scope']
    if not isinstance(scope, list) or not scope or len(scope) > _MAX_NOTE_BYTES // 3:
        raise AICError('Memory requires a bounded nonempty scoped path list.')
    for path in scope:
        if not isinstance(path, str):
            raise AICError('Memory scope must contain relative path text.')
        size += len(path) + 3
        if size > _MAX_NOTE_BYTES:
            raise AICError('Memory candidate exceeds the note byte budget.')
    _text(value['claim'])
    _reference(value['source'])
    for key in ('source_date', 'checked_at'):
        try:
            text = value[key]
            if not isinstance(text, str) or date.fromisoformat(text).isoformat() != text:
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise AICError('Memory dates must be ISO YYYY-MM-DD dates.') from exc
    if value['status'] not in ('observed', 'source-declared'):
        raise AICError('Only observed or source-declared claims can be promoted; hypotheses remain candidates.')
    data = _bounded_json(value)
    for path in value['scope']:
        relative_path(path)
        if root is not None:
            safe_path(root, path)
    return json.loads(data)


def _source_hash(root, candidate, *, require):
    if urlsplit(candidate['source']).scheme == 'https':
        return None
    path = safe_path(root, candidate['source'], must_exist=require)
    if not path.exists() and not require:
        return None
    if not path.is_file():
        raise AICError('Memory source must be a regular file.')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def promote(root: Path, candidate: dict, *, approved=False) -> dict:
    root = checked_root(root)
    candidate = _candidate(candidate, root)
    if approved is not True:
        raise AICError('Explicit promotion approval is required; no note was written.')
    note = {'schema_version': 1, 'kind': 'aic-scoped-reference', 'candidate': candidate,
            'source_sha256': _source_hash(root, candidate, require=True)}
    data = _bounded_json(note)
    digest = hashlib.sha256(data).hexdigest()
    relative = f'.aic/memory/notes/{digest}.json'
    target = safe_path(root, relative)
    # Serialize capacity checks and exclusive creation across cooperating promoters.
    with _promotion_lock(root):
        existing = _read_collection(root)
        for path, raw in existing:
            if path == target:
                if raw != data:
                    raise AICError('Refusing a modified or colliding owned memory note.')
                return {'status': 'unchanged', 'path': relative, 'digest': digest}
        if (len(existing) == _MAX_NOTE_ENTRIES
                or sum(len(raw) for _, raw in existing) + len(data) > _MAX_TOTAL_BYTES):
            raise AICError('Memory promotion would exceed the collection budget.')
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also refuses a note created by a noncooperating writer.
        try:
            with target.open('xb') as stream:
                stream.write(data)
        except FileExistsError as exc:
            raise AICError('Memory note appeared concurrently; nothing was overwritten.') from exc
        return {'status': 'promoted', 'path': relative, 'digest': digest}


def read_notes(root: Path) -> list[dict]:
    root = checked_root(root)
    result = []
    for path, raw in _read_collection(root):
        try:
            note = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise AICError('Memory note is malformed.') from exc
        if (not isinstance(note, dict) or set(note) != {'schema_version', 'kind', 'candidate', 'source_sha256'}
                or type(note['schema_version']) is not int or note['schema_version'] != 1
                or note['kind'] != 'aic-scoped-reference'
                or _bounded_json(note) != raw
                or path.stem != hashlib.sha256(raw).hexdigest()):
            raise AICError('Memory ownership or integrity validation failed.')
        candidate = _candidate(note['candidate'], root)
        stored = note['source_sha256']
        if urlsplit(candidate['source']).scheme == 'https':
            if stored is not None:
                raise AICError('URL notes cannot claim a verified file hash.')
            stale = None
        else:
            if not isinstance(stored, str) or len(stored) != 64 or any(c not in '0123456789abcdef' for c in stored):
                raise AICError('Memory source hash is malformed.')
            stale = _source_hash(root, candidate, require=False) != stored
        result.append({'note': note, 'path': path.relative_to(root).as_posix(),
                       'authority': 'reference-data-only', 'stale': stale,
                       'source_verification': 'not-fetched' if stale is None else 'local-hash'})
    return result


def validate_handoff(value: dict) -> dict:
    fields = {'objective', 'confirmed', 'unverified', 'evidence', 'uncertain_actions', 'blockers', 'next_action'}
    if not isinstance(value, dict) or set(value) != fields:
        raise AICError('Handoff fields must match the read-only handoff schema; approval is not accepted.')
    _text(value['objective'])
    _text(value['next_action'])
    for key in fields - {'objective', 'next_action'}:
        if not isinstance(value[key], list):
            raise AICError('Handoff evidence and findings must be lists.')
        for item in value[key]:
            (_reference if key == 'evidence' else _text)(item)
    return json.loads(canonical_json(value))
