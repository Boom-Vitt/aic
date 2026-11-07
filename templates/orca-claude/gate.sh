#!/bin/sh
# Project gate used by Orca. Exit 0 when the project checks pass, 1 on failure,
# and 2 when this checkout has no configured check.
set -eu
here=$(unset CDPATH; cd -- "$(dirname -- "$0")" && pwd)
case "$here" in
  */scripts|*/.orca) root=$(unset CDPATH; cd -- "$here/.." && pwd) ;;
  *) root=$here ;;
esac
cd "$root"
if [ -x "$root/scripts/verify.sh" ]; then
  exec "$root/scripts/verify.sh"
fi
echo "No ./scripts/verify.sh. Set the project's lint, typecheck, and test commands in gate.sh." >&2
exit 2
