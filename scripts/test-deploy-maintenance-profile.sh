#!/usr/bin/env bash
# Maintenance may omit R9, but must preserve the explicitly pinned active
# binary's capabilities and refuse a changed baseline before publication.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-maintenance-profile.XXXXXX")"
TEST_ROOT="$(cd -P "$TEST_ROOT" && pwd -P)"
trap 'rm -rf -- "$TEST_ROOT"' EXIT
mkdir -p "$TEST_ROOT/source/config" "$TEST_ROOT/source/docs/reports/tts-comparison" \
    "$TEST_ROOT/home" "$TEST_ROOT/bin"
cp -a "$SCRIPT_DIR" "$TEST_ROOT/source/scripts"
cp "$SCRIPT_DIR/../config/omnivoice-canary.json" "$TEST_ROOT/source/config/"
cp "$SCRIPT_DIR/../docs/reports/tts-comparison/human-review-decision-owner-2026-08-15.json" \
    "$TEST_ROOT/source/docs/reports/tts-comparison/"
export HOME="$TEST_ROOT/home"
export AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1
export AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT="$TEST_ROOT"
export AGENT_BRIDGE_INSTALL_DIR="$TEST_ROOT/bin"
export AGENT_BRIDGE_DEPLOY_STATE_DIR="$TEST_ROOT/state"
export AGENT_BRIDGE_AUDIO_EMBODY_PATH="$TEST_ROOT/share/ab-tts/audio_embody.py"
export AGENT_BRIDGE_RUNTIME_ASSET_DIR="$TEST_ROOT/lib/agent-bridge/scripts"
export AGENT_BRIDGE_MAINTENANCE_BASELINE="$TEST_ROOT/active.real"
unset AGENT_BRIDGE_DEPLOY_PROFILE
markers='agent_bridge.app_control.operation_preflight.v0 agent_bridge.app_control.track_settlement.v0 agent_bridge.app_control.wrapper_contract.v1 agent_bridge.avatar.native_linux.v1'
for kind in active missing; do
    extra=''
    [ "$kind" != active ] || extra=present_voice
    printf '#include <stdio.h>\nint main(void) { puts("%s %s"); return 0; }\n' \
        "$markers" "$extra" > "$TEST_ROOT/$kind.c"
    "$(command -v cc)" "$TEST_ROOT/$kind.c" -o "$TEST_ROOT/$kind.real"
done
sha() {
    if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}
export AGENT_BRIDGE_MAINTENANCE_BASELINE_SHA256="$(sha "$TEST_ROOT/active.real")"
publisher="$TEST_ROOT/source/scripts/deploy_from_master.sh"
reject() {
    local expected="$1"; shift
    if "$@" > "$TEST_ROOT/rejected.log" 2>&1; then
        printf 'FAIL: accepted %s\n' "$expected" >&2; exit 1
    fi
    grep -q "$expected" "$TEST_ROOT/rejected.log" || {
        cat "$TEST_ROOT/rejected.log" >&2; exit 1;
    }
    [ ! -e "$TEST_ROOT/bin/agent-bridge.real" ]
    [ ! -e "$AGENT_BRIDGE_AUDIO_EMBODY_PATH" ]
}
reject 'active maintenance baseline changed' env \
    AGENT_BRIDGE_MAINTENANCE_BASELINE_SHA256="$(printf '%064d' 0)" \
    "$publisher" --use-binary "$TEST_ROOT/active.real" --yes
reject 'present_voice' "$publisher" --use-binary "$TEST_ROOT/missing.real" --yes
# A rejected transaction must not contaminate the next independent fixture.
rm -rf -- "$TEST_ROOT/state"
reject 'agent_bridge.workload_receipt_commit.v1' env AGENT_BRIDGE_DEPLOY_PROFILE=r9 \
    "$publisher" --use-binary "$TEST_ROOT/active.real" --yes
rm -rf -- "$TEST_ROOT/state"
reject 'must be maintenance or r9' env AGENT_BRIDGE_DEPLOY_PROFILE=typo \
    "$publisher" --use-binary "$TEST_ROOT/active.real" --yes
"$publisher" --use-binary "$TEST_ROOT/active.real" --yes > "$TEST_ROOT/accepted.log" 2>&1 || {
    cat "$TEST_ROOT/accepted.log" >&2; exit 1;
}
if [ "$(uname -s)" = Darwin ]; then
    # The publisher signs under a unique staging name. Reproduce that exact
    # identifier on a disposable expected copy before comparing all bytes.
    cp "$TEST_ROOT/active.real" "$TEST_ROOT/expected.real"
    codesign --verify --strict "$TEST_ROOT/bin/agent-bridge.real"
    signed_id="$(codesign -d --verbose=2 "$TEST_ROOT/bin/agent-bridge.real" 2>&1 | sed -n 's/^Identifier=//p')"
    [ -n "$signed_id" ]
    codesign --force --sign - --identifier "$signed_id" "$TEST_ROOT/expected.real"
    cmp "$TEST_ROOT/expected.real" "$TEST_ROOT/bin/agent-bridge.real"
else
    cmp "$TEST_ROOT/active.real" "$TEST_ROOT/bin/agent-bridge.real"
fi
printf 'PASS: default maintenance omits R9 while enforcing active-baseline identity and capability parity\n'
