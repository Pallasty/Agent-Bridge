#!/usr/bin/env -S -i /usr/bin/bash
# Exact-baseline gate for S20B non-live rich-packet builders and validators.
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
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'S20B owned-lab rich-packet gate failed: %s\n' "$*" >&2
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
    /usr/bin/bwrap /home/pallasting/.cargo/bin/cargo /usr/bin/time /usr/bin/wc
    /home/pallasting/.cargo/bin/rustc /home/pallasting/.cargo/bin/rustfmt
  )
fi
for tool in "${required_tools[@]}"; do
  [[ -x "$tool" ]] || fail "missing required tool: $tool"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "$repo_root" == /* && -d "$repo_root" && ! -L "$repo_root" ]] \
  || fail "repository root is not one canonical directory"

baseline_commit="bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
baseline_tree="c752a2069fa2d3e5d0e1241bf2342987338f0db5"
baseline_parent="0b76cc23534a230ec3be92cfaeed55503c69478c"
frozen_s20_commit="0b76cc23534a230ec3be92cfaeed55503c69478c"
frozen_s20_tree="dc2c1a027728311c51e40e59eb559a8a9e8142be"
feature="temporal-evidence-s20b-owned-lab-rich-packet-validators-synthetic"

cargo_path="crates/store/Cargo.toml"
s19_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner.rs"
s20_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration.rs"
s20b_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration/rich_packet_validators.rs"
s20b_assignment_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration/rich_packet_validators/assignment_authority.rs"
s20b_schema_packets_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration/rich_packet_validators/schema_aligned_packets.rs"
s20b_s17_rust_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization/source_bound_runner/trusted_controller_orchestration/rich_packet_validators/s17_full_validator.rs"
design_path="docs/design/MEMORY_TEMPORAL_OWNED_LAB_RICH_PACKET_SCHEMA_REPLACEMENTS_S20B_2026_07_18.md"
contract_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-rich-packet-schema-replacements-contract-s20b-v0.json"
status_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-rich-packet-schema-replacements-status-s20b-v0.json"
preflight_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-schema-s20b-v0.json"
preflight_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-synthetic-s20b-v0.json"
control_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-schema-s20b-v0.json"
control_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-synthetic-s20b-v0.json"
claim_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-schema-s20b-v0.json"
claim_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-synthetic-s20b-v0.json"
postrun_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-schema-s20b-v0.json"
postrun_fixture_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-synthetic-s20b-v0.json"
successor_path="docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s20b-v0.json"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-rich-packet-schema-replacements-s20b.md"
checker_path="scripts/eval/check_memory_temporal_owned_lab_rich_packet_schema_replacements_s20b.py"
expected_path="scripts/eval/fixtures/memory_temporal_owned_lab_rich_packet_schema_replacements_s20b.expected.v0.tsv"
gate_path="scripts/check-memory-temporal-owned-lab-rich-packet-schema-replacements-s20b.sh"
s20_gate_path="scripts/check-memory-temporal-owned-lab-trusted-controller-orchestration-s20.sh"

packet_paths=(
  "$cargo_path" "$s19_rust_path" "$s20_rust_path" "$s20b_rust_path"
  "$s20b_assignment_rust_path" "$s20b_schema_packets_rust_path" "$s20b_s17_rust_path"
  "$design_path" "$contract_path" "$status_path"
  "$preflight_schema_path" "$preflight_fixture_path"
  "$control_schema_path" "$control_fixture_path"
  "$claim_schema_path" "$claim_fixture_path"
  "$postrun_schema_path" "$postrun_fixture_path"
  "$successor_path" "$report_path" "$checker_path" "$expected_path" "$gate_path"
)
packet_modes=(
  100644 100644 100644 100644 100644 100644 100644 100644 100644 100644
  100644 100644 100644 100644 100644 100644 100644 100644 100644 100644
  100644 100644 100755
)
report_binding_paths=(
  "$cargo_path" "$s19_rust_path" "$s20_rust_path" "$s20b_rust_path"
  "$s20b_assignment_rust_path" "$s20b_schema_packets_rust_path" "$s20b_s17_rust_path"
  "$design_path" "$contract_path" "$status_path"
  "$preflight_schema_path" "$preflight_fixture_path"
  "$control_schema_path" "$control_fixture_path"
  "$claim_schema_path" "$claim_fixture_path"
  "$postrun_schema_path" "$postrun_fixture_path"
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
head_oid="$(git_clean rev-parse --verify HEAD)" || fail "cannot resolve HEAD"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] || fail "shallow history"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] || fail "Git replace refs"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)"
[[ "$common_dir" == /* && -d "$common_dir" && ! -L "$common_dir" ]] || fail "non-canonical Git common dir"
[[ ! -e "$common_dir/shallow" && ! -e "$common_dir/info/grafts" ]] || fail "shallow/graft state present"
[[ ! -s "$common_dir/objects/info/alternates" ]] || fail "Git alternates present"
[[ -z "${GIT_OBJECT_DIRECTORY:-}${GIT_ALTERNATE_OBJECT_DIRECTORIES:-}" ]] || fail "Git object environment present"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index is not clean"

[[ "$(git_clean cat-file -t "$baseline_commit")" == commit ]] || fail "baseline unavailable"
[[ "$(git_clean show -s --format='%T' "$baseline_commit")" == "$baseline_tree" ]] || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "$baseline_commit")" == "$baseline_parent" ]] || fail "baseline parent drift"
[[ "$(git_clean show -s --format='%T' "$frozen_s20_commit")" == "$frozen_s20_tree" ]] || fail "frozen S20 tree drift"
[[ "$(raw_blob_sha256 "$baseline_commit" "$cargo_path")" == "6c94045720ca77b0a037c9196171960a323f8adadb5d6607b4464eae1d430097" ]] \
  || fail "baseline Cargo hash drift"
[[ "$(raw_blob_sha256 "$baseline_commit" "$s19_rust_path")" == "d9a35534f3c92a9cef3820434cd0bf5ab22c453ca9721712c5c4c595fcea8dc1" ]] \
  || fail "baseline S19 runner hash drift"
[[ "$(raw_blob_sha256 "$baseline_commit" "$s20_rust_path")" == "9c1b1cac42eb541aeb3c566c1356dc0ca66805e9b41304375b22d2e5cdd0bf81" ]] \
  || fail "baseline S20 parent hash drift"

head_lineage=()
IFS=' ' read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "$head_oid") \
  || fail "cannot resolve HEAD topology"
head_parents=("${head_lineage[@]:1}")
mode="" source_commit=""
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
[[ "$(git_clean rev-list --count "$baseline_commit..$source_commit")" == 1 ]] \
  || fail "source is not one exact commit over baseline"

declare -A expected_delta=(
  ["$cargo_path"]="M" ["$s19_rust_path"]="M" ["$s20_rust_path"]="M"
  ["$s20b_rust_path"]="A" ["$s20b_assignment_rust_path"]="A"
  ["$s20b_schema_packets_rust_path"]="A" ["$s20b_s17_rust_path"]="A"
  ["$design_path"]="A" ["$contract_path"]="A"
  ["$status_path"]="A" ["$preflight_schema_path"]="A" ["$preflight_fixture_path"]="A"
  ["$control_schema_path"]="A" ["$control_fixture_path"]="A"
  ["$claim_schema_path"]="A" ["$claim_fixture_path"]="A"
  ["$postrun_schema_path"]="A" ["$postrun_fixture_path"]="A"
  ["$successor_path"]="A" ["$report_path"]="A" ["$checker_path"]="A"
  ["$expected_path"]="A" ["$gate_path"]="A"
)
actual_delta_count=0
while IFS=$'\t' read -r delta_status delta_path delta_extra; do
  [[ -n "$delta_status" && -n "$delta_path" && -z "${delta_extra:-}" ]] || fail "malformed delta row"
  [[ -v "expected_delta[$delta_path]" ]] || fail "unexpected delta path: $delta_path"
  [[ "${expected_delta[$delta_path]}" == "$delta_status" ]] || fail "wrong delta status: $delta_path"
  unset 'expected_delta[$delta_path]'
  actual_delta_count=$((actual_delta_count + 1))
done < <(git_clean diff-tree --no-commit-id --name-status --no-renames -r "$baseline_commit" "$source_commit")
[[ "$actual_delta_count" == 23 && "${#expected_delta[@]}" == 0 ]] \
  || fail "delta is not exact 3M+20A closed packet"

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[$index]}" expected_mode="${packet_modes[$index]}"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")"
  [[ -n "$source_entry" && "${source_entry%% *}" == "$expected_mode" ]] || fail "source path/mode drift: $path"
  [[ "$source_entry" == "$(git_clean ls-tree "$head_oid" -- "$path")" ]] \
    || fail "source/HEAD packet blob or mode mismatch: $path"
done

tmp="$(/usr/bin/mktemp -d -p /Data/CascadeProjects .ab-s20b-gate.XXXXXXXX)" \
  || fail "cannot allocate bounded scratch under /Data"
cleanup() { /usr/bin/rm -rf -- "$tmp"; }
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
for seed in 20021 20099; do
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    /usr/bin/python3 -I "$checker" --repo "$tmp/source" --seed "$seed" \
    >"$tmp/checker-$seed.tsv" || fail "checker seed $seed failed"
done
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$checker" --repo "$tmp/source" --seed 20077 --self-test \
  >"$tmp/checker-self.tsv" || fail "checker mutation self-test failed"
/usr/bin/cmp -s "$tmp/checker-20021.tsv" "$tmp/checker-20099.tsv" || fail "checker output depends on seed"
/usr/bin/cmp -s "$tmp/checker-20021.tsv" "$tmp/checker-self.tsv" || fail "self-test receipt drift"
/usr/bin/cmp -s "$tmp/checker-20021.tsv" "$expected" || fail "expected receipt mismatch"

report="$tmp/source/$report_path"
[[ -f "$report" && ! -L "$report" ]] || fail "report absent"
/usr/bin/grep -Fx 'Hash table state: **FINAL_CLOSED_WORLD_BOUND**' "$report" >/dev/null \
  || fail "report final-state token absent"
/usr/bin/grep -Fx '## Final artifact digest table' "$report" >/dev/null \
  || fail "report digest-table heading absent"
! /usr/bin/grep -E 'TODO_FINAL_SHA256|NON_FINAL|IMPLEMENTATION_PENDING|TODO markers' "$report" >/dev/null \
  || fail "report contains non-final markers"
report_binding_count="$(/usr/bin/grep -Ec '^\| [^|]+ \| [0-9a-f]{64} \|$' "$report")"
[[ "$report_binding_count" == "${#report_binding_paths[@]}" ]] \
  || fail "report digest table is not exact 22 rows"
for path in "${report_binding_paths[@]}"; do
  digest="$(/usr/bin/sha256sum "$tmp/source/$path" | /usr/bin/awk '{print $1}')"
  [[ "$(/usr/bin/grep -Fxc -- "| $path | $digest |" "$report")" == 1 ]] \
    || fail "report lacks exact path/hash binding: $path"
done

rust_s20b_replay="NOT_RUN"
frozen_s20_full_replay="NOT_RUN"
cargo_registry_archive_count="NOT_RUN"
cargo_registry_checksum_catalog_sha256="NOT_RUN"
rust_maximum_resident_set_kbytes="NOT_RUN"
rust_swaps="NOT_RUN"
if [[ "$validation_tier" == full-replay ]]; then
  /usr/bin/mkdir -m 0700 \
    "$tmp/cargo-seed-registry" "$tmp/cargo-seed-registry/cache" \
    "$tmp/cargo-home" "$tmp/cargo-home/registry" "$tmp/cargo-target" \
    "$tmp/cargo-tmp" "$tmp/home" "$tmp/s20b-sqlite"
  trusted_registry="/home/pallasting/.cargo/registry"
  [[ -d "$trusted_registry/cache" && ! -L "$trusted_registry/cache" ]] || fail "trusted Cargo cache missing"
  [[ -d "$trusted_registry/index" && ! -L "$trusted_registry/index" ]] || fail "trusted Cargo index missing"
  /usr/bin/cp -a --no-preserve=ownership "$trusted_registry/index" "$tmp/cargo-seed-registry/index" \
    || fail "cannot snapshot Cargo index"
  [[ ! -e "$tmp/cargo-seed-registry/src" ]] || fail "registry/src entered private seed"
  [[ -z "$(/usr/bin/find "$tmp/cargo-seed-registry" -type l -print -quit)" ]] || fail "private seed contains symlink"
  [[ "$(/usr/bin/sha256sum "$tmp/head/Cargo.lock" | /usr/bin/awk '{print $1}')" == \
      "408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59" ]] \
    || fail "Cargo.lock raw hash drift"

  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    /usr/bin/python3 -I - "$tmp/head/Cargo.lock" "$trusted_registry/cache" \
    "$tmp/cargo-seed-registry/cache" >"$tmp/cargo-catalog.tsv" <<'PY'
import hashlib
import pathlib
import shutil
import sys
import tomllib

lock_path = pathlib.Path(sys.argv[1])
trusted = pathlib.Path(sys.argv[2])
private = pathlib.Path(sys.argv[3])
packages = [
    package for package in tomllib.loads(lock_path.read_text(encoding="utf-8"))["package"]
    if str(package.get("source", "")).startswith("registry+")
]
if len(packages) != 555:
    raise SystemExit(f"registry package count drift: {len(packages)}")
rows = []
for package in packages:
    name, version, checksum = package["name"], package["version"], package.get("checksum")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise SystemExit(f"bad lock checksum: {name} {version}")
    archives = list(trusted.rglob(f"{name}-{version}.crate"))
    if len(archives) != 1:
        raise SystemExit(f"archive multiplicity {len(archives)}: {name} {version}")
    source = archives[0]
    relative = source.relative_to(trusted)
    if source.is_symlink() or not source.is_file() or len(relative.parts) != 2:
        raise SystemExit(f"invalid archive path: {relative}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
        raise SystemExit(f"archive checksum mismatch: {name} {version}")
    destination = private / relative
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if destination.is_symlink() or hashlib.sha256(destination.read_bytes()).hexdigest() != checksum:
        raise SystemExit(f"private archive mismatch: {name} {version}")
    rows.append(f"{name}\t{version}\t{checksum}\n")
archives = sorted(private.rglob("*.crate"))
if len(archives) != 555:
    raise SystemExit(f"private archive count drift: {len(archives)}")
catalog = "".join(sorted(rows)).encode("ascii")
print("cargo_registry_archive_count\t555")
print("cargo_registry_checksum_catalog_sha256\t" + hashlib.sha256(catalog).hexdigest())
PY
  cargo_registry_archive_count="$(/usr/bin/awk -F '\t' '$1=="cargo_registry_archive_count" {print $2}' "$tmp/cargo-catalog.tsv")"
  cargo_registry_checksum_catalog_sha256="$(/usr/bin/awk -F '\t' '$1=="cargo_registry_checksum_catalog_sha256" {print $2}' "$tmp/cargo-catalog.tsv")"
  [[ "$cargo_registry_archive_count" == 555 ]] || fail "Cargo archive count drift"
  [[ "$cargo_registry_checksum_catalog_sha256" == "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8" ]] \
    || fail "Cargo archive catalog drift"
  /usr/bin/cp -a --reflink=auto --no-preserve=ownership "$tmp/cargo-seed-registry/cache" \
    "$tmp/cargo-home/registry/cache" || fail "cannot copy private Cargo cache"
  /usr/bin/cp -a --no-preserve=ownership "$tmp/cargo-seed-registry/index" \
    "$tmp/cargo-home/registry/index" || fail "cannot copy private Cargo index"
  [[ -z "$(/usr/bin/find "$tmp/cargo-home/registry" -type l -print -quit)" ]] \
    || fail "private Cargo home contains symlink"
  [[ ! -e "$tmp/cargo-home/registry/src" ]] || fail "registry/src copied before replay"

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
    AB_S20_TEST_SCRATCH="$tmp/s20b-sqlite"
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
  )
  (
    cd "$tmp/head"
    "${rust_env[@]}" /home/pallasting/.cargo/bin/rustfmt --edition 2021 --check \
      "$s19_rust_path" "$s20_rust_path" "$s20b_rust_path" \
      "$s20b_assignment_rust_path" "$s20b_schema_packets_rust_path" "$s20b_s17_rust_path"
    "${rust_env[@]}" /usr/bin/bwrap --die-with-parent --unshare-net --bind / / --dev /dev \
      --chdir "$tmp/head" /usr/bin/time -v -o "$tmp/rust-time.log" \
      /home/pallasting/.cargo/bin/cargo test --locked --offline \
        -p ab-store --lib --no-default-features --features "$feature" -j1 \
        trusted_controller_orchestration -- --test-threads=1
  ) >"$tmp/rust.log" 2>&1 || {
    /usr/bin/tail -n 200 "$tmp/rust.log" >&2 || true
    fail "Rust S20B serial offline replay failed"
  }
  rust_test_count="$(/usr/bin/awk -F '\t' '$1=="rust_trusted_controller_test_count" {print $2}' "$tmp/checker-20021.tsv")"
  /usr/bin/grep -F "test result: ok. $rust_test_count passed; 0 failed" "$tmp/rust.log" >/dev/null \
    || fail "Rust S20B test count receipt mismatch"
  rust_maximum_resident_set_kbytes="$(/usr/bin/awk -F ': ' '$1 ~ /Maximum resident set size/ {print $2}' "$tmp/rust-time.log")"
  rust_swaps="$(/usr/bin/awk -F ': ' '$1 ~ /^[[:space:]]*Swaps/ {print $2}' "$tmp/rust-time.log")"
  [[ "$rust_maximum_resident_set_kbytes" =~ ^[0-9]+$ && "$rust_swaps" =~ ^[0-9]+$ ]] \
    || fail "Rust resource receipts absent"
  rust_s20b_replay="PASS"

  s20_repo="$tmp/s20-integrated"
  git_clean clone --quiet --no-hardlinks "$repo_root" "$s20_repo" || fail "cannot clone frozen S20 replay"
  [[ ! -s "$s20_repo/.git/objects/info/alternates" ]] || fail "S20 replay clone uses alternates"
  /usr/bin/git -C "$s20_repo" -c safe.directory="$s20_repo" checkout --quiet --detach "$frozen_s20_commit" \
    || fail "cannot checkout frozen S20 integration"
  "$s20_repo/$s20_gate_path" full-replay >"$tmp/s20.log" 2>&1 || {
    /usr/bin/tail -n 200 "$tmp/s20.log" >&2 || true
    fail "frozen S20 full replay failed"
  }
  s20_required_receipts=(
    $'validation_tier\tFULL_REPLAY_SERIAL_OFFLINE_PRIVATE_ARCHIVE_ONLY_CARGO'
    $'release_qualification\tRELEASE_VALIDATION_PASS_NON_LIVE_ONLY'
    $'rust_s20_replay\tPASS'
    $'frozen_s19_full_replay\tPASS'
    $'live_canary\tNOT_RUN'
    $'side_effects_unlocked\tNONE'
    $'gate\tFULL_REPLAY_PASS_NON_LIVE_TRUSTED_CONTROLLER_ORCHESTRATION_SYNTHETIC_ONLY'
  )
  for receipt in "${s20_required_receipts[@]}"; do
    /usr/bin/grep -Fx "$receipt" "$tmp/s20.log" >/dev/null \
      || fail "frozen S20 receipt incomplete: $receipt"
  done
  frozen_s20_full_replay="PASS"
fi

if [[ "$validation_tier" == fast ]]; then
  printf '%s\n' \
    $'validation_tier\tFAST_CONTENT_SCHEMA_SEMANTIC_IDENTITY_ONLY_NO_RUST_OR_PREDECESSOR_REPLAY' \
    $'periodic_or_final_validation_required\ttrue' \
    $'release_qualification\tNON_RELEASE' \
    $'rust_s20b_replay\tNOT_RUN' \
    $'frozen_s20_full_replay\tNOT_RUN' \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFAST_PASS_NON_LIVE_RICH_PACKET_VALIDATORS_ONLY'
else
  printf '%s\n' \
    $'validation_tier\tFULL_REPLAY_SERIAL_OFFLINE_PRIVATE_ARCHIVE_ONLY_CARGO' \
    $'periodic_or_final_validation_required\tfalse' \
    $'release_qualification\tRELEASE_VALIDATION_PASS_NON_LIVE_ONLY' \
    $'rust_s20b_replay\t'"$rust_s20b_replay" \
    $'frozen_s20_full_replay\t'"$frozen_s20_full_replay" \
    $'frozen_s20_replay_boundary\tFROZEN_GATE_NATIVE_HOST_WITH_OWN_OFFLINE_CONTROLS' \
    $'cargo_registry_archive_count\t'"$cargo_registry_archive_count" \
    $'cargo_registry_checksum_catalog_sha256\t'"$cargo_registry_checksum_catalog_sha256" \
    $'rust_maximum_resident_set_kbytes\t'"$rust_maximum_resident_set_kbytes" \
    $'rust_swaps\t'"$rust_swaps" \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFULL_REPLAY_PASS_NON_LIVE_RICH_PACKET_VALIDATORS_ONLY'
fi
