#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT/skills/x-rail/extensions"
node --experimental-strip-types failover.test.ts
node "$ROOT/scripts/test-mock26.mjs"
