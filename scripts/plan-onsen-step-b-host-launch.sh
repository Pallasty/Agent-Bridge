#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

source_fixture="docs/design/fixtures/biocortex-retrieval-onsen-step-b-source-resolution-2026-06-15.json"
source_probe_script="scripts/probe-onsen-step-b-host-source.sh"
checkout=""
probe_json=""
host=""
port=""
out=""
no_remote=0

usage() {
    cat <<'USAGE'
usage: scripts/plan-onsen-step-b-host-launch.sh [flags]

Builds a read-only launch plan for the accepted onsen Step B LSWR dev host.
It never starts Godot or any host process.

Flags:
  --checkout PATH     Candidate onsen Step B checkout.
  --probe-json PATH   Existing source-probe JSON to consume instead of probing.
  --host HOST         Expected loopback host. Forwarded to the source probe.
  --port N            Expected dev host port. Forwarded to the source probe.
  --no-remote         Skip git remote probes when running the source probe.
  --out PATH          Write JSON report to PATH.
  -h, --help          Show this help.

The plan is intentionally conservative: Agent-Bridge is only the TCP client of
the accepted Step B host. Host launch remains an operator/onsen-runtime action.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --checkout) checkout="$2"; shift 2 ;;
        --probe-json) probe_json="$2"; shift 2 ;;
        --host) host="$2"; shift 2 ;;
        --port) port="$2"; shift 2 ;;
        --no-remote) no_remote=1; shift ;;
        --out) out="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! -f "$source_fixture" ]]; then
    echo "required fixture not found: $source_fixture" >&2
    exit 2
fi

if [[ ! -x "$source_probe_script" ]]; then
    echo "required executable source probe not found: $source_probe_script" >&2
    exit 2
fi

tmp_probe=""
cleanup() {
    if [[ -n "$tmp_probe" ]]; then
        rm -f "$tmp_probe"
    fi
}
trap cleanup EXIT

if [[ -n "$probe_json" ]]; then
    if [[ ! -f "$probe_json" ]]; then
        echo "--probe-json not found: $probe_json" >&2
        exit 2
    fi
else
    tmp_probe="$(mktemp "${TMPDIR:-/tmp}/ab-onsen-step-b-source-probe-XXXXXX.json")"
    probe_args=(--out "$tmp_probe")
    if [[ -n "$checkout" ]]; then
        probe_args+=(--checkout "$checkout")
    fi
    if [[ -n "$host" ]]; then
        probe_args+=(--host "$host")
    fi
    if [[ -n "$port" ]]; then
        probe_args+=(--port "$port")
    fi
    if [[ "$no_remote" -eq 1 ]]; then
        probe_args+=(--no-remote)
    fi
    "$source_probe_script" "${probe_args[@]}"
    probe_json="$tmp_probe"
fi

jq -e '.schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_source_probe.v0"' "$probe_json" >/dev/null

source_status="$(jq -r '.status' "$probe_json")"
source_found="$(jq -r '.result.source_found' "$probe_json")"
ready_for_live_probe="$(jq -r '.result.ready_for_live_probe' "$probe_json")"
checkout_path="$(jq -r '.checkout.path' "$probe_json")"
manifest_kind="$(jq -r '.checkout.manifest_kind' "$probe_json")"
endpoint_host="$(jq -r '.expected.endpoint.host' "$probe_json")"
endpoint_port="$(jq -r '.expected.endpoint.port' "$probe_json")"
expected_branch="$(jq -r '.expected.branch' "$probe_json")"
expected_head="$(jq -r '.expected.head' "$probe_json")"

if [[ "$ready_for_live_probe" == "true" ]]; then
    plan_status="ready_for_live_world_visibility_query_probe"
    launch_action="host_already_listening"
    next_step="rerun_live_world_visibility_query_probe"
elif [[ "$source_found" == "true" ]]; then
    plan_status="ready_for_operator_host_launch"
    launch_action="operator_launch_accepted_onsen_step_b_dev_host"
    next_step="launch_onsen_step_b_newline_json_tcp_dev_host_then_rerun_probe"
else
    plan_status="blocked_missing_onsen_step_b_source"
    launch_action="none"
    next_step="provide_or_sync_onsen_step_b_checkout_or_repository_url"
fi

report="$(jq -n \
    --arg schema "agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0" \
    --arg status "$plan_status" \
    --arg source_fixture "$source_fixture" \
    --arg source_probe_json "$probe_json" \
    --arg source_probe_script "$source_probe_script" \
    --arg source_status "$source_status" \
    --arg checkout "$checkout_path" \
    --arg manifest_kind "$manifest_kind" \
    --arg host "$endpoint_host" \
    --argjson port "$endpoint_port" \
    --arg expected_branch "$expected_branch" \
    --arg expected_head "$expected_head" \
    --arg launch_action "$launch_action" \
    --arg next_step "$next_step" \
    --argjson source_found "$source_found" \
    --argjson ready_for_live_probe "$ready_for_live_probe" \
    '{
        schema: $schema,
        status: $status,
        read_only: true,
        source_fixture: $source_fixture,
        source_probe: {
            script: $source_probe_script,
            json: $source_probe_json,
            status: $source_status,
            source_found: $source_found,
            ready_for_live_probe: $ready_for_live_probe
        },
        accepted_source: {
            checkout: $checkout,
            branch: $expected_branch,
            head: $expected_head,
            manifest_kind: $manifest_kind
        },
        expected_host: {
            host: $host,
            port: $port,
            protocol: "newline_json_tcp",
            required_world_tool: "world_visibility_query"
        },
        launch_plan: {
            action: $launch_action,
            operator_action_required: ($status == "ready_for_operator_host_launch"),
            agent_bridge_starts_host: false,
            dev_or_probe_flag_required: true,
            onsen_runtime_must_own_launch: true,
            suggested_manual_checks: [
                "launch accepted onsen Step B checkout with its dev/probe flag enabled",
                "confirm the newline-JSON TCP host listens on the expected loopback endpoint",
                "rerun scripts/probe-onsen-step-b-host-source.sh --strict against the checkout",
                "then collect live world_visibility_query evidence through Agent-Bridge"
            ]
        },
        next_commands: {
            source_probe_strict: ("scripts/probe-onsen-step-b-host-source.sh --strict --checkout " + $checkout),
            live_probe_after_host_launch: "run Agent-Bridge world_visibility_query with AGENT_BRIDGE_TOOL_PROFILE=all against the expected endpoint"
        },
        boundary: {
            starts_host: false,
            clones_repository: false,
            executes_lswr_actions: false,
            calls_memory_search: false,
            runs_biocortex: false,
            writes_approval: false,
            changes_memory_search_order: false,
            default_search_order_change_allowed: false,
            calls_aiot_runtime: false,
            emits_durable_runtime_action_result: false,
            mutates_default_agent_bridge_db: false,
            host_response_included: false,
            raw_queries_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_raw_included: false,
            human_decision_text_included: false
        },
        next_step: $next_step
    }')"

if [[ -n "$out" ]]; then
    mkdir -p "$(dirname "$out")"
    printf '%s\n' "$report" > "$out"
else
    printf '%s\n' "$report"
fi
