#!/usr/bin/env bash
set -euo pipefail
TASK_DIR="${1:-}"
(($#)) && shift
CONFIG=strict
SEEN_CONFIG=0
for arg in "$@"; do
  case "$arg" in
    --strict|--legacy-readonly)
      (( SEEN_CONFIG == 0 )) || { printf 'check-state: conflicting checking options\n' >&2; exit 2; }
      CONFIG="${arg#--}"; SEEN_CONFIG=1 ;;
    *) printf 'check-state: invalid option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
[[ -n "$TASK_DIR" && -f "$TASK_DIR/state.md" ]] || { printf 'check-state: usage: %s TASK_DIR [--strict|--legacy-readonly]\n' "$0" >&2; exit 2; }
command -v python3 >/dev/null || { printf 'check-state: Python 3 is required\n' >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT" "$TASK_DIR" "$CONFIG" <<'PY'
import sys
from pathlib import Path
root, task, config = sys.argv[1:]
sys.path.insert(0, root)
import task_checks
try:
    if config == 'legacy-readonly':
        print('check-state: 历史只读检查，不允许据此提交新完成状态')
    task_checks.check_state(Path(task), strict=config == 'strict')
    print('check-state: passed')
except (OSError, ValueError) as error:
    print(f'check-state: {error}', file=sys.stderr)
    raise SystemExit(1)
PY
