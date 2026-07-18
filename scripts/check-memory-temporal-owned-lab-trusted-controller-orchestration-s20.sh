#!/usr/bin/env -S -i /usr/bin/bash
# Exact-baseline gate for the S20 non-live trusted-controller orchestration kernel.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "$imported_function"
done < <(builtin compgen -A function)

PATH="/usr/bin:/bin:/home/pallasting/.cargo/bin"
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
export GIT_ATTR_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
unset BASH_ENV ENV CDPATH LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset CARGO_ENCODED_RUSTFLAGS CARGO_HOME RUSTUP_HOME RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'S20 owned-lab trusted-controller orchestration gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "$validation_tier" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: $validation_tier" ;;
esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/cmp /usr/bin/cp /usr/bin/dirname
  /usr/bin/env /usr/bin/find /usr/bin/git /usr/bin/grep /usr/bin/mkdir
  /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm /usr/bin/sha256sum
  /usr/bin/stat /usr/bin/tail /usr/bin/tar
)
if [[ "$validation_tier" == full-replay ]]; then
  required_tools+=(
    /usr/bin/bwrap /home/pallasting/.cargo/bin/cargo
    /usr/bin/time /usr/bin/wc /home/pallasting/.cargo/bin/rustc
    /home/pallasting/.cargo/bin/rustfmt
  )
fi
for tool in "${required_tools[@]}"; do
  [[ -x "$tool" ]] || fail "missing required tool: $tool"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "$repo_root" == /* && -d "$repo_root" && ! -L "$repo_root" ]] \
  || fail "repository root is not one canonical directory"

baseline_commit="b90740ebd44632ae4ad88995938890e682d58b18"
baseline_tree="2d3c7c7ae486fd63777a83880c3337462bd9c39f"
baseline_parents="61585e655f7bfd537f8a123141e4e39a590a66d8 1c0f8c77eb730b530d2e026f46c7ba22ffcebd97"
s19_source_commit="1c0f8c77eb730b530d2e026f46c7ba22ffcebd97"
s19_source_tree="826db40e5f499c845b544cc87e6d55ccb85ef3ae"
s19_source_parent="85f686dde161f25166b8f38c38b9a05bd7957bfd"
feature="temporal-evidence-s20-owned-lab-trusted-controller-orchestration-synthetic"

cargo_path="crates/store/Cargo.toml"
s18_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization.rs"
s19_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner.rs"
s20_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration.rs"
design_path="docs/design/MEMORY_TEMPORAL_OWNED_LAB_TRUSTED_CONTROLLER_ORCHESTRATION_S20_2026_07_18.md"
contract_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-trusted-controller-orchestration-contract-s20-v0.json"
status_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-trusted-controller-orchestration-status-s20-v0.json"
checkpoint_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-anti-rollback-checkpoint-schema-s20-v0.json"
checkpoint_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-anti-rollback-checkpoint-synthetic-s20-v0.json"
attempt_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-one-shot-attempt-tombstone-schema-s20-v0.json"
attempt_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-one-shot-attempt-tombstone-synthetic-s20-v0.json"
action_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-action-start-linearization-receipt-schema-s20-v0.json"
action_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-action-start-linearization-receipt-synthetic-s20-v0.json"
index_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-exact-canary-run-index-schema-s20-v0.json"
index_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-exact-canary-run-index-synthetic-s20-v0.json"
successor_path="docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s20-v0.json"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-trusted-controller-orchestration-s20.md"
checker_path="scripts/eval/check_memory_temporal_owned_lab_trusted_controller_orchestration_s20.py"
expected_path="scripts/eval/fixtures/memory_temporal_owned_lab_trusted_controller_orchestration_s20.expected.v0.tsv"
gate_path="scripts/check-memory-temporal-owned-lab-trusted-controller-orchestration-s20.sh"
s19_gate_path="scripts/check-memory-temporal-owned-lab-source-bound-runner-s19.sh"

packet_paths=(
  "$cargo_path" "$s18_rust_path" "$s19_rust_path" "$s20_rust_path"
  "$design_path" "$contract_path" "$status_path"
  "$checkpoint_schema_path" "$checkpoint_fixture_path"
  "$attempt_schema_path" "$attempt_fixture_path"
  "$action_schema_path" "$action_fixture_path"
  "$index_schema_path" "$index_fixture_path"
  "$successor_path" "$report_path" "$checker_path" "$expected_path" "$gate_path"
)
packet_modes=(
  100644 100644 100644 100644 100644 100644 100644 100644 100644 100644
  100644 100644 100644 100644 100644 100644 100644 100644 100644 100755
)
schema_paths=(
  "$checkpoint_schema_path" "$attempt_schema_path" "$action_schema_path" "$index_schema_path"
)
fixture_paths=(
  "$checkpoint_fixture_path" "$attempt_fixture_path" "$action_fixture_path" "$index_fixture_path"
)
report_binding_paths=(
  "$cargo_path" "$s18_rust_path" "$s19_rust_path" "$s20_rust_path"
  "$design_path" "$contract_path" "$status_path"
  "$checkpoint_schema_path" "$checkpoint_fixture_path"
  "$attempt_schema_path" "$attempt_fixture_path"
  "$action_schema_path" "$action_fixture_path"
  "$index_schema_path" "$index_fixture_path"
  "$successor_path" "$checker_path" "$expected_path" "$gate_path"
)

declare -A frozen_s19_artifacts=(
  ["docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-schema-s19-v0.json"]="e8c75dc6fc15d8ca745ff3c27dc3ab7306036429517de9bcfc06cbc063b22495"
  ["docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-schema-s19-v0.json"]="989091d08d3ffa48b97df8a85ef239846d5cee5581d398bcd0a22eee4dfb2aef"
  ["docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-schema-s19-v0.json"]="fcfa9fb441385b30209af48ca130dc93362a98dd5f966c9516b1c8d512774481"
  ["docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-schema-s19-v0.json"]="723627a925c5d876bc210d0ce478a44a439ed7129a7f2f05620a0e63aba038fd"
  ["docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-schema-s19-v0.json"]="f3ecbf2a03ba2c9def0e0d06c0fd2371aede65c79c09fe7f5cc7b907874de491"
  ["scripts/check-memory-temporal-owned-lab-source-bound-runner-s19.sh"]="1b33ee073bb6fbf4446a4f92e4dfc195f32b54b0cdfb48311ab79cf171a02b8f"
  ["scripts/eval/check_memory_temporal_owned_lab_source_bound_runner_s19.py"]="294c9fc3b9ecd12276959a498ff827a1b12df1d00c12f9595ddc73dc2d0771fa"
  ["scripts/eval/fixtures/memory_temporal_owned_lab_source_bound_runner_s19.expected.v0.tsv"]="5468d235a8f9eebffad298b854152e7261d4436a79fa0846081470bc18e7f9d0"
  ["docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-owned-lab-source-bound-runner-s19.md"]="58073a661281448798291b585606df6e0ef85f098506f1832052e2de8eadba9e"
)

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="$repo_root" "$@"
}

raw_blob_sha256() {
  local commit="$1"
  local path="$2"
  git_clean cat-file blob "$commit:$path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}'
}

[[ "$(git_clean config --get-all safe.directory)" == "$repo_root" ]] \
  || fail "Git trust scope is not the exact repository root"
head_oid="$(git_clean rev-parse --verify HEAD)" || fail "cannot resolve HEAD"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] || fail "shallow history"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] || fail "Git replace refs"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)"
[[ "$common_dir" == /* && -d "$common_dir" && ! -L "$common_dir" ]] || fail "non-canonical Git common dir"
[[ ! -e "$common_dir/shallow" ]] || fail "shallow file present"
[[ ! -e "$common_dir/info/grafts" ]] || fail "Git grafts present"
[[ ! -s "$common_dir/objects/info/alternates" ]] || fail "Git alternates present"
[[ -z "${GIT_OBJECT_DIRECTORY:-}${GIT_ALTERNATE_OBJECT_DIRECTORIES:-}" ]] || fail "Git object environment present"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index is not clean"

[[ "$(git_clean cat-file -t "$baseline_commit")" == commit ]] || fail "baseline unavailable"
[[ "$(git_clean show -s --format='%T' "$baseline_commit")" == "$baseline_tree" ]] || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "$baseline_commit")" == "$baseline_parents" ]] || fail "baseline parents drift"
[[ "$(git_clean cat-file -t "$s19_source_commit")" == commit ]] || fail "S19 source unavailable"
[[ "$(git_clean show -s --format='%T' "$s19_source_commit")" == "$s19_source_tree" ]] || fail "S19 source tree drift"
[[ "$(git_clean show -s --format='%P' "$s19_source_commit")" == "$s19_source_parent" ]] || fail "S19 source parent drift"

head_lineage=()
IFS=' ' read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "$head_oid") \
  || fail "cannot resolve HEAD topology"
head_parents=("${head_lineage[@]:1}")
mode=""
source_commit=""
if [[ "${#head_parents[@]}" == 1 && "${head_parents[0]}" == "$baseline_commit" ]]; then
  mode="source"
  source_commit="$head_oid"
elif [[ "${#head_parents[@]}" == 2 ]]; then
  mode="integrated"
  first_parent="${head_parents[0]}"
  source_commit="${head_parents[1]}"
  source_lineage=()
  IFS=' ' read -r -a source_lineage < <(git_clean rev-list --parents -n 1 "$source_commit") \
    || fail "cannot resolve source topology"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "$baseline_commit" ]] \
    || fail "integrated second parent is not exact-baseline source"
  git_clean merge-base --is-ancestor "$baseline_commit" "$first_parent" \
    || fail "integration first parent does not descend from baseline"
  if git_clean merge-base --is-ancestor "$source_commit" "$first_parent"; then
    fail "integration first parent already contains source"
  fi
else
  fail "HEAD must be exact-baseline source or exact two-parent integration"
fi
[[ "$source_commit" != "$baseline_commit" ]] || fail "source commit equals baseline"
[[ "$(git_clean rev-list --count "$baseline_commit..$source_commit")" == 1 ]] \
  || fail "source contains historical descendants beyond one exact commit"

declare -A expected_delta=(
  ["$cargo_path"]="M"
  ["$s18_rust_path"]="M"
  ["$s19_rust_path"]="M"
  ["$s20_rust_path"]="A"
  ["$design_path"]="A"
  ["$contract_path"]="A"
  ["$status_path"]="A"
  ["$checkpoint_schema_path"]="A"
  ["$checkpoint_fixture_path"]="A"
  ["$attempt_schema_path"]="A"
  ["$attempt_fixture_path"]="A"
  ["$action_schema_path"]="A"
  ["$action_fixture_path"]="A"
  ["$index_schema_path"]="A"
  ["$index_fixture_path"]="A"
  ["$successor_path"]="A"
  ["$report_path"]="A"
  ["$checker_path"]="A"
  ["$expected_path"]="A"
  ["$gate_path"]="A"
)
actual_delta_count=0
while IFS=$'\t' read -r delta_status delta_path delta_extra; do
  [[ -n "$delta_status" && -n "$delta_path" && -z "${delta_extra:-}" ]] \
    || fail "malformed delta row"
  [[ -v "expected_delta[$delta_path]" ]] || fail "unexpected delta path: $delta_path"
  [[ "${expected_delta[$delta_path]}" == "$delta_status" ]] \
    || fail "wrong delta status for $delta_path"
  unset 'expected_delta[$delta_path]'
  actual_delta_count=$((actual_delta_count + 1))
done < <(git_clean diff-tree --no-commit-id --name-status --no-renames -r "$baseline_commit" "$source_commit")
[[ "$actual_delta_count" == 20 && "${#expected_delta[@]}" == 0 ]] \
  || fail "delta is not exact 3M+17A closed packet"

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[$index]}"
  expected_mode="${packet_modes[$index]}"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")"
  [[ -n "$source_entry" ]] || fail "source packet path absent: $path"
  source_mode="${source_entry%% *}"
  [[ "$source_mode" == "$expected_mode" ]] || fail "wrong source mode for $path"
  head_entry="$(git_clean ls-tree "$head_oid" -- "$path")"
  [[ "$source_entry" == "$head_entry" ]] \
    || fail "source/HEAD packet mode, type, blob, or path mismatch: $path"
  source_blob="$(git_clean rev-parse "$source_commit:$path")"
  head_blob="$(git_clean rev-parse "$head_oid:$path")"
  [[ "$source_blob" == "$head_blob" ]] || fail "source/HEAD packet blob mismatch: $path"
done

[[ "$(raw_blob_sha256 "$baseline_commit" "$cargo_path")" == "5826f3e800b2337713499612317c158a8348bdc12e1e1420ea028019aa0cf66a" ]] \
  || fail "baseline Cargo.toml raw hash drift"
[[ "$(raw_blob_sha256 "$baseline_commit" "$s18_rust_path")" == "59e03d3523ffe8fdcad5bdfb5032a4e02ab574d05b6240a5039ebd3188679eb2" ]] \
  || fail "baseline S18 Rust raw hash drift"
[[ "$(raw_blob_sha256 "$baseline_commit" "$s19_rust_path")" == "be93a0956540a20280ad4a6725dffb3a1c1f63d824ad7414fe912ae84b642945" ]] \
  || fail "baseline S19 Rust raw hash drift"
for path in "${!frozen_s19_artifacts[@]}"; do
  expected_sha="${frozen_s19_artifacts[$path]}"
  [[ "$(raw_blob_sha256 "$baseline_commit" "$path")" == "$expected_sha" ]] \
    || fail "frozen S19 baseline artifact drift: $path"
  [[ "$(raw_blob_sha256 "$source_commit" "$path")" == "$expected_sha" ]] \
    || fail "frozen S19 source artifact drift: $path"
  [[ "$(raw_blob_sha256 "$head_oid" "$path")" == "$expected_sha" ]] \
    || fail "frozen S19 HEAD artifact drift: $path"
done

tmp="$(/usr/bin/mktemp -d -p /Data/CascadeProjects .ab-s20-gate.XXXXXXXX)" \
  || fail "cannot allocate bounded gate scratch under /Data"
cleanup() {
  /usr/bin/rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM
/usr/bin/mkdir -m 0700 "$tmp/source" "$tmp/head"
git_clean archive --format=tar "$source_commit" | /usr/bin/tar -xf - -C "$tmp/source" \
  || fail "cannot materialize exact source tree"
git_clean archive --format=tar "$head_oid" | /usr/bin/tar -xf - -C "$tmp/head" \
  || fail "cannot materialize exact HEAD tree"

checker="$tmp/source/$checker_path"
expected="$tmp/source/$expected_path"
[[ -f "$checker" && ! -L "$checker" && -f "$expected" && ! -L "$expected" ]] \
  || fail "checker or expected receipt absent"
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$checker" --repo "$tmp/source" --seed 2001 >"$tmp/checker-1.tsv" \
  || fail "checker seed 2001 failed"
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$checker" --repo "$tmp/source" --seed 2099 >"$tmp/checker-2.tsv" \
  || fail "checker seed 2099 failed"
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$checker" --repo "$tmp/source" --seed 2077 --self-test \
  >"$tmp/checker-self.tsv" || fail "checker mutation self-test failed"
/usr/bin/cmp -s "$tmp/checker-1.tsv" "$tmp/checker-2.tsv" || fail "checker output depends on seed"
/usr/bin/cmp -s "$tmp/checker-1.tsv" "$tmp/checker-self.tsv" || fail "self-test receipt drift"
/usr/bin/cmp -s "$tmp/checker-1.tsv" "$expected" || fail "expected receipt mismatch"

/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I - "$tmp/source" \
  "$checkpoint_schema_path" "$checkpoint_fixture_path" \
  "$attempt_schema_path" "$attempt_fixture_path" \
  "$action_schema_path" "$action_fixture_path" \
  "$index_schema_path" "$index_fixture_path" <<'PY'
import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator, ValidationError

root = pathlib.Path(sys.argv[1])
paths = sys.argv[2:]
if len(paths) != 8:
    raise SystemExit("wrong schema/fixture argument count")
for schema_name, fixture_name in zip(paths[0::2], paths[1::2]):
    schema = json.loads((root / schema_name).read_text(encoding="ascii"))
    fixture = json.loads((root / fixture_name).read_text(encoding="ascii"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(fixture)
    extra = copy.deepcopy(fixture)
    extra["unexpected_open_world_field"] = False
    try:
        validator.validate(extra)
    except ValidationError:
        pass
    else:
        raise SystemExit(f"schema accepted an unknown root property: {schema_name}")
    fail_closed_mutations = {
        "biocortex-ab-track-b-owned-lab-external-anti-rollback-checkpoint-synthetic-s20-v0.json":
            ("result", "execution_permit_release_allowed", True),
        "biocortex-ab-track-b-owned-lab-one-shot-attempt-tombstone-synthetic-s20-v0.json":
            ("result", "execution_permit_issued", True),
        "biocortex-ab-track-b-owned-lab-action-start-linearization-receipt-synthetic-s20-v0.json":
            ("start_result", "execution_started", True),
        "biocortex-ab-track-b-owned-lab-exact-canary-run-index-synthetic-s20-v0.json":
            ("evidence_outcome", "execution_occurred", True),
    }
    section, field, unsafe_value = fail_closed_mutations[pathlib.Path(fixture_name).name]
    unsafe = copy.deepcopy(fixture)
    unsafe[section][field] = unsafe_value
    try:
        validator.validate(unsafe)
    except ValidationError:
        pass
    else:
        raise SystemExit(f"schema accepted synthetic live/permit counterexample: {schema_name}")
    if pathlib.Path(fixture_name).name == "biocortex-ab-track-b-owned-lab-external-anti-rollback-checkpoint-synthetic-s20-v0.json":
        false_independence = copy.deepcopy(fixture)
        false_independence["checkpoint_binding"]["independent_failure_domain_proved"] = True
        try:
            validator.validate(false_independence)
        except ValidationError:
            pass
        else:
            raise SystemExit("checkpoint schema accepted synthetic independent-failure-domain claim")
PY

report="$tmp/source/$report_path"
[[ -f "$report" && ! -L "$report" ]] || fail "report absent"
/usr/bin/grep -Fx 'Hash table state: **FINAL_CLOSED_WORLD_BOUND**' "$report" >/dev/null \
  || fail "report final-state token absent"
/usr/bin/grep -Fx '## Final artifact digest table' "$report" >/dev/null \
  || fail "report final digest-table heading absent"
! /usr/bin/grep -E 'TODO_FINAL_SHA256|NON_FINAL|Non-final|TODO markers|must be added|IMPLEMENTATION_PENDING' \
    "$report" >/dev/null \
  || fail "report still contains non-final narrative or hash placeholders"
report_binding_row_count="$(/usr/bin/grep -Ec '^\| [^|]+ \| [0-9a-f]{64} \|$' "$report")"
[[ "$report_binding_row_count" == "${#report_binding_paths[@]}" ]] \
  || fail "report final path/hash table does not contain exactly 19 rows"
for path in "${report_binding_paths[@]}"; do
  digest="$(/usr/bin/sha256sum "$tmp/source/$path" | /usr/bin/awk '{print $1}')"
  [[ "$(/usr/bin/grep -Fxc -- "| $path | $digest |" "$report")" == 1 ]] \
    || fail "report lacks exactly one same-line final path/hash binding: $path"
done

rust_s20_replay="NOT_RUN"
frozen_s19_full_replay="NOT_RUN"
cargo_registry_archive_count="NOT_RUN"
cargo_registry_checksum_catalog_sha256="NOT_RUN"
rust_maximum_resident_set_kbytes="NOT_RUN"
rust_swaps="NOT_RUN"
if [[ "$validation_tier" == full-replay ]]; then
  /usr/bin/mkdir -m 0700 \
    "$tmp/cargo-seed-registry" "$tmp/cargo-seed-registry/cache" \
    "$tmp/cargo-home" "$tmp/cargo-home/registry" \
    "$tmp/cargo-target" \
    "$tmp/cargo-tmp" "$tmp/home" "$tmp/s20-sqlite"
  trusted_registry="/home/pallasting/.cargo/registry"
  [[ -d "$trusted_registry/cache" && ! -L "$trusted_registry/cache" ]] \
    || fail "trusted Cargo registry cache missing"
  [[ -d "$trusted_registry/index" && ! -L "$trusted_registry/index" ]] \
    || fail "trusted Cargo registry index missing"
  /usr/bin/cp -a --no-preserve=ownership "$trusted_registry/index" "$tmp/cargo-seed-registry/index" \
    || fail "cannot snapshot Cargo index"
  [[ ! -e "$tmp/cargo-seed-registry/src" ]] || fail "registry/src must never enter private seed"
  [[ -z "$(/usr/bin/find "$tmp/cargo-seed-registry" -type l -print -quit)" ]] \
    || fail "private Cargo seed contains symlink"
  [[ "$(/usr/bin/sha256sum "$tmp/head/Cargo.lock" | /usr/bin/awk '{print $1}')" == \
      "408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59" ]] \
    || fail "Cargo.lock raw hash drift"

  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    /usr/bin/python3 -I - "$tmp/head/Cargo.lock" "$trusted_registry/cache" \
    "$tmp/cargo-seed-registry/cache" \
    >"$tmp/cargo-catalog.tsv" <<'PY'
import hashlib
import pathlib
import shutil
import sys
import tomllib

lock_path = pathlib.Path(sys.argv[1])
trusted_cache_root = pathlib.Path(sys.argv[2])
private_cache_root = pathlib.Path(sys.argv[3])
lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
packages = [
    package for package in lock["package"]
    if str(package.get("source", "")).startswith("registry+")
]
if len(packages) != 555:
    raise SystemExit(f"registry package count drift: {len(packages)}")
rows = []
for package in packages:
    name = package["name"]
    version = package["version"]
    checksum = package.get("checksum")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise SystemExit(f"bad lock checksum: {name} {version}")
    archives = list(trusted_cache_root.rglob(f"{name}-{version}.crate"))
    if len(archives) != 1:
        raise SystemExit(f"archive multiplicity {len(archives)}: {name} {version}")
    source = archives[0]
    if source.is_symlink() or not source.is_file():
        raise SystemExit(f"archive is not one regular file: {name} {version}")
    relative = source.relative_to(trusted_cache_root)
    if len(relative.parts) != 2 or relative.name != f"{name}-{version}.crate":
        raise SystemExit(f"unexpected Cargo cache layout: {relative}")
    if any(parent.is_symlink() for parent in source.parents if parent != trusted_cache_root.parent):
        raise SystemExit(f"symlink in trusted archive ancestry: {relative}")
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != checksum:
        raise SystemExit(f"archive checksum mismatch: {name} {version}")
    destination = private_cache_root / relative
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists():
        raise SystemExit(f"private archive destination collision: {relative}")
    shutil.copyfile(source, destination)
    if destination.is_symlink() or not destination.is_file():
        raise SystemExit(f"private archive is not regular: {relative}")
    if hashlib.sha256(destination.read_bytes()).hexdigest() != checksum:
        raise SystemExit(f"private archive checksum mismatch: {name} {version}")
    rows.append(f"{name}\t{version}\t{checksum}\n")
private_archives = sorted(private_cache_root.rglob("*.crate"))
if len(private_archives) != 555:
    raise SystemExit(f"private archive count drift: {len(private_archives)}")
other_files = [path for path in private_cache_root.rglob("*") if path.is_file() and path.suffix != ".crate"]
if other_files:
    raise SystemExit(f"unexpected private cache files: {other_files[:3]}")
catalog = "".join(sorted(rows)).encode("ascii")
print("cargo_registry_archive_count\t555")
print("cargo_registry_checksum_catalog_sha256\t" + hashlib.sha256(catalog).hexdigest())
PY
  [[ "$(/usr/bin/find "$tmp/cargo-seed-registry/cache" -type f -name '*.crate' -print | /usr/bin/wc -l)" == 555 ]] \
    || fail "private Cargo cache does not contain exactly 555 archives"
  [[ -z "$(/usr/bin/find "$tmp/cargo-seed-registry/cache" -type f ! -name '*.crate' -print -quit)" ]] \
    || fail "private Cargo cache contains non-archive extras"
  cargo_registry_archive_count="$(/usr/bin/awk -F '\t' '$1=="cargo_registry_archive_count" {print $2}' "$tmp/cargo-catalog.tsv")"
  cargo_registry_checksum_catalog_sha256="$(/usr/bin/awk -F '\t' '$1=="cargo_registry_checksum_catalog_sha256" {print $2}' "$tmp/cargo-catalog.tsv")"
  [[ "$cargo_registry_archive_count" == 555 ]] || fail "Cargo registry archive count drift"
  [[ "$cargo_registry_checksum_catalog_sha256" == \
      "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8" ]] \
    || fail "Cargo registry checksum catalog drift"
  /usr/bin/cp -a --reflink=auto --no-preserve=ownership "$tmp/cargo-seed-registry/cache" \
    "$tmp/cargo-home/registry/cache" || fail "cannot snapshot exact Cargo archive seed"
  /usr/bin/cp -a --no-preserve=ownership "$tmp/cargo-seed-registry/index" \
    "$tmp/cargo-home/registry/index" || fail "cannot copy exact Cargo index seed"
  [[ -z "$(/usr/bin/find "$tmp/cargo-home/registry" -type l -print -quit)" ]] \
    || fail "private Cargo home contains symlink before replay"
  [[ ! -e "$tmp/cargo-home/registry/src" ]] || fail "registry/src was copied into private Cargo home"
  [[ "$(/usr/bin/find "$tmp/cargo-home/registry/cache" -type f -name '*.crate' -print | /usr/bin/wc -l)" == 555 ]] \
    || fail "private Cargo home cache does not contain exactly 555 archives"

  rust_env=(
    /usr/bin/env -i PATH=/usr/bin:/bin:/home/pallasting/.cargo/bin
    HOME="$tmp/home" TMPDIR="$tmp/cargo-tmp" LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC
    RUSTUP_HOME=/home/pallasting/.rustup CARGO_HOME="$tmp/cargo-home"
    CARGO_TARGET_DIR="$tmp/cargo-target" CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0
    CARGO_NET_OFFLINE=true CARGO_TERM_COLOR=never
    CARGO_PROFILE_DEV_CODEGEN_UNITS=256 CARGO_PROFILE_TEST_CODEGEN_UNITS=256
    CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
    RUSTC=/home/pallasting/.cargo/bin/rustc RUSTFLAGS=-C\ debuginfo=0
    RUST_TEST_THREADS=1 TOKIO_WORKER_THREADS=1 MALLOC_ARENA_MAX=2
    AB_S20_TEST_SCRATCH="$tmp/s20-sqlite"
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
  )
  (
    cd "$tmp/head"
    "${rust_env[@]}" /home/pallasting/.cargo/bin/rustfmt --edition 2021 --check \
      "$s18_rust_path" "$s19_rust_path" "$s20_rust_path"
    "${rust_env[@]}" /usr/bin/bwrap --die-with-parent --unshare-net --bind / / --dev /dev \
      --chdir "$tmp/head" /usr/bin/time -v -o "$tmp/rust-time.log" \
        /home/pallasting/.cargo/bin/cargo test --locked --offline \
          -p ab-store --lib --no-default-features --features "$feature" -j1 \
          s20_ -- --test-threads=1
  ) >"$tmp/rust.log" 2>&1 || {
    /usr/bin/tail -n 200 "$tmp/rust.log" >&2 || true
    fail "Rust S20 serial offline replay failed"
  }
  rust_test_count="$(/usr/bin/awk -F '\t' '$1=="rust_s20_test_count" {print $2}' "$tmp/checker-1.tsv")"
  /usr/bin/grep -F "test result: ok. $rust_test_count passed; 0 failed" "$tmp/rust.log" >/dev/null \
    || fail "Rust S20 test count receipt mismatch"
  rust_maximum_resident_set_kbytes="$(/usr/bin/awk -F ': ' '$1 ~ /Maximum resident set size/ {print $2}' "$tmp/rust-time.log")"
  rust_swaps="$(/usr/bin/awk -F ': ' '$1 ~ /^[[:space:]]*Swaps/ {print $2}' "$tmp/rust-time.log")"
  [[ "$rust_maximum_resident_set_kbytes" =~ ^[0-9]+$ ]] || fail "Rust maximum RSS receipt absent"
  [[ "$rust_swaps" =~ ^[0-9]+$ ]] || fail "Rust swap receipt absent"
  rust_s20_replay="PASS"

  s19_repo="$tmp/s19-integrated"
  git_clean clone --quiet --no-hardlinks "$repo_root" "$s19_repo" \
    || fail "cannot clone frozen S19 replay repository"
  [[ ! -s "$s19_repo/.git/objects/info/alternates" ]] || fail "S19 replay clone uses alternates"
  /usr/bin/git -C "$s19_repo" -c safe.directory="$s19_repo" checkout --quiet --detach "$baseline_commit" \
    || fail "cannot checkout frozen S19 integration"
  # The frozen predecessor chain must retain the host's root-owned 01777 /tmp
  # and create its own nested namespaces.  An additional unprivileged outer
  # bwrap maps host root to nobody and makes that frozen invariant impossible.
  # Invoke the frozen S19 gate through its clean-environment shebang instead;
  # S19 and every nested predecessor retain their own frozen offline controls.
  "$s19_repo/$s19_gate_path" full-replay >"$tmp/s19.log" 2>&1 || {
      /usr/bin/tail -n 200 "$tmp/s19.log" >&2 || true
      fail "frozen S19 full replay failed"
    }
  s19_required_receipts=(
    $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_OWNED_LAB_SOURCE_BOUND_RUNNER_S19'
    $'rust_s19_non_live_cas_replay\tPASS'
    $'frozen_s18_full_replay\tPASS'
    $'validation_tier\tFULL_RUST_NON_LIVE_CAS_AND_S18_CHAIN_REPLAY'
    $'periodic_full_replay_required\tfalse'
    $'release_status\tRELEASE_VALIDATION_PASS_NON_LIVE_ONLY'
    $'gate\tPASS'
    $'mode\tintegrated'
    $'baseline\t85f686dde161f25166b8f38c38b9a05bd7957bfd'
    $'source_commit\t1c0f8c77eb730b530d2e026f46c7ba22ffcebd97'
    $'integration_commit\tb90740ebd44632ae4ad88995938890e682d58b18'
    $'head\tb90740ebd44632ae4ad88995938890e682d58b18'
  )
  for receipt in "${s19_required_receipts[@]}"; do
    /usr/bin/grep -Fx "$receipt" "$tmp/s19.log" >/dev/null \
      || fail "frozen S19 replay receipt incomplete or drifted: $receipt"
  done
  frozen_s19_full_replay="PASS"
fi

if [[ "$validation_tier" == fast ]]; then
  printf '%s\n' \
    $'validation_tier\tFAST_CONTENT_IDENTITY_ONLY_NO_RUST_OR_PREDECESSOR_REPLAY' \
    $'periodic_or_final_validation_required\ttrue' \
    $'release_qualification\tNON_RELEASE' \
    $'rust_s20_replay\tNOT_RUN' \
    $'frozen_s19_full_replay\tNOT_RUN' \
    $'frozen_s19_replay_boundary\tNOT_RUN' \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFAST_PASS_NON_LIVE_TRUSTED_CONTROLLER_ORCHESTRATION_SYNTHETIC_ONLY'
else
  printf '%s\n' \
    $'validation_tier\tFULL_REPLAY_SERIAL_OFFLINE_PRIVATE_ARCHIVE_ONLY_CARGO' \
    $'periodic_or_final_validation_required\tfalse' \
    $'release_qualification\tRELEASE_VALIDATION_PASS_NON_LIVE_ONLY' \
    $'rust_s20_replay\t'"$rust_s20_replay" \
    $'frozen_s19_full_replay\t'"$frozen_s19_full_replay" \
    $'frozen_s19_replay_boundary\tFROZEN_GATE_NATIVE_HOST_WITH_OWN_OFFLINE_CONTROLS' \
    $'cargo_registry_archive_count\t'"$cargo_registry_archive_count" \
    $'cargo_registry_checksum_catalog_sha256\t'"$cargo_registry_checksum_catalog_sha256" \
    $'rust_maximum_resident_set_kbytes\t'"$rust_maximum_resident_set_kbytes" \
    $'rust_swaps\t'"$rust_swaps" \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFULL_REPLAY_PASS_NON_LIVE_TRUSTED_CONTROLLER_ORCHESTRATION_SYNTHETIC_ONLY'
fi
