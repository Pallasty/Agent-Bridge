#!/usr/bin/env python3
"""Run and verify the non-authoritative Majorana P7 D2 schedule diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Mapping, Sequence
import uuid


# Importing a frozen checker must not create an untracked __pycache__ before
# the clean-tree gate for the unique preprobe execution.
sys.dont_write_bytecode = True


BASE = Path(__file__).resolve().parent
D1_ORCHESTRATOR_NAME = "majorana_certificate_p7_d1_phase_probe.py"
D1_POLICY_NAME = "majorana_certificate_p7_d1_phase_probe_policy.json"
D1_FIXTURE_NAME = "majorana_certificate_p7_d1_phase_probe_fixture.json"
D1_REPORT_NAME = "majorana_certificate_p7_d1_phase_probe_report.json"
D0_ORCHESTRATOR_NAME = "majorana_certificate_p7_design_probe.py"
D0_POLICY_NAME = "majorana_certificate_p7_design_probe_policy.json"
D0_FIXTURE_NAME = "majorana_certificate_p7_design_probe_fixture.json"
POLICY_NAME = "majorana_certificate_p7_d2_schedule_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p7_d2_schedule_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p7_d2_schedule_probe_report.json"
TEST_NAME = "test_majorana_certificate_p7_d2_schedule_probe.py"
EXECUTION_CLAIM_NAME = ".majorana_certificate_p7_d2_schedule_probe.execution-claimed"
PROBE_DRIVER = (
    "majorana_certificate_p7_d2_schedule_probe/"
    "majorana_p7_step3_schedule_probe.jl"
)
P6_RUNNER_NAME = "majorana_certificate_p6/majorana_p6_runner.jl"

_D1_SPEC = importlib.util.spec_from_file_location(
    "majorana_p7_d1_frozen_for_d2", BASE / D1_ORCHESTRATOR_NAME,
)
if _D1_SPEC is None or _D1_SPEC.loader is None:
    raise RuntimeError("cannot load frozen P7 D1 orchestrator")
D1 = importlib.util.module_from_spec(_D1_SPEC)
_D1_SPEC.loader.exec_module(D1)
D0 = D1.D0

POLICY_ID = "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D2-SCHEDULE-V1"
FIXTURE_ID = POLICY_ID
REPORT_TYPE = "majorana_p7_step3_e768_max_lazy37_schedule_report_d2_v1"
DIAGNOSTIC_PROBE_ID = "P7-D2-E768-MAX-LAZY37-STEP3-SCHEDULE-V1"
DIAGNOSTIC_MODE = "E768_MAX_LAZY37_STEP3_D2_SCHEDULE_V1"
CANDIDATE_ID = D1.CANDIDATE_ID
SCIENTIFIC_PROBE_MODE = D1.SCIENTIFIC_PROBE_MODE
ALGORITHM_ID = D1.ALGORITHM_ID
DIRECT_PARENT = "29911a8ac46c068c550504f8b4a57d27a9441c0c"
D1_REPORT_SHA256 = (
    "9d37609c51f9149baf347fbf801338cc0abe7c7323c187fe71a4932099f8f713"
)
D1_REPORT_SIZE_BYTES = 9523
D1_TERMINAL_STATUS = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
D1_LAST_PHASE_EVENT = "STEP3_ENGINE_STARTED"
D1_ADMISSION_STATUS = "NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC"

# Filled after the policy, fixture and protocol semantic objects are frozen.
POLICY_SEMANTIC_SHA256 = (
    "bafc90b40a1dc1de3d95cd9e7e4d6eb9861a46b73e92c09eb697a671a3868277"
)
FIXTURE_CANONICAL_SHA256 = (
    "417600f82e46086adde81a632cae1da5c0dc1235c3f7a8d83875394d81a64dee"
)
PHASE_PROTOCOL_CANONICAL_SHA256 = (
    "b27caef5156aaae8946da2705c9a1956faa54e123aee341686449129c8da0e97"
)

P6_RUNNER_SHA256 = (
    "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
)
P6_FUNCTION_NAME = b"execute_p6_step2"
D2_FUNCTION_NAME = b"execute_p6_step2_d2"
P6_FUNCTION_SLICE_SHA256 = (
    "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
)
# The insertion tuple is (unique frozen anchor, exact inserted bytes,
# insert-before-anchor).  Marker bytes are checker-owned constants; they are
# never learned from or normalized out of an untrusted D2 driver.
MARKER_INSERTIONS: tuple[tuple[bytes, bytes, bool], ...] = (
    (
        b"    try\n",
        b"    # P7_D2_SCHEDULE_MARKER_BLOCK_1_BEGIN\n"
        b"    d2_marker_segment_ordinal = 0\n"
        b"    d2_marker_composite_ordinal = 0\n"
        b"    d2_marker_label = \"\"\n"
        b"    # P7_D2_SCHEDULE_MARKER_BLOCK_1_END\n",
        True,
    ),
    (
        b"        for stage in stages\n",
        b"            # P7_D2_SCHEDULE_MARKER_BLOCK_2_BEGIN\n"
        b"            d2_marker_segment_ordinal += 1\n"
        b"            d2_marker_composite_ordinal = 0\n"
        b"            d2_marker_label = P7_D2_MARKER_SEGMENT_LABELS[\n"
        b"                d2_marker_segment_ordinal\n"
        b"            ]\n"
        b"            p7_d2_emit(\"STEP3_SEGMENT_$(d2_marker_label)_STARTED\")\n"
        b"            # P7_D2_SCHEDULE_MARKER_BLOCK_2_END\n",
        False,
    ),
    (
        b"                completed_composites += 1\n",
        b"                # P7_D2_SCHEDULE_MARKER_BLOCK_3_BEGIN\n"
        b"                d2_marker_composite_ordinal += 1\n"
        b"                if d2_marker_composite_ordinal == P7_D2_MARKER_CHECKPOINT_1[\n"
        b"                    d2_marker_segment_ordinal\n"
        b"                ]\n"
        b"                    p7_d2_emit(\n"
        b"                        \"STEP3_SEGMENT_$(d2_marker_label)_CHECKPOINT_1_REACHED\",\n"
        b"                    )\n"
        b"                elseif d2_marker_composite_ordinal == P7_D2_MARKER_CHECKPOINT_2[\n"
        b"                    d2_marker_segment_ordinal\n"
        b"                ]\n"
        b"                    p7_d2_emit(\n"
        b"                        \"STEP3_SEGMENT_$(d2_marker_label)_CHECKPOINT_2_REACHED\",\n"
        b"                    )\n"
        b"                end\n"
        b"                # P7_D2_SCHEDULE_MARKER_BLOCK_3_END\n",
        False,
    ),
    (
        b"        end\n    catch error_value\n",
        b"            # P7_D2_SCHEDULE_MARKER_BLOCK_4_BEGIN\n"
        b"            d2_marker_composite_ordinal == P7_D2_MARKER_COMPOSITE_COUNTS[\n"
        b"                d2_marker_segment_ordinal\n"
        b"            ] || error(\"P7 D2 marker composite-count drift\")\n"
        b"            p7_d2_emit(\"STEP3_SEGMENT_$(d2_marker_label)_RETURNED\")\n"
        b"            # P7_D2_SCHEDULE_MARKER_BLOCK_4_END\n",
        True,
    ),
)
MARKER_BLOCK_FORBIDDEN_TOKENS = (
    b"observable", b"cache", b"majoranas", b"coefficient", b"mask",
    b"ticks", b"defect", b"threshold", b"budget", b"resource",
    b"selection", b"retained", b"term_stream", b"digest",
    b"final_state", b"completed_boundaries", b"cap_event",
)
INVALID_D2_PROBE_EXIT_CODE = 66


OUTER_ALLOWED_EVENTS = (
    "D2_RUNNER_STARTED",
    "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D2_STATIC_SETUP_COMPLETED",
    "STEP1_ENGINE_STARTED",
    "STEP1_ENGINE_RETURNED",
    "STEP1_FINALIZER_STARTED",
    "STEP1_FINALIZER_RETURNED",
    "STEP1_DETERMINISTIC_CAP_TERMINAL",
    "STEP1_TO_STEP2_HANDOFF_COMPLETED",
    "STEP2_ENGINE_STARTED",
    "STEP2_ENGINE_RETURNED",
    "STEP2_FINALIZER_STARTED",
    "STEP2_FINALIZER_RETURNED",
    "STEP2_DETERMINISTIC_CAP_TERMINAL",
    "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_FAILED_TERMINAL",
    "STEP2_TO_STEP3_HANDOFF_COMPLETED",
    "STEP3_ENGINE_STARTED",
    "STEP3_ENGINE_RETURNED",
    "STEP3_FINALIZER_STARTED",
    "STEP3_FINALIZER_RETURNED",
    "STEP3_DETERMINISTIC_CAP_TERMINAL",
    "D2_DIAGNOSTIC_SERIALIZATION_STARTED",
    "D2_DIAGNOSTIC_SERIALIZATION_RETURNED",
    "D2_DIAGNOSTIC_COMPLETED",
)
SEGMENT_LABELS = tuple("ABCDEFGHI")
INTERNAL_SCHEDULE_EVENTS = tuple(
    f"STEP3_SEGMENT_{label}_{suffix}"
    for label in SEGMENT_LABELS
    for suffix in ("STARTED", "CHECKPOINT_1_REACHED",
                   "CHECKPOINT_2_REACHED", "RETURNED")
)
UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS = tuple(range(4, 36, 4))
STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS = tuple(
    size for size in range(1, len(INTERNAL_SCHEDULE_EVENTS) + 1)
    if size not in UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS
)
ALLOWED_EVENTS = OUTER_ALLOWED_EVENTS + INTERNAL_SCHEDULE_EVENTS
SEGMENT_MAP = (
    ("A", "H1", 64, 22, 43),
    ("B", "H2", 48, 16, 32),
    ("C", "HU", 64, 22, 43),
    ("D", "H3", 48, 16, 32),
    ("E", "H4", 64, 22, 43),
    ("F", "H3", 48, 16, 32),
    ("G", "HU", 64, 22, 43),
    ("H", "H2", 48, 16, 32),
    ("I", "H1", 64, 22, 43),
)

_COMMON_TO_STEP3 = (
    "D2_RUNNER_STARTED",
    "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D2_STATIC_SETUP_COMPLETED",
    "STEP1_ENGINE_STARTED",
    "STEP1_ENGINE_RETURNED",
    "STEP1_FINALIZER_STARTED",
    "STEP1_FINALIZER_RETURNED",
    "STEP1_TO_STEP2_HANDOFF_COMPLETED",
    "STEP2_ENGINE_STARTED",
    "STEP2_ENGINE_RETURNED",
    "STEP2_FINALIZER_STARTED",
    "STEP2_FINALIZER_RETURNED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
    "STEP2_TO_STEP3_HANDOFF_COMPLETED",
    "STEP3_ENGINE_STARTED",
)
_SERIALIZATION_SUFFIX = (
    "D2_DIAGNOSTIC_SERIALIZATION_STARTED",
    "D2_DIAGNOSTIC_SERIALIZATION_RETURNED",
    "D2_DIAGNOSTIC_COMPLETED",
)
FIXED_TERMINAL_SEQUENCES = {
    "FULL_PATH_RETURNED": list(
        _COMMON_TO_STEP3 + INTERNAL_SCHEDULE_EVENTS + (
            "STEP3_ENGINE_RETURNED",
            "STEP3_FINALIZER_STARTED",
            "STEP3_FINALIZER_RETURNED",
        ) + _SERIALIZATION_SUFFIX
    ),
    "STEP1_DETERMINISTIC_CAP": [
        "D2_RUNNER_STARTED",
        "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D2_STATIC_SETUP_COMPLETED",
        "STEP1_ENGINE_STARTED",
        "STEP1_ENGINE_RETURNED",
        "STEP1_FINALIZER_STARTED",
        "STEP1_FINALIZER_RETURNED",
        "STEP1_DETERMINISTIC_CAP_TERMINAL",
        *_SERIALIZATION_SUFFIX,
    ],
    "STEP2_DETERMINISTIC_CAP": [
        "D2_RUNNER_STARTED",
        "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D2_STATIC_SETUP_COMPLETED",
        "STEP1_ENGINE_STARTED",
        "STEP1_ENGINE_RETURNED",
        "STEP1_FINALIZER_STARTED",
        "STEP1_FINALIZER_RETURNED",
        "STEP1_TO_STEP2_HANDOFF_COMPLETED",
        "STEP2_ENGINE_STARTED",
        "STEP2_ENGINE_RETURNED",
        "STEP2_DETERMINISTIC_CAP_TERMINAL",
        *_SERIALIZATION_SUFFIX,
    ],
    "P6_PREFIX_RESOURCE_CONFORMANCE_FAILURE": [
        "D2_RUNNER_STARTED",
        "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D2_STATIC_SETUP_COMPLETED",
        "STEP1_ENGINE_STARTED",
        "STEP1_ENGINE_RETURNED",
        "STEP1_FINALIZER_STARTED",
        "STEP1_FINALIZER_RETURNED",
        "STEP1_TO_STEP2_HANDOFF_COMPLETED",
        "STEP2_ENGINE_STARTED",
        "STEP2_ENGINE_RETURNED",
        "STEP2_FINALIZER_STARTED",
        "STEP2_FINALIZER_RETURNED",
        "P6_PREFIX_RESOURCE_CONFORMANCE_FAILED_TERMINAL",
        *_SERIALIZATION_SUFFIX,
    ],
}

STAGED_PATHS = tuple(D0.STAGED_PATHS) + (FIXTURE_NAME, PROBE_DRIVER)
SOURCE_PATHS = tuple((
    *STAGED_PATHS,
    D0_ORCHESTRATOR_NAME,
    D0_POLICY_NAME,
    D1_ORCHESTRATOR_NAME,
    D1_POLICY_NAME,
    D1_FIXTURE_NAME,
    Path(__file__).name,
    TEST_NAME,
))
PREPROBE_CHANGED_PATHS = frozenset({
    f"docs/research/fermion-frontier/{POLICY_NAME}",
    f"docs/research/fermion-frontier/{FIXTURE_NAME}",
    f"docs/research/fermion-frontier/{Path(__file__).name}",
    f"docs/research/fermion-frontier/{PROBE_DRIVER}",
    f"docs/research/fermion-frontier/{TEST_NAME}",
})

OBSERVATION_FIELDS = {
    "status", "diagnostic_terminal_branch", "process_started",
    "process_returncode", "outer_timeout_triggered",
    "outer_monotonic_elapsed_ns", "stdout_bytes", "stdout_sha256",
    "stderr_bytes", "stderr_sha256", "time_diagnostics",
    "phase_trace_status", "phase_events", "phase_event_count",
    "phase_trace_protocol_sha256", "phase_channel_bytes",
    "phase_channel_sha256", "phase_channel_eof", "last_phase_event",
    "resource_witness", "host_failure_has_no_mathematical_authority",
}
PHASE_EVENT_REPORT_FIELDS = {
    "sequence", "event", "outer_receive_elapsed_ns",
}
S0_ADMISSION = {
    "status": "NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC",
    "derived_from_D2": False,
    "D1_status_unchanged": D1_ADMISSION_STATUS,
    "same_host_admission_as_D0_and_D1": True,
}


class ProbeError(RuntimeError):
    """Fail-closed P7 D2 validation error."""


canonical_bytes = D0.canonical_bytes
canonical_sha256 = D0.canonical_sha256
file_sha256 = D0.file_sha256
loads_json = D0.loads_json
load_json = D0.load_json


def _run_git(*args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args], cwd=BASE, check=check, capture_output=True,
    )
    return process.stdout.decode("utf-8").strip()


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise ProbeError("P7 D2 source_files is empty or malformed")
    pins: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "size_bytes", "sha256",
        }:
            raise ProbeError("malformed P7 D2 source pin")
        relative = row["relative_path"]
        if not isinstance(relative, str) or relative in pins:
            raise ProbeError("duplicate or invalid P7 D2 source pin")
        pins[relative] = row
    return pins


def _step3_cap_sequences() -> list[list[str]]:
    # A CapExceeded is caught only after a segment STARTED/checkpoint marker,
    # or by the final cap precheck after all 36 internal markers.  There is no
    # cap-raising operation between an A--H RETURNED marker and the next
    # segment's STARTED marker, so those eight prefix lengths are unreachable.
    return [
        list(_COMMON_TO_STEP3 + INTERNAL_SCHEDULE_EVENTS[:size] + (
            "STEP3_ENGINE_RETURNED",
            "STEP3_DETERMINISTIC_CAP_TERMINAL",
        ) + _SERIALIZATION_SUFFIX)
        for size in STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS
    ]


def _terminal_paths() -> list[tuple[str, list[str]]]:
    paths = list(FIXED_TERMINAL_SEQUENCES.items())
    paths.extend(
        ("STEP3_DETERMINISTIC_CAP", sequence)
        for sequence in _step3_cap_sequences()
    )
    return paths


def _classify_event_names(names: list[str]) -> tuple[bool, str | None]:
    matching = [
        (branch, sequence) for branch, sequence in _terminal_paths()
        if names == sequence[:len(names)]
    ]
    if not matching:
        return False, None
    exact = [(branch, sequence) for branch, sequence in matching
             if names == sequence]
    branches = {branch for branch, _ in exact}
    if len(exact) > 1 or len(branches) > 1:
        raise ProbeError("INVALID_D2_PROBE: ambiguous phase terminal")
    return True, next(iter(branches)) if branches else None


def _validate_d1_parent(fixture: Mapping[str, Any]) -> Mapping[str, Any]:
    report_path = BASE / D1_REPORT_NAME
    if not report_path.is_file() or report_path.is_symlink():
        raise ProbeError("P7 D2 frozen D1 parent report is missing")
    body = report_path.read_bytes()
    if (
        len(body) != D1_REPORT_SIZE_BYTES
        or hashlib.sha256(body).hexdigest() != D1_REPORT_SHA256
    ):
        raise ProbeError("P7 D2 frozen D1 parent report bytes drift")
    try:
        report = D1.validate_report(loads_json(body, D1_REPORT_NAME))
    except (D0.ProbeError, D1.ProbeError) as error:
        raise ProbeError("P7 D2 frozen D1 parent report is invalid") from error
    observation = report.get("observation")
    if (
        report.get("report_type") != D1.REPORT_TYPE
        or report.get("scientific_authority") != "NONE"
        or not isinstance(observation, dict)
        or observation.get("status") != D1_TERMINAL_STATUS
        or observation.get("last_phase_event") != D1_LAST_PHASE_EVENT
        or observation.get("resource_witness") is not None
        or report.get("S0_admission", {}).get("status")
        != D1_ADMISSION_STATUS
    ):
        raise ProbeError("P7 D2 allowed D1 parent facts drift")
    if "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED" not in {
        row.get("event") for row in observation.get("phase_events", [])
        if isinstance(row, dict)
    }:
        raise ProbeError("P7 D2 D1 localization fact drift")
    return report


def _extract_function(
    body: bytes, function_name: bytes, *, following_name: bytes,
) -> bytes:
    opening = b"function " + function_name + b"("
    if body.count(opening) != 1:
        raise ProbeError("P7 D2 function-slice opening anchor drift")
    start = body.index(opening)
    closing = b"\nfunction " + following_name + b"("
    if body.count(closing, start) != 1:
        raise ProbeError("P7 D2 function-slice closing anchor drift")
    end = body.index(closing, start)
    # Exactly the function bytes through its final `end\n`; the separating
    # blank line before the next function is not part of either frozen slice.
    return body[start:end]


def _validate_instrumented_kernel() -> dict[str, Any]:
    frozen_path = BASE / P6_RUNNER_NAME
    driver_path = BASE / PROBE_DRIVER
    for path, label in ((frozen_path, "P6 runner"), (driver_path, "D2 driver")):
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"P7 D2 {label} is missing or nonregular")
    frozen_body = frozen_path.read_bytes()
    if hashlib.sha256(frozen_body).hexdigest() != P6_RUNNER_SHA256:
        raise ProbeError("P7 D2 frozen P6 runner bytes drift")
    frozen_function = _extract_function(
        frozen_body, P6_FUNCTION_NAME, following_name=b"main_p6",
    )
    if hashlib.sha256(frozen_function).hexdigest() != P6_FUNCTION_SLICE_SHA256:
        raise ProbeError("P7 D2 frozen P6 function slice drift")
    if len(MARKER_INSERTIONS) != 4:
        raise ProbeError("P7 D2 marker insertion blocks are not frozen")

    expected = frozen_function
    old_opening = b"function " + P6_FUNCTION_NAME + b"("
    new_opening = b"function " + D2_FUNCTION_NAME + b"("
    if expected.count(old_opening) != 1:
        raise ProbeError("P7 D2 frozen function-name anchor drift")
    expected = expected.replace(old_opening, new_opening, 1)
    blocks: list[bytes] = []
    for anchor, block, insert_before in MARKER_INSERTIONS:
        if not anchor or not block or expected.count(anchor) != 1:
            raise ProbeError("P7 D2 marker insertion anchor drift")
        lowered = block.lower()
        if any(token in lowered for token in MARKER_BLOCK_FORBIDDEN_TOKENS):
            raise ProbeError("P7 D2 marker block references live scientific state")
        expected = expected.replace(
            anchor, (block + anchor) if insert_before else (anchor + block), 1,
        )
        blocks.append(block)

    driver_body = driver_path.read_bytes()
    actual = _extract_function(
        driver_body, D2_FUNCTION_NAME,
        following_name=b"p7_d2_execute_adaptive_step",
    )
    if actual != expected:
        raise ProbeError("P7 D2 instrumented function is not byte-derived from P6")

    reversed_slice = actual
    for block in reversed(blocks):
        if reversed_slice.count(block) != 1:
            raise ProbeError("P7 D2 marker block multiplicity drift")
        reversed_slice = reversed_slice.replace(block, b"", 1)
    if reversed_slice.count(new_opening) != 1:
        raise ProbeError("P7 D2 reverse function-name anchor drift")
    reversed_slice = reversed_slice.replace(new_opening, old_opening, 1)
    if reversed_slice != frozen_function:
        raise ProbeError("P7 D2 reverse-deleted function differs from P6")
    return {
        "frozen_P6_runner_sha256": P6_RUNNER_SHA256,
        "frozen_P6_function_slice_sha256": P6_FUNCTION_SLICE_SHA256,
        "instrumented_D2_function_slice_sha256":
            hashlib.sha256(actual).hexdigest(),
        "exact_function_name_substitution_count": 1,
        "exact_marker_insertion_block_count": 4,
        "forward_byte_construction_matches": True,
        "reverse_deletion_matches_frozen_P6_function": True,
        "marker_blocks_contain_no_live_scientific_state_tokens": True,
    }


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    if not isinstance(fixture, dict):
        raise ProbeError("P7 D2 fixture is not an object")
    if canonical_sha256(fixture) != FIXTURE_CANONICAL_SHA256:
        raise ProbeError("P7 D2 fixture semantic object drift")
    required = {
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "diagnostic_role",
        "D1_parent_custody", "frozen_candidate_identity",
        "frozen_execution_relation", "phase_event_protocol",
        "phase_channel_custody", "host_supervisor_caps", "runtime_custody",
        "observation_scope", "authority_exclusions",
        "step3_schedule_marker_map", "scientific_kernel_byte_equivalence",
    }
    if set(fixture) != required:
        raise ProbeError("P7 D2 fixture top-level key drift")
    if (
        fixture.get("schema_version") != 1
        or type(fixture.get("schema_version")) is not int
        or fixture.get("fixture_id") != FIXTURE_ID
        or fixture.get("required_direct_parent_commit") != DIRECT_PARENT
        or fixture.get("scientific_authority") != "NONE"
        or fixture.get("certificate_eligible") is not False
        or fixture.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P7 D2 fixture identity or authority drift")
    identity = fixture["frozen_candidate_identity"]
    if (
        identity.get("candidate_id") != CANDIDATE_ID
        or identity.get("scientific_probe_mode") != SCIENTIFIC_PROBE_MODE
        or identity.get("D2_diagnostic_mode") != DIAGNOSTIC_MODE
        or identity.get("algorithm_id") != ALGORITHM_ID
        or identity.get("D2_does_not_define_a_new_scientific_candidate")
        is not True
    ):
        raise ProbeError("P7 D2 frozen candidate identity drift")
    parent = fixture["D1_parent_custody"]
    if (
        parent.get("result_commit_sha") != DIRECT_PARENT
        or parent.get("report_relative_path") != D1_REPORT_NAME
        or parent.get("report_sha256") != D1_REPORT_SHA256
        or parent.get("report_type") != D1.REPORT_TYPE
        or parent.get("scientific_authority") != "NONE"
        or parent.get("phase_trace_status") != "LEGAL_PREFIX_INTERRUPTED"
        or parent.get("P6_prefix_resource_conformance_passed_marker_reached")
        is not True
        or parent.get("step3_engine_started_marker_reached") is not True
        or parent.get("step3_engine_returned_marker_reached") is not False
        or parent.get("step3_finalizer_started_marker_reached") is not False
        or parent.get("step3_finalizer_returned_marker_reached") is not False
        or parent.get("resource_witness_is_null") is not True
        or parent.get("future_S0_admission_status") != D1_ADMISSION_STATUS
        or parent.get("allowed_result_informed_facts_are_exhaustive") is not True
    ):
        raise ProbeError("P7 D2 D1-parent custody drift")
    protocol = fixture["phase_event_protocol"]
    if (
        canonical_sha256(protocol) != PHASE_PROTOCOL_CANONICAL_SHA256
        or protocol.get("wire_record_exact_fields") != ["event", "sequence"]
        or protocol.get("sequence_origin") != 0
        or protocol.get("sequence_is_contiguous") is not True
        or protocol.get("maximum_event_count") != 57
        or protocol.get("maximum_line_bytes_including_newline") != 256
        or protocol.get("maximum_total_channel_bytes") != 8192
        or protocol.get("allowed_events") != list(ALLOWED_EVENTS)
    ):
        raise ProbeError("P7 D2 phase protocol envelope drift")
    expected_fixed = {
        key: value for key, value in FIXED_TERMINAL_SEQUENCES.items()
        if key != "FULL_PATH_RETURNED"
    }
    if protocol.get("fixed_legal_terminal_sequences") != expected_fixed:
        raise ProbeError("P7 D2 fixed phase terminal sequences drift")
    if (
        protocol.get("step3_internal_event_sequence")
        != list(INTERNAL_SCHEDULE_EVENTS)
        or protocol.get("full_success_sequence")
        != FIXED_TERMINAL_SEQUENCES["FULL_PATH_RETURNED"]
        or protocol.get("all_legal_terminal_branches") != [
            "FULL_PATH_RETURNED", "STEP1_DETERMINISTIC_CAP",
            "STEP2_DETERMINISTIC_CAP",
            "P6_PREFIX_RESOURCE_CONFORMANCE_FAILURE",
            "STEP3_DETERMINISTIC_CAP",
        ]
    ):
        raise ProbeError("P7 D2 full-success phase grammar drift")
    grammar = protocol.get("parameterized_step3_deterministic_cap_terminal")
    if not isinstance(grammar, dict):
        raise ProbeError("P7 D2 step3 deterministic-cap grammar is missing")
    if (
        grammar.get("branch_name") != "STEP3_DETERMINISTIC_CAP"
        or grammar.get("fixed_prefix_through_engine_started")
        != list(_COMMON_TO_STEP3)
        or grammar.get("internal_prefix_source")
        != "step3_internal_event_sequence"
        or grammar.get("minimum_internal_prefix_event_count") != 1
        or grammar.get("maximum_internal_prefix_event_count") != 36
        or grammar.get("allowed_internal_prefix_event_counts")
        != list(STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS)
        or grammar.get(
            "forbidden_segment_returned_prefix_event_counts_without_next_"
            "segment_started"
        ) != list(UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS)
        or grammar.get("exact_reachable_internal_prefix_event_count_cardinality")
        != len(STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS)
        or grammar.get("exact_suffix_after_internal_prefix") != [
            "STEP3_ENGINE_RETURNED", "STEP3_DETERMINISTIC_CAP_TERMINAL",
            *_SERIALIZATION_SUFFIX,
        ]
        or grammar.get(
            "engine_return_after_zero_internal_events_is_forbidden_for_a_"
            "deterministic_cap"
        ) is not True
        or grammar.get(
            "segment_returned_must_be_followed_by_the_next_segment_started_"
            "before_an_engine_cap_return_except_after_all_36_internal_events"
        ) is not True
        or grammar.get(
            "all_36_internal_events_then_engine_returned_may_reach_a_cap_"
            "only_via_the_frozen_final_cap_precheck"
        ) is not True
    ):
        raise ProbeError("P7 D2 step3 deterministic-cap grammar drift")
    d0_fixture = D0._validate_fixture(load_json(BASE / D0_FIXTURE_NAME))
    if fixture["host_supervisor_caps"] != d0_fixture["host_supervisor_caps"]:
        raise ProbeError("P7 D2 host admission differs from D0/D1")
    if fixture["runtime_custody"] != d0_fixture["runtime_custody"]:
        raise ProbeError("P7 D2 runtime custody differs from D0/D1")
    D0._validate_runtime_lock_bytes(fixture["runtime_custody"])
    channel = fixture["phase_channel_custody"]
    if (
        channel.get("transport")
        != "dedicated_inherited_anonymous_pipe_file_descriptor"
        or channel.get("wire_records_are_single_atomic_POSIX_pipe_writes")
        is not True
        or channel.get("stdout_is_strictly_empty") is not True
        or channel.get("stderr_is_not_a_phase_channel") is not True
        or channel.get("raw_channel_bytes_are_not_persisted") is not True
    ):
        raise ProbeError("P7 D2 phase-channel custody drift")
    scope = fixture["observation_scope"]
    if (
        scope.get("resource_witness", object()) is not None
        or scope.get("scientific_values_are_forbidden") is not True
        or scope.get("completed_D2_does_not_establish_future_S0_admission")
        is not True
    ):
        raise ProbeError("P7 D2 observation scope drift")
    if not isinstance(fixture["authority_exclusions"], list):
        raise ProbeError("P7 D2 authority exclusions drift")
    _validate_d1_parent(fixture)
    _validate_instrumented_kernel()
    return fixture


def validate_policy(
    policy: Any, *, require_report_absent: bool,
) -> Mapping[str, Any]:
    if not isinstance(policy, dict):
        raise ProbeError("P7 D2 policy is not an object")
    semantic = {key: value for key, value in policy.items()
                if key != "source_files"}
    if canonical_sha256(semantic) != POLICY_SEMANTIC_SHA256:
        raise ProbeError("P7 D2 policy semantic object drift")
    required = {
        "schema_version", "policy_id", "policy_fingerprint",
        "required_direct_parent_commit", "policy_role",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "hindsight_firewall",
        "candidate_identity", "frozen_D1_dependency",
        "phase_event_protocol", "static_schedule_marker_policy",
        "scientific_kernel_byte_equivalence_policy",
        "phase_channel_permissions", "D2_observation_contract",
        "host_supervisor_caps", "runtime",
        "state_custody_and_runner_visibility", "staged_source_custody",
        "preprobe_and_result_lifecycle", "stop_rules",
        "authority_exclusions", "source_file_pins_status",
        "exact_source_file_count", "source_files",
    }
    if set(policy) != required:
        raise ProbeError("P7 D2 policy top-level key drift")
    if (
        policy.get("schema_version") != 1
        or type(policy.get("schema_version")) is not int
        or policy.get("policy_id") != POLICY_ID
        or policy.get("required_direct_parent_commit") != DIRECT_PARENT
        or policy.get("scientific_authority") != "NONE"
        or policy.get("certificate_eligible") is not False
        or policy.get("result_contract_eligible") is not False
        or policy.get("source_file_pins_status") != "FROZEN_EXACT"
        or policy.get("exact_source_file_count") != len(SOURCE_PATHS)
    ):
        raise ProbeError("P7 D2 policy identity or authority drift")
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    if policy["candidate_identity"] != fixture["frozen_candidate_identity"]:
        raise ProbeError("P7 D2 policy candidate identity drift")
    policy_protocol = policy["phase_event_protocol"]
    if (
        policy_protocol.get("fixture_phase_event_protocol_canonical_sha256")
        != PHASE_PROTOCOL_CANONICAL_SHA256
        or policy_protocol.get("allowed_event_count") != len(ALLOWED_EVENTS)
        or policy_protocol.get("ordered_step3_internal_event_count")
        != len(INTERNAL_SCHEDULE_EVENTS)
        or policy_protocol.get(
            "reachable_step3_deterministic_cap_internal_prefix_event_counts"
        ) != list(STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS)
        or policy_protocol.get(
            "unreachable_segment_returned_cap_prefix_event_counts"
        ) != list(UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS)
        or policy_protocol.get(
            "exact_reachable_step3_deterministic_cap_terminal_count"
        ) != len(STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS)
    ):
        raise ProbeError("P7 D2 policy phase protocol drift")
    dependency = dict(policy["frozen_D1_dependency"])
    if dependency.pop("report_size_bytes", None) != D1_REPORT_SIZE_BYTES:
        raise ProbeError("P7 D2 policy D1 report-size custody drift")
    if dependency != fixture["D1_parent_custody"]:
        raise ProbeError("P7 D2 policy D1 dependency drift")
    if policy["host_supervisor_caps"] != fixture["host_supervisor_caps"]:
        raise ProbeError("P7 D2 policy host admission drift")
    if policy["runtime"] != fixture["runtime_custody"]:
        raise ProbeError("P7 D2 policy runtime custody drift")
    if policy["authority_exclusions"] != fixture["authority_exclusions"]:
        raise ProbeError("P7 D2 policy authority exclusions drift")
    observation = policy["D2_observation_contract"]
    if (
        observation.get("report_observation_exact_fields")
        != sorted(OBSERVATION_FIELDS)
        or observation.get("report_phase_event_exact_fields")
        != sorted(PHASE_EVENT_REPORT_FIELDS)
        or observation.get("resource_witness_is_always_null") is not True
        or observation.get("S0_admission") != S0_ADMISSION
    ):
        raise ProbeError("P7 D2 observation contract drift")
    staged = policy["staged_source_custody"]
    if (
        staged.get("staged_path_order") != list(STAGED_PATHS)
        or staged.get("exact_staged_path_count") != len(STAGED_PATHS)
    ):
        raise ProbeError("P7 D2 staged-source custody drift")
    pins = _source_pins(policy)
    if set(pins) != set(SOURCE_PATHS):
        raise ProbeError("P7 D2 source pin allowlist drift")
    for relative, row in pins.items():
        path = BASE / relative
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"missing or nonregular P7 D2 source: {relative}")
        body = path.read_bytes()
        if (
            row.get("size_bytes") != len(body)
            or row.get("sha256") != hashlib.sha256(body).hexdigest()
        ):
            raise ProbeError(f"P7 D2 source pin drift: {relative}")
    if require_report_absent and (BASE / REPORT_NAME).exists():
        raise ProbeError("P7 D2 report exists before the preprobe commit")
    claim = BASE / EXECUTION_CLAIM_NAME
    if require_report_absent and (claim.exists() or claim.is_symlink()):
        raise ProbeError("P7 D2 execution claim already exists")
    return policy


def stage_probe_tree(
    staging: Path, policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pins = _source_pins(policy)
    rows: list[dict[str, Any]] = []
    for relative in STAGED_PATHS:
        source = BASE / relative
        target = staging / relative
        if not source.is_file() or source.is_symlink():
            raise ProbeError(f"invalid P7 D2 staged source: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target, follow_symlinks=False)
        source_body = source.read_bytes()
        target_body = target.read_bytes()
        digest = hashlib.sha256(source_body).hexdigest()
        row = {
            "relative_path": relative,
            "repository_sha256": digest,
            "staged_size_bytes": len(target_body),
            "staged_sha256": hashlib.sha256(target_body).hexdigest(),
            "byte_identical_to_repository": target_body == source_body,
        }
        if (
            pins[relative]["sha256"] != digest
            or pins[relative]["size_bytes"] != len(source_body)
            or row["staged_sha256"] != digest
            or row["byte_identical_to_repository"] is not True
        ):
            raise ProbeError(f"P7 D2 staging custody failure: {relative}")
        rows.append(row)
    return rows


_PhaseCollector = D1._PhaseCollector
_BoundedStreamCollector = D1._BoundedStreamCollector


def _validate_phase_trace(
    collector: _PhaseCollector, fixture: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    if collector.overflow:
        raise ProbeError("INVALID_D2_PROBE: phase channel exceeded a frozen cap")
    if collector.trailing_partial:
        raise ProbeError("INVALID_D2_PROBE: phase channel ended with a partial line")
    allowed = set(fixture["phase_event_protocol"]["allowed_events"])
    events: list[dict[str, Any]] = []
    for expected_sequence, (line, received_ns) in enumerate(collector.lines):
        try:
            record = loads_json(line, "P7 D2 phase record")
        except D0.ProbeError as error:
            raise ProbeError("INVALID_D2_PROBE: malformed phase JSON") from error
        if (
            not isinstance(record, dict)
            or set(record) != {"event", "sequence"}
            or type(record.get("sequence")) is not int
            or record["sequence"] != expected_sequence
            or not isinstance(record.get("event"), str)
            or record["event"] not in allowed
            or line != canonical_bytes(record) + b"\n"
            or type(received_ns) is not int or received_ns < 0
        ):
            raise ProbeError("INVALID_D2_PROBE: phase record protocol drift")
        events.append({
            "sequence": expected_sequence,
            "event": record["event"],
            "outer_receive_elapsed_ns": received_ns,
        })
    legal, terminal = _classify_event_names(
        [row["event"] for row in events],
    )
    if not legal:
        raise ProbeError("INVALID_D2_PROBE: phase trace is not a legal DFA prefix")
    return events, terminal


def _observation_from_process(
    *, process_started: bool, returncode: int, timed_out: bool,
    stdout_bytes: int, stdout_sha256: str, stderr_bytes: int,
    stderr_sha256: str, stderr_for_time: bytes, elapsed_ns: int,
    collector: _PhaseCollector, fixture: Mapping[str, Any],
) -> dict[str, Any]:
    transport_failed = collector.read_failure or not collector.eof
    events, terminal_branch = _validate_phase_trace(collector, fixture)
    if stdout_bytes:
        raise ProbeError("INVALID_D2_PROBE: stdout must be exactly empty")
    if returncode == INVALID_D2_PROBE_EXIT_CODE:
        raise ProbeError("INVALID_D2_PROBE: Julia rejected custody or schema")
    host = fixture["host_supervisor_caps"]
    host_failed = (
        not process_started or timed_out or returncode != 0
        or stderr_bytes > host["maximum_stderr_bytes"]
        or elapsed_ns > host["outer_safety_timeout_seconds"] * 1_000_000_000
        or transport_failed
    )
    if host_failed:
        status = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        trace_status = "LEGAL_PREFIX_INTERRUPTED"
    else:
        if terminal_branch is None:
            raise ProbeError(
                "INVALID_D2_PROBE: clean exit lacks a complete terminal trace"
            )
        status = "COMPLETED_SCHEDULE_DIAGNOSTIC"
        trace_status = "COMPLETE_TERMINAL_SEQUENCE"
    protocol_rows = [
        {"sequence": row["sequence"], "event": row["event"]}
        for row in events
    ]
    observation = {
        "status": status,
        "diagnostic_terminal_branch": terminal_branch,
        "process_started": process_started,
        "process_returncode": returncode,
        "outer_timeout_triggered": timed_out,
        "outer_monotonic_elapsed_ns": elapsed_ns,
        "stdout_bytes": stdout_bytes,
        "stdout_sha256": stdout_sha256,
        "stderr_bytes": stderr_bytes,
        "stderr_sha256": stderr_sha256,
        "time_diagnostics": (
            D0._parse_time_stderr(stderr_for_time)
            if stderr_bytes <= host["maximum_stderr_bytes"] else {}
        ),
        "phase_trace_status": trace_status,
        "phase_events": events,
        "phase_event_count": len(events),
        "phase_trace_protocol_sha256": canonical_sha256(protocol_rows),
        "phase_channel_bytes": collector.total_bytes,
        "phase_channel_sha256": collector.sha256,
        "phase_channel_eof": collector.eof,
        "last_phase_event": events[-1]["event"] if events else None,
        "resource_witness": None,
        "host_failure_has_no_mathematical_authority": True,
    }
    _validate_observation(observation, fixture)
    return observation


def _terminate_scope(unit: str, process: subprocess.Popen[bytes]) -> None:
    D1._terminate_scope(unit, process)


def _validate_standard_fds_open() -> None:
    for descriptor in (0, 1, 2):
        try:
            os.fstat(descriptor)
        except OSError as error:
            raise ProbeError(
                f"P7 D2 standard file descriptor {descriptor} is closed"
            ) from error


def _run_candidate(
    staging: Path, julia: Path, depot: Path, fixture: Mapping[str, Any],
    scratch_root: Path,
) -> dict[str, Any]:
    host = fixture["host_supervisor_caps"]
    protocol = fixture["phase_event_protocol"]
    scratch = scratch_root / "candidate"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    unit = "majorana-p7-d2-schedule-" + uuid.uuid4().hex
    read_fd, write_fd = os.pipe()
    if read_fd < 3 or write_fd < 3:
        for descriptor in {read_fd, write_fd}:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise ProbeError("P7 D2 phase pipe reused a standard file descriptor")
    os.set_inheritable(write_fd, True)
    started_ns = time.monotonic_ns()
    collector = _PhaseCollector(
        read_fd, started_ns,
        max_line_bytes=protocol["maximum_line_bytes_including_newline"],
        max_total_bytes=protocol["maximum_total_channel_bytes"],
        max_events=protocol["maximum_event_count"],
    )
    reader = threading.Thread(
        target=collector.run, name="p7-d2-phase-reader", daemon=True,
    )
    reader.start()
    julia_command = [
        "/usr/bin/time", "-v", str(julia), "--startup-file=no",
        "--history-file=no", "--compiled-modules=no",
        f"--project={staging / 'majorana_certificate_p0'}",
        str(staging / PROBE_DRIVER),
        str(staging / FIXTURE_NAME),
        str(staging / D0_FIXTURE_NAME),
        str(staging / "majorana_certificate_p6_fixture.json"),
        str(staging / "majorana_certificate_p5_fixture.json"),
        str(staging / "majorana_certificate_p4_fixture.json"),
        str(staging / "majorana_certificate_p3_fixture.json"),
        str(staging / "majorana_certificate_p2_fixture.json"),
        DIAGNOSTIC_MODE, str(write_fd),
    ]
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"MemorySwapMax={host['MemorySwapMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}",
        "--", *julia_command,
    ]
    environment = os.environ.copy()
    environment.update({
        "HOME": str(scratch / "home"),
        "TMPDIR": str(scratch / "tmp"),
        "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
        "JULIA_DEPOT_PATH": f"{scratch / 'depot'}:{depot}",
        "JULIA_LOAD_PATH": "@", "JULIA_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1", "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
    })
    process: subprocess.Popen[bytes] | None = None
    stdout_collector: _BoundedStreamCollector | None = None
    stderr_collector: _BoundedStreamCollector | None = None
    stream_threads: list[threading.Thread] = []
    timed_out = False
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment, pass_fds=(write_fd,), close_fds=True,
        )
        os.close(write_fd)
        write_fd = -1
        if process.stdout is None or process.stderr is None:
            _terminate_scope(unit, process)
            raise ProbeError("P7 D2 child streams were not captured")
        stdout_collector = _BoundedStreamCollector(process.stdout, 0)
        stderr_collector = _BoundedStreamCollector(
            process.stderr, host["maximum_stderr_bytes"],
        )
        stream_threads = [
            threading.Thread(
                target=stdout_collector.run, name="p7-d2-stdout-reader",
                daemon=True,
            ),
            threading.Thread(
                target=stderr_collector.run, name="p7-d2-stderr-reader",
                daemon=True,
            ),
        ]
        for thread in stream_threads:
            thread.start()
        try:
            process.wait(timeout=host["outer_safety_timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_scope(unit, process)
        returncode = process.returncode
        process_started = True
    except OSError as error:
        if process is not None:
            if process.poll() is None:
                _terminate_scope(unit, process)
            raise ProbeError("P7 D2 supervisor failed after process launch") from error
        returncode = -1
        process_started = False
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        for thread in stream_threads:
            thread.join(timeout=10)
        for stream_collector, thread in zip(
            (stdout_collector, stderr_collector), stream_threads,
        ):
            if thread.is_alive() and stream_collector is not None:
                stream_collector.request_stop()
                thread.join(timeout=2)
        reader.join(timeout=10)
        if reader.is_alive():
            collector.request_stop()
            reader.join(timeout=2)
    elapsed_ns = time.monotonic_ns() - started_ns
    if reader.is_alive() or any(thread.is_alive() for thread in stream_threads):
        raise ProbeError("P7 D2 supervisor reader failed to terminate")
    if process_started:
        if (
            stdout_collector is None or stderr_collector is None
            or stdout_collector.read_failure or stderr_collector.read_failure
            or not stdout_collector.eof or not stderr_collector.eof
        ):
            raise ProbeError("P7 D2 stdout/stderr capture failed")
        stdout_bytes = stdout_collector.total_bytes
        stdout_sha256 = stdout_collector.sha256
        stderr_bytes = stderr_collector.total_bytes
        stderr_sha256 = stderr_collector.sha256
        stderr_for_time = bytes(stderr_collector.payload)
    else:
        stdout_bytes = 0
        stdout_sha256 = hashlib.sha256(b"").hexdigest()
        stderr_bytes = 0
        stderr_sha256 = hashlib.sha256(b"").hexdigest()
        stderr_for_time = b""
    return _observation_from_process(
        process_started=process_started, returncode=returncode,
        timed_out=timed_out, stdout_bytes=stdout_bytes,
        stdout_sha256=stdout_sha256, stderr_bytes=stderr_bytes,
        stderr_sha256=stderr_sha256, stderr_for_time=stderr_for_time,
        elapsed_ns=elapsed_ns, collector=collector, fixture=fixture,
    )


def _validate_preprobe_commit_identity(preprobe_commit: Any) -> None:
    if (
        not isinstance(preprobe_commit, str) or len(preprobe_commit) != 40
        or any(character not in "0123456789abcdef"
               for character in preprobe_commit)
    ):
        raise ProbeError("P7 D2 preprobe commit is not a full lowercase SHA-1")
    try:
        ancestry = _run_git("rev-list", "--parents", "-n", "1", preprobe_commit)
    except subprocess.CalledProcessError as error:
        raise ProbeError("P7 D2 preprobe commit is not present") from error
    if ancestry.split() != [preprobe_commit, DIRECT_PARENT]:
        raise ProbeError("P7 D2 preprobe commit has the wrong direct parent")
    changed = set(filter(None, _run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", preprobe_commit,
    ).splitlines()))
    if changed != PREPROBE_CHANGED_PATHS:
        raise ProbeError("P7 D2 preprobe changed-path allowlist drift")
    repository = BASE.parent.parent.parent
    for relative in sorted(PREPROBE_CHANGED_PATHS):
        current = repository / relative
        if not current.is_file() or current.is_symlink():
            raise ProbeError(f"P7 D2 current preprobe source is invalid: {relative}")
        blob = subprocess.run(
            ["git", "show", f"{preprobe_commit}:{relative}"], cwd=BASE,
            check=False, capture_output=True,
        )
        if blob.returncode != 0 or blob.stdout != current.read_bytes():
            raise ProbeError(f"P7 D2 preprobe blob custody drift: {relative}")
    artifact = f"{preprobe_commit}:docs/research/fermion-frontier/{REPORT_NAME}"
    if subprocess.run(
        ["git", "cat-file", "-e", artifact], cwd=BASE,
        check=False, capture_output=True,
    ).returncode == 0:
        raise ProbeError("P7 D2 report exists in the preprobe commit")


def _validate_preprobe_commit(preprobe_commit: str) -> None:
    _validate_preprobe_commit_identity(preprobe_commit)
    if _run_git("rev-parse", "HEAD") != preprobe_commit:
        raise ProbeError("P7 D2 HEAD differs from requested preprobe commit")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ProbeError("P7 D2 worktree is not clean before execution")


def _canonical_output_path(output: Path) -> Path:
    canonical = BASE / REPORT_NAME
    requested = Path(os.path.abspath(output))
    if requested != canonical:
        raise ProbeError("P7 D2 run output must be the canonical report path")
    if canonical.exists() or canonical.is_symlink():
        raise ProbeError("P7 D2 canonical report path already exists")
    return canonical


def _acquire_execution_claim(preprobe_commit: str) -> Path:
    claim = BASE / EXECUTION_CLAIM_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(claim, flags, 0o600)
    except FileExistsError as error:
        raise ProbeError("P7 D2 execution was already claimed") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write((preprobe_commit + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def _write_canonical_json_exclusive(path: Path, value: Any) -> None:
    payload = canonical_bytes(value) + b"\n"
    temporary = BASE / f".{REPORT_NAME}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def run_probe(
    preprobe_commit: str, julia: Path, depot: Path, output: Path,
) -> Mapping[str, Any]:
    policy = validate_policy(
        load_json(BASE / POLICY_NAME), require_report_absent=True,
    )
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    _validate_preprobe_commit(preprobe_commit)
    output = _canonical_output_path(output)
    julia = Path(julia).resolve()
    depot = Path(depot).resolve()
    if (
        not julia.is_file()
        or file_sha256(julia)
        != fixture["runtime_custody"]["julia_executable_sha256"]
    ):
        raise ProbeError("P7 D2 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P7 D2 depot is missing")
    for executable in ("systemd-run", "systemctl", "/usr/bin/time"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P7 D2 missing required executable: {executable}")
    with tempfile.TemporaryDirectory(prefix="majorana-p7-d2-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        staging_manifest = stage_probe_tree(staging, policy)
        scratch = root / "scratch"
        scratch.mkdir()
        _validate_standard_fds_open()
        execution_claim = _acquire_execution_claim(preprobe_commit)
        observation = _run_candidate(staging, julia, depot, fixture, scratch)
    report = {
        "schema_version": 1,
        "report_type": REPORT_TYPE,
        "policy_id": POLICY_ID,
        "policy_sha256": file_sha256(BASE / POLICY_NAME),
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": file_sha256(BASE / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(fixture),
        "preprobe_commit_sha": preprobe_commit,
        "D1_parent_result_commit_sha": DIRECT_PARENT,
        "D1_parent_report_sha256": D1_REPORT_SHA256,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "candidate": fixture["frozen_candidate_identity"],
        "staging_manifest": staging_manifest,
        "staging_manifest_sha256": canonical_sha256(staging_manifest),
        "instrumented_kernel_custody": _validate_instrumented_kernel(),
        "host_caps": fixture["host_supervisor_caps"],
        "observation": observation,
        "S0_admission": S0_ADMISSION,
        "authority_exclusions": fixture["authority_exclusions"],
    }
    validate_report(report)
    _write_canonical_json_exclusive(output, report)
    execution_claim.unlink()
    return report


def _validate_staging_manifest(
    rows: Any, policy: Mapping[str, Any], digest: Any,
) -> None:
    if (
        not isinstance(rows, list) or len(rows) != len(STAGED_PATHS)
        or [row.get("relative_path") for row in rows
            if isinstance(row, dict)] != list(STAGED_PATHS)
    ):
        raise ProbeError("P7 D2 staging manifest path drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "byte_identical_to_repository",
        }:
            raise ProbeError("malformed P7 D2 staging row")
        relative = row["relative_path"]
        body = (BASE / relative).read_bytes()
        expected = hashlib.sha256(body).hexdigest()
        if (
            row["repository_sha256"] != pins[relative]["sha256"]
            or row["staged_size_bytes"] != len(body)
            or row["staged_sha256"] != expected
            or row["repository_sha256"] != row["staged_sha256"]
            or row["byte_identical_to_repository"] is not True
        ):
            raise ProbeError("P7 D2 staging manifest custody drift")
    if digest != canonical_sha256(rows):
        raise ProbeError("P7 D2 staging manifest hash mismatch")


def _validate_observation(
    value: Any, fixture: Mapping[str, Any],
) -> None:
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS:
        raise ProbeError("malformed P7 D2 observation")
    if value["status"] not in {
        "COMPLETED_SCHEDULE_DIAGNOSTIC",
        "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
    }:
        raise ProbeError("unexpected P7 D2 observation status")
    for key in (
        "process_returncode", "outer_monotonic_elapsed_ns", "stdout_bytes",
        "stderr_bytes", "phase_event_count", "phase_channel_bytes",
    ):
        if type(value[key]) is not int:
            raise ProbeError(f"invalid P7 D2 observation integer: {key}")
    if (
        value["outer_monotonic_elapsed_ns"] <= 0
        or value["process_returncode"] == INVALID_D2_PROBE_EXIT_CODE
        or value["stdout_bytes"] != 0
        or value["stderr_bytes"] < 0
        or value["phase_event_count"] < 0
        or value["phase_channel_bytes"] < 0
        or not isinstance(value["process_started"], bool)
        or not isinstance(value["outer_timeout_triggered"], bool)
        or not isinstance(value["phase_channel_eof"], bool)
        or value["resource_witness"] is not None
        or value["host_failure_has_no_mathematical_authority"] is not True
    ):
        raise ProbeError("P7 D2 observation invariant drift")
    for key in (
        "stdout_sha256", "stderr_sha256", "phase_trace_protocol_sha256",
        "phase_channel_sha256",
    ):
        item = value[key]
        if (
            not isinstance(item, str) or len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
        ):
            raise ProbeError(f"invalid P7 D2 digest: {key}")
    if value["stdout_sha256"] != hashlib.sha256(b"").hexdigest():
        raise ProbeError("P7 D2 stdout digest is nonempty")
    events = value["phase_events"]
    if (
        not isinstance(events, list)
        or len(events) != value["phase_event_count"]
        or len(events) > 57
    ):
        raise ProbeError("P7 D2 phase event count drift")
    if not value["process_started"] and (
        value["process_returncode"] != -1
        or value["outer_timeout_triggered"]
        or events
        or value["stdout_bytes"] != 0
        or value["stderr_bytes"] != 0
        or value["stderr_sha256"] != hashlib.sha256(b"").hexdigest()
        or value["phase_channel_bytes"] != 0
        or value["time_diagnostics"] != {}
    ):
        raise ProbeError("unreachable P7 D2 process-not-started observation")
    previous_ns = -1
    protocol_rows: list[dict[str, Any]] = []
    raw = bytearray()
    for sequence, row in enumerate(events):
        if not isinstance(row, dict) or set(row) != PHASE_EVENT_REPORT_FIELDS:
            raise ProbeError("malformed P7 D2 reported phase event")
        if (
            row["sequence"] != sequence
            or row["event"] not in ALLOWED_EVENTS
            or type(row["outer_receive_elapsed_ns"]) is not int
            or row["outer_receive_elapsed_ns"] < previous_ns
            or row["outer_receive_elapsed_ns"]
            > value["outer_monotonic_elapsed_ns"]
        ):
            raise ProbeError("invalid P7 D2 reported phase event")
        previous_ns = row["outer_receive_elapsed_ns"]
        protocol_row = {"sequence": sequence, "event": row["event"]}
        protocol_rows.append(protocol_row)
        raw.extend(canonical_bytes(protocol_row) + b"\n")
    if (
        value["phase_trace_protocol_sha256"] != canonical_sha256(protocol_rows)
        or value["phase_channel_bytes"] != len(raw)
        or value["phase_channel_sha256"] != hashlib.sha256(raw).hexdigest()
        or value["last_phase_event"]
        != (events[-1]["event"] if events else None)
    ):
        raise ProbeError("P7 D2 phase trace custody mismatch")
    legal, terminal = _classify_event_names([row["event"] for row in events])
    if not legal:
        raise ProbeError("P7 D2 report phase DFA drift")
    host = fixture["host_supervisor_caps"]
    host_failed = (
        not value["process_started"] or value["outer_timeout_triggered"]
        or value["process_returncode"] != 0
        or value["stderr_bytes"] > host["maximum_stderr_bytes"]
        or value["outer_monotonic_elapsed_ns"]
        > host["outer_safety_timeout_seconds"] * 1_000_000_000
        or value["phase_channel_eof"] is not True
    )
    if value["status"] == "COMPLETED_SCHEDULE_DIAGNOSTIC":
        if (
            host_failed or terminal is None
            or value["diagnostic_terminal_branch"] != terminal
            or value["phase_trace_status"] != "COMPLETE_TERMINAL_SEQUENCE"
        ):
            raise ProbeError("invalid completed P7 D2 observation")
    elif (
        not host_failed
        or value["phase_trace_status"] != "LEGAL_PREFIX_INTERRUPTED"
        or value["diagnostic_terminal_branch"] != terminal
    ):
        raise ProbeError("invalid indeterminate P7 D2 observation")
    D0._validate_time_diagnostics(
        value["time_diagnostics"],
        completed=value["status"] == "COMPLETED_SCHEDULE_DIAGNOSTIC",
    )


def validate_report(report: Any) -> Mapping[str, Any]:
    policy = validate_policy(
        load_json(BASE / POLICY_NAME), require_report_absent=False,
    )
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    expected_top = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "D1_parent_result_commit_sha",
        "D1_parent_report_sha256", "scientific_authority",
        "certificate_eligible", "result_contract_eligible", "candidate",
        "staging_manifest", "staging_manifest_sha256",
        "instrumented_kernel_custody", "host_caps", "observation",
        "S0_admission", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected_top:
        raise ProbeError("malformed P7 D2 report")
    if (
        report.get("schema_version") != 1
        or type(report.get("schema_version")) is not int
        or report.get("report_type") != REPORT_TYPE
        or report.get("policy_id") != POLICY_ID
        or report.get("fixture_id") != FIXTURE_ID
        or report.get("D1_parent_result_commit_sha") != DIRECT_PARENT
        or report.get("D1_parent_report_sha256") != D1_REPORT_SHA256
        or report.get("scientific_authority") != "NONE"
        or report.get("certificate_eligible") is not False
        or report.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P7 D2 report identity or authority drift")
    if (
        report["policy_sha256"] != file_sha256(BASE / POLICY_NAME)
        or report["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME)
        or report["fixture_canonical_sha256"] != canonical_sha256(fixture)
        or report["candidate"] != fixture["frozen_candidate_identity"]
        or report["instrumented_kernel_custody"]
        != _validate_instrumented_kernel()
        or report["host_caps"] != fixture["host_supervisor_caps"]
        or report["S0_admission"] != S0_ADMISSION
        or report["authority_exclusions"] != fixture["authority_exclusions"]
    ):
        raise ProbeError("P7 D2 report source or scope custody drift")
    _validate_preprobe_commit_identity(report["preprobe_commit_sha"])
    _validate_staging_manifest(
        report["staging_manifest"], policy,
        report["staging_manifest_sha256"],
    )
    _validate_observation(report["observation"], fixture)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-preprobe", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--verify-report", action="store_true")
    parser.add_argument("--preprobe-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--output", type=Path, default=BASE / REPORT_NAME)
    args = parser.parse_args(argv)
    selected = sum(map(int, (
        args.verify_preprobe, args.run, args.verify_report,
    )))
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_preprobe:
        policy = validate_policy(
            load_json(BASE / POLICY_NAME), require_report_absent=True,
        )
        summary = {
            "status": "VERIFIED_P7_D2_SCHEDULE_PREPROBE",
            "policy_id": policy["policy_id"],
        }
    elif args.run:
        if not all((args.preprobe_commit, args.julia, args.depot)):
            parser.error("run requires preprobe commit, Julia, and depot")
        report = run_probe(
            args.preprobe_commit, args.julia, args.depot, args.output,
        )
        summary = {
            "status": "COMPLETED_P7_D2_SCHEDULE_PROBE",
            "report_sha256": file_sha256(args.output),
            "observation_status": report["observation"]["status"],
            "last_phase_event": report["observation"]["last_phase_event"],
            "S0_admission_status": report["S0_admission"]["status"],
        }
    else:
        report = validate_report(load_json(args.output))
        if args.output.read_bytes() != canonical_bytes(report) + b"\n":
            raise ProbeError("P7 D2 report is not canonical JSON plus newline")
        summary = {
            "status": "VERIFIED_P7_D2_SCHEDULE_REPORT",
            "report_sha256": file_sha256(args.output),
            "observation_status": report["observation"]["status"],
            "last_phase_event": report["observation"]["last_phase_event"],
            "S0_admission_status": report["S0_admission"]["status"],
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
