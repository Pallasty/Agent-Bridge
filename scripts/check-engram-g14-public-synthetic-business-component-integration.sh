#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

toolchain="1.96.0"
guest_manifest="scripts/eval/fixtures/engram_g14_business_component_contract_v0/component/Cargo.toml"
scratch="$(mktemp -d)"
cleanup() { rm -rf "$scratch"; }
trap cleanup EXIT

bash -n "$0"

CARGO_NET_OFFLINE=true cargo +"$toolchain" build --release --offline --locked \
  --manifest-path "$guest_manifest" \
  --target wasm32-wasip2 \
  --target-dir "$scratch/guest-target"

component="$scratch/guest-target/wasm32-wasip2/release/g14_business_probe.wasm"
component_sha256="$(shasum -a 256 "$component" | awk '{print $1}')"

host_binary="${AB_G14_HOST_BINARY:-target/release/agent-bridge}"
if [[ ! -x "$host_binary" ]]; then
  CARGO_NET_OFFLINE=true cargo +"$toolchain" build --release --offline --locked \
    -p ab-bridge \
    --no-default-features \
    --features g14-wasi-component-runtime \
    --target-dir "$scratch/host-target"
  host_binary="$scratch/host-target/release/agent-bridge"
fi

output="$scratch/output.json"
"$host_binary" \
  g14-wasi-business-component \
  --artifact "$component" \
  --sha256 "$component_sha256" >"$output"

python3 - "$output" <<'PY'
import json
import sys

value = json.load(open(sys.argv[1], encoding="utf-8"))
expected = {
    "revision": 7,
    "entity-count": 12,
    "occupied-cells": 9,
    "transition-count": 4,
    "occupancy-per-mille": 750,
    "report-code": "WORLD_STATE_V0",
}
assert value == expected, value
print("business component host integration: PASS")
PY

if "$host_binary" \
  g14-wasi-business-component \
  --artifact "$component" \
  --sha256 "0000000000000000000000000000000000000000000000000000000000000000" \
  >"$scratch/bad-sha.out" 2>"$scratch/bad-sha.err"; then
  echo "expected bad component SHA to fail closed" >&2
  exit 1
fi
grep -q "component SHA-256 mismatch" "$scratch/bad-sha.err"

if rg -n \
  'G14WasiBusinessComponent|execute_business_transform' \
  crates/bridge/src/mcp_tools.rs crates/bridge/src/daemon_http.rs; then
  echo "business component integration leaked into MCP or daemon-http surface" >&2
  exit 1
fi

echo "engram G1.4 public synthetic business component construction/host integration: PASS (explicit CLI only)"
