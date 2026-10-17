#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT/skills/x-rail/extensions"
if [[ ! -d node_modules/@earendil-works/pi-coding-agent ]]; then
  npm install
fi
npx tsc -p tsconfig.json --noEmit
printf 'typecheck-extensions: passed\n'
