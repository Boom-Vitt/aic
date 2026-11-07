#!/bin/bash
# Idempotent setup for Boom's Mac mini: Apple Silicon, Homebrew at /opt/homebrew.
# Dry-run unless --apply. Never reads, prints, or writes API keys, tokens, or
# credential files. Claude Code is installed with the official Homebrew cask
# from the Claude Code setup page. This script does not run npm install and
# does not pipe a remote installer into a shell.
set -euo pipefail

PLUGIN_SHA="ad1a6032465546883d57299fda5677d6b2a7750d"
PLUGIN_ID="boom-big-nose-workflow@claude-mods-boombignose"
PLUGIN_URL="https://github.com/Boom-Vitt/claude-mods-boombignose.git"
MIN_FREE_KB="${AIC_ORCA_MIN_FREE_KB:-6291456}"
BREW="/opt/homebrew/bin/brew"

host_os() {
  printf '%s' "${AIC_ORCA_UNAME:-$(uname -s)}"
}

host_arch() {
  printf '%s' "${AIC_ORCA_ARCH:-$(uname -m)}"
}

overrides_set() {
  if [ -n "${AIC_ORCA_UNAME:-}" ] || [ -n "${AIC_ORCA_ARCH:-}" ] || [ -n "${AIC_ORCA_FREE_KB:-}" ]; then
    return 0
  fi
  return 1
}

disk_free_kb() {
  if [ -n "${AIC_ORCA_FREE_KB:-}" ]; then
    printf '%s' "$AIC_ORCA_FREE_KB"
    return 0
  fi
  df -kP / | awk 'NR == 2 { print $4 }'
}

version_ge() {
  awk -v have="$1" -v need="$2" 'BEGIN {
    split(have, a, ".");
    split(need, b, ".");
    for (i = 1; i <= 3; i++) {
      ai = a[i] + 0;
      bi = b[i] + 0;
      if (ai > bi) exit 0;
      if (ai < bi) exit 1;
    }
    exit 0;
  }'
}

git_version() {
  git --version 2>/dev/null | awk '{ print $3 }'
}

plugin_cache() {
  printf '%s' "${HOME}/.local/share/aic/orca-plugin/claude-mods-boombignose"
}

plugin_state() {
  local cache current
  cache="$1"
  if [ -L "$cache" ]; then
    printf '%s' 'symlink'
    return 0
  fi
  if [ ! -d "$cache/.git" ]; then
    printf '%s' 'missing'
    return 0
  fi
  if [ -n "$(git -C "$cache" status --porcelain)" ]; then
    printf '%s' 'dirty'
    return 0
  fi
  current="$(git -C "$cache" rev-parse HEAD 2>/dev/null || true)"
  if [ "$current" = "$PLUGIN_SHA" ]; then
    printf '%s' 'pinned'
  else
    printf '%s' 'moved'
  fi
}

json_escape() {
  printf '%s' "$1" | tr -d '"'
}

emit_json() {
  ok="$1"
  mode="$2"
  applicable="$3"
  message="$4"
  printf '{\n  "ok": %s,\n  "mode": "%s",\n  "applicable": %s,\n  "os": "%s",\n  "arch": "%s",\n  "message": "%s",\n  "plugin_sha": "%s",\n  "secrets_handled": false,\n  "installer": "homebrew-cask-claude-code"\n}\n' \
    "$ok" "$mode" "$applicable" "$(json_escape "$(host_os)")" "$(json_escape "$(host_arch)")" \
    "$(json_escape "$message")" "$PLUGIN_SHA"
}

usage() {
  echo "usage: macos-setup-orca.sh [--dry-run|--apply]" >&2
}

sync_plugin() {
  local cache state
  cache="$(plugin_cache)"
  state="$(plugin_state "$cache")"
  case "$state" in
    symlink|dirty)
      echo "plugin cache is $state; refusing to replace it: $cache" >&2
      return 3
      ;;
    pinned)
      return 0
      ;;
    missing)
      mkdir -p "$(dirname "$cache")"
      git clone --filter=blob:none --no-checkout "$PLUGIN_URL" "$cache"
      ;;
    moved)
      ;;
    *)
      echo "unexpected plugin cache state: $state" >&2
      return 1
      ;;
  esac
  git -C "$cache" fetch --depth 1 origin "$PLUGIN_SHA"
  git -C "$cache" checkout --detach FETCH_HEAD
}

claude_bin() {
  if [ -n "${AIC_ORCA_CLAUDE:-}" ]; then
    printf '%s' "$AIC_ORCA_CLAUDE"
    return 0
  fi
  command -v claude
}

plugin_list_has_pin() {
  local line token has_id has_sha
  local -a tokens
  while IFS= read -r line || [ -n "$line" ]; do
    has_id=0
    has_sha=0
    # shellcheck disable=SC2206
    tokens=( $line )
    for token in "${tokens[@]}"; do
      case "$token" in
        "$PLUGIN_ID") has_id=1 ;;
        "$PLUGIN_SHA"|ad1a603) has_sha=1 ;;
      esac
    done
    if [ "$has_id" -eq 1 ] && [ "$has_sha" -eq 1 ]; then
      return 0
    fi
  done
  return 1
}

link_plugin() {
  local cache binary list
  cache="$(plugin_cache)"
  export PATH="/opt/homebrew/bin:${PATH}"
  binary="$(claude_bin || true)"
  if [ -z "$binary" ]; then
    echo "claude is not on PATH" >&2
    return 1
  fi
  list="$("$binary" plugin list 2>/dev/null || true)"
  if printf '%s\n' "$list" | plugin_list_has_pin; then
    return 0
  fi
  "$binary" plugin marketplace add "$cache"
  "$binary" plugin install "$PLUGIN_ID"
}

run_doctor() {
  local cache doctor work status
  cache="$(plugin_cache)"
  doctor="$cache/boom-big-nose-workflow/scripts/orca-doctor.sh"
  if [ ! -f "$doctor" ]; then
    echo "Orca doctor script is not in the pinned checkout." >&2
    return 1
  fi
  work="$(mktemp -d)"
  git init -q "$work"
  set +e
  (
    cd "$work" || exit 1
    ORCA_DOCTOR_OFFLINE=1 sh "$doctor"
  )
  status=$?
  set -e
  rm -rf "$work"
  if command -v claude >/dev/null 2>&1; then
    claude doctor || true
  fi
  return "$status"
}

ensure_formula() {
  local formula
  formula="$1"
  export PATH="/opt/homebrew/bin:${PATH}"
  if command -v "$formula" >/dev/null 2>&1; then
    return 0
  fi
  "$BREW" install "$formula"
}

main() {
  local mode os_name arch_name free status
  mode="dry-run"
  if [ "${1:-}" = "--apply" ]; then
    mode="apply"
  elif [ "${1:-}" = "--dry-run" ] || [ -z "${1:-}" ]; then
    mode="dry-run"
  elif [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
  else
    usage
    exit 2
  fi
  if [ -n "${2:-}" ]; then
    usage
    exit 2
  fi
  os_name="$(host_os)"
  arch_name="$(host_arch)"
  if [ "$mode" = "apply" ] && overrides_set; then
    emit_json false apply false "refusing --apply while test host overrides are set"
    exit 3
  fi
  if [ "$os_name" != "Darwin" ] || [ "$arch_name" != "arm64" ]; then
    emit_json true "$mode" false "this setup targets an Apple Silicon Mac mini"
    if [ "$mode" = "apply" ]; then
      exit 2
    fi
    exit 0
  fi
  free="$(disk_free_kb)"
  case "$free" in
    ''|*[!0-9]*)
      emit_json false "$mode" true "could not read free disk"
      exit 1
      ;;
  esac
  if [ "$free" -lt "$MIN_FREE_KB" ]; then
    emit_json false "$mode" true "free disk ${free} KiB is below ${MIN_FREE_KB} KiB"
    exit 3
  fi
  if [ ! -x "$BREW" ]; then
    emit_json false "$mode" true "Homebrew is required at ${BREW}"
    exit 1
  fi
  if [ "$mode" = "dry-run" ]; then
    emit_json true dry-run true "dry-run only; re-run with --apply to install and link Orca"
    exit 0
  fi
  export PATH="/opt/homebrew/bin:${PATH}"
  ensure_formula git
  if ! version_ge "$(git_version)" "2.38"; then
    emit_json false apply true "git 2.38 or newer is required"
    exit 1
  fi
  ensure_formula node
  if ! command -v python3 >/dev/null 2>&1 && ! command -v python3.11 >/dev/null 2>&1; then
    if ! "$BREW" list --versions python@3.11 2>/dev/null | grep -q .; then
      ensure_formula python@3.11
    fi
  fi
  if ! command -v claude >/dev/null 2>&1; then
    "$BREW" install --cask claude-code
  fi
  claude --version
  sync_plugin && status=0 || status=$?
  if [ "$status" -ne 0 ]; then
    emit_json false apply true "plugin cache was not updated"
    exit "$status"
  fi
  link_plugin && status=0 || status=$?
  if [ "$status" -ne 0 ]; then
    emit_json false apply true "plugin link failed; run claude once to sign in, then retry"
    exit "$status"
  fi
  run_doctor && status=0 || status=$?
  if [ "$status" -ne 0 ]; then
    emit_json false apply true "offline doctor reported a required failure; optional MCP auth is separate"
    exit "$status"
  fi
  emit_json true apply true "Claude Code, pinned Orca v0.4.0, and offline doctor finished; sign in with claude before real work; optional MCP auth is separate"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
