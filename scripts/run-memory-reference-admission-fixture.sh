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

# Strip project/operator/compiler overrides. In particular, an AB_* sentinel
# supplied by the gate must disappear before the Rust example starts. Keep the
# launch allowlist deliberately small and use the shell's built-in variable
# list rather than an env wrapper (some launchers swallow child stdout when an
# env process is inserted).
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
  --example memory_reference_admission_fixture -- "$fixture_path"
