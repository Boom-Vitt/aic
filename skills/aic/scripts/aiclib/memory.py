"""Approved scoped reference notes; neither evidence nor prose grants authority."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .safety import AICError, canonical_json, checked_root, relative_path, safe_path

_CANDIDATE = {'claim', 'source', 'source_date', 'checked_at', 'scope', 'status'}


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
    if not isinstance(value, dict) or set(value) != _CANDIDATE:
        raise AICError('Memory requires only claim, source, dates, scope and status; no authorization fields.')
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
    if not isinstance(value['scope'], list) or not value['scope']:
        raise AICError('Memory requires a nonempty scoped path list.')
    for path in value['scope']:
        relative_path(path)
        if root is not None:
            safe_path(root, path)
    return json.loads(canonical_json(value))


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
    data = canonical_json(note)
    digest = hashlib.sha256(data).hexdigest()
    relative = f'.aic/memory/notes/{digest}.json'
    target = safe_path(root, relative)
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise AICError('Refusing a modified or colliding owned memory note.')
        return {'status': 'unchanged', 'path': relative, 'digest': digest}
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents overwriting an existing note on a concurrent promotion.
    try:
        with target.open('xb') as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise AICError('Memory note appeared concurrently; nothing was overwritten.') from exc
    return {'status': 'promoted', 'path': relative, 'digest': digest}


def read_notes(root: Path) -> list[dict]:
    root = checked_root(root)
    folder = safe_path(root, '.aic/memory/notes')
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise AICError('Memory notes state is not a directory.')
    result = []
    for entry in sorted(folder.iterdir()):
        path = safe_path(root, entry.relative_to(root).as_posix(), must_exist=True)
        if not path.is_file() or path.suffix != '.json':
            raise AICError('Unexpected object in owned memory notes.')
        try:
            raw = path.read_bytes()
            note = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise AICError('Memory note is malformed.') from exc
        if (not isinstance(note, dict) or set(note) != {'schema_version', 'kind', 'candidate', 'source_sha256'}
                or type(note['schema_version']) is not int or note['schema_version'] != 1
                or note['kind'] != 'aic-scoped-reference'
                or canonical_json(note) != raw
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
