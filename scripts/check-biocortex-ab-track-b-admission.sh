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

source_paths=(
  "docs/reports/goal-c-u/2026-07-13-biocortex-ab-track-b-real-run-admission.md"
  "scripts/check-biocortex-ab-track-b-admission.sh"
  "scripts/eval/check_biocortex_ab_track_b_admission.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_admission_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)
source_modes=(100644 100755 100644 100644 100644 100644)

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
    /usr/bin/python3 "$checker" --root . >"$output" 2>"$error"
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

{
  for path in "${source_paths[@]}"; do
    printf '%s\n' "$path"
  done
} | /usr/bin/sort >"$tmp/expected-paths"
git_clean diff-tree --no-commit-id --name-only -r "$source_commit" \
  | /usr/bin/sort >"$tmp/actual-paths"
/usr/bin/cmp -s "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "source commit changed paths outside the exact public admission packet"

for index in "${!source_paths[@]}"; do
  path="${source_paths[$index]}"
  expected_mode="${source_modes[$index]}"
  [[ -f "$path" && ! -L "$path" && "$(/usr/bin/stat -c '%F' -- "$path")" == "regular file" ]] \
    || fail "protected packet member is not a regular file: $path"
  [[ "$(/usr/bin/stat -c '%h' -- "$path")" == 1 ]] \
    || fail "protected packet member has hard-link aliases: $path"
  read -r mode object stage indexed < <(git_clean ls-files --stage -- "$path")
  [[ "$mode" == "$expected_mode" && "$stage" == 0 && "$indexed" == "$path" ]] \
    || fail "Git identity or mode drift: $path"
  [[ "$(git_clean ls-files -v -- "$path")" == "H $path" ]] \
    || fail "nondefault Git index flag: $path"
  [[ "$(git_clean ls-tree "$source_commit" -- "$path" | /usr/bin/awk '{print $1}')" == "$expected_mode" ]] \
    || fail "source-commit mode drift: $path"
  /usr/bin/cmp -s "$path" <(git_clean cat-file blob "$source_commit:$path") \
    || fail "worktree/source-commit byte drift: $path"
done

# The exact changed-path check is the primary boundary. Reassert the sensitive
# surfaces so a future packet edit cannot silently become a runtime change.
[[ -z "$(git_clean diff --name-only "$parent_commit" "$source_commit" -- crates Cargo.toml Cargo.lock)" ]] \
  || fail "Rust/Cargo runtime surface changed"
[[ -z "$(git_clean diff --name-only "$parent_commit" "$source_commit" -- data)" ]] \
  || fail "private data surface changed"

run_checker "$tmp/run-one.out" "$tmp/run-one.err"
run_checker "$tmp/run-two.out" "$tmp/run-two.err"
[[ ! -s "$tmp/run-one.err" && ! -s "$tmp/run-two.err" ]] \
  || fail "valid checker emitted stderr"
/usr/bin/cmp -s "$tmp/run-one.out" "$tmp/run-two.out" \
  || fail "public checker is nondeterministic"
/usr/bin/cmp -s "$tmp/run-one.out" "$expected_receipt" \
  || fail "fixed public receipt drift"

HOME="$tmp/home" TMPDIR="$tmp/child-tmp" \
  /usr/bin/python3 "$checker" --root . --self-test \
  >"$tmp/self-test.out" 2>"$tmp/self-test.err"
[[ ! -s "$tmp/self-test.err" ]] || fail "self-test emitted stderr"
[[ "$(<"$tmp/self-test.out")" == $'SELF_TEST_OK\tcontract_mutations_rejected=61\tsynthetic_mutations_rejected=67\ttotal_mutations_rejected=128' ]] \
  || fail "adversarial self-test result drift"

final_status="$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ -z "$final_status" ]] || fail "gate changed the worktree"

if [[ "$head_oid" == "$source_commit" ]]; then
  printf 'BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_ADMISSION\n'
else
  printf 'VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_ADMISSION\n'
fi
printf 'source_commit=%s\n' "$source_commit"
printf 'parent_commit=%s\n' "$parent_commit"
printf 'adversarial_mutations_rejected=128\n'
while IFS= read -r row; do
  printf '%s\n' "$row"
done <"$tmp/run-one.out"
