#!/usr/bin/env bash
# Safe, race-resistant deploy of the agent-bridge MCP binary to
# ~/.local/bin/agent-bridge.real (the file the env-injection wrapper exec's).
#
# WHY THIS EXISTS
# ~/.local/bin/agent-bridge.real is a SINGLE shared deploy point. When two lanes
# each build from their own (possibly stale) branch and `cp` over it, the later
# deploy silently clobbers the earlier one's capabilities. 2026-06-03: a
# stale-master avatar/tts build overwrote a freshly-deployed item-3 binary,
# dropping item-3 from live while master source was fine (source-right /
# live-wrong). See lesson_deploy_race_stale_branch_binary_clobber_20260603.
#
# This script enforces the discipline that prevents that:
#   1. build from the LATEST origin/master (the superset of every merged lane),
#      never a stale branch;
#   2. anti-regression gate: the new binary must still contain every lane
#      feature-marker the CURRENTLY-deployed binary has (catches a stale build);
#   3. back up the current .real before overwriting (so a clobber is recoverable
#      — the clobbering lane on 2026-06-03 did NOT back ours up);
#   4. never touch the wrapper (only .real);
#   5. remind to /mcp reconnect (a running MCP server keeps the old binary).
#
# Companion to scripts/wrapper/install.sh (which installs the WRAPPER; this
# installs the BINARY). Honors the same env vars.
#
# Usage:
#   scripts/deploy_from_master.sh              # build latest master, gate, backup, deploy
#   scripts/deploy_from_master.sh --dry-run    # build + gate + show plan, but no backup/cp
#   scripts/deploy_from_master.sh --yes        # skip the interactive confirm
#   scripts/deploy_from_master.sh --use-binary PATH   # skip build; deploy PATH (still gated+backed up)
#                                                     # (provenance NOT verified — prints a warning)
#
# Env:
#   AGENT_BRIDGE_INSTALL_DIR   install dir (default ~/.local/bin)
#   AGENT_BRIDGE_REAL_BIN      real binary path (default $INSTALL_DIR/agent-bridge.real)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

INSTALL_DIR="${AGENT_BRIDGE_INSTALL_DIR:-$HOME/.local/bin}"
REAL_PATH="${AGENT_BRIDGE_REAL_BIN:-$INSTALL_DIR/agent-bridge.real}"
WRAPPER_PATH="$INSTALL_DIR/agent-bridge"

# Lane feature-markers. The gate asserts: every marker present in the CURRENT
# deployed binary is also present in the NEW one (new may add more — superset OK).
# Add a marker when a lane ships a distinctive capability string.
SENTINELS=(
    "desktop_steer.py"      # steer control plane / cross-process injection (item 3)
    "desktop_action.py"     # computer-use: coordinate action
    "desktop_invoke.py"     # computer-use: AT-SPI semantic invoke
    "desktop_confirm"       # host-confirm phase-2 executor
    "avatar_renderer"       # linux avatar renderer backend
    "present_voice"         # voice embodiment (ab-tts/Kokoro)
    "browser_navigate"      # browser CDP surface
    "memory_save"           # core memory
    "forum_post"            # core forum
)

DRY_RUN=0
ASSUME_YES=0
USE_BINARY=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --use-binary) shift; USE_BINARY="${1:-}";;
        -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
    shift
done

say()  { printf '%s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# The anti-regression gate depends on `strings` (binutils). If it is missing,
# markers_in would return EMPTY for every binary and the gate would falsely pass
# ("superset" of nothing) — deploying completely unguarded. Fail closed instead.
command -v strings >/dev/null 2>&1 || die "strings (binutils) is required for the regression gate; install binutils"

# pipe-free ELF check (avoids `head | grep -q` SIGPIPE-under-pipefail flake)
is_elf() {
    local magic
    magic="$(head -c4 "$1" 2>/dev/null)" || return 1
    [ "$magic" = $'\x7fELF' ]
}

# markers present in a binary (intersection with SENTINELS), one per line.
# strings is dumped to a temp file and grep reads the FILE directly — never
# `strings | grep -q`, which under `set -o pipefail` reports failure when grep -q
# closes the pipe early and strings dies of SIGPIPE (the original gate's bug:
# every marker read as "absent", so a stale-build regression sailed through).
markers_in() {
    local bin="$1" m tmp
    tmp="$(mktemp)"
    strings -a "$bin" 2>/dev/null > "$tmp" || true
    for m in "${SENTINELS[@]}"; do
        grep -qF -- "$m" "$tmp" && printf '%s\n' "$m"
    done
    rm -f "$tmp"
}

CLEANUP_WT=""
cleanup() { [ -n "$CLEANUP_WT" ] && git -C "$REPO" worktree remove --force "$CLEANUP_WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# ---- 1. obtain the NEW binary (build from latest master, or --use-binary) ----
NEW_BIN=""
PROVENANCE=""
if [ -n "$USE_BINARY" ]; then
    [ -f "$USE_BINARY" ] || die "--use-binary path not found: $USE_BINARY"
    is_elf "$USE_BINARY" || die "--use-binary is not an ELF binary: $USE_BINARY"
    NEW_BIN="$USE_BINARY"
    PROVENANCE="--use-binary $USE_BINARY (provenance NOT verified)"
    say "WARNING: --use-binary skips the build-from-master guarantee."
    say "         Only the regression gate + backup protect this deploy."
else
    say ">> fetching origin/master ..."
    git -C "$REPO" fetch origin --quiet
    MASTER_SHA="$(git -C "$REPO" rev-parse origin/master)"
    PROVENANCE="origin/master @ ${MASTER_SHA:0:7}"
    # Build in a worktree placed as a SIBLING of the repo so the cross-repo path
    # dep (crates/seed-bridge -> ../../../AiOT/rust/seed_neuron) resolves natively
    # without symlinks. AiOT is always a sibling of the repo on every node.
    # Unique per-run (PID-suffixed) so two concurrent deploys don't rm -rf / build
    # into the SAME staging worktree and corrupt each other — the build dir must
    # stay a sibling of the repo (and thus of AiOT) for ../AiOT to resolve.
    BUILD_DIR="$(dirname "$REPO")/.ab-deploy-build.$$"
    git -C "$REPO" worktree remove --force "$BUILD_DIR" >/dev/null 2>&1 || true
    rm -rf "$BUILD_DIR" 2>/dev/null || true
    say ">> creating build worktree at $BUILD_DIR (detached @ ${MASTER_SHA:0:7})"
    git -C "$REPO" worktree add --detach "$BUILD_DIR" "$MASTER_SHA" >/dev/null
    CLEANUP_WT="$BUILD_DIR"
    git config --global --add safe.directory "$BUILD_DIR" >/dev/null 2>&1 || true
    say ">> cargo build --release --bin agent-bridge (this takes several minutes) ..."
    ( cd "$BUILD_DIR" && CARGO_TERM_COLOR=never cargo build --release --bin agent-bridge )
    NEW_BIN="$BUILD_DIR/target/release/agent-bridge"
    [ -x "$NEW_BIN" ] || die "build produced no binary at $NEW_BIN"
fi

is_elf "$NEW_BIN" || die "new binary is not ELF: $NEW_BIN"

# ---- 2. anti-regression gate vs the currently-deployed binary ----
say
say "=== feature gate (new binary must not drop any current capability) ==="
new_markers="$(markers_in "$NEW_BIN")"
if [ -f "$REAL_PATH" ]; then
    cur_markers="$(markers_in "$REAL_PATH")"
    # markers present in current but missing in new = regression
    missing="$(comm -23 <(printf '%s\n' "$cur_markers" | sort -u) <(printf '%s\n' "$new_markers" | sort -u))"
    if [ -n "$missing" ]; then
        say "current deployed binary has these markers the NEW binary LACKS:"
        printf '  - %s\n' $missing
        die "regression detected — new binary drops a capability the live one has.
       This usually means it was built from a STALE branch, not latest master.
       Refusing to clobber. Rebuild from origin/master."
    fi
    say "OK: new binary is a superset of the current deployed binary's markers."
else
    say "(no current $REAL_PATH — first install, nothing to regress against)"
fi
say "new binary markers present:"; printf '  + %s\n' $new_markers

# ---- 3. plan summary ----
new_size="$(stat -c %s "$NEW_BIN" 2>/dev/null || stat -f %z "$NEW_BIN")"
cur_size="$( [ -f "$REAL_PATH" ] && (stat -c %s "$REAL_PATH" 2>/dev/null || stat -f %z "$REAL_PATH") || echo 0 )"
say
say "=== deploy plan ==="
say "  source     : $PROVENANCE"
say "  new binary : $NEW_BIN ($new_size bytes)"
say "  target     : $REAL_PATH (current $cur_size bytes)"
say "  wrapper    : $WRAPPER_PATH (left untouched)"

if [ "$DRY_RUN" -eq 1 ]; then
    say
    say "[dry-run] gate passed; no backup/cp performed. Re-run without --dry-run to deploy."
    exit 0
fi

# ---- 4. confirm ----
if [ "$ASSUME_YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
        die "non-interactive stdin and no --yes given: re-run with --yes to deploy"
    fi
    printf 'Proceed with deploy? [y/N] '
    read -r ans || ans=""
    case "$ans" in y|Y|yes|YES) ;; *) say "aborted."; exit 0 ;; esac
fi

# ---- 5. backup current, then deploy ----
if [ -f "$REAL_PATH" ]; then
    ts="$(date +%Y%m%dT%H%M%S)"
    # NB: ${MASTER_SHA:0:7} must not be expanded on the --use-binary path, where
    # MASTER_SHA is unset and `set -u` would abort here (before the backup+deploy).
    if [ -n "$USE_BINARY" ]; then tag="usebin"; else tag="${MASTER_SHA:0:7}"; fi
    bak="$REAL_PATH.bak-deploy-$tag-$ts"
    cp "$REAL_PATH" "$bak"
    say ">> backed up current binary -> $bak"
fi

cp -f "$NEW_BIN" "$REAL_PATH"
say ">> deployed -> $REAL_PATH"

# ---- 6. post-deploy verification ----
say
say "=== post-deploy verification ==="
dep_size="$(stat -c %s "$REAL_PATH" 2>/dev/null || stat -f %z "$REAL_PATH")"
[ "$dep_size" = "$new_size" ] || die "deployed size $dep_size != built $new_size (copy failed?)"
# unquoted on purpose: markers are one-per-line + whitespace-free, so word-splitting
# gives one printf arg per marker (each gets its own "  + " prefix).
# shellcheck disable=SC2046,SC2086
say "deployed markers:"; printf '  + %s\n' $(markers_in "$REAL_PATH")

# Reconnect surface: a deployed-over .real shows as "(deleted)" in /proc/PID/exe
# for any MCP server still mapping the OLD inode. Report the count so the operator
# knows which sessions still need /mcp reconnect. Read-only — never kills anything.
stale=0; fresh=0
for pid in $(pgrep -f 'agent-bridge.*mcp' 2>/dev/null || true); do
    exe="$(readlink "/proc/$pid/exe" 2>/dev/null || true)"
    case "$exe" in
        *"(deleted)") stale=$((stale + 1)) ;;
        */agent-bridge.real) fresh=$((fresh + 1)) ;;
    esac
done

say
say "DONE. The running MCP server still holds the OLD binary —"
say "      run /mcp reconnect (per CC session) to activate the new one."
if [ "$stale" -gt 0 ]; then
    say "      reconnect surface: $stale running MCP server(s) still on the OLD binary"
    say "      ($fresh already on the new one) — each is a CC/Codex/Cursor session that"
    say "      needs its own /mcp reconnect to pick up this deploy."
fi
if [ -n "${bak:-}" ]; then say "      rollback: cp '$bak' '$REAL_PATH' && /mcp reconnect"; fi
# Explicit success: the final command above must not leave a nonzero status (a
# bare `[ -n "" ] && …` on a first install returns 1 and, as the last command
# under `set -e`, would falsely report deploy failure to callers checking $?).
exit 0
