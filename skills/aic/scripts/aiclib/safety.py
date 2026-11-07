"""Local path and serialization boundaries; these do not authenticate consent."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# Every scoped relative path (routing, memory, inspection) shares these bounds,
# which also cap the per-component symlink walk. 64 components leaves room for
# inspection's deepest level (max_depth 32 -> 33 parts); routing keeps its own 32.
MAX_PATH_BYTES = 1024
MAX_PATH_COMPONENTS = 64


class AICError(ValueError):
    """An actionable, user-facing contract violation."""


def is_sensitive(value: str | Path) -> bool:
    parts = str(value).replace("\\", "/").lower().split("/")
    excluded = {
        ".git", ".ssh", ".aws", ".azure", ".config", ".gnupg", ".kube",
        "node_modules", ".venv", "venv", "site-packages", "__pycache__",
        "dist", "build", ".next", "secrets", "credentials", "tokens",
        "credentials.json", "credentials.toml", "credentials.yaml",
        "secrets.json", "secrets.yaml", "secrets.toml", "token.json",
        "id_rsa", "id_ed25519", "id_ecdsa", ".netrc", ".npmrc", ".pypirc",
    }
    return any(
        part in excluded or part.startswith(".env") or part.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
        for part in parts
    )


def _no_symlinks(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise AICError(f"Symlink paths are not allowed: {current}")


def checked_root(value: str | Path, *, must_exist: bool = True) -> Path:
    try:
        raw = os.fspath(value)
        if not raw or "\x00" in raw:
            raise AICError("A nonempty project or destination path is required.")
        path = Path(os.path.abspath(raw))
        _no_symlinks(path)
        if path.exists() and not path.is_dir():
            raise AICError(f"Expected a directory: {path}")
        if must_exist and not path.is_dir():
            raise AICError(f"Directory does not exist: {path}")
        return path
    except (OSError, TypeError) as exc:
        raise AICError("The directory path cannot be inspected safely.") from exc


def relative_path(value: str, *, allow_dot: bool = False) -> Path:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value or "\\" in value:
        raise AICError("Expected a nonempty relative path without traversal or backslashes.")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise AICError("Scoped paths must be valid UTF-8.") from exc
    if len(encoded) > MAX_PATH_BYTES:
        raise AICError(f"Scoped paths must not exceed {MAX_PATH_BYTES} UTF-8 bytes.")
    raw_parts = value.split("/")
    if len(raw_parts) > MAX_PATH_COMPONENTS:
        raise AICError(f"Scoped paths must not exceed {MAX_PATH_COMPONENTS} components.")
    path = Path(value)
    if path.is_absolute() or ".." in raw_parts or ":" in value:
        raise AICError("Absolute paths and traversal are not allowed in a scoped path.")
    if path == Path(".") and not allow_dot:
        raise AICError("A specific relative path is required.")
    if is_sensitive(path):
        raise AICError("Sensitive or excluded paths cannot be selected as codebase evidence or scope.")
    return path


def safe_path(root: Path, value: str, *, must_exist: bool = False, allow_dot: bool = False) -> Path:
    base = checked_root(root)
    rel = relative_path(value, allow_dot=allow_dot)
    path = base / rel
    _no_symlinks(path)
    if not path.is_relative_to(base):
        raise AICError("The selected path escapes the project.")
    if must_exist and not path.exists():
        raise AICError(f"Evidence path does not exist: {rel}")
    return path


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AICError("The value must be finite JSON data.") from exc
