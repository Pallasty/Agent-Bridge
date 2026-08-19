#!/usr/bin/env bash
# Real macOS AX read-only acceptance. It never clicks, types, or mutates UI;
# System Events is attempted only after the shared best-effort no-ask preflight.
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
overall_rc=0

run_json_phase() {
  local output="$1"
  local phase="$2"
  local stderr_file="${output%.json}.stderr"
  local rc=0
  shift 2
  "$@" >"$output" 2>"$stderr_file" || rc=$?
  if ! python3 -c 'import json,sys; assert isinstance(json.load(open(sys.argv[1])), dict)' "$output" 2>/dev/null; then
    python3 - "$output" "$phase" "$rc" "$stderr_file" <<'PY'
import json
import sys
from pathlib import Path

output, phase, returncode, stderr_path = sys.argv[1:]
stderr = Path(stderr_path).read_text(encoding="utf-8", errors="replace")[:4096]
Path(output).write_text(
    json.dumps(
        {
            "schema": "agent_bridge.macos_ax_acceptance_phase_error.v0",
            "phase": phase,
            "returncode": int(returncode),
            "stderr": stderr,
        }
    )
    + "\n",
    encoding="utf-8",
)
PY
    overall_rc=1
  fi
  if (( rc != 0 )); then
    overall_rc=1
  fi
}

run_json_phase "$WORK/probe.json" probe \
  python3 "$PROBE" --max-windows 8 --jxa-timeout-secs 4
if ! pid=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["frontmost_app"]["pid"])' "$WORK/probe.json" 2>/dev/null); then
  pid=0
  overall_rc=1
fi
run_json_phase "$WORK/trust.json" trust_verify \
  python3 "$VERIFY" --expect ax_trusted_is --state true --max-windows 0 --timeout 2
run_json_phase "$WORK/app.json" app_verify \
  python3 "$VERIFY" --expect frontmost_app_is --pid "$pid" --max-windows 8 --timeout 3
run_json_phase "$WORK/window.json" window_verify \
  python3 "$VERIFY" --expect window_appeared --pid "$pid" --role AXWindow --max-windows 8 --timeout 3
receipt_rc=0
python3 "$RECEIPT_HELPER" write \
  --output "$OUTPUT" \
  --source-commit "$SOURCE_COMMIT" \
  --probe-script "$PROBE" \
  --verify-script "$VERIFY" \
  --probe "$WORK/probe.json" \
  --trust-verify "$WORK/trust.json" \
  --app-verify "$WORK/app.json" \
  --window-verify "$WORK/window.json" || receipt_rc=$?
validate_rc=0
python3 "$RECEIPT_HELPER" validate "$OUTPUT" || validate_rc=$?
if (( overall_rc != 0 || receipt_rc != 0 || validate_rc != 0 )); then
  exit 1
fi
