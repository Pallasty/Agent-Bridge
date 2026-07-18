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
  printf 'Bootstrap-trust public-vector supply v1 gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "${validation_tier}" in fast|full-replay) ;; *) fail "unknown validation tier" ;; esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/cmp /usr/bin/dirname
  /usr/bin/env /usr/bin/find /usr/bin/git /usr/bin/grep /usr/bin/mkdir
  /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm /usr/bin/rmdir
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar /usr/bin/wc
)
for tool in "${required_tools[@]}"; do [[ -x "${tool}" ]] || fail "missing tool ${tool}"; done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && -d "${repo_root}" && ! -L "${repo_root}" ]] || fail "invalid repository root"

baseline_commit="b4126a4192137e741e32ebb86170884b81185cbf"
baseline_tree="7d0e443c78e9c10e206e1ceed5df845030c85c4f"
baseline_parents="bf4f655207ef9f4e1178d0949a75d44e4877f15e ec8e2fce33c1d75b6e14273d2062666088e71108"
predecessor_gate="scripts/check-biocortex-ab-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.sh"
predecessor_gate_sha256="21c5aa21cebf7e37767a2ec0bcd38bd8b28839bd9b825c86e81920a2ce20aef0"
predecessor_fast_lines=53
predecessor_fast_sha256="2a53b935bd62ff6e004f773c357823867b857d7b9f72e5a2f1f2411a2f1e52b9"
predecessor_full_lines=54
predecessor_full_sha256="a40e9a208209de3a24904dc0957515e11f247ee7e07c070ff2306f32e553d77f"

source_path="scripts/eval/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack.py"
vector_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_public_vector_bundle_v0.json"
receipt_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_generation_provenance_receipt_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_v1_pack_v0.json"
frame_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-bootstrap-trust-public-only-vector-supply-and-generation-provenance-receipt-freeze-v1-pack.sh"
packet_paths=("${source_path}" "${checker_path}" "${vector_path}" "${receipt_path}" "${expected_path}" "${manifest_path}" "${report_path}" "${gate_path}")
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100755)
packet_hash_paths=("${source_path}" "${checker_path}" "${vector_path}" "${receipt_path}" "${expected_path}" "${manifest_path}" "${report_path}")
packet_hashes=(
  2a963bfab7e938deb3fce9c40765694e62d49c324322dec33b31d7ca459f661d
  844b4fe6523121297936e91737380b51023299eb2ca18b667e2e8e69953853a0
  a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7
  bdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0
  c684184bad18fa1265a6aa5e7d5ac0c7111aa49962e66a47b4b24f6bc898e79a
  451e05a19e1b30c70dbb7606ccc6f438cbee69595f8e8b7576fa255ef4ec91d7
  18ec5e3f9af4b4fee0531021b73f36babac4f6c5a9e3a4f9ddf4ae3edca62812
)
checker_stdout_sha256="6a6f20e61f6802970876316c47983df63c460b7ac85f97fe3c95598218359ba8"
checker_stdout_line_count=20

dependency_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.md"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-bootstrap-trust-fixture-custodian-one-shot-authority-amendment-v1-pack.sh"
  "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh"
  "scripts/eval/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1.py"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_owner_decision_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_fixture_custodian_one_shot_authority_amendment_v1_pack_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv"
  "${frame_path}"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json"
)
dependency_hashes=(
  e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55
  90d5327dd22a2b16b3644f7fe935d0401215d13bce6679ccda161866feea2cef
  a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149
  21c5aa21cebf7e37767a2ec0bcd38bd8b28839bd9b825c86e81920a2ce20aef0
  464b975d61403759221fd3aa41da4c38de12f4ec946b161100d23edadbc2b174
  35cdbf44f2f431f72bda796a39fc284dff04f217079c59b00d2ff289e15590cb
  bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1
  ff2a67d51246c482cc309f378e420de700843a13cfa86cd0b5e1d012ab516e0e
  76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf
  d913fa29cdef6d9ebf7ffa3a07c5cd687eaf26cd57611d255776016b8683076f
  c0ea20051d736d6b66090308756b1afaa309a4cd9fa9be53225d7caabe8bf54f
  0264011a5dfd046378c5e35acb8050d4753f6d487c0caa73e23cce4dc1eaaf41
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
tmp="$(/usr/bin/mktemp -d "${tmp_base}/bootstrap-public-vector-supply-v1.XXXXXX")"
cleanup() {
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  if [[ "${tmp_base_created}" == true ]]; then /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true; fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/archive" "${tmp}/home"

printf '%s\n' "${packet_paths[@]}" | /usr/bin/sort >"${tmp}/packet-paths"
/usr/bin/awk '{print "A\t" $0}' "${tmp}/packet-paths" >"${tmp}/expected-delta"
git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" | /usr/bin/sort >"${tmp}/source-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/source-delta" || fail "source is not exact eight-path all-add"
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
  env_args=(/usr/bin/env -i HOME="${tmp}/home" PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED="${seed}" TMPDIR="${tmp}/home")
  if ! "${env_args[@]}" /usr/bin/python3 -B -S -P "${tmp}/archive/${source_path}" "${tmp}/archive/${vector_path}" "${tmp}/archive/${receipt_path}" "${tmp}/archive/${frame_path}" >"${tmp}/source-${seed}.stdout" 2>"${tmp}/source-${seed}.stderr"; then
    /usr/bin/cat "${tmp}/source-${seed}.stderr" >&2
    fail "source failed for hash seed ${seed}"
  fi
  [[ ! -s "${tmp}/source-${seed}.stderr" ]] || fail "source emitted stderr"
  /usr/bin/cmp -s "${tmp}/source-${seed}.stdout" "${tmp}/archive/${expected_path}" || fail "source stdout drift"
  if ! "${env_args[@]}" /usr/bin/python3 -B -S -P "${tmp}/archive/${checker_path}" "${tmp}/archive/${source_path}" "${tmp}/archive/${vector_path}" "${tmp}/archive/${receipt_path}" "${tmp}/archive/${expected_path}" "${tmp}/archive/${frame_path}" "${tmp}/archive/${manifest_path}" >"${tmp}/checker-${seed}.stdout" 2>"${tmp}/checker-${seed}.stderr"; then
    /usr/bin/cat "${tmp}/checker-${seed}.stderr" >&2
    fail "checker failed for hash seed ${seed}"
  fi
  [[ ! -s "${tmp}/checker-${seed}.stderr" ]] || fail "checker emitted stderr"
  [[ "$(/usr/bin/wc -l <"${tmp}/checker-${seed}.stdout")" == "${checker_stdout_line_count}" ]] || fail "checker line count drift"
  [[ "$(/usr/bin/sha256sum "${tmp}/checker-${seed}.stdout" | /usr/bin/awk '{print $1}')" == "${checker_stdout_sha256}" ]] || fail "checker stdout hash drift"
done
/usr/bin/cmp -s "${tmp}/checker-0.stdout" "${tmp}/checker-1.stdout" || fail "checker hash-seed drift"
/usr/bin/cmp -s "${tmp}/checker-0.stdout" "${tmp}/checker-8675309.stdout" || fail "checker hash-seed drift"
[[ -z "$(/usr/bin/find "${tmp}/archive" \( -name '*.pyc' -o -name __pycache__ \) -print -quit)" ]] || fail "Python cache emitted"
[[ "$(/usr/bin/grep -Foc 'a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7' "${report_path}")" -ge 1 ]] || fail "report vector hash binding"
[[ "$(/usr/bin/grep -Foc 'bdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0' "${report_path}")" -ge 1 ]] || fail "report receipt hash binding"
[[ "$(/usr/bin/grep -Foc '451e05a19e1b30c70dbb7606ccc6f438cbee69595f8e8b7576fa255ef4ec91d7' "${report_path}")" -ge 1 ]] || fail "report manifest hash binding"

predecessor_repo="${tmp}/predecessor-replay"
if ! git_clean clone --no-local --no-hardlinks --no-checkout --no-tags --single-branch -- . "${predecessor_repo}" >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone predecessor replay repository"
fi
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" checkout --detach "${baseline_commit}" >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout predecessor integration"; }
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all)" ]] || fail "predecessor replay checkout dirty"
clone_common_dir="$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" rev-parse --path-format=absolute --git-common-dir)"
[[ ! -e "${clone_common_dir}/info/grafts" && ! -L "${clone_common_dir}/info/grafts" ]] || fail "predecessor clone grafts present"
[[ ! -e "${clone_common_dir}/info/attributes" && ! -L "${clone_common_dir}/info/attributes" ]] || fail "predecessor clone info attributes present"
[[ ! -e "${clone_common_dir}/objects/info/alternates" && ! -L "${clone_common_dir}/objects/info/alternates" ]] || fail "predecessor clone alternates present"
[[ "$(/usr/bin/sha256sum "${predecessor_repo}/${predecessor_gate}" | /usr/bin/awk '{print $1}')" == "${predecessor_gate_sha256}" ]] || fail "predecessor gate hash drift"

predecessor_tier=fast
predecessor_lines="${predecessor_fast_lines}"
predecessor_sha256="${predecessor_fast_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  predecessor_tier=full-replay
  predecessor_lines="${predecessor_full_lines}"
  predecessor_sha256="${predecessor_full_sha256}"
fi
if ! "${predecessor_repo}/${predecessor_gate}" "${predecessor_tier}" >"${tmp}/predecessor.stdout" 2>"${tmp}/predecessor.stderr"; then
  /usr/bin/cat "${tmp}/predecessor.stderr" >&2
  fail "predecessor replay failed"
fi
[[ ! -s "${tmp}/predecessor.stderr" ]] || fail "predecessor emitted stderr"
[[ "$(/usr/bin/wc -l <"${tmp}/predecessor.stdout")" == "${predecessor_lines}" ]] || fail "predecessor line count drift"
predecessor_receipt_sha256="$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')"
[[ "${predecessor_receipt_sha256}" == "${predecessor_sha256}" ]] || fail "predecessor receipt hash drift"
if [[ "${validation_tier}" == full-replay ]]; then
  [[ "$(/usr/bin/grep -Fxc $'artifact_release_evidence\ttrue' "${tmp}/predecessor.stdout")" == 1 ]] || fail "predecessor lacks release evidence"
  [[ "$(/usr/bin/grep -Fxc $'underlying_implementation_authority_effective\ttrue' "${tmp}/predecessor.stdout")" == 1 ]] || fail "implementation authority not effective"
  [[ "$(/usr/bin/grep -Fxc $'underlying_implementation_authority_single_use_consumed\ttrue' "${tmp}/predecessor.stdout")" == 0 ]] || fail "implementation authority already consumed"
  /usr/bin/grep -Fq $'underlying_implementation_authority_single_use_consumed\tfalse' "${tmp}/predecessor.stdout" || fail "implementation authority unconsumed marker absent"
fi
[[ "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" rev-parse HEAD)" == "${baseline_commit}" ]] || fail "predecessor replay HEAD moved"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all)" ]] || fail "predecessor replay dirtied checkout"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "gate dirtied worktree"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD moved during gate"

printf 'schema\tagent_bridge.biocortex_ab_track_b.bootstrap_trust_public_only_vector_supply_and_generation_provenance_receipt_freeze_gate.v1\n'
printf 'mode\t%s\n' "${mode}"
printf 'baseline_commit\t%s\n' "${baseline_commit}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'source_parent\t%s\n' "${baseline_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'head_tree\t%s\n' "$(git_clean show -s --format='%T' "${head_oid}")"
printf 'head_parents\t%s\n' "$(git_clean show -s --format='%P' "${head_oid}")"
printf 'packet_path_count\t8\n'
printf 'dependency_artifact_count\t15\n'
printf 'protected_archive_path_count\t23\n'
printf 'source_stdout_sha256\tc684184bad18fa1265a6aa5e7d5ac0c7111aa49962e66a47b4b24f6bc898e79a\n'
printf 'source_stdout_line_count\t41\n'
printf 'checker_stdout_sha256\t%s\n' "${checker_stdout_sha256}"
printf 'checker_stdout_line_count\t20\n'
printf 'directed_mutation_count\t33\n'
printf 'vector_bundle_sha256\ta87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7\n'
printf 'generation_receipt_sha256\tbdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0\n'
printf 'generator_source_sha256\t62a8e32eef9e9a5560cd6dacfce5a181761196cef18a77508eb8552c1e20f083\n'
printf 'fixture_generation_process_entry_count\t1\n'
printf 'fixture_generation_retry_count\t0\n'
printf 'fixture_generation_keypair_count\t6\n'
printf 'fixture_generation_signature_count\t2\n'
printf 'fixture_generation_revoked_leaf_keypair_count\t0\n'
printf 'certificate_link_signature_count\t0\n'
printf 'public_key_count\t6\n'
printf 'distinct_public_key_count\t6\n'
printf 'strict_public_point_validation_count\t6\n'
printf 'strict_signature_verification_count\t2\n'
printf 'positive_signature_verification_count_per_track\t1\n'
printf 'network_provider_credential_attempt_count\t0\n'
printf 'private_material_file_write_count\t0\n'
printf 'committed_private_material_count\t0\n'
printf 'generator_namespace_cleanup_complete\ttrue\n'
printf 'secure_erasure_claimed\tfalse\n'
printf 'fixture_generation_authority_single_use_consumed\ttrue\n'
printf 'underlying_implementation_authority_single_use_consumed\tfalse\n'
printf 'supply_pack_consumes_underlying_implementation_authority\tfalse\n'
printf 'gate_replay_authorizes_additional_generation_attempt\tfalse\n'
printf 'production_ingestion_controls_implemented\t0\n'
printf 'production_threat_specifications_runtime_exercised\t0\n'
printf 'runtime_prerequisites_satisfied\t0\n'
printf 'real_evidence_items_present\t0\n'
printf 'predecessor_amendment_receipt_sha256\t%s\n' "${predecessor_receipt_sha256}"
if [[ "${validation_tier}" == full-replay ]]; then
  printf 'integration_gate\tVALID_INTEGRATED_BOOTSTRAP_TRUST_PUBLIC_ONLY_VECTOR_SUPPLY_AND_GENERATION_PROVENANCE_RECEIPT_FREEZE_V1_PACK\n'
  printf 'gate\tPASS\n'
  printf 'effective_supply_state\tCONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE\n'
  printf 'underlying_implementation_authority_full_replay_verified\ttrue\n'
  printf 'underlying_implementation_authority_effective\ttrue\n'
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'artifact_release_evidence\ttrue\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
  printf 'effective_supply_state\tFROZEN_PUBLIC_OUTPUT_PENDING_INTEGRATED_FULL_GATE\n'
  printf 'underlying_implementation_authority_full_replay_verified\tfalse\n'
  printf 'underlying_implementation_authority_effective\tfalse\n'
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'artifact_release_evidence\tfalse\n'
fi
