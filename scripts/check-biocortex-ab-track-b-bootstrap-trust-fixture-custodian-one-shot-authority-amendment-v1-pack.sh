#!/usr/bin/env -S -i /usr/bin/bash
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
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'Bootstrap-trust fixture-custodian amendment v1 gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "${validation_tier}" in fast|full-replay) ;; *) fail "unknown validation tier" ;; esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/cmp /usr/bin/dirname /usr/bin/env
  /usr/bin/find /usr/bin/git /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp
  /usr/bin/python3 /usr/bin/rm /usr/bin/rmdir /usr/bin/sha256sum /usr/bin/sort
  /usr/bin/stat /usr/bin/tar /usr/bin/wc
)
for tool in "${required_tools[@]}"; do [[ -x "${tool}" ]] || fail "missing tool ${tool}"; done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && -d "${repo_root}" && ! -L "${repo_root}" ]] || fail "invalid repository root"

baseline_commit="a18f0af7b4cbaa971143c71080a2b49786a7f7a3"
baseline_tree="8afca41122ee482493afec9c2c4aa32d600c175e"
baseline_parents="f822f1d94d1327311d8c6443eb1c17a61de9663c 56b311418abc0b3461abe2a6582127f8927f9621"
authority_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
authority_gate_sha256="16fdb98784a567222e98a15cf9afc7947a70055957b1e8fc1735a9d03719daa5"
authority_fast_lines=126
authority_fast_sha256="2ec3b62897c4237b3d2f418a794b64511154ef436bb887b25c7a8418880c6e7c"
authority_full_lines=127
authority_full_sha256="ad5614db7653c4387f57c8e3d5bb52e40d2b21edeeecda7fc2c9bb5f2265dbb9"

source_path="scripts/eval/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack.py"
fixture_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_owner_decision_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.sh"
packet_paths=("${source_path}" "${checker_path}" "${fixture_path}" "${expected_path}" "${manifest_path}" "${report_path}" "${gate_path}")
packet_modes=(100644 100644 100644 100644 100644 100644 100755)
packet_hash_paths=("${source_path}" "${checker_path}" "${fixture_path}" "${expected_path}" "${manifest_path}" "${report_path}")
packet_hashes=(
  35cdbf44f2f431f72bda796a39fc284dff04f217079c59b00d2ff289e15590cb
  ff2a67d51246c482cc309f378e420de700843a13cfa86cd0b5e1d012ab516e0e
  d913fa29cdef6d9ebf7ffa3a07c5cd687eaf26cd57611d255776016b8683076f
  c0ea20051d736d6b66090308756b1afaa309a4cd9fa9be53225d7caabe8bf54f
  0264011a5dfd046378c5e35acb8050d4753f6d487c0caa73e23cce4dc1eaaf41
  90d5327dd22a2b16b3644f7fe935d0401215d13bce6679ccda161866feea2cef
)

dependency_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md"
  "${authority_gate}"
  "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json"
)
dependency_hashes=(
  e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55
  841df2168eaaabfb4c17dcc15e5adfd5ed9c833eb6e40bc2bd9998833549a78b
  a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149
  16fdb98784a567222e98a15cf9afc7947a70055957b1e8fc1735a9d03719daa5
  464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174
  f1168fad03ac6366e8d6501cbd4da3a2969d25cc6ef9f5bf85c0624de9ae545c
  bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1
  7c5f1dcd53db8bdf9360e8e00a6495daa40b97d21fbf4efa1f9f3392bfbd6136
  76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf
  79502975f438ed644306a392131d102e2efadae37560b3489c91547a0125e43f
  05f2fad20896cd108f0695253c617cd0c050e80ae947ec4c90f7d7684e3e344b
  e521a7aab3a3fa00dacade4da1bf88834680a878d4de425f77918734655e255e
  775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847
  324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9
  9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04
)

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="${repo_root}" "$@"
}

[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] || fail "shallow repository"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] || fail "replace refs present"
[[ "$(git_clean cat-file -t "${baseline_commit}")" == commit ]] || fail "baseline unavailable"
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${baseline_tree}" ]] || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${baseline_parents}" ]] || fail "baseline parents drift"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" || fail "cannot resolve common dir"
git_dir="$(git_clean rev-parse --path-format=absolute --git-dir)" || fail "cannot resolve git dir"
[[ -d "${common_dir}" && ! -L "${common_dir}" && -d "${git_dir}" && ! -L "${git_dir}" ]] || fail "git directory lineage invalid"
case "${git_dir}" in "${common_dir}"|"${common_dir}"/worktrees/*) ;; *) fail "git dir outside common lineage" ;; esac
[[ ! -e "${common_dir}/info/grafts" && ! -L "${common_dir}/info/grafts" ]] || fail "legacy grafts present"
[[ ! -e "${common_dir}/info/attributes" && ! -L "${common_dir}/info/attributes" ]] || fail "common info attributes present"
[[ ! -e "${common_dir}/objects/info/alternates" && ! -L "${common_dir}/objects/info/alternates" ]] || fail "alternate object store present"
while IFS= read -r config_key; do
  case "${config_key,,}" in
    filter.*|diff.*|merge.*|core.attributesfile|include.*|includeif.*)
      fail "executable or external git config present: ${config_key}"
      ;;
  esac
done < <(git_clean config --local --includes --name-only --list)
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index dirty"
[[ -z "$(/usr/bin/find . -name .gitattributes -print -quit)" ]] || fail "working-tree attributes present"

head_oid="$(git_clean rev-parse HEAD)"
read -r -a lineage < <(git_clean rev-list --parents -n 1 "${head_oid}")
parents=("${lineage[@]:1}")
mode=""
source_commit=""
first_parent=""
if [[ "${#parents[@]}" == 1 && "${parents[0]}" == "${baseline_commit}" ]]; then
  mode=source
  source_commit="${head_oid}"
elif [[ "${#parents[@]}" == 2 ]]; then
  mode=integrated
  first_parent="${parents[0]}"
  source_commit="${parents[1]}"
  read -r -a source_lineage < <(git_clean rev-list --parents -n 1 "${source_commit}")
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "${baseline_commit}" ]] || fail "second parent is not exact source"
  git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" || fail "first parent not baseline descendant"
  if git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}"; then fail "first parent already contains source"; else [[ "$?" == 1 ]] || fail "source exclusion unknown"; fi
else
  fail "HEAD is neither exact source nor ordinary two-parent integration"
fi
[[ "${validation_tier}" != full-replay || "${mode}" == integrated ]] || fail "full replay requires integration"

tmp_base="/Data/CascadeProjects/.ab-gate-tmp"
tmp_base_created=false
if [[ ! -e "${tmp_base}" ]]; then /usr/bin/mkdir -m 0700 "${tmp_base}"; tmp_base_created=true; fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] || fail "scratch root drift"
tmp="$(/usr/bin/mktemp -d "${tmp_base}/bootstrap-fixture-amendment-v1.XXXXXX")"
cleanup() {
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  if [[ "${tmp_base_created}" == true ]]; then /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true; fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/archive" "${tmp}/home"

printf '%s\n' "${packet_paths[@]}" | /usr/bin/sort >"${tmp}/packet-paths"
/usr/bin/awk '{print "A\t" $0}' "${tmp}/packet-paths" >"${tmp}/expected-delta"
git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" | /usr/bin/sort >"${tmp}/source-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/source-delta" || fail "source is not exact seven-path all-add"
if [[ "${mode}" == integrated ]]; then
  git_clean diff-tree --no-commit-id --name-status -r "${first_parent}" "${head_oid}" | /usr/bin/sort >"${tmp}/integration-delta"
  /usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/integration-delta" || fail "integration first-parent delta drift"
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
  read -r source_mode source_type source_oid source_name < <(git_clean ls-tree "${source_commit}" -- "${path}")
  read -r head_mode head_type head_oid_path head_name < <(git_clean ls-tree "${head_oid}" -- "${path}")
  [[ "${source_mode}" == "${expected_mode}" && "${source_type}" == blob && "${source_name}" == "${path}" ]] || fail "source path identity drift: ${path}"
  [[ "${head_mode}" == "${expected_mode}" && "${head_type}" == blob && "${head_name}" == "${path}" && "${head_oid_path}" == "${source_oid}" ]] || fail "head path identity drift: ${path}"
  [[ -f "${path}" && ! -L "${path}" && "$(/usr/bin/stat -c '%F' "${path}")" == "regular file" && "$(/usr/bin/stat -c '%h' "${path}")" == 1 ]] || fail "working path type drift: ${path}"
  [[ "$(git_clean hash-object -- "${path}")" == "${source_oid}" ]] || fail "working bytes drift: ${path}"
  read -r index_mode index_oid index_stage index_name < <(git_clean ls-files --stage -- "${path}")
  [[ "${index_mode}" == "${expected_mode}" && "${index_oid}" == "${source_oid}" && "${index_stage}" == 0 && "${index_name}" == "${path}" ]] || fail "index identity drift: ${path}"
done

for index in "${!packet_hash_paths[@]}"; do
  path="${packet_hash_paths[$index]}"
  digest="$(/usr/bin/sha256sum "${path}" | /usr/bin/awk '{print $1}')"
  [[ "${digest}" == "${packet_hashes[$index]}" ]] || fail "packet raw hash drift: ${path}"
done
for index in "${!dependency_paths[@]}"; do
  path="${dependency_paths[$index]}"
  reject_symlink_components "${path}"
  [[ -f "${path}" && ! -L "${path}" ]] || fail "dependency working type drift: ${path}"
  digest="$(git_clean show "${source_commit}:${path}" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')"
  [[ "${digest}" == "${dependency_hashes[$index]}" ]] || fail "dependency raw hash drift: ${path}"
  [[ "$(git_clean rev-parse "${source_commit}:${path}")" == "$(git_clean rev-parse "${head_oid}:${path}")" ]] || fail "dependency blob changed at head: ${path}"
done

archive_paths=("${packet_paths[@]}" "${dependency_paths[@]}")
git_clean archive --format=tar "${source_commit}" -- "${archive_paths[@]}" >"${tmp}/archive.tar"
/usr/bin/tar -xf "${tmp}/archive.tar" -C "${tmp}/archive"
for seed in 0 1 8675309; do
  if ! /usr/bin/env -i HOME="${tmp}/home" PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED="${seed}" \
    TMPDIR="${tmp}/home" /usr/bin/python3 -S -P "${tmp}/archive/${checker_path}" >"${tmp}/checker-${seed}.stdout" 2>"${tmp}/checker-${seed}.stderr"; then
    /usr/bin/cat "${tmp}/checker-${seed}.stderr" >&2
    fail "checker failed for hash seed ${seed}"
  fi
  [[ ! -s "${tmp}/checker-${seed}.stderr" ]] || fail "checker emitted stderr"
  /usr/bin/cmp -s "${tmp}/checker-${seed}.stdout" "${tmp}/archive/${expected_path}" || fail "checker stdout drift"
done
[[ -z "$(/usr/bin/find "${tmp}/archive" \( -name '*.pyc' -o -name __pycache__ \) -print -quit)" ]] || fail "Python cache emitted"
[[ "$(/usr/bin/grep -Foc 'd913fa29cdef6d9ebf7ffa3a07c5cd687eaf26cd57611d255776016b8683076f' "${report_path}")" == 1 ]] || fail "report fixture hash binding"
[[ "$(/usr/bin/grep -Foc 'c473be2365a38addebf6565932eeb811636401d8bef8129b791af662733d77fe' "${report_path}")" == 1 ]] || fail "report contract hash binding"
[[ "$(/usr/bin/grep -Foc '0264011a5dfd046378c5e35acb8050d4753f6d487c0caa73e23cce4dc1eaaf41' "${report_path}")" == 1 ]] || fail "report manifest hash binding"

authority_repo="${tmp}/authority-replay"
if ! git_clean clone --no-local --no-hardlinks --no-checkout --no-tags --single-branch -- . "${authority_repo}" >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone authority replay repository"
fi
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${authority_repo}" -C "${authority_repo}" checkout --detach "${baseline_commit}" >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout authority integration"; }
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" status --porcelain=v1 --untracked-files=all)" ]] || fail "authority replay checkout dirty"
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" for-each-ref --format='%(refname)' refs/replace)" ]] || fail "authority clone replace refs present"
clone_common_dir="$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" rev-parse --path-format=absolute --git-common-dir)"
[[ ! -e "${clone_common_dir}/info/grafts" && ! -L "${clone_common_dir}/info/grafts" ]] || fail "authority clone grafts present"
[[ ! -e "${clone_common_dir}/info/attributes" && ! -L "${clone_common_dir}/info/attributes" ]] || fail "authority clone info attributes present"
[[ ! -e "${clone_common_dir}/objects/info/alternates" && ! -L "${clone_common_dir}/objects/info/alternates" ]] || fail "authority clone alternates present"
[[ "$(/usr/bin/sha256sum "${authority_repo}/${authority_gate}" | /usr/bin/awk '{print $1}')" == "${authority_gate_sha256}" ]] || fail "authority gate hash drift"

authority_tier=fast
authority_lines="${authority_fast_lines}"
authority_sha256="${authority_fast_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  authority_tier=full-replay
  authority_lines="${authority_full_lines}"
  authority_sha256="${authority_full_sha256}"
fi
if ! "${authority_repo}/${authority_gate}" "${authority_tier}" >"${tmp}/authority.stdout" 2>"${tmp}/authority.stderr"; then
  /usr/bin/cat "${tmp}/authority.stderr" >&2
  fail "underlying authority replay failed"
fi
[[ ! -s "${tmp}/authority.stderr" ]] || fail "underlying authority emitted stderr"
[[ "$(/usr/bin/wc -l <"${tmp}/authority.stdout")" == "${authority_lines}" ]] || fail "underlying authority line count drift"
authority_receipt_sha256="$(/usr/bin/sha256sum "${tmp}/authority.stdout" | /usr/bin/awk '{print $1}')"
[[ "${authority_receipt_sha256}" == "${authority_sha256}" ]] || fail "underlying authority receipt hash drift"
if [[ "${validation_tier}" == full-replay ]]; then
  [[ "$(/usr/bin/grep -Fxc $'bootstrap_trust_authentication_implementation_authority_effective\ttrue' "${tmp}/authority.stdout")" == 1 ]] || fail "underlying authority not effective"
  /usr/bin/grep -Fq $'implementation_authority_single_use_consumed\tfalse' "${tmp}/authority.stdout" || fail "underlying authority unconsumed marker absent"
  [[ "$(/usr/bin/grep -Fxc $'implementation_authority_single_use_consumed\ttrue' "${tmp}/authority.stdout")" == 0 ]] || fail "underlying authority already consumed"
  [[ "$(/usr/bin/grep -Fxc $'artifact_release_evidence\ttrue' "${tmp}/authority.stdout")" == 1 ]] || fail "underlying authority lacks release evidence"
fi
[[ "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" rev-parse HEAD)" == "${baseline_commit}" ]] || fail "authority replay HEAD moved"
[[ -z "$(/usr/bin/git -c safe.directory="${authority_repo}" -C "${authority_repo}" status --porcelain=v1 --untracked-files=all)" ]] || fail "authority replay dirtied checkout"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "gate dirtied worktree"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD moved during gate"

printf 'schema\tagent_bridge.biocortex_ab_track_b.bootstrap_trust_fixture_custodian_one_shot_authority_amendment_gate.v1\n'
printf 'mode\t%s\n' "${mode}"
printf 'baseline_commit\t%s\n' "${baseline_commit}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'source_parent\t%s\n' "${baseline_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'head_tree\t%s\n' "$(git_clean show -s --format='%T' "${head_oid}")"
printf 'head_parents\t%s\n' "$(git_clean show -s --format='%P' "${head_oid}")"
printf 'packet_path_count\t7\n'
printf 'dependency_artifact_count\t15\n'
printf 'protected_archive_path_count\t22\n'
printf 'checker_stdout_sha256\tc0ea20051d736d6b66090308756b1afaa309a4cd9fa9be53225d7caabe8bf54f\n'
printf 'checker_stdout_line_count\t31\n'
printf 'owner_authorization_explicit\ttrue\n'
printf 'structural_policy_chain_entry_count_per_track\t3\n'
printf 'certificate_link_signature_count\t0\n'
printf 'positive_signature_verifications_per_review\t1\n'
printf 'fixture_keypair_generation_count_authorized\t6\n'
printf 'fixture_signature_generation_count_authorized\t2\n'
printf 'revoked_leaf_key_material_generation_authorized\tfalse\n'
printf 'role_mapping_count\t2\n'
printf 'role_mapping_authorization_effect\tfalse\n'
printf 'fixture_generation_process_start_limit\t1\n'
printf 'fixture_generation_consumption_event\tFIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN\n'
printf 'fixture_generation_retry_authorized\tfalse\n'
printf 'public_key_output_count_authorized\t6\n'
printf 'signature_output_count_authorized\t2\n'
printf 'private_seed_or_key_commit_authorized\tfalse\n'
printf 'generator_commit_authorized\tfalse\n'
printf 'minimum_distinct_semantic_actor_count\t4\n'
printf 'pairwise_actor_distinctness_required\ttrue\n'
printf 't05_implementation_authority_unchanged\ttrue\n'
printf 't06_implemented\tfalse\n'
printf 'production_ingestion_controls_implemented\t0\n'
printf 'production_threat_specifications_runtime_exercised\t0\n'
printf 'runtime_prerequisites_satisfied\t0\n'
printf 'real_evidence_items_present\t0\n'
printf 'network_provider_credential_authority\tfalse\n'
printf 'external_paid_spend_cap\t0\n'
printf 'underlying_authority_receipt_sha256\t%s\n' "${authority_receipt_sha256}"
printf 'underlying_implementation_authority_single_use_consumed\tfalse\n'
printf 'amendment_consumes_underlying_authority\tfalse\n'
printf 'gate_replay_authorizes_additional_generation_attempt\tfalse\n'
printf 'global_single_use_proved\tfalse\n'
if [[ "${validation_tier}" == full-replay ]]; then
  printf 'integration_gate\tVALID_INTEGRATED_BOOTSTRAP_TRUST_FIXTURE_CUSTODIAN_ONE_SHOT_AUTHORITY_AMENDMENT_V1_PACK\n'
  printf 'gate\tPASS\n'
  printf 'effective_amendment_state\tAUTHORIZED_ONE_SHOT_FIXTURE_CUSTODIAN_PENDING_PROCESS_START\n'
  printf 'fixture_generation_authority_effective\ttrue\n'
  printf 'fixture_generation_process_start_observed\tfalse\n'
  printf 'fixture_generation_authority_single_use_consumed\tfalse\n'
  printf 'underlying_implementation_authority_full_replay_verified\ttrue\n'
  printf 'underlying_implementation_authority_effective\ttrue\n'
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'artifact_release_evidence\ttrue\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
  printf 'effective_amendment_state\tUNRECORDED_NO_AUTHORITY_PENDING_AMENDMENT_INTEGRATED_FULL_GATE\n'
  printf 'fixture_generation_authority_effective\tfalse\n'
  printf 'fixture_generation_process_start_observed\tfalse\n'
  printf 'fixture_generation_authority_single_use_consumed\tfalse\n'
  printf 'underlying_implementation_authority_full_replay_verified\tfalse\n'
  printf 'underlying_implementation_authority_effective\tfalse\n'
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'artifact_release_evidence\tfalse\n'
fi
