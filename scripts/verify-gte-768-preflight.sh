#!/usr/bin/env bash
set -euo pipefail

# Read-only preflight for the GTE 768-dim memory embedding cut-over.
#
# This script does not copy state.db, reindex embeddings, deploy binaries, change
# environment variables, or write Agent-Bridge memory/forum state. It only checks
# whether the local node has the assets and runtime posture needed before a
# scratch-copy rehearsal can start.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

model_name="${AGENT_BRIDGE_GTE_MODEL_NAME:-gte-multilingual-base}"
model_base="${AGENT_BRIDGE_ONNX_MODEL_DIR:-$HOME/.cache/agent-bridge/onnx-models}"
db_path="${AB_STATE_DB:-$HOME/.local/share/agent-bridge/state.db}"
ab_bin="${AB_BIN:-$HOME/.local/bin/agent-bridge.real}"
run_tests=false
strict=false
live_cutover=false

usage() {
    cat <<'USAGE'
usage: scripts/verify-gte-768-preflight.sh [flags]

Flags:
  --db PATH            State DB to inspect. Default: ~/.local/share/agent-bridge/state.db
  --model-name NAME    Expected GTE backend label. Default: gte-multilingual-base
  --model-dir PATH     Base dir containing <model-name>/model.onnx. Default:
                       $AGENT_BRIDGE_ONNX_MODEL_DIR or ~/.cache/agent-bridge/onnx-models
  --ab-bin PATH        agent-bridge.real binary for continuity-report.
  --run-tests          Also run the small GTE dimension/gate unit tests.
  --live-cutover       Treat non-GTE live readers as a blocking production
                       cut-over risk. Without this flag, reader mismatch is
                       reported as informational because scratch-copy rehearsal
                       can run safely with old live readers.
  --strict             Exit non-zero when the cut-over is not ready.
  -h, --help           Show this help.

Read-only contract:
  - no live DB writes;
  - no reindex;
  - no binary deploy;
  - no environment changes;
  - no memory/forum writes.

Statuses:
  READY_FOR_SCRATCH_REHEARSAL  assets exist and no old-reader conflict was seen;
  NO_GO_MODEL_ASSET_MISSING    required local ONNX/tokenizer files are missing;
  NO_GO_LIVE_READER_MISMATCH   a live agent-bridge reader is not using GTE;
  CHECK_WARNINGS_PRESENT       non-blocking warnings exist; review output.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --db)
            db_path="${2:-}"
            shift 2
            ;;
        --model-name)
            model_name="${2:-}"
            shift 2
            ;;
        --model-dir)
            model_base="${2:-}"
            shift 2
            ;;
        --ab-bin)
            ab_bin="${2:-}"
            shift 2
            ;;
        --run-tests)
            run_tests=true
            shift
            ;;
        --live-cutover)
            live_cutover=true
            shift
            ;;
        --strict)
            strict=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown flag: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

say() { printf '%s\n' "$*"; }

status="READY_FOR_SCRATCH_REHEARSAL"
warnings=0

warn() {
    warnings=$((warnings + 1))
    say "WARN: $*"
}

block() {
    local next="$1"
    shift
    if [ "$status" = "READY_FOR_SCRATCH_REHEARSAL" ] || [ "$status" = "CHECK_WARNINGS_PRESENT" ]; then
        status="$next"
    fi
    say "BLOCK: $*"
}

if [ ! -x "$ab_bin" ]; then
    block "NO_GO_MODEL_ASSET_MISSING" "agent-bridge binary is not executable: $ab_bin"
fi

say "# GTE 768 preflight"
say "repo:       $repo_root"
say "db:         $db_path"
say "ab_bin:     $ab_bin"
say "model:      $model_name"
say "model_dir:  $model_base/$model_name"
say

say "## Store continuity"
if [ -x "$ab_bin" ]; then
    if [ -f "$db_path" ]; then
        AB_STATE_DB="$db_path" "$ab_bin" continuity-report --json || warn "continuity-report failed"
    else
        warn "state DB not found: $db_path"
    fi
else
    warn "skipping continuity-report because ab_bin is unavailable"
fi
say

say "## GTE model asset files"
model_dir="$model_base/$model_name"
required_files=(
    model.onnx
    tokenizer.json
    config.json
    special_tokens_map.json
    tokenizer_config.json
)
missing=0
for file in "${required_files[@]}"; do
    path="$model_dir/$file"
    if [ -f "$path" ]; then
        bytes="$(wc -c < "$path" | tr -d '[:space:]')"
        say "OK   $file ($bytes bytes)"
    else
        say "MISS $file"
        missing=$((missing + 1))
    fi
done
if [ -f "$model_dir/model.onnx_data" ]; then
    bytes="$(wc -c < "$model_dir/model.onnx_data" | tr -d '[:space:]')"
    say "INFO model.onnx_data present ($bytes bytes)"
fi
if [ -f "$model_dir/asset-manifest.txt" ]; then
    say "INFO asset-manifest.txt present"
fi
if [ "$missing" -gt 0 ]; then
    block "NO_GO_MODEL_ASSET_MISSING" "$missing required model asset file(s) missing"
fi
say

say "## Live agent-bridge readers"
reader_mismatch=0
reader_count=0
while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    [ -r "/proc/$pid/environ" ] || continue
    reader_count=$((reader_count + 1))
    env_lines="$(tr '\0' '\n' < "/proc/$pid/environ" || true)"
    model_env="$(printf '%s\n' "$env_lines" | awk -F= '$1 == "AGENT_BRIDGE_ONNX_MODEL" {print $2; found=1} END {if (!found) print "<unset>"}')"
    model_dir_env="$(printf '%s\n' "$env_lines" | awk -F= '$1 == "AGENT_BRIDGE_ONNX_MODEL_DIR" {print $2; found=1} END {if (!found) print "<unset>"}')"
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    say "pid=$pid model=$model_env model_dir=$model_dir_env cmd=$cmd"
    if [ "$model_env" != "$model_name" ] && [ "$model_env" != "gte" ] && [ "$model_env" != "gte-ml" ]; then
        reader_mismatch=$((reader_mismatch + 1))
    fi
done < <(pgrep -f 'agent-bridge.real (daemon|daemon-http|mcp)' || true)

if [ "$reader_count" -eq 0 ]; then
    warn "no live agent-bridge daemon/mcp readers found"
elif [ "$reader_mismatch" -gt 0 ]; then
    if [ "$live_cutover" = true ]; then
        block "NO_GO_LIVE_READER_MISMATCH" "$reader_mismatch live reader(s) are not using GTE"
    else
        say "INFO $reader_mismatch live reader(s) are not using GTE; OK for scratch rehearsal, not OK for live cut-over"
    fi
fi
say

if [ "$run_tests" = true ]; then
    say "## Cargo gate tests"
    CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" cargo test -p ab-store model_name_dimension_gate_covers_gte_flagday -- --nocapture
    CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" cargo test -p ab-bridge --example recall_eval confirm_window_defaults_are_model_aware -- --nocapture
    CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" cargo test -p ab-bridge --example recall_eval stored_embedding_profile_backend_compatibility_is_strict_when_known -- --nocapture
    say
fi

if [ "$status" = "READY_FOR_SCRATCH_REHEARSAL" ] && [ "$warnings" -gt 0 ]; then
    status="CHECK_WARNINGS_PRESENT"
fi

say "## Verdict"
say "status=$status warnings=$warnings"

if [ "$strict" = true ] && [ "$status" != "READY_FOR_SCRATCH_REHEARSAL" ]; then
    exit 1
fi
