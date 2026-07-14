#!/usr/bin/env -S -i /usr/bin/bash
# Head/source-bound gate for the public Track B real-run admission v0 packet.
set -euo pipefail

while IFS= read -r imported_function; do
  builtin unset -f "$imported_function"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PERL5OPT PERL5LIB PERL_UNICODE
unset LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT
unset GIT_CONFIG_PARAMETERS GIT_NAMESPACE GIT_SHALLOW_FILE
unset GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

for absolute_tool in /usr/bin/awk /usr/bin/bash /usr/bin/chmod /usr/bin/cmp \
  /usr/bin/dirname /usr/bin/env /usr/bin/git /usr/bin/mkdir /usr/bin/mktemp \
  /usr/bin/python3 /usr/bin/rm /usr/bin/sort /usr/bin/stat /usr/bin/tail; do
  [[ -x "$absolute_tool" ]] || {
    printf 'Track B admission gate missing trusted tool: %s\n' "$absolute_tool" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

parent_commit="533ab2607825d877278edd6548e897f93c2acf19"
contract="scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
expected_receipt="scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission.expected.v0.tsv"
checker="scripts/eval/check_biocortex_ab_track_b_admission.py"
gate_path="scripts/check-biocortex-ab-track-b-admission.sh"

source_paths=(
  "docs/reports/goal-c-u/2026-07-13-biocortex-ab-track-b-real-run-admission.md"
  "scripts/check-biocortex-ab-track-b-admission.sh"
  "scripts/eval/check_biocortex_ab_track_b_admission.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_admission_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)
source_modes=(100644 100755 100644 100644 100644 100644)

checker_source_paths=(
  "Cargo.lock"
  "crates/bridge/src/mcp_tools.rs"
  "crates/bridge/src/memory_truth.rs"
  "crates/bridge/src/memory_truth_adapter.rs"
  "crates/store/src/lib.rs"
  "crates/store/src/sqlite.rs"
  "docs/design/MEMORY_PEEK_TRUTH_ADAPTER_PREFLIGHT_V0_2026_07_10.md"
  "docs/design/TEMPORAL_TRUTH_PROJECTION_V0_2026_07_10.md"
  "scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json"
  "scripts/eval/portfolio_continuity_ab_trial.py"
  "scripts/eval/portfolio_continuity_successor_v3_trial.py"
)

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "$tmp" 2>/dev/null || true
  /usr/bin/rm -rf "$tmp"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "$tmp/home" "$tmp/child-tmp"

fail() {
  printf 'Track B admission gate failed: %s\n' "$*" >&2
  exit 1
}

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.hooksPath=/dev/null "$@"
}

run_checker() {
  local output="$1" error="$2"
  HOME="$tmp/home" TMPDIR="$tmp/child-tmp" \
    /usr/bin/python3 "$tmp/snapshot/$checker" --root "$tmp/snapshot" \
      >"$output" 2>"$error"
}

verify_packet_identity() {
  local index path expected_mode binding_commit mode object stage indexed
  for index in "${!source_paths[@]}"; do
    path="${source_paths[$index]}"
    expected_mode="${source_modes[$index]}"
    binding_commit="$source_commit"
    if [[ "$path" == "$gate_path" ]]; then
      binding_commit="$hardening_commit"
    fi
    [[ -f "$path" && ! -L "$path" && "$(/usr/bin/stat -c '%F' -- "$path")" == "regular file" ]] \
      || fail "protected packet member is not a regular file: $path"
    [[ "$(/usr/bin/stat -c '%h' -- "$path")" == 1 ]] \
      || fail "protected packet member has hard-link aliases: $path"
    read -r mode object stage indexed < <(git_clean ls-files --stage -- "$path")
    [[ "$mode" == "$expected_mode" && "$stage" == 0 && "$indexed" == "$path" ]] \
      || fail "Git identity or mode drift: $path"
    [[ "$(git_clean ls-files -v -- "$path")" == "H $path" ]] \
      || fail "nondefault Git index flag: $path"
    [[ "$(git_clean ls-tree "$binding_commit" -- "$path" | /usr/bin/awk '{print $1}')" == "$expected_mode" ]] \
      || fail "binding-commit mode drift: $path"
    /usr/bin/cmp -s "$path" <(git_clean cat-file blob "$binding_commit:$path") \
      || fail "worktree/binding-commit byte drift: $path"
  done
}

[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "Git replace refs are present"
head_oid="$(git_clean rev-parse --verify 'HEAD^{commit}')" \
  || fail "cannot resolve HEAD"
git_clean merge-base --is-ancestor "$parent_commit" "$head_oid" \
  || fail "frozen parent is not an ancestor of HEAD"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)" ]] \
  || fail "worktree must be clean"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags are present"

source_commit="$(
  git_clean log "$head_oid" --diff-filter=A --format='%H' -- "$contract" \
    | /usr/bin/tail -n 1
)"
[[ -n "$source_commit" ]] || fail "cannot locate admission source commit"
[[ "$(git_clean show -s --format='%P' "$source_commit")" == "$parent_commit" ]] \
  || fail "admission source commit must directly parent the frozen baseline"

# The source gate could not attest a concurrent HEAD move after its checker
# began.  Admit exactly one direct successor that changes only this wrapper;
# every other packet byte remains bound to the original source commit.
mapfile -t hardening_commits < <(
  git_clean rev-list --reverse "$source_commit..$head_oid" -- "$gate_path"
)
[[ "${#hardening_commits[@]}" == 1 ]] \
  || fail "expected exactly one admission-gate hardening commit"
hardening_commit="${hardening_commits[0]}"
[[ "$(git_clean show -s --format='%P' "$hardening_commit")" == "$source_commit" ]] \
  || fail "admission-gate hardening must directly follow the source commit"
printf '%s\n' "$gate_path" >"$tmp/expected-hardening-paths"
git_clean diff-tree --no-commit-id --name-only -r "$hardening_commit" \
  | /usr/bin/sort >"$tmp/actual-hardening-paths"
/usr/bin/cmp -s "$tmp/expected-hardening-paths" "$tmp/actual-hardening-paths" \
  || fail "admission-gate hardening changed paths outside the wrapper"

{
  for path in "${source_paths[@]}"; do
    printf '%s\n' "$path"
  done
} | /usr/bin/sort >"$tmp/expected-paths"
git_clean diff-tree --no-commit-id --name-only -r "$source_commit" \
  | /usr/bin/sort >"$tmp/actual-paths"
/usr/bin/cmp -s "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "source commit changed paths outside the exact public admission packet"

verify_packet_identity

# The exact changed-path check is the primary boundary. Reassert the sensitive
# surfaces so a future packet edit cannot silently become a runtime change.
[[ -z "$(git_clean diff --name-only "$parent_commit" "$source_commit" -- crates Cargo.toml Cargo.lock)" ]] \
  || fail "Rust/Cargo runtime surface changed"
[[ -z "$(git_clean diff --name-only "$parent_commit" "$source_commit" -- data)" ]] \
  || fail "private data surface changed"

# Run the checker from immutable HEAD blobs rather than the mutable worktree.
# A concurrent checkout can therefore only make the final fence fail; it
# cannot change which bytes produced the receipt.
/usr/bin/mkdir -m 0700 "$tmp/snapshot"
snapshot_paths=(
  "$contract"
  "$expected_receipt"
  "$checker"
  "scripts/eval/fixtures/biocortex_ab_track_b_admission_synthetic_v0.json"
  "${checker_source_paths[@]}"
)
for path in "${snapshot_paths[@]}"; do
  /usr/bin/mkdir -p "$tmp/snapshot/$(/usr/bin/dirname "$path")"
  git_clean cat-file blob "$head_oid:$path" >"$tmp/snapshot/$path" \
    || fail "cannot materialize immutable checker input: $path"
done

run_checker "$tmp/run-one.out" "$tmp/run-one.err"
run_checker "$tmp/run-two.out" "$tmp/run-two.err"
[[ ! -s "$tmp/run-one.err" && ! -s "$tmp/run-two.err" ]] \
  || fail "valid checker emitted stderr"
/usr/bin/cmp -s "$tmp/run-one.out" "$tmp/run-two.out" \
  || fail "public checker is nondeterministic"
/usr/bin/cmp -s "$tmp/run-one.out" "$tmp/snapshot/$expected_receipt" \
  || fail "fixed public receipt drift"

HOME="$tmp/home" TMPDIR="$tmp/child-tmp" \
  /usr/bin/python3 "$tmp/snapshot/$checker" --root "$tmp/snapshot" --self-test \
  >"$tmp/self-test.out" 2>"$tmp/self-test.err"
[[ ! -s "$tmp/self-test.err" ]] || fail "self-test emitted stderr"
[[ "$(<"$tmp/self-test.out")" == $'SELF_TEST_OK\tcontract_mutations_rejected=61\tsynthetic_mutations_rejected=67\ttotal_mutations_rejected=128' ]] \
  || fail "adversarial self-test result drift"

[[ "$(git_clean rev-parse --verify 'HEAD^{commit}')" == "$head_oid" ]] \
  || fail "HEAD changed while the gate was running"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "Git replace refs appeared while the gate was running"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)" ]] \
  || fail "worktree changed while the gate was running"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags appeared while the gate was running"
verify_packet_identity

if [[ "$head_oid" == "$hardening_commit" ]]; then
  printf 'BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_ADMISSION\n'
else
  printf 'VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_ADMISSION\n'
fi
printf 'source_commit=%s\n' "$source_commit"
printf 'hardening_commit=%s\n' "$hardening_commit"
printf 'parent_commit=%s\n' "$parent_commit"
printf 'adversarial_mutations_rejected=128\n'
while IFS= read -r row; do
  printf '%s\n' "$row"
done <"$tmp/run-one.out"
