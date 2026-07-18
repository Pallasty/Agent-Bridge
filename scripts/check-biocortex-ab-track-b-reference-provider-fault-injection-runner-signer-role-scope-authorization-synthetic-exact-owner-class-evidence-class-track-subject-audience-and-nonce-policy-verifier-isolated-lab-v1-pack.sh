#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound gate for the public-only signer role/scope authorization
# synthetic exact-policy verifier isolated-lab v1 pack.
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
  printf 'Signer role/scope authorization verifier isolated-lab v1 gate failed: %s\n' "$*" >&2
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

baseline_commit="9edc70a870023ebc8e081f61100577345d3c2850"
baseline_tree="261d8d60677229614b18f2eb10f2530648f70505"
baseline_parents="400550236a643867086464e681be1fd5d12e579f 4a298c5f5a8dce6c7482b46fc6b416246fb55547"

authority_integration_commit="${baseline_commit}"
authority_integration_tree="${baseline_tree}"
authority_integration_parents="${baseline_parents}"
authority_integration_first_parent="400550236a643867086464e681be1fd5d12e579f"
authority_source_commit="4a298c5f5a8dce6c7482b46fc6b416246fb55547"
authority_source_parent="7df72e2d49bbc25580d4dcb63bc1a183120bba77"
authority_source_tree="9ec3826e65337cc71c3ba83dd43920bb16288427"
authority_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
authority_expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
authority_gate_sha256="6300618782a27d95e880cf7e7d1dba0ba7be6246ab95d3ab150e62c2f73c0b11"
authority_fast_line_count="157"
authority_fast_stdout_sha256="da8ba9b84cf0564861235b751f403b2c153f7d668162bdde2b683eaed22e4a41"
authority_full_line_count="158"
authority_full_stdout_sha256="f7ebac3d39eeba74d4c8d1cd908c195b8f95340e20e4ca0a126605384d0f01ee"

schema_path="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1.schema.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack.py"
fixture_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_synthetic_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1-pack.sh"

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
  "8c659f8bed05e665c0e663649ec892bb3c82ff17e6ad396c79093047af7de7ca"
  "438a0edbb9deb7d61c7bd8462b24d102123df0b6b7be46109bcf9d97ee8cade0"
  "cd845c7c4d565e816a0667ab2e4c70f8a19a563e612a564b83a0a357834c55a9"
  "cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9"
  "0ebe83cc49753b6dfce5a00fd1971f8ea3308c5d375221e4bd10b588444903ae"
  "f189dd457e7070b918eee8d44d2e94ce28ddf78f2d03e8b32b4226b3b59415e3"
  "b45f4c90c8fad48e02ca1567303705b3c41bf37a8d78e3f8eb18c49c7e3c3029"
)
checker_stdout_line_count="47"
checker_stdout_sha256="0ebe83cc49753b6dfce5a00fd1971f8ea3308c5d375221e4bd10b588444903ae"
checker_self_test_line_count="16"
checker_self_test_stdout_sha256="51309f5ed95d1821253b8b36a65542b4446cf75cd1e15807a5111d4d2830aa36"
directed_mutation_count="241"

# Frozen T05 direct dependency closure: supply pack 8 + original T05
# authority pack 7 + predecessor frame/mode implementation pack 8.
t05_transitive_paths=(
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
t05_transitive_modes=(
  100644 100755 100644 100644 100644 100644 100644 100644
  100644 100755 100644 100644 100644 100644 100644
  100644 100644 100755 100644 100644 100644 100644 100644
)
t05_transitive_hashes=(
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

authority_paths=(
  "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md"
  "${authority_gate}"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
  "${authority_expected}"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
)
authority_modes=(100644 100755 100644 100644 100644 100644 100644)
authority_hashes=(
  c92c8ab419ab1aa937b00b358bebb7e66ba6ac7d205de863d7cc32813b855d25
  6300618782a27d95e880cf7e7d1dba0ba7be6246ab95d3ab150e62c2f73c0b11
  3cd07ed34e3aa9a9b6933ccba69a2da1f20c302c5e7f510f13e539b326f16db5
  18cb9e5d8eb63c5bbc0d930035923504b9a3efb89df67dbbf5741aba3cbc10e7
  6da905a6d05660647ba92b9acf1d494fa277f66bc31b6d0afa07faef9e9e7d45
  ba9bf671ec4985c14089e6e68b0bda5a09c0b4b09df1582ba6b8305f5fee4ee6
  95185cd5a0f7f7fc1b49c1ac92c17cdd6b90dddcf3d00b9251e3ae7832bb8f82
)

t05_owned_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-v1.schema.json"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.sh"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_v0.json"
)
t05_owned_modes=(100644 100644 100755 100644 100644 100644 100644 100644)
t05_owned_hashes=(
  d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c
  9da0b11bfc86011ca792a6c0b2836c53c55837c17ac680296f5ad595b1a32ef0
  aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061
  f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341
  bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20
  0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36
  31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e
  bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b
)

t06_semantic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
t06_semantic_fixture_sha256="3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"

# Direct static closure is exactly current authority 7 + T05 owned 8 +
# T05's frozen direct closure 23 + the T06 semantic fixture 1.  Only the
# current authority gate is executed; all remaining dependencies are identity
# frozen to make the source archive import-complete.
dependency_paths=(
  "${authority_paths[@]}" "${t05_owned_paths[@]}"
  "${t05_transitive_paths[@]}" "${t06_semantic_fixture}"
)
dependency_modes=(
  "${authority_modes[@]}" "${t05_owned_modes[@]}"
  "${t05_transitive_modes[@]}" 100644
)
dependency_hashes=(
  "${authority_hashes[@]}" "${t05_owned_hashes[@]}"
  "${t05_transitive_hashes[@]}" "${t06_semantic_fixture_sha256}"
)

require_filled() {
  local value
  for value in "$@"; do
    [[ "${value}" != __FILL_* ]] || fail "unresolved frozen placeholder: ${value}"
  done
}
require_filled "${packet_hashes[@]}" "${checker_stdout_line_count}" \
  "${checker_stdout_sha256}" "${checker_self_test_line_count}" \
  "${checker_self_test_stdout_sha256}" "${directed_mutation_count}" \
  "${authority_fast_line_count}" "${authority_fast_stdout_sha256}" \
  "${authority_full_line_count}" "${authority_full_stdout_sha256}"

for digest in "${packet_hashes[@]}" "${checker_stdout_sha256}" \
  "${checker_self_test_stdout_sha256}" "${authority_fast_stdout_sha256}" \
  "${authority_full_stdout_sha256}" "${dependency_hashes[@]}"; do
  [[ "${digest}" =~ ^[0-9a-f]{64}$ ]] || fail "malformed frozen SHA-256: ${digest}"
done
for count in "${checker_stdout_line_count}" "${checker_self_test_line_count}" \
  "${directed_mutation_count}" "${authority_fast_line_count}" \
  "${authority_full_line_count}"; do
  [[ "${count}" =~ ^[1-9][0-9]*$ ]] || fail "malformed positive frozen count: ${count}"
done

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
for commit in "${baseline_commit}" "${authority_integration_first_parent}" \
  "${authority_source_commit}" "${authority_source_parent}"; do
  [[ "$(git_clean cat-file -t "${commit}")" == commit ]] \
    || fail "frozen commit unavailable: ${commit}"
done
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${baseline_tree}" ]] \
  || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${baseline_parents}" ]] \
  || fail "baseline parent topology drift"
[[ "${baseline_commit}" == "${authority_integration_commit}" \
  && "$(git_clean show -s --format='%T' "${authority_integration_commit}")" \
    == "${authority_integration_tree}" \
  && "$(git_clean show -s --format='%P' "${authority_integration_commit}")" \
    == "${authority_integration_parents}" ]] \
  || fail "authority integration identity drift"
[[ "$(git_clean show -s --format='%T' "${authority_source_commit}")" \
    == "${authority_source_tree}" \
  && "$(git_clean show -s --format='%P' "${authority_source_commit}")" \
    == "${authority_source_parent}" ]] || fail "authority source topology drift"

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
tmp="$(/usr/bin/mktemp -d "${tmp_base}/signer-role-scope-verifier-v1.XXXXXX")"
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
[[ "${#authority_paths[@]}" == 7 && "${#t05_owned_paths[@]}" == 8 \
  && "${#t05_transitive_paths[@]}" == 23 ]] \
  || fail "dependency partition cardinality drift"
[[ "${#dependency_paths[@]}" == 39 && "${#dependency_modes[@]}" == 39 \
  && "${#dependency_hashes[@]}" == 39 ]] \
  || fail "direct dependency catalog drift"
printf '%s\n' "${packet_paths[@]}" "${dependency_paths[@]}" \
  | /usr/bin/sort >"${tmp}/protected-paths"
[[ "$(/usr/bin/wc -l <"${tmp}/protected-paths")" == 47 \
  && "$(/usr/bin/sort -u "${tmp}/protected-paths" | /usr/bin/wc -l)" == 47 ]] \
  || fail "protected archive path cardinality or uniqueness drift"

printf '%s\n' "${authority_paths[@]}" | /usr/bin/sort \
  | /usr/bin/awk '{print "A\t" $0}' >"${tmp}/expected-authority-delta"
git_clean diff-tree --no-commit-id --name-status -r \
  "${authority_source_parent}" "${authority_source_commit}" | /usr/bin/sort \
  >"${tmp}/authority-source-delta"
/usr/bin/cmp -s "${tmp}/expected-authority-delta" \
  "${tmp}/authority-source-delta" \
  || fail "authority source is not exact seven-path all-add"
git_clean diff-tree --no-commit-id --name-status -r \
  "${authority_integration_first_parent}" "${authority_integration_commit}" \
  | /usr/bin/sort >"${tmp}/authority-integration-delta"
/usr/bin/cmp -s "${tmp}/expected-authority-delta" \
  "${tmp}/authority-integration-delta" \
  || fail "authority integration first-parent delta drift"

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
  /usr/bin/python3 -B -S -P - "${tmp}/archive/${manifest_path}" \
    "${authority_fast_line_count}" "${authority_fast_stdout_sha256}" \
    "${authority_full_line_count}" "${authority_full_stdout_sha256}" \
    "${checker_stdout_line_count}" "${checker_stdout_sha256}" \
    "${checker_self_test_line_count}" "${checker_self_test_stdout_sha256}" \
    "${directed_mutation_count}" <<'PY'
import json
import sys

path = sys.argv[1]
authority_fast_lines = int(sys.argv[2])
authority_fast_sha256 = sys.argv[3]
authority_full_lines = int(sys.argv[4])
authority_full_sha256 = sys.argv[5]
checker_lines = int(sys.argv[6])
checker_sha256 = sys.argv[7]
self_test_lines = int(sys.argv[8])
self_test_sha256 = sys.argv[9]
directed_mutations = int(sys.argv[10])
with open(path, "rb") as stream:
    manifest = json.load(stream)

top_keys = {
    "schema", "schema_version", "date", "status", "decision",
    "source_baseline", "authorized_unit", "next_unit",
    "next_unit_authorized_by_this_pack", "authority", "state", "expected",
    "boundary", "resource_limits", "dependency_topology", "raw_sha256",
    "dependency_artifact_raw_sha256", "dependency_artifact_modes",
    "packet_path_modes", "nonclaims",
}
assert type(manifest) is dict
assert set(manifest) == top_keys
assert manifest["schema_version"] == 1 and type(manifest["schema_version"]) is int
assert manifest["date"] == "2026-07-18"
assert manifest["source_baseline"] == {
    "commit": "9edc70a870023ebc8e081f61100577345d3c2850",
    "tree": "261d8d60677229614b18f2eb10f2530648f70505",
    "parents": [
        "400550236a643867086464e681be1fd5d12e579f",
        "4a298c5f5a8dce6c7482b46fc6b416246fb55547",
    ],
}
authority = manifest["authority"]
assert authority["decision_source_commit"] == (
    "4a298c5f5a8dce6c7482b46fc6b416246fb55547"
)
assert authority["decision_integration_commit"] == (
    "9edc70a870023ebc8e081f61100577345d3c2850"
)
assert authority["decision_gate_raw_sha256"] == (
    "6300618782a27d95e880cf7e7d1dba0ba7be6246ab95d3ab150e62c2f73c0b11"
)
assert authority["decision_fast_stdout_line_count"] == authority_fast_lines
assert authority["decision_fast_stdout_sha256"] == authority_fast_sha256
assert authority["decision_full_stdout_line_count"] == authority_full_lines
assert authority["decision_full_stdout_sha256"] == authority_full_sha256
assert authority["implementation_authority_single_use_consumed_at_source_baseline"] is False
assert authority["decision_full_gate_consumes_new_authority"] is False
state = manifest["state"]
assert type(state) is dict
assert state["implementation_authority_single_use_consumed_before_integrated_full_gate"] is False
assert state["implementation_authority_consumed_only_by_exact_integrated_full_gate"] is True
assert state["global_single_use_proved"] is False
expected = manifest["expected"]
assert type(expected) is dict
assert expected["public_input_count"] == 6
assert expected["positive_track_count"] == 2
assert expected["authorization_grant_count"] == 2
assert expected["request_scope_dimension_count"] == 6
assert expected["total_directed_negative_test_count"] == directed_mutations
assert expected["checker_stdout_line_count"] == checker_lines
assert expected["checker_stdout_sha256"] == checker_sha256
assert expected["checker_self_test_stdout_line_count"] == self_test_lines
assert expected["checker_self_test_stdout_sha256"] == self_test_sha256
boundary = manifest["boundary"]
assert type(boundary) is dict
assert boundary["isolated_lab_candidate_surface_component_total"] == 4
assert boundary["isolated_lab_candidate_surface_components_implemented_after_integrated_full_gate"] == 4
assert boundary["local_threat_specifications_covered_after_integrated_full_gate"] == [
    "T01", "T02", "T03", "T04", "T05", "T06",
]
assert boundary["local_t06_specification_exercised_after_integrated_full_gate"] is True
assert boundary["local_t07_specification_exercised"] is False
assert boundary["local_t08_specification_exercised"] is False
assert boundary["local_t09_specification_exercised"] is False
assert boundary["production_signer_role_scope_authorization_implemented"] is False
assert boundary["production_ingestion_controls_implemented"] == 0
assert boundary["production_ingestion_controls_runtime_exercised"] == 0
assert boundary["production_threat_specifications_runtime_exercised"] == 0
assert boundary["runtime_prerequisites_satisfied"] == 0
assert boundary["real_evidence_items_present"] == 0
assert boundary["provider_authority"] is False
assert boundary["runtime_authority"] is False
topology = manifest["dependency_topology"]
assert topology["t06_authority_decision_pack_artifact_count"] == 7
assert topology["t05_owned_pack_artifact_count"] == 8
assert topology["t05_frozen_direct_dependency_artifact_count"] == 23
assert topology["t06_semantic_specification_artifact_count"] == 1
assert topology["direct_dependency_artifact_count"] == 39
assert topology["owned_packet_path_count"] == 8
assert topology["protected_archive_path_count"] == 47
assert topology["only_current_t06_authority_gate_executed"] is True
assert topology["t05_gate_not_separately_executed"] is True
assert manifest["raw_sha256"] == {
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1.schema.json":
        "8c659f8bed05e665c0e663649ec892bb3c82ff17e6ad396c79093047af7de7ca",
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1.py":
        "438a0edbb9deb7d61c7bd8462b24d102123df0b6b7be46109bcf9d97ee8cade0",
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack.py":
        "cd845c7c4d565e816a0667ab2e4c70f8a19a563e612a564b83a0a357834c55a9",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_synthetic_v0.json":
        "cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack.expected.v0.tsv":
        "0ebe83cc49753b6dfce5a00fd1971f8ea3308c5d375221e4bd10b588444903ae",
}
assert len(manifest["dependency_artifact_raw_sha256"]) == 39
assert len(manifest["dependency_artifact_modes"]) == 39
assert len(manifest["packet_path_modes"]) == 8
assert list(manifest["packet_path_modes"].values()).count("100755") == 1
assert manifest["packet_path_modes"][
    next(key for key in manifest["packet_path_modes"] if key.endswith(".sh"))
] == "100755"
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

authority_repo="${tmp}/authority-replay"
if ! git_clean clone --no-local --no-hardlinks --no-checkout --no-tags --single-branch \
  -- . "${authority_repo}" >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone isolated authority replay repository"
fi
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${authority_repo}" \
  -C "${authority_repo}" sparse-checkout init --cone \
  >"${tmp}/sparse-init.stdout" 2>"${tmp}/sparse-init.stderr" \
  || { /usr/bin/cat "${tmp}/sparse-init.stderr" >&2; fail "cannot initialize authority sparse checkout"; }
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${authority_repo}" \
  -C "${authority_repo}" sparse-checkout set scripts docs/reports/goal-c-u docs/design/fixtures \
  >"${tmp}/sparse-set.stdout" 2>"${tmp}/sparse-set.stderr" \
  || { /usr/bin/cat "${tmp}/sparse-set.stderr" >&2; fail "cannot bind authority sparse paths"; }
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${authority_repo}" \
  -C "${authority_repo}" checkout --detach "${authority_integration_commit}" \
  >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" \
  || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout authority integration"; }
[[ "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" rev-parse HEAD)" \
  == "${authority_integration_commit}" ]] || fail "isolated authority HEAD drift"
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] || fail "isolated authority checkout dirty"
clone_common_dir="$(/usr/bin/git -c safe.directory="${authority_repo}" \
  -C "${authority_repo}" rev-parse --path-format=absolute --git-common-dir)"
[[ -d "${clone_common_dir}" && ! -L "${clone_common_dir}" ]] \
  || fail "isolated authority common directory drift"
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" \
  for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "isolated authority replace refs present"
[[ ! -e "${clone_common_dir}/info/grafts" && ! -L "${clone_common_dir}/info/grafts" ]] \
  || fail "isolated authority grafts present"
[[ ! -e "${clone_common_dir}/info/attributes" \
  && ! -L "${clone_common_dir}/info/attributes" ]] \
  || fail "isolated authority info attributes present"
[[ ! -e "${clone_common_dir}/objects/info/alternates" \
  && ! -L "${clone_common_dir}/objects/info/alternates" ]] \
  || fail "isolated authority alternates present"
read -r cloned_gate_mode cloned_gate_oid cloned_gate_stage cloned_gate_name \
  < <(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" \
    ls-files --stage -- "${authority_gate}") \
  || fail "cannot resolve isolated authority gate identity"
[[ "${cloned_gate_mode}" == 100755 && "${cloned_gate_stage}" == 0 \
  && "${cloned_gate_name}" == "${authority_gate}" \
  && -f "${authority_repo}/${authority_gate}" \
  && ! -L "${authority_repo}/${authority_gate}" \
  && -x "${authority_repo}/${authority_gate}" \
  && "$(/usr/bin/stat -c '%F' "${authority_repo}/${authority_gate}")" == "regular file" \
  && "$(/usr/bin/stat -c '%h' "${authority_repo}/${authority_gate}")" == 1 \
  && "$(/usr/bin/sha256sum "${authority_repo}/${authority_gate}" | /usr/bin/awk '{print $1}')" \
    == "${authority_gate_sha256}" ]] || fail "isolated authority gate mode/type/hash drift"
check_private_scratch_limit

authority_replay_tier="${validation_tier}"
authority_line_count="${authority_fast_line_count}"
authority_stdout_sha256="${authority_fast_stdout_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  authority_line_count="${authority_full_line_count}"
  authority_stdout_sha256="${authority_full_stdout_sha256}"
fi

# Exactly one serial authority invocation.  The authority gate owns all deeper
# T05 replay; this gate neither calls T05 separately nor duplicates authority.
if ! "${authority_repo}/${authority_gate}" "${authority_replay_tier}" \
  >"${tmp}/authority.stdout" 2>"${tmp}/authority.stderr"; then
  /usr/bin/cat "${tmp}/authority.stderr" >&2
  fail "authority ${authority_replay_tier} replay failed"
fi
[[ ! -s "${tmp}/authority.stderr" ]] || fail "authority replay emitted stderr"
[[ "$(/usr/bin/wc -l <"${tmp}/authority.stdout")" == "${authority_line_count}" ]] \
  || fail "authority receipt line-count drift"
authority_receipt_sha256="$(
  /usr/bin/sha256sum "${tmp}/authority.stdout" | /usr/bin/awk '{print $1}'
)"
[[ "${authority_receipt_sha256}" == "${authority_stdout_sha256}" ]] \
  || fail "authority receipt hash drift"

[[ "$(/usr/bin/wc -l <"${authority_repo}/${authority_expected}")" == 79 ]] \
  || fail "authority expected TSV line-count drift"
/usr/bin/awk 'NR <= 79 {print}' "${tmp}/authority.stdout" \
  >"${tmp}/authority-prefix.tsv"
/usr/bin/cmp -s "${authority_repo}/${authority_expected}" \
  "${tmp}/authority-prefix.tsv" || fail "authority expected TSV prefix drift"

for field_value in \
  $'mode\tintegrated' \
  $'source_commit\t4a298c5f5a8dce6c7482b46fc6b416246fb55547' \
  $'head\t9edc70a870023ebc8e081f61100577345d3c2850' \
  $'decision_scope\tSIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT_SINGLE_USE_NON_TRANSITIVE' \
  $'implementation_authority_non_transitive\ttrue' \
  $'implementation_authority_subdelegation_authorized\tfalse' \
  $'decision_full_gate_consumes_new_authority\tfalse' \
  $'global_single_use_proved\tfalse' \
  $'production_environment_implementation_authorized\tfalse' \
  $'production_ingestion_controls_implemented\t0' \
  $'production_ingestion_controls_runtime_exercised\t0' \
  $'runtime_prerequisites_satisfied\t0' \
  $'real_evidence_items_present\t0' \
  $'runtime_authority\tfalse' \
  $'provider_authority\tfalse' \
  $'provider_endpoint_count\t0' \
  $'credential_handle_count\t0' \
  $'credential_path_count\t0'; do
  [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/authority.stdout")" -ge 1 ]] \
    || fail "authority common boundary drift: ${field_value}"
done
[[ "$(/usr/bin/grep -Fxc -- $'implementation_authority_single_use_consumed\tfalse' \
  "${tmp}/authority.stdout")" == 2 ]] \
  || fail "authority decision must remain unconsumed"

authority_full_replay_verified=false
authority_effective_before_consumption=false
if [[ "${validation_tier}" == full-replay ]]; then
  authority_full_replay_verified=true
  authority_effective_before_consumption=true
  for field_value in \
    $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RUNNER_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION_V1_PACK' \
    $'gate\tPASS' \
    $'effective_authorization_state\tAUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT' \
    $'signer_role_scope_authorization_implementation_authority_effective\ttrue' \
    $'effective_implementation_authority_recorded\ttrue' \
    $'effective_implementation_side_effects_unlocked\tREVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY' \
    $'predecessor_authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE' \
    $'predecessor_authorization_consumption_verified\ttrue' \
    $'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY' \
    $'artifact_release_evidence\ttrue'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/authority.stdout")" -ge 1 ]] \
      || fail "authority full receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    "${tmp}/authority.stdout")" == 0 ]] || fail "authority full contains fast marker"
else
  for field_value in \
    $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    $'effective_authorization_state\tUNRECORDED_NO_AUTHORITY_PENDING_DECISION_INTEGRATED_FULL_GATE' \
    $'signer_role_scope_authorization_implementation_authority_effective\tfalse' \
    $'effective_implementation_authority_recorded\tfalse' \
    $'effective_implementation_side_effects_unlocked\tNONE' \
    $'predecessor_authorization_consumption_state\tREQUIRES_INTEGRATED_FULL_REPLAY_VERIFICATION' \
    $'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY' \
    $'artifact_release_evidence\tfalse'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/authority.stdout")" -ge 1 ]] \
      || fail "authority fast receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tPASS' "${tmp}/authority.stdout")" == 0 ]] \
    || fail "authority fast contains release marker"
fi
[[ "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" rev-parse HEAD)" \
  == "${authority_integration_commit}" ]] || fail "authority replay HEAD moved"
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "authority replay dirtied checkout"
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
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_POLICY_VERIFIER_ISOLATED_LAB_V1_PACK\n'
  printf 'gate\tPASS\n'
  printf 'authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
  printf 'implementation_authority_single_use_consumed\ttrue\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
  printf 'authorization_consumption_state\tUNRECORDED_NO_AUTHORITY_REQUIRES_AUTHORITY_AND_SUCCESSOR_INTEGRATED_FULL_REPLAY\n'
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
printf 'current_authority_owned_artifact_count\t7\n'
printf 't05_owned_artifact_count\t8\n'
printf 't05_frozen_direct_dependency_artifact_count\t23\n'
printf 't06_semantic_fixture_artifact_count\t1\n'
printf 'dependency_artifact_count\t39\n'
printf 'protected_archive_path_count\t47\n'
printf 'checker_stdout_sha256\t%s\n' "${checker_stdout_sha256}"
printf 'checker_stdout_line_count\t%s\n' "${checker_stdout_line_count}"
printf 'checker_self_test_stdout_sha256\t%s\n' "${checker_self_test_stdout_sha256}"
printf 'checker_self_test_line_count\t%s\n' "${checker_self_test_line_count}"
printf 'directed_mutation_count\t%s\n' "${directed_mutation_count}"
printf 'public_input_count\t6\n'
printf 'authorization_profile_count\t2\n'
printf 'positive_track_count\t2\n'
printf 'request_scope_dimension_count\t6\n'
printf 'matching_profile\tEXACT_ALL_FIELDS_ASCII_BYTE_EQUAL\n'
printf 'default_effect\tDENY\n'
printf 'deny_on_zero_matches\ttrue\n'
printf 'deny_on_multiple_matches\ttrue\n'
printf 'wildcard_prefix_hierarchy_or_inheritance_authorization_implemented\tfalse\n'
printf 't05_predecessor_review_count_per_success\t1\n'
printf 't05_predecessor_receipt_is_sole_signer_identity_source\ttrue\n'
printf 'caller_supplied_predecessor_receipt_accepted\tfalse\n'
printf 'isolated_lab_candidate_surface_component_total\t4\n'
printf 'candidate_component_conformance\ttrue\n'
printf 'candidate_surface_components_locally_kat_exercised\t4\n'
printf 'candidate_local_threat_specifications_kat_covered\t6\n'
printf 'local_t05_specification_exercised\ttrue\n'
printf 'local_t07_specification_exercised\tfalse\n'
printf 'local_t08_specification_exercised\tfalse\n'
printf 'local_t09_specification_exercised\tfalse\n'
printf 'production_signer_role_scope_authorization_implemented\tfalse\n'
printf 'declared_role_is_scope_authorization\tfalse\n'
printf 'owner_class_is_authenticated_owner_identity\tfalse\n'
printf 'audience_identity_authenticated\tfalse\n'
printf 'track_is_provider_profile_currentness\tfalse\n'
printf 'track_subject_binding_implemented\tfalse\n'
printf 'scope_label_truth_proved\tfalse\n'
printf 'subject_label_truth_proved\tfalse\n'
printf 'nonce_fixed_public_kat_equality_only\ttrue\n'
printf 'nonce_freshness_proved\tfalse\n'
printf 'nonce_replay_protection_proved\tfalse\n'
printf 'nonce_single_use_proved\tfalse\n'
printf 'minimum_independent_reviewer_lane_count\t2\n'
printf 'checker_is_production_security_approval\tfalse\n'
printf 'current_authority_gate_invocation_count\t1\n'
printf 'separate_t05_gate_invocation_count\t0\n'
printf 'authority_gate_owns_deeper_t05_replay\ttrue\n'
printf 'authority_replay_tier\t%s\n' "${authority_replay_tier}"
printf 'authority_receipt_sha256\t%s\n' "${authority_receipt_sha256}"
printf 'authority_decision_full_gate_consumes_new_authority\tfalse\n'
printf 'authority_replay_authorizes_another_successor\tfalse\n'
printf 'global_single_use_proved\tfalse\n'
printf 'production_ingestion_control_count\t14\n'
printf 'production_ingestion_controls_implemented\t0\n'
printf 'production_ingestion_controls_runtime_exercised\t0\n'
printf 'production_threat_specification_count\t20\n'
printf 'production_threat_specifications_runtime_exercised\t0\n'
printf 'runtime_prerequisite_count\t16\n'
printf 'runtime_prerequisites_satisfied\t0\n'
printf 'real_evidence_items_present\t0\n'
printf 'production_validated_evidence_items\t0\n'
printf 'evidence_acceptance_authorized\tfalse\n'
printf 'condition_output_authorized\tfalse\n'
printf 'output_or_claim_authorized\tfalse\n'
printf 'fault_injection_authorized\tfalse\n'
printf 'network_provider_credential_attempt_count\t0\n'
printf 'signing_or_key_generation_count\t0\n'
printf 'private_material_count\t0\n'
printf 'runtime_authority\tfalse\n'
printf 'provider_authority\tfalse\n'
printf 'downstream_gate_count\t4\n'
printf 'downstream_gates_authorized\t0\n'
printf 'side_effects_unlocked\tNONE\n'
if [[ "${validation_tier}" == full-replay ]]; then
  printf 'upstream_effective_authorization_state\tAUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT\n'
  printf 'release_bound_signer_role_scope_authorization_isolated_lab_component_implemented\ttrue\n'
  printf 'local_t06_specification_exercised\ttrue\n'
  printf 'released_isolated_lab_surface_components_implemented\t4\n'
  printf 'released_local_threat_specifications_covered\t6\n'
  printf 'authority_fast_replay_verified\tfalse\n'
  printf 'authority_full_replay_verified\ttrue\n'
  printf 'authority_effective_before_consumption\ttrue\n'
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'full_replay_gate\tVALID_SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_POLICY_VERIFIER_AND_FULL_FROZEN_AUTHORITY_T05_IMPORT_CLOSURE\n'
else
  printf 'upstream_effective_authorization_state\tUNRECORDED_NO_AUTHORITY_PENDING_DECISION_INTEGRATED_FULL_GATE\n'
  printf 'release_bound_signer_role_scope_authorization_isolated_lab_component_implemented\tfalse\n'
  printf 'local_t06_specification_exercised\tfalse\n'
  printf 'released_isolated_lab_predecessor_surface_components_implemented\t3\n'
  printf 'released_local_predecessor_threat_specifications_covered\t5\n'
  printf 'authority_fast_replay_verified\ttrue\n'
  printf 'authority_full_replay_verified\tfalse\n'
  printf 'authority_effective_before_consumption\tfalse\n'
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_AUTHORITY_FAST_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'fast_gate\tVALID_FAST_SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_POLICY_VERIFIER_AND_AUTHORITY_CHAIN_IDENTITY\n'
fi
