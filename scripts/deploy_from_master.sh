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
#   1. build from the LATEST selected remote/master (the superset of every merged lane),
#      never a stale branch;
#   2. re-fetch after the potentially long release build and refuse to deploy
#      when the selected remote/master advanced during that build;
#   3. anti-regression gate: the new binary must still contain every lane
#      feature-marker the CURRENTLY-deployed binary has (catches a stale build);
#   4. back up the current .real before overwriting (so a clobber is recoverable
#      — the clobbering lane on 2026-06-03 did NOT back ours up);
#   5. install repository-matched Python runtime assets at a stable path (the
#      release build worktree is disposable and cannot be a runtime dependency);
#   6. never touch the wrapper (only .real);
#   7. remind to /mcp reconnect (a running MCP server keeps the old binary).
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
#   AGENT_BRIDGE_AUDIO_EMBODY_PATH installed adapter path
#                              (default ~/.local/share/ab-tts/audio_embody.py)
#   AGENT_BRIDGE_RUNTIME_ASSET_DIR stable script directory
#                              (default ~/.local/lib/agent-bridge/scripts)
#   CARGO_TARGET_DIR           build target root (default ~/.cache/agent-bridge-deploy-target,
#                              with one child per master SHA to prevent cross-ref artifact reuse;
#                              kept OFF /Data so ntfs-3g pressure cannot ENOSPC the release build)
#   AGENT_BRIDGE_DEPLOY_REMOTE git remote containing authoritative master
#                              (default: origin; use github after GitHub migration)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

INSTALL_DIR="${AGENT_BRIDGE_INSTALL_DIR:-$HOME/.local/bin}"
REAL_PATH="${AGENT_BRIDGE_REAL_BIN:-$INSTALL_DIR/agent-bridge.real}"
WRAPPER_PATH="$INSTALL_DIR/agent-bridge"
ASSET_SOURCE_ROOT="$REPO"
ADAPTER_SOURCE="$ASSET_SOURCE_ROOT/scripts/audio_embody.py"
ADAPTER_PATH="${AGENT_BRIDGE_AUDIO_EMBODY_PATH:-$HOME/.local/share/ab-tts/audio_embody.py}"
AUDIO_ADAPTER_COMPANIONS=(
    omnivoice_mac_remote_synth.py
    omnivoice_onnx_bundle_synth.py
    omnivoice_onnx_official_decode.py
    omnivoice_tts_synth.py
    qwen3_tts_rust_gate.py
    qwen3_tts_synth.py
    tts_canary_router.py
)
RUNTIME_ASSET_DIR="${AGENT_BRIDGE_RUNTIME_ASSET_DIR:-$HOME/.local/lib/agent-bridge/scripts}"
RUNTIME_ASSETS=(
    app_control.py
    desktop_action.py
    desktop_confirm_store.py
    desktop_grant.py
    desktop_invoke.py
    desktop_snapshot.py
    desktop_steer.py
    desktop_verify.py
    vision_grounding_ocr.py
)
DEPLOY_REMOTE="${AGENT_BRIDGE_DEPLOY_REMOTE:-origin}"
MASTER_REF="refs/remotes/$DEPLOY_REMOTE/master"

# Lane feature-markers. The gate asserts: every marker present in the CURRENT
# deployed binary is also present in the NEW one (new may add more — superset OK).
# Add a marker when a lane ships a distinctive capability string.
SENTINELS=(
    "app_control.py"        # protocol-first application control router
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

# pipe-free native-executable check — ELF on Linux, Mach-O on macOS.
# (avoids `head | grep -q` SIGPIPE-under-pipefail flake). The byte magics below
# contain no NUL/newline, so they survive `$(...)` capture + `[ = ]` byte compare.
is_native_exe() {
    local magic
    magic="$(head -c4 "$1" 2>/dev/null)" || return 1
    [ "$magic" = $'\x7fELF' ]           && return 0   # ELF (Linux)
    [ "$magic" = $'\xcf\xfa\xed\xfe' ]  && return 0   # Mach-O 64-bit thin (macOS arm64/x86_64)
    [ "$magic" = $'\xce\xfa\xed\xfe' ]  && return 0   # Mach-O 32-bit thin
    [ "$magic" = $'\xca\xfe\xba\xbe' ]  && return 0   # Mach-O universal (fat, big-endian)
    [ "$magic" = $'\xbe\xba\xfe\xca' ]  && return 0   # Mach-O universal (fat, little-endian)
    return 1
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
CLEANUP_RUNTIME_STAGE=""
cleanup() {
    [ -n "$CLEANUP_WT" ] && git -C "$REPO" worktree remove --force "$CLEANUP_WT" >/dev/null 2>&1 || true
    [ -n "$CLEANUP_RUNTIME_STAGE" ] && rm -rf "$CLEANUP_RUNTIME_STAGE" 2>/dev/null || true
}
trap cleanup EXIT

# ---- 1. obtain the NEW binary (build from latest master, or --use-binary) ----
NEW_BIN=""
PROVENANCE=""
if [ -n "$USE_BINARY" ]; then
    [ -f "$USE_BINARY" ] || die "--use-binary path not found: $USE_BINARY"
    is_native_exe "$USE_BINARY" || die "--use-binary is not a native executable (ELF/Mach-O): $USE_BINARY"
    NEW_BIN="$USE_BINARY"
    PROVENANCE="--use-binary $USE_BINARY (provenance NOT verified)"
    say "WARNING: --use-binary skips the build-from-master guarantee."
    say "         Only the regression gate + backup protect this deploy."
else
    git -C "$REPO" remote get-url "$DEPLOY_REMOTE" >/dev/null 2>&1 ||
        die "configured deploy remote does not exist: $DEPLOY_REMOTE"
    say ">> fetching $DEPLOY_REMOTE/master ..."
    git -C "$REPO" fetch "$DEPLOY_REMOTE" "+refs/heads/master:$MASTER_REF" --quiet
    MASTER_SHA="$(git -C "$REPO" rev-parse --verify "$MASTER_REF")"
    PROVENANCE="$DEPLOY_REMOTE/master @ ${MASTER_SHA:0:7}"
    # Build in a worktree placed as a SIBLING of the repo so the cross-repo path
    # dep (crates/seed-bridge -> ../../../AiOT/rust/seed_neuron) resolves natively
    # without symlinks. AiOT is always a sibling of the repo on every node.
    # Reclaim staging worktrees leaked by a PRIOR run that was hard-killed (OOM /
    # SIGKILL mid-build, before its EXIT trap could fire). PID-unique names mean the
    # next run no longer collides with a stale dir, but also no longer reclaims it —
    # so sweep dead-PID siblings here (skip any whose PID is still alive to stay
    # concurrency-safe), then prune stale worktree registrations.
    for d in "$(dirname "$REPO")"/.ab-deploy-build.*; do
        [ -e "$d" ] || continue
        pid="${d##*.}"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then continue; fi
        git -C "$REPO" worktree remove --force "$d" >/dev/null 2>&1 || true
        rm -rf "$d" 2>/dev/null || true
    done
    git -C "$REPO" worktree prune >/dev/null 2>&1 || true
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
    # Build target dir defaults to /home (ext4, ~TB free), NOT the build
    # worktree's own target/ under $(dirname "$REPO"). The worktree itself must
    # stay a SIBLING of REPO so the ../AiOT path dep resolves (above) — but its
    # target/ would then land on /Data, an ntfs-3g volume that ~50 sibling
    # worktrees' target/ dirs fill to 100%, ENOSPC-ing the release build
    # mid-link (hit twice on 2026-06-19 by two agents; both had to set
    # CARGO_TARGET_DIR=/home by hand to recover). Redirecting it off /Data is the
    # root fix. A SHA-scoped path prevents concurrent builds from different
    # worktrees from reusing a binary compiled from another ref. Cargo's target
    # lock serializes writes, but does not prove final executable provenance.
    # Honor an operator-set CARGO_TARGET_DIR as the root of this scoped path.
    # See lesson_data_fills_from_worktree_targets_deploy_builds_there_20260619.
    DEPLOY_TARGET_ROOT="${CARGO_TARGET_DIR:-$HOME/.cache/agent-bridge-deploy-target}"
    DEPLOY_TARGET_DIR="$DEPLOY_TARGET_ROOT/$MASTER_SHA"
    mkdir -p "$DEPLOY_TARGET_DIR" || die "cannot create build target dir $DEPLOY_TARGET_DIR"
    say ">> cargo build --release --bin agent-bridge"
    say "   (target dir: $DEPLOY_TARGET_DIR — off /Data; takes several minutes) ..."
    ( cd "$BUILD_DIR" && CARGO_TARGET_DIR="$DEPLOY_TARGET_DIR" CARGO_TERM_COLOR=never cargo build --release --bin agent-bridge )
    NEW_BIN="$DEPLOY_TARGET_DIR/release/agent-bridge"
    [ -x "$NEW_BIN" ] || die "build produced no binary at $NEW_BIN"
    BUILT_VERSION="$("$NEW_BIN" --version 2>&1)" ||
        die "built binary does not execute for provenance verification"
    case "$BUILT_VERSION" in
        *"${MASTER_SHA:0:12}"*) ;;
        *) die "built binary provenance mismatch: expected ${MASTER_SHA:0:12}, got: $BUILT_VERSION" ;;
    esac
    say "OK: built binary reports master ${MASTER_SHA:0:12}."
fi

# A normal deploy must install scripts from the exact detached master snapshot
# that produced NEW_BIN, never from the caller's possibly stale/dirty worktree.
# Otherwise two same-SHA deploys launched from different worktrees can end with
# the correct binary but whichever caller's runtime assets happened to run last.
# --use-binary has no verified source snapshot, so it deliberately retains the
# documented repository-matched behavior and uses the invoking checkout.
if [ -z "$USE_BINARY" ]; then
    ASSET_SOURCE_ROOT="$BUILD_DIR"
fi
ADAPTER_SOURCE="$ASSET_SOURCE_ROOT/scripts/audio_embody.py"
[ -f "$ADAPTER_SOURCE" ] || die "deploy-source audio adapter missing: $ADAPTER_SOURCE"
for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
    [ -f "$ASSET_SOURCE_ROOT/scripts/$asset" ] ||
        die "deploy-source audio companion missing: $ASSET_SOURCE_ROOT/scripts/$asset"
done
for asset in "${RUNTIME_ASSETS[@]}"; do
    [ -f "$ASSET_SOURCE_ROOT/scripts/$asset" ] ||
        die "deploy-source runtime asset missing: $ASSET_SOURCE_ROOT/scripts/$asset"
done

is_native_exe "$NEW_BIN" || die "new binary is not a native executable (ELF/Mach-O): $NEW_BIN"

# ---- 2. post-build master recheck ----
# A release build can take tens of minutes. Another lane may merge during that
# window, making this artifact stale even though it came from remote/master at
# build start. Re-check before the first live-state mutation (backup/copy).
if [ -z "$USE_BINARY" ]; then
    say ">> rechecking $DEPLOY_REMOTE/master after build ..."
    git -C "$REPO" fetch "$DEPLOY_REMOTE" "+refs/heads/master:$MASTER_REF" --quiet
    CURRENT_MASTER_SHA="$(git -C "$REPO" rev-parse --verify "$MASTER_REF")"
    if [ "$CURRENT_MASTER_SHA" != "$MASTER_SHA" ]; then
        die "$DEPLOY_REMOTE/master advanced during the release build (${MASTER_SHA:0:7} -> ${CURRENT_MASTER_SHA:0:7}); refusing to deploy a stale artifact before backup/copy. Re-run the deploy from the new master."
    fi
    say "OK: $DEPLOY_REMOTE/master is still ${MASTER_SHA:0:7}."
fi

# ---- 3. anti-regression gate vs the currently-deployed binary ----
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
       Refusing to clobber. Rebuild from the authoritative remote/master."
    fi
    say "OK: new binary is a superset of the current deployed binary's markers."
else
    say "(no current $REAL_PATH — first install, nothing to regress against)"
fi
say "new binary markers present:"; printf '  + %s\n' $new_markers

# ---- 4. plan summary ----
new_size="$(stat -c %s "$NEW_BIN" 2>/dev/null || stat -f %z "$NEW_BIN")"
cur_size="$( [ -f "$REAL_PATH" ] && (stat -c %s "$REAL_PATH" 2>/dev/null || stat -f %z "$REAL_PATH") || echo 0 )"
say
say "=== deploy plan ==="
say "  source     : $PROVENANCE"
say "  new binary : $NEW_BIN ($new_size bytes)"
say "  target     : $REAL_PATH (current $cur_size bytes)"
say "  wrapper    : $WRAPPER_PATH (left untouched)"
say "  adapter    : $ADAPTER_SOURCE -> $ADAPTER_PATH"
say "  companions : ${#AUDIO_ADAPTER_COMPANIONS[@]} audio scripts -> $(dirname "$ADAPTER_PATH")"
say "  runtime    : ${#RUNTIME_ASSETS[@]} scripts from $ASSET_SOURCE_ROOT -> $RUNTIME_ASSET_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
    say
    say "[dry-run] gate passed; no backup/cp performed. Re-run without --dry-run to deploy."
    exit 0
fi

# ---- 5. confirm ----
if [ "$ASSUME_YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
        die "non-interactive stdin and no --yes given: re-run with --yes to deploy"
    fi
    printf 'Proceed with deploy? [y/N] '
    read -r ans || ans=""
    case "$ans" in y|Y|yes|YES) ;; *) say "aborted."; exit 0 ;; esac
fi

# ---- 6. backup current, then deploy ----
if [ -f "$REAL_PATH" ]; then
    ts="$(date +%Y%m%dT%H%M%S)"
    # NB: ${MASTER_SHA:0:7} must not be expanded on the --use-binary path, where
    # MASTER_SHA is unset and `set -u` would abort here (before the backup+deploy).
    if [ -n "$USE_BINARY" ]; then tag="usebin"; else tag="${MASTER_SHA:0:7}"; fi
    bak="$REAL_PATH.bak-deploy-$tag-$ts"
    cp "$REAL_PATH" "$bak"
    say ">> backed up current binary -> $bak"
fi

# Install every repository-matched audio companion before activating the new
# adapter. A brief interruption can therefore leave the old adapter with extra
# compatible companions, never the new adapter with a missing sibling import.
adapter_dir="$(dirname "$ADAPTER_PATH")"
mkdir -p "$adapter_dir"
if [ -f "$ADAPTER_PATH" ]; then
    adapter_bak="$ADAPTER_PATH.bak-deploy-$(date +%Y%m%dT%H%M%S)"
    cp "$ADAPTER_PATH" "$adapter_bak"
    say ">> backed up current audio adapter -> $adapter_bak"
fi
for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
    companion_source="$ASSET_SOURCE_ROOT/scripts/$asset"
    companion_target="$adapter_dir/$asset"
    companion_stage="$companion_target.stage.$$"
    cp "$companion_source" "$companion_stage"
    chmod +x "$companion_stage"
    mv -f "$companion_stage" "$companion_target"
    cmp -s "$companion_source" "$companion_target" ||
        die "installed audio companion differs from repository source: $asset"
done
adapter_stage="$ADAPTER_PATH.stage.$$"
cp "$ADAPTER_SOURCE" "$adapter_stage"
chmod +x "$adapter_stage"
mv -f "$adapter_stage" "$ADAPTER_PATH"
cmp -s "$ADAPTER_SOURCE" "$ADAPTER_PATH" ||
    die "installed audio adapter differs from repository source"
say ">> deployed matched audio adapter -> $ADAPTER_PATH"
say ">> deployed matched audio companions -> $adapter_dir"

# Install script-backed MCP assets at a stable path. The release binary embeds
# its disposable build worktree in CARGO_MANIFEST_DIR, so compile-time fallback
# alone breaks as soon as the deploy cleanup removes that worktree. Stage the
# complete dependency set, then swap the directory as one repository-matched
# unit before installing the binary that resolves it.
mkdir -p "$(dirname "$RUNTIME_ASSET_DIR")"
runtime_stage="$RUNTIME_ASSET_DIR.stage.$$"
CLEANUP_RUNTIME_STAGE="$runtime_stage"
rm -rf "$runtime_stage"
mkdir -p "$runtime_stage"
for asset in "${RUNTIME_ASSETS[@]}"; do
    install -m 755 "$ASSET_SOURCE_ROOT/scripts/$asset" "$runtime_stage/$asset"
done
if [ -e "$RUNTIME_ASSET_DIR" ]; then
    runtime_bak="$RUNTIME_ASSET_DIR.bak-deploy-$(date +%Y%m%dT%H%M%S)"
    mv "$RUNTIME_ASSET_DIR" "$runtime_bak"
    if ! mv "$runtime_stage" "$RUNTIME_ASSET_DIR"; then
        mv "$runtime_bak" "$RUNTIME_ASSET_DIR" || true
        die "failed to activate staged runtime assets"
    fi
    say ">> backed up current runtime assets -> $runtime_bak"
else
    mv "$runtime_stage" "$RUNTIME_ASSET_DIR"
fi
CLEANUP_RUNTIME_STAGE=""
say ">> deployed matched runtime assets -> $RUNTIME_ASSET_DIR"

cp -f "$NEW_BIN" "$REAL_PATH"
say ">> deployed -> $REAL_PATH"
copied_size="$(stat -c %s "$REAL_PATH" 2>/dev/null || stat -f %z "$REAL_PATH")"
[ "$copied_size" = "$new_size" ] || die "deployed size $copied_size != built $new_size (copy failed?)"
if [ "$(uname -s)" = "Darwin" ]; then
    command -v codesign >/dev/null 2>&1 || die "codesign is required on macOS after copying the Mach-O binary"
    codesign --force --sign - "$REAL_PATH" >/dev/null
    say ">> ad-hoc signed macOS binary -> $REAL_PATH"
    new_size="$(stat -c %s "$REAL_PATH" 2>/dev/null || stat -f %z "$REAL_PATH")"
fi

# ---- 7. post-deploy verification ----
say
say "=== post-deploy verification ==="
dep_size="$(stat -c %s "$REAL_PATH" 2>/dev/null || stat -f %z "$REAL_PATH")"
[ "$dep_size" = "$new_size" ] || die "deployed size $dep_size != built $new_size (copy failed?)"
cmp -s "$ADAPTER_SOURCE" "$ADAPTER_PATH" ||
    die "post-deploy audio adapter parity check failed"
say "audio adapter parity: OK ($ADAPTER_PATH)"
for asset in "${AUDIO_ADAPTER_COMPANIONS[@]}"; do
    cmp -s "$ASSET_SOURCE_ROOT/scripts/$asset" "$adapter_dir/$asset" ||
        die "post-deploy audio companion parity check failed: $asset"
done
say "audio companion parity: OK (${#AUDIO_ADAPTER_COMPANIONS[@]} scripts in $adapter_dir)"
for asset in "${RUNTIME_ASSETS[@]}"; do
    cmp -s "$ASSET_SOURCE_ROOT/scripts/$asset" "$RUNTIME_ASSET_DIR/$asset" ||
        die "post-deploy runtime asset parity check failed: $asset"
done
say "runtime asset parity: OK (${#RUNTIME_ASSETS[@]} scripts in $RUNTIME_ASSET_DIR)"
# Parity alone is insufficient if a stale/partial asset set comes from a
# different checkout. Check the protocol router's shipped action contract too;
# this turns a later MCP `script_missing`/unknown-action failure into a deploy
# gate failure with an actionable message.
APP_CONTROL_RUNTIME="$RUNTIME_ASSET_DIR/app_control.py"
[ -f "$APP_CONTROL_RUNTIME" ] || die "post-deploy app_control asset missing: $APP_CONTROL_RUNTIME"
grep -q '"playlist_current"' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing playlist_current: $APP_CONTROL_RUNTIME"
grep -q '"playlist_activate"' "$APP_CONTROL_RUNTIME" ||
    die "post-deploy app_control contract missing playlist_activate: $APP_CONTROL_RUNTIME"
say "app_control action contract: OK (playlist_current, playlist_activate)"
# unquoted on purpose: markers are one-per-line + whitespace-free, so word-splitting
# gives one printf arg per marker (each gets its own "  + " prefix).
# shellcheck disable=SC2046,SC2086
say "deployed markers:"; printf '  + %s\n' $(markers_in "$REAL_PATH")

# Reconnect surface: a deployed-over .real shows as "(deleted)" in /proc/PID/exe
# for any MCP server still mapping the OLD inode. Report the count so the operator
# knows which sessions still need /mcp reconnect. Read-only — never kills anything.
stale=0; fresh=0; stale_list=""
for pid in $(pgrep -f 'agent-bridge.*mcp' 2>/dev/null || true); do
    exe="$(readlink "/proc/$pid/exe" 2>/dev/null || true)"
    case "$exe" in
        *"(deleted)")
            stale=$((stale + 1))
            # Identify the owning client so the operator knows exactly which session
            # to /mcp reconnect: parent process (CC/Codex/Cursor) + the server's cwd
            # (the project it serves). /proc only — this whole block is Linux-only;
            # on macOS readlink /proc returns nothing so stale stays 0 (no-op).
            ppid="$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null || echo '?')"
            pcomm="$(tr -d '\0' < "/proc/$ppid/comm" 2>/dev/null || echo '?')"
            cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || echo '?')"
            stale_list="${stale_list}
        - pid $pid  (client: ${ppid}/${pcomm}, cwd: ${cwd})"
            ;;
        */agent-bridge.real) fresh=$((fresh + 1)) ;;
    esac
done

say
say "DONE. The running MCP server still holds the OLD binary —"
say "      run /mcp reconnect (per CC session) to activate the new one."
if [ "$stale" -gt 0 ]; then
    say "      reconnect surface: $stale running MCP server(s) still on the OLD binary"
    say "      ($fresh already on the new one) — each needs its own /mcp reconnect"
    say "      (until reconnected, agent-bridge doctor reports warns>=1 and the strict"
    say "      warns=0 pre-write gate stays blocked). Servers to reconnect:"
    printf '%s\n' "$stale_list"
fi
if [ -n "${bak:-}" ]; then say "      rollback: cp '$bak' '$REAL_PATH' && /mcp reconnect"; fi
if [ -n "${adapter_bak:-}" ]; then say "      adapter rollback: cp '$adapter_bak' '$ADAPTER_PATH'"; fi
if [ -n "${runtime_bak:-}" ]; then say "      runtime rollback: mv '$RUNTIME_ASSET_DIR' '${RUNTIME_ASSET_DIR}.failed' && mv '$runtime_bak' '$RUNTIME_ASSET_DIR'"; fi
# Explicit success: the final command above must not leave a nonzero status (a
# bare `[ -n "" ] && …` on a first install returns 1 and, as the last command
# under `set -e`, would falsely report deploy failure to callers checking $?).
exit 0
