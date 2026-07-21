#!/usr/bin/env python3
"""Proof-only P10-A static resource-envelope design and fail-closed validator.

This module never launches Julia or a candidate.  It rederives source-pinned
integer count facts, records the byte-closure gaps, and can emit exactly one
canonical negative assessment report after a four-blob preprobe commit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]

DIRECT_PARENT = "7650fc4beb042571477bca43eb7f62c7beab0368"
GATE_ID = "P10-A-STATIC-RESOURCE-ENVELOPE-PROOF-DESIGN-V1"
FIXTURE_ID = "MAJORANA-P10-A-STATIC-RESOURCE-ENVELOPE-PROOF-DESIGN-V1"
POLICY_ID = FIXTURE_ID
REPORT_TYPE = "majorana_p10_a_static_resource_envelope_proof_design_report_v1"
REPORT_STATUS = "ASSESSED_STATIC_RESOURCE_ENVELOPE_NOT_ESTABLISHED"
OUTCOME = "ASSESSED_NOT_ESTABLISHED"
ADMISSION_STATUS = (
    "NOT_ESTABLISHED_BY_P10_A_STATIC_RESOURCE_ENVELOPE_PROOF_DESIGN"
)
FIXED_CAP_BYTES = 1 << 31

FIXTURE_NAME = "majorana_certificate_p10a_static_resource_envelope_fixture.json"
POLICY_NAME = "majorana_certificate_p10a_static_resource_envelope_policy.json"
MODULE_NAME = "majorana_certificate_p10a_static_resource_envelope.py"
TEST_NAME = "test_majorana_certificate_p10a_static_resource_envelope.py"
REPORT_NAME = "majorana_certificate_p10a_static_resource_envelope_report.json"

PREPROBE_BLOB_NAMES = (FIXTURE_NAME, POLICY_NAME, MODULE_NAME, TEST_NAME)
PREPROBE_CHANGED_PATHS = tuple(
    f"docs/research/fermion-frontier/{name}" for name in PREPROBE_BLOB_NAMES
)
REPORT_PATH = f"docs/research/fermion-frontier/{REPORT_NAME}"

G0_CONTRACT = "majorana_certificate_p9_g0_post_d4_governance_closure_contract.json"
G0_RECORD = "majorana_certificate_p9_g0_post_d4_governance_closure_record.json"
P2_FIXTURE = "majorana_certificate_p2_fixture.json"
P9_FIXTURE = "majorana_certificate_p9_bit_order_resource_probe_fixture.json"
P9_SOURCE = (
    "majorana_certificate_p9_bit_order_resource_probe/"
    "majorana_p9_bit_order_step3_resource_probe.jl"
)

SOURCE_PATHS = (
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0_runtime_lock.json",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p4/majorana_p4_runner.jl",
    "majorana_certificate_p6/majorana_p6_runner.jl",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4_fixture.json",
    "majorana_certificate_p5_fixture.json",
    "majorana_certificate_p6_fixture.json",
    P9_FIXTURE,
    P9_SOURCE,
    "majorana_certificate_p9_bit_order_resource_probe_policy.json",
    G0_CONTRACT,
    G0_RECORD,
    "majorana_certificate_p9_g0_post_d4_governance_closure_validator.py",
    FIXTURE_NAME,
    MODULE_NAME,
    TEST_NAME,
)

OBLIGATION_IDS = (
    "LSB-01-SOURCE-TYPE-ALLOCATION-CLOSURE",
    "LSB-02-ALIAS-OWNERSHIP-LIFETIME-GRAPH",
    "LSB-03-EXACT-PAYLOAD-AND-CAPACITY-BYTES",
    "LSB-04-RUNTIME-OVERHEAD-ENVELOPE",
    "LSB-05-PEAK-COMPOSITION-AND-FIXED-CAP-COMPARISON",
    "LSB-06-INDEPENDENT-CHECKER-AND-ADVERSARIAL-MUTATIONS",
    "RSE-07-OPERATION-COST-CLOSURE",
)

# These anchors identify selected live-set construction sites.  They do not
# claim transitive allocation closure; that missing closure is the P10-A result.
SOURCE_ANCHORS = (
    (
        "P9_IMPORTS_FROZEN_P6",
        P9_SOURCE,
        b'include(joinpath(\n    @__DIR__, "..", "majorana_certificate_p6", "majorana_p6_runner.jl",\n))',
        1,
    ),
    (
        "P9_SELECTION_COUNTER_STRUCT",
        P9_SOURCE,
        b"mutable struct P9SelectionResourceCounters",
        1,
    ),
    (
        "P9_BOUNDARY_DECISION_SNAPSHOT_DICT",
        P9_SOURCE,
        b"snapshot_coefficient_bits::Dict{Any,UInt64}",
        1,
    ),
    (
        "P9_BOUNDARY_DECISION_CALLBACK_SET",
        P9_SOURCE,
        b"callback_seen_masks::Set{Any}",
        1,
    ),
    ("P9_SNAPSHOT_ROWS_VECTOR", P9_SOURCE, b"rows = P6SnapshotRow[]", 1),
    ("P9_SNAPSHOT_ROWS_CAPACITY_HINT", P9_SOURCE, b"sizehint!(rows, count)", 1),
    (
        "P9_SNAPSHOT_BITS_DICT",
        P9_SOURCE,
        b"snapshot_bits = Dict{Any,UInt64}(",
        1,
    ),
    ("P9_SELECTED_RANK_ROWS", P9_SOURCE, b"selected = P6RankRow[]", 1),
    (
        "P9_SOURCE_MASKS_SORTED_COLLECTION",
        P9_SOURCE,
        b"source_masks = sort!(collect(",
        1,
    ),
    ("P9_ACTIONS_VECTOR", P9_SOURCE, b"actions = NamedTuple[]", 1),
    (
        "P9_COLLISION_MASKS_SORTED_COLLECTION",
        P9_SOURCE,
        b"collision_masks = sort!(collect(intersect(",
        1,
    ),
    ("P9_COLLISION_INPUTS_VECTOR", P9_SOURCE, b"collision_inputs = [(", 1),
    (
        "P9_DROPPED_VECTOR",
        P9_SOURCE,
        b"dropped = Tuple{typeof(constituent.rotation.ms_int),Float64}[]",
        1,
    ),
    ("P9_VALIDATION_ACTUAL_MASK_SET", P9_SOURCE, b"actual_masks = Set{Any}()", 1),
    ("P9_TRANSITION_RECORD_VECTOR", P9_SOURCE, b"transition_records = Any[]", 1),
    ("P9_BOUNDARY_RECORD_VECTOR", P9_SOURCE, b"boundary_records = Any[]", 1),
    ("P9_STAGE_RECORD_VECTOR", P9_SOURCE, b"stage_records = Any[]", 1),
    (
        "P6_SNAPSHOT_ROW_TYPE",
        "majorana_certificate_p6/majorana_p6_runner.jl",
        b"struct P6SnapshotRow",
        1,
    ),
    (
        "P6_RANK_ROW_TYPE",
        "majorana_certificate_p6/majorana_p6_runner.jl",
        b"struct P6RankRow",
        1,
    ),
    (
        "P3_CANONICAL_HASHER_TYPE",
        "majorana_certificate_p3/majorana_p3_runner.jl",
        b"mutable struct CanonicalArrayHasher",
        1,
    ),
    (
        "P3_FINALIZER_ENTRY",
        "majorana_certificate_p3/majorana_p3_runner.jl",
        b"function finalize_p3_state!(execution, fixture)",
        1,
    ),
    (
        "P3_FINAL_ROWS_SORTED_COLLECTION",
        "majorana_certificate_p3/majorana_p3_runner.jl",
        b"final_rows = sort!(collect(final_sum.Majoranas); by=first)",
        1,
    ),
    (
        "P3_FINALIZER_FOCK_STATE",
        "majorana_certificate_p3/majorana_p3_runner.jl",
        b"neel = FockState(NSITES, :checkerboard, true; nx=L)",
        1,
    ),
    (
        "P9_STEP3_FINALIZER_BINDING",
        P9_SOURCE,
        b"finalize_p3_state!(execution, execution_fixture)",
        2,
    ),
    (
        "P9_STEP3_INPUT_DEEPCOPY_CUSTODY",
        P9_SOURCE,
        b"step3_input = prefix_conformed ? step2_run.completed_output : nothing",
        1,
    ),
)

# Filled with immutable canonical digests after the B0 sources are assembled.
FIXTURE_CANONICAL_SHA256 = "ffbdb58744b321cd2ab16102c76d0c70352044e3974f465a731b5ff33a1fb6ea"
POLICY_SEMANTIC_SHA256 = "c04200032d5a7fb07d521375f9161cf30045402e54662d10d3c7eae8aaf65c3f"


class ProofError(RuntimeError):
    """A fail-closed P10-A validation error."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise ProofError("value is not canonical-JSON encodable") from error


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reject_constant(value: str) -> None:
    raise ProofError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProofError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_json(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProofError(f"{label} is not strict UTF-8") from error
    if text.startswith("\ufeff"):
        raise ProofError(f"{label} has a forbidden UTF-8 BOM")
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except ProofError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProofError(f"{label} is malformed JSON") from error


def _read_regular(path: Path, label: str) -> bytes:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise ProofError(f"missing {label}") from error
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise ProofError(f"{label} must be a regular non-symlink file")
    return path.read_bytes()


def _load_json_file(relative: str) -> dict[str, Any]:
    value = loads_json(_read_regular(BASE / relative, relative), relative)
    if not isinstance(value, dict):
        raise ProofError(f"{relative} must contain a JSON object")
    return value


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        cwd=REPO,
        check=True,
        capture_output=True,
    ).stdout


def _git_object_exists(specification: str) -> bool:
    completed = subprocess.run(
        ("git", "cat-file", "-e", specification),
        cwd=REPO,
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode in (1, 128):
        return False
    raise ProofError("Git object-existence check failed")


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ProofError(f"{label} key set drift")


def _require_exact_int(value: Any, label: str, *, lower: int = 0) -> int:
    if type(value) is not int or value < lower:
        raise ProofError(f"{label} must be an exact integer >= {lower}")
    return value


def _expected_policy_semantic() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "fixture_id": FIXTURE_ID,
        "gate_id": GATE_ID,
        "required_direct_parent_commit": DIRECT_PARENT,
        "report_contract": {
            "relative_path": REPORT_NAME,
            "report_type": REPORT_TYPE,
            "only_legal_outcome_for_this_design": OUTCOME,
            "report_status": REPORT_STATUS,
            "assessment_lifecycle_status": "CLOSED",
            "admission_status": ADMISSION_STATUS,
            "report_is_canonical_JSON_without_trailing_newline": True,
        },
        "preprobe_lifecycle": {
            "one_direct_child_preprobe_before_report": True,
            "preprobe_changed_paths": list(PREPROBE_CHANGED_PATHS),
            "preprobe_paths_are_regular_mode_100644_stage_zero_additions": True,
            "report_must_be_absent_from_parent_and_preprobe": True,
            "result_commit_is_direct_child_of_preprobe": True,
            "result_commit_adds_only_the_report": True,
            "all_four_preprobe_blobs_are_rebound_byte_for_byte_at_result_time": True,
        },
        "proof_only_contract": {
            "P10_A_is_a_design_assessment_not_an_execution": True,
            "P10_A_does_not_launch_Julia_or_the_candidate": True,
            "P10_A_does_not_change_candidate_algorithm_or_caps": True,
            "P10_A_does_not_establish_a_scientific_or_physical_result": True,
            "P10_A_does_not_establish_S0_or_execution_admission": True,
            "P10_A_does_not_claim_resource_NO_GO_or_OOM_causality": True,
            "P10_A_abstract_count_bounds_are_not_byte_or_wall_clock_bounds": True,
        },
        "authority_boundary": {
            "scientific_authority": "NONE",
            "execution_authority": False,
            "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False,
            "resource_no_go_authority": False,
            "S0_authority": False,
            "certificate_eligible": False,
            "result_contract_eligible": False,
        },
        "fixed_cap_decision_rule": {
            "fixed_process_cap_bytes": FIXED_CAP_BYTES,
            "positive_branch_name": (
                "ADMISSION_BOUND_ESTABLISHED_STRICTLY_BELOW_FIXED_CAP"
            ),
            "negative_assessment_branch_name": OUTCOME,
            "positive_branch_requires_all_seven_obligations_VERIFIED": True,
            "positive_branch_requires_exact_integer_peak_bytes": True,
            "positive_branch_requires_peak_strictly_less_than_fixed_cap": True,
            "unknown_peak_forces_negative_assessment_branch": True,
            "negative_assessment_keeps_execution_gate_closed": True,
            "even_a_positive_branch_would_require_new_independent_governance": True,
        },
        "source_custody": {
            "source_files_are_raw_SHA256_and_size_pinned": True,
            "selected_core_allocation_anchors_are_checked": True,
            "selected_anchors_are_not_claimed_as_transitive_allocation_closure": True,
            "G0_projection_is_limited_to_gate_obligation_and_authority_custody": True,
            "raw_D4_report_trace_events_markers_and_host_fields_are_not_inputs": True,
        },
        "status_taxonomy": {
            "assessment_lifecycle": "CLOSED",
            "outcome": OUTCOME,
            "admission": ADMISSION_STATUS,
            "execution_gate": "CLOSED",
            "malformed_or_incomplete_input_is_INVALID_not_a_negative_outcome": True,
        },
        "forbidden_actions": [
            "execute_Julia_candidate_or_any_D5_repeat",
            "read_or_import_the_D4_report_phase_trace_or_producer",
            "use_D3_or_D4_RSS_timing_returncode_stderr_stdout_markers_or_host_failure_as_proof",
            "infer_exact_bytes_from_logical_counts_or_assumed_bytes_per_term",
            "infer_wall_clock_from_abstract_work_units",
            "claim_resource_NO_GO_OOM_S0_READY_certificate_or_scientific_result",
            "relax_the_fixed_cap_or_change_the_candidate",
            "treat_ASSESSED_NOT_ESTABLISHED_as_execution_permission",
        ],
    }


def _policy_semantic(policy: Mapping[str, Any]) -> dict[str, Any]:
    if set(policy) != set(_expected_policy_semantic()) | {"source_files"}:
        raise ProofError("P10-A policy top-level key set drift")
    return {key: deepcopy(value) for key, value in policy.items() if key != "source_files"}


def _validate_source_pins(policy: Mapping[str, Any], *, commit: str | None = None) -> None:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or len(rows) != len(SOURCE_PATHS):
        raise ProofError("P10-A source pin count drift")
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ProofError("malformed P10-A source pin")
        _require_exact_keys(row, {"relative_path", "sha256", "size_bytes"}, "source pin")
        relative = row["relative_path"]
        digest = row["sha256"]
        size = row["size_bytes"]
        if (
            not isinstance(relative, str)
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or type(size) is not int
            or size < 0
        ):
            raise ProofError("invalid P10-A source pin fields")
        names.append(relative)
        if commit is None:
            raw = _read_regular(BASE / relative, f"P10-A source {relative}")
        else:
            raw = _git_bytes(
                "show", f"{commit}:docs/research/fermion-frontier/{relative}"
            )
        if len(raw) != size or sha256_bytes(raw) != digest:
            raise ProofError(f"P10-A source pin drift: {relative}")
    if tuple(names) != SOURCE_PATHS:
        raise ProofError("P10-A source pin path order drift")


def _validate_policy(policy: Mapping[str, Any], *, commit: str | None = None) -> None:
    semantic = _policy_semantic(policy)
    if semantic != _expected_policy_semantic():
        raise ProofError("P10-A policy semantic drift")
    if canonical_sha256(semantic) != POLICY_SEMANTIC_SHA256:
        raise ProofError("P10-A policy semantic hash drift")
    _validate_source_pins(policy, commit=commit)


def _validate_fixture(fixture: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "fixture_id",
        "gate_id",
        "required_direct_parent_commit",
        "scope",
        "authority",
        "fixed_cap_contract",
        "declared_static_facts",
        "count_relation_contract",
        "live_set_component_model",
        "proof_obligation_ledger",
        "outcome_contract",
        "forbidden_evidence_or_inference",
    }
    _require_exact_keys(fixture, expected_keys, "P10-A fixture")
    if canonical_sha256(fixture) != FIXTURE_CANONICAL_SHA256:
        raise ProofError("P10-A fixture canonical hash drift")
    if (
        fixture.get("schema_version") != 1
        or fixture.get("fixture_id") != FIXTURE_ID
        or fixture.get("gate_id") != GATE_ID
        or fixture.get("required_direct_parent_commit") != DIRECT_PARENT
    ):
        raise ProofError("P10-A fixture identity drift")
    authority = fixture.get("authority")
    expected_authority = _expected_policy_semantic()["authority_boundary"]
    if not isinstance(authority, dict) or authority != expected_authority:
        raise ProofError("P10-A fixture authority drift")
    fixed = fixture.get("fixed_cap_contract")
    if not isinstance(fixed, dict) or fixed.get("fixed_process_cap_bytes") != FIXED_CAP_BYTES:
        raise ProofError("P10-A fixed cap drift")
    ledger = fixture.get("proof_obligation_ledger")
    if not isinstance(ledger, list) or len(ledger) != len(OBLIGATION_IDS):
        raise ProofError("P10-A obligation ledger length drift")
    if tuple(row.get("obligation_id") for row in ledger if isinstance(row, dict)) != OBLIGATION_IDS:
        raise ProofError("P10-A obligation ledger identity drift")
    if any(row.get("current_status") != "NOT_ESTABLISHED" for row in ledger):
        raise ProofError("P10-A design cannot mark a proof obligation established")
    outcome = fixture.get("outcome_contract")
    if not isinstance(outcome, dict) or outcome != {
        "assessment_lifecycle_status": "CLOSED",
        "outcome_classification": OUTCOME,
        "admission_status": ADMISSION_STATUS,
        "execution_gate": "CLOSED",
        "exact_static_peak_bytes": None,
        "strictly_below_fixed_cap": None,
        "all_seven_obligations_positive": False,
        "future_execution_prerequisite_satisfied": False,
        "positive_static_envelope_would_still_require_independent_governance": True,
    }:
        raise ProofError("P10-A outcome contract drift")


def _validate_g0_projection(contract: Mapping[str, Any]) -> dict[str, Any]:
    ledger = contract.get("proof_obligation_ledger")
    next_gate = contract.get("next_gate_contract")
    if not isinstance(ledger, dict) or not isinstance(next_gate, dict):
        raise ProofError("G0 proof-only projection is malformed")
    obligations = ledger.get("obligations")
    if not isinstance(obligations, list):
        raise ProofError("G0 obligation list is malformed")
    observed_ids = tuple(
        row.get("obligation_id") for row in obligations if isinstance(row, dict)
    )
    if observed_ids != OBLIGATION_IDS:
        raise ProofError("G0 obligation identity drift")
    authority_fields = {
        "scientific_authority": contract.get("scientific_authority"),
        "execution_authority": contract.get("execution_authority"),
        "candidate_selection_authority": contract.get("candidate_selection_authority"),
        "candidate_or_cap_change_authority": contract.get(
            "candidate_or_cap_change_authority"
        ),
        "resource_or_no_go_authority": contract.get("resource_or_no_go_authority"),
        "S0_authority": contract.get("S0_authority"),
        "certificate_eligible": contract.get("certificate_eligible"),
        "result_contract_eligible": contract.get("result_contract_eligible"),
    }
    if authority_fields != {
        "scientific_authority": "NONE",
        "execution_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }:
        raise ProofError("G0 authority projection drift")
    if (
        next_gate.get("only_allowed_next_gate") != GATE_ID
        or next_gate.get("next_gate_is_a_design_proposal_not_an_execution") is not True
        or next_gate.get("all_seven_obligations_must_be_positively_verified_before_future_execution_governance")
        is not True
        or next_gate.get("static_resource_envelope_must_be_established_with_peak_strictly_below_2147483648_bytes_before_future_execution_governance")
        is not True
        or next_gate.get("ASSESSED_NOT_ESTABLISHED_keeps_the_execution_gate_closed")
        is not True
    ):
        raise ProofError("G0 next-gate projection drift")
    return {
        "contract_id": contract.get("contract_id"),
        "gate_id": next_gate["only_allowed_next_gate"],
        "obligation_ids": list(observed_ids),
        "authority": authority_fields,
    }


def _extract_static_facts() -> dict[str, Any]:
    p2 = _load_json_file(P2_FIXTURE)
    p9 = _load_json_file(P9_FIXTURE)
    g0 = _load_json_file(G0_CONTRACT)
    _validate_g0_projection(g0)

    prefix = p2.get("heisenberg_prefix")
    if not isinstance(prefix, dict) or not isinstance(prefix.get("stages"), list):
        raise ProofError("P2 schedule fixture is malformed")
    stages = prefix["stages"]
    if len(stages) != 9 or any(not isinstance(row, dict) for row in stages):
        raise ProofError("P2 stage schedule drift")
    schedule = {
        "stage_count": prefix.get("stage_count"),
        "composite_count": prefix.get("planned_composite_count"),
        "constituent_count": prefix.get("planned_constituent_count"),
        "truncation_boundary_count": prefix.get(
            "planned_truncation_boundary_count"
        ),
    }
    totals = {
        "stage_count": len(stages),
        "composite_count": sum(row.get("composite_count", -1) for row in stages),
        "constituent_count": sum(row.get("constituent_count", -1) for row in stages),
        "truncation_boundary_count": sum(
            row.get("truncation_boundary_count", -1) for row in stages
        ),
    }
    if schedule != totals:
        raise ProofError("P2 schedule total mismatch")
    d = stages[3]
    segment_d = {
        "stage_index": d.get("stage_index"),
        "group": d.get("group"),
        "composite_count": d.get("composite_count"),
        "constituent_count": d.get("constituent_count"),
        "truncation_boundary_count": d.get("truncation_boundary_count"),
    }
    pre_d = stages[:3]
    static_prefix = {
        "completed_stage_count": 3,
        "transition_record_count": sum(row["constituent_count"] for row in pre_d),
        "boundary_record_count": sum(
            row["truncation_boundary_count"] for row in pre_d
        ),
        "stage_record_count": 3,
    }

    caps = p9.get("deterministic_step3_probe_caps")
    selection_caps = p9.get("deterministic_step3_bit_order_selection_probe_caps")
    prefix_projection = p9.get("expected_P6_prefix_resource_projection")
    if not all(isinstance(value, dict) for value in (caps, selection_caps, prefix_projection)):
        raise ProofError("P9 cap or prefix fixture is malformed")
    cap_keys = (
        "maximum_step3_current_terms_before_constituent",
        "maximum_step3_premerge_terms",
        "maximum_step3_boundary_retained_terms",
        "maximum_step3_final_retained_terms",
    )
    cap_values = tuple(caps.get(key) for key in cap_keys)
    if len(set(cap_values)) != 1:
        raise ProofError("P9 logical term caps do not share one M")
    m = _require_exact_int(cap_values[0], "logical term cap M", lower=1)
    if m & (m - 1):
        raise ProofError("logical term cap M must be a power of two")
    log2_m = m.bit_length() - 1
    bigint_bits = caps.get("maximum_BigInt_bit_length")
    step2 = prefix_projection.get("step2")
    if not isinstance(step2, dict):
        raise ProofError("P9 frozen step2 projection is malformed")
    n0 = step2.get("final_retained_term_count")
    configured_selection_cap = selection_caps.get(
        "maximum_total_bit_order_selection_work_units"
    )
    b = schedule["truncation_boundary_count"]
    q = schedule["constituent_count"]
    d_b = segment_d["truncation_boundary_count"]
    d_q = segment_d["constituent_count"]
    for value, label in (
        (bigint_bits, "BigInt cap L"),
        (n0, "step2 final count N0"),
        (configured_selection_cap, "configured selection cap"),
        (b, "boundary count"),
        (q, "constituent count"),
        (d_b, "segment D boundary count"),
        (d_q, "segment D constituent count"),
    ):
        _require_exact_int(value, label, lower=1)

    full_sort_coefficient = 2 * q + 3 * b
    d_sort_coefficient = 2 * d_q + 3 * d_b
    return {
        "schedule": schedule,
        "segment_D": segment_d,
        "static_prefix_before_segment_D": static_prefix,
        "cardinality_and_arithmetic_caps": {
            "logical_term_cap_M": m,
            "logical_term_cap_log2": log2_m,
            "maximum_BigInt_bit_length_L": bigint_bits,
            "frozen_step2_final_retained_term_count_N0": n0,
            "configured_total_selection_work_cap": configured_selection_cap,
        },
        "abstract_work_bounds": {
            "full_schedule_selection_work_units": 4 * b * m,
            "full_schedule_sort_scale_coefficient": full_sort_coefficient,
            "full_schedule_sort_scale_units": full_sort_coefficient * m * log2_m,
            "segment_D_sort_scale_coefficient": d_sort_coefficient,
            "segment_D_sort_scale_units": d_sort_coefficient * m * log2_m,
            "sort_scale_definition": "coefficient_times_M_times_log2_M",
            "selection_work_definition": (
                "four_selection_counter_components_times_boundary_count_times_M"
            ),
        },
    }


def _source_anchor_summary() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    cache: dict[str, bytes] = {}
    for anchor_id, relative, needle, expected_count in SOURCE_ANCHORS:
        body = cache.setdefault(
            relative, _read_regular(BASE / relative, f"anchor source {relative}")
        )
        observed_count = body.count(needle)
        if observed_count != expected_count:
            raise ProofError(f"source anchor count drift: {anchor_id}")
        rows.append(
            {
                "anchor_id": anchor_id,
                "relative_path": relative,
                "needle_sha256": sha256_bytes(needle),
                "needle_size_bytes": len(needle),
                "expected_occurrences": expected_count,
            }
        )
    return {
        "anchor_count": len(rows),
        "anchors": rows,
        "anchors_canonical_sha256": canonical_sha256(rows),
        "closure_status": "SELECTED_CORE_ANCHORS_ONLY_NOT_TRANSITIVE_ALLOCATION_CLOSURE",
    }


def validate_count_relations(
    *, n_i: int, a_i: int, c_i: int, p_i: int, ell_j: int | None, k_j: int | None
) -> dict[str, Any]:
    m = _extract_static_facts()["cardinality_and_arithmetic_caps"][
        "logical_term_cap_M"
    ]
    values = {"n_i": n_i, "a_i": a_i, "c_i": c_i, "p_i": p_i}
    for label, value in values.items():
        _require_exact_int(value, label)
    if not (
        n_i <= m
        and a_i <= n_i
        and n_i + a_i <= m
        and c_i <= min(n_i, a_i)
        and p_i <= m
    ):
        raise ProofError("per-constituent count relation failed")
    if (ell_j is None) != (k_j is None):
        raise ProofError("boundary count symbols must be both present or both absent")
    if ell_j is not None and k_j is not None:
        _require_exact_int(ell_j, "ell_j")
        _require_exact_int(k_j, "k_j")
        if not 0 <= k_j <= ell_j <= p_i <= m:
            raise ProofError("per-boundary count relation failed")
    return {**values, "ell_j": ell_j, "k_j": k_j, "logical_term_cap_M": m}


def _validate_source_facts(fixture: Mapping[str, Any]) -> dict[str, Any]:
    facts = _extract_static_facts()
    if facts != fixture.get("declared_static_facts"):
        raise ProofError("P10-A declared static facts do not match frozen sources")
    _source_anchor_summary()
    return facts


def _validate_current_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = _load_json_file(FIXTURE_NAME)
    policy = _load_json_file(POLICY_NAME)
    _validate_fixture(fixture)
    _validate_policy(policy)
    facts = _validate_source_facts(fixture)
    return fixture, policy, facts


def _obligation_assessment(fixture: Mapping[str, Any]) -> dict[str, Any]:
    ledger = deepcopy(fixture["proof_obligation_ledger"])
    statuses = {row["current_status"] for row in ledger}
    if statuses != {"NOT_ESTABLISHED"}:
        raise ProofError("P10-A design obligation status drift")
    return {
        "obligation_count": len(ledger),
        "verified_obligation_count": 0,
        "all_seven_obligations_positive": False,
        "rows": ledger,
    }


def build_assessment(
    fixture: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if fixture is None or policy is None:
        fixture, policy, facts = _validate_current_inputs()
    else:
        _validate_fixture(fixture)
        _validate_policy(policy)
        facts = _validate_source_facts(fixture)
    obligations = _obligation_assessment(fixture)
    outcome = deepcopy(fixture["outcome_contract"])
    if (
        outcome["exact_static_peak_bytes"] is not None
        or outcome["strictly_below_fixed_cap"] is not None
        or outcome["all_seven_obligations_positive"] is not False
    ):
        raise ProofError("negative P10-A outcome must preserve unknown peak and open obligations")
    return {
        "assessment_lifecycle_status": "CLOSED",
        "outcome_classification": OUTCOME,
        "known_static_facts": facts,
        "selected_source_anchor_custody": _source_anchor_summary(),
        "count_envelope": {
            "relation_contract": deepcopy(fixture["count_relation_contract"]),
            "live_set_component_model": deepcopy(fixture["live_set_component_model"]),
            "logical_counts_are_not_bytes": True,
        },
        "byte_envelope": {
            "fixed_process_cap_bytes": FIXED_CAP_BYTES,
            "exact_static_peak_bytes": None,
            "strict_integer_peak_less_than_cap": None,
            "comparison_status": "NOT_EVALUABLE_WITHOUT_EXACT_PEAK_BYTES",
            "resource_no_go_inference": False,
        },
        "operation_cost": {
            "selection_work_units": facts["abstract_work_bounds"][
                "full_schedule_selection_work_units"
            ],
            "sort_scale_units": facts["abstract_work_bounds"][
                "full_schedule_sort_scale_units"
            ],
            "units_are_not_seconds": True,
            "sort_scale_is_not_an_actual_comparison_count": True,
            "wall_clock_bound_status": "NOT_ESTABLISHED",
        },
        "proof_obligations": obligations,
        "admission": {
            "status": ADMISSION_STATUS,
            "future_execution_prerequisite_satisfied": False,
            "execution_gate": "CLOSED",
            "future_independent_governance_still_required": True,
        },
        "nonclaims": [
            "no_exact_static_peak_byte_bound",
            "no_strict_below_2GiB_admission_bound",
            "no_resource_NO_GO_or_OOM_attribution",
            "no_wall_clock_bound",
            "no_candidate_execution_or_change",
            "no_S0_scientific_certificate_or_result_authority",
        ],
    }


def _decode_status_path(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProofError("Git status path is not UTF-8") from error


def _status_records() -> tuple[tuple[str, str], ...]:
    raw = _git_bytes("status", "--porcelain=v1", "-z", "--untracked-files=all")
    if not raw:
        return ()
    pieces = raw.split(b"\0")
    if pieces[-1] != b"":
        raise ProofError("unterminated Git status output")
    records: list[tuple[str, str]] = []
    for piece in pieces[:-1]:
        if len(piece) < 4 or piece[2:3] != b" ":
            raise ProofError("unsupported Git status record")
        status_code = piece[:2].decode("ascii", errors="strict")
        if "R" in status_code or "C" in status_code:
            raise ProofError("renames and copies are forbidden in P10-A lifecycle")
        records.append((status_code, _decode_status_path(piece[3:])))
    return tuple(records)


def _assert_index_blob(path: str) -> None:
    row = _git("ls-files", "--stage", "--", path).strip()
    expected_suffix = f" 0\t{path}"
    if not row.startswith("100644 ") or not row.endswith(expected_suffix):
        raise ProofError(f"P10-A index mode or stage drift: {path}")
    index = _git_bytes("show", f":{path}")
    current = _read_regular(REPO / path, f"P10-A indexed path {path}")
    if index != current:
        raise ProofError(f"P10-A index/worktree byte drift: {path}")


def _validate_staged_preprobe() -> None:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise ProofError("P10-A preprobe must start at the frozen G0 direct parent")
    records = _status_records()
    if tuple(sorted(records)) != tuple(sorted(("A ", path) for path in PREPROBE_CHANGED_PATHS)):
        raise ProofError("P10-A staged preprobe status/path set drift")
    for path in PREPROBE_CHANGED_PATHS:
        _assert_index_blob(path)
    report = BASE / REPORT_NAME
    if report.exists() or report.is_symlink():
        raise ProofError("P10-A report exists before its preprobe commit")


def _commit_parent(commit: str) -> str:
    fields = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(fields) != 2 or fields[0] != commit:
        raise ProofError("P10-A commit must have exactly one parent")
    return fields[1]


def _commit_added_paths(commit: str) -> tuple[str, ...]:
    raw = _git_bytes(
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        "--no-renames",
        "-z",
        commit,
    )
    fields = raw.split(b"\0")
    if fields[-1] != b"" or (len(fields) - 1) % 2:
        raise ProofError("malformed Git diff-tree output")
    paths: list[str] = []
    for offset in range(0, len(fields) - 1, 2):
        status_code = fields[offset].decode("ascii", errors="strict")
        path = _decode_status_path(fields[offset + 1])
        if status_code != "A":
            raise ProofError("P10-A lifecycle permits additions only")
        paths.append(path)
    return tuple(sorted(paths))


def _assert_commit_blob_mode(commit: str, path: str) -> None:
    row = _git("ls-tree", commit, "--", path).strip()
    if not row.startswith("100644 blob ") or not row.endswith(f"\t{path}"):
        raise ProofError(f"P10-A committed blob mode drift: {path}")


def _validate_preprobe_commit(commit: str) -> None:
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ProofError("invalid P10-A preprobe commit SHA")
    if _commit_parent(commit) != DIRECT_PARENT:
        raise ProofError("P10-A preprobe parent drift")
    if _commit_added_paths(commit) != tuple(sorted(PREPROBE_CHANGED_PATHS)):
        raise ProofError("P10-A preprobe committed path set drift")
    for path in PREPROBE_CHANGED_PATHS:
        _assert_commit_blob_mode(commit, path)
    if _git_object_exists(f"{commit}:{REPORT_PATH}"):
        raise ProofError("P10-A preprobe commit already contains a report")
    fixture = loads_json(
        _git_bytes("show", f"{commit}:docs/research/fermion-frontier/{FIXTURE_NAME}"),
        f"{commit}:{FIXTURE_NAME}",
    )
    policy = loads_json(
        _git_bytes("show", f"{commit}:docs/research/fermion-frontier/{POLICY_NAME}"),
        f"{commit}:{POLICY_NAME}",
    )
    if not isinstance(fixture, dict) or not isinstance(policy, dict):
        raise ProofError("P10-A committed preprobe JSON is malformed")
    _validate_fixture(fixture)
    _validate_policy(policy, commit=commit)


def _assert_current_preprobe_blobs(preprobe_commit: str) -> None:
    for name in PREPROBE_BLOB_NAMES:
        current = _read_regular(BASE / name, f"current P10-A preprobe blob {name}")
        frozen = _git_bytes(
            "show", f"{preprobe_commit}:docs/research/fermion-frontier/{name}"
        )
        if current != frozen:
            raise ProofError(f"current P10-A preprobe blob drift: {name}")


def _validate_frozen_preprobe(preprobe_commit: str) -> None:
    if _status_records():
        raise ProofError("frozen P10-A preprobe worktree must be clean")
    _validate_preprobe_commit(preprobe_commit)
    _assert_current_preprobe_blobs(preprobe_commit)
    report = BASE / REPORT_NAME
    if report.exists() or report.is_symlink():
        raise ProofError("P10-A report exists during frozen-preprobe verification")


def verify_preprobe() -> dict[str, Any]:
    fixture, policy, _ = _validate_current_inputs()
    head = _git("rev-parse", "HEAD").strip()
    if head == DIRECT_PARENT:
        _validate_staged_preprobe()
        lifecycle = "STAGED_DIRECT_CHILD"
    else:
        _validate_frozen_preprobe(head)
        lifecycle = "COMMITTED_DIRECT_CHILD"
    return {
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
        "direct_parent_commit": DIRECT_PARENT,
        "lifecycle": lifecycle,
        "status": "VERIFIED_P10_A_STATIC_RESOURCE_ENVELOPE_PREPROBE",
    }


def _preprobe_source_summary(policy: Mapping[str, Any]) -> dict[str, Any]:
    anchor_summary = _source_anchor_summary()
    return {
        "fixture_sha256": sha256_bytes(_read_regular(BASE / FIXTURE_NAME, FIXTURE_NAME)),
        "policy_sha256": sha256_bytes(_read_regular(BASE / POLICY_NAME, POLICY_NAME)),
        "source_files_canonical_sha256": canonical_sha256(policy["source_files"]),
        "selected_source_anchors_canonical_sha256": anchor_summary[
            "anchors_canonical_sha256"
        ],
    }


def _write_canonical_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ProofError("P10-A report already exists")
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
        raise ProofError("P10-A report or temporary path already exists") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def assess() -> dict[str, Any]:
    report_path = BASE / REPORT_NAME
    if report_path.exists() or report_path.is_symlink():
        raise ProofError("P10-A report already exists")
    if _status_records():
        raise ProofError("P10-A assessment requires a clean frozen preprobe")
    preprobe_commit = _git("rev-parse", "HEAD").strip()
    _validate_preprobe_commit(preprobe_commit)
    _assert_current_preprobe_blobs(preprobe_commit)
    fixture, policy, _ = _validate_current_inputs()
    report = {
        "schema_version": 1,
        "report_type": REPORT_TYPE,
        "status": REPORT_STATUS,
        "gate_id": GATE_ID,
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
        "preprobe_commit": preprobe_commit,
        "preprobe_source_summary": _preprobe_source_summary(policy),
        "authority": deepcopy(fixture["authority"]),
        "assessment": build_assessment(fixture, policy),
    }
    validate_report(report)
    _write_canonical_json_exclusive(report_path, report)
    return report


def validate_report(report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from_disk = report is None
    if report is None:
        value = loads_json(_read_regular(BASE / REPORT_NAME, REPORT_NAME), REPORT_NAME)
        if not isinstance(value, dict):
            raise ProofError("P10-A report must be an object")
        report = value
    _require_exact_keys(
        report,
        {
            "schema_version",
            "report_type",
            "status",
            "gate_id",
            "fixture_id",
            "policy_id",
            "preprobe_commit",
            "preprobe_source_summary",
            "authority",
            "assessment",
        },
        "P10-A report",
    )
    if (
        report.get("schema_version") != 1
        or report.get("report_type") != REPORT_TYPE
        or report.get("status") != REPORT_STATUS
        or report.get("gate_id") != GATE_ID
    ):
        raise ProofError("P10-A report identity or status drift")
    preprobe_commit = report.get("preprobe_commit")
    if not isinstance(preprobe_commit, str):
        raise ProofError("P10-A report preprobe commit is malformed")
    _validate_preprobe_commit(preprobe_commit)
    _assert_current_preprobe_blobs(preprobe_commit)
    fixture, policy, _ = _validate_current_inputs()
    if (
        report.get("fixture_id") != fixture["fixture_id"]
        or report.get("policy_id") != policy["policy_id"]
        or report.get("authority") != fixture["authority"]
        or report.get("preprobe_source_summary") != _preprobe_source_summary(policy)
        or report.get("assessment") != build_assessment(fixture, policy)
    ):
        raise ProofError("P10-A report content or authority drift")
    assessment = report["assessment"]
    if (
        assessment.get("assessment_lifecycle_status") != "CLOSED"
        or assessment.get("outcome_classification") != OUTCOME
        or assessment.get("byte_envelope", {}).get("exact_static_peak_bytes") is not None
        or assessment.get("byte_envelope", {}).get("strict_integer_peak_less_than_cap")
        is not None
        or assessment.get("admission", {}).get("execution_gate") != "CLOSED"
    ):
        raise ProofError("P10-A negative outcome invariant drift")
    if from_disk:
        raw = _read_regular(BASE / REPORT_NAME, REPORT_NAME)
        if raw != canonical_bytes(dict(report)):
            raise ProofError("P10-A report is not canonical JSON")
    return dict(report)


def verify_result() -> dict[str, Any]:
    if _status_records():
        raise ProofError("P10-A committed result worktree must be clean")
    result_commit = _git("rev-parse", "HEAD").strip()
    preprobe_commit = _commit_parent(result_commit)
    _validate_preprobe_commit(preprobe_commit)
    if _commit_added_paths(result_commit) != (REPORT_PATH,):
        raise ProofError("P10-A result commit must add only the report")
    _assert_commit_blob_mode(result_commit, REPORT_PATH)
    _assert_current_preprobe_blobs(preprobe_commit)
    current_report = _read_regular(BASE / REPORT_NAME, REPORT_NAME)
    committed_report = _git_bytes("show", f"{result_commit}:{REPORT_PATH}")
    if current_report != committed_report:
        raise ProofError("P10-A result report Git/worktree byte drift")
    report = validate_report()
    if report["preprobe_commit"] != preprobe_commit:
        raise ProofError("P10-A report/preprobe lineage drift")
    return {
        "result_commit": result_commit,
        "preprobe_commit": preprobe_commit,
        "report_sha256": sha256_bytes(current_report),
        "status": "VERIFIED_P10_A_STATIC_RESOURCE_ENVELOPE_RESULT",
        "outcome_classification": OUTCOME,
        "execution_gate": "CLOSED",
    }


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_sha256": sha256_bytes(_read_regular(BASE / REPORT_NAME, REPORT_NAME)),
        "status": report["status"],
        "outcome_classification": report["assessment"]["outcome_classification"],
        "execution_gate": report["assessment"]["admission"]["execution_gate"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-preprobe", action="store_true")
    group.add_argument("--assess", action="store_true")
    group.add_argument("--verify-report", action="store_true")
    group.add_argument("--verify-result", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.verify_preprobe:
            result = verify_preprobe()
        elif arguments.assess:
            result = _summary(assess())
        elif arguments.verify_report:
            result = _summary(validate_report())
        else:
            result = verify_result()
    except (ProofError, subprocess.CalledProcessError) as error:
        print(f"P10_A_STATIC_RESOURCE_ENVELOPE_ERROR: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
