"""Registry-backed discovery roots and non-destructive, manifest-owned installs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from .safety import AICError, canonical_json, checked_root

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "assets/harnesses.json"
_MANIFEST = ".aic-install.json"
_SCHEMA_VERSION = 1
_RUNTIME_DIRECTORIES = frozenset({
    "__pycache__", ".aic", ".work", ".git", ".venv", "venv", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
})
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_AGENT_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SAFE_MUTATION_PRIMITIVES = (
    os.name == "posix"
    and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and hasattr(os, "fchmod")
    and all(function in os.supports_dir_fd for function in (os.open, os.stat, os.mkdir, os.rename, os.unlink, os.rmdir))
    and os.listdir in os.supports_fd
    and os.stat in os.supports_follow_symlinks
)


def _json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AICError("Duplicate JSON keys are not allowed in installer metadata.")
        result[key] = value
    return result


def _relative(value: object) -> Path:
    """Validate install metadata lexically, not with codebase privacy exclusions.

    Discovery adapters intentionally name configuration roots such as .config.
    Neither those roots nor package-owned paths are codebase evidence selection.
    """
    if not isinstance(value, str) or not value or value != value.strip():
        raise AICError("Installer metadata requires a nonempty relative path.")
    if "\x00" in value or "\\" in value or ":" in value:
        raise AICError("Installer paths cannot contain NUL, backslashes or drive prefixes.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or Path(value).is_absolute():
        raise AICError("Installer paths cannot be absolute, noncanonical or traverse directories.")
    return Path(*parts)


def _directory(value: str | Path, *, must_exist: bool, absolute: bool = False) -> Path:
    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise AICError("An explicit directory path is required.") from exc
    if not isinstance(raw, str) or not raw or "\x00" in raw or "\\" in raw or ".." in raw.split("/"):
        raise AICError("Directory paths must not contain traversal, NUL or backslashes.")
    if absolute and not Path(raw).is_absolute():
        raise AICError("Install and uninstall require an absolute destination path.")
    return checked_root(raw, must_exist=must_exist)


def _registry() -> dict[str, dict]:
    try:
        with _REGISTRY_PATH.open(encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_json_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AICError("The harness registry cannot be read as valid JSON.") from exc
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise AICError("The harness registry has an unsupported schema version.")
    if not isinstance(value.get("agents"), list):
        raise AICError("The harness registry requires an agents array.")
    agents = {}
    required = {"id", "name", "project", "user", "source", "status"}
    for entry in value["agents"]:
        if not isinstance(entry, dict) or set(entry) != required:
            raise AICError("The harness registry contains a malformed adapter.")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not _AGENT_ID.fullmatch(identifier) or identifier == "generic" or identifier in agents:
            raise AICError("The harness registry contains an invalid or duplicate adapter ID.")
        if not isinstance(entry["name"], str) or not entry["name"].strip() or entry["status"] != "documented":
            raise AICError("Harness adapters must have a name and documented status.")
        if not isinstance(entry["source"], str):
            raise AICError("Harness adapters require an official HTTPS source URL.")
        try:
            source = urlsplit(entry["source"])
            if source.scheme != "https" or not source.hostname or source.username is not None or source.password is not None:
                raise ValueError("Not a public HTTPS source")
        except ValueError as exc:
            raise AICError("Harness adapters require an official HTTPS source URL.") from exc
        for scope in ("project", "user"):
            if entry[scope] is not None:
                _relative(entry[scope])
        agents[identifier] = entry
    return agents


def destination(
    agent: str,
    scope: str,
    *,
    project: str | Path | None = None,
    home: str | Path | None = None,
    destination: str | Path | None = None,
) -> Path:
    """Return the final /aic path without creating directories or changing state."""
    if not isinstance(scope, str) or scope not in {"project", "user"}:
        raise AICError("Install scope must be project or user.")
    if not isinstance(agent, str) or not agent:
        raise AICError("A documented harness name or generic is required.")
    if agent == "generic":
        if destination is None:
            raise AICError("Generic installs require an explicit skill-root destination directory.")
        root = _directory(destination, must_exist=False)
    else:
        adapters = _registry()
        if agent not in adapters:
            raise AICError(f"Unsupported harness: {agent}")
        if destination is not None:
            raise AICError("Explicit destination overrides require the generic adapter.")
        relative = adapters[agent][scope]
        if relative is None:
            raise AICError(f"The {agent} adapter does not document {scope} scope.")
        if scope == "project":
            if project is None:
                raise AICError("Project installs require an explicit project directory.")
            base = _directory(project, must_exist=True)
        else:
            base = _directory(home if home is not None else Path.home(), must_exist=True)
        root = _directory(base / _relative(relative), must_exist=False)
    return _directory(root / "aic", must_exist=False)


def _target(value: Path) -> Path:
    target = _directory(value, must_exist=False, absolute=True)
    if target.name != "aic":
        raise AICError("The final installed skill directory must be named aic.")
    return target


def _require_safe_mutation() -> None:
    if not _SAFE_MUTATION_PRIMITIVES:
        raise AICError("Safe installation requires POSIX no-follow directory descriptors and dir_fd filesystem operations; this platform is unsupported.")


def _open_child(parent: int, name: str) -> int:
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)


def _open_directory(path: Path, *, create: bool = False) -> int:
    """Open every component relative to its verified parent, never a symlink."""
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in path.parts[1:]:
            if create:
                try:
                    os.mkdir(name, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = _open_child(descriptor, name)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _assert_identity(parent: int, name: str, descriptor: int) -> None:
    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(named.st_mode) or _identity(named) != _identity(os.fstat(descriptor)):
        raise AICError("An installer directory was replaced concurrently; refusing further mutation.")


def _assert_visible_parent(path: Path, descriptor: int) -> None:
    current = _open_directory(path)
    try:
        if _identity(os.fstat(current)) != _identity(os.fstat(descriptor)):
            raise AICError("The destination parent moved concurrently; refusing further mutation.")
    finally:
        os.close(current)


def _file_descriptor(parent: int, name: str) -> int:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise AICError("Only regular package files may be read.")
    return descriptor


def _read_file(parent: int, name: str) -> bytes:
    with os.fdopen(_file_descriptor(parent, name), "rb") as handle:
        before = os.fstat(handle.fileno())
        content = handle.read()
        after = os.fstat(handle.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise AICError("A package file changed while it was being inspected.")
    return content


def _inventory_fd(root: int, *, source: bool = False) -> dict:
    files = {}
    directories = []

    def visit(descriptor: int, prefix: str = "") -> None:
        for name in sorted(os.listdir(descriptor)):
            relative = f"{prefix}/{name}" if prefix else name
            if source and (name in _RUNTIME_DIRECTORIES or name.endswith((".pyc", ".pyo"))):
                continue
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if relative == _MANIFEST:
                if not stat.S_ISREG(info.st_mode):
                    raise AICError("The install ownership manifest must be a regular file.")
                continue
            _relative(relative)
            if stat.S_ISDIR(info.st_mode):
                child = _open_child(descriptor, name)
                try:
                    if _identity(info) != _identity(os.fstat(child)):
                        raise AICError("A package directory changed during inspection.")
                    directories.append(relative)
                    visit(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                files[relative] = hashlib.sha256(_read_file(descriptor, name)).hexdigest()
            else:
                raise AICError(f"Symlinks and special package files are not allowed: {relative}")

    visit(root)
    if "SKILL.md" not in files:
        raise AICError("A self-contained skill requires a regular SKILL.md entry point.")
    return {"schema_version": _SCHEMA_VERSION, "package": "aic", "files": files, "directories": sorted(directories)}


def _validate_manifest(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema_version", "package", "files", "directories"}:
        raise AICError("The install ownership manifest is malformed; no files were changed.")
    if type(value["schema_version"]) is not int or value["schema_version"] != _SCHEMA_VERSION or value["package"] != "aic":
        raise AICError("The install ownership manifest has an unsupported package or version.")
    files, directories = value["files"], value["directories"]
    if not isinstance(files, dict) or "SKILL.md" not in files or not isinstance(directories, list):
        raise AICError("The install ownership manifest requires package files and directories.")
    for name, digest in files.items():
        _relative(name)
        if name == _MANIFEST or not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise AICError("The install ownership manifest contains invalid file hashes or paths.")
    for name in directories:
        _relative(name)
        if name == _MANIFEST:
            raise AICError("The ownership manifest cannot be a package directory.")
    if directories != sorted(set(directories)) or set(files).intersection(directories):
        raise AICError("The ownership manifest contains duplicate or conflicting directories.")
    directory_set = set(directories)
    for name in [*files, *directories]:
        for parent in Path(name).parents:
            if parent != Path(".") and parent.as_posix() not in directory_set:
                raise AICError("The ownership manifest omits a parent directory.")
    return value


def _owned_fd(root: int) -> dict:
    try:
        value = json.loads(_read_file(root, _MANIFEST), object_pairs_hook=_json_object)
    except (UnicodeError, ValueError) as exc:
        raise AICError("The install ownership manifest is not valid JSON; no files were changed.") from exc
    manifest = _validate_manifest(value)
    if _inventory_fd(root) != manifest:
        raise AICError("The installed skill has modified, missing or unexpected files; preserving it unchanged.")
    return manifest


def _report(status: str, target: Path) -> dict:
    return {"status": status, "path": str(target)}


def _relative_directory(root: int, relative: Path) -> int:
    descriptor = os.dup(root)
    try:
        for name in relative.parts:
            child = _open_child(descriptor, name)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _temporary_directory(parent: int, prefix: str) -> tuple[str, int]:
    for _ in range(16):
        name = prefix + secrets.token_hex(16)
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
        except FileExistsError:
            continue
        return name, _open_child(parent, name)
    raise AICError("Could not reserve a private installer staging directory.")


def _delete_contents(root: int, manifest: dict | None = None, prefix: str = "") -> None:
    """Delete through opened directories, never through a pathname ancestor.

    Owned removals enumerate only manifest names, not newly introduced extras.
    Extra entries prevent final rmdir instead of being recursively removed.
    """
    names = set(os.listdir(root))
    if manifest is not None:
        expected = {
            Path(name).name for name in [*manifest["files"], *manifest["directories"]]
            if Path(name).parent.as_posix() == (prefix or ".")
        }
        if not prefix:
            expected.add(_MANIFEST)
        if names != expected:
            raise AICError("Unexpected entries appeared during removal; preserving remaining data.")
        names = expected
    for name in sorted(names):
        relative = f"{prefix}/{name}" if prefix else name
        info = os.stat(name, dir_fd=root, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            child = _open_child(root, name)
            try:
                if _identity(info) != _identity(os.fstat(child)):
                    raise AICError("A directory changed during removal.")
                _delete_contents(child, manifest, relative)
                _assert_identity(root, name, child)
                os.rmdir(name, dir_fd=root)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            if manifest is not None:
                content = _read_file(root, name)
                if relative == _MANIFEST:
                    intact = _validate_manifest(json.loads(content, object_pairs_hook=_json_object)) == manifest
                else:
                    intact = hashlib.sha256(content).hexdigest() == manifest["files"].get(relative)
                if not intact:
                    raise AICError("A managed file changed during removal; preserving remaining data.")
            current = os.stat(name, dir_fd=root, follow_symlinks=False)
            if not stat.S_ISREG(current.st_mode) or _identity(current) != _identity(info):
                raise AICError("A file was replaced during removal; preserving remaining data.")
            os.unlink(name, dir_fd=root)
        else:
            raise AICError("A symlink or special file appeared during removal; preserving remaining data.")


def _remove_directory(parent: int, name: str, descriptor: int, manifest: dict | None = None) -> None:
    _assert_identity(parent, name, descriptor)
    if manifest is not None and _owned_fd(descriptor) != manifest:
        raise AICError("The owned installation changed before removal.")
    _delete_contents(descriptor, manifest)
    _assert_identity(parent, name, descriptor)
    os.rmdir(name, dir_fd=parent)


def _stage(source: int, parent: int, manifest: dict) -> tuple[str, int]:
    name, stage = _temporary_directory(parent, ".aic-stage-")
    try:
        for relative in manifest["directories"]:
            path = Path(relative)
            directory = _relative_directory(stage, path.parent)
            try:
                os.mkdir(path.name, dir_fd=directory)
            finally:
                os.close(directory)
        for relative in manifest["files"]:
            path = Path(relative)
            original_parent = _relative_directory(source, path.parent)
            copied_parent = None
            try:
                copied_parent = _relative_directory(stage, path.parent)
                with os.fdopen(_file_descriptor(original_parent, path.name), "rb") as original:
                    descriptor = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=copied_parent)
                    with os.fdopen(descriptor, "wb") as copied:
                        shutil.copyfileobj(original, copied)
                        os.fchmod(copied.fileno(), stat.S_IMODE(os.fstat(original.fileno()).st_mode) & 0o777)
            finally:
                os.close(original_parent)
                if copied_parent is not None:
                    os.close(copied_parent)
        if _inventory_fd(stage) != manifest:
            raise AICError("The source changed during staging; preserving the previous installation.")
        descriptor = os.open(_MANIFEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=stage)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json(manifest))
        return name, stage
    except BaseException:
        try:
            _remove_directory(parent, name, stage)
        finally:
            os.close(stage)
        raise


def install(source: Path, target: Path) -> dict:
    """Stage and mutate only through no-follow, identity-checked directory FDs."""
    _require_safe_mutation()
    source_fd = parent_fd = target_fd = stage_fd = backup_fd = None
    stage_name = backup_name = None
    try:
        source = _directory(source, must_exist=True, absolute=True)
        target = _target(target)
        if target.is_relative_to(source) or source.is_relative_to(target):
            raise AICError("Source and destination directories must not overlap.")
        source_fd = _open_directory(source)
        manifest = _inventory_fd(source_fd, source=True)
        try:
            parent_fd = _open_directory(target.parent)
        except FileNotFoundError:
            parent_fd = _open_directory(target.parent, create=True)
        try:
            target_fd = _open_child(parent_fd, target.name)
        except FileNotFoundError:
            pass
        previous = _owned_fd(target_fd) if target_fd is not None else None
        if previous == manifest:
            _assert_visible_parent(target.parent, parent_fd)
            _assert_identity(parent_fd, target.name, target_fd)
            return _report("unchanged", target)
        stage_name, stage_fd = _stage(source_fd, parent_fd, manifest)
        _assert_visible_parent(target.parent, parent_fd)
        _assert_identity(parent_fd, stage_name, stage_fd)
        if previous is None:
            try:
                os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise AICError("The destination appeared during staging; preserving it unchanged.")
            os.rename(stage_name, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            stage_name = None
            return _report("installed", target)
        if _owned_fd(target_fd) != previous:
            raise AICError("The installed package changed during staging; preserving it unchanged.")
        _assert_identity(parent_fd, target.name, target_fd)
        backup_name, backup_fd = _temporary_directory(parent_fd, ".aic-backup-")
        os.rename(target.name, "aic", src_dir_fd=parent_fd, dst_dir_fd=backup_fd)
        _assert_identity(backup_fd, "aic", target_fd)
        try:
            os.rename(stage_name, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            stage_name = None
        except BaseException:
            # Roll back into the original opened parent, never a replaced ancestor.
            try:
                os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                _assert_identity(backup_fd, "aic", target_fd)
                os.rename("aic", target.name, src_dir_fd=backup_fd, dst_dir_fd=parent_fd)
            raise
        _remove_directory(backup_fd, "aic", target_fd, previous)
        return _report("upgraded", target)
    except OSError as exc:
        raise AICError(f"The skill could not be installed safely: {exc}") from exc
    finally:
        try:
            if stage_name is not None and stage_fd is not None:
                _remove_directory(parent_fd, stage_name, stage_fd)
            if backup_name is not None and backup_fd is not None and not os.listdir(backup_fd):
                _assert_identity(parent_fd, backup_name, backup_fd)
                os.rmdir(backup_name, dir_fd=parent_fd)
        finally:
            for descriptor in (backup_fd, stage_fd, target_fd, parent_fd, source_fd):
                if descriptor is not None:
                    os.close(descriptor)


def uninstall(target: Path) -> dict:
    """Validate and remove the same opened directory, without resolving ancestors again."""
    _require_safe_mutation()
    parent = owned = None
    try:
        target = _target(target)
        parent = _open_directory(target.parent)
        owned = _open_child(parent, target.name)
        manifest = _owned_fd(owned)
        _assert_visible_parent(target.parent, parent)
        _remove_directory(parent, target.name, owned, manifest)
        return _report("uninstalled", target)
    except OSError as exc:
        raise AICError(f"The skill could not be uninstalled safely: {exc}") from exc
    finally:
        for descriptor in (owned, parent):
            if descriptor is not None:
                os.close(descriptor)
