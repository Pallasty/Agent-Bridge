#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 FIXTURE_JSON" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
fixture_path="$(realpath "$1")"

if [[ ! -f "$fixture_path" ]]; then
  echo "reference admission fixture does not exist: $fixture_path" >&2
  exit 2
fi

# The fixture is source-bound: tracked edits or index changes make the binary
# and the receipt ambiguous. Untracked files outside the runner inputs remain
# allowed so a pre-existing local cache cannot masquerade as source drift.
if ! git -C "$repo_root" diff --quiet -- . || ! git -C "$repo_root" diff --cached --quiet -- .; then
  echo "reference admission runner requires a clean tracked worktree" >&2
  exit 3
fi

# Strip the entire exported parent environment with shell builtins. The exec
# harness used by this repository loses captured stdout when an `env -i`
# process is inserted, so an explicit exported-variable reset provides the same
# allowlist boundary without an intermediate process. Capture only toolchain
# paths first; all other inherited values, including the gate's poison
# sentinels and compiler/project overrides, are removed.
runner_path="${PATH:?}"
runner_home="${HOME:-/tmp}"
runner_cargo_home="${CARGO_HOME:-$runner_home/.cargo}"
runner_rustup_home="${RUSTUP_HOME:-$runner_home/.rustup}"
while IFS= read -r name; do
  unset "$name" 2>/dev/null || true
done < <(compgen -e)

export PATH="$runner_path"
export HOME="$runner_home"
export CARGO_HOME="$runner_cargo_home"
export RUSTUP_HOME="$runner_rustup_home"
export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export CARGO_NET_OFFLINE=true
export CARGO_TARGET_DIR="$repo_root/target/reference-admission"
export CARGO_TERM_COLOR=never
export AB_BOOTSTRAP_SURFACING_DISABLE=1
export AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE=0
export AGENT_BRIDGE_CORRECTION_COSURFACE=0
export AGENT_BRIDGE_OUTCOME_COLLECTOR=0
export AGENT_BRIDGE_RECALL_SEMANTIC_FALLBACK=0
export AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval
export AGENT_BRIDGE_SEED_BOOST_DISABLE=1
export LC_ALL=C
export TZ=UTC
exec cargo run --offline --locked -j 1 -p ab-store --no-default-features \
  --example memory_reference_admission_fixture -- "$fixture_path"
