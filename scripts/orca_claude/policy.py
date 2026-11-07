"""Permission and headless-result rules for the Orca template.

Interactive sessions block destructive commands. A headless session also
rejects commands and tools that are not on its allowlist. ``--bare`` and
permission bypasses are never emitted.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex


DENY_COMMAND = re.compile(
    r'(\bgit\s+push\b|\bgit\s+clean\b|\bgit\s+reset\s+--hard\b|\bgit\s+branch\s+-[dD]\b'
    r'|\brm\s+-[^\s]*[rR][^\s]*|\brm\s+--recursive\b|\bsudo\b|\bcurl\b|\bwget\b|\bssh\b'
    r'|\bchmod\s+777\b|\blaunchctl\b|\bgh\s+auth\s+token\b|\beval\b|\bmkfs\b'
    r'|--dangerously-skip-permissions|\s--bare\b|\s-delete\b|\.env\b)',
    re.IGNORECASE,
)
EXACT_HEADLESS = {
    './scripts/verify.sh',
    './gate.sh',
    './.orca/gate.sh',
    './scripts/orca-gate.sh',
}
GIT_FLAGS = {
    'status': {'-sb', '--short', '--porcelain', '--branch', '-b'},
    'diff': {'--stat', '--name-only', '--name-status', '--cached', '--staged', '--exit-code'},
    'log': {'--oneline', '--stat', '--decorate', '--max-count', '-n'},
    'show': {'--stat', '--name-only', '--name-status', '--no-patch', '--oneline'},
    'rev-parse': {'--abbrev-ref', '--show-toplevel', '--is-inside-work-tree', '--git-common-dir'},
    'merge-base': set(),
    'merge-tree': set(),
    'add': {'-u', '--update', '-A', '--all'},
    'commit': {'-m', '--message'},
}
INTERPRETERS = {
    'python', 'python3', 'node', 'deno', 'bun', 'perl', 'ruby', 'pytest', 'py.test',
}
WRAPPERS = {'command', 'env', 'exec', 'xargs', 'nice', 'nohup', 'builtin'}
TEST_MARKERS = (
    'pytest', 'npm test', 'pnpm test', 'yarn test', 'go test', 'cargo test',
    './scripts/verify.sh', './gate.sh', './.orca/gate.sh', 'unittest',
)
KNOWN_TOOLS = {
    'Read', 'Grep', 'Glob', 'LS', 'Bash', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit',
    'WebFetch', 'WebSearch', 'TodoWrite', 'Skill', 'ToolSearch',
}
WRITE_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}
FORBIDDEN_ARGV = {'--bare', '--dangerously-skip-permissions'}
SENSITIVE = re.compile(r'(^|[\\/._-])(secret|credential|credentials)([\\/._-]|$)', re.IGNORECASE)


class PolicyError(ValueError):
    """An argv or result contract was rejected before a process starts."""


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', text or '')
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def version_at_least(found: tuple[int, int, int] | None, required: tuple[int, int, int]) -> bool:
    return found is not None and found >= required


def _segments(command: str) -> list[str]:
    return [part.strip() for part in re.split(r'(?:&&|\|\||;|\n|\|)', command) if part.strip()]


def _program(token: str) -> str:
    return Path(token).name


def path_is_sensitive(value: str) -> bool:
    text = value.replace('\\', '/')
    name = Path(text).name
    lowered = text.lower()
    if name == '.env' or name.startswith('.env.') or name.endswith('.pem'):
        return True
    if name in {'id_rsa', 'id_ed25519', 'id_ecdsa'}:
        return True
    if '/.ssh/' in f'/{lowered}' or lowered.startswith('.ssh/'):
        return True
    return bool(SENSITIVE.search(name))


def _norm(path: str) -> str:
    text = path.replace('\\', '/')
    if text.startswith('./'):
        text = text[2:]
    return text.rstrip('/')


def path_owned(owned: list[str], target: str) -> bool:
    text = _norm(target)
    if not text or text.startswith('/') or '..' in text.split('/'):
        return False
    for item in owned:
        root = _norm(item)
        if text == root or text.startswith(root + '/'):
            return True
    return False


def _tool_paths(tool_input: dict) -> list[str]:
    found = []
    for key in ('file_path', 'path', 'notebook_path'):
        value = tool_input.get(key)
        if isinstance(value, str):
            found.append(value)
    return found


def _tokens(segment: str) -> list[str] | None:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return None


def _git_push_or_branch_delete(tokens: list[str]) -> bool:
    if not tokens or Path(tokens[0]).name != 'git':
        return False
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--super-prefix', '--config-env', '--exec-path'}:
            index += 2
            continue
        if token.startswith(('--git-dir=', '--work-tree=', '--namespace=', '--super-prefix=', '--config-env=', '--exec-path=')):
            index += 1
            continue
        if token.startswith('-c') and token != '-c':
            index += 1
            continue
        if token.startswith('-') and token not in {'-C', '-c'}:
            index += 1
            continue
        if token == 'push':
            return True
        if token == 'branch':
            return any(item in {'-d', '-D', '--delete'} for item in tokens[index + 1:])
        return False
    return False


def _unwrap_wrappers(tokens: list[str]) -> list[str]:
    current = list(tokens)
    for _ in range(6):
        if not current:
            return current
        name = _program(current[0])
        if name not in WRAPPERS:
            return current
        index = 1
        if name == 'env':
            while index < len(current):
                token = current[index]
                if token == '--':
                    index += 1
                    break
                if token.startswith('-'):
                    index += 2 if token in {'-u', '-C', '-S'} else 1
                    continue
                if '=' in token:
                    index += 1
                    continue
                break
        elif name == 'xargs':
            while index < len(current) and current[index].startswith('-'):
                index += 2 if current[index] in {'-I', '-a', '-n', '-P', '-L', '-s', '-E', '-J'} else 1
        else:
            while index < len(current) and current[index].startswith('-'):
                index += 1
        current = current[index:]
    return current


def _shell_c(tokens: list[str]) -> str | None:
    if not tokens or Path(tokens[0]).name not in {'bash', 'sh', 'dash', 'zsh'}:
        return None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == '-c' or (token.startswith('-') and not token.startswith('--') and 'c' in token[1:]):
            if index + 1 < len(tokens):
                return tokens[index + 1]
            return None
        index += 1
    return None


def _git_parts(tokens: list[str]) -> tuple[str, list[str]] | None:
    if not tokens or _program(tokens[0]) != 'git':
        return None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--super-prefix', '--config-env', '--exec-path'}:
            index += 2
            continue
        if token.startswith(('--git-dir=', '--work-tree=', '--namespace=', '--super-prefix=', '--config-env=', '--exec-path=')):
            index += 1
            continue
        if token.startswith('-c') and token != '-c':
            index += 1
            continue
        if token.startswith('-') and token not in {'-C', '-c'}:
            index += 1
            continue
        return token, tokens[index + 1:]
    return None


def _path_is_outside_or_sensitive(raw: str, worktree: Path | None, cwd: Path | None) -> bool:
    text = raw[2:] if raw.startswith('./') else raw
    if path_is_sensitive(text) or path_is_sensitive(raw):
        return True
    if raw.startswith('~') or text.startswith('~'):
        return True
    if ':' in raw and '://' not in raw:
        _revision, path = raw.split(':', 1)
        if not path:
            return True
        return _path_is_outside_or_sensitive(path, worktree, cwd)
    if worktree is None:
        return raw.startswith('/') or raw.startswith('~') or text.startswith('..')
    base = cwd if cwd is not None else worktree
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(worktree.resolve())
    except (OSError, ValueError):
        return True
    return path_is_sensitive(str(resolved))


def _looks_like_path(token: str) -> bool:
    return token.startswith(('/', '~', '.')) or '/' in token or (':' in token and '://' not in token)


def _contains_denied_expansion(text: str, depth: int = 0) -> bool:
    """Deny command substitution, backticks, here-strings, and process substitution.

    The inner text is scanned again so a nested ``$(...)`` is not missed when the
    outer command would otherwise be an allowed git read.
    """
    if depth > 6 or '<<<' in text or '>(' in text:
        return True
    for opener, closer in (('$(', ')'), ('<(', ')'), ('`', '`')):
        start = 0
        while True:
            found = text.find(opener, start)
            if found == -1:
                break
            begin = found + len(opener)
            end = text.find(closer, begin)
            inner = text[begin:end] if end != -1 else text[begin:]
            if _contains_denied_expansion(inner, depth + 1) or inner.strip() or end != -1:
                return True
            start = begin
    return False


def _git_config_injection(tokens: list[str]) -> bool:
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == '-c' or (token.startswith('-c') and not token.startswith('-C')):
            return True
        if token == '--config-env' or token.startswith('--config-env='):
            return True
        if token in {'-C', '--git-dir', '--work-tree', '--namespace', '--super-prefix', '--exec-path'}:
            index += 2
            continue
        if token.startswith(('--git-dir=', '--work-tree=', '--namespace=', '--super-prefix=', '--exec-path=')):
            index += 1
            continue
        if token.startswith('-'):
            index += 1
            continue
        return False
    return False


def _plan_owns_script(plan: dict | None, script: str) -> bool:
    if not isinstance(plan, dict) or plan.get('status') != 'accepted':
        return False
    relative = script[2:] if script.startswith('./') else script
    parent = Path(relative).parent.as_posix()
    targets = [relative]
    targets.append('.' if parent in {'', '.'} else parent)
    for stream in plan.get('streams') or []:
        if not isinstance(stream, dict):
            continue
        owned = [item for item in stream.get('paths') or [] if isinstance(item, str)]
        for item in owned:
            if _norm(item) in {'', '.'}:
                return True
        if any(path_owned(owned, target) for target in targets):
            return True
    return False


def _safe_git(tokens: list[str], worktree: Path | None, cwd: Path | None) -> bool:
    if '--no-index' in tokens or _git_config_injection(tokens):
        return False
    parts = _git_parts(tokens)
    if parts is None:
        return False
    subcommand, rest = parts
    if subcommand == 'worktree':
        return rest in (['list'], ['list', '--porcelain'])
    flags = GIT_FLAGS.get(subcommand)
    if flags is None:
        return False
    index = 0
    while index < len(rest):
        token = rest[index]
        if token == '--':
            return all(not _path_is_outside_or_sensitive(path, worktree, cwd) for path in rest[index + 1:])
        if token.startswith('-'):
            if token not in flags and not (subcommand == 'log' and token.startswith('-n') and token[2:].isdigit()):
                return False
            if token in {'-n', '--max-count', '-m', '--message'}:
                if index + 1 >= len(rest):
                    return False
                index += 2
                continue
            index += 1
            continue
        if subcommand == 'add' or _looks_like_path(token) or (':' in token and '://' not in token):
            if _path_is_outside_or_sensitive(token, worktree, cwd):
                return False
        index += 1
    return True


def _headless_segment_allowed(segment: str, worktree: Path | None, cwd: Path | None,
                              plan: dict | None) -> bool:
    tokens = _tokens(segment)
    if not tokens:
        return False
    unwrapped = _unwrap_wrappers(tokens)
    if not unwrapped:
        return False
    if len(unwrapped) == 1 and unwrapped[0] in EXACT_HEADLESS:
        return not _plan_owns_script(plan, unwrapped[0])
    names = {_program(unwrapped[0]), _program(tokens[0])}
    if names & INTERPRETERS or 'sed' in names:
        return False
    if _program(unwrapped[0]) == 'git':
        if _contains_denied_expansion(segment) or any(_contains_denied_expansion(token) for token in unwrapped):
            return False
        return _safe_git(unwrapped, worktree, cwd)
    return False


def command_is_blocked(command: str, *, headless: bool, depth: int = 0) -> bool:
    if depth > 5:
        return True
    if DENY_COMMAND.search(command):
        return True
    for segment in _segments(command):
        tokens = _tokens(segment)
        if tokens is None:
            return True
        unwrapped = _unwrap_wrappers(tokens)
        if _git_push_or_branch_delete(tokens) or _git_push_or_branch_delete(unwrapped):
            return True
        inner = _shell_c(tokens)
        if inner and command_is_blocked(inner, headless=headless, depth=depth + 1):
            return True
    return False


def decide_tool(tool_name: str, tool_input: object, *, headless: bool, active_stream: str | None,
                active_worktree: str | None, resolved_toplevel: str | None, plan: dict | None,
                cwd: str | None = None) -> tuple[int, str]:
    """Return ``(0, reason)`` to allow or ``(2, reason)`` to block."""
    if not isinstance(tool_name, str) or not tool_name:
        return 2, 'missing tool name.'
    payload = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == 'Bash':
        command = payload.get('command')
        if not isinstance(command, str) or not command.strip():
            return 2, 'bash command is missing.'
        if command_is_blocked(command, headless=headless):
            return 2, 'command is denied.'
        if active_worktree and any(marker in command for marker in TEST_MARKERS):
            if not resolved_toplevel or Path(resolved_toplevel).resolve() != Path(active_worktree).resolve():
                return 2, 'test command is not running in the active worktree.'
        if headless:
            root = Path(resolved_toplevel) if resolved_toplevel else (Path(active_worktree) if active_worktree else None)
            base = Path(cwd) if cwd else root
            if not all(_headless_segment_allowed(segment, root, base, plan) for segment in _segments(command)):
                return 2, 'command is not on the headless allowlist.'
        return 0, 'bash allowed.'
    paths = _tool_paths(payload)
    if any(path_is_sensitive(item) for item in paths):
        return 2, 'refusing a sensitive path.'
    if tool_name in WRITE_TOOLS:
        if headless and (not isinstance(plan, dict) or plan.get('status') != 'accepted'):
            return 2, 'headless writes require an accepted plan.'
        if isinstance(plan, dict) and plan.get('status') == 'accepted':
            streams = [item for item in plan.get('streams', []) if isinstance(item, dict)]
            if active_stream:
                streams = [item for item in streams if item.get('slug') == active_stream]
            owned: list[str] = []
            for stream in streams:
                owned.extend(item for item in stream.get('paths', []) if isinstance(item, str))
            if not paths or not all(path_owned(owned, item) for item in paths):
                return 2, 'write is outside the accepted stream ownership.'
        return 0, 'write allowed.'
    if tool_name in KNOWN_TOOLS or tool_name.startswith('mcp__'):
        return 0, 'tool allowed.'
    if headless:
        return 2, f'unrecognized tool {tool_name}.'
    return 0, 'interactive tool allowed.'


def build_claude_argv(*, executable: str, prompt: str, max_turns: int, settings: str, schema: str,
                      version: tuple[int, int, int] | None) -> list[str]:
    if not isinstance(executable, str) or not executable or executable.startswith('-') or '\x00' in executable:
        raise PolicyError('claude executable is missing or unsafe.')
    if not isinstance(prompt, str) or not prompt or '\x00' in prompt:
        raise PolicyError('prompt must be nonempty text.')
    if isinstance(max_turns, bool) or not isinstance(max_turns, int) or not 1 <= max_turns <= 60:
        raise PolicyError('max turns must be from 1 through 60.')
    argv = [
        executable, '-p', prompt,
        '--output-format', 'json',
        '--json-schema', schema,
        '--max-turns', str(max_turns),
        '--permission-mode', 'dontAsk',
        '--settings', settings,
    ]
    if version_at_least(version, (2, 1, 259)):
        argv.extend(['--permission-prompts', 'none'])
    if any(item in FORBIDDEN_ARGV or item.startswith('--dangerously') for item in argv):
        raise PolicyError('refusing a bare or permission-bypass invocation.')
    return argv


RESULT_SCHEMA = (
    '{"type":"object","additionalProperties":false,"required":["status","streams","evidence",'
    '"push_performed","delete_performed"],"properties":{"status":{"enum":["passed","partial",'
    '"blocked","failed"]},"streams":{"type":"array"},"evidence":{"type":"array"},'
    '"push_performed":{"const":false},"delete_performed":{"const":false}}}'
)


def interpret_claude_result(payload: object, stderr: str = '', *, required_mcp: tuple[str, ...] = ()) -> list[str]:
    """Return human-readable failures. An empty list means the result is acceptable."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ['Claude result is not a JSON object.']
    subtype = str(payload.get('subtype') or '')
    if payload.get('is_error') is True or subtype.startswith('error') or payload.get('type') not in {None, 'result'}:
        errors.append('Claude reported an error result.')
    structured = payload.get('structured_output')
    if not isinstance(structured, dict):
        errors.append('structured_output is missing.')
    else:
        if structured.get('push_performed') is not False or structured.get('delete_performed') is not False:
            errors.append('structured output did not keep push and delete off.')
        if structured.get('status') != 'passed':
            errors.append('structured status is not passed.')
        if not isinstance(structured.get('evidence'), list) or not isinstance(structured.get('streams'), list):
            errors.append('structured output is missing streams or evidence.')
    denials = payload.get('permission_denials', [])
    if denials not in ([], None):
        errors.append('permission_denials is not empty.')
    lowered = (stderr or '').lower()
    if 'failed to load plugin' in lowered or 'error loading plugin' in lowered or 'plugin load error' in lowered:
        errors.append('plugin load error.')
    servers = payload.get('mcp_servers', payload.get('mcpServers', []))
    if isinstance(servers, dict):
        servers = [{'name': name, **(value if isinstance(value, dict) else {'status': value})} for name, value in servers.items()]
    if not isinstance(servers, list):
        errors.append('mcp server list is invalid.')
        servers = []
    optional = {'perplexity', 'context7'}
    required = set(required_mcp)
    for server in servers:
        if not isinstance(server, dict) or not isinstance(server.get('name', ''), str):
            errors.append('invalid mcp entry.')
            continue
        name = server.get('name', '')
        status = str(server.get('status', '')).lower()
        if name in optional and server.get('required') is not True and name not in required:
            continue
        if server.get('required') is True or name in required:
            if status not in {'connected', 'ok', 'ready'}:
                errors.append(f'required mcp server {name or "(unnamed)"} is not ready.')
            if not name:
                errors.append('invalid required mcp entry.')
    return errors


def recorded_effects() -> dict[str, bool]:
    """Whether the headless hook would allow a push or a branch delete."""
    options = dict(headless=True, active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
    push, _message = decide_tool('Bash', {'command': 'git push origin main'}, **options)
    delete, _message = decide_tool('Bash', {'command': 'git branch -D feature'}, **options)
    return {'push': push == 0, 'delete': delete == 0}
