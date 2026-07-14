#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 REQUEST_JSON" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
request_path="$(realpath "$1")"

if [[ ! -f "$request_path" ]]; then
  echo "reference request does not exist: $request_path" >&2
  exit 2
fi

# A reference run must be reproducible from committed source. Untracked files
# are allowed outside the runner inputs; tracked edits and index changes are
# not, because they would make the binary identity ambiguous.
if ! git -C "$repo_root" diff --quiet -- . || ! git -C "$repo_root" diff --cached --quiet -- .; then
  echo "reference runner requires a clean tracked worktree" >&2
  exit 3
fi

# Do not inherit AB_/AGENT_BRIDGE_ feature flags, project aliases, sidecars,
# semantic knobs, operator overrides, or compiler/logging overrides. The
# request binds the DB, clock and budgets explicitly; the example opens the DB
# query-only. Only the toolchain locations needed for an offline build cross
# the boundary; no parent retrieval or project configuration is inherited.
exec env -i \
  PATH="${PATH:?}" \
  HOME="${HOME:-/tmp}" \
  CARGO_HOME="${CARGO_HOME:-${HOME:-/tmp}/.cargo}" \
  RUSTUP_HOME="${RUSTUP_HOME:-${HOME:-/tmp}/.rustup}" \
  CARGO_BUILD_JOBS=1 \
  CARGO_INCREMENTAL=0 \
  CARGO_NET_OFFLINE=true \
  CARGO_TARGET_DIR="$repo_root/target/reference-s0" \
  CARGO_TERM_COLOR=never \
  AB_BOOTSTRAP_SURFACING_DISABLE=1 \
  AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE=0 \
  AGENT_BRIDGE_CORRECTION_COSURFACE=0 \
  AGENT_BRIDGE_OUTCOME_COLLECTOR=0 \
  AGENT_BRIDGE_RECALL_SEMANTIC_FALLBACK=0 \
  AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval \
  AGENT_BRIDGE_SEED_BOOST_DISABLE=1 \
  LC_ALL=C \
  TZ=UTC \
  cargo run --offline --locked -j 1 -p ab-store --no-default-features \
    --example memory_reference_s0 -- "$request_path"
