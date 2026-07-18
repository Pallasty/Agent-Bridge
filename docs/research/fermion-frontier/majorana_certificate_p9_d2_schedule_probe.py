#!/usr/bin/env python3
"""Freeze, run, and verify the P9-D2 fixed-schedule phase diagnostic.

P9-D2 is a one-fresh-process, phase-only successor to P9-D1.  It derives a
static clone from the frozen P9 source, emits only a bounded fixed-schedule
DFA, and stops before the P9-D0 resource-witness construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
ROOT = "docs/research/fermion-frontier/"
POLICY_NAME = "majorana_certificate_p9_d2_schedule_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p9_d2_schedule_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p9_d2_schedule_probe_report.json"
TEST_NAME = "test_majorana_certificate_p9_d2_schedule_probe.py"
CLONE_DRIVER = (
    "majorana_certificate_p9_d2_schedule_probe/"
    "majorana_p9_bit_order_step3_schedule_probe.jl"
)
EXECUTION_CLAIM_NAME = ".majorana_certificate_p9_d2_schedule_probe.execution-claimed"

POLICY_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D2-SCHEDULE-V1"
FIXTURE_ID = POLICY_ID
REPORT_TYPE = "majorana_p9_step3_e768_bitorder_schedule_report_d2_v1"

# D2 must be a direct child of the immutable P9-D1 B1 receipt.
D1_PREPROBE_COMMIT = "3fa2a4eecdc5c7363f58ff79c425efe1cfc25a13"
D1_RESULT_COMMIT = "47a34a4a0b39c616419c542a4c1b151f4aa9f8cc"
P9_PREPROBE_COMMIT = "ac2125eab524ec574c855a5931e51c7f9292f0c8"
P9_RESULT_COMMIT = "92629e3049ac0dfac12c390fc5ed499597076b7f"

D1_REPORT = "majorana_certificate_p9_d1_phase_probe_report.json"
D1_REPORT_SHA256 = "64cfad2b3de05620954b66df5ade380944e27d33d178ddc82eddbc496ad64faa"
D1_REPORT_SIZE = 7121
D1_FIXTURE = "majorana_certificate_p9_d1_phase_probe_fixture.json"
D1_FIXTURE_SHA256 = "4e9bdf1d496e33e2f8aaae88ddae1fb793358da63bb3417034d457eabe67eacc"
D1_FIXTURE_SIZE = 7213

P9_DRIVER = (
    "majorana_certificate_p9_bit_order_resource_probe/"
    "majorana_p9_bit_order_step3_resource_probe.jl"
)
P9_DRIVER_FULL_PATH = ROOT + P9_DRIVER
P9_DRIVER_SHA256 = "f12ea9a93d4079792de8b5e8bae5b5ee0b45895a4399c19f41b7041034d3f14c"
P9_DRIVER_SIZE = 78229
P9_FIXTURE = "majorana_certificate_p9_bit_order_resource_probe_fixture.json"
P9_FIXTURE_SHA256 = "8365f441765cc5dbe1658b8aba2e2371c1619a0894c73ad5c0b21f8bf74a1be8"
P9_FIXTURE_SIZE = 21575
P9_MODE = "E768_BITORDER_STEP3_V1"
P9_CANDIDATE = "E768-BITORDER-STEP3-V1"
P9_ALGORITHM_ID = "MAJORANA-P9-E768-BITORDER-STEP3-V1"
INVALID_D2_PROBE_EXIT_CODE = 66

RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
RUNTIME_LOCK_ID = "MAJORANA-P0-JULIA-1.11.9-LINUX-X86_64-V1"
RUNTIME_LOCK_SHA256 = "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17"
JULIA_EXECUTABLE_SHA256 = "2976d17aba35be5d546e8e315e521bd9be3e58c2e64abfd588f186696e807b7d"
MAJORANA_SOURCE_TREE_CLOSURE = {
    "file_count": 42,
    "total_bytes": 1875632,
    "closure_sha256": "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5",
}
PAULI_SOURCE_TREE_CLOSURE = {
    "file_count": 119,
    "total_bytes": 7736347,
    "closure_sha256": "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783",
}

FIXED_SEGMENTS = tuple("ABCDEFGHI")
FIXED_STAGE_GROUPS = ("H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1")
FIXED_SCHEDULE_MAP = (
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

STAGED_PATHS = (
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0/Manifest.toml",
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
    FIXTURE_NAME,
    CLONE_DRIVER,
)
PREPROBE_CHANGED_PATHS = (
    ROOT + POLICY_NAME,
    ROOT + FIXTURE_NAME,
    ROOT + Path(CLONE_DRIVER).as_posix(),
    ROOT + Path(__file__).name,
    ROOT + TEST_NAME,
)
RESULT_CHANGED_PATHS = (ROOT + REPORT_NAME,)
SOURCE_PATHS = tuple(dict.fromkeys((
    *STAGED_PATHS,
    RUNTIME_LOCK_NAME,
    Path(__file__).name,
    TEST_NAME,
    P9_DRIVER,
)))

D1_ALLOWED_PROJECTION = {
    "scientific_authority": "NONE",
    "terminal_status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
    "phase_trace_status": "LEGAL_PREFIX_INTERRUPTED",
    "certificate_eligible": False,
    "result_contract_eligible": False,
    "P6_prefix_resource_conformance_passed_marker_reached": True,
    "step3_engine_started_marker_reached": True,
    "step3_engine_returned_marker_reached": False,
    "resource_witness_is_null": True,
    "future_S0_admission_status": "NOT_ESTABLISHED_BY_P9_D1_COARSE_PHASE_DIAGNOSTIC",
}

SCHEDULE_EVENTS = tuple(
    f"STEP3_SEGMENT_{segment}_{checkpoint}"
    for segment in FIXED_SEGMENTS
    for checkpoint in (
        "STARTED",
        "CHECKPOINT_1_REACHED",
        "CHECKPOINT_2_REACHED",
        "RETURNED",
    )
)

PHASE_EVENTS = (
    "D2_RUNNER_STARTED",
    "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D2_STATIC_SETUP_COMPLETED",
    "P6_PREFIX_STARTED",
    "P6_PREFIX_RETURNED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
    "P6_PREFIX_RESOURCE_CONFORMANCE_NOT_ESTABLISHED_TERMINAL",
    "STEP3_ENGINE_STARTED",
    "STEP3_STATE_INITIALIZED",
    "STEP3_SCHEDULE_ENTERED",
    *SCHEDULE_EVENTS,
    "STEP3_SCHEDULE_RETURNED",
    "STEP3_ENGINE_RETURNED",
    "D2_DIAGNOSTIC_COMPLETED",
)


def _terminal_sequences() -> dict[str, list[str]]:
    prefix = [
        "D2_RUNNER_STARTED",
        "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D2_STATIC_SETUP_COMPLETED",
        "P6_PREFIX_STARTED",
        "P6_PREFIX_RETURNED",
    ]
    passed = prefix + [
        "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
        "STEP3_ENGINE_STARTED",
        "STEP3_STATE_INITIALIZED",
        "STEP3_SCHEDULE_ENTERED",
    ]
    result: dict[str, list[str]] = {
        "PREFIX_NOT_ESTABLISHED": prefix + [
            "P6_PREFIX_RESOURCE_CONFORMANCE_NOT_ESTABLISHED_TERMINAL",
            "D2_DIAGNOSTIC_COMPLETED",
        ],
    }
    for completed in range(1, len(SCHEDULE_EVENTS)):
        if completed % 4:
            result[f"STEP3_ENGINE_RETURNED_AFTER_SCHEDULE_PREFIX_{completed}"] = (
                passed + list(SCHEDULE_EVENTS[:completed]) + [
                "STEP3_SCHEDULE_RETURNED",
                "STEP3_ENGINE_RETURNED",
                "D2_DIAGNOSTIC_COMPLETED",
                ]
            )
    result["STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"] = (
        passed + list(SCHEDULE_EVENTS) + [
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D2_DIAGNOSTIC_COMPLETED",
        ]
    )
    return result


TERMINALS = _terminal_sequences()
MARKER_FORBIDDEN_TOKENS = (
    b"majoranas", b"coefficient", b"mask", b"ticks", b"budget",
    b"callback", b"term_count", b"final_state", b"step3_input",
    b"observable", b"cache", b"selection_resources", b"resource_summary",
)


class ProbeError(RuntimeError):
    """Fail-closed P9-D2 diagnostic error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_json(payload: bytes, context: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeError(f"invalid JSON: {context}") from error


def load_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise ProbeError(f"missing or nonregular JSON file: {path.name}")
    return loads_json(path.read_bytes(), path.name)


def _repo_root() -> Path:
    completed = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"), cwd=BASE,
        check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise ProbeError("P9-D2 must run inside a Git worktree")
    root = Path(completed.stdout.strip()).resolve()
    if BASE.resolve() != root / "docs" / "research" / "fermion-frontier":
        raise ProbeError("P9-D2 repository location drift")
    return root


def _git_bytes(*args: str) -> bytes:
    completed = subprocess.run(("git", *args), cwd=_repo_root(), check=False, capture_output=True)
    if completed.returncode != 0:
        raise ProbeError(f"Git command failed: {' '.join(args)}")
    return completed.stdout


def _git_text(*args: str) -> str:
    try:
        return _git_bytes(*args).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeError("Git text is not UTF-8") from error


def _require_sha(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProbeError(f"invalid {label} SHA")
    return value


def _git_blob_optional(commit: str, path: str) -> bytes | None:
    _require_sha(commit, "commit")
    listing = _git_bytes("ls-tree", "-z", commit, "--", path)
    if not listing:
        return None
    rows = listing.split(b"\0")
    if rows[-1] != b"" or len(rows) != 2:
        raise ProbeError("unexpected Git tree record count")
    metadata, separator, actual = rows[0].partition(b"\t")
    fields = metadata.split(b" ")
    if separator != b"\t" or actual != path.encode("utf-8") or len(fields) != 3:
        raise ProbeError("Git tree path drift")
    if fields[0] != b"100644" or fields[1] != b"blob":
        raise ProbeError("Git object is not a regular blob")
    return _git_bytes("cat-file", "blob", fields[2].decode("ascii"))


def _git_blob(commit: str, path: str) -> bytes:
    value = _git_blob_optional(commit, path)
    if value is None:
        raise ProbeError(f"missing Git blob: {path}")
    return value


def _checked_blob(commit: str, path: str, digest: str, size: int, label: str) -> bytes:
    body = _git_blob(commit, path)
    if len(body) != size or sha256_bytes(body) != digest:
        raise ProbeError(f"{label} raw Git-object custody drift")
    return body


def _parents(commit: str) -> tuple[str, ...]:
    fields = _git_text("rev-list", "--parents", "-n", "1", commit).strip().split()
    if not fields or fields[0] != commit:
        raise ProbeError("Git parent receipt drift")
    return tuple(fields[1:])


def _changed_paths(commit: str) -> tuple[str, ...]:
    raw = _git_bytes("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit)
    fields = raw.split(b"\0")
    if fields[-1] != b"":
        raise ProbeError("Git changed paths are not NUL terminated")
    try:
        paths = tuple(sorted(item.decode("utf-8") for item in fields[:-1]))
    except UnicodeDecodeError as error:
        raise ProbeError("Git changed path is not UTF-8") from error
    if len(paths) != len(set(paths)):
        raise ProbeError("duplicate Git changed path")
    return paths


def _status_paths() -> tuple[str, ...]:
    raw = _git_bytes(
        "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames",
    )
    rows = raw.split(b"\0")
    if rows[-1] != b"":
        raise ProbeError("Git status is not NUL terminated")
    if any(len(row) < 4 or row[2:3] != b" " for row in rows[:-1]):
        raise ProbeError("Git status record is malformed")
    try:
        paths = tuple(sorted(row[3:].decode("utf-8") for row in rows[:-1]))
    except UnicodeDecodeError as error:
        raise ProbeError("Git status path is not UTF-8") from error
    if len(paths) != len(set(paths)):
        raise ProbeError("duplicate Git status path")
    return paths


def _read_regular(relative: str) -> bytes:
    path = BASE / relative
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ProbeError(f"missing current source: {relative}") from error
    if not stat.S_ISREG(mode):
        raise ProbeError(f"current source is not regular: {relative}")
    return path.read_bytes()


def _target_p9_d1_projection() -> tuple[bytes, bytes, dict[str, Any]]:
    """Read only the predeclared non-scientific D1 phase projection.

    The D1 event rows are parsed only long enough to establish the three
    explicitly allowed booleans below.  Their names, count, ordering, and raw
    transport records do not cross the P9-D2 parent-result firewall.
    """
    if _parents(D1_PREPROBE_COMMIT) != (P9_RESULT_COMMIT,):
        raise ProbeError("D1 B0 parent topology drift")
    if _parents(D1_RESULT_COMMIT) != (D1_PREPROBE_COMMIT,):
        raise ProbeError("D1 B1 parent topology drift")
    d1_b0_paths = (
        ROOT + "majorana_certificate_p9_d1_phase_probe_policy.json",
        ROOT + "majorana_certificate_p9_d1_phase_probe_fixture.json",
        ROOT + "majorana_certificate_p9_d1_phase_probe/majorana_p9_bit_order_step3_phase_probe.jl",
        ROOT + "majorana_certificate_p9_d1_phase_probe.py",
        ROOT + "test_majorana_certificate_p9_d1_phase_probe.py",
    )
    if _changed_paths(D1_PREPROBE_COMMIT) != tuple(sorted(d1_b0_paths)):
        raise ProbeError("D1 B0 changed-path set drift")
    if _changed_paths(D1_RESULT_COMMIT) != (ROOT + D1_REPORT,):
        raise ProbeError("D1 B1 changed-path set drift")
    driver = _checked_blob(
        D1_RESULT_COMMIT, P9_DRIVER_FULL_PATH, P9_DRIVER_SHA256,
        P9_DRIVER_SIZE, "frozen P9 driver",
    )
    d1_fixture = _checked_blob(
        D1_RESULT_COMMIT, ROOT + D1_FIXTURE, D1_FIXTURE_SHA256,
        D1_FIXTURE_SIZE, "D1 fixture",
    )
    report_raw = _checked_blob(
        D1_RESULT_COMMIT, ROOT + D1_REPORT, D1_REPORT_SHA256,
        D1_REPORT_SIZE, "D1 B1 report",
    )
    report = loads_json(report_raw, "D1 B1 report")
    if not isinstance(report, dict):
        raise ProbeError("D1 B1 report is not an object")
    observation = report.get("observation")
    admission = report.get("S0_admission")
    if not isinstance(observation, dict) or not isinstance(admission, dict):
        raise ProbeError("D1 B1 minimal parent projection is malformed")
    phase_events = observation.get("phase_events")
    if not isinstance(phase_events, list) or any(not isinstance(row, dict) for row in phase_events):
        raise ProbeError("D1 B1 phase projection is malformed")
    phase_names = [row.get("event") for row in phase_events]
    required_d1_prefix = [
        "D1_RUNNER_STARTED",
        "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D1_STATIC_SETUP_COMPLETED",
        "P6_PREFIX_STARTED",
        "P6_PREFIX_RETURNED",
        "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
        "STEP3_ENGINE_STARTED",
    ]
    if phase_names != required_d1_prefix:
        raise ProbeError("D1 B1 allowed phase facts drift")
    projection = {
        "scientific_authority": report.get("scientific_authority"),
        "terminal_status": observation.get("status"),
        "phase_trace_status": observation.get("phase_trace_status"),
        "certificate_eligible": report.get("certificate_eligible"),
        "result_contract_eligible": report.get("result_contract_eligible"),
        "P6_prefix_resource_conformance_passed_marker_reached": (
            "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED" in phase_names
        ),
        "step3_engine_started_marker_reached": "STEP3_ENGINE_STARTED" in phase_names,
        "step3_engine_returned_marker_reached": "STEP3_ENGINE_RETURNED" in phase_names,
        "resource_witness_is_null": observation.get("resource_witness") is None,
        "future_S0_admission_status": admission.get("status"),
    }
    if projection != D1_ALLOWED_PROJECTION:
        raise ProbeError("D1 B1 allowed phase projection drift")
    return driver, d1_fixture, projection


# Compatibility alias for an early local spelling.  New callers must use the
# explicit P9-D1 name above so its one-way parent firewall remains visible.
_target_d1_b1_projection = _target_p9_d1_projection


def _validate_runtime_lock_bytes(runtime: Any) -> None:
    if not isinstance(runtime, dict) or (
        runtime.get("runtime_lock_id") != RUNTIME_LOCK_ID
        or runtime.get("runtime_lock_relative_path") != RUNTIME_LOCK_NAME
        or runtime.get("runtime_lock_sha256") != RUNTIME_LOCK_SHA256
        or runtime.get("julia_executable_sha256") != JULIA_EXECUTABLE_SHA256
        or runtime.get("MajoranaPropagation_source_tree_closure") != MAJORANA_SOURCE_TREE_CLOSURE
        or runtime.get("PauliPropagation_source_tree_closure") != PAULI_SOURCE_TREE_CLOSURE
        or runtime.get("runtime_lock_bytes_verified_by_preprobe_checker") is not True
    ):
        raise ProbeError("P9-D2 runtime custody declaration drift")
    body = _read_regular(RUNTIME_LOCK_NAME)
    if sha256_bytes(body) != RUNTIME_LOCK_SHA256:
        raise ProbeError("P9-D2 runtime-lock bytes SHA-256 mismatch")
    lock = loads_json(body, RUNTIME_LOCK_NAME)
    try:
        executable = lock["julia_runtime"]["executable"]["sha256"]
        packages = lock["direct_and_semantic_upstream_packages"]
        majorana = packages["MajoranaPropagation"]["installed_source_closure"]
        pauli = packages["PauliPropagation"]["installed_source_closure"]
    except (KeyError, TypeError) as error:
        raise ProbeError("P9-D2 runtime-lock projection is malformed") from error
    if (
        not isinstance(lock, dict)
        or type(lock.get("schema_version")) is not int
        or lock.get("schema_version") != 1
        or lock.get("runtime_lock_id") != RUNTIME_LOCK_ID
        or executable != JULIA_EXECUTABLE_SHA256
        or majorana != MAJORANA_SOURCE_TREE_CLOSURE
        or pauli != PAULI_SOURCE_TREE_CLOSURE
    ):
        raise ProbeError("P9-D2 runtime-lock projection drift")


def _expected_step3_schedule_marker_map() -> dict[str, Any]:
    """Return the immutable, non-observational D2 marker map."""
    return {
        "schema_version": 1,
        "schedule_source": "frozen_P2_build_schedule_returned_stages",
        "stage_order": list(FIXED_SEGMENTS),
        "frozen_group_order": list(FIXED_STAGE_GROUPS),
        "frozen_composite_count_per_stage": [row[2] for row in FIXED_SCHEDULE_MAP],
        "checkpoint_1_completed_composite_ordinal_per_stage": [
            row[3] for row in FIXED_SCHEDULE_MAP
        ],
        "checkpoint_2_completed_composite_ordinal_per_stage": [
            row[4] for row in FIXED_SCHEDULE_MAP
        ],
        "started_is_emitted_before_the_first_composite_of_a_stage": True,
        "checkpoints_are_emitted_after_the_frozen_completed_composite_ordinal": True,
        "returned_is_emitted_only_after_the_last_composite_of_a_stage": True,
        "markers_are_static_schedule_progress_not_scientific_state": True,
        "no_segment_marker_exports_an_ordinal_count_group_index_or_scientific_value": True,
        "constituent_boundary_selection_callback_and_hot_loop_markers_are_forbidden": True,
    }


def _step3_schedule_common_prefix() -> list[str]:
    return [
        "D2_RUNNER_STARTED",
        "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        "D2_STATIC_SETUP_COMPLETED",
        "P6_PREFIX_STARTED",
        "P6_PREFIX_RETURNED",
        "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
        "STEP3_ENGINE_STARTED",
        "STEP3_STATE_INITIALIZED",
        "STEP3_SCHEDULE_ENTERED",
    ]


def _expected_phase_event_protocol() -> dict[str, Any]:
    partial_counts = [count for count in range(1, len(SCHEDULE_EVENTS)) if count % 4]
    shared_suffix = [
        "STEP3_SCHEDULE_RETURNED",
        "STEP3_ENGINE_RETURNED",
        "D2_DIAGNOSTIC_COMPLETED",
    ]
    return {
        "schema_version": 1,
        "wire_record_exact_fields": ["event", "sequence"],
        "sequence_origin": 0,
        "sequence_is_contiguous": True,
        "maximum_event_count": 48,
        "maximum_line_bytes_including_newline": 256,
        "maximum_total_channel_bytes": 8192,
        "allowed_events": list(PHASE_EVENTS),
        "fixed_legal_terminal_sequences": {
            "PREFIX_NOT_ESTABLISHED": TERMINALS["PREFIX_NOT_ESTABLISHED"],
        },
        "parameterized_step3_engine_return_terminal": {
            "branch_name": "STEP3_ENGINE_RETURNED_AFTER_SCHEDULE_PREFIX",
            "fixed_prefix_through_step3_schedule_entered": _step3_schedule_common_prefix(),
            "internal_schedule_event_sequence": list(SCHEDULE_EVENTS),
            "allowed_partial_internal_prefix_event_counts": partial_counts,
            "forbidden_partial_internal_prefix_event_counts": [
                0, *range(4, len(SCHEDULE_EVENTS), 4),
            ],
            "full_schedule_internal_event_count": len(SCHEDULE_EVENTS),
            "partial_schedule_suffix": shared_suffix,
            "full_schedule_suffix": shared_suffix,
            "segment_returned_requires_the_next_segment_started_before_an_early_engine_return_except_after_all_36_internal_events": True,
            "engine_return_marker_does_not_establish_a_cap_resource_or_scientific_cause": True,
        },
        "host_or_runtime_failure_may_retain_only_a_prefix_of_a_trace_generated_by_this_DFA": True,
        "clean_exit_requires_exactly_one_complete_terminal_sequence_generated_by_this_DFA": True,
        "prefix_not_established_does_not_establish_an_algorithmic_or_physical_failure": True,
        "step3_schedule_events_do_not_establish_term_processing_selector_execution_or_scientific_truth": True,
    }


def _expected_phase_channel_custody() -> dict[str, Any]:
    return {
        "transport": "dedicated_inherited_anonymous_pipe_file_descriptor",
        "writer_runs_inside_the_same_systemd_scope_as_Julia": True,
        "reader_runs_in_the_outer_supervisor": True,
        "wire_records_are_single_atomic_POSIX_pipe_writes": True,
        "child_emits_only_fixed_event_names_and_sequence": True,
        "child_emits_no_timestamp_term_count_index_mask_coefficient_tick_budget_cap_resource_or_free_text": True,
        "stdout_is_strictly_empty": True,
        "stderr_is_not_a_phase_channel": True,
        "raw_phase_channel_bytes_are_not_persisted": True,
        "no_phase_file_FIFO_checkpoint_or_persistent_sidecar_is_created": True,
        "phase_trace_must_not_enter_S0_or_a_future_D3_runner": True,
    }


def _expected_fixture_clone_contract() -> dict[str, Any]:
    return {
        "clone_driver_relative_path": CLONE_DRIVER,
        "exact_marker_block_count": 12,
        "outer_phase_marker_block_count": 8,
        "schedule_marker_block_count": 4,
        "forward_byte_construction_and_reverse_deletion_are_required": True,
        "runtime_source_or_AST_transform_is_forbidden": True,
        "checker_owned_preamble_and_exact_marker_blocks_only": True,
        "nonmarker_source_difference_stops_without_execution": True,
        "P9_D0_resource_witness_construction_is_unreached_after_a_D2_terminal": True,
        "D2_driver_must_not_include_or_open_D1_clone_or_D1_report": True,
    }


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    """Validate the non-authoritative D2 fixture without importing D1 traces."""
    expected = {
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible", "result_contract_eligible",
        "diagnostic_identity", "d1_parent_custody", "frozen_p9_source_custody",
        "step3_schedule_marker_map", "source_clone_contract", "phase_event_protocol",
        "phase_channel_custody", "host_supervisor_caps", "runtime_custody",
        "authority_exclusions",
    }
    if not isinstance(fixture, dict) or set(fixture) != expected:
        raise ProbeError("P9-D2 fixture key set drift")
    if (
        type(fixture.get("schema_version")) is not int
        or fixture.get("schema_version") != 1
        or fixture.get("fixture_id") != FIXTURE_ID
        or fixture.get("required_direct_parent_commit") != D1_RESULT_COMMIT
        or fixture.get("scientific_authority") != "NONE"
        or fixture.get("certificate_eligible") is not False
        or fixture.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P9-D2 fixture identity or authority drift")
    identity = fixture["diagnostic_identity"]
    expected_identity = {
        "algorithm_id": P9_ALGORITHM_ID,
        "candidate_id": P9_CANDIDATE,
        "classification": "P9_D1_RESULT_INFORMED_D2_RESULT_UNPINNED_SCIENTIFIC_BLIND_SCHEDULE_DIAGNOSTIC",
        "diagnostic_mode": "E768_BITORDER_STEP3_D2_SCHEDULE_V1",
        "diagnostic_probe_id": "P9-D2-E768-BITORDER-STEP3-SCHEDULE-V1",
        "scientific_probe_mode": P9_MODE,
        "one_fresh_process_only": True,
        "does_not_define_a_new_scientific_candidate": True,
        "does_not_establish_future_S0_admission": True,
        "does_not_rerun_or_replace_P9_D0_or_P9_D1": True,
    }
    if identity != expected_identity:
        raise ProbeError("P9-D2 fixture candidate identity drift")
    expected_parent = {
        "preprobe_commit_sha": D1_PREPROBE_COMMIT,
        "result_commit_sha": D1_RESULT_COMMIT,
        "report_relative_path": D1_REPORT,
        "report_size_bytes": D1_REPORT_SIZE,
        "report_sha256": D1_REPORT_SHA256,
        "report_type": "majorana_p9_step3_e768_bitorder_coarse_phase_report_d1_v1",
        **D1_ALLOWED_PROJECTION,
        "allowed_result_informed_facts_are_exhaustive": True,
    }
    if fixture["d1_parent_custody"] != expected_parent:
        raise ProbeError("P9-D2 D1 B1 parent custody drift")
    source = fixture["frozen_p9_source_custody"]
    expected_source = {
        "p9_preprobe_commit_sha": P9_PREPROBE_COMMIT,
        "p9_result_commit_sha": P9_RESULT_COMMIT,
        "p9_driver_relative_path": P9_DRIVER,
        "p9_driver_sha256": P9_DRIVER_SHA256,
        "p9_driver_size_bytes": P9_DRIVER_SIZE,
        "p9_fixture_relative_path": P9_FIXTURE,
        "p9_fixture_sha256": P9_FIXTURE_SHA256,
        "p9_fixture_size_bytes": P9_FIXTURE_SIZE,
        "frozen_candidate_mode_is_passed_unchanged_to_main_p9_d0": True,
        "D2_derives_directly_from_the_frozen_P9_driver_not_the_D1_clone": True,
        "D1_report_policy_fixture_and_clone_are_not_runner_staged": True,
    }
    if source != expected_source:
        raise ProbeError("P9-D2 fixture frozen-source custody drift")
    if fixture["step3_schedule_marker_map"] != _expected_step3_schedule_marker_map():
        raise ProbeError("P9-D2 fixed schedule custody drift")
    if fixture["source_clone_contract"] != _expected_fixture_clone_contract():
        raise ProbeError("P9-D2 fixture clone contract drift")
    protocol = fixture["phase_event_protocol"]
    if protocol != _expected_phase_event_protocol():
        raise ProbeError("P9-D2 phase protocol drift")
    if fixture["phase_channel_custody"] != _expected_phase_channel_custody():
        raise ProbeError("P9-D2 phase-channel custody drift")
    _driver, d1_fixture_raw, projection = _target_p9_d1_projection()
    d1_fixture = loads_json(d1_fixture_raw, D1_FIXTURE)
    if not isinstance(d1_fixture, dict) or (
        fixture["host_supervisor_caps"] != d1_fixture.get("host_supervisor_caps")
        or fixture["runtime_custody"] != d1_fixture.get("runtime_custody")
    ):
        raise ProbeError("P9-D2 host/runtime custody differs from frozen D1")
    _validate_runtime_lock_bytes(fixture["runtime_custody"])
    expected_exclusions = [
        "D2_does_not_run_or_replace_P9_D0_or_P9_D1",
        "D2_does_not_export_term_count_index_mask_coefficient_tick_budget_cap_or_resource_witness",
        "D2_does_not_establish_actual_memory_RSS_allocation_runtime_or_timeout_causality",
        "D2_does_not_change_candidate_algorithm_anchor_cadence_caps_host_admission_or_fallback",
        "D2_does_not_reprove_or_expand_P6_scientific_authority",
        "D2_does_not_establish_S0_step3_error_or_a_physical_result",
        "D2_does_not_select_rank_reject_or_certify_a_candidate_or_READY",
    ]
    if projection != D1_ALLOWED_PROJECTION or fixture["authority_exclusions"] != expected_exclusions:
        raise ProbeError("P9-D2 authority scope drift")
    return fixture


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise ProbeError("P9-D2 source pin manifest is empty")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"relative_path", "size_bytes", "sha256"}:
            raise ProbeError("malformed P9-D2 source pin")
        path = row.get("relative_path")
        size = row.get("size_bytes")
        digest = row.get("sha256")
        if not isinstance(path, str) or path in result:
            raise ProbeError("duplicate P9-D2 source pin")
        if (
            type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ProbeError("malformed P9-D2 source pin value")
        result[path] = row
    if set(result) != set(SOURCE_PATHS):
        raise ProbeError("P9-D2 source pin allowlist drift")
    return result


def validate_policy(policy: Any, *, require_report_absent: bool) -> Mapping[str, Any]:
    expected = {
        "schema_version", "policy_id", "required_direct_parent_commit",
        "policy_role", "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "hindsight_firewall",
        "D2_execution_contract", "source_clone_contract", "phase_report_contract",
        "staged_source_custody", "preprobe_and_result_lifecycle", "source_files",
        "source_pins_status", "exact_source_file_count",
    }
    if not isinstance(policy, dict) or set(policy) != expected:
        raise ProbeError("P9-D2 policy key set drift")
    if (
        type(policy.get("schema_version")) is not int
        or policy.get("schema_version") != 1
        or policy.get("policy_id") != POLICY_ID
        or policy.get("required_direct_parent_commit") != D1_RESULT_COMMIT
        or policy.get("scientific_authority") != "NONE"
        or policy.get("certificate_eligible") is not False
        or policy.get("result_contract_eligible") is not False
        or policy.get("policy_role") != (
            "separately_versioned_non_authoritative_static_schedule_diagnostic_for_the_"
            "frozen_P9_step3_path_under_unchanged_admission"
        )
        or policy.get("exact_source_file_count") != len(SOURCE_PATHS)
        or policy.get("source_pins_status") != "FROZEN_EXACT"
    ):
        raise ProbeError("P9-D2 policy identity or authority drift")
    firewall = policy["hindsight_firewall"]
    expected_firewall = {
        "D1_result_informed": True,
        "D2_does_not_rerun_D0_or_D1": True,
        "D2_result_unpinned_before_preprobe_commit": True,
        "a_second_D2_execution_requires_a_new_precommitted_version": True,
        "allowed_D1_result_facts_are_exhaustive": [
            "D1_report_identity_and_scientific_authority_NONE",
            "D1_certificate_and_result_contract_eligibility_are_false",
            "D1_trace_was_a_legal_interrupted_protocol_prefix",
            "D1_reached_the_P6_prefix_resource_conformance_passed_marker",
            "D1_reached_step3_engine_started_but_not_step3_engine_returned",
            "D1_resource_witness_is_null",
            "D1_future_S0_admission_is_not_established",
        ],
        "classification": "P9_D1_RESULT_INFORMED_D2_RESULT_UNPINNED_SCIENTIFIC_BLIND_SCHEDULE_DIAGNOSTIC",
        "forbidden_D1_or_suppressed_inputs": [
            "D1_raw_report_bytes_after_identity_and_minimal_projection",
            "D1_complete_phase_event_array_event_count_or_phase_digest",
            "D1_host_failure_timeout_or_any_timing_returncode_stdout_stderr_or_time_diagnostics",
            "D1_raw_phase_channel_bytes_hash_or_receive_times",
            "D1_clone_driver_or_any_D1_runner_state",
            "any_resource_count_memory_RSS_or_resource_witness",
            "any_selected_mask_coefficient_tick_budget_final_state_or_selector_callback_value",
            "any_D0_D1_or_D2_observation_used_to_change_candidate_caps_host_admission_or_fallback",
        ],
        "no_D2_execution_output_may_exist_before_the_preprobe_commit": True,
    }
    if firewall != expected_firewall:
        raise ProbeError("P9-D2 hindsight firewall drift")
    expected_execution = {
        "D2_phase_IO_has_no_S0_admission_authority": True,
        "D2_stops_after_the_first_D2_terminal_and_does_not_construct_or_emit_a_P9_D0_resource_witness": True,
        "P9_core_mode_is_exactly_E768_BITORDER_STEP3_V1": True,
        "all_steps_share_one_live_process_until_the_D2_terminal": True,
        "checkpoint_or_serialized_resume_forbidden": True,
        "fresh_O0_process_only": True,
        "only_fixed_outer_and_static_schedule_phase_events_are_allowed": True,
        "phase_event_protocol_maximum_event_count": 48,
        "allowed_early_schedule_prefix_event_counts": [
            count for count in range(1, len(SCHEDULE_EVENTS)) if count % 4
        ],
        "early_and_full_schedule_return_suffix": [
            "STEP3_SCHEDULE_RETURNED", "STEP3_ENGINE_RETURNED", "D2_DIAGNOSTIC_COMPLETED",
        ],
        "zero_schedule_markers_or_a_segment_returned_before_the_next_segment_started_cannot_cleanly_early_return": True,
        "required_step3_custody_events": [
            "STEP3_STATE_INITIALIZED", "STEP3_SCHEDULE_ENTERED", "STEP3_SCHEDULE_RETURNED",
        ],
        "stdout_must_be_empty_and_resource_witness_must_be_null": True,
        "stdout_and_stderr_are_drained_without_unbounded_outer_buffering_and_limit_violation_stops_the_scope": True,
        "term_count_index_mask_coefficient_tick_budget_cap_selector_callback_boundary_constituent_and_hot_loop_events_are_forbidden": True,
    }
    if policy["D2_execution_contract"] != expected_execution:
        raise ProbeError("P9-D2 execution contract drift")
    expected_report_contract = {
        "if_a_D2_legal_prefix_stops_inside_a_static_schedule_segment_then_only_a_new_D3_static_schedule_DFA_may_be_precommitted": True,
        "no_D0_D1_or_D2_timing_RSS_stderr_stdout_returncode_or_resource_measurement_is_persisted": True,
        "no_automatic_repeat_or_in_place_cap_relaxation_is_allowed": True,
        "no_raw_phase_channel_bytes_hash_byte_count_or_receive_times_are_persisted": True,
        "report_contains_only_D2_phase_language_and_nonmathematical_host_status": True,
        "resource_witness_is_always_null": True,
    }
    if policy["phase_report_contract"] != expected_report_contract:
        raise ProbeError("P9-D2 phase report contract drift")
    clone = policy["source_clone_contract"]
    expected_clone = {
        "frozen_P9_driver_git_commit": P9_RESULT_COMMIT,
        "frozen_P9_driver_relative_path": P9_DRIVER_FULL_PATH,
        "frozen_P9_driver_sha256": P9_DRIVER_SHA256,
        "frozen_P9_driver_size_bytes": P9_DRIVER_SIZE,
        "clone_driver_relative_path": CLONE_DRIVER,
        "exact_marker_block_count": 12,
        "outer_phase_marker_block_count": 8,
        "schedule_marker_block_count": 4,
        "forward_byte_construction_and_reverse_deletion_are_required": True,
        "runtime_source_or_AST_transform_is_forbidden": True,
        "checker_owned_preamble_and_exact_marker_blocks_only": True,
        "nonmarker_source_difference_stops_without_execution": True,
        "D2_driver_is_derived_directly_from_frozen_P9_source_not_D1_clone": True,
        "D1_artifacts_are_not_included_opened_or_staged_by_the_D2_driver": True,
    }
    if clone != expected_clone:
        raise ProbeError("P9-D2 source-clone contract drift")
    staged = policy["staged_source_custody"]
    expected_staged = {
        "staged_path_order": list(STAGED_PATHS),
        "exact_staged_path_count": len(STAGED_PATHS),
        "all_staged_files_must_be_regular_nonsymlink_and_byte_pinned_before_B0": True,
        "staged_bytes_must_equal_repository_bytes": True,
        "one_exclusive_execution_claim_is_acquired_immediately_before_launch": True,
        "abnormal_stop_before_a_canonical_report_retains_the_claim": True,
        "D1_report_policy_fixture_Python_and_clone_are_outer_checker_only_and_not_staged": True,
        "original_P9_driver_is_outer_checker_only_and_not_staged": True,
    }
    if staged != expected_staged:
        raise ProbeError("P9-D2 staged path order drift")
    expected_lifecycle = {
        "B0_cannot_contain_a_D2_report_or_execution_claim": True,
        "B0_has_exactly_five_new_paths_and_is_a_direct_child_of_D1_B1": True,
        "B1_has_exactly_one_new_path_the_canonical_D2_report_and_is_a_direct_child_of_B0": True,
        "B1_report_Git_blob_must_equal_canonical_report_bytes_and_the_clean_worktree_file": True,
        "B1_verification_must_reject_any_extra_changed_path_or_dirty_worktree": True,
        "claimed_B0_HEAD_and_worktree_are_reverified_before_report_write_and_claim_release": True,
        "claim_is_deleted_only_after_validate_report_and_exclusive_canonical_report_write_succeed": True,
    }
    if policy["preprobe_and_result_lifecycle"] != expected_lifecycle:
        raise ProbeError("P9-D2 lifecycle policy drift")
    pins = _source_pins(policy)
    for path, row in pins.items():
        body = _read_regular(path)
        if row.get("size_bytes") != len(body) or row.get("sha256") != sha256_bytes(body):
            raise ProbeError(f"P9-D2 source pin drift: {path}")
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    _validate_static_clone(fixture)
    if require_report_absent:
        for name in (REPORT_NAME, EXECUTION_CLAIM_NAME):
            path = BASE / name
            if path.exists() or path.is_symlink():
                raise ProbeError(f"P9-D2 preprobe artifact already exists: {name}")
    return policy


def _preamble(fixture: Mapping[str, Any]) -> bytes:
    """Build the checker-owned Julia transport envelope byte-for-byte."""
    fixture_hash = canonical_sha256(fixture)
    events = ",\n    ".join(f'"{event}"' for event in PHASE_EVENTS)
    labels = ", ".join(f'"{label}"' for label in FIXED_SEGMENTS)
    composite_counts = ", ".join(str(row[2]) for row in FIXED_SCHEDULE_MAP)
    checkpoint_1 = ", ".join(str(row[3]) for row in FIXED_SCHEDULE_MAP)
    checkpoint_2 = ", ".join(str(row[4]) for row in FIXED_SCHEDULE_MAP)
    return (
        "#!/usr/bin/env julia\n"
        "# P9_D2_STATIC_TRANSPORT_PREAMBLE_BEGIN\n"
        "# Checker-owned phase transport and bootstrap. This preamble contains no\n"
        "# live P9 state and remains outside the byte-derived frozen P9 clone.\n"
        "const P9_D2_FIXTURE_CANONICAL_SHA256 =\n"
        f"    \"{fixture_hash}\"\n"
        "const P9_D2_FIXTURE_ID =\n"
        f"    \"{FIXTURE_ID}\"\n"
        "const P9_D2_DIRECT_PARENT =\n"
        f"    \"{D1_RESULT_COMMIT}\"\n"
        "const P9_D2_PHASE_EVENTS = (\n"
        f"    {events},\n"
        ")\n"
        "const P9_D2_MARKER_SEGMENT_LABELS =\n"
        f"    ({labels})\n"
        "const P9_D2_MARKER_COMPOSITE_COUNTS =\n"
        f"    ({composite_counts})\n"
        "const P9_D2_MARKER_CHECKPOINT_1 =\n"
        f"    ({checkpoint_1})\n"
        "const P9_D2_MARKER_CHECKPOINT_2 =\n"
        f"    ({checkpoint_2})\n"
        "const P9_D2_PHASE_FD = Ref{Cint}(-1)\n"
        "const P9_D2_PHASE_SEQUENCE = Ref(0)\n\n"
        f"length(P9_D2_PHASE_EVENTS) == {len(PHASE_EVENTS)} ||\n"
        "    error(\"invalid P9 D2 phase vocabulary\")\n"
        "length(P9_D2_MARKER_SEGMENT_LABELS) == 9 ||\n"
        "    error(\"invalid P9 D2 segment map\")\n"
        "length(P9_D2_MARKER_COMPOSITE_COUNTS) == 9 ||\n"
        "    error(\"invalid P9 D2 composite-count map\")\n"
        "length(P9_D2_MARKER_CHECKPOINT_1) == 9 ||\n"
        "    error(\"invalid P9 D2 first-checkpoint map\")\n"
        "length(P9_D2_MARKER_CHECKPOINT_2) == 9 ||\n"
        "    error(\"invalid P9 D2 second-checkpoint map\")\n\n"
        "struct P9D2PhaseTransportError <: Exception end\n\n"
        "function p9_d2_write_atomic(payload::Vector{UInt8})\n"
        "    length(payload) <= 256 || throw(P9D2PhaseTransportError())\n"
        "    fd = P9_D2_PHASE_FD[]\n"
        "    fd >= 3 || throw(P9D2PhaseTransportError())\n"
        "    written = GC.@preserve payload ccall(\n"
        "        :write, Base.Cssize_t, (Cint, Ptr{UInt8}, Csize_t),\n"
        "        fd, pointer(payload), length(payload),\n"
        "    )\n"
        "    if written == -1 && Base.Libc.errno() == Base.Libc.EINTR\n"
        "        written = GC.@preserve payload ccall(\n"
        "            :write, Base.Cssize_t, (Cint, Ptr{UInt8}, Csize_t),\n"
        "            fd, pointer(payload), length(payload),\n"
        "        )\n"
        "    end\n"
        "    written == length(payload) || throw(P9D2PhaseTransportError())\n"
        "    return nothing\n"
        "end\n\n"
        "function p9_d2_emit(event::AbstractString)\n"
        "    event in P9_D2_PHASE_EVENTS || error(\"unknown P9 D2 phase event\")\n"
        "    sequence = P9_D2_PHASE_SEQUENCE[]\n"
        "    line = \"{\\\"event\\\":\\\"$(event)\\\",\\\"sequence\\\":$(sequence)}\\n\"\n"
        "    p9_d2_write_atomic(Vector{UInt8}(codeunits(line)))\n"
        "    P9_D2_PHASE_SEQUENCE[] = sequence + 1\n"
        "    return nothing\n"
        "end\n\n"
        "function p9_d2_validate_fixture(d2_fixture)\n"
        "    P9_D2_FIXTURE_CANONICAL_SHA256 !=\n"
        "        \"P9_D2_FIXTURE_CANONICAL_SHA256_UNSET\" ||\n"
        "        error(\"P9 D2 fixture canonical SHA is unset\")\n"
        "    canonical_sha256(d2_fixture) == P9_D2_FIXTURE_CANONICAL_SHA256 ||\n"
        "        error(\"P9 D2 fixture differs from frozen semantic object\")\n"
        "    d2_fixture[\"fixture_id\"] == P9_D2_FIXTURE_ID ||\n"
        "        error(\"P9 D2 fixture id drift\")\n"
        "    d2_fixture[\"required_direct_parent_commit\"] == P9_D2_DIRECT_PARENT ||\n"
        "        error(\"P9 D2 direct-parent drift\")\n"
        "    d2_fixture[\"scientific_authority\"] == \"NONE\" ||\n"
        "        error(\"P9 D2 authority drift\")\n"
        "    d2_fixture[\"certificate_eligible\"] == false ||\n"
        "        error(\"P9 D2 certificate drift\")\n"
        "    d2_fixture[\"result_contract_eligible\"] == false ||\n"
        "        error(\"P9 D2 result-contract drift\")\n"
        "    protocol = d2_fixture[\"phase_event_protocol\"]\n"
        "    protocol[\"allowed_events\"] == Any[P9_D2_PHASE_EVENTS...] ||\n"
        "        error(\"P9 D2 phase vocabulary drift\")\n"
        "    protocol[\"maximum_event_count\"] == 48 ||\n"
        "        error(\"P9 D2 phase event cap drift\")\n"
        "    protocol[\"maximum_line_bytes_including_newline\"] == 256 ||\n"
        "        error(\"P9 D2 phase line cap drift\")\n"
        "    protocol[\"maximum_total_channel_bytes\"] == 8192 ||\n"
        "        error(\"P9 D2 phase channel cap drift\")\n"
        "    host = d2_fixture[\"host_supervisor_caps\"]\n"
        "    host[\"MemoryMax_bytes\"] == 2147483648 ||\n"
        "        error(\"P9 D2 memory cap drift\")\n"
        "    host[\"MemorySwapMax_bytes\"] == 0 ||\n"
        "        error(\"P9 D2 swap cap drift\")\n"
        "    host[\"RuntimeMaxSec\"] == \"1800s\" ||\n"
        "        error(\"P9 D2 runtime cap drift\")\n"
        "    return d2_fixture\n"
        "end\n\n"
        "function p9_d2_bootstrap!()\n"
        "    length(ARGS) == 9 || error(\"invalid P9 D2 argument count\")\n"
        "    d2_fixture = JSON.parsefile(abspath(ARGS[1]))\n"
        "    p9_d2_validate_fixture(d2_fixture)\n"
        "    phase_fd = parse(Int, ARGS[9])\n"
        "    3 <= phase_fd <= typemax(Cint) || error(\"invalid P9 D2 phase fd\")\n"
        "    P9_D2_PHASE_FD[] = Cint(phase_fd)\n"
        "    deleteat!(ARGS, 1)\n"
        "    pop!(ARGS)\n"
        "    length(ARGS) == 7 || error(\"P9 D2 core argument normalization drift\")\n"
        "    p9_d2_emit(\"D2_RUNNER_STARTED\")\n"
        "    return nothing\n"
        "end\n"
        "# P9_D2_STATIC_TRANSPORT_PREAMBLE_END\n\n"
        "# P9_D2_STATIC_P9_D0_CLONE_BEGIN\n"
    ).encode("utf-8")


CLONE_END = b"\n# P9_D2_STATIC_P9_D0_CLONE_END\n"


def _marker_blocks() -> tuple[tuple[bytes, bytes, bool], ...]:
    return (
        (
            b"function main_p9_d0()\n    P9_D0_FAILURE_PHASE[] = P9_D0_INVALID_FAILURE_PHASE\n",
            b"    # P9_D2_OUTER_MARKER_BLOCK_1_BEGIN\n"
            b"    p9_d2_bootstrap!()\n"
            b"    # P9_D2_OUTER_MARKER_BLOCK_1_END\n",
            False,
        ),
        (
            b"function p9_execute_prefix(\n"
            b"    p9_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,\n"
            b")\n",
            b"    # P9_D2_OUTER_MARKER_BLOCK_2_BEGIN\n"
            b"    p9_d2_emit(\"P6_PREFIX_STARTED\")\n"
            b"    # P9_D2_OUTER_MARKER_BLOCK_2_END\n",
            False,
        ),
        (
            b"function p9_execute_bit_order_step(\n"
            b"    stages, execution_fixture, input_sum, trig_lookup, engine_caps,\n"
            b"    selection_caps; copy_completed_output::Bool,\n"
            b")\n",
            b"    # P9_D2_OUTER_MARKER_BLOCK_3_BEGIN\n"
            b"    p9_d2_emit(\"STEP3_ENGINE_STARTED\")\n"
            b"    # P9_D2_OUTER_MARKER_BLOCK_3_END\n",
            False,
        ),
        (
            b"    runtime_custody = p9_validate_runtime(p9_fixture)\n",
            b"    # P9_D2_OUTER_MARKER_BLOCK_4_BEGIN\n"
            b"    p9_d2_emit(\"D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED\")\n"
            b"    # P9_D2_OUTER_MARKER_BLOCK_4_END\n",
            False,
        ),
        (
            b"    observable, _initial = initial_observable()\n",
            b"    # P9_D2_OUTER_MARKER_BLOCK_5_BEGIN\n"
            b"    p9_d2_emit(\"D2_STATIC_SETUP_COMPLETED\")\n"
            b"    # P9_D2_OUTER_MARKER_BLOCK_5_END\n",
            False,
        ),
        (
            b"    prefix = p9_execute_prefix(\n"
            b"        p9_fixture, p6_fixture, p3_fixture, stages, observable, trig_lookup,\n"
            b"    )\n",
            b"    # P9_D2_OUTER_MARKER_BLOCK_6_BEGIN\n"
            b"    p9_d2_emit(\"P6_PREFIX_RETURNED\")\n"
            b"    if prefix.prefix_conformed\n"
            b"        p9_d2_emit(\"P6_PREFIX_RESOURCE_CONFORMANCE_PASSED\")\n"
            b"    else\n"
            b"        p9_d2_emit(\n"
            b"            \"P6_PREFIX_RESOURCE_CONFORMANCE_NOT_ESTABLISHED_TERMINAL\",\n"
            b"        )\n"
            b"        p9_d2_emit(\"D2_DIAGNOSTIC_COMPLETED\")\n"
            b"        return nothing\n"
            b"    end\n"
            b"    # P9_D2_OUTER_MARKER_BLOCK_6_END\n",
            False,
        ),
        (
            b"        execution = execute_p9_step3_bitorder(\n"
            b"            stages, execution_fixture, input_sum, trig_lookup,\n"
            b"            P6_K37_THRESHOLD,\n"
            b"        )\n",
            b"        # P9_D2_OUTER_MARKER_BLOCK_7_BEGIN\n"
            b"        p9_d2_emit(\"STEP3_SCHEDULE_RETURNED\")\n"
            b"        # P9_D2_OUTER_MARKER_BLOCK_7_END\n",
            False,
        ),
        (
            b"        step3_run = p9_execute_bit_order_step(\n"
            b"            stages, step3_fixture, step3_input, trig_lookup, step3_caps,\n"
            b"            step3_selection_caps; copy_completed_output=false,\n"
            b"        )\n",
            b"        # P9_D2_OUTER_MARKER_BLOCK_8_BEGIN\n"
            b"        p9_d2_emit(\"STEP3_ENGINE_RETURNED\")\n"
            b"        p9_d2_emit(\"D2_DIAGNOSTIC_COMPLETED\")\n"
            b"        return nothing\n"
            b"        # P9_D2_OUTER_MARKER_BLOCK_8_END\n",
            False,
        ),
        (
            b"    try\n"
            b"        for stage in stages\n",
            b"    # P9_D2_SCHEDULE_MARKER_BLOCK_1_BEGIN\n"
            b"    d2_marker_segment_ordinal = 0\n"
            b"    d2_marker_composite_ordinal = 0\n"
            b"    d2_marker_label = \"\"\n"
            b"    p9_d2_emit(\"STEP3_STATE_INITIALIZED\")\n"
            b"    p9_d2_emit(\"STEP3_SCHEDULE_ENTERED\")\n"
            b"    # P9_D2_SCHEDULE_MARKER_BLOCK_1_END\n",
            True,
        ),
        (
            b"        for stage in stages\n",
            b"            # P9_D2_SCHEDULE_MARKER_BLOCK_2_BEGIN\n"
            b"            d2_marker_segment_ordinal += 1\n"
            b"            d2_marker_segment_ordinal <= length(P9_D2_MARKER_SEGMENT_LABELS) ||\n"
            b"                error(\"P9 D2 marker segment-count drift\")\n"
            b"            d2_marker_composite_ordinal = 0\n"
            b"            d2_marker_label = P9_D2_MARKER_SEGMENT_LABELS[\n"
            b"                d2_marker_segment_ordinal\n"
            b"            ]\n"
            b"            p9_d2_emit(\"STEP3_SEGMENT_$(d2_marker_label)_STARTED\")\n"
            b"            # P9_D2_SCHEDULE_MARKER_BLOCK_2_END\n",
            False,
        ),
        (
            b"                completed_composites += 1\n",
            b"                # P9_D2_SCHEDULE_MARKER_BLOCK_3_BEGIN\n"
            b"                d2_marker_composite_ordinal += 1\n"
            b"                if d2_marker_composite_ordinal == P9_D2_MARKER_CHECKPOINT_1[\n"
            b"                    d2_marker_segment_ordinal\n"
            b"                ]\n"
            b"                    p9_d2_emit(\n"
            b"                        \"STEP3_SEGMENT_$(d2_marker_label)_CHECKPOINT_1_REACHED\",\n"
            b"                    )\n"
            b"                elseif d2_marker_composite_ordinal == P9_D2_MARKER_CHECKPOINT_2[\n"
            b"                    d2_marker_segment_ordinal\n"
            b"                ]\n"
            b"                    p9_d2_emit(\n"
            b"                        \"STEP3_SEGMENT_$(d2_marker_label)_CHECKPOINT_2_REACHED\",\n"
            b"                    )\n"
            b"                end\n"
            b"                # P9_D2_SCHEDULE_MARKER_BLOCK_3_END\n",
            False,
        ),
        (
            b"                cumulative_accuracy_charged_event_count=\n"
            b"                    accuracy_after.accuracy_charged_event_count,\n"
            b"            )))\n",
            b"            # P9_D2_SCHEDULE_MARKER_BLOCK_4_BEGIN\n"
            b"            d2_marker_composite_ordinal == P9_D2_MARKER_COMPOSITE_COUNTS[\n"
            b"                d2_marker_segment_ordinal\n"
            b"            ] || error(\"P9 D2 marker composite-count drift\")\n"
            b"            p9_d2_emit(\"STEP3_SEGMENT_$(d2_marker_label)_RETURNED\")\n"
            b"            # P9_D2_SCHEDULE_MARKER_BLOCK_4_END\n",
            False,
        ),
    )


def _build_expected_clone(frozen: bytes, fixture: Mapping[str, Any]) -> tuple[bytes, list[bytes]]:
    expected = frozen
    blocks: list[bytes] = []
    for anchor, block, before in _marker_blocks():
        if expected.count(anchor) != 1:
            raise ProbeError("P9-D2 frozen marker anchor drift")
        lowered = block.lower()
        if any(token in lowered for token in MARKER_FORBIDDEN_TOKENS):
            raise ProbeError("P9-D2 marker block references forbidden live state")
        expected = expected.replace(anchor, (block + anchor) if before else (anchor + block), 1)
        blocks.append(block)
    return _preamble(fixture) + expected + CLONE_END, blocks


def _validate_static_clone(fixture: Mapping[str, Any]) -> dict[str, Any]:
    frozen, _d1_fixture, _projection = _target_p9_d1_projection()
    expected, blocks = _build_expected_clone(frozen, fixture)
    actual = _read_regular(CLONE_DRIVER)
    if actual != expected:
        raise ProbeError("P9-D2 clone is not exactly checker-derived from frozen P9")
    preamble = _preamble(fixture)
    if not actual.startswith(preamble) or not actual.endswith(CLONE_END):
        raise ProbeError("P9-D2 clone envelope drift")
    reversed_body = actual[len(preamble):-len(CLONE_END)]
    for block in reversed(blocks):
        if reversed_body.count(block) != 1:
            raise ProbeError("P9-D2 marker block multiplicity drift")
        reversed_body = reversed_body.replace(block, b"", 1)
    if reversed_body != frozen:
        raise ProbeError("P9-D2 reverse marker deletion differs from frozen P9")
    if b"p9_d1" in actual.lower() or b"majorana_certificate_p9_d1" in actual.lower():
        raise ProbeError("P9-D2 clone directly references a prohibited D1 artifact")
    return {
        "frozen_P9_driver_sha256": P9_DRIVER_SHA256,
        "frozen_P9_driver_size_bytes": P9_DRIVER_SIZE,
        "clone_driver_sha256": sha256_bytes(actual),
        "exact_marker_insertion_block_count": len(blocks),
        "outer_phase_marker_block_count": 8,
        "schedule_marker_block_count": 4,
        "forward_byte_construction_matches": True,
        "reverse_deletion_matches_frozen_P9": True,
        "marker_blocks_contain_no_forbidden_live_state_tokens": True,
        "D1_artifacts_are_not_included_opened_or_staged_by_the_D2_driver": True,
        "P9_D0_resource_witness_construction_is_unreached_after_a_D2_terminal": True,
    }


def _stage_probe_tree(staging: Path, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Copy only the predeclared child inputs into a fresh process tree."""
    pins = _source_pins(policy)
    rows: list[dict[str, Any]] = []
    for relative in STAGED_PATHS:
        source = BASE / relative
        if not source.is_file() or source.is_symlink():
            raise ProbeError(f"invalid P9-D2 staged source: {relative}")
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target, follow_symlinks=False)
        body = source.read_bytes()
        staged = target.read_bytes()
        digest = sha256_bytes(body)
        if (
            pins[relative]["sha256"] != digest
            or pins[relative]["size_bytes"] != len(body)
            or staged != body
        ):
            raise ProbeError(f"P9-D2 staging custody drift: {relative}")
        rows.append({
            "relative_path": relative,
            "repository_sha256": digest,
            "staged_size_bytes": len(staged),
            "staged_sha256": sha256_bytes(staged),
            "byte_identical_to_repository": True,
        })
    return rows


class _PhaseCollector:
    """Transient bounded pipe collector; raw bytes never leave this process."""

    def __init__(
        self,
        read_fd: int,
        *,
        maximum_line_bytes: int,
        maximum_total_bytes: int,
        maximum_events: int,
    ) -> None:
        self.read_fd = read_fd
        self.maximum_line_bytes = maximum_line_bytes
        self.maximum_total_bytes = maximum_total_bytes
        self.maximum_events = maximum_events
        self.lines: list[bytes] = []
        self.total_bytes = 0
        self.eof = False
        self.overflow = False
        self.partial = False
        self.failure = False

    def run(self) -> None:
        pending = bytearray()
        try:
            while True:
                block = os.read(self.read_fd, 4096)
                if not block:
                    self.eof = True
                    break
                self.total_bytes += len(block)
                if self.total_bytes > self.maximum_total_bytes:
                    self.overflow = True
                    continue
                pending.extend(block)
                while b"\n" in pending:
                    end = pending.index(0x0A) + 1
                    line = bytes(pending[:end])
                    del pending[:end]
                    if len(line) > self.maximum_line_bytes or len(self.lines) >= self.maximum_events:
                        self.overflow = True
                    else:
                        self.lines.append(line)
                if len(pending) >= self.maximum_line_bytes:
                    self.overflow = True
                    pending.clear()
        except OSError:
            self.failure = True
        finally:
            self.partial = bool(pending)
            try:
                os.close(self.read_fd)
            except OSError:
                pass


class _BoundedStreamCollector:
    """Drain a child stream without retaining its bytes in outer memory."""

    def __init__(
        self,
        stream: Any,
        *,
        maximum_bytes: int,
        reject_any_bytes: bool,
        violation: threading.Event,
    ) -> None:
        if type(maximum_bytes) is not int or maximum_bytes < 0:
            raise ProbeError("invalid P9-D2 child stream byte cap")
        self.stream = stream
        self.maximum_bytes = maximum_bytes
        self.reject_any_bytes = reject_any_bytes
        self.violation = violation
        self.total_bytes = 0
        self.nonempty = False
        self.overflow = False
        self.eof = False
        self.failure = False

    def run(self) -> None:
        try:
            descriptor = self.stream.fileno()
            while True:
                block = os.read(descriptor, 65536)
                if not block:
                    self.eof = True
                    break
                self.total_bytes += len(block)
                self.nonempty = True
                if self.total_bytes > self.maximum_bytes:
                    self.overflow = True
                if self.reject_any_bytes or self.overflow:
                    self.violation.set()
        except OSError:
            self.failure = True
            self.violation.set()
        finally:
            try:
                self.stream.close()
            except OSError:
                pass


def _validate_phase_trace(
    collector: _PhaseCollector,
    fixture: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    """Reduce transient records to the fixed D2 DFA language only."""
    if collector.overflow or collector.partial or collector.failure:
        raise ProbeError("invalid P9-D2 phase transport")
    protocol = fixture["phase_event_protocol"]
    events: list[dict[str, Any]] = []
    for sequence, line in enumerate(collector.lines):
        record = loads_json(line, "P9-D2 phase record")
        if (
            not isinstance(record, dict)
            or set(record) != {"event", "sequence"}
            or type(record.get("sequence")) is not int
            or record.get("sequence") != sequence
            or record.get("event") not in PHASE_EVENTS
            or line != canonical_bytes(record) + b"\n"
        ):
            raise ProbeError("invalid P9-D2 phase record")
        events.append({"sequence": sequence, "event": record["event"]})
    if len(events) > protocol["maximum_event_count"]:
        raise ProbeError("P9-D2 phase trace exceeds its event cap")
    names = [event["event"] for event in events]
    terminal = [
        branch for branch, sequence in TERMINALS.items()
        if names == sequence
    ]
    prefixes = [
        branch for branch, sequence in TERMINALS.items()
        if names == sequence[:len(names)]
    ]
    if not prefixes or len(terminal) > 1:
        raise ProbeError("P9-D2 phase trace is not a legal DFA prefix")
    return events, terminal[0] if terminal else None


def _terminate_scope(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ("systemctl", "--user", "kill", "--kill-who=all", f"{unit}.scope"),
        check=False, capture_output=True,
    )
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _run_candidate(
    staging: Path,
    julia: Path,
    depot: Path,
    fixture: Mapping[str, Any],
    scratch_root: Path,
) -> dict[str, Any]:
    """Run the one allowed process and retain only its normalized DFA trace."""
    host = fixture["host_supervisor_caps"]
    protocol = fixture["phase_event_protocol"]
    scratch = scratch_root / "candidate"
    for name in ("depot", "home", "tmp"):
        (scratch / name).mkdir(parents=True, exist_ok=False)
    read_fd, write_fd = os.pipe()
    if read_fd < 3 or write_fd < 3:
        raise ProbeError("P9-D2 pipe descriptor is too small")
    os.set_inheritable(write_fd, True)
    collector = _PhaseCollector(
        read_fd,
        maximum_line_bytes=protocol["maximum_line_bytes_including_newline"],
        maximum_total_bytes=protocol["maximum_total_channel_bytes"],
        maximum_events=protocol["maximum_event_count"],
    )
    reader = threading.Thread(target=collector.run, name="p9-d2-phase-reader", daemon=True)
    reader.start()
    unit = "majorana-p9-d2-schedule-" + uuid.uuid4().hex
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"MemorySwapMax={host['MemorySwapMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}",
        "--", str(julia), "--startup-file=no", "--history-file=no",
        "--compiled-modules=no", f"--project={staging / 'majorana_certificate_p0'}",
        str(staging / CLONE_DRIVER), str(staging / FIXTURE_NAME),
        str(staging / P9_FIXTURE),
        str(staging / "majorana_certificate_p6_fixture.json"),
        str(staging / "majorana_certificate_p5_fixture.json"),
        str(staging / "majorana_certificate_p4_fixture.json"),
        str(staging / "majorana_certificate_p3_fixture.json"),
        str(staging / "majorana_certificate_p2_fixture.json"),
        P9_MODE, str(write_fd),
    ]
    environment = os.environ.copy()
    environment.update({
        "HOME": str(scratch / "home"),
        "TMPDIR": str(scratch / "tmp"),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "JULIA_DEPOT_PATH": f"{scratch / 'depot'}:{depot}",
        "JULIA_LOAD_PATH": "@",
        "JULIA_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
    })
    process: subprocess.Popen[bytes] | None = None
    outer_timeout = False
    process_returned = -1
    process_started = False
    stream_violation = threading.Event()
    stdout_collector: _BoundedStreamCollector | None = None
    stderr_collector: _BoundedStreamCollector | None = None
    stream_readers: list[threading.Thread] = []
    try:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                pass_fds=(write_fd,),
                close_fds=True,
            )
        except OSError:
            process = None
        else:
            process_started = True
            if process.stdout is None or process.stderr is None:
                raise ProbeError("P9-D2 child stream custody was not established")
            stdout_collector = _BoundedStreamCollector(
                process.stdout,
                maximum_bytes=host["maximum_stdout_bytes"],
                reject_any_bytes=True,
                violation=stream_violation,
            )
            stderr_collector = _BoundedStreamCollector(
                process.stderr,
                maximum_bytes=host["maximum_stderr_bytes"],
                reject_any_bytes=False,
                violation=stream_violation,
            )
            for name, stream_collector in (
                ("stdout", stdout_collector),
                ("stderr", stderr_collector),
            ):
                stream_reader = threading.Thread(
                    target=stream_collector.run,
                    name=f"p9-d2-{name}-reader",
                    daemon=True,
                )
                stream_reader.start()
                stream_readers.append(stream_reader)
            os.close(write_fd)
            write_fd = -1
            deadline = time.monotonic() + host["outer_safety_timeout_seconds"]
            while process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    outer_timeout = True
                    _terminate_scope(unit, process)
                    break
                if stream_violation.wait(timeout=min(0.25, remaining)):
                    _terminate_scope(unit, process)
                    break
            process_returned = process.returncode
    finally:
        try:
            if process is not None and process.poll() is None:
                _terminate_scope(unit, process)
        finally:
            if write_fd >= 0:
                os.close(write_fd)
            for stream_reader in stream_readers:
                stream_reader.join(timeout=15)
            reader.join(timeout=15)
    if reader.is_alive() or any(item.is_alive() for item in stream_readers):
        raise ProbeError("P9-D2 bounded child reader did not terminate")
    if stdout_collector is not None and stdout_collector.nonempty:
        raise ProbeError("invalid P9-D2 probe: stdout is not empty")
    if process_returned == INVALID_D2_PROBE_EXIT_CODE:
        raise ProbeError("invalid P9-D2 probe: inner custody or protocol rejection")
    events, terminal = _validate_phase_trace(collector, fixture)
    host_failed = (
        not process_started
        or outer_timeout
        or process_returned != 0
        or stdout_collector is None
        or stdout_collector.failure
        or not stdout_collector.eof
        or stderr_collector is None
        or stderr_collector.failure
        or stderr_collector.overflow
        or not stderr_collector.eof
        or not collector.eof
    )
    complete = terminal is not None
    if not host_failed and not complete:
        raise ProbeError("P9-D2 clean process lacks a complete terminal sequence")
    status = (
        "COMPLETED_PHASE_DIAGNOSTIC"
        if not host_failed else "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
    )
    trace_status = (
        "COMPLETE_TERMINAL_SEQUENCE" if complete else "LEGAL_PREFIX_INTERRUPTED"
    )
    observation = {
        "status": status,
        "diagnostic_terminal_branch": terminal,
        "phase_trace_status": trace_status,
        "phase_events": events,
        "phase_event_count": len(events),
        "phase_trace_protocol_sha256": canonical_sha256(events),
        "last_phase_event": events[-1]["event"] if events else None,
        "outer_timeout_triggered": outer_timeout,
        "host_failure_observed": host_failed,
        "resource_witness": None,
        "host_failure_has_no_mathematical_authority": True,
    }
    _validate_observation(observation, fixture)
    return observation


def _validate_observation(observation: Any, fixture: Mapping[str, Any]) -> None:
    expected = {
        "status", "diagnostic_terminal_branch", "phase_trace_status",
        "phase_events", "phase_event_count", "phase_trace_protocol_sha256",
        "last_phase_event", "outer_timeout_triggered", "host_failure_observed",
        "resource_witness", "host_failure_has_no_mathematical_authority",
    }
    if not isinstance(observation, dict) or set(observation) != expected:
        raise ProbeError("P9-D2 observation key set drift")
    if observation["status"] not in {
        "COMPLETED_PHASE_DIAGNOSTIC", "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
    }:
        raise ProbeError("P9-D2 observation status drift")
    if (
        type(observation["outer_timeout_triggered"]) is not bool
        or type(observation["host_failure_observed"]) is not bool
        or observation["resource_witness"] is not None
        or observation["host_failure_has_no_mathematical_authority"] is not True
    ):
        raise ProbeError("P9-D2 observation host boundary drift")
    events = observation["phase_events"]
    if (
        not isinstance(events, list)
        or type(observation["phase_event_count"]) is not int
        or len(events) != observation["phase_event_count"]
    ):
        raise ProbeError("P9-D2 phase-event count drift")
    if len(events) > fixture["phase_event_protocol"]["maximum_event_count"]:
        raise ProbeError("P9-D2 phase-event cap drift")
    names: list[str] = []
    for sequence, event in enumerate(events):
        if not isinstance(event, dict) or set(event) != {"sequence", "event"}:
            raise ProbeError("P9-D2 reported phase row drift")
        if (
            type(event.get("sequence")) is not int
            or event.get("sequence") != sequence
            or event.get("event") not in PHASE_EVENTS
        ):
            raise ProbeError("P9-D2 reported phase order drift")
        names.append(event["event"])
    if observation["phase_trace_protocol_sha256"] != canonical_sha256(events):
        raise ProbeError("P9-D2 phase protocol digest drift")
    if observation["last_phase_event"] != (names[-1] if names else None):
        raise ProbeError("P9-D2 last phase event drift")
    prefixes = [branch for branch, sequence in TERMINALS.items() if names == sequence[:len(names)]]
    exact = [branch for branch, sequence in TERMINALS.items() if names == sequence]
    if not prefixes or len(exact) > 1:
        raise ProbeError("P9-D2 report trace grammar drift")
    if observation["status"] == "COMPLETED_PHASE_DIAGNOSTIC":
        if (
            observation["host_failure_observed"]
            or observation["outer_timeout_triggered"]
            or len(exact) != 1
            or observation["diagnostic_terminal_branch"] != exact[0]
            or observation["phase_trace_status"] != "COMPLETE_TERMINAL_SEQUENCE"
        ):
            raise ProbeError("P9-D2 completed observation drift")
    else:
        expected_trace_status = (
            "COMPLETE_TERMINAL_SEQUENCE" if exact else "LEGAL_PREFIX_INTERRUPTED"
        )
        if (
            not observation["host_failure_observed"]
            or observation["phase_trace_status"] != expected_trace_status
            or observation["diagnostic_terminal_branch"] != (exact[0] if exact else None)
        ):
            raise ProbeError("P9-D2 indeterminate observation drift")


def _validate_preprobe_commit_identity(commit: str) -> None:
    """Require B0 to be exactly five new, pinned files atop D1 B1."""
    _require_sha(commit, "P9-D2 preprobe")
    if _parents(commit) != (D1_RESULT_COMMIT,):
        raise ProbeError("P9-D2 preprobe direct-parent drift")
    if _changed_paths(commit) != tuple(sorted(PREPROBE_CHANGED_PATHS)):
        raise ProbeError("P9-D2 preprobe changed-path set drift")
    for path in PREPROBE_CHANGED_PATHS:
        if _git_blob_optional(D1_RESULT_COMMIT, path) is not None:
            raise ProbeError("P9-D2 preprobe changed a non-new path")
        relative = path.removeprefix(ROOT)
        if _git_blob(commit, path) != _read_regular(relative):
            raise ProbeError("P9-D2 preprobe Git blob/current byte mismatch")
    for name in (REPORT_NAME, EXECUTION_CLAIM_NAME):
        if _git_blob_optional(commit, ROOT + name) is not None:
            raise ProbeError("P9-D2 preprobe already contains a run artifact")


def _validate_result_commit_identity(commit: str, report: Mapping[str, Any]) -> None:
    """Require B1 to add only the canonical report to its B0 parent."""
    _require_sha(commit, "P9-D2 result")
    preprobe = report.get("preprobe_commit_sha")
    if not isinstance(preprobe, str):
        raise ProbeError("P9-D2 result report preprobe receipt is malformed")
    _require_sha(preprobe, "P9-D2 report preprobe")
    if _parents(commit) != (preprobe,):
        raise ProbeError("P9-D2 result direct-parent drift")
    if _changed_paths(commit) != RESULT_CHANGED_PATHS:
        raise ProbeError("P9-D2 result changed-path set drift")
    if _git_blob_optional(preprobe, ROOT + REPORT_NAME) is not None:
        raise ProbeError("P9-D2 result parent already contains a report")
    report_blob = _git_blob(commit, ROOT + REPORT_NAME)
    if report_blob != canonical_bytes(report):
        raise ProbeError("P9-D2 result Git blob is not canonical report bytes")
    if report_blob != _read_regular(REPORT_NAME):
        raise ProbeError("P9-D2 result Git blob/current byte mismatch")


def _index_blob(path: str) -> bytes:
    raw = _git_bytes("ls-files", "--stage", "-z", "--", path)
    rows = raw.split(b"\0")
    if rows[-1] != b"" or len(rows) != 2:
        raise ProbeError("unexpected P9-D2 index record count")
    metadata, separator, actual = rows[0].partition(b"\t")
    fields = metadata.split(b" ")
    if (
        separator != b"\t"
        or actual != path.encode("utf-8")
        or len(fields) != 3
        or fields[0] != b"100644"
        or fields[2] != b"0"
    ):
        raise ProbeError("P9-D2 staged path is not a stage-zero regular blob")
    return _git_bytes("cat-file", "blob", fields[1].decode("ascii"))


def _validate_staged_preprobe() -> None:
    """Allow verification before committing B0, but only as exact additions."""
    if _git_text("rev-parse", "HEAD").strip() != D1_RESULT_COMMIT:
        raise ProbeError("P9-D2 staged preprobe must start at D1 B1")
    raw = _git_bytes("diff", "--cached", "--name-only", "-z").split(b"\0")
    added = _git_bytes(
        "diff", "--cached", "--name-only", "--diff-filter=A", "-z",
    ).split(b"\0")
    if raw[-1] != b"" or added[-1] != b"":
        raise ProbeError("P9-D2 staged paths are not NUL terminated")
    try:
        paths = tuple(sorted(item.decode("utf-8") for item in raw[:-1]))
        additions = tuple(sorted(item.decode("utf-8") for item in added[:-1]))
    except UnicodeDecodeError as error:
        raise ProbeError("P9-D2 staged path is not UTF-8") from error
    expected_paths = tuple(sorted(PREPROBE_CHANGED_PATHS))
    if paths != expected_paths or additions != expected_paths:
        raise ProbeError("P9-D2 staged preprobe path set drift")
    if _status_paths() != expected_paths:
        raise ProbeError("P9-D2 staged preprobe worktree path drift")
    for path in PREPROBE_CHANGED_PATHS:
        if _index_blob(path) != _read_regular(path.removeprefix(ROOT)):
            raise ProbeError("P9-D2 staged/current byte mismatch")


def verify_preprobe() -> dict[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    head = _git_text("rev-parse", "HEAD").strip()
    if head == D1_RESULT_COMMIT:
        _validate_staged_preprobe()
    else:
        if _status_paths():
            raise ProbeError("frozen P9-D2 preprobe worktree is not clean")
        _validate_preprobe_commit_identity(head)
    return {
        "status": "VERIFIED_P9_D2_STATIC_SCHEDULE_PREPROBE",
        "policy_id": policy["policy_id"],
    }


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _acquire_claim(commit: str) -> Path:
    claim = BASE / EXECUTION_CLAIM_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(claim, flags, 0o600)
    except FileExistsError as error:
        raise ProbeError("P9-D2 execution was already claimed") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write((commit + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(BASE)
    return claim


def _validate_claimed_preprobe_worktree(
    commit: str,
    claim: Path,
    report: Mapping[str, Any] | None,
) -> None:
    """Recheck B0 and the durable one-shot artifacts before claim release."""
    if claim != BASE / EXECUTION_CLAIM_NAME:
        raise ProbeError("P9-D2 execution claim path drift")
    _validate_preprobe_commit_identity(commit)
    if _git_text("rev-parse", "HEAD").strip() != commit:
        raise ProbeError("P9-D2 claimed preprobe HEAD drift")
    expected_paths = [ROOT + EXECUTION_CLAIM_NAME]
    if report is not None:
        expected_paths.append(ROOT + REPORT_NAME)
    if _status_paths() != tuple(sorted(expected_paths)):
        raise ProbeError("P9-D2 claimed preprobe worktree drift")
    try:
        claim_mode = claim.lstat().st_mode
    except FileNotFoundError as error:
        raise ProbeError("P9-D2 execution claim disappeared") from error
    if not stat.S_ISREG(claim_mode) or claim.read_bytes() != (commit + "\n").encode("ascii"):
        raise ProbeError("P9-D2 execution claim receipt drift")
    if report is not None:
        report_path = BASE / REPORT_NAME
        try:
            report_mode = report_path.lstat().st_mode
        except FileNotFoundError as error:
            raise ProbeError("P9-D2 canonical report disappeared") from error
        if (
            not stat.S_ISREG(report_mode)
            or report_path.read_bytes() != canonical_bytes(report)
        ):
            raise ProbeError("P9-D2 canonical report receipt drift")


def _write_canonical_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ProbeError("P9-D2 report already exists")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
            _fsync_directory(path.parent)


S0_ADMISSION = {
    "status": "NOT_ESTABLISHED_BY_P9_D2_STATIC_SCHEDULE_DIAGNOSTIC",
    "derived_from_D2": False,
    "D1_B1_status_unchanged": D1_ALLOWED_PROJECTION["future_S0_admission_status"],
    "same_host_admission_as_P9_D0": True,
}


def run_probe(preprobe_commit: str, julia: Path, depot: Path, output: Path) -> Mapping[str, Any]:
    """Execute the single claimed D2 run from an immutable B0 receipt."""
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    _validate_preprobe_commit_identity(preprobe_commit)
    if _git_text("rev-parse", "HEAD").strip() != preprobe_commit or _status_paths():
        raise ProbeError("P9-D2 must execute a clean frozen preprobe")
    if output.resolve() != (BASE / REPORT_NAME).resolve():
        raise ProbeError("P9-D2 report path must be canonical")
    julia = julia.resolve()
    depot = depot.resolve()
    if not julia.is_file() or file_sha256(julia) != fixture["runtime_custody"]["julia_executable_sha256"]:
        raise ProbeError("P9-D2 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P9-D2 depot is missing")
    for executable in ("systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P9-D2 missing executable: {executable}")
    with tempfile.TemporaryDirectory(prefix="majorana-p9-d2-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        manifest = _stage_probe_tree(staging, policy)
        scratch = root / "scratch"
        scratch.mkdir()
        claim = _acquire_claim(preprobe_commit)
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
        "D1_B1_parent_commit_sha": D1_RESULT_COMMIT,
        "D1_B1_parent_report_sha256": D1_REPORT_SHA256,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "staging_manifest": manifest,
        "staging_manifest_sha256": canonical_sha256(manifest),
        "source_clone_custody": _validate_static_clone(fixture),
        "observation": observation,
        "S0_admission": S0_ADMISSION,
        "authority_exclusions": fixture["authority_exclusions"],
    }
    validate_report(report)
    _validate_claimed_preprobe_worktree(preprobe_commit, claim, None)
    _write_canonical_json_exclusive(output, report)
    _validate_claimed_preprobe_worktree(preprobe_commit, claim, report)
    claim.unlink()
    _fsync_directory(BASE)
    return report


def _validate_manifest(rows: Any, policy: Mapping[str, Any], digest: Any) -> None:
    if not isinstance(rows, list) or [
        row.get("relative_path") for row in rows if isinstance(row, dict)
    ] != list(STAGED_PATHS):
        raise ProbeError("P9-D2 staging manifest path drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "byte_identical_to_repository",
        }:
            raise ProbeError("malformed P9-D2 staging row")
        relative = row["relative_path"]
        if relative not in pins:
            raise ProbeError("P9-D2 staging manifest contains an unpinned path")
        body = _read_regular(relative)
        digest_now = sha256_bytes(body)
        if (
            type(row["staged_size_bytes"]) is not int
            or row["repository_sha256"] != pins[relative]["sha256"]
            or row["staged_size_bytes"] != len(body)
            or row["staged_sha256"] != digest_now
            or row["repository_sha256"] != row["staged_sha256"]
            or row["byte_identical_to_repository"] is not True
        ):
            raise ProbeError("P9-D2 staging manifest custody drift")
    if digest != canonical_sha256(rows):
        raise ProbeError("P9-D2 staging manifest digest drift")


def validate_report(
    report: Any,
    *,
    require_result_commit: bool = False,
) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=False)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    expected = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "D1_B1_parent_commit_sha", "D1_B1_parent_report_sha256",
        "scientific_authority", "certificate_eligible", "result_contract_eligible",
        "staging_manifest", "staging_manifest_sha256", "source_clone_custody",
        "observation", "S0_admission", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected:
        raise ProbeError("P9-D2 report key set drift")
    if (
        type(report.get("schema_version")) is not int
        or report.get("schema_version") != 1
        or report.get("report_type") != REPORT_TYPE
        or report.get("policy_id") != POLICY_ID
        or report.get("fixture_id") != FIXTURE_ID
        or report.get("D1_B1_parent_commit_sha") != D1_RESULT_COMMIT
        or report.get("D1_B1_parent_report_sha256") != D1_REPORT_SHA256
        or report.get("scientific_authority") != "NONE"
        or report.get("certificate_eligible") is not False
        or report.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P9-D2 report identity or authority drift")
    if (
        report["policy_sha256"] != file_sha256(BASE / POLICY_NAME)
        or report["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME)
        or report["fixture_canonical_sha256"] != canonical_sha256(fixture)
        or report["source_clone_custody"] != _validate_static_clone(fixture)
        or report["S0_admission"] != S0_ADMISSION
        or report["authority_exclusions"] != fixture["authority_exclusions"]
    ):
        raise ProbeError("P9-D2 report source custody drift")
    preprobe = report.get("preprobe_commit_sha")
    if not isinstance(preprobe, str):
        raise ProbeError("P9-D2 report preprobe receipt is malformed")
    _validate_preprobe_commit_identity(preprobe)
    _validate_manifest(report["staging_manifest"], policy, report["staging_manifest_sha256"])
    _validate_observation(report["observation"], fixture)
    if require_result_commit:
        _validate_result_commit_identity(_git_text("rev-parse", "HEAD").strip(), report)
    return report


def verify_report(output: Path) -> Mapping[str, Any]:
    if output.resolve() != (BASE / REPORT_NAME).resolve():
        raise ProbeError("P9-D2 report path must be canonical")
    report = validate_report(load_json(output), require_result_commit=True)
    if output.read_bytes() != canonical_bytes(report):
        raise ProbeError("P9-D2 report is not canonical JSON")
    if _status_paths():
        raise ProbeError("frozen P9-D2 result worktree is not clean")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-preprobe", action="store_true")
    group.add_argument("--run", action="store_true")
    group.add_argument("--verify-report", action="store_true")
    parser.add_argument("--preprobe-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--output", type=Path, default=BASE / REPORT_NAME)
    args = parser.parse_args(argv)
    try:
        if args.verify_preprobe:
            result = verify_preprobe()
        elif args.run:
            if not all((args.preprobe_commit, args.julia, args.depot)):
                parser.error("--run requires --preprobe-commit, --julia, and --depot")
            report = run_probe(args.preprobe_commit, args.julia, args.depot, args.output)
            result = {
                "status": "COMPLETED_P9_D2_STATIC_SCHEDULE_PROBE",
                "observation_status": report["observation"]["status"],
                "last_phase_event": report["observation"]["last_phase_event"],
                "report_sha256": file_sha256(args.output),
            }
        else:
            report = verify_report(args.output)
            result = {
                "status": "VERIFIED_P9_D2_STATIC_SCHEDULE_REPORT",
                "observation_status": report["observation"]["status"],
                "last_phase_event": report["observation"]["last_phase_event"],
                "report_sha256": file_sha256(args.output),
            }
    except ProbeError as error:
        print(f"P9_D2_PROBE_ERROR: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
