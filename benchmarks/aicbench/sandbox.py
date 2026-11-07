"""Bubblewrap command line for an aicbench agent.

The repository is not mounted. Callers that need a published result still have
to run this sandbox; building the command does not start an agent.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from .grading import GradeError


def sandbox_runtime() -> str:
    """Return the bubblewrap executable, or raise when it is not installed."""
    found = shutil.which("bwrap")
    if not found:
        raise GradeError(
            "Container sandbox requires bubblewrap (bwrap) on PATH. "
            "Without it, aicbench cannot hide the checkout from the agent filesystem."
        )
    return found


def _outside_repo(path: Path, repo: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise GradeError(f"Cannot resolve sandbox path: {path}") from exc
    return resolved != repo and repo not in resolved.parents


def container_command(
    inner: list[str],
    *,
    workspace: Path,
    skill_root: Path | None,
    home: Path,
    config: Path,
    binary: Path,
    repo: Path,
) -> list[str]:
    """Bubblewrap argv that mounts the workspace and skill, not the repository."""
    repo_resolved = repo.resolve()
    for label, path in (("binary", binary), ("workspace", workspace), ("home", home), ("config", config)):
        if not _outside_repo(path, repo_resolved):
            raise GradeError(f"Refusing to mount a repository path into the sandbox ({label}).")
    if skill_root is not None and not _outside_repo(skill_root, repo_resolved):
        raise GradeError("Refusing to mount a repository path into the sandbox (skill).")
    command = [
        "bwrap",
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
    ]
    for directory in ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc/ssl", "/etc/pki", "/etc/ca-certificates"):
        candidate = Path(directory)
        if candidate.is_dir() and _outside_repo(candidate, repo_resolved):
            command.extend(["--ro-bind", directory, directory])
    resolv = Path("/etc/resolv.conf")
    if resolv.is_file() and _outside_repo(resolv, repo_resolved):
        command.extend(["--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf"])
    command.extend(["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"])
    for path in (workspace, home, config):
        text = str(path.resolve())
        command.extend(["--bind", text, text])
    if skill_root is not None:
        text = str(skill_root.resolve())
        command.extend(["--ro-bind", text, text])
    binary_text = str(binary.resolve())
    system_prefixes = ("/usr/", "/lib/", "/lib64/", "/bin/", "/sbin/")
    if not binary_text.startswith(system_prefixes):
        command.extend(["--ro-bind", binary_text, binary_text])
    command.extend(["--chdir", str(workspace.resolve()), "--"])
    command.extend(inner)
    if str(repo_resolved) in command:
        raise GradeError("Sandbox command included the repository path.")
    return command
