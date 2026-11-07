"""Permission and headless-result rules for the Orca template.

Interactive sessions block destructive commands. A headless session also
rejects commands and tools that are not on its allowlist. ``--bare`` and
permission bypasses are never emitted.
"""
from __future__ import annotations

from pathlib import Path
import re


DENY_COMMAND = re.compile(
    r'(\bgit\s+push\b|\bgit\s+clean\b|\bgit\s+reset\s+--hard\b|\bgit\s+branch\s+-[dD]\b'
    r'|\brm\s+-[^\s]*[rR][^\s]*|\brm\s+--recursive\b|\bsudo\b|\bcurl\b|\bwget\b|\bssh\b'
    r'|\bchmod\s+777\b|\blaunchctl\b|\bgh\s+auth\s+token\b|\beval\b|\bmkfs\b'
    r'|--dangerously-skip-permissions|\s--bare\b|\s-delete\b|\.env\b)',
    re.IGNORECASE,
)
ALLOW_PREFIXES = (
    'git status', 'git diff', 'git log', 'git show', 'git rev-parse', 'git worktree list',
    'git merge-base', 'git merge-tree', 'git add', 'git commit', 'git checkout', 'git switch',
    'git branch', 'pytest', 'python', 'python3', 'node', 'npm test', 'npm run lint',
    'npm run typecheck', 'npm run test', 'pnpm test', 'pnpm run lint', 'pnpm run typecheck',
    'pnpm run test', 'yarn test', 'yarn lint', './scripts/verify.sh', './gate.sh',
    './.orca/gate.sh', './scripts/orca-gate.sh', 'mkdir', 'ls', 'cat', 'rg', 'sed',
)
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


def _allowed_segment(segment: str) -> bool:
    return any(segment == prefix or segment.startswith(prefix + ' ') or segment.startswith(prefix + '\t') for prefix in ALLOW_PREFIXES)


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


def decide_tool(tool_name: str, tool_input: object, *, headless: bool, active_stream: str | None,
                active_worktree: str | None, resolved_toplevel: str | None, plan: dict | None) -> tuple[int, str]:
    """Return ``(0, reason)`` to allow or ``(2, reason)`` to block."""
    if not isinstance(tool_name, str) or not tool_name:
        return 2, 'missing tool name.'
    payload = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == 'Bash':
        command = payload.get('command')
        if not isinstance(command, str) or not command.strip():
            return 2, 'bash command is missing.'
        if DENY_COMMAND.search(command):
            return 2, 'command is denied.'
        if active_worktree and any(marker in command for marker in TEST_MARKERS):
            if not resolved_toplevel or Path(resolved_toplevel).resolve() != Path(active_worktree).resolve():
                return 2, 'test command is not running in the active worktree.'
        if headless and not all(_allowed_segment(segment) for segment in _segments(command)):
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
