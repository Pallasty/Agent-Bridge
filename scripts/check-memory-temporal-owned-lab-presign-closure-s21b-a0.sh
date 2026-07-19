#!/usr/bin/env -S -i /usr/bin/bash
# Release gate for the blocked, non-live S21B-A0 pre-sign closure audit.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "$imported_function"
done < <(builtin compgen -A function)

PATH="/usr/bin:/bin:/home/pallasting/.cargo/bin"
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
export GIT_ATTR_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
export GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never
export GIT_ASKPASS=/bin/false
unset BASH_ENV ENV CDPATH LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset CARGO_ENCODED_RUSTFLAGS CARGO_HOME RUSTUP_HOME RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'S21B-A0 pre-sign closure gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "$validation_tier" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: $validation_tier" ;;
esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/cmp /usr/bin/dirname /usr/bin/env
  /usr/bin/find /usr/bin/git /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp
  /usr/bin/python3 /usr/bin/rm /usr/bin/sha256sum /usr/bin/stat
  /usr/bin/tail /usr/bin/tar /usr/bin/wc
)
for tool in "${required_tools[@]}"; do
  [[ -x "$tool" ]] || fail "missing required tool: $tool"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "$repo_root" == /* && -d "$repo_root" && ! -L "$repo_root" ]] \
  || fail "repository root is not one canonical directory"

# Immutable audit target. This is intentionally not the moving remote head.
target_commit="34b1c7e6ca9c2b75fd2ef3cf418a444353059511"
target_tree="00bbf534c33ecfa56d05579d8a7f4c83e60b208e"
target_first_parent="8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5"
target_second_parent="ed5d959489f88d0eead21b604d03a142e0584982"
target_source_tree="7d1db2c9eb04d75cc980ea83d369b9129155252f"
target_source_parent="33c2c4df78ef302fd0538986b95fa40a3711ba86"
target_archive_sha256="d45312d5b343dd036ef6906af0abe9f59da8220cf6ef16fb87caf8c1265c0bb5"
target_archive_byte_count="48107520"
target_cargo_lock_sha256="408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59"

# The A0 packet source is exactly one commit over this construction base. An
# ordinary later integration may have a newer first parent descending from it.
packet_base_commit="36d3e8a4f05caa2731dc8224b035e2f1ac4f4d73"
packet_base_tree="595e8f953f93960ed58429ee3898bd7e702f6311"

design_path="docs/design/MEMORY_TEMPORAL_OWNED_LAB_PRESIGN_CLOSURE_S21B_A0_2026_07_18.md"
contract_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-contract-s21b-a0-v0.json"
status_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-status-s21b-a0-v0.json"
schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-receipt-schema-s21b-a0-v0.json"
fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-receipt-synthetic-s21b-a0-v0.json"
successor_path="docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s21b-a0-v0.json"
checker_path="scripts/eval/check_memory_temporal_owned_lab_presign_closure_s21b_a0.py"
expected_path="scripts/eval/fixtures/memory_temporal_owned_lab_presign_closure_s21b_a0.expected.v0.tsv"
gate_path="scripts/check-memory-temporal-owned-lab-presign-closure-s21b-a0.sh"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-presign-closure-s21b-a0.md"
s21a_gate_path="scripts/check-memory-temporal-owned-lab-final-refreeze-external-input-admission-s21a.sh"

packet_paths=(
  "$design_path" "$contract_path" "$status_path" "$schema_path" "$fixture_path"
  "$successor_path" "$checker_path" "$expected_path" "$gate_path" "$report_path"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100755 100644)
report_binding_paths=(
  "$design_path" "$contract_path" "$status_path" "$schema_path" "$fixture_path"
  "$successor_path" "$checker_path" "$expected_path" "$gate_path"
)

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="$repo_root" "$@"
}

raw_blob_sha256() {
  local commit="$1" path="$2"
  git_clean cat-file blob "$commit:$path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}'
}

[[ "$(git_clean config --get-all safe.directory)" == "$repo_root" ]] \
  || fail "Git trust scope is not the exact repository root"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] || fail "shallow history"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)"
[[ "$common_dir" == /* && -d "$common_dir" && ! -L "$common_dir" ]] \
  || fail "non-canonical Git common directory"
[[ ! -e "$common_dir/shallow" && ! -e "$common_dir/info/grafts" ]] \
  || fail "shallow or graft state present"
[[ ! -s "$common_dir/objects/info/alternates" ]] || fail "Git alternates present"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] || fail "Git replace refs"
[[ -z "$(git_clean config --local --get extensions.partialClone || true)" ]] \
  || fail "Git partial-clone extension present"
[[ -z "$(git_clean config --local --get-regexp '^remote\..*\.promisor$' || true)" ]] \
  || fail "Git promisor remote present"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"

[[ "$(git_clean cat-file -t "$target_commit")" == commit ]] || fail "S21A target absent"
[[ "$(git_clean show -s --format='%T' "$target_commit")" == "$target_tree" ]] \
  || fail "S21A target tree drift"
[[ "$(git_clean show -s --format='%P' "$target_commit")" == \
    "$target_first_parent $target_second_parent" ]] || fail "S21A target parent topology drift"
[[ "$(git_clean show -s --format='%T' "$target_second_parent")" == "$target_source_tree" ]] \
  || fail "S21A source tree drift"
[[ "$(git_clean show -s --format='%P' "$target_second_parent")" == "$target_source_parent" ]] \
  || fail "S21A source parent drift"
[[ "$(git_clean show -s --format='%T' "$packet_base_commit")" == "$packet_base_tree" ]] \
  || fail "A0 packet construction base drift"

head_oid="$(git_clean rev-parse --verify HEAD)" || fail "cannot resolve HEAD"
head_lineage=()
IFS=' ' read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "$head_oid") \
  || fail "cannot resolve HEAD topology"
head_parents=("${head_lineage[@]:1}")
source_commit=""
if [[ "${#head_parents[@]}" == 1 && "${head_parents[0]}" == "$packet_base_commit" ]]; then
  source_commit="$head_oid"
elif [[ "${#head_parents[@]}" == 2 ]]; then
  first_parent="${head_parents[0]}"
  source_commit="${head_parents[1]}"
  source_lineage=()
  IFS=' ' read -r -a source_lineage < <(git_clean rev-list --parents -n 1 "$source_commit") \
    || fail "cannot resolve packet source topology"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "$packet_base_commit" ]] \
    || fail "integrated second parent is not exact A0 packet source"
  git_clean merge-base --is-ancestor "$packet_base_commit" "$first_parent" \
    || fail "integration first parent does not descend from A0 construction base"
  if git_clean merge-base --is-ancestor "$source_commit" "$first_parent"; then
    fail "integration first parent already contains A0 packet source"
  fi
else
  fail "HEAD must be exact A0 packet source or ordinary two-parent integration"
fi
[[ "$(git_clean rev-list --count "$packet_base_commit..$source_commit")" == 1 ]] \
  || fail "A0 packet source is not one exact commit over construction base"

declare -A expected_delta=(
  ["$design_path"]="A" ["$contract_path"]="A" ["$status_path"]="A"
  ["$schema_path"]="A" ["$fixture_path"]="A" ["$successor_path"]="A"
  ["$checker_path"]="A" ["$expected_path"]="A" ["$gate_path"]="A" ["$report_path"]="A"
)
actual_delta_count=0
while IFS=$'\t' read -r delta_status delta_path delta_extra; do
  [[ -n "$delta_status" && -n "$delta_path" && -z "${delta_extra:-}" ]] \
    || fail "malformed packet delta row"
  [[ -v "expected_delta[$delta_path]" ]] || fail "unexpected packet delta path: $delta_path"
  [[ "${expected_delta[$delta_path]}" == "$delta_status" ]] \
    || fail "wrong packet delta status: $delta_path"
  unset 'expected_delta[$delta_path]'
  actual_delta_count=$((actual_delta_count + 1))
done < <(git_clean diff-tree --no-commit-id --name-status --no-renames -r \
  "$packet_base_commit" "$source_commit")
[[ "$actual_delta_count" == 10 && "${#expected_delta[@]}" == 0 ]] \
  || fail "A0 packet delta is not exact 10A"

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[$index]}" expected_mode="${packet_modes[$index]}"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")"
  [[ -n "$source_entry" && "${source_entry%% *}" == "$expected_mode" ]] \
    || fail "packet path or mode drift: $path"
  [[ "$source_entry" == "$(git_clean ls-tree "$head_oid" -- "$path")" ]] \
    || fail "source/HEAD packet blob or mode mismatch: $path"
done

tmp="$(/usr/bin/mktemp -d -p /Data/CascadeProjects .ab-s21b-a0-gate.XXXXXXXX)" \
  || fail "cannot allocate bounded scratch under /Data"
cleanup() { /usr/bin/rm -rf -- "$tmp"; }
trap cleanup EXIT HUP INT TERM
/usr/bin/mkdir -m 0700 "$tmp/target"
git_clean -c tar.umask=0022 archive --format=tar "$target_commit" >"$tmp/target.tar" \
  || fail "cannot reconstruct exact S21A target archive"
[[ "$(/usr/bin/sha256sum "$tmp/target.tar" | /usr/bin/awk '{print $1}')" == \
    "$target_archive_sha256" ]] || fail "S21A target archive digest drift"
[[ "$(/usr/bin/wc -c <"$tmp/target.tar" | /usr/bin/awk '{print $1}')" == \
    "$target_archive_byte_count" ]] || fail "S21A target archive byte count drift"
/usr/bin/tar --same-permissions -xf "$tmp/target.tar" -C "$tmp/target" \
  || fail "cannot materialize exact S21A target archive"
[[ -z "$(/usr/bin/find "$tmp/target" -type l -print -quit)" ]] \
  || fail "materialized S21A target contains a symlink"
[[ -z "$(/usr/bin/find "$tmp/target" -mindepth 1 -perm /022 -print -quit)" ]] \
  || fail "materialized S21A target is group/world writable"
[[ "$(/usr/bin/sha256sum "$tmp/target/Cargo.lock" | /usr/bin/awk '{print $1}')" == \
    "$target_cargo_lock_sha256" ]] || fail "materialized Cargo.lock drift"

checker="$repo_root/$checker_path"
expected="$repo_root/$expected_path"
[[ -f "$checker" && ! -L "$checker" && -f "$expected" && ! -L "$expected" ]] \
  || fail "checker or expected receipt absent"
for seed in 21121 21199; do
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    /usr/bin/python3 -I "$checker" --repo "$repo_root" --seed "$seed" \
    >"$tmp/checker-$seed.tsv" || fail "checker seed $seed failed"
done
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$checker" --repo "$repo_root" --seed 21177 --self-test \
  >"$tmp/checker-self.tsv" || fail "checker mutation self-test failed"
/usr/bin/cmp -s "$tmp/checker-21121.tsv" "$tmp/checker-21199.tsv" \
  || fail "checker output depends on seed"
/usr/bin/cmp -s "$tmp/checker-21121.tsv" "$tmp/checker-self.tsv" \
  || fail "checker self-test receipt drift"
/usr/bin/cmp -s "$tmp/checker-21121.tsv" "$expected" || fail "expected receipt mismatch"

required_checker_rows=(
  $'status\tS21B_A0_BLOCKED_MISSING_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES'
  $'decision\tS21B_A0_REMAINS_BLOCKED_NO_UNSIGNED_SUBJECT_OR_OWNER_SIGNING_REQUEST'
  $'required_role_binary_present_count\t0'
  $'external_owner_private_key_read\tfalse'
  $'owner_signature_artifact_generated\tfalse'
  $'signable_subject_emitted\tfalse'
  $'signing_message_emitted\tfalse'
  $'live_canary\tNOT_RUN'
  $'side_effects_unlocked\tNONE'
  $'gate\tBLOCKED_PRESIGN_CLOSURE_AUDIT_PASS_NON_LIVE_ONLY'
)
for row in "${required_checker_rows[@]}"; do
  /usr/bin/grep -Fx "$row" "$expected" >/dev/null || fail "checker receipt boundary missing: $row"
done

report="$repo_root/$report_path"
[[ -f "$report" && ! -L "$report" ]] || fail "report absent"
/usr/bin/grep -Fx 'Hash table state: **FINAL_CLOSED_WORLD_BOUND**' "$report" >/dev/null \
  || fail "report final-state token absent"
/usr/bin/grep -Fx '## Final artifact digest table' "$report" >/dev/null \
  || fail "report digest-table heading absent"
! /usr/bin/grep -E 'TODO_FINAL_SHA256|IMPLEMENTATION_PENDING|TODO markers|\| PENDING \|' "$report" >/dev/null \
  || fail "report contains non-final markers"
report_binding_count="$(/usr/bin/grep -Ec '^\| [^|]+ \| [0-9a-f]{64} \|$' "$report")"
[[ "$report_binding_count" == "${#report_binding_paths[@]}" ]] \
  || fail "report digest table is not exact ${#report_binding_paths[@]} rows"
for path in "${report_binding_paths[@]}"; do
  digest="$(raw_blob_sha256 "$source_commit" "$path")"
  [[ "$(/usr/bin/grep -Fxc -- "| $path | $digest |" "$report")" == 1 ]] \
    || fail "report lacks exact path/hash binding: $path"
done

s21a_full_replay="NOT_RUN"
if [[ "$validation_tier" == full-replay ]]; then
  s21a_repo="$tmp/s21a-integration"
  git_clean clone --quiet --no-hardlinks "$repo_root" "$s21a_repo" \
    || fail "cannot clone immutable S21A target"
  [[ ! -s "$s21a_repo/.git/objects/info/alternates" ]] \
    || fail "S21A replay clone uses alternates"
  /usr/bin/git -C "$s21a_repo" -c safe.directory="$s21a_repo" checkout --quiet --detach \
    "$target_commit" || fail "cannot checkout immutable S21A target"
  /usr/bin/env -i PATH=/usr/bin:/bin:/home/pallasting/.cargo/bin LC_ALL=C TZ=UTC \
    CARGO_BUILD_JOBS=1 RUST_TEST_THREADS=1 \
    "$s21a_repo/$s21a_gate_path" full-replay >"$tmp/s21a.log" 2>&1 || {
      /usr/bin/tail -n 200 "$tmp/s21a.log" >&2 || true
      fail "immutable S21A serial offline full replay failed"
    }
  s21a_required_receipts=(
    $'validation_tier\tFULL_REPLAY_SERIAL_OFFLINE_PRIVATE_ARCHIVE_ONLY_CARGO'
    $'release_qualification\tRELEASE_VALIDATION_PASS_NON_LIVE_ONLY'
    $'rust_s21a_replay\tPASS'
    $'frozen_s20b_full_replay\tPASS'
    $'live_canary\tNOT_RUN'
    $'side_effects_unlocked\tNONE'
    $'gate\tFULL_REPLAY_PASS_NON_LIVE_FINAL_REFREEZE_ADMISSION_ONLY'
  )
  for row in "${s21a_required_receipts[@]}"; do
    /usr/bin/grep -Fx "$row" "$tmp/s21a.log" >/dev/null \
      || fail "immutable S21A replay receipt incomplete: $row"
  done
  s21a_full_replay="PASS"
fi

if [[ "$validation_tier" == fast ]]; then
  printf '%s\n' \
    $'validation_tier\tFAST_IDENTITY_SCHEMA_SEMANTIC_BLOCKED_AUDIT_NO_RUST' \
    $'release_qualification\tNON_RELEASE' \
    $'s21a_full_replay\tNOT_RUN' \
    $'presign_closure_status\tBLOCKED' \
    $'owner_signature\tNOT_REQUESTED' \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFAST_PASS_NON_LIVE_BLOCKED_PRESIGN_CLOSURE_ONLY'
else
  printf '%s\n' \
    $'validation_tier\tFULL_REPLAY_SERIAL_OFFLINE_IMMUTABLE_S21A_GATE_ONLY' \
    $'release_qualification\tRELEASE_VALIDATION_PASS_NON_LIVE_BLOCKED_ONLY' \
    $'s21a_full_replay\t'"$s21a_full_replay" \
    $'presign_closure_status\tBLOCKED' \
    $'owner_signature\tNOT_REQUESTED' \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFULL_REPLAY_PASS_NON_LIVE_BLOCKED_PRESIGN_CLOSURE_ONLY'
fi
