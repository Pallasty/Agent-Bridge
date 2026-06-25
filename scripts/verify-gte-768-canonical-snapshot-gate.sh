#!/usr/bin/env bash
set -euo pipefail

# Gate the next GTE/768 step against an explicit canonical frozen snapshot.
#
# Default mode is discovery-only: no DB copy, no reindex, no deploy, no live
# reader/env changes, and no Agent-Bridge memory/forum writes.
#
# Rehearsal mode is opt-in and scratch-only:
#   --snapshot PATH --run-rehearsal
# It copies PATH to ~/.cache/agent-bridge/gte-rehearsal/<timestamp>/state.db,
# reindexes that copy with AGENT_BRIDGE_ONNX_MODEL, and runs recall_eval against
# the copy via AB_BASELINE_DB.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

model_name="${AGENT_BRIDGE_GTE_MODEL_NAME:-gte-multilingual-base}"
model_base="${AGENT_BRIDGE_ONNX_MODEL_DIR:-$HOME/.cache/agent-bridge/onnx-models}"
live_db="${AB_STATE_DB:-$HOME/.local/share/agent-bridge/state.db}"
snapshot_path="${AB_CANONICAL_BASELINE_DB:-${AB_BASELINE_DB:-}}"
scratch_base="${AB_GTE_REHEARSAL_DIR:-$HOME/.cache/agent-bridge/gte-rehearsal}"
search_roots_raw="${AB_GTE_SNAPSHOT_SEARCH_ROOTS:-$HOME/.cache/agent-bridge:$HOME/.local/share/agent-bridge}"
expect_active="${AB_GTE_EXPECT_ACTIVE:-}"
expect_edges="${AB_GTE_EXPECT_EDGES:-}"
expect_newest="${AB_GTE_EXPECT_NEWEST:-}"
run_rehearsal=false
run_preflight=true
strict=false

usage() {
    cat <<'USAGE'
usage: scripts/verify-gte-768-canonical-snapshot-gate.sh [flags]

Flags:
  --snapshot PATH      Explicit frozen/canonical source DB to check or rehearse.
                       Defaults to $AB_CANONICAL_BASELINE_DB, then $AB_BASELINE_DB.
  --scratch-dir DIR    Scratch base for rehearsal copies. Default:
                       ~/.cache/agent-bridge/gte-rehearsal
  --search-roots LIST  Colon-separated roots to search for candidate DBs.
                       Default: ~/.cache/agent-bridge:~/.local/share/agent-bridge
  --model-name NAME    Expected GTE backend label. Default: gte-multilingual-base
  --model-dir PATH     Base dir containing <model-name>/model.onnx.
  --expect-active N    Optional expected active-memory count for --snapshot.
  --expect-edges N     Optional expected memory-edge count for --snapshot.
  --expect-newest N    Optional expected newest created_at for --snapshot.
  --skip-preflight     Do not call verify-gte-768-preflight.sh first.
  --run-rehearsal      Copy --snapshot into scratch, reindex that copy, and run
                       recall_eval against the copy. Requires --snapshot.
  --strict             Exit non-zero on a NO_GO status.
  -h, --help           Show this help.

Read-only / no-live-mutation contract:
  - never writes the live state DB;
  - refuses to use the live state DB as a source snapshot;
  - never deploys binaries or changes live reader environments;
  - default mode writes nothing;
  - rehearsal mode writes only under --scratch-dir.

Statuses:
  NO_GO_CANONICAL_SNAPSHOT_MISSING  no explicit snapshot and no canonical hint;
  NO_GO_LIVE_STORE_SOURCE           --snapshot points at the live store;
  NO_GO_SNAPSHOT_HAS_WAL            --snapshot has a non-empty WAL sidecar;
  NO_GO_SNAPSHOT_FINGERPRINT_MISMATCH explicit snapshot does not match an
                                      expected logical fingerprint;
  READY_FOR_CANONICAL_REHEARSAL     explicit snapshot is safe to rehearse;
  REHEARSAL_COMPLETED_REVIEW_METRICS scratch reindex + recall_eval completed.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --snapshot)
            snapshot_path="${2:-}"
            shift 2
            ;;
        --scratch-dir)
            scratch_base="${2:-}"
            shift 2
            ;;
        --search-roots)
            search_roots_raw="${2:-}"
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
        --expect-active)
            expect_active="${2:-}"
            shift 2
            ;;
        --expect-edges)
            expect_edges="${2:-}"
            shift 2
            ;;
        --expect-newest)
            expect_newest="${2:-}"
            shift 2
            ;;
        --skip-preflight)
            run_preflight=false
            shift
            ;;
        --run-rehearsal)
            run_rehearsal=true
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

status="READY_FOR_CANONICAL_REHEARSAL"
warnings=0

warn() {
    warnings=$((warnings + 1))
    say "WARN: $*"
}

block() {
    local next="$1"
    shift
    if [[ "$status" != NO_GO_* ]]; then
        status="$next"
    fi
    say "BLOCK: $*"
}

sha_or_unknown() {
    local path="$1"
    if [ -f "$path" ]; then
        sha256sum "$path" | awk '{print $1}'
    else
        printf '<missing>'
    fi
}

file_bytes() {
    stat -c '%s' "$1" 2>/dev/null || printf '?'
}

file_mtime() {
    stat -c '%y' "$1" 2>/dev/null || printf '?'
}

snapshot_fingerprint() {
    local path="$1"
    python3 - "$path" <<'PY'
import pathlib
import sqlite3
import sys

path = pathlib.Path(sys.argv[1]).resolve()
uri = path.as_uri() + "?mode=ro"
con = sqlite3.connect(uri, uri=True)
con.execute("PRAGMA query_only=ON")

active = con.execute("SELECT count(*) FROM memories WHERE status = 'active'").fetchone()[0]
edges = con.execute("SELECT count(*) FROM memory_edges").fetchone()[0]
newest = con.execute("SELECT coalesce(max(created_at), 0) FROM memories").fetchone()[0]
print(f"{active} {edges} {newest}")
PY
}

is_live_db() {
    local path="$1"
    [ -f "$path" ] && [ -f "$live_db" ] && [ "$path" -ef "$live_db" ]
}

classify_db_path() {
    local path="$1"
    if is_live_db "$path"; then
        printf 'live_store_do_not_use'
        return
    fi
    case "$path" in
        *"/gte-rehearsal/"*)
            printf 'scratch_rehearsal_product'
            ;;
        *"/recovery/"*)
            printf 'local_recovery_snapshot_not_canonical_by_itself'
            ;;
        *4016*|*frozen*|*Frozen*|*canonical*|*Canonical*|*mac*|*Mac*|*baseline*|*Baseline*)
            printf 'name_suggests_canonical_candidate'
            ;;
        *)
            printf 'unknown_db_candidate'
            ;;
    esac
}

say "# GTE 768 canonical snapshot gate"
say "repo:        $repo_root"
say "live_db:     $live_db"
say "snapshot:    ${snapshot_path:-<unset>}"
say "model:       $model_name"
say "model_dir:   $model_base/$model_name"
say "scratch:     $scratch_base"
say "expect:      active=${expect_active:-<unset>} edges=${expect_edges:-<unset>} newest=${expect_newest:-<unset>}"
say

say "## Reference contract"
say "source: forum #105/#2550 and docs/reports/goal-c-u/2026-06-25-gte-768-local-rehearsal.md"
say "boundary: no live cut-over until recall benefit is reproduced on the canonical frozen snapshot"
say

if [ "$run_preflight" = true ]; then
    say "## Existing GTE preflight"
    if [ -x scripts/verify-gte-768-preflight.sh ]; then
        scripts/verify-gte-768-preflight.sh \
            --db "$live_db" \
            --model-name "$model_name" \
            --model-dir "$model_base" || warn "GTE preflight command failed"
    else
        warn "scripts/verify-gte-768-preflight.sh is missing or not executable"
    fi
    say
fi

say "## Local DB candidate inventory"
IFS=':' read -r -a search_roots <<< "$search_roots_raw"
db_files=()
for root in "${search_roots[@]}"; do
    [ -d "$root" ] || continue
    while IFS= read -r path; do
        db_files+=("$path")
    done < <(find "$root" -type f \( -name 'state.db' -o -name '*.db' -o -name 'state*.db' \) 2>/dev/null)
done

if [ "${#db_files[@]}" -eq 0 ]; then
    say "INFO no DB candidates found under search roots"
else
    mapfile -t db_files < <(printf '%s\n' "${db_files[@]}" | sort -u)
fi

canonical_hint_count=0
for path in "${db_files[@]}"; do
    role="$(classify_db_path "$path")"
    if [ "$role" = "name_suggests_canonical_candidate" ]; then
        canonical_hint_count=$((canonical_hint_count + 1))
    fi
    say "role=$role bytes=$(file_bytes "$path") mtime=$(file_mtime "$path") sha256=$(sha_or_unknown "$path") path=$path"
done

if [ -z "$snapshot_path" ]; then
    if [ "$canonical_hint_count" -eq 0 ]; then
        block "NO_GO_CANONICAL_SNAPSHOT_MISSING" "no explicit snapshot and no candidate filename/path suggests canonical/frozen/Mac/#4016 baseline"
    else
        warn "$canonical_hint_count path(s) have canonical-looking names; pass one explicitly with --snapshot before rehearsal"
    fi
else
    say
    say "## Explicit snapshot check"
    if [ ! -f "$snapshot_path" ]; then
        block "NO_GO_CANONICAL_SNAPSHOT_MISSING" "snapshot not found: $snapshot_path"
    elif is_live_db "$snapshot_path"; then
        block "NO_GO_LIVE_STORE_SOURCE" "refusing to use live store as source snapshot: $snapshot_path"
    else
        role="$(classify_db_path "$snapshot_path")"
        say "role=$role"
        say "bytes=$(file_bytes "$snapshot_path")"
        say "mtime=$(file_mtime "$snapshot_path")"
        say "sha256=$(sha_or_unknown "$snapshot_path")"
        if command -v python3 >/dev/null 2>&1; then
            if fp="$(snapshot_fingerprint "$snapshot_path" 2>/dev/null)"; then
                read -r fp_active fp_edges fp_newest <<< "$fp"
                say "fingerprint=active=$fp_active edges=$fp_edges newest=$fp_newest"
                if [ -n "$expect_active" ] && [ "$fp_active" != "$expect_active" ]; then
                    block "NO_GO_SNAPSHOT_FINGERPRINT_MISMATCH" "active count mismatch: expected $expect_active got $fp_active"
                fi
                if [ -n "$expect_edges" ] && [ "$fp_edges" != "$expect_edges" ]; then
                    block "NO_GO_SNAPSHOT_FINGERPRINT_MISMATCH" "edge count mismatch: expected $expect_edges got $fp_edges"
                fi
                if [ -n "$expect_newest" ] && [ "$fp_newest" != "$expect_newest" ]; then
                    block "NO_GO_SNAPSHOT_FINGERPRINT_MISMATCH" "newest created_at mismatch: expected $expect_newest got $fp_newest"
                fi
            else
                warn "could not read snapshot logical fingerprint with python3/sqlite"
            fi
        else
            warn "python3 unavailable; cannot read snapshot logical fingerprint"
        fi
        if [ -s "$snapshot_path-wal" ]; then
            block "NO_GO_SNAPSHOT_HAS_WAL" "non-empty WAL sidecar exists; provide a checkpointed/frozen snapshot instead: $snapshot_path-wal"
        elif [ -e "$snapshot_path-wal" ]; then
            warn "zero-byte WAL sidecar exists: $snapshot_path-wal"
        fi
        if [ -s "$snapshot_path-shm" ]; then
            warn "SHM sidecar exists; source is acceptable only if the DB was frozen/checkpointed before capture: $snapshot_path-shm"
        fi
    fi
fi

if [ "$run_rehearsal" = true ]; then
    say
    say "## Scratch rehearsal"
    if [ -z "$snapshot_path" ]; then
        block "NO_GO_CANONICAL_SNAPSHOT_MISSING" "--run-rehearsal requires --snapshot"
    fi
    if [[ "$status" != NO_GO_* ]]; then
        stamp="$(date -u +%Y-%m-%dT%H%M%SZ)"
        out_dir="$scratch_base/$stamp-canonical-snapshot-gate"
        mkdir -p "$out_dir"
        cp -p "$snapshot_path" "$out_dir/state.db"
        say "copied_snapshot=$out_dir/state.db"
        say "copied_sha256=$(sha_or_unknown "$out_dir/state.db")"
        say

        say "### Reindex copy"
        AGENT_BRIDGE_ONNX_MODEL="$model_name" \
            cargo run -p ab-store --example reindex_to_active_model -- "$out_dir/state.db" \
            2>&1 | tee "$out_dir/reindex.log"
        say

        say "### recall_eval on reindexed copy"
        AB_BASELINE_DB="$out_dir/state.db" \
            AGENT_BRIDGE_ONNX_MODEL="$model_name" \
            cargo run -p ab-bridge --example recall_eval \
            2>&1 | tee "$out_dir/recall_eval.log"
        status="REHEARSAL_COMPLETED_REVIEW_METRICS"
    fi
fi

if [ "$status" = "READY_FOR_CANONICAL_REHEARSAL" ] && [ -z "$snapshot_path" ]; then
    status="NO_GO_CANONICAL_SNAPSHOT_MISSING"
fi

say
say "## Verdict"
say "status=$status warnings=$warnings"

if [ "$strict" = true ] && [[ "$status" == NO_GO_* ]]; then
    exit 1
fi
