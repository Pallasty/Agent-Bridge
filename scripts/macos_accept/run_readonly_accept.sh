#!/usr/bin/env bash
# Real macOS AX read-only acceptance. Never prompts, clicks, types, or mutates UI.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../.." && pwd)"
PROBE="${AB_MACOS_AX_PROBE_SCRIPT:-$ROOT/scripts/macos_ax_probe.py}"
VERIFY="${AB_MACOS_AX_VERIFY_SCRIPT:-$ROOT/scripts/macos_ax_verify.py}"
RECEIPT_HELPER="$DIR/macos_ax_acceptance_receipt.py"
OUTPUT="${AB_MACOS_ACCEPT_RECEIPT_PATH:?set AB_MACOS_ACCEPT_RECEIPT_PATH}"
SOURCE_COMMIT="${AB_MACOS_ACCEPT_SOURCE_COMMIT:-$(git -C "$ROOT" rev-parse HEAD)}"
WORK="$(mktemp -d)"
cleanup() { find "$WORK" -depth -delete 2>/dev/null || true; }
trap cleanup EXIT

python3 "$PROBE" --max-windows 8 --jxa-timeout-secs 4 >"$WORK/probe.json"
pid=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["frontmost_app"]["pid"])' "$WORK/probe.json")
python3 "$VERIFY" --expect ax_trusted_is --state true --max-windows 0 --timeout 2 >"$WORK/trust.json"
python3 "$VERIFY" --expect frontmost_app_is --pid "$pid" --max-windows 8 --timeout 3 >"$WORK/app.json"
python3 "$VERIFY" --expect window_appeared --role AXWindow --max-windows 8 --timeout 3 >"$WORK/window.json"
python3 "$RECEIPT_HELPER" write \
  --output "$OUTPUT" \
  --source-commit "$SOURCE_COMMIT" \
  --probe-script "$PROBE" \
  --verify-script "$VERIFY" \
  --probe "$WORK/probe.json" \
  --trust-verify "$WORK/trust.json" \
  --app-verify "$WORK/app.json" \
  --window-verify "$WORK/window.json"
python3 "$RECEIPT_HELPER" validate "$OUTPUT"
