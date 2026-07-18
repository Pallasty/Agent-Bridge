#!/usr/bin/env python3
"""Git-object-only independent audit of the frozen P8-A V2 proof result.

This program deliberately does not import, execute, or subprocess the P8-A
producer or its tests.  It reads only named Git blobs from the frozen P8-A
preprobe/result chain, independently recomputes the finite-binary64 selector
model, and preserves P8-A's non-scientific authority boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


BASE = Path(__file__).resolve().parent
AUDIT_NAME = "majorana_certificate_p8_selector_equivalence_independent_audit.py"
AUDIT_FIXTURE_NAME = "majorana_certificate_p8_selector_equivalence_independent_audit_fixture.json"
AUDIT_REPORT_NAME = "majorana_certificate_p8_selector_equivalence_independent_audit_report.json"
TEST_NAME = "test_majorana_certificate_p8_selector_equivalence_independent_audit.py"
AUDIT_RELATIVE_PATH = f"docs/research/fermion-frontier/{AUDIT_NAME}"
AUDIT_FIXTURE_RELATIVE_PATH = f"docs/research/fermion-frontier/{AUDIT_FIXTURE_NAME}"
AUDIT_REPORT_RELATIVE_PATH = f"docs/research/fermion-frontier/{AUDIT_REPORT_NAME}"
TEST_RELATIVE_PATH = f"docs/research/fermion-frontier/{TEST_NAME}"

# P8-A V2 is already frozen and pushed.  These values are audit inputs, not
# values derived from the current worktree.
P8_RESULT_COMMIT = "5cf53d73c4e375d9c8159cb7a742b4c22edd9622"
P8_PREPROBE_COMMIT = "adb89df8558a3db34dc757b0ce5f0273fa3ce238"
P8_DIRECT_PARENT_COMMIT = "c82e2443dfae07af17cb9108ccb344c2f0cbebba"

P8_ROOT = "docs/research/fermion-frontier/"
P8_REPORT_NAME = "majorana_certificate_p8_selector_equivalence_report.json"
P8_FIXTURE_NAME = "majorana_certificate_p8_selector_equivalence_fixture.json"
P8_POLICY_NAME = "majorana_certificate_p8_selector_equivalence_policy.json"
P8_MODULE_NAME = "majorana_certificate_p8_selector_equivalence.py"
P8_TEST_NAME = "test_majorana_certificate_p8_selector_equivalence.py"
P3_RUNNER_NAME = "majorana_certificate_p3/majorana_p3_runner.jl"
P6_RUNNER_NAME = "majorana_certificate_p6/majorana_p6_runner.jl"

P8_REPORT_PATH = P8_ROOT + P8_REPORT_NAME
D4_REPORT_NAME = "majorana_certificate_p7_d4_e_per_composite_probe_report.json"
D4_REPORT_PATH = P8_ROOT + D4_REPORT_NAME
P8_PREPROBE_CHANGED_PATHS = (
    P8_ROOT + P8_FIXTURE_NAME,
    P8_ROOT + P8_POLICY_NAME,
    P8_ROOT + P8_MODULE_NAME,
    P8_ROOT + P8_TEST_NAME,
)
AUDIT_PREPROBE_CHANGED_PATHS = (
    AUDIT_FIXTURE_RELATIVE_PATH,
    AUDIT_RELATIVE_PATH,
    TEST_RELATIVE_PATH,
)

P8_REPORT_SHA256 = "014148df4be0f1c234456a5d0a09fb84dc7cb25d91d6d67e0d7f5ff66e3bb97a"
P8_REPORT_SIZE_BYTES = 3668
P8_FIXTURE_CANONICAL_SHA256 = "fd3bdf6228b5645a7a15f4658e8aa2dd77ad1be530ef19ace1d2743a0021cb06"
P8_POLICY_SEMANTIC_SHA256 = "144a8882580a77b5638b0d3be54eb7c7b9024865b693d67f35dc61ea15d6adc5"
P8_SOURCE_FILES_CANONICAL_SHA256 = "b390e1865cc5622e120f63564d341e9297bca1f27e8b693f4be6d8651c3a4d6e"

# (path relative to P8_ROOT, raw SHA-256, raw byte size)
P8_SOURCE_ROWS = (
    (P8_FIXTURE_NAME, "aa43d6cffcc9f69eca84651ec3c46ad90271659de8c5e915d64d000daab729ab", 3931),
    (P8_MODULE_NAME, "0a6d4381be5c9a79294b670d34c9ae815b72adf02e7880bca17dd1f04c91d79b", 48084),
    (P3_RUNNER_NAME, "958de8886bb8e56cda26eb6c45029c7016e886caae26c598c7e6b5c595257fe2", 59318),
    (P6_RUNNER_NAME, "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c", 74471),
    (P8_TEST_NAME, "5ff4f676bc28c62e2f7bf5ec8436d1fd2a3f8e0bef0691e9671f3af2b1042591", 13422),
)
P8_POLICY_RAW_SHA256 = "f06ef2ed652a249c38e67fc93f6b6dc3a790504ac355f2dda92feb38eb4d038b"
P8_POLICY_SIZE_BYTES = 2936
D4_REPORT_SHA256 = "269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19"
D4_REPORT_SIZE_BYTES = 11822
AUDIT_FIXTURE_CANONICAL_SHA256 = "0289b0eb4d862151da6e5f2af10bdd48245461310ce630a4585d94952eeb4599"
AUDIT_CASE_IDS_SHA256 = "a68d10770999ff657534949e1fe325d7561b3e56aa583dcec681083607b00e3c"
AUDIT_REPORT_TYPE = "majorana_p8_b_independent_selector_audit_report_v1"
AUDIT_REPORT_STATUS = "VERIFIED_INDEPENDENT_P8_A_SELECTOR_EQUIVALENCE_AUDIT"

P8_D4_PROJECTION = {
    "certificate_eligible": False,
    "instrumented_kernel_custody": {
        "frozen_P6_function_slice_sha256": (
            "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
        ),
        "frozen_P6_runner_sha256": (
            "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
        ),
    },
    "report_type": "majorana_p7_step3_e768_max_lazy37_e_per_composite_report_d4_v2",
    "result_contract_eligible": False,
    "scientific_authority": "NONE",
}
P8_PREPROBE_LINEAGE = {
    "revision": "V2",
    "superseded_preprobe_commit": "f59eb88571384256a5e90c2a5745aa929b9153b7",
    "supersession_reason": "FROZEN_PREPROBE_VERIFICATION_LIFECYCLE_COVERAGE",
}

GRID_EXPONENT = 128
GRID_DENOMINATOR = 1 << GRID_EXPONENT
FRACTION_MASK = 0x000FFFFFFFFFFFFF
MAX_FINITE_ABS_BITS = 0x7FEFFFFFFFFFFFFF
P6_K37_ABS_BITS = 0x3DA0000000000000
MASK_MAX = (1 << 256) - 1
MAXIMUM_BIGINT_BITS = 2048


class AuditError(RuntimeError):
    """A closed failure of the non-scientific P8-B audit."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise AuditError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def loads_json(payload: bytes, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError(f"invalid JSON: {label}") from error


def _repo_root() -> Path:
    completed = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"),
        cwd=BASE,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AuditError("P8-B audit must run inside a git worktree")
    root = Path(completed.stdout.strip()).resolve()
    if BASE.resolve() != root / "docs" / "research" / "fermion-frontier":
        raise AuditError("P8-B audit repository location drift")
    return root


def _git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=_repo_root(),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AuditError(f"git command failed: {' '.join(arguments)}")
    return completed.stdout


def _git_text(*arguments: str) -> str:
    try:
        return _git_bytes(*arguments).decode("utf-8")
    except UnicodeDecodeError as error:
        raise AuditError(f"git command is not UTF-8: {' '.join(arguments)}") from error


def _require_commit_sha(value: str, label: str) -> str:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise AuditError(f"invalid {label} commit SHA")
    return value


def _git_blob_optional(commit: str, relative_path: str) -> bytes | None:
    _require_commit_sha(commit, "Git object")
    listing = _git_bytes("ls-tree", "-z", commit, "--", relative_path)
    if not listing:
        return None
    records = listing.split(b"\0")
    if records[-1] != b"" or len(records) != 2:
        raise AuditError("unexpected Git tree record count")
    record = records[0]
    metadata, separator, actual_path = record.partition(b"\t")
    if separator != b"\t" or actual_path != relative_path.encode("utf-8"):
        raise AuditError("Git tree path drift")
    fields = metadata.split(b" ")
    if len(fields) != 3 or fields[0] != b"100644" or fields[1] != b"blob":
        raise AuditError("Git object is not a regular blob")
    object_id = fields[2]
    if len(object_id) != 40 or any(character not in b"0123456789abcdef" for character in object_id):
        raise AuditError("invalid Git blob object ID")
    return _git_bytes("cat-file", "blob", object_id.decode("ascii"))


def _git_blob(commit: str, relative_path: str) -> bytes:
    body = _git_blob_optional(commit, relative_path)
    if body is None:
        raise AuditError(f"missing Git blob: {relative_path}")
    return body


def _git_blob_object_id(commit: str, relative_path: str) -> str:
    _require_commit_sha(commit, "Git object")
    listing = _git_bytes("ls-tree", "-z", commit, "--", relative_path)
    records = listing.split(b"\0")
    if not listing or records[-1] != b"" or len(records) != 2:
        raise AuditError(f"missing or malformed Git blob record: {relative_path}")
    metadata, separator, actual_path = records[0].partition(b"\t")
    if separator != b"\t" or actual_path != relative_path.encode("utf-8"):
        raise AuditError("Git blob object-ID path drift")
    fields = metadata.split(b" ")
    if len(fields) != 3 or fields[0] != b"100644" or fields[1] != b"blob":
        raise AuditError("Git blob object-ID mode drift")
    try:
        object_id = fields[2].decode("ascii")
    except UnicodeDecodeError as error:
        raise AuditError("Git blob object ID is not ASCII") from error
    if len(object_id) != 40 or any(character not in "0123456789abcdef" for character in object_id):
        raise AuditError("invalid Git blob object ID")
    return object_id


def _commit_parents(commit: str) -> tuple[str, ...]:
    _require_commit_sha(commit, "commit")
    fields = _git_text("rev-list", "--parents", "-n", "1", commit).split()
    if not fields or fields[0] != commit:
        raise AuditError("Git commit parent record drift")
    parents = tuple(fields[1:])
    if any(len(parent) != 40 for parent in parents):
        raise AuditError("malformed Git commit parent")
    return parents


def _require_sha1_commit(commit: str) -> None:
    if _git_text("rev-parse", "--show-object-format").strip() != "sha1":
        raise AuditError("P8-B audit requires a SHA-1 Git object format")
    if _git_text("cat-file", "-t", commit).strip() != "commit":
        raise AuditError("P8-B expected a Git commit object")


def _changed_paths(commit: str) -> tuple[str, ...]:
    _require_commit_sha(commit, "commit")
    return tuple(sorted(
        path for path in _git_text(
            "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", commit,
        ).splitlines() if path
    ))


def _status_paths() -> tuple[str, ...]:
    status = _git_text("status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    for line in status.splitlines():
        if len(line) < 4 or line[2] != " ":
            raise AuditError("unsupported git status record")
        paths.append(line[3:])
    return tuple(sorted(paths))


def _preprobe_staged_paths() -> tuple[str, ...]:
    status = _git_text("status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    for line in status.splitlines():
        if len(line) < 4 or line[:3] != "A  ":
            raise AuditError("P8-B preprobe requires final staged additions")
        paths.append(line[3:])
    return tuple(sorted(paths))


def _index_regular_blob(relative_path: str) -> bytes:
    listing = _git_bytes("ls-files", "-s", "--", relative_path)
    records = listing.splitlines()
    if len(records) != 1:
        raise AuditError(f"missing or ambiguous staged index entry: {relative_path}")
    metadata, separator, actual_path = records[0].partition(b"\t")
    if separator != b"\t" or actual_path != relative_path.encode("utf-8"):
        raise AuditError("staged index path drift")
    fields = metadata.split(b" ")
    if len(fields) != 3 or fields[0] != b"100644" or fields[2] != b"0":
        raise AuditError("staged index entry is not a regular stage-0 blob")
    try:
        object_id = fields[1].decode("ascii")
    except UnicodeDecodeError as error:
        raise AuditError("staged index blob ID is not ASCII") from error
    if len(object_id) != 40 or any(character not in "0123456789abcdef" for character in object_id):
        raise AuditError("invalid staged index blob ID")
    return _git_bytes("cat-file", "blob", object_id)


def _validate_preprobe_index_blobs() -> None:
    for name, path in (
        (AUDIT_FIXTURE_NAME, AUDIT_FIXTURE_RELATIVE_PATH),
        (AUDIT_NAME, AUDIT_RELATIVE_PATH),
        (TEST_NAME, TEST_RELATIVE_PATH),
    ):
        if _read_current_regular(name) != _index_regular_blob(path):
            raise AuditError(f"P8-B staged index blob differs from current bytes: {name}")


def _read_current_regular(name: str) -> bytes:
    path = BASE / name
    if not path.is_file() or path.is_symlink():
        raise AuditError(f"current P8-B audit blob is missing or non-regular: {name}")
    return path.read_bytes()


def _validate_audit_preprobe_commit(commit: str) -> None:
    _require_sha1_commit(commit)
    if _commit_parents(commit) != (P8_RESULT_COMMIT,):
        raise AuditError("P8-B audit preprobe parent or merge topology drift")
    if _changed_paths(commit) != tuple(sorted(AUDIT_PREPROBE_CHANGED_PATHS)):
        raise AuditError("P8-B audit preprobe changed-path set drift")
    if _git_blob_optional(commit, AUDIT_REPORT_RELATIVE_PATH) is not None:
        raise AuditError("P8-B audit preprobe already contains an audit report")
    for path in AUDIT_PREPROBE_CHANGED_PATHS:
        _git_blob(commit, path)


def _assert_current_audit_blobs(commit: str) -> None:
    for name, path in (
        (AUDIT_FIXTURE_NAME, AUDIT_FIXTURE_RELATIVE_PATH),
        (AUDIT_NAME, AUDIT_RELATIVE_PATH),
        (TEST_NAME, TEST_RELATIVE_PATH),
    ):
        if _read_current_regular(name) != _git_blob(commit, path):
            raise AuditError(f"current P8-B audit blob drift: {name}")


def _expected_p8_source_files() -> list[dict[str, Any]]:
    return [
        {"relative_path": path, "sha256": digest, "size_bytes": size}
        for path, digest, size in P8_SOURCE_ROWS
    ]


def _checked_blob(commit: str, relative_path: str, digest: str, size: int, label: str) -> bytes:
    body = _git_blob(commit, relative_path)
    if len(body) != size or sha256_bytes(body) != digest:
        raise AuditError(f"{label} raw blob identity drift")
    return body


def _validate_p8_object_lineage() -> None:
    for commit in (P8_DIRECT_PARENT_COMMIT, P8_PREPROBE_COMMIT, P8_RESULT_COMMIT):
        _require_sha1_commit(commit)
    if _commit_parents(P8_PREPROBE_COMMIT) != (P8_DIRECT_PARENT_COMMIT,):
        raise AuditError("P8-A preprobe parent or merge topology drift")
    if _commit_parents(P8_RESULT_COMMIT) != (P8_PREPROBE_COMMIT,):
        raise AuditError("P8-A result parent or merge topology drift")
    if _changed_paths(P8_PREPROBE_COMMIT) != tuple(sorted(P8_PREPROBE_CHANGED_PATHS)):
        raise AuditError("P8-A preprobe changed-path set drift")
    if _changed_paths(P8_RESULT_COMMIT) != (P8_REPORT_PATH,):
        raise AuditError("P8-A result changed-path set drift")
    if _git_blob_optional(P8_PREPROBE_COMMIT, P8_REPORT_PATH) is not None:
        raise AuditError("P8-A preprobe unexpectedly contains a result report")
    for path, digest, size in P8_SOURCE_ROWS:
        full_path = P8_ROOT + path
        preprobe_body = _checked_blob(P8_PREPROBE_COMMIT, full_path, digest, size, f"P8-A {path}")
        if path in {P8_FIXTURE_NAME, P8_MODULE_NAME, P8_TEST_NAME}:
            if _git_blob_object_id(P8_RESULT_COMMIT, full_path) != _git_blob_object_id(
                P8_PREPROBE_COMMIT, full_path,
            ) or _git_blob(P8_RESULT_COMMIT, full_path) != preprobe_body:
                raise AuditError(f"P8-A result changed frozen preprobe blob: {path}")
    if _git_blob_object_id(P8_RESULT_COMMIT, P8_ROOT + P3_RUNNER_NAME) != _git_blob_object_id(
        P8_PREPROBE_COMMIT, P8_ROOT + P3_RUNNER_NAME,
    ):
        raise AuditError("P8-A result changed inherited P3 blob")
    if _git_blob_object_id(P8_RESULT_COMMIT, P8_ROOT + P6_RUNNER_NAME) != _git_blob_object_id(
        P8_PREPROBE_COMMIT, P8_ROOT + P6_RUNNER_NAME,
    ):
        raise AuditError("P8-A result changed inherited P6 blob")


def _expected_proof_scope() -> dict[str, Any]:
    return {
        "P8_A_is_proof_only": True,
        "P8_A_does_not_execute_a_new_candidate": True,
        "P8_A_does_not_change_or_requalify_the_P7_candidate": True,
        "P8_A_proves_only_successful_selector_membership_and_selected_cost_total": True,
        "P8_A_resource_consumption_cap_paths_and_host_behavior_are_not_equated": True,
        "P8_A_does_not_establish_future_S0_admission": True,
        "P8_A_does_not_establish_a_step3_or_physical_result": True,
        "future_algorithm_change_requires_a_new_candidate_id_and_independent_preprobe": True,
    }


def _expected_selector_contract() -> dict[str, Any]:
    return {
        "P6_K37_abs_bits_hex": "3da0000000000000",
        "P6_rank_key": "(point_abs_ticks,abs_bits,unsigned_mask)",
        "abs_bits_mask_hex": "7fffffffffffffff",
        "all_costs_are_exact_nonnegative_BigInt": True,
        "all_selector_rows_have_unique_unsigned_masks": True,
        "binary64_domain": "finite_Float64_magnitude_bits_only",
        "bit_order_key": "(abs_bits,unsigned_mask)",
        "grid_denominator": str(GRID_DENOMINATOR),
        "grid_denominator_power_of_two_exponent": GRID_EXPONENT,
        "maximum_BigInt_bit_length": MAXIMUM_BIGINT_BITS,
        "maximum_finite_abs_bits_hex": "7fefffffffffffff",
        "point_abs_ticks": "ceil(2^128*abs(exact_finite_Float64))",
        "snapshot_is_finite_and_immutable_during_selection": True,
        "tier1_predicate": "abs_bits < P6_K37_abs_bits",
        "tier2_inclusion": "point_abs_ticks <= tier1_remaining_budget",
        "tier2_source": "same_original_immutable_snapshot",
    }


def _expected_source_contract() -> dict[str, Any]:
    return {
        "D4_frozen_P6_execute_slice_sha256": (
            "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
        ),
        "P3_point_abs_ticks_slice_sha256": (
            "51a2a2b7f9945fdc925f19519706bb0897397f191254ed55ba317f40e1acdec2"
        ),
        "P6_prepare_boundary_drop_slice_sha256": (
            "5f79beaf09dd9a1f04b44c3f9d30e331de717fb4887ee650a948c8b34da9bbf5"
        ),
        "P6_selector_closure_sha256": (
            "4c3bc76d4056fc503c589e17b0ba32c951cb1ba7ad562e7990295fd9fe25ec25"
        ),
        "P6_selector_constants_sha256": (
            "70a4e5c4aec5009348acf2102972ff0f219194f60a4934beb59f77cd85c8f9b7"
        ),
        "source_contract_is_static_and_not_a_runtime_performance_claim": True,
    }


def _expected_d4_parent_custody() -> dict[str, Any]:
    return {
        "result_commit_sha": P8_DIRECT_PARENT_COMMIT,
        "report_relative_path": D4_REPORT_NAME,
        "report_size_bytes": D4_REPORT_SIZE_BYTES,
        "report_sha256": D4_REPORT_SHA256,
        "projection": P8_D4_PROJECTION,
        "projection_sha256": "b89776eaed1261a2c0eff17ec660b212f0ca80151e46d8c9770eb2b946284fac",
    }


def _validate_d4_allowed_projection_from_git() -> dict[str, Any]:
    """Validate only D4's frozen identity and six allowed provenance fields.

    This leaf never forwards the D4 object to selector code and does not
    access observations, host/resource fields, markers, timing, candidate
    data, or any other suppressed D4 fields.
    """

    body = _checked_blob(
        P8_DIRECT_PARENT_COMMIT, D4_REPORT_PATH, D4_REPORT_SHA256, D4_REPORT_SIZE_BYTES,
        "frozen D4 report",
    )
    report = loads_json(body, "frozen D4 report")
    if not isinstance(report, dict):
        raise AuditError("frozen D4 report is not an object")
    custody = report.get("instrumented_kernel_custody")
    if not isinstance(custody, dict):
        raise AuditError("frozen D4 instrumented kernel custody is malformed")
    projection = {
        "report_type": report.get("report_type"),
        "scientific_authority": report.get("scientific_authority"),
        "certificate_eligible": report.get("certificate_eligible"),
        "result_contract_eligible": report.get("result_contract_eligible"),
        "instrumented_kernel_custody": {
            "frozen_P6_runner_sha256": custody.get("frozen_P6_runner_sha256"),
            "frozen_P6_function_slice_sha256": custody.get("frozen_P6_function_slice_sha256"),
        },
    }
    if projection != P8_D4_PROJECTION:
        raise AuditError("frozen D4 allowed projection drift")
    if canonical_sha256(projection) != "b89776eaed1261a2c0eff17ec660b212f0ca80151e46d8c9770eb2b946284fac":
        raise AuditError("frozen D4 allowed projection hash drift")
    return projection


def _validate_p8_fixture(fixture: Mapping[str, Any]) -> None:
    if canonical_sha256(fixture) != P8_FIXTURE_CANONICAL_SHA256:
        raise AuditError("P8-A fixture canonical identity drift")
    expected_keys = {
        "D4_parent_custody",
        "authority_exclusions",
        "certificate_eligible",
        "direct_parent_commit",
        "fixture_id",
        "preprobe_lineage",
        "proof_scope",
        "result_contract_eligible",
        "schema_version",
        "scientific_authority",
        "selector_contract",
        "source_contract",
        "synthetic_differential_domain",
    }
    if set(fixture) != expected_keys:
        raise AuditError("P8-A fixture key set drift")
    if (
        fixture.get("D4_parent_custody") != _expected_d4_parent_custody()
        or fixture.get("certificate_eligible") is not False
        or fixture.get("direct_parent_commit") != P8_DIRECT_PARENT_COMMIT
        or fixture.get("fixture_id") != "MAJORANA-P8-A-FINITE-BINARY64-SELECTOR-EQUIVALENCE-V2"
        or fixture.get("preprobe_lineage") != P8_PREPROBE_LINEAGE
        or fixture.get("proof_scope") != _expected_proof_scope()
        or fixture.get("result_contract_eligible") is not False
        or fixture.get("schema_version") != 1
        or fixture.get("scientific_authority") != "NONE"
        or fixture.get("selector_contract") != _expected_selector_contract()
        or fixture.get("source_contract") != _expected_source_contract()
    ):
        raise AuditError("P8-A fixture semantic drift")
    if fixture.get("authority_exclusions") != [
        "P8_A_does_not_identify_a_D4_interruption_cause_or_active_composite",
        "P8_A_does_not_use_D4_observation_or_host_fields_as_an_input",
        "P8_A_does_not_establish_resource_feasibility_or_a_resource_no_go",
        "P8_A_does_not_establish_S0_admission",
        "P8_A_does_not_establish_a_step3_certificate_or_three_step_error_bound",
        "P8_A_does_not_make_a_performance_or_physical_claim",
    ]:
        raise AuditError("P8-A fixture authority exclusions drift")
    if fixture.get("synthetic_differential_domain") != {
        "boundary_abs_bits_hex": [
            "0000000000000000", "0000000000000001", "000fffffffffffff",
            "0010000000000000", "37efffffffffffff", "37f0000000000000",
            "37f0000000000001", "3d9fffffffffffff", "3da0000000000000",
            "3da0000000000001", "7fefffffffffffff",
        ],
        "maximum_snapshot_rows": 3,
        "must_compare_full_domain_tiered_and_bit_order_implementations": True,
        "must_cover_zero_subnormal_normal_threshold_ties_and_maximum": True,
    }:
        raise AuditError("P8-A fixture synthetic domain drift")


def _validate_p8_policy(policy: Mapping[str, Any]) -> None:
    if sha256_bytes(canonical_bytes({key: value for key, value in policy.items() if key != "source_files"})) != P8_POLICY_SEMANTIC_SHA256:
        raise AuditError("P8-A policy semantic identity drift")
    source_files = policy.get("source_files")
    if source_files != _expected_p8_source_files():
        raise AuditError("P8-A policy source pin drift")
    if canonical_sha256(source_files) != P8_SOURCE_FILES_CANONICAL_SHA256:
        raise AuditError("P8-A policy source pin canonical identity drift")


def _audit_proof_scope() -> dict[str, Any]:
    return {
        "P8_B_is_an_independent_Git_object_only_audit": True,
        "P8_B_does_not_import_or_execute_the_P8_A_producer": True,
        "P8_B_does_not_execute_or_change_the_P7_candidate": True,
        "P8_B_compares_only_selector_membership_and_selected_cost_total": True,
        "P8_B_does_not_establish_resource_cap_host_or_performance_equivalence": True,
        "P8_B_does_not_establish_a_D4_cause_S0_step3_or_physical_result": True,
    }


def _independent_schedule_contract() -> dict[str, Any]:
    return {
        "boundary_abs_bits_hex": [
            "0000000000000000", "0000000000000001", "000fffffffffffff",
            "0010000000000000", "37efffffffffffff", "37f0000000000000",
            "37f0000000000001", "3d9fffffffffffff", "3da0000000000000",
            "3da0000000000001", "7fefffffffffffff",
        ],
        "base_budget_rules": [
            "zero",
            "full_prefix_costs",
            "positive_full_prefix_costs_minus_one",
        ],
        "case_id_template": "audit-n{cardinality}-c{ordinal}-{input_label}-b{budget}",
        "expected_case_count": 4026,
        "expected_case_ids_sha256": AUDIT_CASE_IDS_SHA256,
        "input_orders": ["forward", "reverse"],
        "mask_stride": 19,
        "maximum_snapshot_rows": 3,
        "snapshot_enumeration": "multiset_combinations_with_replacement",
        "three_row_supplement": "full_selected_cost_total_plus_one_except_all_zero_snapshot",
    }


def _expected_audit_fixture() -> dict[str, Any]:
    return {
        "audit_id": "MAJORANA-P8-B-INDEPENDENT-SELECTOR-AUDIT-V1",
        "independent_differential_schedule": _independent_schedule_contract(),
        "proof_scope": _audit_proof_scope(),
        "schema_version": 1,
        "target_object_manifest": {
            "P8_A_fixture_canonical_sha256": P8_FIXTURE_CANONICAL_SHA256,
            "P8_A_policy_semantic_sha256": P8_POLICY_SEMANTIC_SHA256,
            "P8_A_preprobe_commit": P8_PREPROBE_COMMIT,
            "P8_A_report_case_ids_sha256": "1eb936034258f16513b4f1494026386a3e3a2219145f1158847851c3ee0ceea6",
            "P8_A_report_sha256": P8_REPORT_SHA256,
            "P8_A_report_size_bytes": P8_REPORT_SIZE_BYTES,
            "P8_A_result_commit": P8_RESULT_COMMIT,
            "P8_A_source_files_canonical_sha256": P8_SOURCE_FILES_CANONICAL_SHA256,
        },
    }


def _load_current_audit_fixture() -> dict[str, Any]:
    body = _read_current_regular(AUDIT_FIXTURE_NAME)
    value = loads_json(body, AUDIT_FIXTURE_NAME)
    if not isinstance(value, dict):
        raise AuditError("P8-B audit fixture is not an object")
    if canonical_bytes(value) != body:
        raise AuditError("P8-B audit fixture is not canonical JSON")
    return value


def _validate_audit_fixture(fixture: Mapping[str, Any]) -> None:
    if dict(fixture) != _expected_audit_fixture():
        raise AuditError("P8-B audit fixture schema or semantic content drift")
    if canonical_sha256(fixture) != AUDIT_FIXTURE_CANONICAL_SHA256:
        raise AuditError("P8-B audit fixture canonical identity drift")


@dataclass(frozen=True)
class AuditRow:
    abs_bits: int
    mask: int


@dataclass(frozen=True)
class AuditRankedRow:
    row: AuditRow
    point_cost: int


@dataclass(frozen=True)
class AuditSelection:
    ordered_rows: tuple[AuditRankedRow, ...]
    remaining_budget: int

    @property
    def membership(self) -> frozenset[int]:
        return frozenset(item.row.mask for item in self.ordered_rows)

    @property
    def selected_cost_total(self) -> int:
        return sum(item.point_cost for item in self.ordered_rows)


def _require_int(value: Any, label: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise AuditError(f"invalid {label}")
    return value


def _validate_rows(rows: Iterable[AuditRow]) -> tuple[AuditRow, ...]:
    materialized = tuple(rows)
    masks: set[int] = set()
    for row in materialized:
        if not isinstance(row, AuditRow):
            raise AuditError("audit selector row type drift")
        _require_int(row.abs_bits, "finite binary64 magnitude bits", 0, MAX_FINITE_ABS_BITS)
        _require_int(row.mask, "unsigned selector mask", 0, MASK_MAX)
        if row.mask in masks:
            raise AuditError("duplicate audit selector mask")
        masks.add(row.mask)
    return materialized


def _finite_components(abs_bits: int) -> tuple[int, int]:
    _require_int(abs_bits, "finite binary64 magnitude bits", 0, MAX_FINITE_ABS_BITS)
    exponent_bits = (abs_bits >> 52) & 0x7FF
    fraction_bits = abs_bits & FRACTION_MASK
    if exponent_bits == 0:
        return fraction_bits, -1074
    return (1 << 52) | fraction_bits, exponent_bits - 1023 - 52


def independent_point_abs_ticks(abs_bits: int) -> int:
    """Pure-integer reconstruction of ceil(2^128 * |finite binary64|)."""

    significand, exponent = _finite_components(abs_bits)
    if significand == 0:
        return 0
    shift = exponent + GRID_EXPONENT
    if shift >= 0:
        result = significand << shift
    else:
        divisor = 1 << (-shift)
        result = (significand + divisor - 1) // divisor
    if result.bit_length() > MAXIMUM_BIGINT_BITS:
        raise AuditError("independent point cost exceeds frozen BigInt bound")
    return result


def _exact_abs_fraction(abs_bits: int) -> Fraction:
    significand, exponent = _finite_components(abs_bits)
    if significand == 0:
        return Fraction(0, 1)
    return Fraction(significand << exponent, 1) if exponent >= 0 else Fraction(
        significand, 1 << (-exponent),
    )


def _rank_key(item: AuditRankedRow) -> tuple[int, int, int]:
    return item.point_cost, item.row.abs_bits, item.row.mask


def _bit_key(row: AuditRow) -> tuple[int, int]:
    return row.abs_bits, row.mask


def _affordable_prefix(rows: Sequence[AuditRankedRow], available: int) -> AuditSelection:
    remaining = _require_int(available, "audit selector budget", 0, (1 << 4096) - 1)
    selected: list[AuditRankedRow] = []
    for item in rows:
        if item.point_cost > remaining:
            break
        selected.append(item)
        remaining -= item.point_cost
    return AuditSelection(tuple(selected), remaining)


def full_domain_selection(rows: Iterable[AuditRow], available: int) -> AuditSelection:
    ranked = [
        AuditRankedRow(row, independent_point_abs_ticks(row.abs_bits))
        for row in _validate_rows(rows)
    ]
    ranked.sort(key=_rank_key)
    return _affordable_prefix(ranked, available)


def tiered_selection(rows: Iterable[AuditRow], available: int) -> AuditSelection:
    materialized = _validate_rows(rows)
    remaining = _require_int(available, "audit selector budget", 0, (1 << 4096) - 1)
    tier1 = [
        AuditRankedRow(row, independent_point_abs_ticks(row.abs_bits))
        for row in materialized if row.abs_bits < P6_K37_ABS_BITS
    ]
    tier1.sort(key=_rank_key)
    first = _affordable_prefix(tier1, remaining)
    selected = list(first.ordered_rows)
    if len(first.ordered_rows) != len(tier1) or first.remaining_budget == 0:
        return AuditSelection(tuple(selected), first.remaining_budget)
    tier2 = [
        AuditRankedRow(row, independent_point_abs_ticks(row.abs_bits))
        for row in materialized
        if row.abs_bits >= P6_K37_ABS_BITS
        and independent_point_abs_ticks(row.abs_bits) <= first.remaining_budget
    ]
    tier2.sort(key=_rank_key)
    second = _affordable_prefix(tier2, first.remaining_budget)
    selected.extend(second.ordered_rows)
    return AuditSelection(tuple(selected), second.remaining_budget)


def bit_order_selection(rows: Iterable[AuditRow], available: int) -> AuditSelection:
    remaining = _require_int(available, "audit selector budget", 0, (1 << 4096) - 1)
    selected: list[AuditRankedRow] = []
    for row in sorted(_validate_rows(rows), key=_bit_key):
        cost = independent_point_abs_ticks(row.abs_bits)
        if cost > remaining:
            break
        selected.append(AuditRankedRow(row, cost))
        remaining -= cost
    return AuditSelection(tuple(selected), remaining)


def _selection_semantics(selection: AuditSelection) -> tuple[frozenset[int], int]:
    return selection.membership, selection.selected_cost_total


def _parse_u64_hex(value: Any, label: str) -> int:
    if not isinstance(value, str) or len(value) != 16:
        raise AuditError(f"invalid {label} hexadecimal magnitude")
    try:
        parsed = int(value, 16)
    except ValueError as error:
        raise AuditError(f"invalid {label} hexadecimal magnitude") from error
    if f"{parsed:016x}" != value.lower():
        raise AuditError(f"noncanonical {label} hexadecimal magnitude")
    return parsed


def _audit_boundary_bits(fixture: Mapping[str, Any]) -> tuple[int, ...]:
    schedule = fixture["independent_differential_schedule"]
    values = schedule["boundary_abs_bits_hex"]
    if not isinstance(values, list) or not values:
        raise AuditError("empty P8-B independent boundary domain")
    parsed = tuple(_parse_u64_hex(value, "P8-B boundary") for value in values)
    if tuple(sorted(parsed)) != parsed or len(set(parsed)) != len(parsed):
        raise AuditError("P8-B independent boundary ordering drift")
    required = {
        0,
        1,
        FRACTION_MASK,
        1 << 52,
        0x37EFFFFFFFFFFFFF,
        0x37F0000000000000,
        0x37F0000000000001,
        P6_K37_ABS_BITS - 1,
        P6_K37_ABS_BITS,
        P6_K37_ABS_BITS + 1,
        MAX_FINITE_ABS_BITS,
    }
    if set(parsed) != required:
        raise AuditError("P8-B independent boundary coverage drift")
    return parsed


def _independent_cases(fixture: Mapping[str, Any]) -> tuple[tuple[str, tuple[AuditRow, ...], int], ...]:
    schedule = fixture["independent_differential_schedule"]
    values = _audit_boundary_bits(fixture)
    if schedule["maximum_snapshot_rows"] != 3 or schedule["mask_stride"] != 19:
        raise AuditError("P8-B independent schedule cardinality or mask stride drift")
    cases: list[tuple[str, tuple[AuditRow, ...], int]] = []
    for cardinality in range(1, schedule["maximum_snapshot_rows"] + 1):
        for ordinal, combination in enumerate(combinations_with_replacement(values, cardinality)):
            rows = tuple(
                AuditRow(abs_bits=value, mask=(cardinality - index) * schedule["mask_stride"] + ordinal)
                for index, value in enumerate(combination)
            )
            complete = full_domain_selection(
                rows, sum(independent_point_abs_ticks(row.abs_bits) for row in rows),
            )
            prefix = 0
            budgets = {0}
            for item in complete.ordered_rows:
                prefix += item.point_cost
                budgets.add(prefix)
                if prefix > 0:
                    budgets.add(prefix - 1)
            if cardinality == 3 and any(row.abs_bits != 0 for row in rows):
                budgets.add(complete.selected_cost_total + 1)
            for input_label, input_rows in (
                ("forward", rows),
                ("reverse", tuple(reversed(rows))),
            ):
                for budget in sorted(budgets):
                    cases.append((
                        f"audit-n{cardinality}-c{ordinal}-{input_label}-b{budget}",
                        input_rows,
                        budget,
                    ))
    return tuple(cases)


def _prove_equivalence(
    reference: Callable[[Iterable[AuditRow], int], AuditSelection],
    candidate: Callable[[Iterable[AuditRow], int], AuditSelection],
    cases: Iterable[tuple[str, tuple[AuditRow, ...], int]],
    *,
    require_rank_trace: bool,
) -> int:
    count = 0
    for case_id, rows, budget in cases:
        expected = reference(rows, budget)
        observed = candidate(rows, budget)
        if _selection_semantics(expected) != _selection_semantics(observed):
            raise AuditError(f"independent selector semantic mismatch at {case_id}")
        if require_rank_trace and expected != observed:
            raise AuditError(f"independent selector rank trace mismatch at {case_id}")
        count += 1
    if count == 0:
        raise AuditError("empty P8-B independent selector schedule")
    return count


def _independent_monotonicity() -> dict[str, Any]:
    transitions = 0
    previous_end: int | None = None
    for exponent_bits in range(0, 0x7FF):
        start = 0 if exponent_bits == 0 else exponent_bits << 52
        end = (exponent_bits << 52) | FRACTION_MASK
        low_significand, low_exponent = _finite_components(start)
        high_significand, high_exponent = _finite_components(end)
        if low_significand > high_significand or low_exponent != high_exponent:
            raise AuditError("independent binary64 intra-binade order drift")
        if previous_end is not None:
            if not _exact_abs_fraction(previous_end) < _exact_abs_fraction(start):
                raise AuditError("independent binary64 binade boundary order drift")
            if independent_point_abs_ticks(previous_end) > independent_point_abs_ticks(start):
                raise AuditError("independent binary64 point-cost monotonicity drift")
            transitions += 1
        previous_end = end
    if previous_end != MAX_FINITE_ABS_BITS or transitions != 2046:
        raise AuditError("independent binary64 binade coverage drift")
    return {
        "adjacent_binade_transition_count": transitions,
        "all_2047_finite_binary64_binades_symbolically_checked": True,
        "intra_binade_significand_order_is_exact_integer_order": True,
        "point_cost_is_ceil_of_the_exact_nonnegative_grid_scaled_magnitude": True,
    }


def _independent_boundary_facts(fixture: Mapping[str, Any]) -> dict[str, Any]:
    values = _audit_boundary_bits(fixture)
    costs = {value: independent_point_abs_ticks(value) for value in values}
    if costs[0] != 0 or costs[1] != 1 or costs[FRACTION_MASK] != 1:
        raise AuditError("independent zero or subnormal boundary fact drift")
    if [
        costs[0x37EFFFFFFFFFFFFF],
        costs[0x37F0000000000000],
        costs[0x37F0000000000001],
    ] != [1, 1, 2]:
        raise AuditError("independent ceil-grid transition fact drift")
    if costs[P6_K37_ABS_BITS] != 1 << 91:
        raise AuditError("independent K37 cost fact drift")
    if costs[P6_K37_ABS_BITS - 1] >= costs[P6_K37_ABS_BITS]:
        raise AuditError("independent K37 boundary fact drift")
    if costs[MAX_FINITE_ABS_BITS] != (1 << 1152) - (1 << 1099):
        raise AuditError("independent maximum finite cost fact drift")
    if costs[MAX_FINITE_ABS_BITS].bit_length() != 1152:
        raise AuditError("independent maximum finite bit length drift")
    return {
        "K37_cost": str(costs[P6_K37_ABS_BITS]),
        "K37_minus_one_cost": str(costs[P6_K37_ABS_BITS - 1]),
        "ceil_grid_first_integer_transition_costs": ["1", "1", "2"],
        "maximum_finite_cost": str(costs[MAX_FINITE_ABS_BITS]),
        "maximum_finite_cost_bit_length": 1152,
        "nonzero_subnormal_cost": "1",
        "signed_zero_is_ranked_by_abs_bits_zero_and_mask_only": True,
    }


def build_independent_selector_proof(fixture: Mapping[str, Any]) -> dict[str, Any]:
    _validate_audit_fixture(fixture)
    cases = _independent_cases(fixture)
    case_ids = [case[0] for case in cases]
    if len(cases) != fixture["independent_differential_schedule"]["expected_case_count"]:
        raise AuditError("P8-B independent case count drift")
    if canonical_sha256(case_ids) != fixture["independent_differential_schedule"]["expected_case_ids_sha256"]:
        raise AuditError("P8-B independent case-ID hash drift")
    full_tiered = _prove_equivalence(
        full_domain_selection, tiered_selection, cases, require_rank_trace=False,
    )
    full_bit = _prove_equivalence(
        full_domain_selection, bit_order_selection, cases, require_rank_trace=False,
    )
    tiered_trace = _prove_equivalence(
        full_domain_selection, tiered_selection, cases, require_rank_trace=True,
    )
    bit_trace = _prove_equivalence(
        full_domain_selection, bit_order_selection, cases, require_rank_trace=True,
    )
    return {
        "boundary_facts": _independent_boundary_facts(fixture),
        "case_count": len(cases),
        "case_ids_sha256": canonical_sha256(case_ids),
        "full_domain_equals_bit_order_membership_and_cost_total_case_count": full_bit,
        "full_domain_equals_tiered_membership_and_cost_total_case_count": full_tiered,
        "internal_canonical_rank_trace_check_case_counts": {
            "bit_order": bit_trace,
            "tiered": tiered_trace,
        },
        "internal_rank_trace_is_not_P6_selected_costs_Dict_iteration_semantics": True,
        "monotonicity_check": _independent_monotonicity(),
        "selector_semantics": "membership_and_selected_cost_total_only",
    }


def _load_target_p8_objects() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _validate_p8_object_lineage()
    _validate_d4_allowed_projection_from_git()
    fixture_body = _checked_blob(
        P8_PREPROBE_COMMIT, P8_ROOT + P8_FIXTURE_NAME, P8_SOURCE_ROWS[0][1], P8_SOURCE_ROWS[0][2],
        "P8-A fixture",
    )
    policy_body = _checked_blob(
        P8_PREPROBE_COMMIT, P8_ROOT + P8_POLICY_NAME, P8_POLICY_RAW_SHA256, P8_POLICY_SIZE_BYTES,
        "P8-A policy",
    )
    report_body = _checked_blob(
        P8_RESULT_COMMIT, P8_REPORT_PATH, P8_REPORT_SHA256, P8_REPORT_SIZE_BYTES,
        "P8-A result report",
    )
    fixture = loads_json(fixture_body, "frozen P8-A fixture")
    policy = loads_json(policy_body, "frozen P8-A policy")
    report = loads_json(report_body, "frozen P8-A result report")
    if not isinstance(fixture, dict) or not isinstance(policy, dict) or not isinstance(report, dict):
        raise AuditError("frozen P8-A JSON object type drift")
    if canonical_bytes(report) != report_body:
        raise AuditError("P8-A result report is not canonical JSON")
    _validate_p8_fixture(fixture)
    _validate_p8_policy(policy)
    return fixture, policy, report


def _target_preprobe_source_summary(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fixture_sha256": P8_SOURCE_ROWS[0][1],
        "policy_sha256": P8_POLICY_RAW_SHA256,
        "source_files_canonical_sha256": canonical_sha256(policy["source_files"]),
    }


def _validate_target_p8_report(
    report: Mapping[str, Any], policy: Mapping[str, Any], independent_proof: Mapping[str, Any],
) -> None:
    expected_keys = {
        "D4_parent_projection",
        "S0_admission_status",
        "certificate_eligible",
        "fixture_id",
        "policy_id",
        "preprobe_commit",
        "preprobe_lineage",
        "preprobe_source_summary",
        "proof",
        "report_type",
        "result_contract_eligible",
        "scientific_authority",
        "status",
    }
    if set(report) != expected_keys:
        raise AuditError("P8-A result report key set drift")
    if (
        report.get("D4_parent_projection") != P8_D4_PROJECTION
        or report.get("S0_admission_status") != "NOT_ESTABLISHED_BY_P8_A_PROOF_ONLY"
        or report.get("certificate_eligible") is not False
        or report.get("fixture_id") != "MAJORANA-P8-A-FINITE-BINARY64-SELECTOR-EQUIVALENCE-V2"
        or report.get("policy_id") != "MAJORANA-P8-A-FINITE-BINARY64-SELECTOR-EQUIVALENCE-V2"
        or report.get("preprobe_commit") != P8_PREPROBE_COMMIT
        or report.get("preprobe_lineage") != P8_PREPROBE_LINEAGE
        or report.get("preprobe_source_summary") != _target_preprobe_source_summary(policy)
        or report.get("report_type") != "majorana_p8_a_selector_bit_order_equivalence_report_v2"
        or report.get("result_contract_eligible") is not False
        or report.get("scientific_authority") != "NONE"
        or report.get("status") != "VERIFIED_CONDITIONAL_P8_A_SELECTOR_EQUIVALENCE"
    ):
        raise AuditError("P8-A result report authority or provenance drift")
    proof = report.get("proof")
    if not isinstance(proof, dict):
        raise AuditError("P8-A result proof is not an object")
    expected_proof_keys = {
        "assumptions", "boundary_facts", "differential_witness", "lemma", "monotonicity_check",
        "nonclaims", "proof_status",
    }
    if set(proof) != expected_proof_keys:
        raise AuditError("P8-A result proof key set drift")
    if proof.get("boundary_facts") != independent_proof["boundary_facts"]:
        raise AuditError("P8-A result boundary facts differ from independent reconstruction")
    if proof.get("monotonicity_check") != independent_proof["monotonicity_check"]:
        raise AuditError("P8-A result monotonicity witness differs from independent reconstruction")
    if proof.get("assumptions") != [
        "finite_immutable_snapshot_with_unique_unsigned_masks",
        "P3_exact_point_abs_ticks_and_no_BigInt_cap_exception",
        "same_nonnegative_BigInt_available_budget_and_same_P6_K37_threshold",
        "P6_rank_key_is_point_cost_then_abs_bits_then_unsigned_mask",
        "tier2_rescans_the_same_snapshot_and_includes_every_cost_not_exceeding_tier1_remaining_budget",
    ]:
        raise AuditError("P8-A result assumption list drift")
    if proof.get("lemma") != {
        "finite_binary64_abs_bits_order_implies_non_decreasing_P3_point_cost": True,
        "tier1_is_an_initial_segment_of_the_full_P6_rank_order": True,
        "tiered_and_full_domain_successful_selection_membership_and_cost_total_are_equal": True,
        "bit_order_and_full_domain_successful_selection_membership_and_cost_total_are_equal": True,
    }:
        raise AuditError("P8-A result lemma drift")
    if proof.get("nonclaims") != [
        "no_resource_consumption_equivalence",
        "no_cap_path_equivalence",
        "no_host_or_performance_claim",
        "no_D4_interruption_cause_inference",
        "no_S0_or_step3_scientific_claim",
    ] or proof.get("proof_status") != "VERIFIED_CONDITIONAL_P8_A_SELECTOR_EQUIVALENCE":
        raise AuditError("P8-A result nonclaim boundary drift")
    receipt = proof.get("differential_witness")
    if receipt != {
        "case_count": 4026,
        "case_ids_sha256": "1eb936034258f16513b4f1494026386a3e3a2219145f1158847851c3ee0ceea6",
        "full_domain_equals_P6_tiered_membership_and_cost_total_case_count": 4026,
        "full_domain_equals_bit_order_membership_and_cost_total_case_count": 4026,
        "internal_canonical_rank_trace_check_case_counts": {"P6_tiered": 4026, "bit_order": 4026},
        "internal_rank_trace_is_not_P6_selected_costs_Dict_iteration_semantics": True,
    }:
        raise AuditError("P8-A result differential receipt drift")


def _audit_report_body(audit_preprobe_commit: str) -> dict[str, Any]:
    _validate_audit_preprobe_commit(audit_preprobe_commit)
    _assert_current_audit_blobs(audit_preprobe_commit)
    fixture = _load_current_audit_fixture()
    _validate_audit_fixture(fixture)
    independent_proof = build_independent_selector_proof(fixture)
    _, policy, target_report = _load_target_p8_objects()
    _validate_target_p8_report(target_report, policy, independent_proof)
    return {
        "audit_fixture_canonical_sha256": AUDIT_FIXTURE_CANONICAL_SHA256,
        "audit_preprobe_commit": audit_preprobe_commit,
        "certificate_eligible": False,
        "independent_verification": independent_proof,
        "proof_scope": _audit_proof_scope(),
        "report_type": AUDIT_REPORT_TYPE,
        "result_contract_eligible": False,
        "scientific_authority": "NONE",
        "status": AUDIT_REPORT_STATUS,
        "target_p8_a": {
            "preprobe_commit": P8_PREPROBE_COMMIT,
            "result_commit": P8_RESULT_COMMIT,
            "result_report_case_ids_sha256": (
                "1eb936034258f16513b4f1494026386a3e3a2219145f1158847851c3ee0ceea6"
            ),
            "result_report_sha256": P8_REPORT_SHA256,
        },
        "target_report_differential_receipt_is_not_claimed_to_be_the_P8_B_schedule": True,
    }


def _write_canonical_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise AuditError("P8-B audit report already exists")
    payload = canonical_bytes(value)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        os.unlink(temporary)
    except FileExistsError as error:
        raise AuditError("P8-B audit report or temporary path already exists") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _validate_preprobe_worktree() -> None:
    if _git_text("rev-parse", "HEAD").strip() != P8_RESULT_COMMIT:
        raise AuditError("P8-B preprobe must start from the frozen P8-A result")
    if _preprobe_staged_paths() != tuple(sorted(AUDIT_PREPROBE_CHANGED_PATHS)):
        raise AuditError("P8-B preprobe changed-path set drift")
    _validate_preprobe_index_blobs()
    report = BASE / AUDIT_REPORT_NAME
    if report.exists() or report.is_symlink():
        raise AuditError("P8-B audit report exists before the preprobe commit")


def verify_preprobe() -> dict[str, Any]:
    fixture = _load_current_audit_fixture()
    _validate_audit_fixture(fixture)
    _load_target_p8_objects()
    head = _git_text("rev-parse", "HEAD").strip()
    if head == P8_RESULT_COMMIT:
        _validate_preprobe_worktree()
    else:
        if _status_paths():
            raise AuditError("frozen P8-B preprobe worktree must be clean")
        _validate_audit_preprobe_commit(head)
        _assert_current_audit_blobs(head)
        report = BASE / AUDIT_REPORT_NAME
        if report.exists() or report.is_symlink():
            raise AuditError("P8-B audit report exists before frozen-preprobe verification")
    return {
        "audit_id": fixture["audit_id"],
        "direct_parent_commit": P8_RESULT_COMMIT,
        "status": "VERIFIED_P8_B_INDEPENDENT_AUDIT_PREPROBE",
    }


def _validate_audit_result_commit(
    result_commit: str, audit_preprobe_commit: str, report_body: bytes,
) -> None:
    _require_sha1_commit(result_commit)
    if _commit_parents(result_commit) != (audit_preprobe_commit,):
        raise AuditError("P8-B audit result parent or merge topology drift")
    if _changed_paths(result_commit) != (AUDIT_REPORT_RELATIVE_PATH,):
        raise AuditError("P8-B audit result changed-path set drift")
    for path in AUDIT_PREPROBE_CHANGED_PATHS:
        if _git_blob_object_id(result_commit, path) != _git_blob_object_id(audit_preprobe_commit, path):
            raise AuditError(f"P8-B audit result changed frozen preprobe blob: {path}")
    if _git_blob(result_commit, AUDIT_REPORT_RELATIVE_PATH) != report_body:
        raise AuditError("P8-B current audit report differs from result Git blob")


def validate_audit_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from_disk = report is None
    raw = b""
    if report is None:
        raw = _read_current_regular(AUDIT_REPORT_NAME)
        value = loads_json(raw, AUDIT_REPORT_NAME)
        if not isinstance(value, dict):
            raise AuditError("P8-B audit report is not an object")
        report = value
    expected_keys = {
        "audit_fixture_canonical_sha256",
        "audit_preprobe_commit",
        "certificate_eligible",
        "independent_verification",
        "proof_scope",
        "report_type",
        "result_contract_eligible",
        "scientific_authority",
        "status",
        "target_p8_a",
        "target_report_differential_receipt_is_not_claimed_to_be_the_P8_B_schedule",
    }
    if set(report) != expected_keys:
        raise AuditError("P8-B audit report key set drift")
    preprobe_commit = report.get("audit_preprobe_commit")
    if not isinstance(preprobe_commit, str):
        raise AuditError("P8-B audit preprobe commit is malformed")
    expected = _audit_report_body(preprobe_commit)
    if dict(report) != expected:
        raise AuditError("P8-B audit report content drift")
    if from_disk:
        if raw != canonical_bytes(dict(report)):
            raise AuditError("P8-B audit report is not canonical JSON")
        if _status_paths():
            raise AuditError("P8-B audit report verification requires a clean worktree")
        head = _git_text("rev-parse", "HEAD").strip()
        _validate_audit_result_commit(head, preprobe_commit, raw)
    return dict(report)


def audit() -> dict[str, Any]:
    if _status_paths():
        raise AuditError("P8-B audit requires a clean frozen preprobe worktree")
    audit_preprobe_commit = _git_text("rev-parse", "HEAD").strip()
    _validate_audit_preprobe_commit(audit_preprobe_commit)
    _assert_current_audit_blobs(audit_preprobe_commit)
    report_path = BASE / AUDIT_REPORT_NAME
    if report_path.exists() or report_path.is_symlink():
        raise AuditError("P8-B audit report already exists")
    report = _audit_report_body(audit_preprobe_commit)
    validate_audit_report(report)
    _write_canonical_json_exclusive(report_path, report)
    return report


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    report_path = BASE / AUDIT_REPORT_NAME
    return {
        "audit_report_sha256": sha256_bytes(_read_current_regular(AUDIT_REPORT_NAME)),
        "scientific_authority": report["scientific_authority"],
        "status": report["status"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-preprobe", action="store_true")
    group.add_argument("--audit", action="store_true")
    group.add_argument("--verify-report", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.verify_preprobe:
            output = verify_preprobe()
        elif arguments.audit:
            output = _summary(audit())
        else:
            output = _summary(validate_audit_report())
    except AuditError as error:
        print(f"P8_B_INDEPENDENT_AUDIT_ERROR: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(output).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
