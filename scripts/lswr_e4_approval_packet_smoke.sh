#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO"
exec cargo run -q -p ab-bridge --example lswr_e3_dry_run_smoke -- --assert-non-empty --assert-approval-packet "$@"
