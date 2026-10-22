#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT/skills/x-rail/extensions"
if [[ ! -d node_modules/@earendil-works/pi-coding-agent ]]; then
  npm install
fi
npx tsc -p tsconfig.json --noEmit
# 模型恢复插件独立编译，复用已安装的宿主类型，不额外下载。
cd "$ROOT/plugins/pi-model-recovery"
"$ROOT/skills/x-rail/extensions/node_modules/.bin/tsc" -p tsconfig.json --noEmit
node decide.test.ts >/dev/null
printf 'typecheck-extensions: passed\n'
