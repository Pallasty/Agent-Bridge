#!/usr/bin/env python3
"""Contract tests for the P9-D3 phase-only segment-D subgrid diagnostic."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
FIXTURE_PATH = BASE / "majorana_certificate_p9_d3_segment_d_probe_fixture.json"
POLICY_PATH = BASE / "majorana_certificate_p9_d3_segment_d_probe_policy.json"
D2_REPORT_PATH = BASE / "majorana_certificate_p9_d2_schedule_probe_report.json"
D3_MODULE_PATH = BASE / "majorana_certificate_p9_d3_segment_d_probe.py"

SPEC = importlib.util.spec_from_file_location("majorana_p9_d3", D3_MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P9-D3 module")
D3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D3)

D2_RESULT_COMMIT = "770076085452822a0128a5898042d986b5c2ec36"
D2_PREPROBE_COMMIT = "4eedd7a65f5c9ddcf8940e3a40a9246e059a30b8"
D2_REPORT_SHA256 = "c0e78bdb445a52d08a7cf0eba25c6a265068d7304d4f757170bc76fc02455b0b"
D2_REPORT_SIZE = 8170
POLICY_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D3-SEGMENT-D-SUBGRID-V1"
REPORT_TYPE = "majorana_p9_step3_e768_bitorder_segment_d_subgrid_report_d3_v1"

SUBGRID_ORDINALS = [20, 24, 28]
SUBGRID_EVENTS = [
    "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED",
    "STEP3_SEGMENT_D_SUBGRID_BETA_REACHED",
    "STEP3_SEGMENT_D_SUBGRID_GAMMA_REACHED",
]
ALLOWED_PARTIAL_COUNTS = [
    1, 2, 3,
    5, 6, 7,
    9, 10, 11,
    13, 14, 15, 16, 17, 18,
    20, 21, 22,
    24, 25, 26,
    28, 29, 30,
    32, 33, 34,
    36, 37, 38,
]
FORBIDDEN_PARTIAL_COUNTS = [0, 4, 8, 12, 19, 23, 27, 31, 35]

B0_PATHS = {
    "docs/research/fermion-frontier/majorana_certificate_p9_d3_segment_d_probe.py",
    "docs/research/fermion-frontier/majorana_certificate_p9_d3_segment_d_probe/"
    "majorana_p9_bit_order_step3_segment_d_probe.jl",
    "docs/research/fermion-frontier/majorana_certificate_p9_d3_segment_d_probe_fixture.json",
    "docs/research/fermion-frontier/majorana_certificate_p9_d3_segment_d_probe_policy.json",
    "docs/research/fermion-frontier/test_majorana_certificate_p9_d3_segment_d_probe.py",
}
B1_REPORT_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p9_d3_segment_d_probe_report.json"
)

STAGED_PATHS = [
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
    "majorana_certificate_p9_bit_order_resource_probe_fixture.json",
    "majorana_certificate_p9_d3_segment_d_probe_fixture.json",
    "majorana_certificate_p9_d3_segment_d_probe/"
    "majorana_p9_bit_order_step3_segment_d_probe.jl",
]


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path.name} must contain a JSON object")
    return value


def expected_internal_schedule() -> list[str]:
    events: list[str] = []
    for label in "ABCDEFGHI":
        events.extend([
            f"STEP3_SEGMENT_{label}_STARTED",
            f"STEP3_SEGMENT_{label}_CHECKPOINT_1_REACHED",
        ])
        if label == "D":
            events.extend(SUBGRID_EVENTS)
        events.extend([
            f"STEP3_SEGMENT_{label}_CHECKPOINT_2_REACHED",
            f"STEP3_SEGMENT_{label}_RETURNED",
        ])
    return events


class MajoranaP9D3SegmentDContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_object(FIXTURE_PATH)
        cls.policy = load_object(POLICY_PATH)
        cls.d2_report = load_object(D2_REPORT_PATH)

    def _collector(self, events: list[str]) -> SimpleNamespace:
        lines = [
            D3.canonical_bytes({"event": event, "sequence": index}) + b"\n"
            for index, event in enumerate(events)
        ]
        return SimpleNamespace(
            overflow=False,
            partial=False,
            failure=False,
            lines=lines,
            eof=True,
        )

    def _observation(
        self,
        names: list[str],
        *,
        status: str,
        branch: str | None,
        trace_status: str,
        host_failed: bool,
        outer_timeout: bool = False,
    ) -> dict[str, object]:
        events = [
            {"sequence": index, "event": event}
            for index, event in enumerate(names)
        ]
        return {
            "status": status,
            "diagnostic_terminal_branch": branch,
            "phase_trace_status": trace_status,
            "phase_events": events,
            "phase_event_count": len(events),
            "phase_trace_protocol_sha256": D3.canonical_sha256(events),
            "last_phase_event": names[-1] if names else None,
            "outer_timeout_triggered": outer_timeout,
            "host_failure_observed": host_failed,
            "resource_witness": None,
            "host_failure_has_no_mathematical_authority": True,
        }

    def test_direct_parent_and_exhaustive_minimal_d2_projection_are_frozen(self) -> None:
        fixture = D3._validate_fixture(self.fixture)
        custody = fixture["d2_parent_custody"]
        self.assertEqual(fixture["fixture_id"], POLICY_ID)
        self.assertEqual(fixture["required_direct_parent_commit"], D2_RESULT_COMMIT)
        self.assertEqual(custody["result_commit_sha"], D2_RESULT_COMMIT)
        self.assertEqual(custody["preprobe_commit_sha"], D2_PREPROBE_COMMIT)
        self.assertEqual(custody["report_schema_version"], 1)
        self.assertEqual(custody["report_size_bytes"], D2_REPORT_SIZE)
        self.assertEqual(custody["report_sha256"], D2_REPORT_SHA256)
        report_bytes = D2_REPORT_PATH.read_bytes()
        self.assertEqual(len(report_bytes), D2_REPORT_SIZE)
        self.assertEqual(hashlib.sha256(report_bytes).hexdigest(), D2_REPORT_SHA256)

        report = self.d2_report
        observation = report["observation"]
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["scientific_authority"], "NONE")
        self.assertFalse(report["certificate_eligible"])
        self.assertFalse(report["result_contract_eligible"])
        self.assertEqual(observation["status"], custody["terminal_status"])
        self.assertEqual(observation["phase_trace_status"], custody["phase_trace_status"])
        self.assertIsNone(observation["diagnostic_terminal_branch"])
        names = [row["event"] for row in observation["phase_events"]]
        required = [
            "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
            "STEP3_ENGINE_STARTED",
            "STEP3_STATE_INITIALIZED",
            "STEP3_SCHEDULE_ENTERED",
            "STEP3_SEGMENT_A_RETURNED",
            "STEP3_SEGMENT_B_RETURNED",
            "STEP3_SEGMENT_C_RETURNED",
            "STEP3_SEGMENT_D_STARTED",
            "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED",
        ]
        for event in required:
            self.assertIn(event, names)
        forbidden = [
            "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
            "STEP3_SEGMENT_D_RETURNED",
            "STEP3_SEGMENT_E_STARTED",
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D2_DIAGNOSTIC_COMPLETED",
        ]
        for event in forbidden:
            self.assertNotIn(event, names)
        self.assertIsNone(observation["resource_witness"])
        self.assertEqual(
            report["S0_admission"]["status"],
            custody["future_S0_admission_status"],
        )

        driver, d2_fixture, projection = D3._target_p9_d2_projection()
        self.assertEqual(projection, D3.D2_ALLOWED_PROJECTION)
        self.assertEqual(hashlib.sha256(driver).hexdigest(), D3.P9_DRIVER_SHA256)
        self.assertEqual(len(driver), D3.P9_DRIVER_SIZE)
        self.assertEqual(hashlib.sha256(d2_fixture).hexdigest(), D3.D2_FIXTURE_SHA256)
        self.assertEqual(len(d2_fixture), D3.D2_FIXTURE_SIZE)
        self.assertEqual(set(projection), set(D3.D2_ALLOWED_PROJECTION))
        self.assertTrue(custody["diagnostic_terminal_branch_is_null"])
        self.assertFalse(custody["D2_diagnostic_completed_marker_reached"])
        self.assertFalse(custody["later_schedule_markers_reached"])

    def test_static_segment_d_subgrid_language_is_exact(self) -> None:
        mapping = self.fixture["step3_schedule_marker_map"]
        protocol = self.fixture["phase_event_protocol"]
        parameterized = protocol["parameterized_step3_engine_return_terminal"]

        self.assertEqual(mapping["stage_order"], list("ABCDEFGHI"))
        self.assertEqual(
            mapping["frozen_group_order"],
            ["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"],
        )
        self.assertEqual(
            mapping["frozen_composite_count_per_stage"],
            [64, 48, 64, 48, 64, 48, 64, 48, 64],
        )
        self.assertEqual(
            mapping["checkpoint_1_completed_composite_ordinal_per_stage"],
            [22, 16, 22, 16, 22, 16, 22, 16, 22],
        )
        self.assertEqual(
            mapping["checkpoint_2_completed_composite_ordinal_per_stage"],
            [43, 32, 43, 32, 43, 32, 43, 32, 43],
        )
        self.assertEqual(
            mapping["segment_D_anonymous_subgrid_completed_composite_ordinals"],
            SUBGRID_ORDINALS,
        )
        self.assertEqual(mapping["segment_D_anonymous_subgrid_events"], SUBGRID_EVENTS)
        self.assertEqual(mapping["segment_D_subgrid_partition_width_in_composites"], 4)
        self.assertEqual(mapping["segment_D_subgrid_partition_count"], 4)
        self.assertTrue(mapping["three_internal_markers_are_the_minimum_for_four_equal_partitions"])
        self.assertTrue(mapping["subgrid_wire_event_names_are_anonymous_and_export_no_ordinal"])

        internal = expected_internal_schedule()
        self.assertEqual(len(internal), 39)
        self.assertEqual(list(D3.SCHEDULE_EVENTS), internal)
        self.assertEqual(parameterized["internal_schedule_event_sequence"], internal)
        self.assertEqual(
            internal[12:19],
            [
                "STEP3_SEGMENT_D_STARTED",
                "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED",
                *SUBGRID_EVENTS,
                "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
                "STEP3_SEGMENT_D_RETURNED",
            ],
        )
        self.assertEqual(parameterized["full_schedule_internal_event_count"], 39)
        self.assertEqual(
            parameterized["fixed_prefix_through_step3_schedule_entered"][-3:],
            ["STEP3_ENGINE_STARTED", "STEP3_STATE_INITIALIZED", "STEP3_SCHEDULE_ENTERED"],
        )
        self.assertEqual(
            parameterized["allowed_partial_internal_prefix_event_counts"],
            ALLOWED_PARTIAL_COUNTS,
        )
        self.assertEqual(
            parameterized["forbidden_partial_internal_prefix_event_counts"],
            FORBIDDEN_PARTIAL_COUNTS,
        )
        suffix = [
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D3_DIAGNOSTIC_COMPLETED",
        ]
        self.assertEqual(parameterized["partial_schedule_suffix"], suffix)
        self.assertEqual(parameterized["full_schedule_suffix"], suffix)
        self.assertEqual(parameterized["exact_partial_terminal_count"], 30)
        self.assertEqual(parameterized["exact_total_step3_engine_return_terminal_count"], 31)
        self.assertEqual(protocol["exact_total_legal_terminal_count"], 32)
        self.assertEqual(protocol["allowed_event_vocabulary_count"], 52)
        self.assertEqual(len(protocol["allowed_events"]), 52)
        self.assertEqual(len(set(protocol["allowed_events"])), 52)
        self.assertEqual(protocol["maximum_event_count"], 51)
        self.assertEqual(protocol["maximum_line_bytes_including_newline"], 256)
        self.assertEqual(protocol["maximum_total_channel_bytes"], 8192)

        execution = self.policy["D3_execution_contract"]
        self.assertEqual(execution["phase_event_vocabulary_count"], 52)
        self.assertEqual(execution["phase_event_protocol_maximum_event_count"], 51)
        self.assertEqual(execution["ordered_internal_schedule_event_count"], 39)
        self.assertEqual(execution["exact_legal_terminal_count"], 32)
        self.assertEqual(execution["allowed_early_schedule_prefix_event_counts"], ALLOWED_PARTIAL_COUNTS)
        self.assertEqual(execution["forbidden_early_schedule_prefix_event_counts"], FORBIDDEN_PARTIAL_COUNTS)

    def test_every_precommitted_terminal_language_is_accepted(self) -> None:
        self.assertEqual(len(D3.TERMINALS), 32)
        partial_branches = [
            branch for branch in D3.TERMINALS
            if branch.startswith("STEP3_ENGINE_RETURNED_AFTER_SCHEDULE_PREFIX_")
        ]
        self.assertEqual(len(partial_branches), 30)
        for branch, sequence in D3.TERMINALS.items():
            events, terminal = D3._validate_phase_trace(
                self._collector(sequence), self.fixture,
            )
            self.assertEqual(terminal, branch)
            self.assertEqual([row["event"] for row in events], sequence)
        full = D3.TERMINALS[
            "STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"
        ]
        self.assertEqual(len(full), 51)
        full_bytes = sum(
            len(D3.canonical_bytes({"event": event, "sequence": index}) + b"\n")
            for index, event in enumerate(full)
        )
        self.assertEqual(full_bytes, 2832)
        self.assertEqual(
            self.fixture["phase_event_protocol"]["exact_maximum_legal_canonical_trace_bytes"],
            full_bytes,
        )
        maximum_line = max(
            len(D3.canonical_bytes({"event": event, "sequence": index}) + b"\n")
            for sequence in D3.TERMINALS.values()
            for index, event in enumerate(sequence)
        )
        self.assertEqual(maximum_line, 81)

    def test_schedule_boundary_early_returns_are_rejected(self) -> None:
        prefix = D3._step3_schedule_common_prefix()
        suffix = [
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D3_DIAGNOSTIC_COMPLETED",
        ]
        for count in FORBIDDEN_PARTIAL_COUNTS:
            invalid = prefix + list(D3.SCHEDULE_EVENTS[:count]) + suffix
            with self.subTest(internal_schedule_event_count=count):
                with self.assertRaises(D3.ProbeError):
                    D3._validate_phase_trace(self._collector(invalid), self.fixture)

    def test_interruption_must_retain_a_legal_dfa_prefix(self) -> None:
        for branch, sequence in D3.TERMINALS.items():
            for count in range(len(sequence)):
                with self.subTest(branch=branch, prefix_event_count=count):
                    legal_prefix = sequence[:count]
                    events, terminal = D3._validate_phase_trace(
                        self._collector(legal_prefix), self.fixture,
                    )
                    self.assertIsNone(terminal)
                    self.assertEqual([row["event"] for row in events], legal_prefix)
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(
                self._collector([
                    "D3_RUNNER_STARTED",
                    "D3_STATIC_SETUP_COMPLETED",
                ]),
                self.fixture,
            )

    def test_phase_wire_rejects_noncanonical_or_unbounded_records(self) -> None:
        collector = self._collector(["D3_RUNNER_STARTED"])
        collector.lines[0] = b'{"sequence": 0, "event": "D3_RUNNER_STARTED"}\n'
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(collector, self.fixture)

        collector = self._collector(["D3_RUNNER_STARTED"])
        collector.lines[0] = D3.canonical_bytes({
            "event": "D3_RUNNER_STARTED", "sequence": 1,
        }) + b"\n"
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(collector, self.fixture)

        collector = self._collector([
            "D3_RUNNER_STARTED",
            "D3_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        ])
        collector.lines[1] = D3.canonical_bytes({
            "event": "D3_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
            "sequence": True,
        }) + b"\n"
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(collector, self.fixture)

        for flag in ("overflow", "partial", "failure"):
            collector = self._collector(["D3_RUNNER_STARTED"])
            setattr(collector, flag, True)
            with self.subTest(transport_flag=flag):
                with self.assertRaises(D3.ProbeError):
                    D3._validate_phase_trace(collector, self.fixture)

    def test_static_clone_is_exactly_forward_and_reverse_derived(self) -> None:
        relation = D3._validate_static_clone(self.fixture)
        self.assertTrue(relation["forward_byte_construction_matches"])
        self.assertTrue(relation["reverse_deletion_matches_frozen_P9"])
        self.assertEqual(relation["exact_marker_insertion_block_count"], 12)
        self.assertEqual(relation["outer_phase_marker_block_count"], 8)
        self.assertEqual(relation["schedule_marker_block_count"], 4)
        self.assertTrue(relation["marker_blocks_contain_no_forbidden_live_state_tokens"])
        self.assertTrue(
            relation["D2_artifacts_are_not_included_opened_or_staged_by_the_D3_driver"]
        )

    def test_subgrid_markers_are_anonymous_and_at_distinct_control_points(self) -> None:
        clone_path = BASE / D3.CLONE_DRIVER
        source = clone_path.read_text(encoding="utf-8")
        for event in SUBGRID_EVENTS:
            self.assertIn(event, source)
        for ordinal in SUBGRID_ORDINALS:
            self.assertNotIn(f"SUBGRID_{ordinal}_REACHED", source)

        wrapper = source[
            source.index("function p9_execute_bit_order_step("):
            source.index("function p9_execute_prefix(")
        ]
        self.assertLess(
            wrapper.index("execution = execute_p9_step3_bitorder("),
            wrapper.index('p9_d3_emit("STEP3_SCHEDULE_RETURNED")'),
        )
        self.assertLess(
            wrapper.index('p9_d3_emit("STEP3_SCHEDULE_RETURNED")'),
            wrapper.index("final_cap = execution.cap_event"),
        )

        schedule = source[
            source.index("function execute_p9_step3_bitorder("):
            source.index("function main_p9_d0()")
        ]
        self.assertLess(
            schedule.index("cap_event = nothing"),
            schedule.index('p9_d3_emit("STEP3_STATE_INITIALIZED")'),
        )
        self.assertLess(
            schedule.index('p9_d3_emit("STEP3_SCHEDULE_ENTERED")'),
            schedule.index("try\n        for stage in stages"),
        )
        for forbidden in (
            "completed_constituents", "majoranas", "coefficient", "mask",
            "ticks", "budget", "selection_resources", "resource_summary",
        ):
            marker_lines = "\n".join(
                line for line in schedule.splitlines()
                if "p9_d3_emit" in line and "STEP3_SEGMENT" in line
            ).lower()
            self.assertNotIn(forbidden, marker_lines)

    def test_phase_contract_excludes_measurement_and_scientific_data(self) -> None:
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8").lower()
        for forbidden in (
            "outer_receive_elapsed", "outer_monotonic_elapsed", "maximum_resident",
            "process_returncode", "stderr_sha256", "stdout_sha256",
            "time_diagnostics", "phase_channel_sha256",
        ):
            self.assertNotIn(forbidden, fixture_text)
        custody = self.fixture["phase_channel_custody"]
        self.assertTrue(
            custody[
                "child_emits_no_timestamp_term_count_index_mask_coefficient_tick_budget_cap_resource_or_free_text"
            ]
        )
        self.assertTrue(custody["anonymous_subgrid_event_names_export_no_completed_composite_ordinal"])
        self.assertTrue(
            self.fixture["step3_schedule_marker_map"]
            ["constituent_boundary_selection_callback_and_hot_loop_markers_are_forbidden"]
        )
        report_contract = self.policy["phase_report_contract"]
        self.assertTrue(
            report_contract[
                "no_D0_D1_D2_or_D3_timing_RSS_stderr_stdout_returncode_or_resource_measurement_is_persisted"
            ]
        )
        self.assertTrue(
            report_contract[
                "no_raw_phase_channel_bytes_hash_byte_count_or_receive_times_are_persisted"
            ]
        )

        full_branch = "STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"
        full = D3.TERMINALS[full_branch]
        completed = self._observation(
            full,
            status="COMPLETED_PHASE_DIAGNOSTIC",
            branch=full_branch,
            trace_status="COMPLETE_TERMINAL_SEQUENCE",
            host_failed=False,
        )
        D3._validate_observation(completed, self.fixture)
        forbidden_fields = {
            "outer_receive_elapsed_ns",
            "outer_monotonic_elapsed_ns",
            "process_returncode",
            "stderr_bytes",
            "stderr_sha256",
            "stdout_bytes",
            "stdout_sha256",
            "time_diagnostics",
            "maximum_resident_set_size",
            "raw_phase_channel_bytes",
            "phase_channel_sha256",
        }
        self.assertTrue(forbidden_fields.isdisjoint(completed))
        contaminated = dict(completed)
        contaminated["process_returncode"] = 0
        with self.assertRaises(D3.ProbeError):
            D3._validate_observation(contaminated, self.fixture)

        noninteger_count = dict(completed)
        noninteger_count["phase_event_count"] = float(len(full))
        with self.assertRaises(D3.ProbeError):
            D3._validate_observation(noninteger_count, self.fixture)

        interrupted_names = full[:24]
        interrupted = self._observation(
            interrupted_names,
            status="INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            branch=None,
            trace_status="LEGAL_PREFIX_INTERRUPTED",
            host_failed=True,
            outer_timeout=True,
        )
        D3._validate_observation(interrupted, self.fixture)

        exact_with_host_failure = self._observation(
            full,
            status="INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            branch=full_branch,
            trace_status="COMPLETE_TERMINAL_SEQUENCE",
            host_failed=True,
        )
        D3._validate_observation(exact_with_host_failure, self.fixture)
        contradictory = dict(exact_with_host_failure)
        contradictory["phase_trace_status"] = "LEGAL_PREFIX_INTERRUPTED"
        with self.assertRaises(D3.ProbeError):
            D3._validate_observation(contradictory, self.fixture)

    def test_child_stdout_and_stderr_collectors_are_memory_bounded(self) -> None:
        def collect(
            payload: bytes, *, maximum: int, reject_any: bool,
        ) -> tuple[object, threading.Event]:
            read_fd, write_fd = os.pipe()
            stream = os.fdopen(read_fd, "rb", buffering=0)
            violation = threading.Event()
            collector = D3._BoundedStreamCollector(
                stream,
                maximum_bytes=maximum,
                reject_any_bytes=reject_any,
                violation=violation,
            )
            os.write(write_fd, payload)
            os.close(write_fd)
            collector.run()
            return collector, violation

        empty, empty_violation = collect(b"", maximum=4, reject_any=True)
        self.assertTrue(empty.eof)
        self.assertFalse(empty.nonempty)
        self.assertFalse(empty_violation.is_set())

        stdout, stdout_violation = collect(b"x", maximum=4, reject_any=True)
        self.assertEqual(stdout.total_bytes, 1)
        self.assertTrue(stdout.nonempty)
        self.assertFalse(stdout.overflow)
        self.assertTrue(stdout_violation.is_set())

        stderr, stderr_violation = collect(b"12345", maximum=4, reject_any=False)
        self.assertEqual(stderr.total_bytes, 5)
        self.assertTrue(stderr.overflow)
        self.assertTrue(stderr_violation.is_set())
        for collector in (empty, stdout, stderr):
            self.assertFalse(hasattr(collector, "bytes"))
            self.assertFalse(hasattr(collector, "payload"))

    def test_parent_projection_does_not_read_suppressed_d2_measurements(self) -> None:
        source = inspect.getsource(D3._target_p9_d2_projection)
        for forbidden in (
            "outer_timeout_triggered",
            "host_failure_observed",
            "phase_event_count",
            "phase_trace_protocol_sha256",
            "returncode",
            "stdout",
            "stderr",
            "elapsed",
            "maximum_resident",
            "time_diagnostics",
        ):
            self.assertNotIn(forbidden, source)
        custody = self.fixture["phase_channel_custody"]
        self.assertTrue(
            custody[
                "D2_phase_trace_is_transiently_validated_but_must_not_cross_the_minimal_projection_firewall_into_the_D3_child_or_persisted_state"
            ]
        )
        firewall = self.policy["hindsight_firewall"]
        forbidden_after_validation = firewall[
            "forbidden_D2_or_suppressed_inputs_beyond_transient_parent_validation"
        ]
        self.assertIn(
            "D2_complete_phase_event_array_event_count_or_phase_digest_after_transient_exact_parent_validation",
            forbidden_after_validation,
        )
        self.assertIn(
            "D2_fixture_bytes_after_transient_host_and_runtime_custody_validation",
            forbidden_after_validation,
        )

    def test_no_runtime_source_or_ast_transform_route_exists(self) -> None:
        source = D3_MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        self.assertNotIn("runpy", imported_modules)
        self.assertNotIn("ast", imported_modules)
        self.assertNotIn("exec(", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("ast.parse(", inspect.getsource(D3._build_expected_clone))
        self.assertTrue(all("p9_d2" not in path.lower() for path in D3.STAGED_PATHS))
        self.assertNotIn(D3.D2_REPORT, D3.STAGED_PATHS)

    def test_b0_and_b1_path_gates_are_explicit(self) -> None:
        lifecycle = self.policy["preprobe_and_result_lifecycle"]
        self.assertEqual(len(B0_PATHS), 5)
        self.assertNotIn(B1_REPORT_PATH, B0_PATHS)
        self.assertTrue(lifecycle["B0_has_exactly_five_new_paths_and_is_a_direct_child_of_D2_B1"])
        self.assertTrue(lifecycle["B0_cannot_contain_a_D3_report_or_execution_claim"])
        self.assertTrue(lifecycle["B1_has_exactly_one_new_path_the_canonical_D3_report_and_is_a_direct_child_of_B0"])
        self.assertTrue(lifecycle["B1_report_Git_blob_must_equal_canonical_report_bytes_and_the_clean_worktree_file"])
        self.assertTrue(lifecycle["B1_verification_must_reject_any_extra_changed_path_or_dirty_worktree"])
        self.assertTrue(
            lifecycle[
                "claimed_B0_HEAD_and_worktree_are_reverified_before_report_write_and_claim_release"
            ]
        )
        self.assertIn('"--untracked-files=all"', inspect.getsource(D3._status_paths))
        self.assertIn("_fsync_directory(BASE)", inspect.getsource(D3._acquire_claim))

    def test_staging_and_source_pin_manifest_are_explicit(self) -> None:
        custody = self.policy["staged_source_custody"]
        self.assertEqual(self.policy["policy_id"], POLICY_ID)
        self.assertEqual(self.policy["required_direct_parent_commit"], D2_RESULT_COMMIT)
        self.assertEqual(self.policy["phase_report_contract"]["report_type"], REPORT_TYPE)
        self.assertEqual(custody["staged_path_order"], STAGED_PATHS)
        self.assertEqual(custody["exact_staged_path_count"], 14)
        self.assertEqual(list(D3.STAGED_PATHS), STAGED_PATHS)
        self.assertTrue(
            custody[
                "D2_report_policy_fixture_Python_and_clone_are_outer_checker_only_and_not_staged"
            ]
        )
        self.assertTrue(custody["original_P9_driver_is_outer_checker_only_and_not_staged"])

        rows = self.policy["source_files"]
        self.assertEqual(self.policy["exact_source_file_count"], 18)
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row["relative_path"] for row in rows}), 18)
        self.assertEqual(
            [row["relative_path"] for row in rows],
            list(D3.SOURCE_PATHS),
        )
        self.assertEqual(self.policy["source_pins_status"], "FROZEN_EXACT")
        for row in rows:
            relative = row["relative_path"]
            body = (BASE / relative).read_bytes()
            self.assertEqual(row["size_bytes"], len(body), relative)
            self.assertEqual(
                row["sha256"], hashlib.sha256(body).hexdigest(), relative,
            )
        D3.validate_policy(self.policy, require_report_absent=True)

    def test_only_allowed_post_d3_route_is_single_partition_d4(self) -> None:
        fixture_route = self.fixture["post_D3_route_contract"]
        policy_route = self.policy["phase_report_contract"]
        self.assertTrue(
            fixture_route[
                "route_is_available_only_for_a_legal_interrupted_prefix_inside_one_segment_D_subgrid_partition"
            ]
        )
        self.assertEqual(
            policy_route["only_allowed_post_D3_refinement_route"],
            "a_new_precommitted_D4_static_per_composite_DFA_for_the_single_four_composite_partition_containing_a_legal_D3_interruption",
        )
        expected_routes = [
            (
                "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED",
                "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED",
                [17, 18, 19, 20],
            ),
            (
                "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED",
                "STEP3_SEGMENT_D_SUBGRID_BETA_REACHED",
                [21, 22, 23, 24],
            ),
            (
                "STEP3_SEGMENT_D_SUBGRID_BETA_REACHED",
                "STEP3_SEGMENT_D_SUBGRID_GAMMA_REACHED",
                [25, 26, 27, 28],
            ),
            (
                "STEP3_SEGMENT_D_SUBGRID_GAMMA_REACHED",
                "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
                [29, 30, 31, 32],
            ),
        ]
        rows = policy_route["target_partition_route_map"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            [
                (
                    row["last_reached_boundary"],
                    row["required_absent_next_boundary"],
                    row["only_allowed_D4_completed_composite_ordinals"],
                )
                for row in rows
            ],
            expected_routes,
        )
        self.assertTrue(policy_route["complete_invalid_or_outside_target_D3_traces_do_not_authorize_this_D4_route"])
        self.assertTrue(policy_route["D3_phase_trace_must_not_enter_the_D4_runner"])
        self.assertTrue(policy_route["no_automatic_repeat_or_in_place_cap_relaxation_is_allowed"])

    def test_d2_projection_compatibility_alias_is_published(self) -> None:
        self.assertIs(D3._target_p9_d2_projection, D3._target_d2_b1_projection)

    def test_frozen_preprobe_or_report_is_verifiable_after_commit(self) -> None:
        report_path = BASE / D3.REPORT_NAME
        head = D3._git_text("rev-parse", "HEAD").strip()
        if report_path.exists():
            report = D3.verify_report(report_path)
            self.assertEqual(report["report_type"], REPORT_TYPE)
            self.assertEqual(D3.RESULT_CHANGED_PATHS, (D3.ROOT + D3.REPORT_NAME,))
        elif head != D2_RESULT_COMMIT:
            receipt = D3.verify_preprobe()
            self.assertEqual(
                receipt["status"], "VERIFIED_P9_D3_SEGMENT_D_SUBGRID_PREPROBE",
            )
        else:
            self.skipTest("P9-D3 B0 is not yet committed")


if __name__ == "__main__":
    unittest.main()
