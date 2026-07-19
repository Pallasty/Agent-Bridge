#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound gate for the public-only T07 synthetic exact track-profile
# binding verifier isolated-lab v1 pack.
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
  printf 'T07 track-profile binding verifier isolated-lab v1 gate failed: %s\n' "$*" >&2
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
  /usr/bin/tar
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || fail "missing tool ${tool}"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not a canonical directory"

# The exact released T07 authority integration is the sole admissible source
# parent.  A later release remains an ordinary two-parent merge.
baseline_commit="084eb71dd9c95fbc6285041b1503327705f9a6a1"
baseline_tree="bc577acfb1e7614daf2008a1758379bb09c9f357"
baseline_parents="5f509375248aae43b7524effd30f023c86d83087 f39307d093a91f3d2734488ca5db31c9e4e50df3"

authority_integration_commit="${baseline_commit}"
authority_integration_tree="${baseline_tree}"
authority_integration_parents="${baseline_parents}"
authority_integration_first_parent="5f509375248aae43b7524effd30f023c86d83087"
authority_source_commit="f39307d093a91f3d2734488ca5db31c9e4e50df3"
authority_source_parent="1f44c69d31ae29d0cd6c90e84294b3ad0407d9a0"
authority_source_tree="cf0b248724642fdd35a44221418587d3772485cc"
authority_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-track-profile-binding-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
authority_expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
authority_gate_sha256="63ccb6cb7ab5f8c31fa3be1d1c64192002694b59246ee3390aed9f5172d73dc0"
authority_fast_line_count="144"
authority_fast_stdout_sha256="a08ed2dd908df85d8cdd7f503c519772293566c4f1a49670eade320d2bee679e"
authority_full_line_count="145"
authority_full_stdout_sha256="8a873b53a205027b14412507d4d65e5ccb181275eab5a6afb8760af130408ab8"
authority_expected_line_count="79"

schema_path="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-track-profile-binding-synthetic-exact-packet-profile-provider-or-lab-profile-namespace-configuration-sha256-and-non-substitutable-track-verifier-isolated-lab-v1.schema.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1_pack.py"
fixture_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1_pack_synthetic_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-track-profile-binding-synthetic-exact-packet-profile-provider-or-lab-profile-namespace-configuration-sha256-and-non-substitutable-track-verifier-isolated-lab-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-track-profile-binding-synthetic-exact-packet-profile-provider-or-lab-profile-namespace-configuration-sha256-and-non-substitutable-track-verifier-isolated-lab-v1-pack.sh"

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
  "7cdbb084c193e5936cd66237504f40cd3d050a3b5f814c0e8e92992a68ac9634"
  "777bfaa0c18569e68af1cf7c6e5957f1712079bfcfe4e2085e607dba5c9fcb23"
  "27c25f6c75504925859d693d09c391a6f60ec2c34aab84dda26bd610d4b94e91"
  "97a45faa1a2e4d1198c5ea5222ada4d31e46093c8956ecb319a2912e46b5b4e4"
  "bb1bb0f215cf8e272335dbec1d6c7ac2958dd52985a090a9e9fbf2abaf72585a"
  "75bcb6f0a47395b0aa5969f8071701a5ef8d777e902c255299d069413278b7e5"
  "31398214bd12861b8ae614e1a255dcd58325186d74602b6f8ef92e4f802be128"
)
checker_stdout_line_count="48"
checker_stdout_sha256="bb1bb0f215cf8e272335dbec1d6c7ac2958dd52985a090a9e9fbf2abaf72585a"
checker_self_test_line_count="16"
checker_self_test_stdout_sha256="636e47eb4cce7ef2b8588f9da7b8d636140b5dab912d227709caf28cd6da80fc"
directed_mutation_count="141"

# Current T07 authority decision pack, frozen at the exact released baseline.
authority_paths=(
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
  "${authority_expected}"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-track-profile-binding-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md"
  "${authority_gate}"
)
authority_modes=(100644 100644 100644 100644 100644 100644 100755)
authority_hashes=(
  fbd7fe686d38cad7db0e16622d969257257e92047907a7b50ca550996d262101
  243649c047facf5a577af1baec5c989c312d90a63af18ad47023819961925225
  064b9215a94ab3f649898ef924e755354578ec5c51c0dc50b978a84fa914a6ce
  a95f4ee21ffdfb3d6bb55dd076ea2bd61121e94a70b938bedfaaa93d829c06fe
  6d983ba964e28899f9f339427fe79c92f6d6f50ba9c4dca1f4e2f049d24b2c45
  05612b69906f6599b13ac6c2feab8ce6d49a2baf6e0e97aff84c24c5d320dc1a
  63ccb6cb7ab5f8c31fa3be1d1c64192002694b59246ee3390aed9f5172d73dc0
)

# T06 owned implementation pack.  Its manifest is the frozen source of truth
# for the 39-path import-complete direct closure below.
t06_manifest="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_v0.json"
t06_manifest_sha256="f189dd457e7070b918eee8d44d2e94ce28ddf78f2d03e8b32b4226b3b59415e3"
t06_owned_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1.schema.json"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack.expected.v0.tsv"
  "${t06_manifest}"
  "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1-pack.sh"
)
t06_owned_modes=(100644 100644 100644 100644 100644 100644 100644 100755)
t06_owned_hashes=(
  8c659f8bed05e665c0e663649ec892bb3c82ff17e6ad396c79093047af7de7ca
  438a0edbb9deb7d61c7bd8462b24d102123df0b6b7be46109bcf9d97ee8cade0
  cd845c7c4d565e816a0667ab2e4c70f8a19a563e612a564b83a0a357834c55a9
  cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9
  0ebe83cc49753b6dfce5a00fd1971f8ea3308c5d375221e4bd10b588444903ae
  f189dd457e7070b918eee8d44d2e94ce28ddf78f2d03e8b32b4226b3b59415e3
  b45f4c90c8fad48e02ca1567303705b3c41bf37a8d78e3f8eb18c49c7e3c3029
  db3ce063668144dc91fbb52ed4bebeb8c4937630789aaa6c3a69400332233444
)

require_filled() {
  local value
  for value in "$@"; do
    [[ "${value}" != __FILL_*__ ]] || fail "unresolved frozen placeholder: ${value}"
  done
}
require_filled "${packet_hashes[@]}" \
  "${checker_stdout_line_count}" "${checker_stdout_sha256}" \
  "${checker_self_test_line_count}" "${checker_self_test_stdout_sha256}" \
  "${directed_mutation_count}"

for digest in "${packet_hashes[@]}" "${checker_stdout_sha256}" \
  "${checker_self_test_stdout_sha256}" "${authority_fast_stdout_sha256}" \
  "${authority_full_stdout_sha256}" "${authority_hashes[@]}" \
  "${t06_owned_hashes[@]}"; do
  [[ "${digest}" =~ ^[0-9a-f]{64}$ ]] || fail "malformed frozen SHA-256: ${digest}"
done
for count in "${checker_stdout_line_count}" "${checker_self_test_line_count}" \
  "${directed_mutation_count}" "${authority_fast_line_count}" \
  "${authority_full_line_count}"; do
  [[ "${count}" =~ ^[1-9][0-9]*$ ]] || fail "malformed positive count: ${count}"
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
tmp="$(/usr/bin/mktemp -d "${tmp_base}/track-profile-binding-verifier-v1.XXXXXX")"
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
    || fail "private scratch checkpoint exceeds ${max_private_scratch_bytes} bytes"
}

reject_symlink_components() {
  local path="$1" component cursor=""
  local -a components
  IFS=/ read -r -a components <<<"${path}"
  for component in "${components[@]}"; do
    if [[ -n "${cursor}" ]]; then cursor="${cursor}/${component}"; else cursor="${component}"; fi
    [[ ! -L "${cursor}" ]] || fail "protected path contains symlink component: ${path}"
  done
}

# The T06 manifest is itself raw-hash frozen.  Parse its exact 39-entry direct
# dependency maps instead of maintaining a second hand-copied catalog.
reject_symlink_components "${t06_manifest}"
[[ -f "${t06_manifest}" && ! -L "${t06_manifest}" \
  && "$(/usr/bin/stat -c '%F' "${t06_manifest}")" == "regular file" \
  && "$(/usr/bin/stat -c '%h' "${t06_manifest}")" == 1 ]] \
  || fail "T06 manifest path type or link-count drift"
[[ "$(/usr/bin/sha256sum "${t06_manifest}" | /usr/bin/awk '{print $1}')" \
  == "${t06_manifest_sha256}" ]] || fail "T06 manifest raw hash drift"
if ! /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -B -S -P - "${t06_manifest}" >"${tmp}/t06-direct.tsv" <<'PY'
import json
import re
import sys

def reject_duplicate(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    manifest = json.load(
        handle,
        object_pairs_hook=reject_duplicate,
        parse_float=lambda _value: (_ for _ in ()).throw(ValueError("float forbidden")),
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant forbidden")),
    )
hashes = manifest["dependency_artifact_raw_sha256"]
modes = manifest["dependency_artifact_modes"]
topology = manifest["dependency_topology"]
assert type(hashes) is dict and type(modes) is dict
assert set(hashes) == set(modes) and len(hashes) == 39
assert topology["direct_dependency_artifact_count"] == 39
assert topology["protected_archive_path_count"] == 47
assert topology["only_current_t06_authority_gate_executed"] is True
assert topology["t05_gate_not_separately_executed"] is True
for path in sorted(hashes):
    digest = hashes[path]
    mode = modes[path]
    assert re.fullmatch(r"[A-Za-z0-9._/-]+", path)
    assert ".." not in path.split("/") and not path.startswith("/")
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert mode in {"100644", "100755"}
    print(f"{path}\t{mode}\t{digest}")
PY
then
  fail "cannot derive frozen T06 direct dependency catalog"
fi

t06_direct_paths=()
t06_direct_modes=()
t06_direct_hashes=()
while IFS=$'\t' read -r path mode digest; do
  [[ -n "${path}" && -n "${mode}" && -n "${digest}" ]] \
    || fail "malformed T06 direct dependency row"
  t06_direct_paths+=("${path}")
  t06_direct_modes+=("${mode}")
  t06_direct_hashes+=("${digest}")
done <"${tmp}/t06-direct.tsv"

dependency_paths=(
  "${authority_paths[@]}" "${t06_owned_paths[@]}" "${t06_direct_paths[@]}"
)
dependency_modes=(
  "${authority_modes[@]}" "${t06_owned_modes[@]}" "${t06_direct_modes[@]}"
)
dependency_hashes=(
  "${authority_hashes[@]}" "${t06_owned_hashes[@]}" "${t06_direct_hashes[@]}"
)

[[ "${#packet_paths[@]}" == 8 && "${#packet_modes[@]}" == 8 \
  && "${#packet_hash_paths[@]}" == 7 && "${#packet_hashes[@]}" == 7 ]] \
  || fail "eight-path packet catalog drift"
[[ "${#authority_paths[@]}" == 7 && "${#t06_owned_paths[@]}" == 8 \
  && "${#t06_direct_paths[@]}" == 39 ]] \
  || fail "dependency partition cardinality drift"
[[ "${#dependency_paths[@]}" == 54 && "${#dependency_modes[@]}" == 54 \
  && "${#dependency_hashes[@]}" == 54 ]] \
  || fail "54-path direct dependency catalog drift"
printf '%s\n' "${packet_paths[@]}" "${dependency_paths[@]}" \
  | /usr/bin/sort >"${tmp}/protected-paths"
[[ "$(/usr/bin/awk 'END {print NR}' "${tmp}/protected-paths")" == 62 \
  && "$(/usr/bin/sort -u "${tmp}/protected-paths" | /usr/bin/awk 'END {print NR}')" == 62 ]] \
  || fail "62-path protected archive cardinality or uniqueness drift"

printf '%s\n' "${authority_paths[@]}" | /usr/bin/sort \
  | /usr/bin/awk '{print "A\t" $0}' >"${tmp}/expected-authority-delta"
git_clean diff-tree --no-commit-id --name-status -r \
  "${authority_source_parent}" "${authority_source_commit}" | /usr/bin/sort \
  >"${tmp}/authority-source-delta"
/usr/bin/cmp -s "${tmp}/expected-authority-delta" "${tmp}/authority-source-delta" \
  || fail "authority source is not exact seven-path all-add"
git_clean diff-tree --no-commit-id --name-status -r \
  "${authority_integration_first_parent}" "${authority_integration_commit}" \
  | /usr/bin/sort >"${tmp}/authority-integration-delta"
/usr/bin/cmp -s "${tmp}/expected-authority-delta" "${tmp}/authority-integration-delta" \
  || fail "authority integration first-parent delta drift"

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

printf '%s\n' "${packet_paths[@]}" | /usr/bin/sort \
  | /usr/bin/awk '{print "A\t" $0}' >"${tmp}/expected-source-delta"
git_clean diff-tree --no-commit-id --name-status -r \
  "${baseline_commit}" "${source_commit}" | /usr/bin/sort >"${tmp}/source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/source-delta" \
  || fail "source is not exact eight-path all-add"
if [[ "${mode}" == integrated ]]; then
  git_clean diff-tree --no-commit-id --name-status -r \
    "${first_parent}" "${head_oid}" | /usr/bin/sort >"${tmp}/integration-delta"
  /usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/integration-delta" \
    || fail "integration first-parent delta drift"
fi

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

validate_unique_tsv() {
  local path="$1"
  /usr/bin/awk -F '\t' '
    NF != 2 { exit 1 }
    $1 !~ /^[a-z][a-z0-9_]*$/ { exit 1 }
    seen[$1]++ { exit 1 }
    END { if (NR < 1) exit 1 }
  ' "${path}" || fail "TSV must have exact two-column globally unique ASCII keys: ${path}"
}

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
  validate_unique_tsv "${tmp}/checker-${seed}.stdout"
  /usr/bin/cmp -s "${tmp}/checker-${seed}.stdout" "${tmp}/archive/${expected_path}" \
    || fail "checker stdout differs from exact expected TSV for seed ${seed}"
  [[ "$(/usr/bin/awk 'END {print NR}' "${tmp}/checker-${seed}.stdout")" \
    == "${checker_stdout_line_count}" ]] || fail "checker stdout line-count drift"
  [[ "$(/usr/bin/sha256sum "${tmp}/checker-${seed}.stdout" | /usr/bin/awk '{print $1}')" \
    == "${checker_stdout_sha256}" ]] || fail "checker stdout hash drift"
done
/usr/bin/cmp -s "${tmp}/checker-0.stdout" "${tmp}/checker-1.stdout" \
  || fail "checker hash-seed drift"
/usr/bin/cmp -s "${tmp}/checker-0.stdout" "${tmp}/checker-8675309.stdout" \
  || fail "checker hash-seed drift"
validate_unique_tsv "${tmp}/archive/${expected_path}"

if ! /usr/bin/env -i HOME="${tmp}/home" PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  PYTHONHASHSEED=314159 TMPDIR="${tmp}/home" \
  /usr/bin/python3 -B -S -P "${tmp}/archive/${checker_path}" --self-test \
  >"${tmp}/checker-self-test.stdout" 2>"${tmp}/checker-self-test.stderr"; then
  /usr/bin/cat "${tmp}/checker-self-test.stderr" >&2
  fail "checker self-test failed"
fi
[[ ! -s "${tmp}/checker-self-test.stderr" ]] || fail "checker self-test emitted stderr"
[[ "$(/usr/bin/awk 'END {print NR}' "${tmp}/checker-self-test.stdout")" \
  == "${checker_self_test_line_count}" ]] || fail "checker self-test line-count drift"
[[ "$(/usr/bin/sha256sum "${tmp}/checker-self-test.stdout" | /usr/bin/awk '{print $1}')" \
  == "${checker_self_test_stdout_sha256}" ]] || fail "checker self-test hash drift"
[[ -z "$(/usr/bin/find "${tmp}/archive" \( -name '*.pyc' -o -name __pycache__ \) -print -quit)" ]] \
  || fail "Python cache emitted"

# Closed-world manifest assertions cover the release topology and single-use
# semantics.  The independent checker remains the semantic oracle for T07.
if ! /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -B -S -P - "${tmp}/archive/${manifest_path}" \
    "${checker_stdout_line_count}" "${checker_stdout_sha256}" \
    "${checker_self_test_line_count}" "${checker_self_test_stdout_sha256}" \
    "${directed_mutation_count}" <<'PY'
import json
import sys

def reject_duplicate(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    manifest = json.load(
        handle,
        object_pairs_hook=reject_duplicate,
        parse_float=lambda _value: (_ for _ in ()).throw(ValueError("float forbidden")),
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant forbidden")),
    )
assert type(manifest) is dict
assert manifest["schema_version"] == 1 and type(manifest["schema_version"]) is int
assert manifest["date"] == "2026-07-18"
assert manifest["source_baseline"] == {
    "commit": "084eb71dd9c95fbc6285041b1503327705f9a6a1",
    "tree": "bc577acfb1e7614daf2008a1758379bb09c9f357",
    "parents": [
        "5f509375248aae43b7524effd30f023c86d83087",
        "f39307d093a91f3d2734488ca5db31c9e4e50df3",
    ],
}
authority = manifest["authority"]
assert authority["decision_source_commit"] == "f39307d093a91f3d2734488ca5db31c9e4e50df3"
assert authority["decision_integration_commit"] == "084eb71dd9c95fbc6285041b1503327705f9a6a1"
assert authority["decision_gate_raw_sha256"] == (
    "63ccb6cb7ab5f8c31fa3be1d1c64192002694b59246ee3390aed9f5172d73dc0"
)
assert authority["decision_fast_stdout_line_count"] == 144
assert authority["decision_fast_stdout_sha256"] == (
    "a08ed2dd908df85d8cdd7f503c519772293566c4f1a49670eade320d2bee679e"
)
assert authority["decision_full_stdout_line_count"] == 145
assert authority["decision_full_stdout_sha256"] == (
    "8a873b53a205027b14412507d4d65e5ccb181275eab5a6afb8760af130408ab8"
)
assert authority["implementation_authority_single_use_consumed_at_source_baseline"] is False
assert authority["decision_full_gate_consumes_new_authority"] is False
state = manifest["state"]
assert state["implementation_authority_single_use_consumed_before_integrated_full_gate"] is False
assert state["implementation_authority_consumed_only_by_exact_integrated_full_gate"] is True
assert state["source_fast_consumes_implementation_authority"] is False
assert state["integrated_fast_consumes_implementation_authority"] is False
assert state["failed_full_gate_consumes_implementation_authority"] is False
assert state["global_single_use_proved"] is False
topology = manifest["dependency_topology"]
assert topology["t07_authority_decision_pack_artifact_count"] == 7
assert topology["t06_owned_pack_artifact_count"] == 8
assert topology["t06_frozen_direct_dependency_artifact_count"] == 39
assert topology["direct_dependency_artifact_count"] == 54
assert topology["owned_packet_path_count"] == 8
assert topology["protected_archive_path_count"] == 62
assert topology["only_current_t07_authority_gate_executed"] is True
assert topology["t06_gate_not_separately_executed"] is True
assert topology["t05_gate_not_separately_executed"] is True
expected = manifest["expected"]
assert expected["checker_stdout_line_count"] == int(sys.argv[2])
assert expected["checker_stdout_sha256"] == sys.argv[3]
assert expected["checker_self_test_stdout_line_count"] == int(sys.argv[4])
assert expected["checker_self_test_stdout_sha256"] == sys.argv[5]
assert expected["total_directed_negative_test_count"] == int(sys.argv[6])
boundary = manifest["boundary"]
assert boundary["isolated_lab_candidate_surface_component_total"] == 5
assert boundary["local_t07_specification_exercised_after_integrated_full_gate"] is True
assert boundary["local_t08_specification_exercised"] is False
assert boundary["local_t09_specification_exercised"] is False
assert boundary["production_ingestion_controls_implemented"] == 0
assert boundary["production_ingestion_controls_runtime_exercised"] == 0
assert boundary["runtime_prerequisites_satisfied"] == 0
assert boundary["real_evidence_items_present"] == 0
assert boundary["runtime_authority"] is False
assert boundary["provider_authority"] is False
assert len(manifest["dependency_artifact_raw_sha256"]) == 54
assert len(manifest["dependency_artifact_modes"]) == 54
assert len(manifest["packet_path_modes"]) == 8
assert list(manifest["packet_path_modes"].values()).count("100755") == 1
assert all(value is False for value in manifest["nonclaims"].values())
PY
then
  fail "manifest closed-world semantic validation failed"
fi

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
check_private_scratch_limit
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
check_private_scratch_limit

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
    == "${authority_gate_sha256}" ]] || fail "isolated authority gate identity drift"

authority_line_count="${authority_fast_line_count}"
authority_stdout_sha256="${authority_fast_stdout_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  authority_line_count="${authority_full_line_count}"
  authority_stdout_sha256="${authority_full_stdout_sha256}"
fi

# Exactly one foreground, serial authority invocation.  The T07 authority gate
# owns T06 and all deeper replay; this gate never calls T06 or T05 separately.
if ! "${authority_repo}/${authority_gate}" "${validation_tier}" \
  >"${tmp}/authority.stdout" 2>"${tmp}/authority.stderr"; then
  /usr/bin/cat "${tmp}/authority.stderr" >&2
  fail "authority ${validation_tier} replay failed"
fi
[[ ! -s "${tmp}/authority.stderr" ]] || fail "authority replay emitted stderr"
validate_unique_tsv "${tmp}/authority.stdout"
[[ "$(/usr/bin/awk 'END {print NR}' "${tmp}/authority.stdout")" == "${authority_line_count}" ]] \
  || fail "authority receipt line-count drift"
authority_receipt_sha256="$(
  /usr/bin/sha256sum "${tmp}/authority.stdout" | /usr/bin/awk '{print $1}'
)"
[[ "${authority_receipt_sha256}" == "${authority_stdout_sha256}" ]] \
  || fail "authority receipt hash drift"
[[ "$(/usr/bin/awk 'END {print NR}' "${authority_repo}/${authority_expected}")" \
  == "${authority_expected_line_count}" ]] || fail "authority expected TSV line-count drift"
/usr/bin/awk -v limit="${authority_expected_line_count}" 'NR <= limit {print}' \
  "${tmp}/authority.stdout" >"${tmp}/authority-prefix.tsv"
/usr/bin/cmp -s "${authority_repo}/${authority_expected}" "${tmp}/authority-prefix.tsv" \
  || fail "authority expected TSV prefix drift"

receipt_value() {
  local key="$1" path="$2"
  /usr/bin/awk -F '\t' -v key="${key}" '$1 == key {print $2}' "${path}"
}
require_receipt_value() {
  local key="$1" expected="$2" path="$3" actual
  actual="$(receipt_value "${key}" "${path}")"
  [[ "${actual}" == "${expected}" ]] \
    || fail "receipt field drift: ${key}=${actual}; expected ${expected}"
}

require_receipt_value topology_mode integrated "${tmp}/authority.stdout"
require_receipt_value source_commit "${authority_source_commit}" "${tmp}/authority.stdout"
require_receipt_value head "${authority_integration_commit}" "${tmp}/authority.stdout"
require_receipt_value decision_scope \
  TRACK_PROFILE_BINDING_ISOLATED_LAB_EXACT_UNIT_SINGLE_USE_NON_TRANSITIVE \
  "${tmp}/authority.stdout"
require_receipt_value decision_full_gate_consumes_new_authority false "${tmp}/authority.stdout"
require_receipt_value implementation_authority_non_transitive true "${tmp}/authority.stdout"
require_receipt_value implementation_authority_subdelegation_authorized false \
  "${tmp}/authority.stdout"
require_receipt_value implementation_authority_single_use_consumed false \
  "${tmp}/authority.stdout"
require_receipt_value production_ingestion_controls_implemented 0 "${tmp}/authority.stdout"
require_receipt_value production_ingestion_controls_runtime_exercised 0 \
  "${tmp}/authority.stdout"
require_receipt_value runtime_prerequisites_satisfied 0 "${tmp}/authority.stdout"
require_receipt_value real_evidence_items_present 0 "${tmp}/authority.stdout"
require_receipt_value runtime_authority false "${tmp}/authority.stdout"
require_receipt_value provider_authority false "${tmp}/authority.stdout"

authority_effective_before_consumption=false
authority_full_replay_verified=false
if [[ "${validation_tier}" == full-replay ]]; then
  require_receipt_value gate PASS "${tmp}/authority.stdout"
  require_receipt_value effective_authorization_state \
    AUTHORIZED_TRACK_PROFILE_BINDING_ISOLATED_LAB_EXACT_UNIT "${tmp}/authority.stdout"
  require_receipt_value track_profile_binding_implementation_authority_effective true \
    "${tmp}/authority.stdout"
  require_receipt_value effective_implementation_authority_recorded true \
    "${tmp}/authority.stdout"
  require_receipt_value gate_verified_predecessor_authorization_consumption_state \
    CONSUMED_SCOPE_COMPLETE "${tmp}/authority.stdout"
  require_receipt_value predecessor_authorization_consumption_verified true \
    "${tmp}/authority.stdout"
  require_receipt_value artifact_release_evidence true "${tmp}/authority.stdout"
  require_receipt_value validation_tier PERIODIC_FULL_FROZEN_CHAIN_REPLAY \
    "${tmp}/authority.stdout"
  [[ -z "$(receipt_value fast_gate "${tmp}/authority.stdout")" ]] \
    || fail "authority full receipt contains fast marker"
  authority_effective_before_consumption=true
  authority_full_replay_verified=true
else
  require_receipt_value gate FAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY \
    "${tmp}/authority.stdout"
  require_receipt_value effective_authorization_state \
    UNRECORDED_NO_AUTHORITY_PENDING_DECISION_INTEGRATED_FULL_GATE \
    "${tmp}/authority.stdout"
  require_receipt_value track_profile_binding_implementation_authority_effective false \
    "${tmp}/authority.stdout"
  require_receipt_value effective_implementation_authority_recorded false \
    "${tmp}/authority.stdout"
  require_receipt_value artifact_release_evidence false "${tmp}/authority.stdout"
  require_receipt_value validation_tier FAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY \
    "${tmp}/authority.stdout"
  [[ "$(receipt_value gate "${tmp}/authority.stdout")" != PASS ]] \
    || fail "authority fast receipt contains release marker"
fi
check_private_scratch_limit
[[ "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" rev-parse HEAD)" \
  == "${authority_integration_commit}" ]] || fail "authority replay HEAD moved"
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "authority replay dirtied checkout"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD changed during gate"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "gate dirtied worktree or index"

suffix="${tmp}/gate-suffix.tsv"
: >"${suffix}"
if [[ "${validation_tier}" == full-replay ]]; then
  [[ "${authority_effective_before_consumption}" == true \
    && "${authority_full_replay_verified}" == true ]] \
    || fail "consumption requires effective unconsumed full authority"
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_T07_TRACK_PROFILE_BINDING_SYNTHETIC_EXACT_VERIFIER_ISOLATED_LAB_V1_PACK\n' >>"${suffix}"
  printf 'gate\tPASS\n' >>"${suffix}"
  printf 'authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE\n' >>"${suffix}"
  printf 'implementation_authority_single_use_consumed\ttrue\n' >>"${suffix}"
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n' >>"${suffix}"
  printf 'authorization_consumption_state\tUNRECORDED_NO_AUTHORITY_REQUIRES_AUTHORITY_AND_SUCCESSOR_INTEGRATED_FULL_REPLAY\n' >>"${suffix}"
  printf 'implementation_authority_single_use_consumed\tfalse\n' >>"${suffix}"
fi
printf 'topology_mode\t%s\n' "${mode}" >>"${suffix}"
printf 'baseline_commit\t%s\n' "${baseline_commit}" >>"${suffix}"
printf 'source_commit\t%s\n' "${source_commit}" >>"${suffix}"
printf 'source_parent\t%s\n' "${baseline_commit}" >>"${suffix}"
printf 'head\t%s\n' "${head_oid}" >>"${suffix}"
printf 'head_tree\t%s\n' "$(git_clean show -s --format='%T' "${head_oid}")" >>"${suffix}"
printf 'head_parents\t%s\n' "$(git_clean show -s --format='%P' "${head_oid}")" >>"${suffix}"
printf 'packet_path_count\t8\n' >>"${suffix}"
printf 't07_authority_owned_artifact_count\t7\n' >>"${suffix}"
printf 't06_owned_artifact_count\t8\n' >>"${suffix}"
printf 't06_frozen_direct_dependency_artifact_count\t39\n' >>"${suffix}"
printf 'dependency_artifact_count\t54\n' >>"${suffix}"
printf 'protected_archive_path_count\t62\n' >>"${suffix}"
printf 'checker_stdout_sha256\t%s\n' "${checker_stdout_sha256}" >>"${suffix}"
printf 'checker_stdout_line_count\t%s\n' "${checker_stdout_line_count}" >>"${suffix}"
printf 'checker_self_test_stdout_sha256\t%s\n' "${checker_self_test_stdout_sha256}" >>"${suffix}"
printf 'checker_self_test_line_count\t%s\n' "${checker_self_test_line_count}" >>"${suffix}"
printf 'directed_mutation_count\t%s\n' "${directed_mutation_count}" >>"${suffix}"
printf 'current_authority_gate_invocation_count\t1\n' >>"${suffix}"
printf 'separate_t06_gate_invocation_count\t0\n' >>"${suffix}"
printf 'separate_t05_gate_invocation_count\t0\n' >>"${suffix}"
printf 'authority_gate_owns_deeper_t06_and_t05_replay\ttrue\n' >>"${suffix}"
printf 'authority_replay_tier\t%s\n' "${validation_tier}" >>"${suffix}"
printf 'authority_receipt_sha256\t%s\n' "${authority_receipt_sha256}" >>"${suffix}"
printf 'authority_decision_full_gate_consumes_new_authority\tfalse\n' >>"${suffix}"
printf 'authority_effective_before_consumption\t%s\n' "${authority_effective_before_consumption}" >>"${suffix}"
printf 'authority_full_replay_verified\t%s\n' "${authority_full_replay_verified}" >>"${suffix}"
printf 'authority_replay_authorizes_another_successor\tfalse\n' >>"${suffix}"
printf 'global_single_use_proved\tfalse\n' >>"${suffix}"
printf 'private_scratch_checkpoint_cap_bytes\t%s\n' "${max_private_scratch_bytes}" >>"${suffix}"
printf 'private_scratch_checkpoint_cap_passed\ttrue\n' >>"${suffix}"
printf 'private_scratch_checkpoint_scope\tSUCCESSOR_GATE_TREE_ONLY_AFTER_PROTECTED_ARCHIVE_CLONE_CHECKOUT_AND_T07_AUTHORITY_REPLAY\n' >>"${suffix}"
printf 'private_scratch_quota_enforced\tfalse\n' >>"${suffix}"
printf 'max_parallel_workers\t1\n' >>"${suffix}"
if [[ "${validation_tier}" == full-replay ]]; then
  printf 'released_track_profile_binding_component_implemented\ttrue\n' >>"${suffix}"
  printf 'release_local_t07_specification_exercised\ttrue\n' >>"${suffix}"
  printf 'released_isolated_lab_surface_components_implemented\t5\n' >>"${suffix}"
  printf 'released_local_threat_specifications_covered\t7\n' >>"${suffix}"
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n' >>"${suffix}"
  printf 'periodic_full_replay_required\tfalse\n' >>"${suffix}"
  printf 'artifact_release_evidence\ttrue\n' >>"${suffix}"
  printf 'full_replay_gate\tVALID_T07_TRACK_PROFILE_BINDING_SYNTHETIC_EXACT_VERIFIER_AND_FULL_FROZEN_AUTHORITY_T06_T05_IMPORT_CLOSURE\n' >>"${suffix}"
else
  printf 'released_track_profile_binding_component_implemented\tfalse\n' >>"${suffix}"
  printf 'release_local_t07_specification_exercised\tfalse\n' >>"${suffix}"
  printf 'released_isolated_lab_predecessor_surface_components_implemented\t4\n' >>"${suffix}"
  printf 'released_local_predecessor_threat_specifications_covered\t6\n' >>"${suffix}"
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_AUTHORITY_FAST_REPLAY\n' >>"${suffix}"
  printf 'periodic_full_replay_required\ttrue\n' >>"${suffix}"
  printf 'artifact_release_evidence\tfalse\n' >>"${suffix}"
  printf 'fast_gate\tVALID_FAST_T07_TRACK_PROFILE_BINDING_SYNTHETIC_EXACT_VERIFIER_AND_AUTHORITY_CHAIN_IDENTITY\n' >>"${suffix}"
fi

validate_unique_tsv "${suffix}"
/usr/bin/cat "${tmp}/checker-0.stdout" "${suffix}" >"${tmp}/final-receipt.tsv"
validate_unique_tsv "${tmp}/final-receipt.tsv"

# All checks have completed.  Emit the already-validated unique-key receipt;
# EXIT cleanup removes the private scratch tree.
/usr/bin/cat "${tmp}/final-receipt.tsv"
