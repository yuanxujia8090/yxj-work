#!/usr/bin/env bash
# 打包脚本的自检：dry-run 不落盘、导出可重复拒绝、两个清单互不包含、无运行数据。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DEST="$WORK/pkg"

fail() { printf 'package test: %s\n' "$1" >&2; exit 1; }

bash "$ROOT/scripts/package-v4.sh" --dest "$DEST" --dry-run >"$WORK/dry.txt"
[[ ! -e "$DEST" ]] || fail 'dry-run 创建了目录'
grep -q 'cross' "$WORK/dry.txt" 2>/dev/null || grep -q '交叉收录: 无' "$WORK/dry.txt" || fail 'dry-run 缺少交叉收录结论'
grep -q 'tree sha256:' "$WORK/dry.txt" || fail 'dry-run 缺少摘要'

bash "$ROOT/scripts/package-v4.sh" --dest "$DEST" >"$WORK/export.txt"
[[ -f "$DEST/x-rail/manifest.json" ]] || fail '缺少 x-rail manifest'
[[ -f "$DEST/model-recovery/manifest.json" ]] || fail '缺少 model-recovery manifest'
[[ -f "$DEST/x-rail/SKILL.md" ]] || fail '缺少 x-rail 入口'
[[ -f "$DEST/model-recovery/index.ts" ]] || fail '缺少插件入口'

if bash "$ROOT/scripts/package-v4.sh" --dest "$DEST" >/dev/null 2>&1; then
  fail '重复导出应被拒绝'
fi

python3 - "$DEST" <<'PY'
import json, pathlib, sys
dest = pathlib.Path(sys.argv[1])
xr = json.loads((dest / "x-rail/manifest.json").read_text())
plugin = json.loads((dest / "model-recovery/manifest.json").read_text())
assert xr["product"] == "x-rail" and plugin["product"] == "model-recovery"
assert xr["entry"].startswith("skills/x-rail/") and plugin["entry"].startswith("plugins/")
assert xr["source_commit"] and plugin["source_commit"] == xr["source_commit"]
assert xr["tree_digest"].startswith("sha256:") and plugin["tree_digest"].startswith("sha256:")
overlap = set(xr["files"]) & set(plugin["files"])
assert not overlap, f"清单重叠: {overlap}"
for name, files in (("x-rail", xr["files"]), ("model-recovery", plugin["files"])):
    for file in files:
        assert "node_modules" not in file, f"{name} 含 node_modules: {file}"
        assert not file.endswith(".pyc"), f"{name} 含 .pyc: {file}"
        assert "/.work-docs/" not in file and "plans/" not in file, f"{name} 含运行数据: {file}"
        assert file not in {"auth.json", ".env"}, f"{name} 含凭据: {file}"
        assert "failover" not in file, f"{name} 含旧 failover: {file}"
        assert (dest / ("x-rail" if name == "x-rail" else "model-recovery") / file).is_file(), f"缺文件 {name}/{file}"
PY

printf 'package test: passed\n'
