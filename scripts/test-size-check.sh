#!/usr/bin/env bash
# 体积检查自检：真实预算必须通过；故意调小的预算必须失败。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 "$ROOT/scripts/check-size.py" --root "$ROOT" >"$TMP/pass.txt"

python3 - "$ROOT/scripts/size-budget.json" "$TMP/tiny.json" <<'PY'
import json, sys
budget = json.load(open(sys.argv[1], encoding="utf-8"))
budget["limits"]["skill_md_bytes"] = 10
json.dump(budget, open(sys.argv[2], "w", encoding="utf-8"))
PY

if python3 "$ROOT/scripts/check-size.py" --root "$ROOT" --budget "$TMP/tiny.json" >"$TMP/fail.txt" 2>&1; then
  printf 'size test: 超限预算竟然通过了\n' >&2
  exit 1
fi
grep -q '超限 skill_md_bytes' "$TMP/fail.txt" || { printf 'size test: 失败信息不精确\n' >&2; exit 1; }
printf 'size test: passed\n'
