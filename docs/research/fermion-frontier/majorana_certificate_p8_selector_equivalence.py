#!/usr/bin/env python3
"""P8-A proof-only gate for a finite-binary64 selector equivalence lemma.

This program deliberately does not execute the P7 candidate, construct a new
candidate, or make a resource, timing, S0, or scientific claim.  It freezes
the narrow mathematical interface used by the P6 adaptive selector and proves
only the conditional equality of successful selector memberships and selected
cost totals under that interface.
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
POLICY_NAME = "majorana_certificate_p8_selector_equivalence_policy.json"
FIXTURE_NAME = "majorana_certificate_p8_selector_equivalence_fixture.json"
REPORT_NAME = "majorana_certificate_p8_selector_equivalence_report.json"
TEST_NAME = "test_majorana_certificate_p8_selector_equivalence.py"
D4_REPORT_NAME = "majorana_certificate_p7_d4_e_per_composite_probe_report.json"
P3_RUNNER_NAME = "majorana_certificate_p3/majorana_p3_runner.jl"
P6_RUNNER_NAME = "majorana_certificate_p6/majorana_p6_runner.jl"

DIRECT_PARENT = "c82e2443dfae07af17cb9108ccb344c2f0cbebba"
POLICY_ID = "MAJORANA-P8-A-FINITE-BINARY64-SELECTOR-EQUIVALENCE-V2"
FIXTURE_ID = POLICY_ID
REPORT_TYPE = "majorana_p8_a_selector_bit_order_equivalence_report_v2"
REPORT_STATUS = "VERIFIED_CONDITIONAL_P8_A_SELECTOR_EQUIVALENCE"
SUPERSEDED_PREPROBE_COMMIT = "f59eb88571384256a5e90c2a5745aa929b9153b7"
D4_REPORT_SIZE_BYTES = 11822
D4_REPORT_SHA256 = "269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19"
D4_PROJECTION_SHA256 = "b89776eaed1261a2c0eff17ec660b212f0ca80151e46d8c9770eb2b946284fac"

# These two values pin the policy/fixture semantic contents, while source-file
# hashes remain in the policy and are checked independently.
POLICY_SEMANTIC_SHA256 = "144a8882580a77b5638b0d3be54eb7c7b9024865b693d67f35dc61ea15d6adc5"
FIXTURE_CANONICAL_SHA256 = "fd3bdf6228b5645a7a15f4658e8aa2dd77ad1be530ef19ace1d2743a0021cb06"

SIGN_MASK = 0x8000000000000000
ABS_BITS_MASK = 0x7FFFFFFFFFFFFFFF
EXPONENT_MASK = 0x7FF0000000000000
FRACTION_MASK = 0x000FFFFFFFFFFFFF
MAX_FINITE_ABS_BITS = 0x7FEFFFFFFFFFFFFF
GRID_EXPONENT = 128
GRID_DENOMINATOR = 1 << GRID_EXPONENT
MAXIMUM_BIGINT_BITS = 2048
P6_K37_ABS_BITS = 0x3DA0000000000000
MASK_MAX = (1 << 256) - 1

PREPROBE_CHANGED_PATHS = (
    f"docs/research/fermion-frontier/{FIXTURE_NAME}",
    f"docs/research/fermion-frontier/{POLICY_NAME}",
    f"docs/research/fermion-frontier/{Path(__file__).name}",
    f"docs/research/fermion-frontier/{TEST_NAME}",
)
SOURCE_PATHS = (
    FIXTURE_NAME,
    Path(__file__).name,
    P3_RUNNER_NAME,
    P6_RUNNER_NAME,
    TEST_NAME,
)
PREPROBE_BLOB_NAMES = (
    FIXTURE_NAME,
    POLICY_NAME,
    Path(__file__).name,
    TEST_NAME,
)


class ProofError(RuntimeError):
    """A closed, non-scientific P8-A validation failure."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProofError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_json(payload: bytes, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProofError(f"invalid JSON: {label}") from error


def _read_regular(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ProofError(f"{label} is missing or not a regular file")
    return path.read_bytes()


def _load_json_file(name: str) -> dict[str, Any]:
    value = loads_json(_read_regular(BASE / name, name), name)
    if not isinstance(value, dict):
        raise ProofError(f"{name} is not a JSON object")
    return value


def _repo_root() -> Path:
    completed = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"),
        cwd=BASE,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ProofError("P8-A must run inside a git worktree")
    root = Path(completed.stdout.strip()).resolve()
    if BASE.resolve() != root / "docs" / "research" / "fermion-frontier":
        raise ProofError("P8-A repository location drift")
    return root


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ProofError(f"git command failed: {' '.join(arguments)}")
    return completed.stdout


def _git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=_repo_root(),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ProofError(f"git command failed: {' '.join(arguments)}")
    return completed.stdout


def _hex_u64(value: int) -> str:
    if type(value) is not int or not 0 <= value <= ABS_BITS_MASK:
        raise ProofError("invalid UInt64 value")
    return f"{value:016x}"


def _parse_hex_u64(value: Any, label: str) -> int:
    if not isinstance(value, str) or len(value) != 16:
        raise ProofError(f"invalid {label} UInt64 hex")
    try:
        parsed = int(value, 16)
    except ValueError as error:
        raise ProofError(f"invalid {label} UInt64 hex") from error
    if _hex_u64(parsed) != value.lower():
        raise ProofError(f"noncanonical {label} UInt64 hex")
    return parsed


def _expected_d4_parent_projection() -> dict[str, Any]:
    return {
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


def _validate_d4_parent(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Read only the frozen identity/authority/kernel projection from D4.

    In particular, this leaf does not access D4 observation, host, marker,
    candidate, D3, staging, resource, timing, or return-code fields.  The
    returned projection is provenance-only and is never an input to selector
    theorem functions.
    """

    report_path = BASE / D4_REPORT_NAME
    body = _read_regular(report_path, "P8-A frozen D4 report")
    if len(body) != D4_REPORT_SIZE_BYTES or sha256_bytes(body) != D4_REPORT_SHA256:
        raise ProofError("P8-A frozen D4 report byte identity drift")
    parent_body = _git_bytes(
        "show", f"{DIRECT_PARENT}:docs/research/fermion-frontier/{D4_REPORT_NAME}",
    )
    if parent_body != body:
        raise ProofError("P8-A D4 report differs from its direct-parent object")
    report = loads_json(body, D4_REPORT_NAME)
    if not isinstance(report, dict):
        raise ProofError("P8-A frozen D4 report is not an object")
    custody = report.get("instrumented_kernel_custody")
    if not isinstance(custody, dict):
        raise ProofError("P8-A D4 kernel custody is malformed")
    projection = {
        "report_type": report.get("report_type"),
        "scientific_authority": report.get("scientific_authority"),
        "certificate_eligible": report.get("certificate_eligible"),
        "result_contract_eligible": report.get("result_contract_eligible"),
        "instrumented_kernel_custody": {
            "frozen_P6_runner_sha256": custody.get("frozen_P6_runner_sha256"),
            "frozen_P6_function_slice_sha256": custody.get(
                "frozen_P6_function_slice_sha256",
            ),
        },
    }
    if projection != _expected_d4_parent_projection():
        raise ProofError("P8-A allowed D4 parent projection drift")
    if canonical_sha256(projection) != D4_PROJECTION_SHA256:
        raise ProofError("P8-A D4 parent projection hash drift")
    parent = fixture.get("D4_parent_custody")
    expected_parent = {
        "result_commit_sha": DIRECT_PARENT,
        "report_relative_path": D4_REPORT_NAME,
        "report_size_bytes": D4_REPORT_SIZE_BYTES,
        "report_sha256": D4_REPORT_SHA256,
        "projection": projection,
        "projection_sha256": D4_PROJECTION_SHA256,
    }
    if parent != expected_parent:
        raise ProofError("P8-A D4 parent custody drift")
    return projection


def _expected_selector_contract() -> dict[str, Any]:
    return {
        "abs_bits_mask_hex": _hex_u64(ABS_BITS_MASK),
        "all_costs_are_exact_nonnegative_BigInt": True,
        "all_selector_rows_have_unique_unsigned_masks": True,
        "binary64_domain": "finite_Float64_magnitude_bits_only",
        "bit_order_key": "(abs_bits,unsigned_mask)",
        "grid_denominator": str(GRID_DENOMINATOR),
        "grid_denominator_power_of_two_exponent": GRID_EXPONENT,
        "maximum_BigInt_bit_length": MAXIMUM_BIGINT_BITS,
        "maximum_finite_abs_bits_hex": _hex_u64(MAX_FINITE_ABS_BITS),
        "P6_K37_abs_bits_hex": _hex_u64(P6_K37_ABS_BITS),
        "P6_rank_key": "(point_abs_ticks,abs_bits,unsigned_mask)",
        "point_abs_ticks": "ceil(2^128*abs(exact_finite_Float64))",
        "snapshot_is_finite_and_immutable_during_selection": True,
        "tier1_predicate": "abs_bits < P6_K37_abs_bits",
        "tier2_source": "same_original_immutable_snapshot",
        "tier2_inclusion": "point_abs_ticks <= tier1_remaining_budget",
    }


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


def _expected_source_contract() -> dict[str, Any]:
    return {
        "D4_frozen_P6_execute_slice_sha256": (
            "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
        ),
        "P3_point_abs_ticks_slice_sha256": (
            "51a2a2b7f9945fdc925f19519706bb0897397f191254ed55ba317f40e1acdec2"
        ),
        "P6_selector_closure_sha256": (
            "4c3bc76d4056fc503c589e17b0ba32c951cb1ba7ad562e7990295fd9fe25ec25"
        ),
        "P6_selector_constants_sha256": (
            "70a4e5c4aec5009348acf2102972ff0f219194f60a4934beb59f77cd85c8f9b7"
        ),
        "P6_prepare_boundary_drop_slice_sha256": (
            "5f79beaf09dd9a1f04b44c3f9d30e331de717fb4887ee650a948c8b34da9bbf5"
        ),
        "source_contract_is_static_and_not_a_runtime_performance_claim": True,
    }


def _expected_preprobe_lineage() -> dict[str, Any]:
    return {
        "revision": "V2",
        "superseded_preprobe_commit": SUPERSEDED_PREPROBE_COMMIT,
        "supersession_reason": "FROZEN_PREPROBE_VERIFICATION_LIFECYCLE_COVERAGE",
    }


def _expected_fixture() -> dict[str, Any]:
    return {
        "D4_parent_custody": {
            "result_commit_sha": DIRECT_PARENT,
            "report_relative_path": D4_REPORT_NAME,
            "report_size_bytes": D4_REPORT_SIZE_BYTES,
            "report_sha256": D4_REPORT_SHA256,
            "projection": _expected_d4_parent_projection(),
            "projection_sha256": D4_PROJECTION_SHA256,
        },
        "authority_exclusions": [
            "P8_A_does_not_identify_a_D4_interruption_cause_or_active_composite",
            "P8_A_does_not_use_D4_observation_or_host_fields_as_an_input",
            "P8_A_does_not_establish_resource_feasibility_or_a_resource_no_go",
            "P8_A_does_not_establish_S0_admission",
            "P8_A_does_not_establish_a_step3_certificate_or_three_step_error_bound",
            "P8_A_does_not_make_a_performance_or_physical_claim",
        ],
        "certificate_eligible": False,
        "direct_parent_commit": DIRECT_PARENT,
        "fixture_id": FIXTURE_ID,
        "preprobe_lineage": _expected_preprobe_lineage(),
        "proof_scope": _expected_proof_scope(),
        "result_contract_eligible": False,
        "schema_version": 1,
        "scientific_authority": "NONE",
        "selector_contract": _expected_selector_contract(),
        "source_contract": _expected_source_contract(),
        "synthetic_differential_domain": {
            "boundary_abs_bits_hex": [
                "0000000000000000",
                "0000000000000001",
                "000fffffffffffff",
                "0010000000000000",
                "37efffffffffffff",
                "37f0000000000000",
                "37f0000000000001",
                "3d9fffffffffffff",
                "3da0000000000000",
                "3da0000000000001",
                "7fefffffffffffff",
            ],
            "maximum_snapshot_rows": 3,
            "must_compare_full_domain_tiered_and_bit_order_implementations": True,
            "must_cover_zero_subnormal_normal_threshold_ties_and_maximum": True,
        },
    }


def _validate_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    expected = _expected_fixture()
    if dict(fixture) != expected:
        raise ProofError("P8-A fixture schema or semantic content drift")
    if canonical_sha256(fixture) != FIXTURE_CANONICAL_SHA256:
        raise ProofError("P8-A fixture canonical hash drift")
    return expected


def _policy_semantic(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in policy.items() if key != "source_files"}


def _expected_policy_semantic() -> dict[str, Any]:
    return {
        "D4_parent_dependency": {
            "allowed_projection_fields": [
                "report_type",
                "scientific_authority",
                "certificate_eligible",
                "result_contract_eligible",
                "instrumented_kernel_custody.frozen_P6_runner_sha256",
                "instrumented_kernel_custody.frozen_P6_function_slice_sha256",
            ],
            "full_D4_report_object_must_not_be_returned_forwarded_or_enter_the_selector": True,
            "raw_D4_report_bytes_are_checked_only_for_identity_before_projection": True,
        },
        "direct_parent_commit": DIRECT_PARENT,
        "forbidden_D4_or_suppressed_inputs": [
            "observation",
            "host_caps",
            "S0_admission",
            "D3_parent_custody",
            "candidate",
            "staging_manifest",
            "phase_events",
            "markers",
            "phase_channel",
            "time",
            "return_code",
            "stderr",
            "stdout",
            "RSS",
            "resource_witness",
            "scientific_values",
        ],
        "fixture_id": FIXTURE_ID,
        "one_preprobe_commit_before_deterministic_proof_report": True,
        "policy_id": POLICY_ID,
        "preprobe_changed_paths": list(PREPROBE_CHANGED_PATHS),
        "preprobe_lineage": _expected_preprobe_lineage(),
        "proof_only_contract": _expected_proof_scope(),
        "report_must_be_absent_at_preprobe": True,
        "schema_version": 1,
        "source_files_are_preprobe_pinned": True,
    }


def _validate_source_pins(policy: Mapping[str, Any], *, commit: str | None = None) -> None:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or len(rows) != len(SOURCE_PATHS):
        raise ProofError("P8-A source pin count drift")
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"relative_path", "sha256", "size_bytes"}:
            raise ProofError("malformed P8-A source pin")
        relative = row["relative_path"]
        size = row["size_bytes"]
        digest = row["sha256"]
        if (
            not isinstance(relative, str)
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ProofError("invalid P8-A source pin fields")
        names.append(relative)
        if commit is None:
            body = _read_regular(BASE / relative, f"P8-A source {relative}")
        else:
            body = _git_bytes(
                "show", f"{commit}:docs/research/fermion-frontier/{relative}",
            )
        if len(body) != size or sha256_bytes(body) != digest:
            raise ProofError(f"P8-A source pin drift: {relative}")
    if tuple(names) != SOURCE_PATHS:
        raise ProofError("P8-A source pin ordering or path set drift")


def _validate_policy(policy: Mapping[str, Any], *, commit: str | None = None) -> dict[str, Any]:
    expected = _expected_policy_semantic()
    if _policy_semantic(policy) != expected:
        raise ProofError("P8-A policy schema or semantic content drift")
    if canonical_sha256(_policy_semantic(policy)) != POLICY_SEMANTIC_SHA256:
        raise ProofError("P8-A policy semantic hash drift")
    _validate_source_pins(policy, commit=commit)
    return expected


def _slice_at(body: bytes, start: int, end: int, label: str) -> bytes:
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(body):
        raise ProofError(f"invalid P8-A {label} slice bounds")
    return body[start:end]


def _validate_source_contract(fixture: Mapping[str, Any]) -> None:
    source_contract = fixture.get("source_contract")
    if source_contract != _expected_source_contract():
        raise ProofError("P8-A source contract drift")
    p3 = _read_regular(BASE / P3_RUNNER_NAME, "P8-A P3 runner")
    p6 = _read_regular(BASE / P6_RUNNER_NAME, "P8-A P6 runner")
    checks = (
        (p3, 13110, 13291, "P3 point_abs_ticks", source_contract["P3_point_abs_ticks_slice_sha256"]),
        (p6, 1189, 1575, "P6 selector constants", source_contract["P6_selector_constants_sha256"]),
        (p6, 23132, 36710, "P6 selector closure", source_contract["P6_selector_closure_sha256"]),
        (p6, 31313, 34103, "P6 prepare boundary", source_contract["P6_prepare_boundary_drop_slice_sha256"]),
        (p6, 37040, 64204, "P6 execute", source_contract["D4_frozen_P6_execute_slice_sha256"]),
    )
    for body, start, end, label, digest in checks:
        if sha256_bytes(_slice_at(body, start, end, label)) != digest:
            raise ProofError(f"P8-A {label} source-slice drift")
    p3_slice = _slice_at(p3, 13110, 13291, "P3 point_abs_ticks")
    if p3_slice != (
        b"function point_abs_ticks(value::Float64, maximum_bits::Int, context)\n"
        b"    ticks = ceil_grid(abs(exact_float_q(value)))\n"
        b"    return check_bigint_cap!(ticks, maximum_bits, context)\n"
        b"end\n"
    ):
        raise ProofError("P8-A P3 exact point-cost formula drift")
    if p6.count(b"p6_prepare_boundary_drop!(") < 2:
        raise ProofError("P8-A P6 prepare hook anchor drift")
    execute = _slice_at(p6, 37040, 64204, "P6 execute")
    for token in (
        b"p6_prepare_boundary_drop!(",
        b"p6_should_drop(",
        b"p6_validate_selected_drop_ticks!(",
    ):
        if execute.count(token) != 1:
            raise ProofError("P8-A P6 selector/execute binding drift")


def _parse_status_paths() -> tuple[str, ...]:
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    for line in status.splitlines():
        if len(line) < 4 or line[2] != " ":
            raise ProofError("P8-A unsupported git status record")
        paths.append(line[3:])
    return tuple(sorted(paths))


def _parse_preprobe_staged_paths() -> tuple[str, ...]:
    """Accept only final, staged additions for the four new preprobe blobs.

    Since P8-A starts from a parent that has none of these paths, an ``A  ``
    porcelain record proves that the index contains the same bytes that the
    verifier just read from the worktree.  It rejects an unstaged edit (``AM``)
    or an untracked file (``??``), either of which would otherwise leave a
    gap between verified bytes and the proposed commit.
    """

    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    for line in status.splitlines():
        if len(line) < 4 or line[:3] != "A  ":
            raise ProofError("P8-A preprobe requires final staged additions")
        paths.append(line[3:])
    return tuple(sorted(paths))


def _validate_preprobe_worktree() -> None:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise ProofError("P8-A preprobe must start from its frozen direct parent")
    if _parse_preprobe_staged_paths() != tuple(sorted(PREPROBE_CHANGED_PATHS)):
        raise ProofError("P8-A preprobe changed-path set drift")
    report = BASE / REPORT_NAME
    if report.exists() or report.is_symlink():
        raise ProofError("P8-A report exists before its preprobe commit")


def _validate_frozen_preprobe_worktree(preprobe_commit: str) -> None:
    if _parse_status_paths():
        raise ProofError("P8-A frozen preprobe worktree must be clean")
    _validate_preprobe_commit(preprobe_commit)
    _assert_current_preprobe_blobs(preprobe_commit)
    report = BASE / REPORT_NAME
    if report.exists() or report.is_symlink():
        raise ProofError("P8-A report exists before its frozen preprobe verification")


def _validate_preprobe_commit(commit: str) -> None:
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ProofError("invalid P8-A preprobe commit SHA")
    if _git("rev-parse", f"{commit}^").strip() != DIRECT_PARENT:
        raise ProofError("P8-A preprobe parent drift")
    changed = tuple(sorted(
        item for item in _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
        if item
    ))
    if changed != tuple(sorted(PREPROBE_CHANGED_PATHS)):
        raise ProofError("P8-A preprobe committed-path set drift")
    report_object = subprocess.run(
        (
            "git", "cat-file", "-e",
            f"{commit}:docs/research/fermion-frontier/{REPORT_NAME}",
        ),
        cwd=_repo_root(),
        check=False,
        capture_output=True,
    )
    if report_object.returncode == 0:
        raise ProofError("P8-A preprobe commit already contains a report")
    if report_object.returncode not in (1, 128):
        raise ProofError("P8-A preprobe report-absence check failed")
    policy = loads_json(
        _git_bytes("show", f"{commit}:docs/research/fermion-frontier/{POLICY_NAME}"),
        f"{commit}:{POLICY_NAME}",
    )
    fixture = loads_json(
        _git_bytes("show", f"{commit}:docs/research/fermion-frontier/{FIXTURE_NAME}"),
        f"{commit}:{FIXTURE_NAME}",
    )
    if not isinstance(policy, dict) or not isinstance(fixture, dict):
        raise ProofError("P8-A preprobe fixture or policy is malformed")
    _validate_policy(policy, commit=commit)
    _validate_fixture(fixture)


def _assert_current_preprobe_blobs(preprobe_commit: str) -> None:
    """Require result-time P8 sources to be byte-identical to the preprobe.

    The policy's source list cannot self-pin its own bytes without a cycle, so
    this explicit commit-object comparison closes that custody edge as well as
    binding the Python verifier and its preprobe test.
    """

    for name in PREPROBE_BLOB_NAMES:
        current = _read_regular(BASE / name, f"P8-A current preprobe blob {name}")
        frozen = _git_bytes(
            "show", f"{preprobe_commit}:docs/research/fermion-frontier/{name}",
        )
        if current != frozen:
            raise ProofError(f"P8-A current preprobe blob drift: {name}")


def _require_exact_int(value: Any, label: str, *, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ProofError(f"invalid {label}")
    return value


@dataclass(frozen=True)
class SelectorRow:
    """A sign-erased finite-binary64 selector input row."""

    abs_bits: int
    mask: int


@dataclass(frozen=True)
class RankedRow:
    row: SelectorRow
    point_cost: int


@dataclass(frozen=True)
class Selection:
    ordered_rows: tuple[RankedRow, ...]
    remaining_budget: int

    @property
    def membership(self) -> frozenset[int]:
        return frozenset(item.row.mask for item in self.ordered_rows)

    @property
    def selected_cost_total(self) -> int:
        return sum(item.point_cost for item in self.ordered_rows)


def _validate_rows(rows: Iterable[SelectorRow]) -> tuple[SelectorRow, ...]:
    materialized = tuple(rows)
    masks: set[int] = set()
    for row in materialized:
        if not isinstance(row, SelectorRow):
            raise ProofError("selector row type drift")
        _require_exact_int(row.abs_bits, "finite Float64 magnitude bits", lower=0, upper=MAX_FINITE_ABS_BITS)
        _require_exact_int(row.mask, "unsigned selector mask", lower=0, upper=MASK_MAX)
        if row.mask in masks:
            raise ProofError("duplicate selector mask")
        masks.add(row.mask)
    return materialized


def _finite_components(abs_bits: int) -> tuple[int, int]:
    """Return |x| as significand * 2**exponent without host float arithmetic."""

    _require_exact_int(abs_bits, "finite Float64 magnitude bits", lower=0, upper=MAX_FINITE_ABS_BITS)
    exponent_bits = (abs_bits >> 52) & 0x7FF
    fraction_bits = abs_bits & FRACTION_MASK
    if exponent_bits == 0:
        return fraction_bits, -1074
    return (1 << 52) + fraction_bits, exponent_bits - 1023 - 52


def exact_abs_fraction(abs_bits: int) -> Fraction:
    significand, exponent = _finite_components(abs_bits)
    if significand == 0:
        return Fraction(0, 1)
    return Fraction(significand << exponent, 1) if exponent >= 0 else Fraction(
        significand, 1 << (-exponent),
    )


def point_abs_ticks_from_bits(abs_bits: int) -> int:
    """The P3 exact ceil-grid cost for a finite binary64 magnitude bit pattern."""

    significand, exponent = _finite_components(abs_bits)
    if significand == 0:
        return 0
    shifted_exponent = exponent + GRID_EXPONENT
    if shifted_exponent >= 0:
        result = significand << shifted_exponent
    else:
        divisor = 1 << (-shifted_exponent)
        result = (significand + divisor - 1) // divisor
    if result.bit_length() > MAXIMUM_BIGINT_BITS:
        raise ProofError("P8-A point cost exceeds the frozen BigInt cap")
    return result


def _rank_key(item: RankedRow) -> tuple[int, int, int]:
    return (item.point_cost, item.row.abs_bits, item.row.mask)


def _bit_order_key(row: SelectorRow) -> tuple[int, int]:
    return (row.abs_bits, row.mask)


def _affordable_prefix(rows: Sequence[RankedRow], available: int) -> Selection:
    remaining = _require_exact_int(available, "available selector budget", lower=0, upper=(1 << 4096) - 1)
    selected: list[RankedRow] = []
    for row in rows:
        if row.point_cost > remaining:
            break
        selected.append(row)
        remaining -= row.point_cost
    return Selection(tuple(selected), remaining)


def full_domain_selector(rows: Iterable[SelectorRow], available: int) -> Selection:
    """Independent full-domain P6-rank oracle, not the bit-order implementation."""

    materialized = _validate_rows(rows)
    ranked = [RankedRow(row, point_abs_ticks_from_bits(row.abs_bits)) for row in materialized]
    ranked.sort(key=_rank_key)
    return _affordable_prefix(ranked, available)


def p6_tiered_selector(rows: Iterable[SelectorRow], available: int) -> Selection:
    """A pure successful-path model of P6 tier-1/tier-2 membership semantics.

    Resource charging and cap exceptions are intentionally absent: P8-A does
    not claim that a lazy implementation and a full-domain implementation take
    the same resource/cap path.
    """

    materialized = _validate_rows(rows)
    remaining = _require_exact_int(available, "available selector budget", lower=0, upper=(1 << 4096) - 1)
    tier1 = [
        RankedRow(row, point_abs_ticks_from_bits(row.abs_bits))
        for row in materialized if row.abs_bits < P6_K37_ABS_BITS
    ]
    tier1.sort(key=_rank_key)
    first = _affordable_prefix(tier1, remaining)
    selected = list(first.ordered_rows)
    remaining = first.remaining_budget
    if len(first.ordered_rows) != len(tier1) or remaining == 0:
        return Selection(tuple(selected), remaining)
    tier2 = [
        RankedRow(row, point_abs_ticks_from_bits(row.abs_bits))
        for row in materialized
        if row.abs_bits >= P6_K37_ABS_BITS
        and point_abs_ticks_from_bits(row.abs_bits) <= remaining
    ]
    tier2.sort(key=_rank_key)
    second = _affordable_prefix(tier2, remaining)
    selected.extend(second.ordered_rows)
    return Selection(tuple(selected), second.remaining_budget)


def bit_order_selector(rows: Iterable[SelectorRow], available: int) -> Selection:
    """The proposed P8-A semantic selector: bit order with lazy exact costs."""

    materialized = _validate_rows(rows)
    remaining = _require_exact_int(available, "available selector budget", lower=0, upper=(1 << 4096) - 1)
    selected: list[RankedRow] = []
    for row in sorted(materialized, key=_bit_order_key):
        point_cost = point_abs_ticks_from_bits(row.abs_bits)
        if point_cost > remaining:
            break
        selected.append(RankedRow(row, point_cost))
        remaining -= point_cost
    return Selection(tuple(selected), remaining)


def _selector_summary(value: Selection) -> dict[str, Any]:
    return {
        "ordered_masks": [str(item.row.mask) for item in value.ordered_rows],
        "remaining_budget": str(value.remaining_budget),
        "selected_cost_total": str(value.selected_cost_total),
    }


def _selection_semantics(value: Selection) -> tuple[frozenset[int], int]:
    """The P6 selected-costs contract, excluding any Dict iteration order."""

    return (value.membership, value.selected_cost_total)


def _prove_equivalence(
    reference: Callable[[Iterable[SelectorRow], int], Selection],
    candidate: Callable[[Iterable[SelectorRow], int], Selection],
    cases: Iterable[tuple[str, tuple[SelectorRow, ...], int]],
) -> int:
    count = 0
    for case_id, rows, available in cases:
        expected = reference(rows, available)
        actual = candidate(rows, available)
        if _selection_semantics(expected) != _selection_semantics(actual):
            raise ProofError(
                f"selector equivalence mismatch at {case_id}: "
                f"{_selector_summary(expected)} != {_selector_summary(actual)}",
            )
        count += 1
    if count == 0:
        raise ProofError("empty P8-A differential proof domain")
    return count


def _prove_internal_rank_trace_equivalence(
    reference: Callable[[Iterable[SelectorRow], int], Selection],
    candidate: Callable[[Iterable[SelectorRow], int], Selection],
    cases: Iterable[tuple[str, tuple[SelectorRow, ...], int]],
) -> int:
    """Check the pinned canonical rank witness, not P6 Dict output order."""

    count = 0
    for case_id, rows, available in cases:
        expected = reference(rows, available)
        actual = candidate(rows, available)
        if expected != actual:
            raise ProofError(f"internal rank-trace mismatch at {case_id}")
        count += 1
    if count == 0:
        raise ProofError("empty P8-A internal rank-trace domain")
    return count


def _boundary_bits(fixture: Mapping[str, Any]) -> tuple[int, ...]:
    domain = fixture["synthetic_differential_domain"]
    values = domain["boundary_abs_bits_hex"]
    if not isinstance(values, list) or not values:
        raise ProofError("P8-A synthetic differential domain is empty")
    parsed = tuple(_parse_hex_u64(value, "P8-A boundary") for value in values)
    if tuple(sorted(parsed)) != parsed or len(set(parsed)) != len(parsed):
        raise ProofError("P8-A boundary magnitude ordering drift")
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
        raise ProofError("P8-A boundary magnitude coverage drift")
    return parsed


def _differential_cases(fixture: Mapping[str, Any]) -> tuple[tuple[str, tuple[SelectorRow, ...], int], ...]:
    values = _boundary_bits(fixture)
    maximum_rows = fixture["synthetic_differential_domain"]["maximum_snapshot_rows"]
    if maximum_rows != 3:
        raise ProofError("P8-A synthetic maximum row count drift")
    cases: list[tuple[str, tuple[SelectorRow, ...], int]] = []
    for cardinality in range(maximum_rows + 1):
        for ordinal, combination in enumerate(combinations_with_replacement(values, cardinality)):
            rows = tuple(
                SelectorRow(abs_bits=value, mask=(cardinality - index) * 17 + ordinal)
                for index, value in enumerate(combination)
            )
            full = full_domain_selector(rows, sum(point_abs_ticks_from_bits(item.abs_bits) for item in rows))
            budgets = {
                0,
                1,
                *(item.point_cost for item in full.ordered_rows),
                *(sum(item.point_cost for item in full.ordered_rows[:index]) for index in range(len(full.ordered_rows) + 1)),
                full.selected_cost_total,
                full.selected_cost_total + 1,
            }
            for input_label, input_rows in (("forward", rows), ("reverse", tuple(reversed(rows)))):
                for budget in sorted(budgets):
                    case_id = f"n{cardinality}-c{ordinal}-{input_label}-b{budget}"
                    cases.append((case_id, input_rows, budget))
    return tuple(cases)


def _assert_binary64_monotonicity() -> dict[str, Any]:
    """Mechanically check every binade transition for the symbolic bit proof."""

    transitions = 0
    previous_end: int | None = None
    for exponent_bits in range(0, 0x7FF):
        start = 0 if exponent_bits == 0 else exponent_bits << 52
        end = (exponent_bits << 52) | FRACTION_MASK
        if exponent_bits == 0:
            significand_low, exponent_low = 0, -1074
            significand_high, exponent_high = FRACTION_MASK, -1074
        else:
            significand_low, exponent_low = _finite_components(start)
            significand_high, exponent_high = _finite_components(end)
        if significand_low > significand_high or exponent_low != exponent_high:
            raise ProofError("P8-A binary64 intra-binade symbolic order drift")
        if previous_end is not None:
            if not exact_abs_fraction(previous_end) < exact_abs_fraction(start):
                raise ProofError("P8-A binary64 binade boundary order drift")
            if point_abs_ticks_from_bits(previous_end) > point_abs_ticks_from_bits(start):
                raise ProofError("P8-A point-cost binade monotonicity drift")
            transitions += 1
        previous_end = end
    if previous_end != MAX_FINITE_ABS_BITS or transitions != 2046:
        raise ProofError("P8-A binary64 binade coverage drift")
    return {
        "all_2047_finite_binary64_binades_symbolically_checked": True,
        "adjacent_binade_transition_count": transitions,
        "intra_binade_significand_order_is_exact_integer_order": True,
        "point_cost_is_ceil_of_the_exact_nonnegative_grid_scaled_magnitude": True,
    }


def _assert_hand_boundary_facts(fixture: Mapping[str, Any]) -> dict[str, Any]:
    values = _boundary_bits(fixture)
    costs = {value: point_abs_ticks_from_bits(value) for value in values}
    if costs[0] != 0 or costs[1] != 1 or costs[FRACTION_MASK] != 1:
        raise ProofError("P8-A zero or subnormal cost fact drift")
    if (
        costs[0x37EFFFFFFFFFFFFF] != 1
        or costs[0x37F0000000000000] != 1
        or costs[0x37F0000000000001] != 2
    ):
        raise ProofError("P8-A ceil-grid first-integer transition fact drift")
    if costs[P6_K37_ABS_BITS] != 1 << 91:
        raise ProofError("P8-A K37 point-cost fact drift")
    if not costs[P6_K37_ABS_BITS - 1] < costs[P6_K37_ABS_BITS]:
        raise ProofError("P8-A K37 tier cost-gap fact drift")
    if costs[MAX_FINITE_ABS_BITS] != (1 << 1152) - (1 << 1099):
        raise ProofError("P8-A maximum finite point-cost fact drift")
    if costs[MAX_FINITE_ABS_BITS].bit_length() != 1152:
        raise ProofError("P8-A maximum finite point-cost bit length drift")
    return {
        "K37_cost": str(costs[P6_K37_ABS_BITS]),
        "K37_minus_one_cost": str(costs[P6_K37_ABS_BITS - 1]),
        "ceil_grid_first_integer_transition_costs": [
            str(costs[0x37EFFFFFFFFFFFFF]),
            str(costs[0x37F0000000000000]),
            str(costs[0x37F0000000000001]),
        ],
        "maximum_finite_cost": str(costs[MAX_FINITE_ABS_BITS]),
        "maximum_finite_cost_bit_length": costs[MAX_FINITE_ABS_BITS].bit_length(),
        "nonzero_subnormal_cost": str(costs[1]),
        "signed_zero_is_ranked_by_abs_bits_zero_and_mask_only": True,
    }


def build_selector_proof(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Build a pure proof object; it intentionally accepts no D4 data."""

    if fixture["selector_contract"] != _expected_selector_contract():
        raise ProofError("P8-A selector theorem contract drift")
    monotonicity = _assert_binary64_monotonicity()
    boundaries = _assert_hand_boundary_facts(fixture)
    cases = _differential_cases(fixture)
    full_vs_tiered = _prove_equivalence(full_domain_selector, p6_tiered_selector, cases)
    full_vs_bit = _prove_equivalence(full_domain_selector, bit_order_selector, cases)
    tiered_rank_trace = _prove_internal_rank_trace_equivalence(
        full_domain_selector, p6_tiered_selector, cases,
    )
    bit_rank_trace = _prove_internal_rank_trace_equivalence(
        full_domain_selector, bit_order_selector, cases,
    )
    case_summary = {
        "case_count": len(cases),
        "case_ids_sha256": canonical_sha256([case[0] for case in cases]),
        "full_domain_equals_P6_tiered_membership_and_cost_total_case_count": full_vs_tiered,
        "full_domain_equals_bit_order_membership_and_cost_total_case_count": full_vs_bit,
        "internal_canonical_rank_trace_check_case_counts": {
            "P6_tiered": tiered_rank_trace,
            "bit_order": bit_rank_trace,
        },
        "internal_rank_trace_is_not_P6_selected_costs_Dict_iteration_semantics": True,
    }
    return {
        "assumptions": [
            "finite_immutable_snapshot_with_unique_unsigned_masks",
            "P3_exact_point_abs_ticks_and_no_BigInt_cap_exception",
            "same_nonnegative_BigInt_available_budget_and_same_P6_K37_threshold",
            "P6_rank_key_is_point_cost_then_abs_bits_then_unsigned_mask",
            "tier2_rescans_the_same_snapshot_and_includes_every_cost_not_exceeding_tier1_remaining_budget",
        ],
        "boundary_facts": boundaries,
        "differential_witness": case_summary,
        "lemma": {
            "finite_binary64_abs_bits_order_implies_non_decreasing_P3_point_cost": True,
            "tier1_is_an_initial_segment_of_the_full_P6_rank_order": True,
            "tiered_and_full_domain_successful_selection_membership_and_cost_total_are_equal": True,
            "bit_order_and_full_domain_successful_selection_membership_and_cost_total_are_equal": True,
        },
        "monotonicity_check": monotonicity,
        "nonclaims": [
            "no_resource_consumption_equivalence",
            "no_cap_path_equivalence",
            "no_host_or_performance_claim",
            "no_D4_interruption_cause_inference",
            "no_S0_or_step3_scientific_claim",
        ],
        "proof_status": REPORT_STATUS,
    }


def _preprobe_source_summary(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fixture_sha256": sha256_bytes(_read_regular(BASE / FIXTURE_NAME, FIXTURE_NAME)),
        "policy_sha256": sha256_bytes(_read_regular(BASE / POLICY_NAME, POLICY_NAME)),
        "source_files_canonical_sha256": canonical_sha256(policy["source_files"]),
    }


def _validate_current_preprobe_inputs(*, require_parent_worktree: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = _load_json_file(POLICY_NAME)
    fixture = _load_json_file(FIXTURE_NAME)
    _validate_policy(policy)
    _validate_fixture(fixture)
    _validate_source_contract(fixture)
    _validate_d4_parent(fixture)
    if require_parent_worktree:
        _validate_preprobe_worktree()
    return policy, fixture


def verify_preprobe() -> dict[str, Any]:
    policy, fixture = _validate_current_preprobe_inputs(require_parent_worktree=False)
    head = _git("rev-parse", "HEAD").strip()
    if head == DIRECT_PARENT:
        _validate_preprobe_worktree()
    else:
        _validate_frozen_preprobe_worktree(head)
    return {
        "direct_parent_commit": DIRECT_PARENT,
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
        "status": "VERIFIED_P8_A_SELECTOR_EQUIVALENCE_PREPROBE",
    }


def _write_canonical_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ProofError("P8-A report already exists")
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
        raise ProofError("P8-A report or temporary path already exists") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def prove() -> dict[str, Any]:
    report_path = BASE / REPORT_NAME
    if report_path.exists() or report_path.is_symlink():
        raise ProofError("P8-A report already exists")
    if _parse_status_paths():
        raise ProofError("P8-A proof requires a clean preprobe worktree")
    preprobe_commit = _git("rev-parse", "HEAD").strip()
    _validate_preprobe_commit(preprobe_commit)
    _assert_current_preprobe_blobs(preprobe_commit)
    policy, fixture = _validate_current_preprobe_inputs(require_parent_worktree=False)
    proof = build_selector_proof(fixture)
    report = {
        "D4_parent_projection": _expected_d4_parent_projection(),
        "certificate_eligible": False,
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
        "preprobe_lineage": _expected_preprobe_lineage(),
        "preprobe_commit": preprobe_commit,
        "preprobe_source_summary": _preprobe_source_summary(policy),
        "proof": proof,
        "report_type": REPORT_TYPE,
        "result_contract_eligible": False,
        "S0_admission_status": "NOT_ESTABLISHED_BY_P8_A_PROOF_ONLY",
        "scientific_authority": "NONE",
        "status": REPORT_STATUS,
    }
    validate_proof_report(report)
    _write_canonical_json_exclusive(report_path, report)
    return report


def validate_proof_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from_disk = report is None
    if report is None:
        value = loads_json(_read_regular(BASE / REPORT_NAME, REPORT_NAME), REPORT_NAME)
        if not isinstance(value, dict):
            raise ProofError("P8-A report is not an object")
        report = value
    expected_keys = {
        "D4_parent_projection",
        "certificate_eligible",
        "fixture_id",
        "policy_id",
        "preprobe_lineage",
        "preprobe_commit",
        "preprobe_source_summary",
        "proof",
        "report_type",
        "result_contract_eligible",
        "S0_admission_status",
        "scientific_authority",
        "status",
    }
    if set(report) != expected_keys:
        raise ProofError("P8-A report key set drift")
    if (
        report.get("report_type") != REPORT_TYPE
        or report.get("status") != REPORT_STATUS
        or report.get("scientific_authority") != "NONE"
        or report.get("certificate_eligible") is not False
        or report.get("result_contract_eligible") is not False
        or report.get("S0_admission_status") != "NOT_ESTABLISHED_BY_P8_A_PROOF_ONLY"
    ):
        raise ProofError("P8-A authority boundary drift")
    preprobe_commit = report.get("preprobe_commit")
    if not isinstance(preprobe_commit, str):
        raise ProofError("P8-A preprobe commit is malformed")
    _validate_preprobe_commit(preprobe_commit)
    _assert_current_preprobe_blobs(preprobe_commit)
    policy, fixture = _validate_current_preprobe_inputs(require_parent_worktree=False)
    if report.get("fixture_id") != fixture["fixture_id"] or report.get("policy_id") != policy["policy_id"]:
        raise ProofError("P8-A report identity drift")
    if report.get("D4_parent_projection") != _expected_d4_parent_projection():
        raise ProofError("P8-A report D4 projection drift")
    if report.get("preprobe_lineage") != _expected_preprobe_lineage():
        raise ProofError("P8-A report preprobe lineage drift")
    if report.get("preprobe_source_summary") != _preprobe_source_summary(policy):
        raise ProofError("P8-A report source custody drift")
    expected_proof = build_selector_proof(fixture)
    if report.get("proof") != expected_proof:
        raise ProofError("P8-A report proof object drift")
    if from_disk:
        raw = _read_regular(BASE / REPORT_NAME, REPORT_NAME)
        if raw != canonical_bytes(dict(report)):
            raise ProofError("P8-A report is not canonical JSON")
    return dict(report)


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    report_path = BASE / REPORT_NAME
    return {
        "report_sha256": sha256_bytes(_read_regular(report_path, REPORT_NAME)),
        "scientific_authority": report["scientific_authority"],
        "status": report["status"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-preprobe", action="store_true")
    group.add_argument("--prove", action="store_true")
    group.add_argument("--verify-report", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.verify_preprobe:
            result = verify_preprobe()
        elif arguments.prove:
            result = _summary(prove())
        else:
            result = _summary(validate_proof_report())
    except ProofError as error:
        print(f"P8_A_SELECTOR_EQUIVALENCE_ERROR: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
