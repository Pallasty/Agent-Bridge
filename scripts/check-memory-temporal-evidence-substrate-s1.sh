#!/usr/bin/env -S -i /usr/bin/bash
# Clean-HEAD gate for the public, synthetic S1 evidence-substrate design packet.

set -euo pipefail

while IFS= read -r imported_function; do
  builtin unset -f "$imported_function"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null
unset BASH_ENV ENV CDPATH PERL5OPT PERL5LIB PERL_UNICODE
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
unset GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS GIT_NAMESPACE
unset GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
unset LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD

script_dir="$(cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(/usr/bin/git -C "$script_dir/.." rev-parse --show-toplevel)"
contract_rel="scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_contract_v0.json"
fixture_rel="scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_synthetic_v0.json"
expected_rel="scripts/eval/fixtures/memory_temporal_evidence_substrate_s1.expected.v0.tsv"
checker_rel="scripts/eval/check_memory_temporal_evidence_substrate_s1.py"
gate_rel="scripts/check-memory-temporal-evidence-substrate-s1.sh"
design_rel="docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S1_2026_07_14.md"
report_rel="docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s1.md"

paths=(
  "$contract_rel"
  "$fixture_rel"
  "$expected_rel"
  "$checker_rel"
  "$gate_rel"
  "$design_rel"
  "$report_rel"
)
modes=(100644 100644 100644 100644 100755 100644 100644)
for index in "${!paths[@]}"; do
  path="${paths[$index]}"
  absolute="$repo_root/$path"
  [[ -f "$absolute" && ! -L "$absolute" ]] || {
    echo "S1 packet member is missing or symlinked: $path" >&2
    exit 1
  }
  actual_mode="$(/usr/bin/git -C "$repo_root" ls-tree HEAD -- "$path" | /usr/bin/awk '{print $1}')"
  [[ "$actual_mode" == "${modes[$index]}" ]] || {
    echo "S1 packet mode drifted for $path: $actual_mode" >&2
    exit 1
  }
done

status_before="$(/usr/bin/git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ -z "$status_before" ]] || {
  echo "S1 design gate requires a clean worktree and index" >&2
  exit 3
}
head_before="$(/usr/bin/git -C "$repo_root" rev-parse --verify HEAD^{commit})"

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "$tmp" 2>/dev/null || true
  /usr/bin/rm -rf "$tmp"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "$tmp/home" "$tmp/snapshot"

for path in "${paths[@]}"; do
  target="$tmp/snapshot/$path"
  /usr/bin/mkdir -p "$(/usr/bin/dirname "$target")"
  /usr/bin/git -C "$repo_root" cat-file blob "$head_before:$path" >"$target"
done

sha() {
  /usr/bin/sha256sum "$1" | /usr/bin/awk '{print $1}'
}

for path in "$design_rel" "$contract_rel" "$fixture_rel" "$checker_rel" "$expected_rel" "$gate_rel"; do
  digest="$(sha "$tmp/snapshot/$path")"
  /usr/bin/grep -Fq "$digest" "$tmp/snapshot/$report_rel" || {
    echo "S1 report does not bind $path at $digest" >&2
    exit 1
  }
done

run_checker() (
  runner_path=/usr/bin:/bin
  runner_home="$tmp/home"
  while IFS= read -r name; do
    builtin unset "$name" 2>/dev/null || true
  done < <(builtin compgen -e)
  export PATH="$runner_path"
  export HOME="$runner_home"
  export LC_ALL=C
  export TZ=UTC
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONHASHSEED=0
  export PYTHONNOUSERSITE=1
  export PYTHONSAFEPATH=1
  /usr/bin/python3 "$tmp/snapshot/$checker_rel" \
    --contract "$tmp/snapshot/$contract_rel" \
    --fixture "$tmp/snapshot/$fixture_rel"
)

AB_EVIDENCE_SUBSTRATE_SENTINEL=poison \
AGENT_BRIDGE_EVIDENCE_SUBSTRATE_SENTINEL=poison \
PYTHONINSPECT=1 \
  run_checker >"$tmp/run-one.tsv" 2>"$tmp/run-one.err"
AB_EVIDENCE_SUBSTRATE_SENTINEL=poison \
AGENT_BRIDGE_EVIDENCE_SUBSTRATE_SENTINEL=poison \
PYTHONINSPECT=1 \
  run_checker >"$tmp/run-two.tsv" 2>"$tmp/run-two.err"

[[ ! -s "$tmp/run-one.err" && ! -s "$tmp/run-two.err" ]] || {
  echo "S1 design checker wrote unexpected stderr" >&2
  /usr/bin/cat "$tmp/run-one.err" "$tmp/run-two.err" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/run-two.tsv" || {
  echo "S1 design checker is nondeterministic" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/snapshot/$expected_rel" || {
  echo "S1 design receipt drifted" >&2
  exit 1
}

head_after="$(/usr/bin/git -C "$repo_root" rev-parse --verify HEAD^{commit})"
status_after="$(/usr/bin/git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ "$head_after" == "$head_before" && "$status_after" == "$status_before" ]] || {
  echo "HEAD, worktree, or index changed while S1 design gate ran" >&2
  exit 1
}
/usr/bin/git -C "$repo_root" diff --quiet -- .
/usr/bin/git -C "$repo_root" diff --cached --quiet -- .

printf 'BOUND_TO_HEAD_MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S1\n'
printf 'head=%s\n' "$head_before"
printf 'design_sha256=%s\n' "$(sha "$repo_root/$design_rel")"
printf 'contract_sha256=%s\n' "$(sha "$repo_root/$contract_rel")"
printf 'fixture_sha256=%s\n' "$(sha "$repo_root/$fixture_rel")"
printf 'checker_sha256=%s\n' "$(sha "$repo_root/$checker_rel")"
printf 'receipt_sha256=%s\n' "$(sha "$repo_root/$expected_rel")"
printf 'report_sha256=%s\n' "$(sha "$repo_root/$report_rel")"
printf 'negative_cases=36\n'
printf 'schema_migration_present=false\n'
printf 'runtime_writer_present=false\n'
printf 'store_adapter_present=false\n'
printf 'real_capture_authorized=false\n'
printf 'decision=BLOCKED_FAIL_CLOSED\n'
