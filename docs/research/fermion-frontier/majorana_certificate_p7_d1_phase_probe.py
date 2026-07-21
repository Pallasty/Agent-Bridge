#!/usr/bin/env python3
"""Run and verify the non-authoritative Majorana P7 D1 phase diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Mapping, Sequence
import uuid


# The frozen D0 module is loaded from source below.  A preprobe execution must
# not dirty its own worktree with import caches before the clean-tree gate.
sys.dont_write_bytecode = True


BASE = Path(__file__).resolve().parent
D0_ORCHESTRATOR_NAME = "majorana_certificate_p7_design_probe.py"
D0_POLICY_NAME = "majorana_certificate_p7_design_probe_policy.json"
D0_FIXTURE_NAME = "majorana_certificate_p7_design_probe_fixture.json"
D0_REPORT_NAME = "majorana_certificate_p7_design_probe_report.json"
D0_DRIVER = (
    "majorana_certificate_p7_design_probe/"
    "majorana_p7_step3_resource_probe.jl"
)
POLICY_NAME = "majorana_certificate_p7_d1_phase_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p7_d1_phase_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p7_d1_phase_probe_report.json"
TEST_NAME = "test_majorana_certificate_p7_d1_phase_probe.py"
EXECUTION_CLAIM_NAME = ".majorana_certificate_p7_d1_phase_probe.execution-claimed"
PROBE_DRIVER = (
    "majorana_certificate_p7_d1_phase_probe/"
    "majorana_p7_step3_phase_probe.jl"
)

_D0_SPEC = importlib.util.spec_from_file_location(
    "majorana_p7_d0_frozen", BASE / D0_ORCHESTRATOR_NAME,
)
if _D0_SPEC is None or _D0_SPEC.loader is None:
    raise RuntimeError("cannot load frozen P7 D0 orchestrator")
D0 = importlib.util.module_from_spec(_D0_SPEC)
_D0_SPEC.loader.exec_module(D0)

POLICY_ID = "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D1-PHASE-V1"
FIXTURE_ID = POLICY_ID
REPORT_TYPE = "majorana_p7_step3_e768_max_lazy37_phase_report_d1_v1"
DIAGNOSTIC_PROBE_ID = "P7-D1-E768-MAX-LAZY37-STEP3-PHASE-V1"
DIAGNOSTIC_MODE = "E768_MAX_LAZY37_STEP3_D1_PHASE_V1"
CANDIDATE_ID = "E768-MAX-LAZY37-STEP3-V1"
SCIENTIFIC_PROBE_MODE = "E768_MAX_LAZY37_STEP3_V1"
ALGORITHM_ID = "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1"
DIRECT_PARENT = "4ebed6b651e3c9605f84939d6a9efff8281bc38b"
D0_REPORT_SHA256 = (
    "4bf4be7f77fd499ffc9bd975f07353fd14ee7403cd6fc7759974dda37f8588cf"
)
D0_REPORT_SIZE_BYTES = 9781
D0_TERMINAL_STATUS = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
D0_ADMISSION_STATUS = (
    "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
)
POLICY_SEMANTIC_SHA256 = (
    "160263d1646965c2919a1cb09a0b339ffe04933ff865fe6890bd43d591758b24"
)
FIXTURE_CANONICAL_SHA256 = (
    "7b1f52866315cb241dbb24263d95fc0d61fc3fda83b2c05720bc89d2ca35c36d"
)
PHASE_PROTOCOL_CANONICAL_SHA256 = (
    "ed1b72ebef7f432725585d0efddff4373bd7cc9e54deea12973ab67101236d6c"
)
INVALID_D1_PROBE_EXIT_CODE = 66

STAGED_PATHS = tuple(D0.STAGED_PATHS) + (FIXTURE_NAME, PROBE_DRIVER)
SOURCE_PATHS = tuple((
    *STAGED_PATHS, D0_ORCHESTRATOR_NAME, D0_POLICY_NAME,
    Path(__file__).name, TEST_NAME,
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
    "status": "NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC",
    "derived_from_D1": False,
    "D0_status_unchanged": D0_ADMISSION_STATUS,
    "same_host_admission_as_D0": True,
}


class ProbeError(RuntimeError):
    """Fail-closed P7 D1 validation error."""


canonical_bytes = D0.canonical_bytes
canonical_sha256 = D0.canonical_sha256
file_sha256 = D0.file_sha256
loads_json = D0.loads_json
load_json = D0.load_json
write_canonical_json = D0.write_canonical_json


def _run_git(*args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args], cwd=BASE, check=check, capture_output=True,
    )
    return process.stdout.decode("utf-8").strip()


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise ProbeError("P7 D1 source_files is empty or malformed")
    pins: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "size_bytes", "sha256",
        }:
            raise ProbeError("malformed P7 D1 source pin")
        relative = row["relative_path"]
        if not isinstance(relative, str) or relative in pins:
            raise ProbeError("duplicate or invalid P7 D1 source pin")
        pins[relative] = row
    return pins


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    expected_top = {
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "diagnostic_role",
        "D0_parent_custody", "frozen_candidate_identity",
        "frozen_execution_relation", "phase_event_protocol",
        "phase_channel_custody", "host_supervisor_caps", "runtime_custody",
        "observation_scope", "authority_exclusions",
    }
    if not isinstance(fixture, dict) or set(fixture) != expected_top:
        raise ProbeError("P7 D1 fixture top-level key drift")
    if canonical_sha256(fixture) != FIXTURE_CANONICAL_SHA256:
        raise ProbeError("P7 D1 fixture semantic object drift")
    if (
        fixture.get("schema_version") != 1
        or type(fixture.get("schema_version")) is not int
        or fixture.get("fixture_id") != FIXTURE_ID
        or fixture.get("required_direct_parent_commit") != DIRECT_PARENT
        or fixture.get("scientific_authority") != "NONE"
        or fixture.get("certificate_eligible") is not False
        or fixture.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P7 D1 fixture identity or authority drift")
    role = fixture["diagnostic_role"]
    if (
        role.get("diagnostic_probe_id") != DIAGNOSTIC_PROBE_ID
        or role.get("classification")
        != "P7_D0_TIMEOUT_RESULT_INFORMED_D1_RESULT_UNPINNED_"
           "SCIENTIFIC_BLIND"
        or role.get("one_fresh_process_only") is not True
        or role.get("resource_and_phase_timing_diagnostic_only") is not True
        or role.get("D1_establishes_future_S0_admission") is not False
    ):
        raise ProbeError("P7 D1 diagnostic role drift")
    parent = fixture["D0_parent_custody"]
    if (
        parent.get("result_commit_sha") != DIRECT_PARENT
        or parent.get("report_relative_path") != D0_REPORT_NAME
        or parent.get("report_size_bytes") != D0_REPORT_SIZE_BYTES
        or parent.get("report_sha256") != D0_REPORT_SHA256
        or parent.get("report_type") != D0.REPORT_TYPE
        or parent.get("scientific_authority") != "NONE"
        or parent.get("terminal_status") != D0_TERMINAL_STATUS
        or parent.get("resource_witness_is_null") is not True
        or parent.get("future_S0_admission_status") != D0_ADMISSION_STATUS
        or parent.get("allowed_result_informed_facts_are_exhaustive") is not True
    ):
        raise ProbeError("P7 D1 D0-parent custody drift")
    identity = fixture["frozen_candidate_identity"]
    if identity != {
        "candidate_id": CANDIDATE_ID,
        "scientific_probe_mode": SCIENTIFIC_PROBE_MODE,
        "D1_diagnostic_mode": DIAGNOSTIC_MODE,
        "algorithm_id": ALGORITHM_ID,
        "D1_does_not_define_a_new_scientific_candidate": True,
    }:
        raise ProbeError("P7 D1 frozen candidate identity drift")
    relation = fixture["frozen_execution_relation"]
    required_true = {
        "all_three_steps_execute_in_one_process",
        "checkpoint_serialization_or_cross_process_resume_forbidden",
        "D1_includes_the_exact_source_pinned_D0_driver",
        "D1_reuses_the_frozen_P3_and_P6_scientific_kernels",
        "D1_adds_only_constant_count_outer_phase_emissions",
        "stage_composite_constituent_boundary_and_selection_hot_loop_"
        "instrumentation_forbidden",
        "D1_phase_IO_changes_the_runtime_path_and_therefore_has_no_S0_"
        "admission_authority",
    }
    if any(relation.get(key) is not True for key in required_true):
        raise ProbeError("P7 D1 frozen execution relation drift")
    protocol = fixture["phase_event_protocol"]
    if (
        canonical_sha256(protocol) != PHASE_PROTOCOL_CANONICAL_SHA256
        or
        protocol.get("schema_version") != 1
        or protocol.get("wire_record_exact_fields") != ["event", "sequence"]
        or protocol.get("sequence_origin") != 0
        or protocol.get("sequence_is_contiguous") is not True
        or protocol.get("maximum_event_count") != 32
        or protocol.get("maximum_line_bytes_including_newline") != 256
        or protocol.get("maximum_total_channel_bytes") != 8192
        or protocol.get("host_or_runtime_failure_may_retain_only_a_legal_"
                        "sequence_prefix") is not True
        or protocol.get("clean_exit_requires_exactly_one_complete_terminal_"
                        "sequence") is not True
    ):
        raise ProbeError("P7 D1 phase protocol envelope drift")
    events = protocol.get("allowed_events")
    terminals = protocol.get("legal_terminal_sequences")
    if (
        not isinstance(events, list) or len(events) != len(set(events))
        or not all(isinstance(item, str) and item for item in events)
        or not isinstance(terminals, dict) or set(terminals) != {
            "FULL_PATH_RETURNED", "STEP1_DETERMINISTIC_CAP",
            "STEP2_DETERMINISTIC_CAP",
            "P6_PREFIX_RESOURCE_CONFORMANCE_FAILURE",
            "STEP3_DETERMINISTIC_CAP",
        }
    ):
        raise ProbeError("P7 D1 phase language drift")
    for branch, sequence in terminals.items():
        if (
            not isinstance(sequence, list) or not sequence
            or any(event not in events for event in sequence)
            or len(sequence) != len(set(sequence))
            or sequence[0] != "D1_RUNNER_STARTED"
            or sequence[-1] != "D1_DIAGNOSTIC_COMPLETED"
        ):
            raise ProbeError(f"malformed P7 D1 terminal sequence: {branch}")
    channel = fixture["phase_channel_custody"]
    if (
        channel.get("transport")
        != "dedicated_inherited_anonymous_pipe_file_descriptor"
        or channel.get("wire_records_are_single_atomic_POSIX_pipe_writes")
        is not True
        or channel.get(
            "child_emits_no_timestamps_scientific_counts_scientific_indices_"
            "state_or_free_text_except_protocol_sequence"
        ) is not True
        or channel.get("stdout_is_strictly_empty") is not True
        or channel.get("stderr_is_not_a_phase_channel") is not True
        or channel.get("raw_channel_bytes_are_not_persisted") is not True
    ):
        raise ProbeError("P7 D1 phase-channel custody drift")
    d0_fixture = D0._validate_fixture(load_json(BASE / D0_FIXTURE_NAME))
    if fixture["host_supervisor_caps"] != d0_fixture["host_supervisor_caps"]:
        raise ProbeError("P7 D1 host admission differs from D0")
    if fixture["runtime_custody"] != d0_fixture["runtime_custody"]:
        raise ProbeError("P7 D1 runtime custody differs from D0")
    D0._validate_runtime_lock_bytes(fixture["runtime_custody"])
    scope = fixture["observation_scope"]
    if (
        scope.get("resource_witness", object()) is not None
        or scope.get("scientific_values_are_forbidden") is not True
        or scope.get("completed_D1_does_not_establish_future_S0_admission")
        is not True
    ):
        raise ProbeError("P7 D1 observation scope drift")
    if not isinstance(fixture["authority_exclusions"], list):
        raise ProbeError("P7 D1 authority exclusions drift")
    return fixture


def _validate_d0_parent(fixture: Mapping[str, Any]) -> Mapping[str, Any]:
    report_path = BASE / D0_REPORT_NAME
    if not report_path.is_file() or report_path.is_symlink():
        raise ProbeError("P7 D1 frozen D0 parent report is missing")
    body = report_path.read_bytes()
    if (
        len(body) != D0_REPORT_SIZE_BYTES
        or hashlib.sha256(body).hexdigest() != D0_REPORT_SHA256
    ):
        raise ProbeError("P7 D1 frozen D0 parent report bytes drift")
    try:
        report = D0.validate_report(loads_json(body, D0_REPORT_NAME))
    except D0.ProbeError as error:
        raise ProbeError("P7 D1 frozen D0 parent report is invalid") from error
    observations = report.get("observations")
    if (
        report.get("report_type") != fixture["D0_parent_custody"][
            "report_type"
        ]
        or report.get("scientific_authority") != "NONE"
        or not isinstance(observations, list) or len(observations) != 1
        or observations[0].get("status") != D0_TERMINAL_STATUS
        or observations[0].get("resource_witness") is not None
        or report.get("fixed_formal_admission", {}).get("status")
        != D0_ADMISSION_STATUS
    ):
        raise ProbeError("P7 D1 allowed D0 parent facts drift")
    return report


def validate_policy(
    policy: Any, *, require_report_absent: bool,
) -> Mapping[str, Any]:
    expected_top = {
        "schema_version", "policy_id", "policy_fingerprint",
        "required_direct_parent_commit", "policy_role",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "hindsight_firewall",
        "candidate_identity", "frozen_D0_dependency",
        "phase_event_protocol", "phase_channel_permissions",
        "D1_observation_contract", "host_supervisor_caps", "runtime",
        "state_custody_and_runner_visibility", "staged_source_custody",
        "preprobe_and_result_lifecycle", "stop_rules",
        "authority_exclusions", "source_files",
    }
    if not isinstance(policy, dict) or set(policy) != expected_top:
        raise ProbeError("P7 D1 policy top-level key drift")
    semantic = {key: value for key, value in policy.items()
                if key != "source_files"}
    if canonical_sha256(semantic) != POLICY_SEMANTIC_SHA256:
        raise ProbeError("P7 D1 policy semantic object drift")
    if (
        policy.get("schema_version") != 1
        or type(policy.get("schema_version")) is not int
        or policy.get("policy_id") != POLICY_ID
        or policy.get("required_direct_parent_commit") != DIRECT_PARENT
        or policy.get("scientific_authority") != "NONE"
        or policy.get("certificate_eligible") is not False
        or policy.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P7 D1 policy identity or authority drift")
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    if policy["candidate_identity"] != fixture["frozen_candidate_identity"]:
        raise ProbeError("P7 D1 policy candidate identity drift")
    if policy["frozen_D0_dependency"] != fixture["D0_parent_custody"]:
        raise ProbeError("P7 D1 policy D0 dependency drift")
    if policy["phase_event_protocol"] != {
        "fixture_relative_path": FIXTURE_NAME,
        "fixture_phase_event_protocol_canonical_sha256":
            PHASE_PROTOCOL_CANONICAL_SHA256,
        "constant_count_outer_events_only": True,
        "host_failure_trace_must_be_a_legal_terminal_sequence_prefix": True,
        "clean_exit_requires_one_complete_terminal_sequence": True,
    }:
        raise ProbeError("P7 D1 policy phase protocol drift")
    if policy["host_supervisor_caps"] != fixture["host_supervisor_caps"]:
        raise ProbeError("P7 D1 policy host admission drift")
    if policy["runtime"] != fixture["runtime_custody"]:
        raise ProbeError("P7 D1 policy runtime custody drift")
    if policy["authority_exclusions"] != fixture["authority_exclusions"]:
        raise ProbeError("P7 D1 policy authority exclusions drift")
    firewall = policy["hindsight_firewall"]
    if (
        firewall.get("classification")
        != "P7_D0_TIMEOUT_RESULT_INFORMED_D1_RESULT_UNPINNED_"
           "SCIENTIFIC_BLIND"
        or firewall.get("D1_result_unpinned_before_precommit") is not True
        or firewall.get("allowed_D0_result_facts_are_exhaustive") is not True
        or firewall.get("D1_cannot_change_candidate_algorithm_caps_host_"
                        "admission_or_fallback_in_place") is not True
    ):
        raise ProbeError("P7 D1 hindsight firewall drift")
    if firewall.get("allowed_D0_result_facts") != [
        "D0_report_identity_and_scientific_authority_NONE",
        "D0_terminal_status_INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        "D0_resource_witness_is_null",
        "D0_future_S0_admission_is_not_established",
    ]:
        raise ProbeError("P7 D1 allowed D0 result facts drift")
    forbidden = firewall.get("forbidden_D0_or_suppressed_inputs")
    if not isinstance(forbidden, list) or len(forbidden) < 5:
        raise ProbeError("P7 D1 hindsight exclusions are incomplete")
    channel = policy["phase_channel_permissions"]
    if (
        channel.get("transport")
        != fixture["phase_channel_custody"]["transport"]
        or channel.get("stdout_must_be_exactly_empty") is not True
        or channel.get("stderr_must_not_be_parsed_for_phase_branching")
        is not True
        or channel.get("raw_pipe_bytes_must_not_be_persisted") is not True
        or channel.get(
            "event_names_must_not_contain_scientific_state_counts_"
            "scientific_indices_ticks_budgets_or_free_text_except_frozen_"
            "step_labels"
        ) is not True
    ):
        raise ProbeError("P7 D1 channel permissions drift")
    observation = policy["D1_observation_contract"]
    if (
        observation.get("report_observation_exact_fields")
        != sorted(OBSERVATION_FIELDS)
        or observation.get("report_phase_event_exact_fields")
        != sorted(PHASE_EVENT_REPORT_FIELDS)
        or observation.get("resource_witness_is_always_null") is not True
        or observation.get("S0_admission") != S0_ADMISSION
    ):
        raise ProbeError("P7 D1 observation contract drift")
    staged = policy["staged_source_custody"]
    if (
        staged.get("staged_path_order") != list(STAGED_PATHS)
        or staged.get("exact_staged_path_count") != len(STAGED_PATHS)
        or staged.get("D0_report_policy_and_Python_orchestrators_are_not_"
                      "runner_staged") is not True
        or staged.get("D1_driver_includes_the_exact_staged_D0_driver")
        is not True
        or staged.get("source_or_AST_transform_is_forbidden") is not True
    ):
        raise ProbeError("P7 D1 staged-source custody drift")
    visibility = policy["state_custody_and_runner_visibility"]
    if (
        visibility.get("each_D1_execution_starts_from_O0") is not True
        or visibility.get("all_steps_share_one_live_process") is not True
        or visibility.get("checkpoint_or_serialized_resume_is_forbidden")
        is not True
        or visibility.get("D0_report_is_outer_checker_only_and_not_staged")
        is not True
        or visibility.get("phase_trace_must_not_enter_any_future_runner")
        is not True
        or visibility.get("one_exclusive_nonresult_execution_claim_is_"
                          "acquired_immediately_before_process_launch")
        is not True
        or visibility.get("an_abnormal_post_claim_stop_retains_the_claim_and_"
                          "forbids_a_repeat") is not True
    ):
        raise ProbeError("P7 D1 state custody drift")
    pins = _source_pins(policy)
    if set(pins) != set(SOURCE_PATHS):
        raise ProbeError("P7 D1 source pin allowlist drift")
    for relative, row in pins.items():
        path = BASE / relative
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"missing or nonregular P7 D1 source: {relative}")
        body = path.read_bytes()
        if (
            row.get("size_bytes") != len(body)
            or row.get("sha256") != hashlib.sha256(body).hexdigest()
        ):
            raise ProbeError(f"P7 D1 source pin drift: {relative}")
    _validate_d0_parent(fixture)
    if require_report_absent and (BASE / REPORT_NAME).exists():
        raise ProbeError("P7 D1 report exists before the preprobe commit")
    if require_report_absent and (
        (BASE / EXECUTION_CLAIM_NAME).exists()
        or (BASE / EXECUTION_CLAIM_NAME).is_symlink()
    ):
        raise ProbeError("P7 D1 execution claim already exists")
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
            raise ProbeError(f"invalid P7 D1 staged source: {relative}")
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
            raise ProbeError(f"P7 D1 staging custody failure: {relative}")
        rows.append(row)
    return rows


class _PhaseCollector:
    def __init__(
        self, read_fd: int, started_ns: int, *, max_line_bytes: int,
        max_total_bytes: int, max_events: int,
    ) -> None:
        self._read_fd = read_fd
        self._started_ns = started_ns
        self._max_line_bytes = max_line_bytes
        self._max_total_bytes = max_total_bytes
        self._max_events = max_events
        self.lines: list[tuple[bytes, int]] = []
        self.total_bytes = 0
        self.digest = hashlib.sha256()
        self.eof = False
        self.overflow = False
        self.trailing_partial = False
        self.read_failure = False
        self._stop_requested = threading.Event()

    def request_stop(self) -> None:
        self._stop_requested.set()

    def run(self) -> None:
        pending = bytearray()
        try:
            os.set_blocking(self._read_fd, False)
            while not self._stop_requested.is_set():
                readable, _, _ = select.select([self._read_fd], [], [], 0.25)
                if not readable:
                    continue
                try:
                    block = os.read(self._read_fd, 4096)
                except BlockingIOError:
                    continue
                if not block:
                    self.eof = True
                    break
                self.total_bytes += len(block)
                self.digest.update(block)
                if self.total_bytes > self._max_total_bytes:
                    self.overflow = True
                    pending.clear()
                    continue
                if self.overflow:
                    continue
                pending.extend(block)
                while True:
                    try:
                        boundary = pending.index(0x0A)
                    except ValueError:
                        if len(pending) >= self._max_line_bytes:
                            self.overflow = True
                            pending.clear()
                        break
                    line = bytes(pending[:boundary + 1])
                    del pending[:boundary + 1]
                    if len(line) > self._max_line_bytes:
                        self.overflow = True
                    if len(self.lines) >= self._max_events:
                        self.overflow = True
                        pending.clear()
                        break
                    else:
                        self.lines.append((
                            line, time.monotonic_ns() - self._started_ns,
                        ))
        except OSError:
            self.read_failure = True
        finally:
            if self._stop_requested.is_set() and not self.eof:
                self.read_failure = True
            if pending:
                self.trailing_partial = True
            try:
                os.close(self._read_fd)
            except OSError:
                pass

    @property
    def sha256(self) -> str:
        return self.digest.hexdigest()


class _BoundedStreamCollector:
    """Drain one child stream without retaining more than the frozen cap."""

    def __init__(self, handle: Any, maximum_capture_bytes: int) -> None:
        self._handle = handle
        self._file_descriptor = handle.fileno()
        self._maximum_capture_bytes = maximum_capture_bytes
        self.total_bytes = 0
        self.digest = hashlib.sha256()
        self.payload = bytearray()
        self.eof = False
        self.read_failure = False
        self._stop_requested = threading.Event()

    def run(self) -> None:
        try:
            os.set_blocking(self._file_descriptor, False)
            while not self._stop_requested.is_set():
                readable, _, _ = select.select(
                    [self._file_descriptor], [], [], 0.25,
                )
                if not readable:
                    continue
                try:
                    block = os.read(self._file_descriptor, 64 * 1024)
                except BlockingIOError:
                    continue
                if not block:
                    self.eof = True
                    break
                self.total_bytes += len(block)
                self.digest.update(block)
                remaining = self._maximum_capture_bytes - len(self.payload)
                if remaining > 0:
                    self.payload.extend(block[:remaining])
        except (OSError, ValueError):
            self.read_failure = True
        finally:
            if self._stop_requested.is_set() and not self.eof:
                self.read_failure = True
            try:
                self._handle.close()
            except (OSError, ValueError):
                pass

    def request_stop(self) -> None:
        self._stop_requested.set()

    @property
    def sha256(self) -> str:
        return self.digest.hexdigest()


def _validate_phase_trace(
    collector: _PhaseCollector, fixture: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    if collector.overflow:
        raise ProbeError("INVALID_D1_PROBE: phase channel exceeded a frozen cap")
    if collector.trailing_partial:
        raise ProbeError("INVALID_D1_PROBE: phase channel ended with a partial line")
    protocol = fixture["phase_event_protocol"]
    allowed = set(protocol["allowed_events"])
    events: list[dict[str, Any]] = []
    for expected_sequence, (line, received_ns) in enumerate(collector.lines):
        try:
            record = loads_json(line, "P7 D1 phase record")
        except D0.ProbeError as error:
            raise ProbeError("INVALID_D1_PROBE: malformed phase JSON") from error
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
            raise ProbeError("INVALID_D1_PROBE: phase record protocol drift")
        events.append({
            "sequence": expected_sequence,
            "event": record["event"],
            "outer_receive_elapsed_ns": received_ns,
        })
    names = [row["event"] for row in events]
    terminals = protocol["legal_terminal_sequences"]
    matching_prefixes = [
        branch for branch, sequence in terminals.items()
        if names == sequence[:len(names)]
    ]
    if not matching_prefixes:
        raise ProbeError("INVALID_D1_PROBE: phase trace is not a legal prefix")
    terminal = [
        branch for branch, sequence in terminals.items() if names == sequence
    ]
    if len(terminal) > 1 or (terminal and len(matching_prefixes) != 1):
        raise ProbeError("INVALID_D1_PROBE: ambiguous phase terminal")
    return events, terminal[0] if terminal else None


def _terminate_scope(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ["systemctl", "--user", "kill", "--kill-who=all", f"{unit}.scope"],
        check=False, capture_output=True,
    )
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _observation_from_process(
    *, process_started: bool, returncode: int, timed_out: bool,
    stdout_bytes: int, stdout_sha256: str, stderr_bytes: int,
    stderr_sha256: str, stderr_for_time: bytes, elapsed_ns: int,
    collector: _PhaseCollector, fixture: Mapping[str, Any],
) -> dict[str, Any]:
    transport_failed = collector.read_failure or not collector.eof
    events, terminal_branch = _validate_phase_trace(collector, fixture)
    if stdout_bytes:
        raise ProbeError("INVALID_D1_PROBE: stdout must be exactly empty")
    if returncode == INVALID_D1_PROBE_EXIT_CODE:
        raise ProbeError("INVALID_D1_PROBE: Julia rejected custody or schema")
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
                "INVALID_D1_PROBE: clean exit lacks a complete terminal trace"
            )
        status = "COMPLETED_PHASE_DIAGNOSTIC"
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


def _run_candidate(
    staging: Path, julia: Path, depot: Path, fixture: Mapping[str, Any],
    scratch_root: Path,
) -> dict[str, Any]:
    host = fixture["host_supervisor_caps"]
    protocol = fixture["phase_event_protocol"]
    scratch = scratch_root / "candidate"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    unit = "majorana-p7-d1-phase-" + uuid.uuid4().hex
    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, True)
    started_ns = time.monotonic_ns()
    collector = _PhaseCollector(
        read_fd, started_ns,
        max_line_bytes=protocol["maximum_line_bytes_including_newline"],
        max_total_bytes=protocol["maximum_total_channel_bytes"],
        max_events=protocol["maximum_event_count"],
    )
    reader = threading.Thread(
        target=collector.run, name="p7-d1-phase-reader", daemon=True,
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
            raise ProbeError("P7 D1 child streams were not captured")
        stdout_collector = _BoundedStreamCollector(
            process.stdout, 0,
        )
        stderr_collector = _BoundedStreamCollector(
            process.stderr, host["maximum_stderr_bytes"],
        )
        stream_threads = [
            threading.Thread(
                target=stdout_collector.run, name="p7-d1-stdout-reader",
                daemon=True,
            ),
            threading.Thread(
                target=stderr_collector.run, name="p7-d1-stderr-reader",
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
            raise ProbeError("P7 D1 supervisor failed after process launch") from error
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
        raise ProbeError("P7 D1 supervisor reader failed to terminate")
    if process_started:
        if (
            stdout_collector is None or stderr_collector is None
            or stdout_collector.read_failure or stderr_collector.read_failure
            or not stdout_collector.eof or not stderr_collector.eof
        ):
            raise ProbeError("P7 D1 stdout/stderr capture failed")
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
        raise ProbeError("P7 D1 preprobe commit is not a full lowercase SHA-1")
    try:
        ancestry = _run_git("rev-list", "--parents", "-n", "1", preprobe_commit)
    except subprocess.CalledProcessError as error:
        raise ProbeError("P7 D1 preprobe commit is not present") from error
    if ancestry.split() != [preprobe_commit, DIRECT_PARENT]:
        raise ProbeError("P7 D1 preprobe commit has the wrong direct parent")
    changed = set(filter(None, _run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", preprobe_commit,
    ).splitlines()))
    if changed != PREPROBE_CHANGED_PATHS:
        raise ProbeError("P7 D1 preprobe changed-path allowlist drift")
    for relative in sorted(PREPROBE_CHANGED_PATHS):
        current = BASE.parent.parent.parent / relative
        if not current.is_file() or current.is_symlink():
            raise ProbeError(f"P7 D1 current preprobe source is invalid: {relative}")
        blob = subprocess.run(
            ["git", "show", f"{preprobe_commit}:{relative}"], cwd=BASE,
            check=False, capture_output=True,
        )
        if blob.returncode != 0 or blob.stdout != current.read_bytes():
            raise ProbeError(f"P7 D1 preprobe blob custody drift: {relative}")
    artifact = f"{preprobe_commit}:docs/research/fermion-frontier/{REPORT_NAME}"
    if subprocess.run(
        ["git", "cat-file", "-e", artifact], cwd=BASE,
        check=False, capture_output=True,
    ).returncode == 0:
        raise ProbeError("P7 D1 report exists in the preprobe commit")


def _validate_preprobe_commit(preprobe_commit: str) -> None:
    _validate_preprobe_commit_identity(preprobe_commit)
    if _run_git("rev-parse", "HEAD") != preprobe_commit:
        raise ProbeError("P7 D1 HEAD differs from requested preprobe commit")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ProbeError("P7 D1 worktree is not clean before execution")


def _canonical_output_path(output: Path) -> Path:
    canonical = BASE / REPORT_NAME
    requested = Path(os.path.abspath(output))
    if requested != canonical:
        raise ProbeError("P7 D1 run output must be the canonical report path")
    if canonical.exists() or canonical.is_symlink():
        raise ProbeError("P7 D1 canonical report path already exists")
    return canonical


def _acquire_execution_claim(preprobe_commit: str) -> Path:
    claim = BASE / EXECUTION_CLAIM_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(claim, flags, 0o600)
    except FileExistsError as error:
        raise ProbeError("P7 D1 execution was already claimed") from error
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
    policy = validate_policy(load_json(BASE / POLICY_NAME),
                             require_report_absent=True)
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
        raise ProbeError("P7 D1 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P7 D1 depot is missing")
    for executable in ("systemd-run", "systemctl", "/usr/bin/time"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P7 D1 missing required executable: {executable}")
    with tempfile.TemporaryDirectory(prefix="majorana-p7-d1-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        staging_manifest = stage_probe_tree(staging, policy)
        scratch = root / "scratch"
        scratch.mkdir()
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
        "D0_parent_result_commit_sha": DIRECT_PARENT,
        "D0_parent_report_sha256": D0_REPORT_SHA256,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "candidate": fixture["frozen_candidate_identity"],
        "staging_manifest": staging_manifest,
        "staging_manifest_sha256": canonical_sha256(staging_manifest),
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
        raise ProbeError("P7 D1 staging manifest path drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "byte_identical_to_repository",
        }:
            raise ProbeError("malformed P7 D1 staging row")
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
            raise ProbeError("P7 D1 staging manifest custody drift")
    if digest != canonical_sha256(rows):
        raise ProbeError("P7 D1 staging manifest hash mismatch")


def _validate_observation(
    value: Any, fixture: Mapping[str, Any],
) -> None:
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS:
        raise ProbeError("malformed P7 D1 observation")
    if value["status"] not in {
        "COMPLETED_PHASE_DIAGNOSTIC",
        "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
    }:
        raise ProbeError("unexpected P7 D1 observation status")
    for key in (
        "process_returncode", "outer_monotonic_elapsed_ns", "stdout_bytes",
        "stderr_bytes", "phase_event_count", "phase_channel_bytes",
    ):
        if type(value[key]) is not int:
            raise ProbeError(f"invalid P7 D1 observation integer: {key}")
    if (
        value["outer_monotonic_elapsed_ns"] <= 0
        or value["process_returncode"] == INVALID_D1_PROBE_EXIT_CODE
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
        raise ProbeError("P7 D1 observation invariant drift")
    for key in (
        "stdout_sha256", "stderr_sha256", "phase_trace_protocol_sha256",
        "phase_channel_sha256",
    ):
        item = value[key]
        if (
            not isinstance(item, str) or len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
        ):
            raise ProbeError(f"invalid P7 D1 digest: {key}")
    if value["stdout_sha256"] != hashlib.sha256(b"").hexdigest():
        raise ProbeError("P7 D1 stdout digest is nonempty")
    events = value["phase_events"]
    if (
        not isinstance(events, list)
        or len(events) != value["phase_event_count"]
        or len(events) > fixture["phase_event_protocol"]["maximum_event_count"]
    ):
        raise ProbeError("P7 D1 phase event count drift")
    previous_ns = -1
    protocol_rows: list[dict[str, Any]] = []
    raw = bytearray()
    for sequence, row in enumerate(events):
        if not isinstance(row, dict) or set(row) != PHASE_EVENT_REPORT_FIELDS:
            raise ProbeError("malformed P7 D1 reported phase event")
        if (
            row["sequence"] != sequence
            or row["event"] not in
            fixture["phase_event_protocol"]["allowed_events"]
            or type(row["outer_receive_elapsed_ns"]) is not int
            or row["outer_receive_elapsed_ns"] < previous_ns
            or row["outer_receive_elapsed_ns"]
            > value["outer_monotonic_elapsed_ns"]
        ):
            raise ProbeError("invalid P7 D1 reported phase event")
        previous_ns = row["outer_receive_elapsed_ns"]
        protocol_row = {"sequence": sequence, "event": row["event"]}
        protocol_rows.append(protocol_row)
        raw.extend(canonical_bytes(protocol_row) + b"\n")
    if (
        value["phase_trace_protocol_sha256"]
        != canonical_sha256(protocol_rows)
        or value["phase_channel_bytes"] != len(raw)
        or value["phase_channel_sha256"]
        != hashlib.sha256(raw).hexdigest()
        or value["last_phase_event"]
        != (events[-1]["event"] if events else None)
    ):
        raise ProbeError("P7 D1 phase trace custody mismatch")
    names = [row["event"] for row in events]
    terminals = fixture["phase_event_protocol"]["legal_terminal_sequences"]
    matching = [branch for branch, sequence in terminals.items()
                if names == sequence[:len(names)]]
    exact = [branch for branch, sequence in terminals.items()
             if names == sequence]
    if not matching or len(exact) > 1:
        raise ProbeError("P7 D1 report phase grammar drift")
    host = fixture["host_supervisor_caps"]
    host_failed = (
        not value["process_started"] or value["outer_timeout_triggered"]
        or value["process_returncode"] != 0
        or value["stderr_bytes"] > host["maximum_stderr_bytes"]
        or value["outer_monotonic_elapsed_ns"]
        > host["outer_safety_timeout_seconds"] * 1_000_000_000
        or value["phase_channel_eof"] is not True
    )
    if value["status"] == "COMPLETED_PHASE_DIAGNOSTIC":
        if (
            host_failed or len(exact) != 1
            or value["diagnostic_terminal_branch"] != exact[0]
            or value["phase_trace_status"] != "COMPLETE_TERMINAL_SEQUENCE"
        ):
            raise ProbeError("invalid completed P7 D1 observation")
    elif (
        not host_failed
        or value["phase_trace_status"] != "LEGAL_PREFIX_INTERRUPTED"
        or value["diagnostic_terminal_branch"]
        != (exact[0] if exact else None)
    ):
        raise ProbeError("invalid indeterminate P7 D1 observation")
    D0._validate_time_diagnostics(
        value["time_diagnostics"],
        completed=value["status"] == "COMPLETED_PHASE_DIAGNOSTIC",
    )


def validate_report(report: Any) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME),
                             require_report_absent=False)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    expected_top = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "D0_parent_result_commit_sha",
        "D0_parent_report_sha256", "scientific_authority",
        "certificate_eligible", "result_contract_eligible", "candidate",
        "staging_manifest", "staging_manifest_sha256", "host_caps",
        "observation", "S0_admission", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected_top:
        raise ProbeError("malformed P7 D1 report")
    if (
        report.get("schema_version") != 1
        or type(report.get("schema_version")) is not int
        or report.get("report_type") != REPORT_TYPE
        or report.get("policy_id") != POLICY_ID
        or report.get("fixture_id") != FIXTURE_ID
        or report.get("D0_parent_result_commit_sha") != DIRECT_PARENT
        or report.get("D0_parent_report_sha256") != D0_REPORT_SHA256
        or report.get("scientific_authority") != "NONE"
        or report.get("certificate_eligible") is not False
        or report.get("result_contract_eligible") is not False
    ):
        raise ProbeError("P7 D1 report identity or authority drift")
    if (
        report["policy_sha256"] != file_sha256(BASE / POLICY_NAME)
        or report["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME)
        or report["fixture_canonical_sha256"] != canonical_sha256(fixture)
        or report["candidate"] != fixture["frozen_candidate_identity"]
        or report["host_caps"] != fixture["host_supervisor_caps"]
        or report["S0_admission"] != S0_ADMISSION
        or report["authority_exclusions"] != fixture["authority_exclusions"]
    ):
        raise ProbeError("P7 D1 report source or scope custody drift")
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
            "status": "VERIFIED_P7_D1_PHASE_PREPROBE",
            "policy_id": policy["policy_id"],
        }
    elif args.run:
        if not all((args.preprobe_commit, args.julia, args.depot)):
            parser.error("run requires preprobe commit, Julia, and depot")
        report = run_probe(
            args.preprobe_commit, args.julia, args.depot, args.output,
        )
        summary = {
            "status": "COMPLETED_P7_D1_PHASE_PROBE",
            "report_sha256": file_sha256(args.output),
            "observation_status": report["observation"]["status"],
            "last_phase_event": report["observation"]["last_phase_event"],
            "S0_admission_status": report["S0_admission"]["status"],
        }
    else:
        report = validate_report(load_json(args.output))
        if args.output.read_bytes() != canonical_bytes(report) + b"\n":
            raise ProbeError("P7 D1 report is not canonical JSON plus newline")
        summary = {
            "status": "VERIFIED_P7_D1_PHASE_REPORT",
            "report_sha256": file_sha256(args.output),
            "observation_status": report["observation"]["status"],
            "last_phase_event": report["observation"]["last_phase_event"],
            "S0_admission_status": report["S0_admission"]["status"],
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
