#!/usr/bin/env python3
"""Contract tests for the P9-D4 phase-only segment-D per-composite diagnostic."""

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
FIXTURE_PATH = BASE / "majorana_certificate_p9_d4_segment_d_per_composite_probe_fixture.json"
POLICY_PATH = BASE / "majorana_certificate_p9_d4_segment_d_per_composite_probe_policy.json"
D3_REPORT_PATH = BASE / "majorana_certificate_p9_d3_segment_d_probe_report.json"
D4_MODULE_PATH = BASE / "majorana_certificate_p9_d4_segment_d_per_composite_probe.py"

SPEC = importlib.util.spec_from_file_location("majorana_p9_d4", D4_MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P9-D4 module")
D4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D4)

D3_RESULT_COMMIT = "e1f3d12bfaa51076ffea4ed43752c664970a4c92"
D3_PREPROBE_COMMIT = "430f6fb19cace09ba920e50887e4dbfbdf34d497"
D3_REPORT_SHA256 = "61cebcf8553333449927147640e5fed278e0156befa8d66c2cb68df13bf5f2ea"
D3_REPORT_SIZE = 8275
POLICY_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D4-SEGMENT-D-PER-COMPOSITE-V1"
REPORT_TYPE = "majorana_p9_step3_e768_bitorder_segment_d_per_composite_report_d4_v1"

RETAINED_SUBGRID_ORDINALS = [20, 28]
RETAINED_SUBGRID_EVENTS = [
    "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED",
    "STEP3_SEGMENT_D_SUBGRID_GAMMA_REACHED",
]
PER_COMPOSITE_ORDINALS = [21, 22, 23, 24]
PER_COMPOSITE_EVENTS = [
    "STEP3_SEGMENT_D_COMPOSITE_KAPPA_REACHED",
    "STEP3_SEGMENT_D_COMPOSITE_LAMBDA_REACHED",
    "STEP3_SEGMENT_D_COMPOSITE_MU_REACHED",
    "STEP3_SEGMENT_D_COMPOSITE_NU_REACHED",
]
BETA_EVENT = "STEP3_SEGMENT_D_SUBGRID_BETA_REACHED"
ALLOWED_PARTIAL_COUNTS = [
    1, 2, 3,
    5, 6, 7,
    9, 10, 11,
    13, 14, 15, 16, 17, 18, 19, 20, 21,
    23, 24, 25,
    27, 28, 29,
    31, 32, 33,
    35, 36, 37,
    39, 40, 41,
]
FORBIDDEN_PARTIAL_COUNTS = [0, 4, 8, 12, 22, 26, 30, 34, 38]

B0_PATHS = {
    "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe.py",
    "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe/"
    "majorana_p9_bit_order_step3_segment_d_per_composite_probe.jl",
    "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe_fixture.json",
    "docs/research/fermion-frontier/majorana_certificate_p9_d4_segment_d_per_composite_probe_policy.json",
    "docs/research/fermion-frontier/test_majorana_certificate_p9_d4_segment_d_per_composite_probe.py",
}
B1_REPORT_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p9_d4_segment_d_per_composite_probe_report.json"
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
    "majorana_certificate_p9_d4_segment_d_per_composite_probe_fixture.json",
    "majorana_certificate_p9_d4_segment_d_per_composite_probe/"
    "majorana_p9_bit_order_step3_segment_d_per_composite_probe.jl",
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
            events.extend([
                RETAINED_SUBGRID_EVENTS[0],
                *PER_COMPOSITE_EVENTS,
                RETAINED_SUBGRID_EVENTS[1],
            ])
        events.extend([
            f"STEP3_SEGMENT_{label}_CHECKPOINT_2_REACHED",
            f"STEP3_SEGMENT_{label}_RETURNED",
        ])
    return events


class MajoranaP9D4PerCompositeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_object(FIXTURE_PATH)
        cls.policy = load_object(POLICY_PATH)
        cls.d3_report = load_object(D3_REPORT_PATH)

    def _collector(self, events: list[str]) -> SimpleNamespace:
        return SimpleNamespace(
            overflow=False,
            partial=False,
            failure=False,
            lines=[
                D4.canonical_bytes({"event": event, "sequence": index}) + b"\n"
                for index, event in enumerate(events)
            ],
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
            "phase_trace_protocol_sha256": D4.canonical_sha256(events),
            "last_phase_event": names[-1] if names else None,
            "outer_timeout_triggered": outer_timeout,
            "host_failure_observed": host_failed,
            "resource_witness": None,
            "host_failure_has_no_mathematical_authority": True,
        }

    def test_direct_parent_and_exact_32_field_d3_projection_are_frozen(self) -> None:
        fixture = D4._validate_fixture(self.fixture)
        custody = fixture["d3_parent_custody"]
        self.assertEqual(len(custody), 32)
        self.assertEqual(fixture["fixture_id"], POLICY_ID)
        self.assertEqual(fixture["required_direct_parent_commit"], D3_RESULT_COMMIT)
        self.assertEqual(custody["result_commit_sha"], D3_RESULT_COMMIT)
        self.assertEqual(custody["preprobe_commit_sha"], D3_PREPROBE_COMMIT)
        self.assertEqual(custody["report_schema_version"], 1)
        self.assertEqual(custody["report_size_bytes"], D3_REPORT_SIZE)
        self.assertEqual(custody["report_sha256"], D3_REPORT_SHA256)
        report_bytes = D3_REPORT_PATH.read_bytes()
        self.assertEqual(len(report_bytes), D3_REPORT_SIZE)
        self.assertEqual(hashlib.sha256(report_bytes).hexdigest(), D3_REPORT_SHA256)

        report = self.d3_report
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
            "STEP3_SEGMENT_D_SUBGRID_ALPHA_REACHED",
        ]
        for event in required:
            self.assertIn(event, names)
        forbidden = [
            BETA_EVENT,
            "STEP3_SEGMENT_D_SUBGRID_GAMMA_REACHED",
            "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
            "STEP3_SEGMENT_D_RETURNED",
            "STEP3_SEGMENT_E_STARTED",
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D3_DIAGNOSTIC_COMPLETED",
        ]
        for event in forbidden:
            self.assertNotIn(event, names)
        self.assertIsNone(observation["resource_witness"])
        self.assertEqual(
            report["S0_admission"]["status"],
            custody["future_S0_admission_status"],
        )

        driver, d3_fixture, projection = D4._target_p9_d3_projection()
        self.assertEqual(projection, D4.D3_ALLOWED_PROJECTION)
        self.assertEqual(len(projection), 32)
        self.assertEqual(set(projection), set(custody))
        self.assertEqual(hashlib.sha256(driver).hexdigest(), D4.P9_DRIVER_SHA256)
        self.assertEqual(len(driver), D4.P9_DRIVER_SIZE)
        self.assertEqual(hashlib.sha256(d3_fixture).hexdigest(), D4.D3_FIXTURE_SHA256)
        self.assertEqual(len(d3_fixture), D4.D3_FIXTURE_SIZE)
        self.assertTrue(custody["segment_D_subgrid_ALPHA_marker_reached"])
        self.assertFalse(custody["segment_D_subgrid_BETA_marker_reached"])
        self.assertFalse(custody["segment_D_subgrid_GAMMA_marker_reached"])
        self.assertFalse(custody["D3_diagnostic_completed_marker_reached"])
        self.assertTrue(custody["diagnostic_terminal_branch_is_null"])

    def test_static_segment_d_per_composite_language_is_exact(self) -> None:
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
            mapping["segment_D_retained_anonymous_subgrid_completed_composite_ordinals"],
            RETAINED_SUBGRID_ORDINALS,
        )
        self.assertEqual(
            mapping["segment_D_retained_anonymous_subgrid_events"],
            RETAINED_SUBGRID_EVENTS,
        )
        self.assertEqual(
            mapping["segment_D_anonymous_per_composite_completed_composite_ordinals"],
            PER_COMPOSITE_ORDINALS,
        )
        self.assertEqual(
            mapping["segment_D_anonymous_per_composite_events"],
            PER_COMPOSITE_EVENTS,
        )
        self.assertEqual(
            mapping["segment_D_removed_redundant_subgrid_completed_composite_ordinal"],
            24,
        )
        self.assertEqual(mapping["segment_D_removed_redundant_subgrid_event"], BETA_EVENT)
        self.assertTrue(mapping["NU_at_ordinal_24_is_the_only_D4_marker_at_the_former_BETA_boundary"])
        self.assertTrue(mapping["BETA_is_absent_from_the_D4_wire_vocabulary_and_marker_emission"])

        internal = expected_internal_schedule()
        self.assertEqual(len(internal), 42)
        self.assertEqual(list(D4.SCHEDULE_EVENTS), internal)
        self.assertEqual(parameterized["internal_schedule_event_sequence"], internal)
        self.assertEqual(
            internal[12:22],
            [
                "STEP3_SEGMENT_D_STARTED",
                "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED",
                RETAINED_SUBGRID_EVENTS[0],
                *PER_COMPOSITE_EVENTS,
                RETAINED_SUBGRID_EVENTS[1],
                "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
                "STEP3_SEGMENT_D_RETURNED",
            ],
        )
        self.assertNotIn(BETA_EVENT, internal)
        self.assertNotIn(BETA_EVENT, protocol["allowed_events"])
        self.assertEqual(parameterized["full_schedule_internal_event_count"], 42)
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
            "D4_DIAGNOSTIC_COMPLETED",
        ]
        self.assertEqual(parameterized["partial_schedule_suffix"], suffix)
        self.assertEqual(parameterized["full_schedule_suffix"], suffix)
        self.assertEqual(parameterized["exact_partial_terminal_count"], 33)
        self.assertEqual(parameterized["exact_total_step3_engine_return_terminal_count"], 34)
        self.assertEqual(protocol["exact_total_legal_terminal_count"], 35)
        self.assertEqual(protocol["allowed_event_vocabulary_count"], 55)
        self.assertEqual(len(protocol["allowed_events"]), 55)
        self.assertEqual(len(set(protocol["allowed_events"])), 55)
        self.assertEqual(protocol["maximum_event_count"], 54)
        self.assertEqual(protocol["exact_maximum_legal_line_bytes_including_newline"], 81)
        self.assertEqual(protocol["exact_maximum_legal_canonical_trace_bytes"], 3028)

        execution = self.policy["D4_execution_contract"]
        self.assertEqual(execution["phase_event_vocabulary_count"], 55)
        self.assertEqual(execution["phase_event_protocol_maximum_event_count"], 54)
        self.assertEqual(execution["ordered_internal_schedule_event_count"], 42)
        self.assertEqual(execution["exact_legal_terminal_count"], 35)
        self.assertEqual(execution["allowed_early_schedule_prefix_event_counts"], ALLOWED_PARTIAL_COUNTS)
        self.assertEqual(execution["forbidden_early_schedule_prefix_event_counts"], FORBIDDEN_PARTIAL_COUNTS)

    def test_every_precommitted_terminal_language_is_accepted(self) -> None:
        self.assertEqual(len(D4.TERMINALS), 35)
        partial_branches = [
            branch for branch in D4.TERMINALS
            if branch.startswith("STEP3_ENGINE_RETURNED_AFTER_SCHEDULE_PREFIX_")
        ]
        self.assertEqual(len(partial_branches), 33)
        for branch, sequence in D4.TERMINALS.items():
            events, terminal = D4._validate_phase_trace(
                self._collector(sequence), self.fixture,
            )
            self.assertEqual(terminal, branch)
            self.assertEqual([row["event"] for row in events], sequence)
        full = D4.TERMINALS[
            "STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"
        ]
        self.assertEqual(len(full), 54)
        full_bytes = sum(
            len(D4.canonical_bytes({"event": event, "sequence": index}) + b"\n")
            for index, event in enumerate(full)
        )
        self.assertEqual(full_bytes, 3028)
        maximum_line = max(
            len(D4.canonical_bytes({"event": event, "sequence": index}) + b"\n")
            for sequence in D4.TERMINALS.values()
            for index, event in enumerate(sequence)
        )
        self.assertEqual(maximum_line, 81)

    def test_schedule_boundary_early_returns_are_rejected(self) -> None:
        prefix = D4._step3_schedule_common_prefix()
        suffix = [
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D4_DIAGNOSTIC_COMPLETED",
        ]
        for count in FORBIDDEN_PARTIAL_COUNTS:
            invalid = prefix + list(D4.SCHEDULE_EVENTS[:count]) + suffix
            with self.subTest(internal_schedule_event_count=count):
                with self.assertRaises(D4.ProbeError):
                    D4._validate_phase_trace(self._collector(invalid), self.fixture)

    def test_interruption_must_retain_a_legal_dfa_prefix(self) -> None:
        for branch, sequence in D4.TERMINALS.items():
            for count in range(len(sequence)):
                with self.subTest(branch=branch, prefix_event_count=count):
                    legal_prefix = sequence[:count]
                    events, terminal = D4._validate_phase_trace(
                        self._collector(legal_prefix), self.fixture,
                    )
                    self.assertIsNone(terminal)
                    self.assertEqual([row["event"] for row in events], legal_prefix)
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(
                self._collector(["D4_RUNNER_STARTED", "D4_STATIC_SETUP_COMPLETED"]),
                self.fixture,
            )

    def test_phase_wire_rejects_noncanonical_or_unbounded_records(self) -> None:
        collector = self._collector(["D4_RUNNER_STARTED"])
        collector.lines[0] = b'{"sequence": 0, "event": "D4_RUNNER_STARTED"}\n'
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(collector, self.fixture)

        collector = self._collector(["D4_RUNNER_STARTED"])
        collector.lines[0] = D4.canonical_bytes({
            "event": "D4_RUNNER_STARTED", "sequence": 1,
        }) + b"\n"
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(collector, self.fixture)

        collector = self._collector([
            "D4_RUNNER_STARTED",
            "D4_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        ])
        collector.lines[1] = D4.canonical_bytes({
            "event": "D4_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
            "sequence": True,
        }) + b"\n"
        with self.assertRaises(D4.ProbeError):
            D4._validate_phase_trace(collector, self.fixture)

        for flag in ("overflow", "partial", "failure"):
            collector = self._collector(["D4_RUNNER_STARTED"])
            setattr(collector, flag, True)
            with self.subTest(transport_flag=flag):
                with self.assertRaises(D4.ProbeError):
                    D4._validate_phase_trace(collector, self.fixture)

    def test_static_clone_is_exactly_forward_and_reverse_derived(self) -> None:
        relation = D4._validate_static_clone(self.fixture)
        self.assertTrue(relation["forward_byte_construction_matches"])
        self.assertTrue(relation["reverse_deletion_matches_frozen_P9"])
        self.assertEqual(relation["exact_marker_insertion_block_count"], 12)
        self.assertEqual(relation["outer_phase_marker_block_count"], 8)
        self.assertEqual(relation["schedule_marker_block_count"], 4)
        self.assertTrue(relation["marker_blocks_contain_no_forbidden_live_state_tokens"])
        self.assertTrue(
            relation[
                "D1_D2_and_D3_artifacts_are_not_included_opened_or_staged_by_the_D4_driver"
            ]
        )

    def test_per_composite_markers_are_anonymous_and_beta_is_disabled(self) -> None:
        clone_path = BASE / D4.CLONE_DRIVER
        source = clone_path.read_text(encoding="utf-8")
        for event in [*RETAINED_SUBGRID_EVENTS, *PER_COMPOSITE_EVENTS]:
            self.assertIn(event, source)
        self.assertNotIn(BETA_EVENT, source)
        for ordinal in PER_COMPOSITE_ORDINALS:
            self.assertNotIn(f"COMPOSITE_{ordinal}_REACHED", source)

        wrapper = source[
            source.index("function p9_execute_bit_order_step("):
            source.index("function p9_execute_prefix(")
        ]
        self.assertLess(
            wrapper.index("execution = execute_p9_step3_bitorder("),
            wrapper.index('p9_d4_emit("STEP3_SCHEDULE_RETURNED")'),
        )
        self.assertLess(
            wrapper.index('p9_d4_emit("STEP3_SCHEDULE_RETURNED")'),
            wrapper.index("final_cap = execution.cap_event"),
        )
        schedule = source[
            source.index("function execute_p9_step3_bitorder("):
            source.index("function main_p9_d0()")
        ]
        self.assertLess(
            schedule.index("cap_event = nothing"),
            schedule.index('p9_d4_emit("STEP3_STATE_INITIALIZED")'),
        )
        self.assertLess(
            schedule.index('p9_d4_emit("STEP3_SCHEDULE_ENTERED")'),
            schedule.index("try\n        for stage in stages"),
        )

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
        self.assertTrue(custody["anonymous_per_composite_event_names_export_no_completed_composite_ordinal"])
        report_contract = self.policy["phase_report_contract"]
        self.assertTrue(
            report_contract[
                "no_D0_D1_D2_D3_or_D4_timing_RSS_stderr_stdout_returncode_or_resource_measurement_is_persisted"
            ]
        )

        full_branch = "STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"
        full = D4.TERMINALS[full_branch]
        completed = self._observation(
            full,
            status="COMPLETED_PHASE_DIAGNOSTIC",
            branch=full_branch,
            trace_status="COMPLETE_TERMINAL_SEQUENCE",
            host_failed=False,
        )
        D4._validate_observation(completed, self.fixture)
        forbidden_fields = {
            "outer_receive_elapsed_ns", "outer_monotonic_elapsed_ns",
            "process_returncode", "stderr_bytes", "stderr_sha256",
            "stdout_bytes", "stdout_sha256", "time_diagnostics",
            "maximum_resident_set_size", "raw_phase_channel_bytes",
            "phase_channel_sha256",
        }
        self.assertTrue(forbidden_fields.isdisjoint(completed))
        contaminated = dict(completed)
        contaminated["process_returncode"] = 0
        with self.assertRaises(D4.ProbeError):
            D4._validate_observation(contaminated, self.fixture)
        noninteger_count = dict(completed)
        noninteger_count["phase_event_count"] = float(len(full))
        with self.assertRaises(D4.ProbeError):
            D4._validate_observation(noninteger_count, self.fixture)

        interrupted = self._observation(
            full[:25],
            status="INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            branch=None,
            trace_status="LEGAL_PREFIX_INTERRUPTED",
            host_failed=True,
            outer_timeout=True,
        )
        D4._validate_observation(interrupted, self.fixture)

    def test_child_stdout_and_stderr_collectors_are_memory_bounded(self) -> None:
        def collect(
            payload: bytes, *, maximum: int, reject_any: bool,
        ) -> tuple[object, threading.Event]:
            read_fd, write_fd = os.pipe()
            stream = os.fdopen(read_fd, "rb", buffering=0)
            violation = threading.Event()
            collector = D4._BoundedStreamCollector(
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

    def test_parent_projection_does_not_read_suppressed_d3_measurements(self) -> None:
        source = inspect.getsource(D4._target_p9_d3_projection)
        for forbidden in (
            "outer_timeout_triggered", "host_failure_observed",
            "phase_event_count", "phase_trace_protocol_sha256",
            "returncode", "stdout", "stderr", "elapsed",
            "maximum_resident", "time_diagnostics",
        ):
            self.assertNotIn(forbidden, source)

    def test_no_runtime_source_or_ast_transform_route_exists(self) -> None:
        source = D4_MODULE_PATH.read_text(encoding="utf-8")
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
        self.assertNotIn("ast.parse(", inspect.getsource(D4._build_expected_clone))
        self.assertTrue(all("p9_d3" not in path.lower() for path in D4.STAGED_PATHS))
        self.assertNotIn(D4.D3_REPORT, D4.STAGED_PATHS)

    def test_b0_and_b1_path_gates_are_explicit(self) -> None:
        lifecycle = self.policy["preprobe_and_result_lifecycle"]
        self.assertEqual(len(B0_PATHS), 5)
        self.assertNotIn(B1_REPORT_PATH, B0_PATHS)
        self.assertTrue(lifecycle["B0_has_exactly_five_new_paths_and_is_a_direct_child_of_D3_B1"])
        self.assertTrue(lifecycle["B0_cannot_contain_a_D4_report_or_execution_claim"])
        self.assertTrue(lifecycle["B1_has_exactly_one_new_path_the_canonical_D4_report_and_is_a_direct_child_of_B0"])
        self.assertTrue(lifecycle["B1_report_Git_blob_must_equal_canonical_report_bytes_and_the_clean_worktree_file"])
        self.assertTrue(lifecycle["B1_verification_must_reject_any_extra_changed_path_or_dirty_worktree"])
        self.assertIn('"--untracked-files=all"', inspect.getsource(D4._status_paths))
        self.assertIn("_fsync_directory(BASE)", inspect.getsource(D4._acquire_claim))

    def test_staging_and_source_pin_manifest_are_explicit_without_b0_only_validation(self) -> None:
        custody = self.policy["staged_source_custody"]
        self.assertEqual(self.policy["policy_id"], POLICY_ID)
        self.assertEqual(self.policy["required_direct_parent_commit"], D3_RESULT_COMMIT)
        self.assertEqual(self.policy["phase_report_contract"]["report_type"], REPORT_TYPE)
        self.assertEqual(custody["staged_path_order"], STAGED_PATHS)
        self.assertEqual(custody["exact_staged_path_count"], 14)
        self.assertEqual(list(D4.STAGED_PATHS), STAGED_PATHS)

        rows = self.policy["source_files"]
        self.assertEqual(self.policy["exact_source_file_count"], 18)
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row["relative_path"] for row in rows}), 18)
        self.assertEqual([row["relative_path"] for row in rows], list(D4.SOURCE_PATHS))
        self.assertEqual(self.policy["source_pins_status"], "FROZEN_EXACT")
        for row in rows:
            relative = row["relative_path"]
            body = (BASE / relative).read_bytes()
            self.assertEqual(row["size_bytes"], len(body), relative)
            self.assertEqual(row["sha256"], hashlib.sha256(body).hexdigest(), relative)
        # Deliberately do not call validate_policy(require_report_absent=True) here:
        # that B0-only assertion conflicts with a legitimate committed B1 report.

    def test_post_d4_creates_review_targets_but_never_authorizes_d5(self) -> None:
        fixture_route = self.fixture["post_D4_route_contract"]
        policy_route = self.policy["phase_report_contract"]
        self.assertTrue(fixture_route["D4_result_may_create_only_a_nonexecuting_governance_review_target"])
        self.assertTrue(fixture_route["review_target_has_no_execution_candidate_selection_resource_or_scientific_authority"])
        self.assertTrue(fixture_route["per_composite_boundary_resolution_is_the_finest_currently_authorized_static_resolution"])
        self.assertTrue(fixture_route["constituent_or_hot_loop_refinement_is_forbidden"])
        self.assertTrue(fixture_route["no_D4_outcome_automatically_authorizes_D5"])
        self.assertTrue(fixture_route["any_future_route_requires_a_new_independent_governance_decision"])
        self.assertEqual(policy_route["review_target_map"], fixture_route["review_target_map"])
        self.assertTrue(policy_route["no_D4_outcome_automatically_authorizes_D5"])
        self.assertNotIn("target_partition_route_map", policy_route)
        self.assertNotIn("only_allowed_post_D4_refinement_route", policy_route)

    def test_d3_projection_compatibility_alias_is_published(self) -> None:
        self.assertIs(D4._target_p9_d3_projection, D4._target_d3_b1_projection)

    def test_policy_and_receipt_validation_are_b0_b1_aware(self) -> None:
        head = D4._git_text("rev-parse", "HEAD").strip()
        committed_report = D4._git_blob_optional(
            head, D4.ROOT + D4.REPORT_NAME,
        )
        report_path = BASE / D4.REPORT_NAME
        if committed_report is not None:
            D4.validate_policy(self.policy, require_report_absent=False)
            report = D4.verify_report(report_path)
            self.assertEqual(report["report_type"], REPORT_TYPE)
            self.assertEqual(D4.RESULT_CHANGED_PATHS, (D4.ROOT + D4.REPORT_NAME,))
        elif head != D3_RESULT_COMMIT:
            D4.validate_policy(self.policy, require_report_absent=True)
            receipt = D4.verify_preprobe()
            self.assertEqual(
                receipt["status"],
                "VERIFIED_P9_D4_SEGMENT_D_PER_COMPOSITE_PREPROBE",
            )
        else:
            self.skipTest("P9-D4 B0 is not yet committed")


if __name__ == "__main__":
    unittest.main()
