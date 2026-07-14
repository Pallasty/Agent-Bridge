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
# query-only. The shell's built-in variable list is used instead of an
# `env ... command` wrapper because some launchers lose child stdout when an
# `env` process is involved, which would defeat receipt auditing. The
# allowlisted process still has no retrieval knobs.
runner_path="${PATH:?}"
runner_home="${HOME:-/tmp}"
runner_cargo_home="${CARGO_HOME:-$runner_home/.cargo}"
runner_rustup_home="${RUSTUP_HOME:-$runner_home/.rustup}"
while IFS= read -r name; do
  case "$name" in
    AB_*|AGENT_BRIDGE_*|RUSTFLAGS|RUSTDOCFLAGS|RUSTC_WRAPPER|RUSTC_WORKSPACE_WRAPPER|CARGO_ENCODED_RUSTFLAGS|RUST_LOG|LD_PRELOAD)
      unset "$name"
      ;;
  esac
done < <(compgen -v)

export PATH="$runner_path"
export HOME="$runner_home"
export CARGO_HOME="$runner_cargo_home"
export RUSTUP_HOME="$runner_rustup_home"
export CARGO_BUILD_JOBS=1
export CARGO_TARGET_DIR="$repo_root/target"
export LC_ALL=C
export TZ=UTC
exec cargo run --offline --locked -j 1 -p ab-store --no-default-features \
  --example memory_reference_s0 -- "$request_path"
