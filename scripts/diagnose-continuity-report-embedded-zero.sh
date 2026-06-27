#!/usr/bin/env bash
# Diagnose: `agent-bridge continuity-report` reports embedded=0 while the store
# actually holds embeddings (observed on Mac, 2026-06-27; aio2 is unaffected).
#
# Root-cause hypothesis (see memory `mac_continuity_report_embedded_zero_diagnostic_20260627`):
# continuity-report opens `AB_BASELINE_DB` else `ab_store::default_db_path()`
# (macOS: ~/Library/Application Support/agent-bridge/state.db; Linux: ~/.local/share/...),
# then counts active rows with a non-null `embedding`. embedded=0 + an EMPTY backend
# list means that query saw an empty/different DB than the live one — a path/WAL
# mismatch, NOT a model filter. The report already carries a `db_path` field, so it
# is self-diagnosing. This script makes the comparison explicit.
#
# READ-ONLY: opens DBs with SQLite immutable URIs, never writes. Safe to run anywhere.
# Usage: scripts/diagnose-continuity-report-embedded-zero.sh
set -euo pipefail

say() { printf '%s\n' "$*"; }
hr()  { printf -- '----------------------------------------------------------------------\n'; }

# Portable helpers (macOS BSD coreutils vs GNU).
resolve() { # absolute, symlink-resolved path
    local p="$1"
    if command -v realpath >/dev/null 2>&1; then realpath "$p" 2>/dev/null && return; fi
    if command -v python3 >/dev/null 2>&1; then python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$p" 2>/dev/null && return; fi
    readlink "$p" 2>/dev/null || printf '%s' "$p"
}
inode() { stat -f %i "$1" 2>/dev/null || stat -c %i "$1" 2>/dev/null || echo '?'; }

# active rows carrying a non-null embedding, grouped by backend — approximates
# ab_bridge::continuity::build_report's query. Opens read-only + immutable so it
# never creates -wal/-shm sidecars on the snapshot.
sql_embed_count() { # $1 = db path
    local db="$1"
    command -v sqlite3 >/dev/null 2>&1 || { echo "(sqlite3 not installed — install or inspect manually)"; return; }
    [ -f "$db" ] || { echo "(no such file)"; return; }
    sqlite3 "file:${db}?mode=ro&immutable=1" \
        "SELECT COALESCE(embedding_backend,'<null>') AS b, COUNT(*) \
         FROM memories WHERE status='active' AND embedding IS NOT NULL \
         GROUP BY b ORDER BY 2 DESC;" 2>/dev/null \
      || echo "(query failed — locked/encrypted/incompatible?)"
}

# --- locate the agent-bridge binary (wrapper preferred so env injection applies) ---
AB=""
for c in agent-bridge "$HOME/.local/bin/agent-bridge"; do
    command -v "$c" >/dev/null 2>&1 && { AB="$c"; break; }
done
[ -n "$AB" ] || { say "ERROR: agent-bridge not found on PATH or ~/.local/bin"; exit 1; }

hr; say "1) What continuity-report SEES (its own --json)"; hr
JSON="$("$AB" continuity-report --json 2>/dev/null || true)"
if [ -z "$JSON" ]; then say "(continuity-report --json produced no output)"; fi
# Field extraction: python3 if present, else grep/sed (portable, tolerant).
get() { # $1 = json key
    if command -v python3 >/dev/null 2>&1; then
        printf '%s' "$JSON" | python3 -c 'import sys,json
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
v=d.get(sys.argv[1])
print(v if v is not None else "")' "$1" 2>/dev/null
    else
        printf '%s' "$JSON" | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*(\"[^\"]*\"|[0-9]+)" | head -1 | sed -E 's/.*:[[:space:]]*//; s/^"//; s/"$//'
    fi
}
REPORT_DB="$(get db_path)"
say "  report db_path     : ${REPORT_DB:-<unparsed>}"
say "  report embedded    : $(get embedded)"
say "  report dominant    : $(get dominant_backend)"
say "  AB_BASELINE_DB env : ${AB_BASELINE_DB:-<unset>}"

hr; say "2) Candidate LIVE DBs on this host (resolved + ground-truth embedded count)"; hr
CANDS=(
    "$HOME/Library/Application Support/agent-bridge/state.db"   # macOS default
    "$HOME/.local/share/agent-bridge/state.db"                  # Linux/XDG default + Mac symlink
)
[ -n "${AB_BASELINE_DB:-}" ] && CANDS+=("$AB_BASELINE_DB")
[ -n "$REPORT_DB" ] && CANDS+=("$REPORT_DB")
seen=""
for db in "${CANDS[@]}"; do
    [ -e "$db" ] || { say "  [missing] $db"; continue; }
    r="$(resolve "$db")"; ino="$(inode "$r")"
    case " $seen " in *" $ino "*) continue ;; esac    # de-dupe by inode
    seen="$seen $ino"
    say "  path   : $db"
    say "    → real: $r  (inode $ino)"
    say "    → -wal present: $( [ -f "${r}-wal" ] && echo yes || echo no )"
    say "    → active embedded by backend:"
    sql_embed_count "$r" | sed 's/^/        /'
done

hr; say "3) VERDICT"; hr
if [ -n "$REPORT_DB" ] && [ -e "$REPORT_DB" ]; then
    rino="$(inode "$(resolve "$REPORT_DB")")"
    live=""
    for db in "$HOME/Library/Application Support/agent-bridge/state.db" "$HOME/.local/share/agent-bridge/state.db"; do
        [ -e "$db" ] || continue
        cnt="$(sql_embed_count "$(resolve "$db")" | awk -F'|' '{s+=$2} END{print s+0}')"
        [ "${cnt:-0}" -gt 0 ] && live="$db ($cnt embedded, inode $(inode "$(resolve "$db")"))"
    done
    if [ -n "$live" ]; then
        lino="$(inode "$(resolve "${live%% *}")")"
        if [ "$rino" = "$lino" ]; then
            say "  Report opens the SAME file as the live data (inode $rino) but reports embedded=0."
            say "  → NOT a path bug. Suspect WAL/connection: check journal_mode, an uncheckpointed"
            say "    -wal the read-only/immutable open can't see, or a build_report query mismatch."
        else
            say "  MISMATCH: report opened inode $rino, but live embeddings are in: $live."
            say "  → PATH bug. Fix: reconcile default_db_path()/AB_BASELINE_DB with the daemon's DB"
            say "    (likely a stale ~/.local/share symlink or an AB_BASELINE_DB override)."
        fi
    else
        say "  Could not find any candidate DB with embeddings via sqlite3 (install sqlite3?)."
        say "  Compare 'report db_path' above against where the daemon actually writes."
    fi
else
    say "  continuity-report did not expose a db_path — update/redeploy the binary, or inspect manually."
fi
