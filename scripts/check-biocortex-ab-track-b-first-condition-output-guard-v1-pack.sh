#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, descendant-compatible, fail-closed Git gate for the Track B
# first-condition-output guard v1 local validation packet.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONSAFEPATH=1
export GIT_OPTIONAL_LOCKS=0
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

for absolute_tool in /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/chmod \
  /usr/bin/cmp /usr/bin/dirname /usr/bin/env /usr/bin/git /usr/bin/head \
  /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm \
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar; do
  [[ -x "${absolute_tool}" ]] || {
    printf 'Track B first-condition-output guard v1 gate missing trusted tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

baseline_commit="8daa44ee5406b700c59b57b0e44514421bc2f0ad"
plan_schema="docs/design/fixtures/biocortex-ab-track-b-pre-output-generation-plan-schema-v1.json"
receipt_schema="docs/design/fixtures/biocortex-ab-track-b-local-guard-validation-receipt-schema-v1.json"
guard_source="scripts/eval/biocortex_ab_track_b_first_condition_output_guard_v1.py"
purpose_checker="scripts/eval/check_biocortex_ab_track_b_first_condition_output_guard_v1_pack.py"
synthetic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack_synthetic_v0.json"
expected_result="scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack.expected.v0.tsv"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack_v0.json"
report="docs/reports/goal-c-u/2026-07-15-biocortex-track-b-first-condition-output-guard-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-first-condition-output-guard-v1-pack.sh"
custodian_gate="scripts/check-biocortex-ab-track-b-sampling-attempt-custodian-v1-pack.sh"

packet_paths=(
  "${plan_schema}"
  "${receipt_schema}"
  "${guard_source}"
  "${purpose_checker}"
  "${synthetic_fixture}"
  "${expected_result}"
  "${manifest}"
  "${report}"
  "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100755)

# Freeze these after the checker, oracle, and manifest have reached their final
# bytes.  The report and this gate are instead bound by the exact source-commit
# blob identities, avoiding a circular report<->gate digest dependency.  The
# final report may record the settled gate digest after these slots are filled.
frozen_manifest_sha256="a7d8e5bf314b873b539211d5909427b0e26a8209bf8ef141096e39eb75b9e1a6"
frozen_purpose_checker_sha256="e156255d5dd136e35672c429201beda3ebd2e57e57cc672adf7c20a69bdb3f4a"
frozen_expected_result_sha256="96e1d5910f02c3777e7274657e906be7a8265d876a0692904827a81d2899368c"

required_manifest_evidence_paths=(
  "crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs"
  "docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json"
  "${receipt_schema}"
  "${plan_schema}"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s11-v0.json"
  "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-atomic-authority-operation-s11.md"
  "docs/reports/goal-c-u/2026-07-14-biocortex-track-b-sampling-attempt-custodian-v1-pack.md"
  "${custodian_gate}"
  "scripts/check-memory-temporal-atomic-authority-operation-s11.sh"
  "${guard_source}"
  "scripts/eval/biocortex_ab_track_b_sampling_attempt_custodian_v1.py"
  "${purpose_checker}"
  "scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py"
  "scripts/eval/check_memory_temporal_atomic_authority_operation_s11.py"
  "${expected_result}"
  "${synthetic_fixture}"
  "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack_v0.json"
  "scripts/eval/fixtures/memory_temporal_atomic_authority_operation_s11.expected.v0.tsv"
)

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp"

fail() {
  printf 'Track B first-condition-output guard v1 gate failed: %s\n' "$*" >&2
  exit 1
}

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.commitGraph=false -c core.hooksPath=/dev/null "$@"
}

verify_history_metadata() {
  local common_dir grafts_path
  [[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
    || fail "Git replace refs are present"
  [[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] \
    || fail "shallow repository history is not admissible"
  common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
    || fail "cannot resolve absolute Git common directory"
  [[ -d "${common_dir}" && ! -L "${common_dir}" ]] \
    || fail "Git common directory is missing or is a symlink"
  grafts_path="${common_dir}/info/grafts"
  [[ ! -e "${grafts_path}" && ! -L "${grafts_path}" ]] \
    || fail "legacy Git graft metadata is present"
}

reject_symlink_components() {
  local path="$1" component cursor=""
  local -a components
  IFS=/ read -r -a components <<<"${path}"
  for component in "${components[@]}"; do
    if [[ -n "${cursor}" ]]; then
      cursor="${cursor}/${component}"
    else
      cursor="${component}"
    fi
    [[ ! -L "${cursor}" ]] || fail "protected path contains a symlink: ${path}"
  done
}

verify_regular_unaliased() {
  local path="$1"
  reject_symlink_components "${path}"
  [[ -f "${path}" && "$(/usr/bin/stat -c '%F' -- "${path}")" == "regular file" ]] \
    || fail "protected path is not a regular file: ${path}"
  [[ "$(/usr/bin/stat -c '%h' -- "${path}")" == 1 ]] \
    || fail "protected path has hard-link aliases: ${path}"
}

verify_packet_identity() {
  local index path expected_mode
  local index_mode index_object index_stage indexed
  local source_mode source_type source_object source_indexed
  local head_mode head_type head_object head_indexed
  [[ "${#packet_paths[@]}" == 9 && "${#packet_paths[@]}" == "${#packet_modes[@]}" ]] \
    || fail "packet path/mode catalog length drift"
  for index in "${!packet_paths[@]}"; do
    path="${packet_paths[$index]}"
    expected_mode="${packet_modes[$index]}"
    verify_regular_unaliased "${path}"
    read -r index_mode index_object index_stage indexed \
      < <(git_clean ls-files --stage -- "${path}") \
      || fail "cannot resolve index identity: ${path}"
    read -r source_mode source_type source_object source_indexed \
      < <(git_clean ls-tree "${source_commit}" -- "${path}") \
      || fail "cannot resolve source identity: ${path}"
    read -r head_mode head_type head_object head_indexed \
      < <(git_clean ls-tree "${head_oid}" -- "${path}") \
      || fail "cannot resolve HEAD identity: ${path}"
    [[ "${index_mode}" == "${expected_mode}" \
      && "${source_mode}" == "${expected_mode}" \
      && "${head_mode}" == "${expected_mode}" \
      && "${source_type}" == blob && "${head_type}" == blob \
      && "${index_stage}" == 0 && "${indexed}" == "${path}" \
      && "${source_indexed}" == "${path}" && "${head_indexed}" == "${path}" \
      && "${index_object}" == "${source_object}" \
      && "${head_object}" == "${source_object}" ]] \
      || fail "source/HEAD/index Git identity or mode drift: ${path}"
    [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
      || fail "nondefault Git index flag: ${path}"
    /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${source_object}") \
      || fail "worktree/source-commit byte drift: ${path}"
  done
}

verify_descendant_integration_shape() {
  local merge_oid first_parent path precontains_packet found=0
  local -a merge_candidates parents
  [[ "${head_oid}" != "${source_commit}" ]] || return 0
  mapfile -t merge_candidates < <(
    git_clean rev-list --ancestry-path --merges "${source_commit}..${head_oid}"
  )
  for merge_oid in "${merge_candidates[@]}"; do
    parents=()
    mapfile -t parents < <(
      git_clean cat-file commit "${merge_oid}" | /usr/bin/awk '
        BEGIN { in_headers = 1 }
        in_headers && $0 == "" { in_headers = 0 }
        in_headers && $1 == "parent" { print $2 }
      '
    )
    [[ "${#parents[@]}" == 2 ]] || continue
    [[ "${parents[1]}" == "${source_commit}" ]] || continue
    first_parent="${parents[0]}"
    git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" \
      || continue
    if git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}"; then
      continue
    fi
    precontains_packet=0
    for path in "${packet_paths[@]}"; do
      if [[ -n "$(git_clean ls-tree "${first_parent}" -- "${path}")" ]]; then
        precontains_packet=1
        break
      fi
    done
    [[ "${precontains_packet}" == 0 ]] || continue
    found=1
    break
  done
  [[ "${found}" == 1 ]] \
    || fail "descendant HEAD lacks an ordinary two-parent merge with the exact source as second parent"
}

verify_frozen_sha256() {
  local label="$1" expected="$2" path="$3" actual
  [[ "${expected}" =~ ^[0-9a-f]{64}$ ]] \
    || fail "${label} SHA-256 is not frozen: ${expected}"
  actual="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] \
    || fail "${label} frozen SHA-256 drift: ${path}"
}

materialize_source_archive() {
  /usr/bin/mkdir -m 0700 "${tmp}/source-archive"
  git_clean archive --format=tar "${source_commit}" \
    | /usr/bin/tar -xf - -C "${tmp}/source-archive" \
    || fail "cannot materialize exact source commit archive"
  HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" PYTHONHASHSEED=0 \
    /usr/bin/python3 -S -P - "${tmp}/source-archive" <<'PY' \
      || fail "source archive contains a symlink, hard link, or special file"
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
for directory, directory_names, file_names in os.walk(root, followlinks=False):
    for name in directory_names + file_names:
        path = Path(directory, name)
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise SystemExit(f"symlink in source archive: {path.relative_to(root)}")
        if stat.S_ISREG(metadata.st_mode):
            if metadata.st_nlink != 1:
                raise SystemExit(f"hard-linked file in source archive: {path.relative_to(root)}")
        elif not stat.S_ISDIR(metadata.st_mode):
            raise SystemExit(f"special file in source archive: {path.relative_to(root)}")
PY
}

read_manifest_evidence_catalog() {
  HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" PYTHONHASHSEED=0 \
    /usr/bin/python3 -S -P - \
      "${tmp}/source-archive/${manifest}" \
      >"${tmp}/manifest-evidence.tsv" <<'PY' \
      || fail "cannot read immutable manifest evidence catalog"
import json
import re
import sys
from pathlib import Path


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


manifest_path = Path(sys.argv[1])
raw = manifest_path.read_bytes()
payload = json.loads(
    raw.decode("utf-8"),
    object_pairs_hook=reject_duplicate_keys,
    parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-finite {token}")),
)
canonical = (
    json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    )
    + "\n"
).encode("utf-8")
if raw != canonical:
    raise SystemExit("manifest is not canonical JSON")
evidence = payload.get("evidence_sha256")
if not isinstance(evidence, dict) or not evidence:
    raise SystemExit("manifest evidence_sha256 must be a nonempty object")
for relative, digest in sorted(evidence.items()):
    if (
        not isinstance(relative, str)
        or relative.startswith("/")
        or "\\" in relative
        or "\t" in relative
        or "\n" in relative
        or any(part in ("", ".", "..") for part in relative.split("/"))
    ):
        raise SystemExit(f"unsafe evidence path: {relative!r}")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise SystemExit(f"invalid evidence SHA-256: {relative}")
    print(f"{relative}\t{digest}")
PY

  {
    local path
    for path in "${required_manifest_evidence_paths[@]}"; do
      printf '%s\n' "${path}"
    done
  } | /usr/bin/sort >"${tmp}/expected-evidence-paths"
  /usr/bin/awk -F '\t' '{print $1}' "${tmp}/manifest-evidence.tsv" \
    >"${tmp}/actual-evidence-paths"
  /usr/bin/cmp -s "${tmp}/expected-evidence-paths" "${tmp}/actual-evidence-paths" \
    || fail "manifest evidence path catalog drift"
}

verify_manifest_evidence() {
  local path expected_digest actual_digest
  local index_mode index_object index_stage indexed
  local source_mode source_type source_object source_indexed
  local head_mode head_type head_object head_indexed
  while IFS=$'\t' read -r path expected_digest; do
    verify_regular_unaliased "${path}"
    read -r index_mode index_object index_stage indexed \
      < <(git_clean ls-files --stage -- "${path}") \
      || fail "cannot resolve evidence index identity: ${path}"
    read -r source_mode source_type source_object source_indexed \
      < <(git_clean ls-tree "${source_commit}" -- "${path}") \
      || fail "cannot resolve evidence source identity: ${path}"
    read -r head_mode head_type head_object head_indexed \
      < <(git_clean ls-tree "${head_oid}" -- "${path}") \
      || fail "cannot resolve evidence HEAD identity: ${path}"
    [[ "${index_mode}" == "${source_mode}" && "${head_mode}" == "${source_mode}" \
      && "${source_type}" == blob && "${head_type}" == blob \
      && "${index_stage}" == 0 && "${indexed}" == "${path}" \
      && "${source_indexed}" == "${path}" && "${head_indexed}" == "${path}" \
      && "${index_object}" == "${source_object}" \
      && "${head_object}" == "${source_object}" ]] \
      || fail "evidence source/HEAD/index Git identity drift: ${path}"
    [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
      || fail "nondefault evidence Git index flag: ${path}"
    /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${source_object}") \
      || fail "evidence worktree/source-commit byte drift: ${path}"
    actual_digest="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
    [[ "${actual_digest}" == "${expected_digest}" ]] \
      || fail "manifest evidence SHA-256 drift: ${path}"
  done <"${tmp}/manifest-evidence.tsv"
}

run_required_gate() {
  local path="$1" expected_marker="$2" label="$3"
  if ! "${path}" >"${tmp}/${label}.out" 2>"${tmp}/${label}.err"; then
    /usr/bin/cat "${tmp}/${label}.err" >&2
    fail "required ${label} gate failed"
  fi
  [[ ! -s "${tmp}/${label}.err" ]] || fail "required ${label} gate emitted stderr"
  [[ "$(/usr/bin/head -n 1 "${tmp}/${label}.out")" == "${expected_marker}" ]] \
    || fail "required ${label} gate marker drift"
  [[ "$(/usr/bin/awk -F= '$1 == "integration_status" {print $2}' \
      "${tmp}/${label}.out")" == "VALID_INTEGRATED" ]] \
    || fail "required ${label} gate is not VALID_INTEGRATED"
}

run_purpose_checker() {
  local output="$1" error="$2" hash_seed="$3"
  shift 3
  (
    cd "${tmp}/source-archive"
    HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" PYTHONHASHSEED="${hash_seed}" \
      /usr/bin/python3 -S -P "${tmp}/source-archive/${purpose_checker}" \
        --root "${tmp}/source-archive" "$@"
  ) >"${output}" 2>"${error}"
}

require_tsv_value() {
  local path="$1" key="$2" expected="$3" actual
  actual="$({
    /usr/bin/awk -F '\t' -v wanted="${key}" '
      $1 == wanted { count += 1; value = $2 }
      END {
        if (count != 1) exit 1
        print value
      }
    ' "${path}"
  })" || fail "checker result does not contain exactly one ${key} row"
  [[ "${actual}" == "${expected}" ]] \
    || fail "checker result ${key} drift: ${actual}"
}

verify_history_metadata
head_oid="$(git_clean rev-parse --verify 'HEAD^{commit}')" || fail "cannot resolve HEAD"
git_clean cat-file -e "${baseline_commit}^{commit}" || fail "cannot resolve frozen baseline"
git_clean merge-base --is-ancestor "${baseline_commit}" "${head_oid}" \
  || fail "frozen baseline is not an ancestor of HEAD"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)" ]] \
  || fail "worktree must be clean"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags are present"

source_candidates=()
mapfile -t source_candidates < <(
  git_clean log "${head_oid}" --diff-filter=A --format='%H' -- "${manifest}"
)
[[ "${#source_candidates[@]}" == 1 ]] \
  || fail "first-condition-output guard manifest must have exactly one add commit"
source_commit="${source_candidates[0]}"
raw_parent_headers="$(
  git_clean cat-file commit "${source_commit}" | /usr/bin/awk '
    BEGIN { in_headers = 1 }
    in_headers && $0 == "" { in_headers = 0 }
    in_headers && $1 == "parent" { print $2 }
  '
)"
[[ "${raw_parent_headers}" == "${baseline_commit}" ]] \
  || fail "raw source commit must have exactly the frozen baseline as parent"
git_clean merge-base --is-ancestor "${source_commit}" "${head_oid}" \
  || fail "source commit is not an ancestor of HEAD"
verify_descendant_integration_shape

{
  for path in "${packet_paths[@]}"; do
    printf 'A\t%s\n' "${path}"
  done
} | /usr/bin/sort >"${tmp}/expected-source-delta"
git_clean diff-tree --no-commit-id --no-renames --name-status -r "${source_commit}" \
  | /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-source-delta" \
  || fail "source commit is not the exact nine-path all-add packet"
git_clean diff --check "${baseline_commit}" "${source_commit}" \
  || fail "source packet fails git diff --check"

verify_packet_identity
run_required_gate "${custodian_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_SAMPLING_ATTEMPT_CUSTODIAN_V1_PACK" \
  "sampling-attempt-custodian-v1-pack"

materialize_source_archive
read_manifest_evidence_catalog
verify_manifest_evidence
verify_frozen_sha256 "manifest" "${frozen_manifest_sha256}" "${manifest}"
verify_frozen_sha256 "purpose checker" "${frozen_purpose_checker_sha256}" "${purpose_checker}"
verify_frozen_sha256 "expected result" "${frozen_expected_result_sha256}" "${expected_result}"
/usr/bin/chmod -R a-w "${tmp}/source-archive"

run_purpose_checker "${tmp}/normal-zero.out" "${tmp}/normal-zero.err" 0 \
  || { /usr/bin/cat "${tmp}/normal-zero.err" >&2; fail "normal checker failed"; }
run_purpose_checker "${tmp}/normal-alt.out" "${tmp}/normal-alt.err" 314159 \
  || { /usr/bin/cat "${tmp}/normal-alt.err" >&2; fail "alternate-hash normal checker failed"; }
run_purpose_checker "${tmp}/self-zero.out" "${tmp}/self-zero.err" 0 --self-test \
  || { /usr/bin/cat "${tmp}/self-zero.err" >&2; fail "self-test failed"; }
run_purpose_checker "${tmp}/self-alt.out" "${tmp}/self-alt.err" 314159 --self-test \
  || { /usr/bin/cat "${tmp}/self-alt.err" >&2; fail "alternate-hash self-test failed"; }
[[ ! -s "${tmp}/normal-zero.err" && ! -s "${tmp}/normal-alt.err" \
  && ! -s "${tmp}/self-zero.err" && ! -s "${tmp}/self-alt.err" ]] \
  || fail "purpose checker emitted stderr"
for checker_output in \
  "${tmp}/normal-zero.out" "${tmp}/normal-alt.out" \
  "${tmp}/self-zero.out" "${tmp}/self-alt.out"; do
  /usr/bin/cmp -s "${checker_output}" "${tmp}/source-archive/${expected_result}" \
    || fail "normal/self-test result differs from the frozen expected TSV"
done

require_tsv_value "${tmp}/normal-zero.out" decision \
  "SOURCE_PROFILE_PASS_BLOCKED_FAIL_CLOSED_EXTERNAL_ATOMIC_AUTHORITY_AND_NON_BYPASSABLE_OUTPUT_PATH_UNBOUND"
require_tsv_value "${tmp}/normal-zero.out" status \
  "LOCAL_PRE_OUTPUT_TUPLE_VALIDATION_ONLY_NO_LIVE_OUTPUT_PERMIT"
require_tsv_value "${tmp}/normal-zero.out" condition_output_authorized false
require_tsv_value "${tmp}/normal-zero.out" side_effects_unlocked NONE

[[ "$(git_clean rev-parse --verify 'HEAD^{commit}')" == "${head_oid}" ]] \
  || fail "HEAD changed while gate was running"
verify_history_metadata
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)" ]] \
  || fail "worktree changed while gate was running"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags appeared while gate was running"
verify_packet_identity
verify_manifest_evidence
verify_frozen_sha256 "manifest" "${frozen_manifest_sha256}" "${manifest}"
verify_frozen_sha256 "purpose checker" "${frozen_purpose_checker_sha256}" "${purpose_checker}"
verify_frozen_sha256 "expected result" "${frozen_expected_result_sha256}" "${expected_result}"

if [[ "${head_oid}" == "${source_commit}" ]]; then
  marker="BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_FIRST_CONDITION_OUTPUT_GUARD_V1_PACK"
  integration_status="BOUND_TO_HEAD"
else
  marker="VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_FIRST_CONDITION_OUTPUT_GUARD_V1_PACK"
  integration_status="VALID_INTEGRATED"
fi
printf '%s\n' "${marker}"
printf 'integration_status=%s\n' "${integration_status}"
printf 'decision=SOURCE_PROFILE_PASS_BLOCKED_FAIL_CLOSED_EXTERNAL_ATOMIC_AUTHORITY_AND_NON_BYPASSABLE_OUTPUT_PATH_UNBOUND\n'
printf 'status=LOCAL_PRE_OUTPUT_TUPLE_VALIDATION_ONLY_NO_LIVE_OUTPUT_PERMIT\n'
printf 'synthetic_only=true\n'
printf 'condition_output_authorized=false\n'
printf 'side_effects_unlocked=NONE\n'
printf 'head=%s\n' "${head_oid}"
printf 'source_commit=%s\n' "${source_commit}"
printf 'baseline_commit=%s\n' "${baseline_commit}"
printf 'sampling_attempt_custodian_v1_gate_status=VALID_INTEGRATED\n'
printf 'strict_s11_gate_execution=NOT_RUN_NON_DESCENDANT_STRICT_GATE_BY_DESIGN\n'
printf 'atomic_authority_s11_evidence_status=SYNTHETIC_HASH_PINNED_NOT_LIVE_AUTHORITY\n'
printf 'source_archive_validation=PASS\n'
printf 'normal_checker_status=PASS_EXPECTED_BYTES\n'
printf 'self_test_status=PASS_EXPECTED_BYTES\n'
printf 'manifest_sha256=%s\n' "${frozen_manifest_sha256}"
printf 'purpose_checker_sha256=%s\n' "${frozen_purpose_checker_sha256}"
printf 'expected_result_sha256=%s\n' "${frozen_expected_result_sha256}"
printf 'checker_output_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/normal-zero.out" | /usr/bin/awk '{print $1}')"
