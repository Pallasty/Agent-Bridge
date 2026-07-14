#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir/.." rev-parse --show-toplevel)"
fixture="$repo_root/scripts/eval/fixtures/biocortex_ab_reference_admission_v0.json"
expected="$repo_root/scripts/eval/fixtures/biocortex_ab_reference_admission.expected.v0.tsv"
runner="$repo_root/scripts/run-memory-reference-admission-fixture.sh"

for path in "$fixture" "$expected" "$runner"; do
  [[ -f "$path" && ! -L "$path" ]] || {
    echo "required reference admission member is missing or symlinked: $path" >&2
    exit 1
  }
done
[[ "$(stat -c '%a' "$runner")" == 755 ]] || {
  echo "reference admission runner must be executable" >&2
  exit 1
}

if ! git -C "$repo_root" diff --quiet -- . || ! git -C "$repo_root" diff --cached --quiet -- .; then
  echo "reference admission gate requires a clean tracked worktree" >&2
  exit 3
fi

head_before="$(git -C "$repo_root" rev-parse --verify HEAD^{commit})"
status_before="$(git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
tmp="$(mktemp -d)"
cleanup() {
  chmod -R u+w "$tmp" 2>/dev/null || true
  rm -rf "$tmp"
}
trap cleanup EXIT

run_once() {
  local output="$1" error="$2"
  AB_REFERENCE_ADMISSION_SENTINEL=poison \
    AGENT_BRIDGE_REFERENCE_ADMISSION_SENTINEL=poison \
    RUST_LOG=trace \
    "$runner" "$fixture" >"$output" 2>"$error"
}

run_once "$tmp/run-one.tsv" "$tmp/run-one.err"
run_once "$tmp/run-two.tsv" "$tmp/run-two.err"
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/run-two.tsv" || {
  echo "reference admission runner is nondeterministic" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$expected" || {
  echo "reference admission receipt drifted" >&2
  exit 1
}

head_after="$(git -C "$repo_root" rev-parse --verify HEAD^{commit})"
status_after="$(git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ "$head_after" == "$head_before" ]] || {
  echo "HEAD changed while the reference admission fixture ran" >&2
  exit 1
}
[[ "$status_after" == "$status_before" ]] || {
  echo "worktree changed while the reference admission fixture ran" >&2
  exit 1
}
git -C "$repo_root" diff --quiet -- . || {
  echo "tracked worktree drifted while the reference admission fixture ran" >&2
  exit 1
}
git -C "$repo_root" diff --cached --quiet -- . || {
  echo "index drifted while the reference admission fixture ran" >&2
  exit 1
}

fixture_sha256="$(sha256sum "$fixture" | awk '{print $1}')"
receipt_sha256="$(sha256sum "$expected" | awk '{print $1}')"
printf 'BOUND_TO_HEAD_BIOCORTEX_AB_REFERENCE_ADMISSION_FIXTURE\n'
printf 'head=%s\n' "$head_before"
printf 'fixture_sha256=%s\n' "$fixture_sha256"
printf 'receipt_sha256=%s\n' "$receipt_sha256"
printf 'fresh_clones=3\n'
printf 'repeated_runs=2\n'
printf 'real_capture_authorized=false\n'
printf 'decision=BLOCKED_FAIL_CLOSED\n'
