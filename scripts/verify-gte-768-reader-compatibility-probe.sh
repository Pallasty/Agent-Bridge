#!/usr/bin/env bash
set -euo pipefail

# Read-only copied-DB reader compatibility probe for the GTE 768 cut-over lane.
#
# This script does not copy DBs, reindex embeddings, start/stop readers, deploy
# binaries, or change live environments. It only inspects explicitly supplied
# DB files and emits the backend/dimension evidence needed for a later owner
# decision.

target_backend="${AGENT_BRIDGE_GTE_MODEL_NAME:-gte-multilingual-base}"
target_dim="${AGENT_BRIDGE_GTE_DIM:-768}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$script_dir/lib/ab-platform.sh"
live_db="${AB_STATE_DB:-$(ab_default_state_db)}"
pre_db="${AB_GTE_COMPAT_PRE_DB:-${AB_CANONICAL_BASELINE_DB:-${AB_BASELINE_DB:-}}}"
post_db="${AB_GTE_COMPAT_POST_DB:-}"
strict=false

usage() {
    cat <<'USAGE'
usage: scripts/verify-gte-768-reader-compatibility-probe.sh [flags]

Flags:
  --pre-db PATH          Pre-reindex copied DB to inspect. Defaults to
                         $AB_GTE_COMPAT_PRE_DB, then $AB_CANONICAL_BASELINE_DB,
                         then $AB_BASELINE_DB.
  --post-db PATH         Optional post-reindex copied/scratch DB to inspect.
                         Defaults to $AB_GTE_COMPAT_POST_DB.
  --live-db PATH         Live DB path that inputs must not equal. Default:
                         platform default
                         (Linux: ~/.local/share/agent-bridge/state.db;
                         macOS: ~/Library/Application Support/agent-bridge/state.db)
  --target-backend NAME  Expected GTE backend label. Default:
                         gte-multilingual-base
  --target-dim N         Expected target vector dimension. Default: 768.
  --strict              Exit non-zero on a NO_GO verdict.
  -h, --help            Show this help.

Read-only / no-live-mutation contract:
  - refuses the live DB as --pre-db or --post-db;
  - opens inspected DBs read-only with SQLite immutable mode;
  - never writes DB files, WAL/SHM files, memory, forum, or runtime env;
  - never proves mixed-reader support by itself.

Verdicts:
  READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL
      Copied DB evidence is coherent enough to draft an atomic cut-over
      proposal. Mixed-reader support is still NOT proven.
  CHECK_WARNINGS_PRESENT
      Evidence is incomplete but no hard invariant failed.
  NO_GO_DB_MISSING
      A required DB path is missing.
  NO_GO_LIVE_STORE_SOURCE
      An inspected DB path is the live store.
  NO_GO_POST_REINDEX_INVARIANT
      The post-reindex DB does not show all active embedded rows on the target
      backend and target dimension.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --pre-db)
            pre_db="${2:-}"
            shift 2
            ;;
        --post-db)
            post_db="${2:-}"
            shift 2
            ;;
        --live-db)
            live_db="${2:-}"
            shift 2
            ;;
        --target-backend)
            target_backend="${2:-}"
            shift 2
            ;;
        --target-dim)
            target_dim="${2:-}"
            shift 2
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

status="READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL"
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

same_file_as_live() {
    local path="$1"
    ab_same_file "$path" "$live_db"
}

check_db_arg() {
    local label="$1"
    local path="$2"
    local required="$3"

    if [ -z "$path" ]; then
        if [ "$required" = true ]; then
            block "NO_GO_DB_MISSING" "$label DB path is required"
        else
            warn "$label DB path is unset; skipping $label profile"
        fi
        return
    fi

    if [ ! -f "$path" ]; then
        block "NO_GO_DB_MISSING" "$label DB not found: $path"
        return
    fi

    if same_file_as_live "$path"; then
        block "NO_GO_LIVE_STORE_SOURCE" "refusing live store as $label DB: $path"
    fi
}

say "# GTE 768 reader compatibility probe"
say "live_db:        $live_db"
say "pre_db:         ${pre_db:-<unset>}"
say "post_db:        ${post_db:-<unset>}"
say "target_backend: $target_backend"
say "target_dim:     $target_dim"
say
say "## Contract"
say "read_only=true"
say "writes_db=false"
say "runs_reindex=false"
say "starts_or_stops_readers=false"
say "mixed_readers_supported=false"
say "recommendation=atomic_node_cutover_only_unless_separately_proven"
say

check_db_arg "pre" "$pre_db" true
check_db_arg "post" "$post_db" false

if [[ "$status" != NO_GO_* ]]; then
    python3 - "$live_db" "$target_backend" "$target_dim" "$pre_db" "$post_db" <<'PY'
import pathlib
import sqlite3
import sys

_live_db = pathlib.Path(sys.argv[1])
target_backend = sys.argv[2]
target_dim = int(sys.argv[3])
pre_db = pathlib.Path(sys.argv[4]) if sys.argv[4] else None
post_db = pathlib.Path(sys.argv[5]) if sys.argv[5] else None
target_bytes = target_dim * 4


def connect(path: pathlib.Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA query_only=ON")
    return con


def scalar(con: sqlite3.Connection, sql: str, args=()):
    return con.execute(sql, args).fetchone()[0]


def profile(path: pathlib.Path) -> dict:
    con = connect(path)
    try:
        buckets = con.execute(
            """
            SELECT COALESCE(NULLIF(embedding_backend, ''), 'unknown') AS backend,
                   LENGTH(embedding) AS bytes,
                   COUNT(*) AS rows
              FROM memories
             WHERE status='active'
               AND embedding IS NOT NULL
               AND LENGTH(embedding) > 0
             GROUP BY backend, bytes
             ORDER BY rows DESC, bytes DESC, backend ASC
            """
        ).fetchall()
        active_total = scalar(con, "SELECT COUNT(*) FROM memories WHERE status='active'")
        embedded = scalar(
            con,
            """
            SELECT COUNT(*) FROM memories
             WHERE status='active'
               AND embedding IS NOT NULL
               AND LENGTH(embedding) > 0
            """,
        )
        null_or_empty = scalar(
            con,
            """
            SELECT COUNT(*) FROM memories
             WHERE status='active'
               AND (embedding IS NULL OR LENGTH(embedding) = 0)
            """,
        )
        target_good = scalar(
            con,
            """
            SELECT COUNT(*) FROM memories
             WHERE status='active'
               AND embedding_backend = ?1
               AND embedding IS NOT NULL
               AND LENGTH(embedding) = ?2
            """,
            (target_backend, target_bytes),
        )
        target_bad_dim = scalar(
            con,
            """
            SELECT COUNT(*) FROM memories
             WHERE status='active'
               AND embedding_backend = ?1
               AND embedding IS NOT NULL
               AND LENGTH(embedding) != ?2
            """,
            (target_backend, target_bytes),
        )
        stale_for_target = scalar(
            con,
            """
            SELECT COUNT(*) FROM memories
             WHERE status='active'
               AND (embedding IS NULL
                    OR LENGTH(embedding) = 0
                    OR embedding_backend IS NULL
                    OR embedding_backend != ?1
                    OR LENGTH(embedding) != ?2)
            """,
            (target_backend, target_bytes),
        )
        dominant = buckets[0] if buckets else ("none", 0, 0)
        return {
            "path": str(path),
            "active_total": int(active_total),
            "embedded": int(embedded),
            "null_or_empty": int(null_or_empty),
            "target_good": int(target_good),
            "target_bad_dim": int(target_bad_dim),
            "stale_for_target": int(stale_for_target),
            "dominant_backend": dominant[0],
            "dominant_bytes": int(dominant[1] or 0),
            "dominant_dim": int(dominant[1] // 4) if dominant[1] else 0,
            "dominant_rows": int(dominant[2]),
            "buckets": [
                {"backend": b, "bytes": int(by or 0), "dim": int(by // 4) if by else 0, "rows": int(n)}
                for (b, by, n) in buckets
            ],
        }
    finally:
        con.close()


def print_profile(label: str, p: dict) -> None:
    print(f"## {label} profile")
    print(f"path={p['path']}")
    print(f"active_total={p['active_total']}")
    print(f"embedded={p['embedded']}")
    print(f"null_or_empty={p['null_or_empty']}")
    print(
        "dominant="
        f"backend={p['dominant_backend']} dim={p['dominant_dim']} rows={p['dominant_rows']}"
    )
    print(f"target_good={p['target_good']}")
    print(f"target_bad_dim={p['target_bad_dim']}")
    print(f"stale_for_target={p['stale_for_target']}")
    print("buckets:")
    for bucket in p["buckets"]:
        print(
            "  - "
            f"backend={bucket['backend']} bytes={bucket['bytes']} "
            f"dim={bucket['dim']} rows={bucket['rows']}"
        )
    print()


pre = profile(pre_db)
print_profile("pre_db", pre)

post = None
if post_db is not None:
    post = profile(post_db)
    print_profile("post_db", post)

print("## Compatibility interpretation")
if post is None:
    print("post_reindex_invariant=unknown")
    print("mixed_reader_support=not_proven")
    print("recommended_mode=atomic_node_cutover_only")
    print("probe_result=CHECK_WARNINGS_PRESENT")
elif post["target_good"] == post["active_total"] and post["target_bad_dim"] == 0:
    print("post_reindex_invariant=pass")
    print("mixed_reader_support=not_proven")
    print("recommended_mode=atomic_node_cutover_only")
    print("probe_result=READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL")
else:
    print("post_reindex_invariant=fail")
    print("mixed_reader_support=not_proven")
    print("recommended_mode=do_not_cut_over")
    print("probe_result=NO_GO_POST_REINDEX_INVARIANT")
PY
    probe_result="$(
        python3 - "$target_backend" "$target_dim" "$post_db" <<'PY'
import pathlib
import sqlite3
import sys

target_backend = sys.argv[1]
target_dim = int(sys.argv[2])
post = pathlib.Path(sys.argv[3]) if sys.argv[3] else None
if post is None:
    print("CHECK_WARNINGS_PRESENT")
    raise SystemExit

con = sqlite3.connect(post.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
con.execute("PRAGMA query_only=ON")
active = con.execute("SELECT COUNT(*) FROM memories WHERE status='active'").fetchone()[0]
good = con.execute(
    """
    SELECT COUNT(*) FROM memories
     WHERE status='active'
       AND embedding_backend = ?1
       AND embedding IS NOT NULL
       AND LENGTH(embedding) = ?2
    """,
    (target_backend, target_dim * 4),
).fetchone()[0]
bad_dim = con.execute(
    """
    SELECT COUNT(*) FROM memories
     WHERE status='active'
       AND embedding_backend = ?1
       AND embedding IS NOT NULL
       AND LENGTH(embedding) != ?2
    """,
    (target_backend, target_dim * 4),
).fetchone()[0]
print(
    "READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL"
    if good == active and bad_dim == 0
    else "NO_GO_POST_REINDEX_INVARIANT"
)
PY
    )"
    if [ "$probe_result" = "CHECK_WARNINGS_PRESENT" ]; then
        status="CHECK_WARNINGS_PRESENT"
        warnings=$((warnings + 1))
    elif [[ "$probe_result" == NO_GO_* ]]; then
        status="$probe_result"
    fi
fi

say "## Verdict"
say "status=$status warnings=$warnings"

if [ "$strict" = true ] && [[ "$status" == NO_GO_* ]]; then
    exit 1
fi
