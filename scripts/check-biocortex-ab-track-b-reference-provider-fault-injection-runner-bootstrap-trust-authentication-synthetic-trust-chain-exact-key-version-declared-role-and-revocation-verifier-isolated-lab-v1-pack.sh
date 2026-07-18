#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound gate for the public-only bootstrap-trust authentication
# synthetic verifier isolated-lab v1 pack.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

PATH="/usr/bin:/bin:/home/pallasting/.cargo/bin"
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
export GIT_ATTR_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
unset BASH_ENV ENV CDPATH LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'Bootstrap-trust verifier isolated-lab v1 gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "${validation_tier}" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: ${validation_tier}" ;;
esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/chmod /usr/bin/cmp
  /usr/bin/dirname /usr/bin/du /usr/bin/env /usr/bin/find /usr/bin/findmnt
  /usr/bin/git /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3
  /usr/bin/rm /usr/bin/rmdir /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat
  /usr/bin/tar /usr/bin/wc
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || fail "missing tool ${tool}"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not a canonical directory"

baseline_commit="61585e655f7bfd537f8a123141e4e39a590a66d8"
baseline_tree="9dcd1f700a7e4523307ef9704218b9f87a7fe5f1"
baseline_parents="2a0028eacc8fdd36463d4fa2f297f4d19807cd65 4ce033e70781a5886d986939e879f6e3f7eadebd"

supply_integration_commit="61585e655f7bfd537f8a123141e4e39a590a66d8"
supply_integration_tree="9dcd1f700a7e4523307ef9704218b9f87a7fe5f1"
supply_integration_parents="2a0028eacc8fdd36463d4fa2f297f4d19807cd65 4ce033e70781a5886d986939e879f6e3f7eadebd"
supply_source_commit="4ce033e70781a5886d986939e879f6e3f7eadebd"
supply_source_parent="b4126a4192137e741e32ebb86170884b81185cbf"
supply_gate="scripts/check-biocortex-ab-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.sh"
supply_gate_sha256="ecc81672ea4754a85128b084e6f4f5d17d3f9e3982cb9224333994138b2f8972"
supply_fast_line_count=50
supply_fast_stdout_sha256="dcd18e07ca5e25dfbb33a6903a65883efd534f35772b0676d9e74e33d91bae67"
supply_full_line_count=51
supply_full_stdout_sha256="7c48aa07f3a4fc0aa06b57d8f8bf7a00f1e03ad3dce5b96828498d911f6f3e37"

schema_path="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-v1.schema.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack.py"
fixture_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.sh"

packet_paths=(
  "${schema_path}" "${source_path}" "${checker_path}" "${fixture_path}"
  "${expected_path}" "${manifest_path}" "${report_path}" "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100755)
packet_hash_paths=(
  "${schema_path}" "${source_path}" "${checker_path}" "${fixture_path}"
  "${expected_path}" "${manifest_path}" "${report_path}"
)
packet_hashes=(
  "d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c"
  "f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341"
  "bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20"
  "31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e"
  "0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36"
  "bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b"
  "9da0b11bfc86011ca792a6c0b2836c53c55837c17ac680296f5ad595b1a32ef0"
)
checker_stdout_line_count="44"
checker_stdout_sha256="0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36"
checker_self_test_line_count="13"
checker_self_test_stdout_sha256="921bf2a83c28348a95905f6b4c41349372d38a9489a1ce3b96baa42116a4bf8c"
directed_mutation_count="116"

# Direct dependencies are exactly: supply pack 8 + original implementation
# authority pack 7 + predecessor frame/mode implementation pack 8.  The
# fixture-custodian amendment is intentionally indirect: the supply gate owns
# and replays that chain.
dependency_paths=(
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.sh"
  "scripts/eval/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_generation_provenance_receipt_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_public_vector_bundle_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json"
)
dependency_modes=(
  100644 100755 100644 100644 100644 100644 100644 100644
  100644 100755 100644 100644 100644 100644 100644
  100644 100644 100755 100644 100644 100644 100644 100644
)
dependency_hashes=(
  18ec5e3f9af4b4fee0531021b73f36babac4f6c5a9e3a4f9ddf4ae3edca62812
  ecc81672ea4754a85128b084e6f4f5d17d3f9e3982cb9224333994138b2f8972
  2a963bfab7e938deb3fce9c40765694e62d49c324322dec33b31d7ca459f661d
  844b4fe6523121297936e91737380b51023299eb2ca18b667e2e8e69953853a0
  c684184bad18fa1265a6aa5e7d5ac0c7111aa49962e66a47b4b24f6bc898e79a
  bdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0
  a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7
  451e05a19e1b30c70dbb7606ccc6f438cbee69595f8e8b7576fa255ef4ec91d7
  841df2168eaaabfb4c17dcc15e5adfd5ed9c833eb6e40bc2bd9998833549a78b
  16fdb98784a567222e98a15cf9afc7947a70055957b1e8fc1735a9d03719daa5
  f1168fad03ac6366e8d6501cbd4da3a2969d25cc6ef9f5bf85c0624de9ae545c
  7c5f1dcd53db8bdf9360e8e00a6495daa40b97d21fbf4efa1f9f3392bfbd6136
  79502975f438ed644306a392131d102e2efadae37560b3489c91547a0125e43f
  05f2fad20896cd108f0695253c617cd0c050e80ae947ec4c90f7d7684e3e344b
  e521a7aab3a3fa00dacade4da1bf88834680a878d4de425f77918734655e255e
  e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55
  a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149
  464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174
  bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1
  76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf
  775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847
  324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9
  9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04
)

require_filled() {
  local value
  for value in "$@"; do
    [[ "${value}" != __FILL_* ]] || fail "unresolved frozen placeholder: ${value}"
  done
}
require_filled "${packet_hashes[@]}" "${checker_stdout_line_count}" \
  "${checker_stdout_sha256}" "${checker_self_test_line_count}" \
  "${checker_self_test_stdout_sha256}" "${directed_mutation_count}"

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="${repo_root}" "$@"
}

[[ "$(git_clean config --get-all safe.directory)" == "${repo_root}" ]] \
  || fail "Git trust scope is not the exact repository root"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] \
  || fail "shallow repository is not admissible"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "replace refs are present"
for commit in "${baseline_commit}" "${supply_source_commit}" "${supply_source_parent}"; do
  [[ "$(git_clean cat-file -t "${commit}")" == commit ]] \
    || fail "frozen commit unavailable: ${commit}"
done
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${baseline_tree}" ]] \
  || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${baseline_parents}" ]] \
  || fail "baseline parent topology drift"
[[ "${baseline_commit}" == "${supply_integration_commit}" \
  && "$(git_clean show -s --format='%T' "${supply_integration_commit}")" == "${supply_integration_tree}" \
  && "$(git_clean show -s --format='%P' "${supply_integration_commit}")" == "${supply_integration_parents}" ]] \
  || fail "supply integration identity drift"
[[ "$(git_clean show -s --format='%P' "${supply_source_commit}")" == "${supply_source_parent}" ]] \
  || fail "supply source topology drift"

common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
  || fail "cannot resolve Git common directory"
git_dir="$(git_clean rev-parse --path-format=absolute --git-dir)" \
  || fail "cannot resolve Git directory"
[[ -d "${common_dir}" && ! -L "${common_dir}" && -d "${git_dir}" && ! -L "${git_dir}" ]] \
  || fail "Git directory lineage invalid"
case "${git_dir}" in
  "${common_dir}"|"${common_dir}"/worktrees/*) ;;
  *) fail "Git directory outside common lineage" ;;
esac
[[ ! -e "${common_dir}/info/grafts" && ! -L "${common_dir}/info/grafts" ]] \
  || fail "legacy grafts present"
[[ ! -e "${common_dir}/info/attributes" && ! -L "${common_dir}/info/attributes" ]] \
  || fail "common info attributes present"
[[ ! -e "${common_dir}/objects/info/alternates" \
  && ! -L "${common_dir}/objects/info/alternates" ]] \
  || fail "alternate object store present"
while IFS= read -r config_key; do
  case "${config_key,,}" in
    filter.*|diff.*|merge.*|core.attributesfile|include.*|includeif.*)
      fail "executable or external Git config present: ${config_key}"
      ;;
  esac
done < <(git_clean config --local --includes --name-only --list)
[[ -z "$(/usr/bin/find . -name .gitattributes -print -quit)" ]] \
  || fail "working-tree attributes present"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index dirty"

head_oid="$(git_clean rev-parse HEAD)"
read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "${head_oid}") \
  || fail "cannot resolve HEAD topology"
head_parents=("${head_lineage[@]:1}")
mode=""
source_commit=""
first_parent=""
if [[ "${#head_parents[@]}" == 1 && "${head_parents[0]}" == "${baseline_commit}" ]]; then
  mode=source
  source_commit="${head_oid}"
elif [[ "${#head_parents[@]}" == 2 ]]; then
  mode=integrated
  first_parent="${head_parents[0]}"
  source_commit="${head_parents[1]}"
  read -r -a source_lineage < <(git_clean rev-list --parents -n 1 "${source_commit}") \
    || fail "cannot resolve source topology"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "${baseline_commit}" ]] \
    || fail "integrated second parent is not exact source"
  git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" \
    || fail "integrated first parent is not a baseline descendant"
  if git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}"; then
    fail "integrated first parent already contains source"
  else
    [[ "$?" == 1 ]] || fail "cannot establish source exclusion"
  fi
else
  fail "HEAD is neither exact source nor ordinary two-parent integration"
fi
[[ "${validation_tier}" != full-replay || "${mode}" == integrated ]] \
  || fail "full replay requires ordinary integration"

tmp_base="/Data/CascadeProjects/.ab-gate-tmp"
tmp_base_created=false
if [[ ! -e "${tmp_base}" ]]; then
  /usr/bin/mkdir -m 0700 "${tmp_base}"
  tmp_base_created=true
fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" \
  && "$(cd "${tmp_base}" && builtin pwd -P)" == "${tmp_base}" \
  && "$(/usr/bin/stat -c '%F' "${tmp_base}")" == directory \
  && "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] \
  || fail "scratch root owner, mode, type, or canonical path drift"
scratch_fstype="$(/usr/bin/findmnt -T "${tmp_base}" -n -o FSTYPE)" \
  || fail "cannot resolve scratch filesystem"
case "${scratch_fstype,,}" in tmpfs|fuse*) fail "scratch requires persistent non-FUSE filesystem" ;; esac
tmp="$(/usr/bin/mktemp -d "${tmp_base}/bootstrap-trust-verifier-v1.XXXXXX")"
[[ -d "${tmp}" && ! -L "${tmp}" \
  && "$(/usr/bin/stat -c '%u' "${tmp}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp}")" == 700 ]] \
  || fail "private scratch directory drift"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  if [[ "${tmp_base_created}" == true ]]; then
    /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/archive"
max_private_scratch_bytes=67108864
check_private_scratch_limit() {
  local bytes
  bytes="$(/usr/bin/du -sb -- "${tmp}" | /usr/bin/awk '{print $1}')"
  [[ "${bytes}" =~ ^[0-9]+$ && "${bytes}" -le "${max_private_scratch_bytes}" ]] \
    || fail "private scratch exceeds ${max_private_scratch_bytes} bytes"
}

[[ "${#packet_paths[@]}" == 8 && "${#packet_modes[@]}" == 8 \
  && "${#packet_hash_paths[@]}" == 7 && "${#packet_hashes[@]}" == 7 ]] \
  || fail "eight-path packet catalog drift"
[[ "${#dependency_paths[@]}" == 23 && "${#dependency_modes[@]}" == 23 \
  && "${#dependency_hashes[@]}" == 23 ]] \
  || fail "direct dependency catalog drift"
printf '%s\n' "${packet_paths[@]}" "${dependency_paths[@]}" \
  | /usr/bin/sort >"${tmp}/protected-paths"
[[ "$(/usr/bin/wc -l <"${tmp}/protected-paths")" == 31 \
  && "$(/usr/bin/sort -u "${tmp}/protected-paths" | /usr/bin/wc -l)" == 31 ]] \
  || fail "protected archive path cardinality or uniqueness drift"

printf '%s\n' "${packet_paths[@]}" | /usr/bin/sort \
  | /usr/bin/awk '{print "A\t" $0}' >"${tmp}/expected-delta"
git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" \
  | /usr/bin/sort >"${tmp}/source-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/source-delta" \
  || fail "source is not exact eight-path all-add"
if [[ "${mode}" == integrated ]]; then
  git_clean diff-tree --no-commit-id --name-status -r "${first_parent}" "${head_oid}" \
    | /usr/bin/sort >"${tmp}/integration-delta"
  /usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/integration-delta" \
    || fail "integration first-parent delta drift"
fi

reject_symlink_components() {
  local path="$1" component cursor=""
  local -a components
  IFS=/ read -r -a components <<<"${path}"
  for component in "${components[@]}"; do
    if [[ -n "${cursor}" ]]; then cursor="${cursor}/${component}"; else cursor="${component}"; fi
    [[ ! -L "${cursor}" ]] || fail "protected path contains symlink component: ${path}"
  done
}

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[$index]}"
  expected_mode="${packet_modes[$index]}"
  reject_symlink_components "${path}"
  [[ -f "${path}" && ! -L "${path}" \
    && "$(/usr/bin/stat -c '%F' "${path}")" == "regular file" \
    && "$(/usr/bin/stat -c '%h' "${path}")" == 1 ]] \
    || fail "packet working path type drift: ${path}"
  read -r index_mode index_oid index_stage index_name < <(git_clean ls-files --stage -- "${path}") \
    || fail "cannot resolve packet index identity: ${path}"
  read -r source_mode source_type source_oid source_name < <(git_clean ls-tree "${source_commit}" -- "${path}") \
    || fail "cannot resolve packet source identity: ${path}"
  read -r head_mode head_type head_oid_path head_name < <(git_clean ls-tree "${head_oid}" -- "${path}") \
    || fail "cannot resolve packet HEAD identity: ${path}"
  [[ "${index_mode}" == "${expected_mode}" && "${source_mode}" == "${expected_mode}" \
    && "${head_mode}" == "${expected_mode}" && "${source_type}" == blob \
    && "${head_type}" == blob && "${index_stage}" == 0 \
    && "${index_name}" == "${path}" && "${source_name}" == "${path}" \
    && "${head_name}" == "${path}" && "${index_oid}" == "${source_oid}" \
    && "${head_oid_path}" == "${source_oid}" ]] \
    || fail "packet source/HEAD/index identity or mode drift: ${path}"
  [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
    || fail "packet nondefault index flag: ${path}"
  /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${source_oid}") \
    || fail "packet working/source bytes drift: ${path}"
done

for index in "${!dependency_paths[@]}"; do
  path="${dependency_paths[$index]}"
  expected_mode="${dependency_modes[$index]}"
  expected_hash="${dependency_hashes[$index]}"
  reject_symlink_components "${path}"
  [[ -f "${path}" && ! -L "${path}" \
    && "$(/usr/bin/stat -c '%F' "${path}")" == "regular file" \
    && "$(/usr/bin/stat -c '%h' "${path}")" == 1 ]] \
    || fail "dependency working path type drift: ${path}"
  read -r dep_index_mode dep_index_oid dep_index_stage dep_index_name \
    < <(git_clean ls-files --stage -- "${path}") \
    || fail "cannot resolve dependency index identity: ${path}"
  baseline_entry="$(git_clean ls-tree "${baseline_commit}" -- "${path}")"
  source_entry="$(git_clean ls-tree "${source_commit}" -- "${path}")"
  head_entry="$(git_clean ls-tree "${head_oid}" -- "${path}")"
  [[ -n "${baseline_entry}" && "${baseline_entry}" == "${source_entry}" \
    && "${source_entry}" == "${head_entry}" ]] \
    || fail "dependency Git identity drift: ${path}"
  read -r dep_mode dep_type dep_oid dep_name <<<"${baseline_entry}"
  [[ "${dep_mode}" == "${expected_mode}" && "${dep_type}" == blob \
    && "${dep_name}" == "${path}" && "${dep_index_mode}" == "${expected_mode}" \
    && "${dep_index_oid}" == "${dep_oid}" && "${dep_index_stage}" == 0 \
    && "${dep_index_name}" == "${path}" ]] \
    || fail "dependency mode/type/index identity drift: ${path}"
  [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
    || fail "dependency nondefault index flag: ${path}"
  /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${dep_oid}") \
    || fail "dependency working/baseline bytes drift: ${path}"
  [[ "$(/usr/bin/sha256sum "${path}" | /usr/bin/awk '{print $1}')" == "${expected_hash}" ]] \
    || fail "dependency raw hash drift: ${path}"
done

for index in "${!packet_hash_paths[@]}"; do
  path="${packet_hash_paths[$index]}"
  expected_hash="${packet_hashes[$index]}"
  [[ "$(/usr/bin/sha256sum "${path}" | /usr/bin/awk '{print $1}')" == "${expected_hash}" ]] \
    || fail "packet raw hash drift: ${path}"
done

archive_paths=("${packet_paths[@]}" "${dependency_paths[@]}")
git_clean archive --format=tar "${source_commit}" -- "${archive_paths[@]}" \
  | /usr/bin/tar -x -C "${tmp}/archive"
[[ -z "$(/usr/bin/find "${tmp}/archive" -type l -print -quit)" ]] \
  || fail "protected archive contains symlink"
[[ -z "$(/usr/bin/find "${tmp}/archive" -type f -links +1 -print -quit)" ]] \
  || fail "protected archive contains hardlinked file"
for index in "${!dependency_paths[@]}"; do
  path="${dependency_paths[$index]}"
  [[ "$(/usr/bin/sha256sum "${tmp}/archive/${path}" | /usr/bin/awk '{print $1}')" \
    == "${dependency_hashes[$index]}" ]] || fail "archive dependency hash drift: ${path}"
done
for index in "${!packet_hash_paths[@]}"; do
  path="${packet_hash_paths[$index]}"
  [[ "$(/usr/bin/sha256sum "${tmp}/archive/${path}" | /usr/bin/awk '{print $1}')" \
    == "${packet_hashes[$index]}" ]] || fail "archive packet hash drift: ${path}"
done
check_private_scratch_limit

if ! /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -B -S -P - "${tmp}/archive/${manifest_path}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "rb") as stream:
    manifest = json.load(stream)

top_keys = {
    "schema", "schema_version", "date", "status", "decision",
    "source_baseline", "next_unit", "next_unit_authorized_by_this_pack",
    "state", "expected", "boundary", "dependency_topology", "raw_sha256",
    "dependency_artifact_raw_sha256", "packet_path_modes", "nonclaims",
}
assert set(manifest) == top_keys
assert manifest["schema"] == (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1_pack_manifest.v1"
)
assert manifest["schema_version"] == 1 and type(manifest["schema_version"]) is int
assert manifest["date"] == "2026-07-17"
assert manifest["status"] == (
    "FROZEN_IMPLEMENTATION_CANDIDATE_PENDING_EXACT_SOURCE_FAST_AND_ORDINARY_"
    "INTEGRATION_FULL_GATE"
)
assert manifest["decision"] == (
    "IMPLEMENT_EXACT_BOUNDED_PUBLIC_ONLY_SYNTHETIC_BOOTSTRAP_TRUST_"
    "AUTHENTICATION_VERIFIER_FAIL_CLOSED"
)
assert manifest["source_baseline"] == {
    "commit": "61585e655f7bfd537f8a123141e4e39a590a66d8",
    "tree": "9dcd1f700a7e4523307ef9704218b9f87a7fe5f1",
    "parents": [
        "2a0028eacc8fdd36463d4fa2f297f4d19807cd65",
        "4ce033e70781a5886d986939e879f6e3f7eadebd",
    ],
}
assert manifest["next_unit_authorized_by_this_pack"] is False
state = manifest["state"]
assert set(state.values()) <= {True, False}
assert state["fixture_generation_authority_single_use_consumed"] is True
assert state["implementation_authority_effective_at_source_baseline"] is True
assert state["implementation_authority_single_use_consumed_before_integrated_full_gate"] is False
assert state["implementation_authority_consumed_only_by_exact_integrated_full_gate"] is True
assert state["global_single_use_proved"] is False
expected = manifest["expected"]
assert expected["public_input_count"] == 4
assert expected["positive_track_count"] == 2
assert expected["signature_verification_count_per_success"] == 1
assert expected["strict_public_key_point_validation_count_per_success"] == 6
assert expected["strict_signature_r_point_validation_count_per_success"] == 1
assert expected["total_directed_negative_test_count"] == 116
assert expected["source_ast_guard_count"] == 15
assert expected["fixture_schema_guard_count"] == 23
assert expected["checker_stdout_line_count"] == 44
assert expected["checker_stdout_sha256"] == (
    "0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36"
)
boundary = manifest["boundary"]
assert boundary["local_t05_specification_exercised"] is True
assert boundary["local_t06_specification_exercised"] is False
assert boundary["local_t07_specification_exercised"] is False
assert boundary["production_ingestion_controls_implemented"] == 0
assert boundary["production_threat_specifications_runtime_exercised"] == 0
assert boundary["runtime_prerequisites_satisfied"] == 0
assert boundary["real_evidence_items_present"] == 0
assert boundary["provider_authority"] is False
assert boundary["runtime_authority"] is False
topology = manifest["dependency_topology"]
assert topology["direct_dependency_artifact_count"] == 23
assert topology["owned_packet_path_count"] == 8
assert topology["protected_archive_path_count"] == 31
assert len(manifest["raw_sha256"]) == 5
assert len(manifest["dependency_artifact_raw_sha256"]) == 23
assert len(manifest["packet_path_modes"]) == 8
assert set(manifest["packet_path_modes"].values()) == {"100644", "100755"}
assert manifest["packet_path_modes"][next(
    key for key in manifest["packet_path_modes"] if key.endswith(".sh")
)] == "100755"
assert all(value is False for value in manifest["nonclaims"].values())
PY
then
  fail "manifest closed-world semantic validation failed"
fi

for seed in 0 1 8675309; do
  env_args=(
    /usr/bin/env -i HOME="${tmp}/home" PATH=/usr/bin:/bin LC_ALL=C TZ=UTC
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
    PYTHONHASHSEED="${seed}" TMPDIR="${tmp}/home"
  )
  if ! "${env_args[@]}" /usr/bin/python3 -B -S -P \
    "${tmp}/archive/${checker_path}" \
    >"${tmp}/checker-${seed}.stdout" 2>"${tmp}/checker-${seed}.stderr"; then
    /usr/bin/cat "${tmp}/checker-${seed}.stderr" >&2
    fail "checker failed for hash seed ${seed}"
  fi
  [[ ! -s "${tmp}/checker-${seed}.stderr" ]] || fail "checker emitted stderr"
  /usr/bin/cmp -s "${tmp}/checker-${seed}.stdout" "${tmp}/archive/${expected_path}" \
    || fail "checker stdout differs from exact expected TSV for seed ${seed}"
  [[ "$(/usr/bin/wc -l <"${tmp}/checker-${seed}.stdout")" == "${checker_stdout_line_count}" ]] \
    || fail "checker stdout line-count drift"
  [[ "$(/usr/bin/sha256sum "${tmp}/checker-${seed}.stdout" | /usr/bin/awk '{print $1}')" \
    == "${checker_stdout_sha256}" ]] || fail "checker stdout hash drift"
done
/usr/bin/cmp -s "${tmp}/checker-0.stdout" "${tmp}/checker-1.stdout" \
  || fail "checker hash-seed drift"
/usr/bin/cmp -s "${tmp}/checker-0.stdout" "${tmp}/checker-8675309.stdout" \
  || fail "checker hash-seed drift"

if ! /usr/bin/env -i HOME="${tmp}/home" PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  PYTHONHASHSEED=314159 TMPDIR="${tmp}/home" \
  /usr/bin/python3 -B -S -P "${tmp}/archive/${checker_path}" --self-test \
  >"${tmp}/checker-self-test.stdout" 2>"${tmp}/checker-self-test.stderr"; then
  /usr/bin/cat "${tmp}/checker-self-test.stderr" >&2
  fail "checker self-test failed"
fi
[[ ! -s "${tmp}/checker-self-test.stderr" ]] || fail "checker self-test emitted stderr"
[[ "$(/usr/bin/wc -l <"${tmp}/checker-self-test.stdout")" == "${checker_self_test_line_count}" ]] \
  || fail "checker self-test line-count drift"
[[ "$(/usr/bin/sha256sum "${tmp}/checker-self-test.stdout" | /usr/bin/awk '{print $1}')" \
  == "${checker_self_test_stdout_sha256}" ]] || fail "checker self-test hash drift"
[[ -z "$(/usr/bin/find "${tmp}/archive" \( -name '*.pyc' -o -name __pycache__ \) -print -quit)" ]] \
  || fail "Python cache emitted"

[[ "$(/usr/bin/grep -Fxc -- '## Artifact binding' "${tmp}/archive/${report_path}")" == 1 ]] \
  || fail "report lacks exact-once Artifact binding heading"
for index in "${!packet_hash_paths[@]}"; do
  path="${packet_hash_paths[$index]}"
  digest="${packet_hashes[$index]}"
  if [[ "${path}" != "${report_path}" ]]; then
    [[ "$(/usr/bin/grep -Foc -- "${digest}" "${tmp}/archive/${report_path}")" == 1 ]] \
      || fail "report does not bind artifact hash exactly once: ${path}"
  fi
done

predecessor_repo="${tmp}/supply-replay"
if ! git_clean clone --no-local --no-hardlinks --no-checkout --no-tags --single-branch \
  -- . "${predecessor_repo}" >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone isolated supply replay repository"
fi
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" sparse-checkout init --cone \
  >"${tmp}/sparse-init.stdout" 2>"${tmp}/sparse-init.stderr" \
  || { /usr/bin/cat "${tmp}/sparse-init.stderr" >&2; fail "cannot initialize supply sparse checkout"; }
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" sparse-checkout set scripts docs/reports/goal-c-u docs/design/fixtures \
  >"${tmp}/sparse-set.stdout" 2>"${tmp}/sparse-set.stderr" \
  || { /usr/bin/cat "${tmp}/sparse-set.stderr" >&2; fail "cannot bind supply sparse paths"; }
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" checkout --detach "${supply_integration_commit}" \
  >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" \
  || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout supply integration"; }
[[ "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" rev-parse HEAD)" \
  == "${supply_integration_commit}" ]] || fail "isolated supply HEAD drift"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] || fail "isolated supply checkout dirty"
clone_common_dir="$(/usr/bin/git -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" rev-parse --path-format=absolute --git-common-dir)"
[[ -d "${clone_common_dir}" && ! -L "${clone_common_dir}" ]] \
  || fail "isolated supply common directory drift"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
  for-each-ref --format='%(refname)' refs/replace)" ]] || fail "isolated supply replace refs present"
[[ ! -e "${clone_common_dir}/info/grafts" && ! -L "${clone_common_dir}/info/grafts" ]] \
  || fail "isolated supply grafts present"
[[ ! -e "${clone_common_dir}/info/attributes" && ! -L "${clone_common_dir}/info/attributes" ]] \
  || fail "isolated supply info attributes present"
[[ ! -e "${clone_common_dir}/objects/info/alternates" \
  && ! -L "${clone_common_dir}/objects/info/alternates" ]] \
  || fail "isolated supply alternates present"
read -r cloned_gate_mode cloned_gate_oid cloned_gate_stage cloned_gate_name \
  < <(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
    ls-files --stage -- "${supply_gate}") \
  || fail "cannot resolve isolated supply gate identity"
[[ "${cloned_gate_mode}" == 100755 && "${cloned_gate_stage}" == 0 \
  && "${cloned_gate_name}" == "${supply_gate}" \
  && -f "${predecessor_repo}/${supply_gate}" && ! -L "${predecessor_repo}/${supply_gate}" \
  && -x "${predecessor_repo}/${supply_gate}" \
  && "$(/usr/bin/stat -c '%F' "${predecessor_repo}/${supply_gate}")" == "regular file" \
  && "$(/usr/bin/stat -c '%h' "${predecessor_repo}/${supply_gate}")" == 1 \
  && "$(/usr/bin/sha256sum "${predecessor_repo}/${supply_gate}" | /usr/bin/awk '{print $1}')" \
    == "${supply_gate_sha256}" ]] || fail "isolated supply gate mode/type/hash drift"
check_private_scratch_limit

upstream_line_count="${supply_fast_line_count}"
upstream_stdout_sha256="${supply_fast_stdout_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  upstream_line_count="${supply_full_line_count}"
  upstream_stdout_sha256="${supply_full_stdout_sha256}"
fi
if ! "${predecessor_repo}/${supply_gate}" "${validation_tier}" \
  >"${tmp}/supply.stdout" 2>"${tmp}/supply.stderr"; then
  /usr/bin/cat "${tmp}/supply.stderr" >&2
  fail "supply ${validation_tier} replay failed"
fi
[[ ! -s "${tmp}/supply.stderr" ]] || fail "supply replay emitted stderr"
[[ "$(/usr/bin/wc -l <"${tmp}/supply.stdout")" == "${upstream_line_count}" ]] \
  || fail "supply receipt line-count drift"
upstream_receipt_sha256="$(/usr/bin/sha256sum "${tmp}/supply.stdout" | /usr/bin/awk '{print $1}')"
[[ "${upstream_receipt_sha256}" == "${upstream_stdout_sha256}" ]] \
  || fail "supply receipt hash drift"
for field_value in \
  $'mode\tintegrated' \
  $'source_commit\t4ce033e70781a5886d986939e879f6e3f7eadebd' \
  $'head\t61585e655f7bfd537f8a123141e4e39a590a66d8' \
  $'fixture_generation_authority_single_use_consumed\ttrue' \
  $'underlying_implementation_authority_single_use_consumed\tfalse' \
  $'supply_pack_consumes_underlying_implementation_authority\tfalse' \
  $'gate_replay_authorizes_additional_generation_attempt\tfalse' \
  $'private_material_file_write_count\t0' \
  $'committed_private_material_count\t0' \
  $'network_provider_credential_attempt_count\t0'; do
  [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/supply.stdout")" == 1 ]] \
    || fail "supply receipt boundary drift: ${field_value}"
done
if [[ "${validation_tier}" == full-replay ]]; then
  for field_value in \
    $'gate\tPASS' \
    $'effective_supply_state\tCONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE' \
    $'underlying_implementation_authority_full_replay_verified\ttrue' \
    $'underlying_implementation_authority_effective\ttrue' \
    $'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY' \
    $'artifact_release_evidence\ttrue'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/supply.stdout")" == 1 ]] \
      || fail "supply full receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    "${tmp}/supply.stdout")" == 0 ]] || fail "supply full contains fast marker"
else
  for field_value in \
    $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    $'effective_supply_state\tFROZEN_PUBLIC_OUTPUT_PENDING_INTEGRATED_FULL_GATE' \
    $'underlying_implementation_authority_full_replay_verified\tfalse' \
    $'underlying_implementation_authority_effective\tfalse' \
    $'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY' \
    $'artifact_release_evidence\tfalse'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/supply.stdout")" == 1 ]] \
      || fail "supply fast receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tPASS' "${tmp}/supply.stdout")" == 0 ]] \
    || fail "supply fast contains release marker"
fi
[[ "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" rev-parse HEAD)" \
  == "${supply_integration_commit}" ]] || fail "supply replay HEAD moved"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] || fail "supply replay dirtied checkout"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD changed during gate"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "gate dirtied worktree or index"

checker_result="$(/usr/bin/cat "${tmp}/checker-0.stdout")"
/usr/bin/chmod -R u+w "${tmp}" || fail "cannot make scratch removable"
/usr/bin/rm -rf "${tmp}" || fail "cannot remove scratch"
if [[ "${tmp_base_created}" == true ]]; then /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true; fi
trap - EXIT

printf '%s\n' "${checker_result}"
if [[ "${validation_tier}" == full-replay ]]; then
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER_ISOLATED_LAB_V1_PACK\n'
  printf 'gate\tPASS\n'
  printf 'authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
  printf 'implementation_authority_single_use_consumed\ttrue\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
  printf 'authorization_consumption_state\tAUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT_PENDING_INTEGRATED_FULL_GATE\n'
  printf 'implementation_authority_single_use_consumed\tfalse\n'
fi
printf 'mode\t%s\n' "${mode}"
printf 'baseline_commit\t%s\n' "${baseline_commit}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'source_parent\t%s\n' "${baseline_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'head_tree\t%s\n' "$(git_clean show -s --format='%T' "${head_oid}")"
printf 'head_parents\t%s\n' "$(git_clean show -s --format='%P' "${head_oid}")"
printf 'packet_path_count\t8\n'
printf 'dependency_artifact_count\t23\n'
printf 'protected_archive_path_count\t31\n'
printf 'checker_stdout_sha256\t%s\n' "${checker_stdout_sha256}"
printf 'checker_stdout_line_count\t%s\n' "${checker_stdout_line_count}"
printf 'directed_mutation_count\t%s\n' "${directed_mutation_count}"
printf 'public_input_count\t4\n'
printf 'preobservation_mode_guard\ttrue\n'
printf 'track_count\t2\n'
printf 'predecessor_frame_review_count_per_success\t1\n'
printf 'structural_chain_entry_count_per_track\t3\n'
printf 'certificate_link_signature_verification_count\t0\n'
printf 'active_leaf_signature_verification_count_per_success\t1\n'
printf 'strict_public_key_point_validation_count_per_success\t6\n'
printf 'strict_signature_r_point_validation_count_per_success\t1\n'
printf 'local_t05_specification_exercised\ttrue\n'
printf 'local_t06_specification_exercised\tfalse\n'
printf 'local_t07_specification_exercised\tfalse\n'
printf 'declared_role_is_scope_authorization\tfalse\n'
printf 'track_subject_binding_implemented\tfalse\n'
printf 'minimum_independent_reviewer_lane_count\t2\n'
printf 'checker_is_production_security_approval\tfalse\n'
printf 'fixture_generation_authority_single_use_consumed\ttrue\n'
printf 'gate_replay_authorizes_additional_generation_attempt\tfalse\n'
printf 'implementation_authority_replay_authorizes_another_successor\tfalse\n'
printf 'global_single_use_proved\tfalse\n'
printf 'production_ingestion_controls_implemented\t0\n'
printf 'production_ingestion_controls_runtime_exercised\t0\n'
printf 'production_threat_specifications_runtime_exercised\t0\n'
printf 'runtime_prerequisites_satisfied\t0\n'
printf 'real_evidence_items_present\t0\n'
printf 'network_provider_credential_attempt_count\t0\n'
printf 'signing_or_key_generation_count\t0\n'
printf 'private_material_count\t0\n'
printf 'upstream_supply_receipt_sha256\t%s\n' "${upstream_receipt_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  printf 'upstream_implementation_authority_full_replay_verified\ttrue\n'
  printf 'upstream_implementation_authority_effective_before_consumption\ttrue\n'
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'full_replay_gate\tVALID_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER_AND_FULL_FROZEN_SUPPLY_AUTHORITY_FRAME_CHAIN\n'
else
  printf 'upstream_implementation_authority_full_replay_verified\tfalse\n'
  printf 'upstream_implementation_authority_effective_before_consumption\tfalse\n'
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'fast_gate\tVALID_FAST_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER_AND_SUPPLY_CHAIN_IDENTITY\n'
fi
