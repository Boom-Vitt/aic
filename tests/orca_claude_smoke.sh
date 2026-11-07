#!/bin/sh
# Public-script smoke test. No network and no model call.
set -eu
ROOT=$(unset CDPATH; cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

python3 -c 'import json,sys; json.dump({"version":1,"title":"cycle","status":"draft","goal":"g","streams":[{"slug":"a","role":"claude-code","paths":["a.txt"],"dependsOn":["b"],"acceptance":["pytest"]},{"slug":"b","role":"claude-code","paths":["b.txt"],"dependsOn":["a"],"acceptance":["pytest"]}]}, open(sys.argv[1],"w"))' "$tmp/cycle.json"
if "$ROOT/scripts/orca-headless.sh" --plan "$tmp/cycle.json" >"$tmp/cycle.out"; then
  echo "cyclic plan was accepted" >&2
  exit 1
fi

"$ROOT/scripts/orca-headless.sh" --plan "$ROOT/templates/orca-claude/plan.example.json" >"$tmp/ok.json"
python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["ok"] is True; assert data["invoked_claude"] is False; assert data["push"] is False; assert data["delete"] is False' "$tmp/ok.json"

mkdir "$tmp/exists"
if "$ROOT/scripts/bootstrap-orca-project.sh" "$tmp/exists"; then
  echo "bootstrap overwrote an existing path" >&2
  exit 1
fi
"$ROOT/scripts/bootstrap-orca-project.sh" "$tmp/fresh"
"$tmp/fresh/gate.sh" && code=$? || code=$?
test "$code" -eq 2
test -x "$tmp/fresh/.orca/gate.sh"

python3 "$ROOT/.claude/hooks/guard.py" <<'EOF' && code=$? || code=$?
{"tool_name":"Bash","tool_input":{"command":"git push origin main"},"cwd":"/tmp"}
EOF
test "$code" -eq 2

out=$(ANTHROPIC_API_KEY=sk-ant-testsecret AIC_ORCA_UNAME=Linux "$ROOT/scripts/macos-setup-orca.sh" --dry-run 2>&1)
case "$out" in
  *sk-ant-testsecret*)
    echo "setup printed a secret" >&2
    exit 1
    ;;
esac
case "$out" in
  *'"secrets_handled": false'*) ;;
  *)
    echo "setup result did not record that it handled no secrets" >&2
    exit 1
    ;;
esac

printf '%s\n' "smoke ok"
