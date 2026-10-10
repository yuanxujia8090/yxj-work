#!/usr/bin/env bash
set -euo pipefail
TASK_DIR="${1:-}"
(($#)) && shift
MODE=ready
CONFIG=strict
SEEN_MODE=0
SEEN_CONFIG=0
for arg in "$@"; do
  case "$arg" in
    --draft|--ready|--seal|--locked)
      (( SEEN_MODE == 0 )) || { printf 'check-contract: duplicate mode\n' >&2; exit 2; }
      MODE="${arg#--}"; SEEN_MODE=1 ;;
    --strict|--legacy-readonly)
      (( SEEN_CONFIG == 0 )) || { printf 'check-contract: conflicting checking options\n' >&2; exit 2; }
      CONFIG="${arg#--}"; SEEN_CONFIG=1 ;;
    *) printf 'check-contract: invalid option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
[[ -n "$TASK_DIR" ]] || { printf 'check-contract: usage: %s TASK_DIR [MODE] [--strict|--legacy-readonly]\n' "${0##*/}" >&2; exit 2; }
[[ "$CONFIG:$MODE" != legacy-readonly:seal ]] || { printf 'check-contract: legacy-readonly cannot seal\n' >&2; exit 2; }
command -v python3 >/dev/null || { printf 'check-contract: Python 3 is required\n' >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHONDONTWRITEBYTECODE=1 python3 - "$ROOT" "$TASK_DIR" "$MODE" "$CONFIG" <<'PY'
import sys
from pathlib import Path
root, task, mode, config = sys.argv[1:]
sys.path.insert(0, root)
import task_checks
try:
    if config == 'legacy-readonly':
        print('check-contract: 历史只读检查，不允许据此提交新完成状态')
    task_checks.check_contract(Path(task), mode=mode, strict=config == 'strict')
    print('check-contract: passed')
except (OSError, ValueError) as error:
    print(f'check-contract: {error}', file=sys.stderr)
    raise SystemExit(1)
PY
