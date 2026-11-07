# Security audit — 2026-11-07

Audit of `main` at `a580af9112c3770b046424c82ad15914f909ee4b` (the 0.0.3 security merge). The question was whether the optional MCP adapter is read-only, including path traversal and symlink escape; whether the scripts interpolate a shell or use unsafe temporary files; whether the Claude Code plugin ships hooks or a permissive manifest; and whether the declared dependencies have known advisories.

This pass did not change `safety.py`, `inspection.py`, the scripts, or the plugin manifests. The one code change is in the MCP packaged-file reader, described under the finding it closes. No Critical, High, or Medium defect was reproduced.

## How this was checked

- Read the MCP server (`skills/aic/scripts/aiclib/mcp_server.py`), the path helpers it calls, the official MCP Python SDK 2.3.0 that `build_server` loads, the scripts under `scripts/`, the skill helpers those scripts import, `.claude-plugin/`, and `.github/workflows/security.yml`.
- Ran an in-process official MCP client (SDK 2.3.0, Python 3.12.3) against `build_server` on a temporary project containing a private README body, a `.env` marker, an outside file, a directory symlink, a file symlink, a hard link to the outside file, a FIFO, `id_rsa`, `id_rsa.pub`, `password.txt`, and a filename containing a newline.
- Searched the repository for `shell=True`, `os.system`, `eval(`, `exec(`, `mktemp`, `NamedTemporaryFile`, and `tempfile` usage in production code.
- Ran `pip-audit` 2.10.1 the way `.github/workflows/security.yml` does: a requirements file of `hatchling==1.29.0` and `mcp==2.3.0`, `--strict`, binary-only installs, Python 3.12.3. Also queried OSV directly for `mcp` 2.3.0, `hatchling` 1.29.0, and `packaging` 26.3.

Temporary projects lived under `/tmp`. The real skill tree was not replaced during the probes.

## Findings

### Low — Packaged MCP reads followed a symlink swapped in after the path check

`_portable_text` allowed the path with `safe_path`, then called `Path.read_text`. `read_text` follows a symlink. `safe_path` rejects a symlink that is already there, so a symlink planted before the call was refused. Replacing the file with a symlink after `safe_path` returned made the read return the target's bytes.

Reproduction on the audited revision, using a temporary skill root and a synthetic marker `SYMLINK_WINDOW_SECRET`:

1. Point the packaged root at a temporary directory whose `SKILL.md` is a regular file.
2. Wrap `safe_path` so that, after the real check returns, it unlinks `SKILL.md` and replaces it with a symlink to the marker file.
3. Call `_portable_text("SKILL.md")`.

Observed result before the change: the function returned `SYMLINK_WINDOW_SECRET`. A two-second race (4 reader threads, 2 swapper threads) did not win that window: 4064 reads returned the regular-file text, 10710 calls were rejected, and 0 reads returned the marker. The defect is the non-atomic check-then-follow, not a race that was won on this machine.

Practical reach is limited. The swapped path is an allowlisted file under the installed skill directory, not a path inside the bound project. The process can return a target only when it can read that target and something can replace the skill file between the check and the open. `SECURITY.md` already says concurrent filesystem replacement is not contained by path checks alone. A same-user writer who can replace the skill file can also write the bytes they want read. The extra reach is a symlink to a file the server uid can read.

**Remediation in this change.** The allowlisted read now opens the skill root and each relative component with `O_NOFOLLOW` / `O_DIRECTORY`, requires a regular file, and stops at 1 MiB (the largest allowlisted file on this revision is `references/research.md`, 33891 bytes). The same post-check swap now raises `AICError` with the message `The packaged resource cannot be read safely.` and does not return the marker. Regression coverage is in `tests/test_mcp.py`: a pre-existing resource symlink, the post-check swap through `aic_get_guidance`, and a normal guidance read that still returns packaged text. A hard link planted in place of an allowlisted name is still a regular file and is still read; closing that would require a content manifest, which this change does not add. Replacing a directory with another real directory (not a symlink) between the check and the open is still outside this fix.

### Low — Metadata inventory reports names the sensitive-path list does not cover

`aic_inspect_project` did not return file bodies, did not follow the directory or file symlinks, did not list `id_rsa` or `.env`, and did not list the FIFO. It did list these names and sizes from the temporary project:

- `password.txt`
- `id_rsa.pub`
- `notes.txt`, a hard link to a file outside the project whose body was the marker `SECRET_BODY_SHOULD_NOT_LEAK_9f3a` (the marker was not in the tool result)
- `weird\nname.txt` (the newline was preserved in the returned path)

`is_sensitive` in `safety.py` is an explicit denylist, and `inspection.py` also skips hidden names. `SECURITY.md` says this is not complete secret detection. The newline is ordinary filename metadata; a host that treats tool JSON as instructions can still be nudged by it. No change was made here. The denylist and the inventory live outside the MCP module.

### Low — Verification scratch directory follows the process umask

`scripts/verify.py` creates `<checkout>/.work` with `Path.mkdir` and no explicit mode. On this machine the process umask was `0o022`, and a new directory created the same way was mode `0o755`. Child test directories use `tempfile.TemporaryDirectory`, which is mode `0o700`, so other users who can traverse `.work` still cannot list those children. The directory name is inside the checkout, not `/tmp`. Not changed in this pass.

The installer does not use that pattern. Staging directories are `mode=0o700`, named with `secrets.token_hex(16)`, and created with `mkdir` on a directory file descriptor. Maintainer plist writes use `O_CREAT | O_EXCL | O_NOFOLLOW` and mode `0o600`.

### Low — `pip-audit` skips `packaging` when the audit environment already has it

The workflow installs the two direct pins and lets `pip-audit` 2.10.1 resolve them with `pip install --dry-run --report`. That report lists packages the empty environment would install. After `pip-audit` upgrades `pip`, `wheel`, and `setuptools`, `packaging` is already installed. Hatchling 1.29.0 depends on it, and the dry-run report then omits it.

Observed audited set (32 distributions), `pip-audit` 2.10.1, `--strict`, no ignores, result `No known vulnerabilities found`:

| Distribution | Version |
| --- | --- |
| hatchling | 1.29.0 |
| mcp | 2.3.0 |
| mcp-types | 2.3.0 |
| anyio | 4.16.0 |
| httpx2 | 2.16.0 |
| httpcore2 | 2.16.0 |
| h11 | 0.16.0 |
| idna | 3.20 |
| jsonschema | 4.26.0 |
| attrs | 26.1.0 |
| jsonschema-specifications | 2025.9.1 |
| opentelemetry-api | 1.45.2 |
| pathspec | 1.1.1 |
| pluggy | 1.7.0 |
| pydantic | 2.14.3 |
| pydantic_core | 2.50.4 |
| annotated-types | 0.8.0 |
| PyJWT | 2.15.1 |
| cryptography | 50.0.2 |
| cffi | 2.1.1 |
| python-multipart | 0.0.33 |
| referencing | 0.37.0 |
| rpds-py | 2026.9.1 |
| sse-starlette | 3.7.0 |
| starlette | 1.10.0 |
| truststore | 0.10.5 |
| typing_extensions | 4.16.0 |
| typing-inspection | 0.4.5 |
| uvicorn | 0.54.0 |
| click | 8.5.1 |
| pycparser | 3.12 |
| trove-classifiers | 2026.9.21.13 |

The simulated audit environment already contained `packaging==26.3`. OSV returned no vulnerabilities for `packaging` 26.3, `mcp` 2.3.0, or `hatchling` 1.29.0 at query time. The gap is coverage of a build dependency that happens to be preinstalled, not a current advisory. Runtime dependencies of the published package remain empty; `mcp` is optional.

## Informational

- **No shell injection sink was found.** Production Python does not call `shell=True`, `os.system`, or `eval`. `subprocess.run` / `Popen` sites pass argument lists. `scripts/verify.sh` quotes `"$PY"` and the script path. The supervision guide's `mktemp -d /tmp/aic-tmux.XXXXXX` example is documentation, uses the safe `mktemp -d` form, and quotes the expansions it shows. It is not a script the plugin runs.
- **PATH lookup remains for approved local CLIs.** `orca-apply` executes the operator-supplied binary (default `orca`) as `argv[0]` with `shell` left false, after rejecting an empty name, a NUL, and a leading `-`. `git` in the handoff plan is the same kind of argv. A directory earlier on `PATH` can still supply that executable. That is the process environment, not a shell metacharacter bug.
- **CLI errors can include local paths.** `safety.AICError` messages name the path that failed, and `cli.py` prints them to stderr. The MCP tools replace those messages with a fixed rejection string. The probe's symlink and traversal failures did not echo the outside directory, the secret body, or `Traceback`.
- **Failed resource lookups are logged with the client-supplied URI.** SDK 2.3.0 logs `Resource ... failed` at INFO. A probe that requested `file:///tmp/.../approved/.env` saw that URI on stderr. The server did not read the file. The URI is the one the client sent.
- **Plugin manifest does not grant hooks or an MCP server.** `.claude-plugin/plugin.json` is name, display name, version `0.0.3`, description, author, homepage, repository, and Apache-2.0. `.claude-plugin/marketplace.json` points the single plugin at `./`. There is no `hooks` entry, no `hooks/hooks.json`, no `.mcp.json`, and no plugin `settings.json`. `SKILL.md` does not declare an `allowed-tools` list. Installing the marketplace still means the plugin root is the repository root, so maintainer modules are present in that tree; nothing in the manifest starts them.
- **MCP capability advertisement matched the tool list.** The probed server exposed exactly `aic_get_workflow_catalog`, `aic_get_guidance`, `aic_inspect_project`, and `aic_validate_recommendation`, each with `read_only_hint=True`, `destructive_hint=False`, `idempotent_hint=True`, and `open_world_hint=False`. Twelve concrete `aic://skill/...` resources were listed, with no resource templates and no prompts. Negotiated capabilities had `resources.subscribe=False`, `logging=None`, and no completions, extensions, or tasks. `main` calls `server.run(transport="stdio")` only. Unknown tool names (`execute`, `aic_write_file`, `aic_launch_agents`) returned errors. The temporary project's file list was unchanged after the session.

## Controls that held under the probe

| Check | Result |
| --- | --- |
| Symlink as `--project` / `build_server` root | Rejected (`AICError`) |
| Relative root, missing root, file root | Rejected |
| Resource URIs for the project `.env`, `aic://skill/references/../../.env`, percent-encoded `..`, `file:///etc/passwd` | `MCPError`; marker text not in the error |
| Guidance section `../.env`, a filesystem path, `file:///etc/passwd` | Tool error; marker text absent |
| Directory symlink and file symlink inside the project | Not walked and not read |
| Evidence paths `../other/...`, `linked-dir/...`, `linked-file`, `.env` | Rejected; outside path and secret body absent |
| Extra tool argument whose value was the secret marker | Rejected; marker absent (`hide_input_in_errors`) |
| `max_files` set to that same marker | Rejected; marker absent |
| Serialized plan string | Rejected (coercion stays disabled) |
| Valid recommendation | `approval_required` stayed true and `next_action` stayed `recommend`; README body was not added |
| Project tree after the session | Same relative paths as before |

`read_only_hint` is still an annotation. The behavior above is what the four tools and the allowlisted resources did in this process. It is not an OS sandbox. A bind mount inside the approved project would still look like a directory to `inspect_project`; that case was not mounted here.

## Limits

- Linux only (Python 3.12.3). No macOS, no Windows, no Claude Code plugin install in this run.
- The natural symlink race was not won. The post-check swap was forced in-process.
- No claim that filename denylists, atime, or a hostile concurrent directory replacement are solved.
- `pip-audit` answers known published advisories for the versions it actually resolved on this date. It does not review AIC's own code.
