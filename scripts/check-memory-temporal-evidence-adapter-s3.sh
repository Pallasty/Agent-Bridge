#!/usr/bin/env -S -i /usr/bin/bash
# Clean-HEAD, source-bound gate for the fail-closed S3 adapter preregistration.

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
baseline="a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259"
contract_rel="scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_contract_v0.json"
fixture_rel="scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_synthetic_v0.json"
expected_rel="scripts/eval/fixtures/memory_temporal_evidence_adapter_s3.expected.v0.tsv"
checker_rel="scripts/eval/check_memory_temporal_evidence_adapter_s3.py"
gate_rel="scripts/check-memory-temporal-evidence-adapter-s3.sh"
design_rel="docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S3_2026_07_14.md"
report_rel="docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s3.md"

paths=(
  "$design_rel"
  "$report_rel"
  "$gate_rel"
  "$checker_rel"
  "$expected_rel"
  "$contract_rel"
  "$fixture_rel"
)
modes=(100644 100644 100755 100644 100644 100644 100644)

source_paths=(
  "Cargo.lock"
  "crates/store/Cargo.toml"
  "crates/store/src/sqlite.rs"
  "crates/store/src/sqlite/temporal_evidence.rs"
  "crates/store/src/sqlite/temporal_evidence/tests.rs"
  "docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md"
  "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s2.md"
  "scripts/check-memory-temporal-evidence-substrate-s2.sh"
  "scripts/eval/check_memory_temporal_evidence_substrate_s2.py"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2.expected.v0.tsv"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_synthetic_v0.json"
  "crates/bridge/src/memory_truth.rs"
  "crates/bridge/src/memory_truth_adapter.rs"
  "docs/reports/goal-c-u/2026-07-14-biocortex-track-b-artifact-dependency-graph.md"
  "scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh"
  "scripts/eval/check_biocortex_ab_track_b_artifact_dependency_graph.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
)

status_before="$(/usr/bin/git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ -z "$status_before" ]] || {
  echo "S3 gate requires a clean worktree and index" >&2
  exit 3
}
head_before="$(/usr/bin/git -C "$repo_root" rev-parse --verify HEAD^{commit})"
/usr/bin/git -C "$repo_root" cat-file -e "$baseline^{commit}"
read -r -a parent_vector <<<"$(/usr/bin/git -C "$repo_root" rev-list --parents -n 1 "$head_before")"
[[ "${#parent_vector[@]}" == "2" ]] || {
  echo "S3 HEAD must be a single-parent commit" >&2
  exit 1
}
parent="${parent_vector[1]}"
[[ "$parent" == "$baseline" ]] || {
  echo "S3 HEAD must have the reviewed S2 baseline as its direct parent" >&2
  exit 1
}

[[ -z "$(/usr/bin/git -C "$repo_root" replace -l)" ]] || {
  echo "S3 gate rejects replace refs" >&2
  exit 1
}
git_common_dir="$(/usr/bin/git -C "$repo_root" rev-parse --git-common-dir)"
[[ "$git_common_dir" = /* ]] || git_common_dir="$repo_root/$git_common_dir"
[[ ! -s "$git_common_dir/info/grafts" ]] || {
  echo "S3 gate rejects grafted history" >&2
  exit 1
}
shallow_path="$(/usr/bin/git -C "$repo_root" rev-parse --git-path shallow)"
[[ "$shallow_path" = /* ]] || shallow_path="$repo_root/$shallow_path"
[[ ! -s "$shallow_path" ]] || {
  echo "S3 gate rejects shallow history" >&2
  exit 1
}

for index in "${!paths[@]}"; do
  path="${paths[$index]}"
  actual_mode="$(/usr/bin/git -C "$repo_root" ls-tree "$head_before" -- "$path" | /usr/bin/awk '{print $1}')"
  [[ "$actual_mode" == "${modes[$index]}" ]] || {
    echo "S3 packet mode drifted for $path: $actual_mode" >&2
    exit 1
  }
done

expected_delta=(
  "docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S3_2026_07_14.md"
  "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s3.md"
  "scripts/check-memory-temporal-evidence-adapter-s3.sh"
  "scripts/eval/check_memory_temporal_evidence_adapter_s3.py"
  "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3.expected.v0.tsv"
  "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_contract_v0.json"
  "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_synthetic_v0.json"
)
actual_delta=()
while IFS= read -r path; do
  [[ -z "$path" ]] || actual_delta+=("$path")
done < <(/usr/bin/git -C "$repo_root" diff --name-only --diff-filter=ACDMRTUXB "$baseline" "$head_before" -- | /usr/bin/sort)
[[ "${actual_delta[*]}" == "${expected_delta[*]}" ]] || {
  echo "S3 tranche contains paths outside the reviewed allowlist" >&2
  /usr/bin/printf 'actual: %s\n' "${actual_delta[*]}" >&2
  exit 1
}

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "$tmp" 2>/dev/null || true
  /usr/bin/rm -rf "$tmp"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "$tmp/home" "$tmp/snapshot"
/usr/bin/git -C "$repo_root" archive --format=tar "$head_before" | /usr/bin/tar -xf - -C "$tmp/snapshot"

for path in "${paths[@]}" "${source_paths[@]}"; do
  [[ -f "$tmp/snapshot/$path" && ! -L "$tmp/snapshot/$path" ]] || {
    echo "S3 archived source/packet member is missing or symlinked: $path" >&2
    exit 1
  }
  [[ "$(/usr/bin/stat -c '%h' "$tmp/snapshot/$path")" == "1" ]] || {
    echo "S3 archived source/packet member is hardlinked: $path" >&2
    exit 1
  }
done

sha() {
  /usr/bin/sha256sum "$1" | /usr/bin/awk '{print $1}'
}

for path in "$design_rel" "$contract_rel" "$fixture_rel" "$checker_rel" "$expected_rel" "$gate_rel"; do
  digest="$(sha "$tmp/snapshot/$path")"
  /usr/bin/grep -Fq "$digest" "$tmp/snapshot/$report_rel" || {
    echo "S3 report does not bind packet member $path at $digest" >&2
    exit 1
  }
done
for path in "${source_paths[@]}"; do
  digest="$(sha "$tmp/snapshot/$path")"
  /usr/bin/grep -Fq "$digest" "$tmp/snapshot/$report_rel" || {
    echo "S3 report does not bind upstream source $path at $digest" >&2
    exit 1
  }
done

run_checker() (
  while IFS= read -r name; do
    builtin unset "$name" 2>/dev/null || true
  done < <(builtin compgen -e)
  export PATH=/usr/bin:/bin
  export HOME="$tmp/home"
  export LC_ALL=C
  export TZ=UTC
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONHASHSEED=0
  export PYTHONNOUSERSITE=1
  export PYTHONSAFEPATH=1
  /usr/bin/python3 "$tmp/snapshot/$checker_rel" \
    --contract "$tmp/snapshot/$contract_rel" \
    --fixture "$tmp/snapshot/$fixture_rel" \
    --source-root "$tmp/snapshot"
)

AB_EVIDENCE_ADAPTER_S3_SENTINEL=poison \
AGENT_BRIDGE_EVIDENCE_ADAPTER_S3_SENTINEL=poison \
PYTHONINSPECT=1 \
  run_checker >"$tmp/run-one.tsv" 2>"$tmp/run-one.err"
AB_EVIDENCE_ADAPTER_S3_SENTINEL=poison \
AGENT_BRIDGE_EVIDENCE_ADAPTER_S3_SENTINEL=poison \
PYTHONINSPECT=1 \
  run_checker >"$tmp/run-two.tsv" 2>"$tmp/run-two.err"

[[ ! -s "$tmp/run-one.err" && ! -s "$tmp/run-two.err" ]] || {
  echo "S3 checker wrote unexpected stderr" >&2
  /usr/bin/cat "$tmp/run-one.err" "$tmp/run-two.err" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/run-two.tsv" || {
  echo "S3 checker is nondeterministic" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/snapshot/$expected_rel" || {
  echo "S3 receipt drifted" >&2
  /usr/bin/diff -u "$tmp/snapshot/$expected_rel" "$tmp/run-one.tsv" >&2 || true
  exit 1
}

head_after="$(/usr/bin/git -C "$repo_root" rev-parse --verify HEAD^{commit})"
status_after="$(/usr/bin/git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ "$head_after" == "$head_before" && "$status_after" == "$status_before" ]] || {
  echo "HEAD, worktree, or index changed while S3 gate ran" >&2
  exit 1
}
/usr/bin/git -C "$repo_root" diff --quiet -- .
/usr/bin/git -C "$repo_root" diff --cached --quiet -- .

/usr/bin/printf 'BOUND_TO_HEAD_MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S3\n'
/usr/bin/printf 'head=%s\n' "$head_before"
/usr/bin/printf 'design_sha256=%s\n' "$(sha "$repo_root/$design_rel")"
/usr/bin/printf 'contract_sha256=%s\n' "$(sha "$repo_root/$contract_rel")"
/usr/bin/printf 'fixture_sha256=%s\n' "$(sha "$repo_root/$fixture_rel")"
/usr/bin/printf 'checker_sha256=%s\n' "$(sha "$repo_root/$checker_rel")"
/usr/bin/printf 'receipt_sha256=%s\n' "$(sha "$repo_root/$expected_rel")"
/usr/bin/printf 'report_sha256=%s\n' "$(sha "$repo_root/$report_rel")"
/usr/bin/printf 'rust_delta=false\n'
/usr/bin/printf 's3_gap_count=10\n'
/usr/bin/printf 'negative_controls=28\n'
/usr/bin/printf 'projector_invoked=false\n'
/usr/bin/printf 'producer_profile_reserved=false\n'
/usr/bin/printf 'real_capture_authorized=false\n'
/usr/bin/printf 'biocortex_runtime_influence=false\n'
/usr/bin/printf 'decision=BLOCKED_FAIL_CLOSED\n'
