#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

fixture="docs/design/fixtures/biocortex-retrieval-onsen-step-b-source-resolution-2026-06-15.json"
checkout=""
host=""
port=""
out=""
strict=0
no_remote=0
repos=()

usage() {
    cat <<'USAGE'
usage: scripts/probe-onsen-step-b-host-source.sh [flags]

Checks whether the accepted onsen Step B LSWR host source is available and
whether the expected newline-JSON TCP dev host is listening.

Flags:
  --checkout PATH     Candidate onsen Step B checkout. Defaults to fixture path.
  --repo URL          Candidate git remote to probe with git ls-remote. Repeatable.
  --no-remote        Skip git remote probes.
  --host HOST         Expected loopback host. Defaults to fixture endpoint host.
  --port N            Expected dev host port. Defaults to fixture endpoint port.
  --out PATH          Write JSON report to PATH.
  --strict            Exit 1 when the source or listener is missing.
  -h, --help          Show this help.

This probe is read-only except for --out. It never clones, starts a host,
executes LSWR actions, calls memory_search, runs BioCortex, writes approval
state, or mutates the default Agent-Bridge DB.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --checkout) checkout="$2"; shift 2 ;;
        --repo) repos+=("$2"); shift 2 ;;
        --host) host="$2"; shift 2 ;;
        --port) port="$2"; shift 2 ;;
        --out) out="$2"; shift 2 ;;
        --strict) strict=1; shift ;;
        --no-remote) no_remote=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! -f "$fixture" ]]; then
    echo "required fixture not found: $fixture" >&2
    exit 2
fi

expected_branch="$(jq -r '.accepted_onsen_step_b_runtime.documented_branch' "$fixture")"
expected_head="$(jq -r '.accepted_onsen_step_b_runtime.documented_head' "$fixture")"
expected_endpoint="$(jq -r '.accepted_onsen_step_b_runtime.expected_endpoint' "$fixture")"
default_checkout="$(jq -r '.local_resolution.linux_candidate_worktree' "$fixture")"
default_host="${expected_endpoint%:*}"
default_port="${expected_endpoint##*:}"

if [[ -z "$checkout" ]]; then
    checkout="$default_checkout"
fi
if [[ -z "$host" ]]; then
    host="$default_host"
fi
if [[ -z "$port" ]]; then
    port="$default_port"
fi

case "$host" in
    127.0.0.1|localhost|::1) ;;
    *)
        echo "--host must be loopback for this Step B probe: $host" >&2
        exit 2
        ;;
esac

if [[ ! "$port" =~ ^[0-9]+$ ]] || [[ "$port" -lt 1 || "$port" -gt 65535 ]]; then
    echo "--port must be an integer in 1..65535" >&2
    exit 2
fi

if [[ "$no_remote" -eq 0 && "${#repos[@]}" -eq 0 ]]; then
    while IFS= read -r repo_url; do
        [[ -n "$repo_url" ]] && repos+=("$repo_url")
    done < <(jq -r '.remote_resolution.git_ssh_candidates[].url' "$fixture")
fi

checkout_present=false
checkout_is_git=false
checkout_branch=""
checkout_head=""
checkout_head_matches=false
checkout_branch_matches=false
checkout_manifest_kind="none"

if [[ -d "$checkout" ]]; then
    checkout_present=true
    if git -C "$checkout" rev-parse --git-dir >/dev/null 2>&1; then
        checkout_is_git=true
        checkout_branch="$(git -C "$checkout" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
        checkout_head="$(git -C "$checkout" rev-parse --short HEAD 2>/dev/null || true)"
        if [[ "$checkout_branch" == "$expected_branch" ]]; then
            checkout_branch_matches=true
        fi
        if [[ "$checkout_head" == "$expected_head"* ]]; then
            checkout_head_matches=true
        fi
    fi
    if [[ -f "$checkout/package.json" ]]; then
        checkout_manifest_kind="package_json"
    elif [[ -f "$checkout/Cargo.toml" ]]; then
        checkout_manifest_kind="cargo_toml"
    elif [[ -f "$checkout/Makefile" ]]; then
        checkout_manifest_kind="makefile"
    fi
fi

port_listening=false
if timeout 1 bash -c ':</dev/tcp/"$0"/"$1"' "$host" "$port" >/dev/null 2>&1; then
    port_listening=true
fi

repo_results_file="$(mktemp "${TMPDIR:-/tmp}/ab-onsen-step-b-repos-XXXXXX.jsonl")"
trap 'rm -f "$repo_results_file"' EXIT

if [[ "$no_remote" -eq 0 ]]; then
    for repo_url in "${repos[@]}"; do
        tmp_out="$(mktemp "${TMPDIR:-/tmp}/ab-onsen-step-b-lsremote-XXXXXX.txt")"
        if timeout 15 git ls-remote "$repo_url" HEAD "refs/heads/$expected_branch" >"$tmp_out" 2>&1; then
            if [[ -s "$tmp_out" ]]; then
                if grep -Fq "refs/heads/$expected_branch" "$tmp_out"; then
                    result="reachable_expected_branch_found"
                elif grep -Fq "$expected_head" "$tmp_out"; then
                    result="reachable_expected_head_found"
                else
                    result="reachable_but_not_accepted_step_b_source"
                fi
            else
                result="reachable_no_matching_ref"
            fi
        else
            result="not_found_or_inaccessible"
        fi
        jq -cn \
            --arg url "$repo_url" \
            --arg result "$result" \
            --arg preview "$(head -n 1 "$tmp_out" | tr -d '\r')" \
            '{url: $url, result: $result, preview: $preview}' >> "$repo_results_file"
        rm -f "$tmp_out"
    done
fi

remote_usable=false
if jq -s -e '
    any(.[]; .result == "reachable_expected_branch_found"
        or .result == "reachable_expected_head_found")
' "$repo_results_file" >/dev/null; then
    remote_usable=true
fi

source_found=false
if [[ "$checkout_branch_matches" == true || "$checkout_head_matches" == true ]]; then
    source_found=true
elif [[ "$remote_usable" == true ]]; then
    source_found=true
fi

if [[ "$source_found" == true && "$port_listening" == true ]]; then
    status="ready_for_live_world_visibility_query_probe"
elif [[ "$source_found" == true ]]; then
    status="source_found_host_not_listening"
else
    status="blocked_missing_onsen_step_b_source"
fi

report="$(jq -n \
    --arg schema "agent_bridge.biocortex_retrieval.onsen_step_b_host_source_probe.v0" \
    --arg fixture "$fixture" \
    --arg status "$status" \
    --arg checkout "$checkout" \
    --arg expected_branch "$expected_branch" \
    --arg expected_head "$expected_head" \
    --arg checkout_branch "$checkout_branch" \
    --arg checkout_head "$checkout_head" \
    --arg checkout_manifest_kind "$checkout_manifest_kind" \
    --arg host "$host" \
    --argjson port "$port" \
    --argjson checkout_present "$checkout_present" \
    --argjson checkout_is_git "$checkout_is_git" \
    --argjson checkout_branch_matches "$checkout_branch_matches" \
    --argjson checkout_head_matches "$checkout_head_matches" \
    --argjson port_listening "$port_listening" \
    --argjson remote_attempted "$([[ "$no_remote" -eq 0 ]] && echo true || echo false)" \
    --argjson remote_usable "$remote_usable" \
    --argjson source_found "$source_found" \
    --slurpfile repos "$repo_results_file" \
    '{
        schema: $schema,
        status: $status,
        read_only: true,
        source_fixture: $fixture,
        expected: {
            branch: $expected_branch,
            head: $expected_head,
            endpoint: { host: $host, port: $port, protocol: "newline_json_tcp" },
            world_tool: "world_visibility_query"
        },
        checkout: {
            path: $checkout,
            present: $checkout_present,
            is_git: $checkout_is_git,
            branch: $checkout_branch,
            head: $checkout_head,
            branch_matches_expected: $checkout_branch_matches,
            head_matches_expected: $checkout_head_matches,
            manifest_kind: $checkout_manifest_kind
        },
        remote_resolution: {
            attempted: $remote_attempted,
            usable_remote_found: $remote_usable,
            candidates: $repos
        },
        listener: {
            host: $host,
            port: $port,
            listening: $port_listening
        },
        result: {
            source_found: $source_found,
            ready_for_live_probe: ($source_found and $port_listening),
            blocked_by: (if $source_found then "host_not_listening" else "missing_checkout_or_accessible_repository_url" end),
            next_step: (if $source_found and $port_listening then "rerun_live_world_visibility_query_probe" elif $source_found then "launch_onsen_step_b_newline_json_tcp_dev_host" else "provide_or_sync_onsen_step_b_checkout_or_repository_url" end)
        },
        boundary: {
            clones_repository: false,
            starts_host: false,
            calls_memory_search: false,
            runs_biocortex: false,
            writes_approval: false,
            changes_memory_search_order: false,
            default_search_order_change_allowed: false,
            calls_aiot_runtime: false,
            executes_lswr_actions: false,
            emits_durable_runtime_action_result: false,
            mutates_default_agent_bridge_db: false,
            host_response_included: false,
            raw_queries_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_raw_included: false,
            human_decision_text_included: false
        }
    }')"

if [[ -n "$out" ]]; then
    mkdir -p "$(dirname "$out")"
    printf '%s\n' "$report" > "$out"
else
    printf '%s\n' "$report"
fi

if [[ "$strict" -eq 1 && "$status" != "ready_for_live_world_visibility_query_probe" ]]; then
    exit 1
fi
