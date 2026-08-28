#!/usr/bin/env bash
# Isolated contract tests for deploy_from_master.sh publisher lease v0.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY="$SCRIPT_DIR/deploy_from_master.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-publisher-lease-v0.XXXXXX")"
TEST_ROOT="$(cd -P "$TEST_ROOT" && pwd -P)"
TEST_TEMP_BASE="$(cd -P "${TMPDIR:-/tmp}" && pwd -P)"
DESCENDANT_PIDS=""

cleanup() {
    local descendant_pid
    for descendant_pid in $DESCENDANT_PIDS; do
        kill -9 "$descendant_pid" 2>/dev/null || true
    done
    case "$TEST_ROOT" in
        "$TEST_TEMP_BASE"/ab-publisher-lease-v0.*)
            find "$TEST_ROOT" -mindepth 1 -depth -delete 2>/dev/null || true
            rmdir "$TEST_ROOT" 2>/dev/null || true
            ;;
    esac
}
trap cleanup EXIT

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

sha256_fixture() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{ print $1 }'
    else
        sha256sum "$1" | awk '{ print $1 }'
    fi
}

mutation_count() {
    if [ -f "$1/mutations.log" ]; then
        wc -l < "$1/mutations.log" | tr -d ' '
    else
        printf '%s\n' 0
    fi
}

receipt_field_count() {
    local root="$1" key="$2" value="$3" file count=0
    for file in "$root/state/receipts/"*.meta; do
        [ -f "$file" ] || continue
        if grep -qx "$key=$value" "$file"; then
            count=$((count + 1))
        fi
    done
    printf '%s\n' "$count"
}

quarantine_field_count() {
    local root="$1" key="$2" value="$3" suffix="$4" file count=0
    for file in "$root/state/quarantine/"*"$suffix"; do
        [ -f "$file" ] || continue
        if grep -qx "$key=$value" "$file"; then
            count=$((count + 1))
        fi
    done
    printf '%s\n' "$count"
}

wait_kernel_lock_released() {
    local root="$1" attempt=0
    while [ "$attempt" -lt 200 ]; do
        if [ "$(/usr/bin/uname -s 2>/dev/null || uname -s)" = Darwin ]; then
            /usr/bin/lockf -k -s -t 0 "$root/state/publisher.kernel.lock" /usr/bin/true 2>/dev/null && return 0
        elif flock -n "$root/state/publisher.kernel.lock" /usr/bin/true 2>/dev/null; then
            return 0
        fi
        sleep 0.02
        attempt=$((attempt + 1))
    done
    fail "publisher kernel mutex did not release after holder exit"
}

pending_challenge() {
    sed -n 's/^challenge=//p' "$1/state/pending-admission.meta"
}

meta_field() {
    sed -n "s/^$2=//p" "$1"
}

receipt_for() {
    local root="$1" disposition="$2" file
    for file in "$root/state/receipts/"*.meta; do
        [ -f "$file" ] || continue
        if grep -qx "disposition=$disposition" "$file"; then
            printf '%s\n' "$file"
            return 0
        fi
    done
    return 1
}

assert_recovery_binding() {
    local predecessor_lease="$1" predecessor_challenge="$2" acquired="$3" completed="$4" pending="$5" label="$6"
    [ "$(meta_field "$acquired" predecessor_lease_id)" = "$predecessor_lease" ] ||
        fail "$label acquired predecessor lease mismatch"
    [ "$(meta_field "$acquired" predecessor_challenge)" = "$predecessor_challenge" ] ||
        fail "$label acquired predecessor challenge mismatch"
    [ "$(meta_field "$completed" predecessor_lease_id)" = "$predecessor_lease" ] ||
        fail "$label completed predecessor lease mismatch"
    [ "$(meta_field "$completed" predecessor_challenge)" = "$predecessor_challenge" ] ||
        fail "$label completed predecessor challenge mismatch"
    [ "$(meta_field "$acquired" successor_lease_id)" = "$(meta_field "$pending" lease_id)" ] ||
        fail "$label acquired successor lease mismatch"
    [ "$(meta_field "$acquired" successor_challenge)" = "$(meta_field "$pending" challenge)" ] ||
        fail "$label acquired successor challenge mismatch"
    [ "$(meta_field "$completed" successor_lease_id)" = "$(meta_field "$pending" lease_id)" ] ||
        fail "$label completed successor lease mismatch"
    [ "$(meta_field "$completed" successor_challenge)" = "$(meta_field "$pending" challenge)" ] ||
        fail "$label completed successor challenge mismatch"
}

new_case() {
    local name="$1" root="$TEST_ROOT/$1"
    mkdir -p "$root/bin" "$root/home" "$root/state"
    printf 'baseline-%s\n' "$name" > "$root/bin/agent-bridge.real"
    printf 'candidate-a-%s\n' "$name" > "$root/payload-a"
    printf 'candidate-b-%s\n' "$name" > "$root/payload-b"
    CASE_ROOT="$root"
}

run_lease() {
    local root="$1" action="$2" candidate="$3" payload="${4:-$1/payload-a}" fresh_probe="${5:-}"
    local live_fresh_probe="${6:-0}" hold_after_settled="${7:-0}"
    HOME="$root/home" \
    AGENT_BRIDGE_INSTALL_DIR="$root/bin" \
    AGENT_BRIDGE_REAL_BIN="$root/bin/agent-bridge.real" \
    AGENT_BRIDGE_DEPLOY_STATE_DIR="$root/state" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1 \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT="$TEST_ROOT" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION="$action" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_CANDIDATE="$candidate" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_PAYLOAD="$payload" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_MUTATION_LOG="$root/mutations.log" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_PROBE="$fresh_probe" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_LIVE_FRESH_MCP="$live_fresh_probe" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_HOLD_AFTER_FRESH_MCP_SETTLED="$hold_after_settled" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_TIMEOUT_SECONDS="${FRESH_MCP_TEST_TIMEOUT_SECONDS:-}" \
    AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_STDOUT_LIMIT_BYTES="${FRESH_MCP_TEST_STDOUT_LIMIT_BYTES:-}" \
        "$DEPLOY" --yes
}

write_fresh_mcp_probe_fixture() {
    local path="$1" build_sha="$2" evidence="${3:-}"
    {
        printf 'schema=%s\n' agent_bridge.publisher_fresh_mcp_probe.v0
        printf 'server_name=%s\n' agent-bridge
        printf 'server_version=%s\n' 0.14.0-test
        printf 'protocol_version=%s\n' 2024-11-05
        printf 'build_git_sha=%s\n' "$build_sha"
        printf 'toolset=%s\n' codex-essential
        printf 'tool_count=%s\n' 110
        printf 'capabilities_tool_present=%s\n' true
        printf 'probe_method=%s\n' independent_stdio_exact_installed_binary
    } > "$path"
    [ -n "$evidence" ] || evidence="$(sha256_fixture "$path")"
    printf 'evidence_sha256=%s\n' "$evidence" >> "$path"
    chmod 600 "$path"
}

write_live_mcp_executable() {
    local path="$1" build_sha="$2" mode="${3:-normal}"
    cat > "$path" <<PY
#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time

BUILD_SHA = "$build_sha"
MODE = "$mode"
DESCENDANT_MARKER = "$path.descendant.pid"
TOOLS = [
    {"name": "capabilities", "description": "test", "inputSchema": {"type": "object"}},
] + [
    {"name": f"essential_test_{index}", "description": "test", "inputSchema": {"type": "object"}}
    for index in range(109)
]

def spawn_descendant():
    child_code = (
        "import os,signal,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "open(sys.argv[1], 'w').write(str(os.getpid())); "
        "time.sleep(300)"
    )
    subprocess.Popen(
        [sys.executable, "-c", child_code, DESCENDANT_MARKER],
        close_fds=True,
    )
    deadline = time.monotonic() + 5
    while not os.path.exists(DESCENDANT_MARKER):
        if time.monotonic() >= deadline:
            raise SystemExit("descendant marker was not published")
        time.sleep(0.01)

if MODE.startswith("descendant-"):
    spawn_descendant()
if MODE == "descendant-stderr-limit":
    sys.stderr.write("e" * (512 * 1024))
    sys.stderr.flush()

for line in sys.stdin:
    request = json.loads(line)
    request_id = request.get("id")
    if request_id is None:
        continue
    method = request.get("method")
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "agent-bridge", "version": "0.14.0-test"},
        }
        if MODE == "oversized-output":
            result["serverInfo"]["version"] = "x" * (2 * 1024 * 1024)
    elif method == "tools/list":
        result = {"tools": TOOLS}
        if MODE == "next-cursor":
            result["nextCursor"] = "unexpected-page"
    elif method == "tools/call":
        if MODE == "duplicate-capabilities-key":
            capabilities_text = (
                '{"build":{"git_sha":' + json.dumps(BUILD_SHA) + '},'
                '"build":{"git_sha":' + json.dumps(BUILD_SHA) + '},'
                '"mcp":{"toolset":"codex-essential","exposed_tool_count":' +
                str(len(TOOLS)) + '}}'
            )
        else:
            capabilities = {
                "build": {"git_sha": BUILD_SHA},
                "mcp": {"toolset": "codex-essential", "exposed_tool_count": len(TOOLS)},
            }
            capabilities_text = json.dumps(capabilities)
        result = {"content": [{"type": "text", "text": capabilities_text}]}
        if MODE == "is-error":
            result["isError"] = True
        elif MODE == "extra-content":
            result["content"].append({"type": "text", "text": "unexpected"})
    else:
        continue
    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
    if MODE == "wrong-jsonrpc":
        response["jsonrpc"] = "1.0"
    elif MODE == "boolean-id":
        response["id"] = True
    elif MODE == "wrong-id":
        response["id"] = "publisher-admission-unrelated-id"
    elif MODE in ("slow", "descendant-timeout") and method == "initialize":
        time.sleep(60)
    if MODE == "duplicate-object-id":
        response_text = (
            '{"jsonrpc":"2.0","id":' + json.dumps(response["id"]) +
            ',"id":' + json.dumps(response["id"]) +
            ',"result":' + json.dumps(response["result"]) + '}'
        )
    elif MODE == "duplicate-object-result":
        response_text = (
            '{"jsonrpc":"2.0","id":' + json.dumps(response["id"]) +
            ',"result":{},"result":' + json.dumps(response["result"]) + '}'
        )
    else:
        response_text = json.dumps(response)
    print(response_text, flush=True)
    if MODE == "duplicate-tools-list" and method == "tools/list":
        print(json.dumps(response), flush=True)
    if MODE == "unknown-id" and method == "tools/list":
        response["id"] = "publisher-admission-unknown-id"
        print(json.dumps(response), flush=True)
PY
    chmod 755 "$path"
}

assert_live_probe_rejected() {
    local case_name="$1" candidate="$2" mode="$3" reason="$4"
    local root pending_sha output status
    new_case "$case_name"; root="$CASE_ROOT"
    chmod 755 "$root/bin/agent-bridge.real"
    write_live_mcp_executable "$root/payload-a" "${candidate:0:12}" "$mode"
    run_lease "$root" install "$candidate" >/dev/null
    pending_sha="$(sha256_fixture "$root/state/pending-admission.meta")"
    set +e
    output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "" 1 2>&1)"
    status=$?
    set -e
    [ "$status" -ne 0 ] || fail "fresh MCP live probe accepted $reason"
    case "$output" in *"fresh MCP admission probe failed"*) ;; *)
        fail "fresh MCP $reason rejection reason missing" ;;
    esac
    [ "$(sha256_fixture "$root/state/pending-admission.meta")" = "$pending_sha" ] ||
        fail "fresh MCP $reason rejection changed pending state"
    [ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] ||
        fail "fresh MCP $reason rejection published an admission intent"
}

assert_descendant_reaped() {
    local marker="$1" label="$2" attempt=0 pid command
    while [ ! -f "$marker" ] && [ "$attempt" -lt 200 ]; do
        sleep 0.02
        attempt=$((attempt + 1))
    done
    [ -f "$marker" ] || fail "$label did not publish a descendant PID marker"
    pid="$(cat "$marker")"
    case "$pid" in ''|*[!0-9]*) fail "$label published an invalid descendant PID" ;; esac
    DESCENDANT_PIDS="$DESCENDANT_PIDS $pid"
    attempt=0
    while [ "$attempt" -lt 200 ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
        case "$command" in *"$marker"*) ;; *) return 0 ;; esac
        sleep 0.02
        attempt=$((attempt + 1))
    done
    fail "$label left descendant process $pid alive"
}

write_hostile_python_environment() {
    local root="$1"
    mkdir -p "$root/hostile-bin" "$root/hostile-pythonpath"
    cat > "$root/hostile-bin/python3" <<'SH'
#!/usr/bin/env bash
printf '%s\n' path-python-ran >> "${HOSTILE_PYTHON_MARKER:?}"
exec /usr/bin/python3 "$@"
SH
    chmod 755 "$root/hostile-bin/python3"
    cat > "$root/hostile-pythonpath/sitecustomize.py" <<'PY'
import os
with open(os.environ["HOSTILE_PYTHON_MARKER"], "a", encoding="utf-8") as marker:
    marker.write("sitecustomize-ran\n")
PY
}

fresh_admission_receipt() {
    local root="$1" file
    for file in "$root/state/receipts/"*.fresh-mcp-admitted.meta; do
        [ -f "$file" ] || continue
        printf '%s\n' "$file"
        return 0
    done
    return 1
}

fresh_admission_quarantine() {
    local root="$1" file
    for file in "$root/state/quarantine/"*.fresh-mcp-admitted.pending.meta; do
        [ -f "$file" ] || continue
        printf '%s\n' "$file"
        return 0
    done
    return 1
}

fresh_admission_settled_intent() {
    local root="$1" file
    for file in "$root/state/quarantine/"*.fresh-mcp-admission-intent.settled.meta; do
        [ -f "$file" ] || continue
        printf '%s\n' "$file"
        return 0
    done
    return 1
}

start_holder() {
    local root="$1" phase="$2" timezone="${3:-UTC}" ready="$root/ready"
    (
        trap - EXIT
        exec env \
            HOME="$root/home" \
            AGENT_BRIDGE_INSTALL_DIR="$root/bin" \
            AGENT_BRIDGE_REAL_BIN="$root/bin/agent-bridge.real" \
            AGENT_BRIDGE_DEPLOY_STATE_DIR="$root/state" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1 \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT="$TEST_ROOT" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION=hold \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_CANDIDATE=holder \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_PHASE="$phase" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE="$ready" \
            TZ="$timezone" \
            "$DEPLOY" --yes
    ) > "$root/holder.log" 2>&1 &
    HOLDER_PID=$!
    attempt=0
    while [ ! -f "$ready" ] && [ "$attempt" -lt 200 ]; do
        sleep 0.02
        attempt=$((attempt + 1))
    done
    [ -f "$ready" ] || fail "holder did not become ready ($phase)"
    HOLDER_CHILD_PID="$(cat "$ready")"
}

start_fresh_admission_holder() {
    local root="$1" probe="$2" ready="$root/fresh-admission-ready"
    (
        trap - EXIT
        exec env \
            HOME="$root/home" \
            AGENT_BRIDGE_INSTALL_DIR="$root/bin" \
            AGENT_BRIDGE_REAL_BIN="$root/bin/agent-bridge.real" \
            AGENT_BRIDGE_DEPLOY_STATE_DIR="$root/state" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1 \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT="$TEST_ROOT" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION=admit-fresh-mcp \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_FRESH_MCP_PROBE="$probe" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE="$ready" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_HOLD_AFTER_FRESH_MCP_SETTLED=1 \
            "$DEPLOY" --yes
    ) > "$root/fresh-admission-holder.log" 2>&1 &
    HOLDER_PID=$!
    attempt=0
    while [ ! -f "$ready" ] && [ "$attempt" -lt 200 ]; do
        sleep 0.02
        attempt=$((attempt + 1))
    done
    [ -f "$ready" ] || fail "fresh MCP admission holder did not reach settled state"
    HOLDER_CHILD_PID="$(cat "$ready")"
}

kill_holder_without_cleanup() {
    kill -9 "$HOLDER_CHILD_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
    wait_kernel_lock_released "$1"
}

wait_for_direct_child() {
    local parent="$1" attempt=0 child=""
    while [ "$attempt" -lt 200 ]; do
        child="$(ps -axo pid=,ppid= | awk -v parent="$parent" '$2 == parent { print $1; exit }')"
        [ -z "$child" ] || break
        sleep 0.01
        attempt=$((attempt + 1))
    done
    [ -n "$child" ] || fail "publisher did not expose a live foreground child"
    DIRECT_CHILD_PID="$child"
}

write_release_intent_fixture() {
    local root="$1" quarantine="$2" reason="$3" meta="$root/state/active.lock/lease.meta"
    local lease_id challenge real_path shared_targets meta_sha current_sha current_inode receipt
    lease_id="$(meta_field "$meta" lease_id)"
    challenge="$(meta_field "$meta" challenge)"
    real_path="$(meta_field "$meta" real_path)"
    shared_targets="$(meta_field "$meta" shared_targets)"
    meta_sha="$(sha256_fixture "$meta")"
    current_sha="$(sha256_fixture "$real_path")"
    current_inode="$(stat -f %i "$real_path" 2>/dev/null || stat -c %i "$real_path")"
    receipt="$root/state/receipts/$lease_id.$challenge.test_release_settled.release-completed.meta"
    {
        printf 'schema=%s\n' agent_bridge.publisher_release_intent.v0
        printf 'lease_id=%s\n' "$lease_id"
        printf 'challenge=%s\n' "$challenge"
        printf 'disposition=%s\n' test_release_settled
        printf 'reason=%s\n' "$reason"
        printf 'quarantine_path=%s\n' "$quarantine"
        printf 'active_meta_sha256=%s\n' "$meta_sha"
        printf 'current_binary_sha256=%s\n' "$current_sha"
        printf 'current_binary_inode=%s\n' "$current_inode"
        printf 'receipt_path=%s\n' "$receipt"
        printf 'real_path=%s\n' "$real_path"
        printf 'shared_targets=%s\n' "$shared_targets"
        printf 'started_at=%s\n' 2026-08-26T00:00:00Z
    } > "$root/state/release-intent.meta"
    chmod 600 "$root/state/release-intent.meta"
}

write_handoff_fixture() {
    local root="$1" successor="$2" successor_challenge="$3"
    local handoff="$root/state/recovery-handoff.meta"
    local shared_targets="$root/bin/agent-bridge.real|$root/home/.local/share/ab-tts/audio_embody.py|$root/home/.local/lib/agent-bridge/scripts|$root/bin/agent-bridge"
    mkdir -p "$root/state/intents" "$root/state/quarantine" "$root/state/receipts"
    {
        printf 'schema=%s\n' agent_bridge.publisher_handoff_intent.v0
        printf 'predecessor_lease_id=%s\n' "predecessor-$successor"
        printf 'predecessor_challenge=%s\n' aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        printf 'predecessor_phase=%s\n' recovery_required
        printf 'predecessor_failed_phase=%s\n' committing
        printf 'predecessor_boot_identity=%s\n' cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
        printf 'predecessor_binary_sha256=%s\n' absent
        printf 'successor_lease_id=%s\n' "$successor"
        printf 'successor_challenge=%s\n' "$successor_challenge"
        printf 'successor_stage_path=%s\n' "$root/state/intents/$successor.lock"
        printf 'real_path=%s\n' "$root/bin/agent-bridge.real"
        printf 'shared_targets=%s\n' "$shared_targets"
        printf 'started_at=%s\n' 2026-08-26T00:00:00Z
        printf 'reason=%s\n' interrupted-handoff-completion
    } > "$handoff"
    chmod 600 "$handoff"
}

write_handoff_completion_fixture() {
    local root="$1" successor="$2" successor_challenge="$3" quarantine="$4"
    local handoff="$root/state/recovery-handoff.meta" meta_sha handoff_receipt recovery_receipt
    meta_sha="$(sha256_fixture "$handoff")"
    handoff_receipt="$root/state/receipts/$successor.$successor_challenge.governed_roll_forward_handoff_completed.meta"
    recovery_receipt="$root/state/receipts/$successor.$successor_challenge.governed_roll_forward_recovery_completed.meta"
    {
        printf 'schema=%s\n' agent_bridge.publisher_handoff_completion_intent.v0
        printf 'successor_lease_id=%s\n' "$successor"
        printf 'successor_challenge=%s\n' "$successor_challenge"
        printf 'successor_candidate_commit=%s\n' fixture-candidate
        printf 'handoff_meta_sha256=%s\n' "$meta_sha"
        printf 'quarantine_path=%s\n' "$quarantine"
        printf 'handoff_receipt_path=%s\n' "$handoff_receipt"
        printf 'recovery_receipt_path=%s\n' "$recovery_receipt"
        printf 'started_at=%s\n' 2026-08-26T00:00:00Z
    } > "$root/state/recovery-handoff-completion.meta"
    chmod 600 "$root/state/recovery-handoff-completion.meta"
}

# 1. A live pid with the exact start+boot fingerprint owns the mutex.
new_case live-owner; root="$CASE_ROOT"
start_holder "$root" building America/Los_Angeles
set +e
output="$(TZ=Asia/Shanghai run_lease "$root" probe contender 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "live exact owner did not block"
kill "$HOLDER_CHILD_PID" 2>/dev/null || true
wait "$HOLDER_PID" 2>/dev/null || true
wait_kernel_lock_released "$root"

# 2. A reused live pid with a mismatched start fingerprint is not its recorded owner.
new_case pid-reuse; root="$CASE_ROOT"
start_holder "$root" building
kill -9 "$HOLDER_CHILD_PID" 2>/dev/null || true
wait "$HOLDER_PID" 2>/dev/null || true
wait_kernel_lock_released "$root"
meta="$root/state/active.lock/lease.meta"
sed "s/^pid=.*/pid=$$/" "$meta" > "$meta.next"
mv -f "$meta.next" "$meta"
sed 's/^process_start_fingerprint=.*/process_start_fingerprint=0000000000000000000000000000000000000000000000000000000000000000/' "$meta" > "$meta.next"
mv -f "$meta.next" "$meta"
run_lease "$root" probe contender >/dev/null
grep -Rqs '^reason=dead_owner_pre_mutation_reclaimed$' "$root/state/receipts" ||
    fail "pid-reuse reclaim receipt missing"

# 3. A dead pre-mutation owner is reclaimable only while the baseline is unchanged.
new_case dead-pre; root="$CASE_ROOT"
start_holder "$root" building
kill -9 "$HOLDER_CHILD_PID" 2>/dev/null || true
wait "$HOLDER_PID" 2>/dev/null || true
wait_kernel_lock_released "$root"
run_lease "$root" probe contender >/dev/null
grep -Rqs '^disposition=aborted$' "$root/state/receipts" ||
    fail "dead pre-mutation aborted receipt missing"

# 4. A dead owner at/after committing leaves a recovery_required lock.
new_case dead-post; root="$CASE_ROOT"
start_holder "$root" committing
recovery_predecessor_lease="$(meta_field "$root/state/active.lock/lease.meta" lease_id)"
recovery_predecessor_challenge="$(meta_field "$root/state/active.lock/lease.meta" challenge)"
kill -9 "$HOLDER_CHILD_PID" 2>/dev/null || true
wait "$HOLDER_PID" 2>/dev/null || true
wait_kernel_lock_released "$root"
set +e
output="$(run_lease "$root" probe contender 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "dead post-mutation owner was reclaimed"
grep -qx 'phase=recovery_required' "$root/state/active.lock/lease.meta" ||
    fail "dead post-mutation lock was not marked recovery_required"
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=test-audited-roll-forward \
    run_lease "$root" install recovered "$root/payload-a" >/dev/null
grep -Rqs '^disposition=governed_roll_forward_recovery_started$' "$root/state/receipts" ||
    fail "governed recovery started receipt missing"
recovery_acquired="$(receipt_for "$root" governed_roll_forward_successor_acquired)" ||
    fail "governed recovery successor-acquired receipt missing"
recovery_completed="$(receipt_for "$root" governed_roll_forward_recovery_completed)" ||
    fail "governed recovery completed receipt missing"
successor_pending="$root/state/pending-admission.meta"
[ "$(meta_field "$recovery_acquired" predecessor_lease_id)" = "$recovery_predecessor_lease" ] ||
    fail "governed recovery acquired predecessor lease mismatch"
[ "$(meta_field "$recovery_acquired" predecessor_challenge)" = "$recovery_predecessor_challenge" ] ||
    fail "governed recovery acquired predecessor challenge mismatch"
[ "$(meta_field "$recovery_completed" predecessor_lease_id)" = "$recovery_predecessor_lease" ] ||
    fail "governed recovery completion predecessor lease mismatch"
[ "$(meta_field "$recovery_completed" predecessor_challenge)" = "$recovery_predecessor_challenge" ] ||
    fail "governed recovery completion predecessor challenge mismatch"
[ "$(meta_field "$recovery_completed" successor_lease_id)" = "$(meta_field "$successor_pending" lease_id)" ] ||
    fail "governed recovery completion successor lease mismatch"
[ "$(meta_field "$recovery_completed" successor_challenge)" = "$(meta_field "$successor_pending" challenge)" ] ||
    fail "governed recovery completion successor challenge mismatch"
[ "$(meta_field "$recovery_acquired" successor_lease_id)" = "$(meta_field "$successor_pending" lease_id)" ] ||
    fail "governed recovery acquired successor lease mismatch"
[ "$(meta_field "$recovery_acquired" successor_challenge)" = "$(meta_field "$successor_pending" challenge)" ] ||
    fail "governed recovery acquired successor challenge mismatch"

# 5. Same candidate + exact installed fingerprint is an idempotent no-op.
new_case same-candidate; root="$CASE_ROOT"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 1 ] ||
    fail "same-candidate pending admission mutated twice"
grep -Rqs '^disposition=idempotent_pending_match$' "$root/state/receipts" ||
    fail "same-candidate idempotent receipt missing"

# 6. Pending metadata cannot authorize mutation after installed fingerprint drift.
new_case pending-mismatch; root="$CASE_ROOT"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
printf 'external-drift\n' > "$root/bin/agent-bridge.real"
set +e
output="$(run_lease "$root" probe candidate-a 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "pending fingerprint mismatch was accepted"
case "$output" in *"pending-admission fingerprint no longer matches"*) ;; *) fail "pending mismatch reason missing" ;; esac

# 7. A same-candidate no-op also binds the installed binary mode, not only its
# content and inode.
new_case pending-binary-mode-mismatch; root="$CASE_ROOT"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
binary="$root/bin/agent-bridge.real"
binary_mode="$(stat -f %Lp "$binary" 2>/dev/null || stat -c %a "$binary")"
case "$binary_mode" in
    700) chmod 755 "$binary" ;;
    *) chmod 700 "$binary" ;;
esac
set +e
output="$(run_lease "$root" probe candidate-a 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "same-candidate binary mode drift used the idempotent path"
case "$output" in *"pending-admission fingerprint no longer matches"*) ;; *) fail "binary mode drift reason missing" ;; esac
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 1 ] ||
    fail "binary mode drift caused an unexpected mutation"

# 8. A same-candidate no-op also binds fingerprinted asset content.
new_case pending-asset-content-mismatch; root="$CASE_ROOT"
adapter="$root/home/.local/share/ab-tts/audio_embody.py"
mkdir -p "$(dirname "$adapter")"
printf 'asset-v1\n' > "$adapter"
chmod 755 "$adapter"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
printf 'asset-v2\n' > "$adapter"
set +e
output="$(run_lease "$root" probe candidate-a 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "same-candidate asset content drift used the idempotent path"
case "$output" in *"pending-admission fingerprint no longer matches"*) ;; *) fail "asset content drift reason missing" ;; esac
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 1 ] ||
    fail "asset content drift caused an unexpected mutation"

# 9. A different candidate is blocked by default, then superseded explicitly.
new_case supersede; root="$CASE_ROOT"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
challenge="$(pending_challenge "$root")"
predecessor_lease="$(meta_field "$root/state/pending-admission.meta" lease_id)"
set +e
output="$(run_lease "$root" install candidate-b "$root/payload-b" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "different candidate bypassed pending admission without explicit supersede"
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 1 ] ||
    fail "blocked different candidate mutated installed state"
AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING=1 \
AGENT_BRIDGE_DEPLOY_SUPERSEDE_REASON=test-explicit-new-candidate \
AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE="$challenge" \
    run_lease "$root" install candidate-b "$root/payload-b" >/dev/null
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 2 ] ||
    fail "different candidate did not perform exactly one new mutation"
grep -qx 'candidate_commit=candidate-b' "$root/state/pending-admission.meta" ||
    fail "new candidate pending admission missing"
grep -Rqs '^disposition=supersede-started$' "$root/state/receipts" ||
    fail "supersede-started pending receipt missing"
grep -Rqs '^disposition=supersede-completed$' "$root/state/receipts" ||
    fail "supersede-completed pending receipt missing"
supersede_completed="$(receipt_for "$root" supersede-completed)"
successor_pending="$root/state/pending-admission.meta"
[ "$(meta_field "$supersede_completed" predecessor_lease_id)" = "$predecessor_lease" ] ||
    fail "supersede completion predecessor lease mismatch"
[ "$(meta_field "$supersede_completed" predecessor_challenge)" = "$challenge" ] ||
    fail "supersede completion predecessor challenge mismatch"
[ "$(meta_field "$supersede_completed" successor_lease_id)" = "$(meta_field "$successor_pending" lease_id)" ] ||
    fail "supersede completion successor lease mismatch"
[ "$(meta_field "$supersede_completed" successor_challenge)" = "$(meta_field "$successor_pending" challenge)" ] ||
    fail "supersede completion successor challenge mismatch"
[ "$(meta_field "$supersede_completed" successor_candidate_commit)" = candidate-b ] ||
    fail "supersede completion successor candidate mismatch"

# 10. Fingerprint drift requires roll-forward plus the exact pending challenge.
new_case pending-drift-recovery; root="$CASE_ROOT"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
challenge="$(pending_challenge "$root")"
predecessor_lease="$(meta_field "$root/state/pending-admission.meta" lease_id)"
printf 'external-drift\n' > "$root/bin/agent-bridge.real"
set +e
output="$(AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING=1 \
    AGENT_BRIDGE_DEPLOY_SUPERSEDE_REASON=drift-without-recovery \
    AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE="$challenge" \
    run_lease "$root" install candidate-b "$root/payload-b" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "fingerprint drift recovered without roll-forward"
set +e
output="$(AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
    AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=test-drift-roll-forward \
    AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING=1 \
    AGENT_BRIDGE_DEPLOY_SUPERSEDE_REASON=test-drift-supersede \
    AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE=0000000000000000000000000000000000000000000000000000000000000000 \
    run_lease "$root" install candidate-b "$root/payload-b" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "fingerprint drift recovered with the wrong pending challenge"
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=test-drift-roll-forward \
AGENT_BRIDGE_DEPLOY_SUPERSEDE_PENDING=1 \
AGENT_BRIDGE_DEPLOY_SUPERSEDE_REASON=test-drift-supersede \
AGENT_BRIDGE_DEPLOY_SUPERSEDE_EXPECTED_CHALLENGE="$challenge" \
    run_lease "$root" install candidate-b "$root/payload-b" >/dev/null
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 2 ] ||
    fail "exact challenged drift recovery did not perform one successor mutation"
grep -Rqs '^disposition=recovery-roll-forward-started$' "$root/state/receipts" ||
    fail "drift recovery started receipt missing"
grep -Rqs '^disposition=recovery-roll-forward-completed$' "$root/state/receipts" ||
    fail "drift recovery completed receipt missing"
drift_completed="$(receipt_for "$root" recovery-roll-forward-completed)"
successor_pending="$root/state/pending-admission.meta"
[ "$(meta_field "$drift_completed" predecessor_lease_id)" = "$predecessor_lease" ] ||
    fail "drift recovery predecessor lease mismatch"
[ "$(meta_field "$drift_completed" predecessor_challenge)" = "$challenge" ] ||
    fail "drift recovery predecessor challenge mismatch"
[ "$(meta_field "$drift_completed" successor_lease_id)" = "$(meta_field "$successor_pending" lease_id)" ] ||
    fail "drift recovery successor lease mismatch"
[ "$(meta_field "$drift_completed" successor_challenge)" = "$(meta_field "$successor_pending" challenge)" ] ||
    fail "drift recovery successor challenge mismatch"

# 11. Shared-target drift cannot use the same-candidate idempotent path.
new_case shared-target-mismatch; root="$CASE_ROOT"
run_lease "$root" install candidate-a "$root/payload-a" >/dev/null
pending="$root/state/pending-admission.meta"
sed 's|^shared_targets=.*|shared_targets=/mismatched/physical/targets|' "$pending" > "$pending.next"
mv -f "$pending.next" "$pending"
set +e
output="$(run_lease "$root" install candidate-a "$root/payload-a" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "shared-target mismatch used same-candidate no-op"
[ "$(wc -l < "$root/mutations.log" | tr -d ' ')" = 1 ] ||
    fail "shared-target mismatch mutated installed state"

# 12. A corrupt active lock is blocked by default and recoverable only through
# an audited roll-forward with complete predecessor/successor binding.
new_case corrupt-active-recovery; root="$CASE_ROOT"
mkdir "$root/state/active.lock"
printf '%s\n' 999999 > "$root/state/active.lock/pid"
set +e
output="$(run_lease "$root" probe corrupt-default 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "missing active lease metadata was accepted without recovery"
case "$output" in *"governed roll_forward recovery is required"*) ;; *) fail "corrupt active default blocker reason missing" ;; esac
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=test-corrupt-active-roll-forward \
    run_lease "$root" install corrupt-successor "$root/payload-a" >/dev/null
corrupt_started="$(receipt_for "$root" governed_corrupt_recovery_started)" ||
    fail "corrupt recovery started receipt missing"
corrupt_acquired="$(receipt_for "$root" governed_roll_forward_successor_acquired)" ||
    fail "corrupt recovery successor-acquired receipt missing"
corrupt_completed="$(receipt_for "$root" governed_roll_forward_recovery_completed)" ||
    fail "corrupt recovery completed receipt missing"
corrupt_pending="$root/state/pending-admission.meta"
corrupt_predecessor_lease="$(meta_field "$corrupt_started" predecessor_lease_id)"
corrupt_predecessor_challenge="$(meta_field "$corrupt_started" predecessor_challenge)"
assert_recovery_binding "$corrupt_predecessor_lease" "$corrupt_predecessor_challenge" \
    "$corrupt_acquired" "$corrupt_completed" "$corrupt_pending" corrupt-recovery
[ "$(meta_field "$corrupt_started" successor_lease_id)" = "$(meta_field "$corrupt_pending" lease_id)" ] ||
    fail "corrupt started receipt successor lease mismatch"
[ "$(meta_field "$corrupt_started" successor_challenge)" = "$(meta_field "$corrupt_pending" challenge)" ] ||
    fail "corrupt started receipt successor challenge mismatch"
[ ! -e "$root/state/recovery-handoff.meta" ] || fail "corrupt recovery left the canonical handoff marker"

# 13. A durable handoff marker with no active lease blocks ordinary publication;
# roll-forward resumes it, completes the successor, and retires the marker.
new_case orphaned-handoff; root="$CASE_ROOT"
mkdir -p "$root/state/intents"
handoff="$root/state/recovery-handoff.meta"
handoff_predecessor=predecessor-handoff
handoff_predecessor_challenge=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
handoff_old_successor=successor-lost
handoff_old_challenge=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
handoff_shared_targets="$root/bin/agent-bridge.real|$root/home/.local/share/ab-tts/audio_embody.py|$root/home/.local/lib/agent-bridge/scripts|$root/bin/agent-bridge"
{
    printf 'schema=%s\n' agent_bridge.publisher_handoff_intent.v0
    printf 'predecessor_lease_id=%s\n' "$handoff_predecessor"
    printf 'predecessor_challenge=%s\n' "$handoff_predecessor_challenge"
    printf 'predecessor_phase=%s\n' corrupt_unknown
    printf 'predecessor_failed_phase=%s\n' corrupt_unknown
    printf 'predecessor_boot_identity=%s\n' cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
    printf 'predecessor_binary_sha256=%s\n' absent
    printf 'successor_lease_id=%s\n' "$handoff_old_successor"
    printf 'successor_challenge=%s\n' "$handoff_old_challenge"
    printf 'successor_stage_path=%s\n' "$root/state/intents/$handoff_old_successor.lock"
    printf 'real_path=%s\n' "$root/bin/agent-bridge.real"
    printf 'shared_targets=%s\n' "$handoff_shared_targets"
    printf 'started_at=%s\n' 2026-08-26T00:00:00Z
    printf 'reason=%s\n' interrupted-before-successor-publication
} > "$handoff"
chmod 600 "$handoff"
set +e
output="$(run_lease "$root" probe handoff-default 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "orphaned recovery handoff did not block ordinary publication"
case "$output" in *"incomplete governed recovery handoff exists"*) ;; *) fail "orphaned handoff default blocker reason missing" ;; esac
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=test-resume-orphaned-handoff \
    run_lease "$root" install handoff-successor "$root/payload-b" >/dev/null
handoff_resumed="$(receipt_for "$root" governed_roll_forward_handoff_resumed)" ||
    fail "handoff resumed receipt missing"
handoff_completed="$(receipt_for "$root" governed_roll_forward_handoff_completed)" ||
    fail "handoff completed receipt missing"
handoff_acquired="$(receipt_for "$root" governed_roll_forward_successor_acquired)" ||
    fail "resumed handoff successor-acquired receipt missing"
handoff_recovery_completed="$(receipt_for "$root" governed_roll_forward_recovery_completed)" ||
    fail "resumed handoff recovery-completed receipt missing"
handoff_pending="$root/state/pending-admission.meta"
assert_recovery_binding "$handoff_predecessor" "$handoff_predecessor_challenge" \
    "$handoff_acquired" "$handoff_recovery_completed" "$handoff_pending" resumed-handoff
[ "$(meta_field "$handoff_resumed" successor_lease_id)" = "$handoff_old_successor" ] ||
    fail "handoff resumed receipt lost the interrupted successor identity"
[ "$(meta_field "$handoff_completed" successor_lease_id)" = "$(meta_field "$handoff_pending" lease_id)" ] ||
    fail "handoff completed receipt successor lease mismatch"
[ "$(meta_field "$handoff_completed" successor_challenge)" = "$(meta_field "$handoff_pending" challenge)" ] ||
    fail "handoff completed receipt successor challenge mismatch"
[ ! -e "$handoff" ] || fail "completed recovery left the canonical handoff marker"

# 14. A dangling final symlink is rejected before lease acquisition.
new_case dangling-symlink; root="$CASE_ROOT"
mv "$root/bin/agent-bridge.real" "$root/bin/original-real"
ln -s "$root/bin/missing-real" "$root/bin/agent-bridge.real"
set +e
output="$(run_lease "$root" probe dangling 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "dangling final symlink was accepted"
case "$output" in *"dangling final symlink"*) ;; *) fail "dangling symlink reason missing" ;; esac

# 15. Sixteen stale-lock contenders yield exactly one live holder.
new_case reclaim-stress; root="$CASE_ROOT"
start_holder "$root" building
kill -9 "$HOLDER_CHILD_PID" 2>/dev/null || true
wait "$HOLDER_PID" 2>/dev/null || true
wait_kernel_lock_released "$root"
stress_pids=()
i=1
while [ "$i" -le 16 ]; do
    ready="$root/contender-$i.ready"
    (
        trap - EXIT
        exec env HOME="$root/home" \
            AGENT_BRIDGE_INSTALL_DIR="$root/bin" \
            AGENT_BRIDGE_REAL_BIN="$root/bin/agent-bridge.real" \
            AGENT_BRIDGE_DEPLOY_STATE_DIR="$root/state" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_MODE=1 \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_ROOT="$TEST_ROOT" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_ACTION=hold \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_CANDIDATE="contender-$i" \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_PHASE=building \
            AGENT_BRIDGE_DEPLOY_LEASE_TEST_READY_FILE="$ready" \
            "$DEPLOY" --yes
    ) > "$root/contender-$i.log" 2>&1 &
    stress_pids+=("$!")
    i=$((i + 1))
done
attempt=0
ready_count=0
while [ "$attempt" -lt 200 ]; do
    ready_count="$(find "$root" -maxdepth 1 -name 'contender-*.ready' | wc -l | tr -d ' ')"
    [ "$ready_count" -ge 1 ] && break
    sleep 0.02
    attempt=$((attempt + 1))
done
sleep 0.2
ready_count="$(find "$root" -maxdepth 1 -name 'contender-*.ready' | wc -l | tr -d ' ')"
[ "$ready_count" = 1 ] || fail "stale reclaim stress produced $ready_count live holders"
winner_ready="$(find "$root" -maxdepth 1 -name 'contender-*.ready' -print -quit)"
winner_pid="$(cat "$winner_ready")"
kill "$winner_pid" 2>/dev/null || true
for pid in "${stress_pids[@]}"; do wait "$pid" 2>/dev/null || true; done

# 16. The publisher itself owns fd 9. If SIGKILL removes that shell while its
# foreground child still has the inherited fd, no contender may publish a
# second active lease.
new_case inherited-child-mutex; root="$CASE_ROOT"
start_holder "$root" building
publisher_pid="$HOLDER_CHILD_PID"
[ "$publisher_pid" = "$HOLDER_PID" ] || fail "publisher pid is hidden behind an independent lock supervisor"
meta="$root/state/active.lock/lease.meta"
[ "$(meta_field "$meta" pid)" = "$publisher_pid" ] || fail "active lease pid is not the fd 9 publisher"
original_lease="$(meta_field "$meta" lease_id)"
wait_for_direct_child "$publisher_pid"
publisher_child="$DIRECT_CHILD_PID"
kill -STOP "$publisher_child"
kill -9 "$publisher_pid" 2>/dev/null || true
wait "$HOLDER_PID" 2>/dev/null || true
kill -0 "$publisher_child" 2>/dev/null || fail "publisher child did not survive publisher SIGKILL"
set +e
output="$(run_lease "$root" probe inherited-fd-contender 2>&1)"
status=$?
set -e
case "$(/usr/bin/uname -s 2>/dev/null || uname -s)" in
    Darwin) expected_mutex_busy=75 ;;
    Linux) expected_mutex_busy=1 ;;
    *) fail "unsupported inherited-child mutex test platform" ;;
esac
[ "$status" -eq "$expected_mutex_busy" ] ||
    fail "contender did not fail with the kernel mutex busy status while inherited child was alive"
[ "$(meta_field "$meta" lease_id)" = "$original_lease" ] || fail "contender replaced the original active lease"
staged_count="$(find "$root/state/intents" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
[ "$staged_count" = 0 ] || fail "blocked contender formed a second staged active lease"
kill -9 "$publisher_child" 2>/dev/null || true
wait_kernel_lock_released "$root"

# 17. Startup settles a release intent left before active.lock was moved.
new_case release-before-move; root="$CASE_ROOT"
start_holder "$root" building
kill_holder_without_cleanup "$root"
old_lease="$(meta_field "$root/state/active.lock/lease.meta" lease_id)"
quarantine="$root/state/quarantine/test-$old_lease.before-move.lock"
write_release_intent_fixture "$root" "$quarantine" release_crash_before_move
run_lease "$root" probe release-before-successor >/dev/null
[ ! -e "$root/state/release-intent.meta" ] || fail "crash-before-move release intent remained canonical"
[ -d "$quarantine" ] || fail "crash-before-move active lease was not quarantined"
[ "$(receipt_field_count "$root" reason release_crash_before_move)" = 1 ] ||
    fail "crash-before-move release receipt was missing or duplicated"
settled_count="$(quarantine_field_count "$root" lease_id "$old_lease" settled-release-intent.meta)"
[ "$settled_count" = 1 ] || fail "crash-before-move release intent was not archived exactly once"
[ "$(mutation_count "$root")" = 0 ] || fail "crash-before-move startup settlement mutated the binary"

# 18. Startup also settles when active.lock was already moved but its release
# intent had not yet been retired.
new_case release-after-move; root="$CASE_ROOT"
start_holder "$root" building
kill_holder_without_cleanup "$root"
old_lease="$(meta_field "$root/state/active.lock/lease.meta" lease_id)"
quarantine="$root/state/quarantine/test-$old_lease.after-move.lock"
write_release_intent_fixture "$root" "$quarantine" release_crash_after_move
mv "$root/state/active.lock" "$quarantine"
run_lease "$root" probe release-after-successor >/dev/null
[ ! -e "$root/state/release-intent.meta" ] || fail "crash-after-move release intent remained canonical"
[ -d "$quarantine" ] || fail "crash-after-move quarantine disappeared"
[ "$(receipt_field_count "$root" reason release_crash_after_move)" = 1 ] ||
    fail "crash-after-move release receipt was missing or duplicated"
settled_count="$(quarantine_field_count "$root" lease_id "$old_lease" settled-release-intent.meta)"
[ "$settled_count" = 1 ] || fail "crash-after-move release intent was not archived exactly once"
[ "$(mutation_count "$root")" = 0 ] || fail "crash-after-move startup settlement mutated the binary"

# 19. Startup settles a handoff-completion intent whose canonical marker has
# not yet moved to quarantine.
new_case handoff-completion-before-move; root="$CASE_ROOT"
successor=handoff-successor-before
successor_challenge=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
quarantine="$root/state/quarantine/$successor.completed-recovery-handoff.meta"
write_handoff_fixture "$root" "$successor" "$successor_challenge"
write_handoff_completion_fixture "$root" "$successor" "$successor_challenge" "$quarantine"
run_lease "$root" probe handoff-completion-before-successor >/dev/null
[ ! -e "$root/state/recovery-handoff.meta" ] || fail "canonical-before-move handoff marker remained canonical"
[ ! -e "$root/state/recovery-handoff-completion.meta" ] || fail "canonical-before-move completion intent remained canonical"
[ -f "$quarantine" ] || fail "canonical-before-move handoff marker was not quarantined"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_handoff_completed)" = 1 ] ||
    fail "canonical-before-move handoff completion receipt was missing or duplicated"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_recovery_completed)" = 1 ] ||
    fail "canonical-before-move formal recovery completion receipt was missing or duplicated"
settled_count="$(find "$root/state/quarantine" -type f -name '*.settled-handoff-completion.meta' | wc -l | tr -d ' ')"
[ "$settled_count" = 1 ] || fail "canonical-before-move completion intent was not archived exactly once"
[ "$(mutation_count "$root")" = 0 ] || fail "canonical-before-move handoff settlement mutated the binary"

# 20. Startup settles the complementary crash point where the handoff marker
# reached quarantine before its completion intent was retired.
new_case handoff-completion-after-move; root="$CASE_ROOT"
successor=handoff-successor-after
successor_challenge=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
quarantine="$root/state/quarantine/$successor.completed-recovery-handoff.meta"
write_handoff_fixture "$root" "$successor" "$successor_challenge"
write_handoff_completion_fixture "$root" "$successor" "$successor_challenge" "$quarantine"
mv "$root/state/recovery-handoff.meta" "$quarantine"
run_lease "$root" probe handoff-completion-after-successor >/dev/null
[ ! -e "$root/state/recovery-handoff.meta" ] || fail "quarantine-after-move handoff marker reappeared canonical"
[ ! -e "$root/state/recovery-handoff-completion.meta" ] || fail "quarantine-after-move completion intent remained canonical"
[ -f "$quarantine" ] || fail "quarantine-after-move handoff marker disappeared"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_handoff_completed)" = 1 ] ||
    fail "quarantine-after-move handoff completion receipt was missing or duplicated"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_recovery_completed)" = 1 ] ||
    fail "quarantine-after-move formal recovery completion receipt was missing or duplicated"
settled_count="$(find "$root/state/quarantine" -type f -name '*.settled-handoff-completion.meta' | wc -l | tr -d ' ')"
[ "$settled_count" = 1 ] || fail "quarantine-after-move completion intent was not archived exactly once"
[ "$(mutation_count "$root")" = 0 ] || fail "quarantine-after-move handoff settlement mutated the binary"

# 21. A SIGKILL between exclusive active mkdir and staged metadata movement is
# exactly related through the handoff's staged successor and can be resumed.
new_case partial-successor-active; root="$CASE_ROOT"
start_holder "$root" acquired
successor="$(meta_field "$root/state/active.lock/lease.meta" lease_id)"
successor_challenge="$(meta_field "$root/state/active.lock/lease.meta" challenge)"
kill_holder_without_cleanup "$root"
mkdir -p "$root/state/intents"
mv "$root/state/active.lock" "$root/state/intents/$successor.lock"
mkdir "$root/state/active.lock"
write_handoff_fixture "$root" "$successor" "$successor_challenge"
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=resume-partial-successor-active \
    run_lease "$root" install recovered-partial-successor "$root/payload-a" >/dev/null
[ ! -e "$root/state/active.lock" ] || fail "partial successor recovery left an active lease"
[ ! -e "$root/state/recovery-handoff.meta" ] || fail "partial successor recovery left a canonical handoff"
[ ! -e "$root/state/intents/$successor.lock" ] || fail "partial successor recovery left its old staged lease"
[ "$(find "$root/state/quarantine" -type d -name '*.partial-successor-active.lock' | wc -l | tr -d ' ')" = 1 ] ||
    fail "partial successor active claim was not quarantined exactly once"
[ "$(find "$root/state/quarantine" -type d -name '*.partial-successor-stage.lock' | wc -l | tr -d ' ')" = 1 ] ||
    fail "partial successor stage was not quarantined exactly once"
[ "$(mutation_count "$root")" = 1 ] || fail "partial successor recovery did not perform exactly one successor mutation"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_recovery_completed)" = 1 ] ||
    fail "partial successor recovery completion receipt missing"
partial_acquired="$(receipt_for "$root" governed_roll_forward_successor_acquired)"
partial_completed="$(receipt_for "$root" governed_roll_forward_recovery_completed)"
[ "$(meta_field "$partial_acquired" predecessor_lease_id)" = "predecessor-$successor" ] ||
    fail "partial successor recovery lost the original predecessor lease"
[ "$(meta_field "$partial_completed" predecessor_challenge)" = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ] ||
    fail "partial successor completion lost the original predecessor challenge"

# 22. The complementary crash after metadata reached active.lock but before
# successor-acquired handoff archival also resumes the original predecessor.
new_case published-successor-active; root="$CASE_ROOT"
start_holder "$root" acquired
successor="$(meta_field "$root/state/active.lock/lease.meta" lease_id)"
successor_challenge="$(meta_field "$root/state/active.lock/lease.meta" challenge)"
kill_holder_without_cleanup "$root"
write_handoff_fixture "$root" "$successor" "$successor_challenge"
AGENT_BRIDGE_DEPLOY_RECOVERY=roll_forward \
AGENT_BRIDGE_DEPLOY_RECOVERY_REASON=resume-published-successor-active \
    run_lease "$root" install recovered-published-successor "$root/payload-b" >/dev/null
[ ! -e "$root/state/active.lock" ] || fail "published successor recovery left an active lease"
[ ! -e "$root/state/recovery-handoff.meta" ] || fail "published successor recovery left a canonical handoff"
[ "$(mutation_count "$root")" = 1 ] || fail "published successor recovery did not perform exactly one successor mutation"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_recovery_completed)" = 1 ] ||
    fail "published successor recovery completion receipt missing"
published_acquired="$(receipt_for "$root" governed_roll_forward_successor_acquired)"
published_completed="$(receipt_for "$root" governed_roll_forward_recovery_completed)"
[ "$(meta_field "$published_acquired" predecessor_lease_id)" = "predecessor-$successor" ] ||
    fail "published successor recovery lost the original predecessor lease"
[ "$(meta_field "$published_acquired" predecessor_challenge)" = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ] ||
    fail "published successor acquired receipt lost the original predecessor challenge"
[ "$(meta_field "$published_completed" predecessor_lease_id)" = "predecessor-$successor" ] ||
    fail "published successor completion lost the original predecessor lease"
[ "$(meta_field "$published_completed" predecessor_challenge)" = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ] ||
    fail "published successor completion lost the original predecessor challenge"

# 23. Replaying a release intent after its exact receipt was already written
# must verify that receipt and retire the intent without duplicating it.
new_case release-receipt-replay; root="$CASE_ROOT"
start_holder "$root" building
kill_holder_without_cleanup "$root"
old_lease="$(meta_field "$root/state/active.lock/lease.meta" lease_id)"
quarantine="$root/state/quarantine/test-$old_lease.receipt-replay.lock"
write_release_intent_fixture "$root" "$quarantine" release_receipt_replay
cp "$root/state/release-intent.meta" "$root/release-intent.replay"
run_lease "$root" probe release-receipt-first-successor >/dev/null
cp "$root/release-intent.replay" "$root/state/release-intent.meta"
run_lease "$root" probe release-receipt-second-successor >/dev/null
[ "$(receipt_field_count "$root" reason release_receipt_replay)" = 1 ] ||
    fail "replayed release intent duplicated its prebound completion receipt"
[ ! -e "$root/state/release-intent.meta" ] || fail "replayed release intent remained canonical"
release_receipt="$(meta_field "$root/release-intent.replay" receipt_path)"
cp "$root/release-intent.replay" "$root/state/release-intent.meta"
printf '%s\n' tampered >> "$release_receipt"
set +e
output="$(run_lease "$root" probe release-receipt-mismatch-successor 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "mismatched prebound release receipt was accepted"
case "$output" in *"prebound publisher receipt already exists with different content"*) ;; *)
    fail "mismatched prebound release receipt fail-closed reason missing" ;;
esac
[ -e "$root/state/release-intent.meta" ] || fail "mismatched release receipt retired its canonical intent"

# 24. The two prebound handoff-completion receipts are likewise exactly-once
# when SIGKILL is modelled after receipt publication but before intent retire.
new_case handoff-receipt-replay; root="$CASE_ROOT"
successor=handoff-successor-receipt-replay
successor_challenge=ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
quarantine="$root/state/quarantine/$successor.completed-recovery-handoff.meta"
write_handoff_fixture "$root" "$successor" "$successor_challenge"
write_handoff_completion_fixture "$root" "$successor" "$successor_challenge" "$quarantine"
cp "$root/state/recovery-handoff-completion.meta" "$root/handoff-completion.replay"
run_lease "$root" probe handoff-receipt-first-successor >/dev/null
cp "$root/handoff-completion.replay" "$root/state/recovery-handoff-completion.meta"
run_lease "$root" probe handoff-receipt-second-successor >/dev/null
[ "$(receipt_field_count "$root" disposition governed_roll_forward_handoff_completed)" = 1 ] ||
    fail "replayed handoff completion duplicated its prebound marker receipt"
[ "$(receipt_field_count "$root" disposition governed_roll_forward_recovery_completed)" = 1 ] ||
    fail "replayed handoff completion duplicated its prebound formal recovery receipt"
[ ! -e "$root/state/recovery-handoff-completion.meta" ] ||
    fail "replayed handoff completion intent remained canonical"

# 25. A matching exact installed fingerprint and fresh-MCP probe consume the
# pending state into one deterministic receipt and one quarantined source.
new_case fresh-mcp-admission; root="$CASE_ROOT"
candidate=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
cp "$root/state/pending-admission.meta" "$root/pending.before-admission"
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" >/dev/null
[ ! -e "$root/state/pending-admission.meta" ] || fail "fresh MCP admission left canonical pending state"
[ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP admission left canonical completion intent"
receipt="$(fresh_admission_receipt "$root")" || fail "fresh MCP admission receipt missing"
quarantine="$(fresh_admission_quarantine "$root")" || fail "fresh MCP admitted pending quarantine missing"
settled_intent="$(fresh_admission_settled_intent "$root")" || fail "fresh MCP settled intent archive missing"
cmp -s "$root/pending.before-admission" "$quarantine" || fail "fresh MCP admitted pending content changed"
[ "$(meta_field "$receipt" candidate_commit)" = "$candidate" ] || fail "fresh MCP receipt candidate mismatch"
[ "$(meta_field "$receipt" fresh_mcp)" = verified ] || fail "fresh MCP receipt is not verified"
[ "$(meta_field "$receipt" probe_build_git_sha)" = "${candidate:0:12}" ] || fail "fresh MCP receipt probe build mismatch"
[ "$(meta_field "$receipt" probe_toolset)" = codex-essential ] || fail "fresh MCP receipt toolset mismatch"
[ "$(meta_field "$receipt" probe_tool_count)" = 110 ] || fail "fresh MCP receipt tool count mismatch"

# 26. Receipt publication before pending quarantine is replay-idempotent: the
# exact receipt is reused and the still-canonical pending state is retired.
mv "$settled_intent" "$root/state/fresh-mcp-admission-intent.meta"
mv "$quarantine" "$root/state/pending-admission.meta"
receipt_sha="$(sha256_fixture "$receipt")"
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" >/dev/null
[ "$(sha256_fixture "$receipt")" = "$receipt_sha" ] || fail "fresh MCP receipt-before-move replay changed the receipt"
[ ! -e "$root/state/pending-admission.meta" ] || fail "fresh MCP receipt-before-move replay left pending state"
[ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP receipt-before-move replay left completion intent"

# 27. Pending quarantine before publisher release is also replay-idempotent:
# the exact quarantined source and receipt settle the interrupted admission.
settled_intent="$(fresh_admission_settled_intent "$root")"
mv "$settled_intent" "$root/state/fresh-mcp-admission-intent.meta"
quarantine="$(fresh_admission_quarantine "$root")"
quarantine_sha="$(sha256_fixture "$quarantine")"
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" >/dev/null
[ "$(sha256_fixture "$quarantine")" = "$quarantine_sha" ] || fail "fresh MCP post-move replay changed quarantined pending state"
[ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP post-move replay left completion intent"

# 28. A probe for any other build fails before intent publication and preserves
# the exact pending admission for a later authoritative retry.
new_case fresh-mcp-wrong-build; root="$CASE_ROOT"
candidate=cccccccccccccccccccccccccccccccccccccccc
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" dddddddddddd
run_lease "$root" install "$candidate" >/dev/null
pending_sha="$(sha256_fixture "$root/state/pending-admission.meta")"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "fresh MCP probe for a different build was accepted"
case "$output" in *"probe build does not match pending candidate"*) ;; *)
    fail "fresh MCP wrong-build fail-closed reason missing" ;;
esac
[ "$(sha256_fixture "$root/state/pending-admission.meta")" = "$pending_sha" ] || fail "fresh MCP wrong-build failure changed pending state"
[ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP wrong-build failure published an intent"

# 29. Binary drift after pending publication fails before the probe and leaves
# the original pending state untouched for governed recovery.
new_case fresh-mcp-binary-drift; root="$CASE_ROOT"
candidate=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
pending_sha="$(sha256_fixture "$root/state/pending-admission.meta")"
printf '%s\n' externally-changed > "$root/bin/agent-bridge.real"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "fresh MCP admission accepted a drifted installed binary"
case "$output" in *"fingerprint no longer matches"*) ;; *)
    fail "fresh MCP binary-drift fail-closed reason missing" ;;
esac
[ "$(sha256_fixture "$root/state/pending-admission.meta")" = "$pending_sha" ] || fail "fresh MCP binary-drift failure changed pending state"

# 30. A conflicting prebound admission receipt fails closed after journaling;
# neither the canonical pending source nor the intent may be silently retired.
new_case fresh-mcp-receipt-conflict; root="$CASE_ROOT"
candidate=ffffffffffffffffffffffffffffffffffffffff
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
pending="$root/state/pending-admission.meta"
pending_sha="$(sha256_fixture "$pending")"
lease_id="$(meta_field "$pending" lease_id)"
challenge="$(meta_field "$pending" challenge)"
receipt="$root/state/receipts/$lease_id.$challenge.fresh-mcp-admitted.meta"
printf '%s\n' tampered > "$receipt"
chmod 600 "$receipt"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "conflicting fresh MCP admission receipt was accepted"
case "$output" in *"prebound publisher receipt already exists with different content"*) ;; *)
    fail "fresh MCP conflicting-receipt fail-closed reason missing" ;;
esac
[ "$(sha256_fixture "$pending")" = "$pending_sha" ] || fail "fresh MCP receipt conflict changed pending state"
[ -f "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP receipt conflict lost its durable intent"

# 31. The committed integration path launches the exact installed executable
# and validates the real JSON-RPC initialize/list/call exchange without fixture
# substitution.
new_case fresh-mcp-live-probe; root="$CASE_ROOT"
candidate=1111111111111111111111111111111111111111
chmod 755 "$root/bin/agent-bridge.real"
write_live_mcp_executable "$root/payload-a" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "" 1 >/dev/null
receipt="$(fresh_admission_receipt "$root")" || fail "fresh MCP live-probe admission receipt missing"
[ "$(meta_field "$receipt" probe_build_git_sha)" = "${candidate:0:12}" ] || fail "fresh MCP live-probe build mismatch"
[ "$(meta_field "$receipt" probe_tool_count)" = 110 ] || fail "fresh MCP live-probe tool count mismatch"

# 32. Duplicate response ids from a controlled MCP executable are rejected;
# one later response may not overwrite another in the probe parser.
new_case fresh-mcp-live-duplicate-response; root="$CASE_ROOT"
candidate=2222222222222222222222222222222222222222
chmod 755 "$root/bin/agent-bridge.real"
write_live_mcp_executable "$root/payload-a" "${candidate:0:12}" duplicate-tools-list
run_lease "$root" install "$candidate" >/dev/null
pending_sha="$(sha256_fixture "$root/state/pending-admission.meta")"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "" 1 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "fresh MCP live probe accepted duplicate response ids"
case "$output" in *"fresh MCP admission probe failed"*) ;; *) fail "fresh MCP duplicate-response reason missing" ;; esac
[ "$(sha256_fixture "$root/state/pending-admission.meta")" = "$pending_sha" ] || fail "fresh MCP duplicate-response failure changed pending state"

# 33. The evidence digest is recomputed from the observed fields; an arbitrary
# shape-valid 64-hex value cannot be admitted by the synthetic contract lane.
new_case fresh-mcp-invalid-evidence; root="$CASE_ROOT"
candidate=3333333333333333333333333333333333333333
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" "${candidate:0:12}" aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
run_lease "$root" install "$candidate" >/dev/null
pending_sha="$(sha256_fixture "$root/state/pending-admission.meta")"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "fresh MCP admission accepted an invalid evidence digest"
case "$output" in *"probe fixture is invalid"*|*"probe receipt is invalid"*) ;; *)
    fail "fresh MCP invalid-evidence reason missing" ;;
esac
[ "$(sha256_fixture "$root/state/pending-admission.meta")" = "$pending_sha" ] || fail "fresh MCP invalid-evidence failure changed pending state"

# 34. SIGKILL after receipt/pending settlement but before lease release is
# recovered directly because admission never mutates the installed baseline.
new_case fresh-mcp-active-lease-crash; root="$CASE_ROOT"
candidate=4444444444444444444444444444444444444444
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
start_fresh_admission_holder "$root" "$probe"
[ -f "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP crash holder did not publish completion intent"
[ -f "$(fresh_admission_quarantine "$root")" ] || fail "fresh MCP crash holder did not quarantine pending state"
kill_holder_without_cleanup "$root"
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" >/dev/null
[ ! -e "$root/state/active.lock" ] || fail "fresh MCP active-lease crash recovery left an active lease"
[ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] || fail "fresh MCP active-lease crash recovery left completion intent"
[ "$(receipt_field_count "$root" disposition fresh_mcp_admission_recovered)" = 1 ] ||
    fail "fresh MCP active-lease crash recovery receipt missing"

# 35. Publisher state subdirectories are physical trust roots; a symlinked
# receipt directory is rejected before lease acquisition.
new_case publisher-state-symlink; root="$CASE_ROOT"
mkdir -p "$root/external-receipts"
ln -s "$root/external-receipts" "$root/state/receipts"
set +e
output="$(run_lease "$root" probe symlinked-state 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "publisher accepted a symlinked receipt directory"
case "$output" in *"not a physical directory"*|*"must not traverse a symlink"*) ;; *)
    fail "publisher state symlink fail-closed reason missing" ;;
esac

# 36. The live parser accepts only exact JSON-RPC 2.0 responses for the three
# nonce-derived request ids. Booleans are not integers here; wrong, unknown,
# and duplicate ids cannot be spliced into the transcript.
assert_live_probe_rejected fresh-mcp-live-wrong-jsonrpc \
    5555555555555555555555555555555555555555 wrong-jsonrpc "non-2.0 jsonrpc"
assert_live_probe_rejected fresh-mcp-live-boolean-id \
    6666666666666666666666666666666666666666 boolean-id "boolean response id"
assert_live_probe_rejected fresh-mcp-live-wrong-id \
    7777777777777777777777777777777777777777 wrong-id "wrong response id"
assert_live_probe_rejected fresh-mcp-live-unknown-id \
    8888888888888888888888888888888888888888 unknown-id "unknown response id"
assert_live_probe_rejected fresh-mcp-live-duplicate-nonce-id \
    9999999999999999999999999999999999999999 duplicate-tools-list "duplicate response id"

# 37. A JSON-RPC success envelope is not enough: capabilities must not report
# isError, content must be exactly one text block, and v0 fails closed instead
# of silently admitting a partial tools/list page.
assert_live_probe_rejected fresh-mcp-live-is-error \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab is-error "capabilities isError result"
assert_live_probe_rejected fresh-mcp-live-extra-content \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac extra-content "extra capabilities content"
assert_live_probe_rejected fresh-mcp-live-next-cursor \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaad next-cursor "paginated tools/list result"

# 38. The admission controller must use the fixed trusted interpreter in
# isolated mode and give the child a minimal environment. A PATH-resolved
# python shim and PYTHONPATH/sitecustomize payload must never execute.
new_case fresh-mcp-hostile-python-environment; root="$CASE_ROOT"
candidate=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaae
marker="$root/hostile-python.marker"
write_hostile_python_environment "$root"
chmod 755 "$root/bin/agent-bridge.real"
write_live_mcp_executable "$root/payload-a" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
PATH="$root/hostile-bin:$PATH" \
PYTHONPATH="$root/hostile-pythonpath" \
HOSTILE_PYTHON_MARKER="$marker" \
    run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "" 1 >/dev/null
[ ! -e "$marker" ] || fail "hostile PATH/PYTHONPATH executed during fresh MCP admission"
receipt="$(fresh_admission_receipt "$root")" || fail "isolated-interpreter admission receipt missing"
[ "$(meta_field "$receipt" probe_method)" = independent_stdio_private_exact_binary_copy ] ||
    fail "isolated-interpreter receipt did not record private exact-copy method"
[ "$(meta_field "$receipt" probe_copied_binary_sha256)" = "$(meta_field "$receipt" installed_binary_sha256)" ] ||
    fail "private probe copy is not bound to the installed binary digest"

# 39. Output and wall-clock bounds fail closed before intent publication. The
# timeout override is test-only; the production limit remains fixed in the
# admission implementation.
FRESH_MCP_TEST_STDOUT_LIMIT_BYTES=1024 assert_live_probe_rejected fresh-mcp-live-oversized-output \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaf oversized-output "oversized MCP output"
unset FRESH_MCP_TEST_STDOUT_LIMIT_BYTES
FRESH_MCP_TEST_TIMEOUT_SECONDS=1 assert_live_probe_rejected fresh-mcp-live-timeout \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaba slow "MCP response timeout"
unset FRESH_MCP_TEST_TIMEOUT_SECONDS

# 40. A deterministic settled-intent archive is itself replay-idempotent when
# its physical mode-600 content is exact. Conflicts and symlinks remain durable
# fail-closed states rather than causing the canonical intent to disappear.
new_case fresh-mcp-settled-intent-replay; root="$CASE_ROOT"
candidate=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabb
probe="$root/fresh-probe.meta"
write_fresh_mcp_probe_fixture "$probe" "${candidate:0:12}"
run_lease "$root" install "$candidate" >/dev/null
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" >/dev/null
settled_intent="$(fresh_admission_settled_intent "$root")" || fail "settled-intent replay fixture missing"
settled_sha="$(sha256_fixture "$settled_intent")"
cp "$settled_intent" "$root/state/fresh-mcp-admission-intent.meta"
chmod 600 "$root/state/fresh-mcp-admission-intent.meta"
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" >/dev/null
[ ! -e "$root/state/fresh-mcp-admission-intent.meta" ] || fail "exact settled-intent replay left canonical intent"
[ "$(sha256_fixture "$settled_intent")" = "$settled_sha" ] || fail "exact settled-intent replay changed archive"

# A nonce or pending-context edit must invalidate the intent's complete
# admission binding; neither edit may be accepted as a display-only change.
for tampered_key in probe_nonce pending_challenge; do
    awk -F= -v key="$tampered_key" '
        BEGIN { OFS="=" }
        $1 == key { $2="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" }
        { print }
    ' "$settled_intent" > "$root/intent.tampered"
    chmod 600 "$root/intent.tampered"
    mv "$root/intent.tampered" "$root/state/fresh-mcp-admission-intent.meta"
    set +e
    output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
    status=$?
    set -e
    [ "$status" -ne 0 ] || fail "fresh MCP intent accepted tampered $tampered_key binding context"
    [ -f "$root/state/fresh-mcp-admission-intent.meta" ] || fail "tampered $tampered_key intent was retired"
    rm "$root/state/fresh-mcp-admission-intent.meta"
done

cp "$settled_intent" "$root/state/fresh-mcp-admission-intent.meta"
printf '%s\n' conflict >> "$settled_intent"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "conflicting settled-intent archive was accepted"
case "$output" in *"settled-intent target conflicts with canonical intent"*) ;; *)
    fail "settled-intent conflict fail-closed reason missing" ;;
esac
[ -f "$root/state/fresh-mcp-admission-intent.meta" ] || fail "settled-intent conflict lost canonical intent"
rm "$settled_intent"
ln -s "$root/state/fresh-mcp-admission-intent.meta" "$settled_intent"
set +e
output="$(run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "$probe" 2>&1)"
status=$?
set -e
[ "$status" -ne 0 ] || fail "symlinked settled-intent archive was accepted"
case "$output" in *"settled-intent target is not an exact physical mode-600 file"*) ;; *)
    fail "settled-intent symlink fail-closed reason missing" ;;
esac
[ -f "$root/state/fresh-mcp-admission-intent.meta" ] || fail "settled-intent symlink lost canonical intent"

# 41. The durable receipt binds the random probe transcript to both publisher
# lease contexts and the complete pending/install fingerprint, not merely to a
# display summary of MCP identity.
receipt="$(fresh_admission_receipt "$root")" || fail "binding receipt fixture missing"
for key in pending_lease_id pending_challenge candidate_commit installed_binary_sha256 \
        installed_binary_inode installed_binary_mode installed_assets_sha256 \
        admission_lease_id admission_challenge probe_nonce probe_started_at probe_finished_at \
        probe_copied_binary_sha256 probe_evidence_sha256 admission_binding_sha256 receipt_binding_sha256; do
    [ -n "$(meta_field "$receipt" "$key")" ] || fail "fresh MCP receipt omitted binding field $key"
done
[ "$(meta_field "$receipt" probe_copied_binary_sha256)" = "$(meta_field "$receipt" installed_binary_sha256)" ] ||
    fail "fresh MCP receipt copy digest is not exact-installed bound"

# 42. JSON text with duplicate object keys is ambiguous even when both values
# are identical. Reject duplicate envelope id/result keys and recursively reject
# duplicate keys inside the capabilities text payload.
assert_live_probe_rejected fresh-mcp-live-duplicate-object-id \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabc duplicate-object-id "duplicate JSON object id key"
assert_live_probe_rejected fresh-mcp-live-duplicate-object-result \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabd duplicate-object-result "duplicate JSON object result key"
assert_live_probe_rejected fresh-mcp-live-duplicate-capabilities-key \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabe duplicate-capabilities-key "duplicate capabilities payload key"

# 43. Process-group custody includes descendants. Whether the direct MCP parent
# exits normally, times out, or exceeds stderr bounds, its same-group child must
# be gone before the admission controller returns. Markers and PIDs live only in
# this case's disposable test root, and the suite cleanup is a final safety net.
new_case fresh-mcp-descendant-normal-exit; root="$CASE_ROOT"
candidate=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabf
write_live_mcp_executable "$root/payload-a" "${candidate:0:12}" descendant-normal
run_lease "$root" install "$candidate" >/dev/null
run_lease "$root" admit-fresh-mcp ignored "$root/payload-a" "" 1 >/dev/null
assert_descendant_reaped "$root/payload-a.descendant.pid" "normal MCP parent exit"
fresh_admission_receipt "$root" >/dev/null || fail "normal parent exit with descendant was not admitted"

FRESH_MCP_TEST_TIMEOUT_SECONDS=1 assert_live_probe_rejected fresh-mcp-descendant-timeout \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaacb descendant-timeout "MCP descendant timeout"
unset FRESH_MCP_TEST_TIMEOUT_SECONDS
assert_descendant_reaped "$CASE_ROOT/payload-a.descendant.pid" "timed-out MCP parent"

assert_live_probe_rejected fresh-mcp-descendant-stderr-limit \
    aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaacc descendant-stderr-limit "MCP descendant stderr overflow"
assert_descendant_reaped "$CASE_ROOT/payload-a.descendant.pid" "stderr-over-limit MCP parent"

printf '%s\n' publisher-lease-v0-ok
