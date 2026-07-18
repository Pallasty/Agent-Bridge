#!/usr/bin/env python3
"""Contract tests for the P9-D2 phase-only schedule diagnostic."""

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
FIXTURE_PATH = BASE / "majorana_certificate_p9_d2_schedule_probe_fixture.json"
POLICY_PATH = BASE / "majorana_certificate_p9_d2_schedule_probe_policy.json"
D1_REPORT_PATH = BASE / "majorana_certificate_p9_d1_phase_probe_report.json"
D2_MODULE_PATH = BASE / "majorana_certificate_p9_d2_schedule_probe.py"

SPEC = importlib.util.spec_from_file_location("majorana_p9_d2", D2_MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P9-D2 module")
D2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D2)

D1_RESULT_COMMIT = "47a34a4a0b39c616419c542a4c1b151f4aa9f8cc"
D1_REPORT_SHA256 = "64cfad2b3de05620954b66df5ade380944e27d33d178ddc82eddbc496ad64faa"
D1_REPORT_SIZE = 7121

B0_PATHS = {
    "docs/research/fermion-frontier/majorana_certificate_p9_d2_schedule_probe.py",
    "docs/research/fermion-frontier/majorana_certificate_p9_d2_schedule_probe/"
    "majorana_p9_bit_order_step3_schedule_probe.jl",
    "docs/research/fermion-frontier/majorana_certificate_p9_d2_schedule_probe_fixture.json",
    "docs/research/fermion-frontier/majorana_certificate_p9_d2_schedule_probe_policy.json",
    "docs/research/fermion-frontier/test_majorana_certificate_p9_d2_schedule_probe.py",
}
B1_REPORT_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p9_d2_schedule_probe_report.json"
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
    "majorana_certificate_p9_d2_schedule_probe_fixture.json",
    "majorana_certificate_p9_d2_schedule_probe/"
    "majorana_p9_bit_order_step3_schedule_probe.jl",
]


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path.name} must contain a JSON object")
    return value


class MajoranaP9D2ScheduleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_object(FIXTURE_PATH)
        cls.policy = load_object(POLICY_PATH)
        cls.d1_report = load_object(D1_REPORT_PATH)

    def _collector(self, events: list[str]) -> SimpleNamespace:
        lines = [
            D2.canonical_bytes({"event": event, "sequence": index}) + b"\n"
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
            "phase_trace_protocol_sha256": D2.canonical_sha256(events),
            "last_phase_event": names[-1] if names else None,
            "outer_timeout_triggered": outer_timeout,
            "host_failure_observed": host_failed,
            "resource_witness": None,
            "host_failure_has_no_mathematical_authority": True,
        }

    def test_direct_parent_and_minimal_d1_projection_are_frozen(self) -> None:
        fixture = D2._validate_fixture(self.fixture)
        custody = fixture["d1_parent_custody"]
        self.assertEqual(fixture["required_direct_parent_commit"], D1_RESULT_COMMIT)
        self.assertEqual(custody["result_commit_sha"], D1_RESULT_COMMIT)
        self.assertEqual(custody["report_size_bytes"], D1_REPORT_SIZE)
        self.assertEqual(custody["report_sha256"], D1_REPORT_SHA256)
        self.assertEqual(
            hashlib.sha256(D1_REPORT_PATH.read_bytes()).hexdigest(), D1_REPORT_SHA256,
        )
        self.assertEqual(len(D1_REPORT_PATH.read_bytes()), D1_REPORT_SIZE)

        report = self.d1_report
        observation = report["observation"]
        self.assertEqual(report["scientific_authority"], "NONE")
        self.assertFalse(report["certificate_eligible"])
        self.assertFalse(report["result_contract_eligible"])
        self.assertEqual(observation["status"], custody["terminal_status"])
        self.assertEqual(observation["phase_trace_status"], custody["phase_trace_status"])
        names = [row["event"] for row in observation["phase_events"]]
        self.assertIn("P6_PREFIX_RESOURCE_CONFORMANCE_PASSED", names)
        self.assertIn("STEP3_ENGINE_STARTED", names)
        self.assertNotIn("STEP3_ENGINE_RETURNED", names)
        self.assertIsNone(observation["resource_witness"])
        self.assertEqual(
            report["S0_admission"]["status"],
            custody["future_S0_admission_status"],
        )
        driver, d1_fixture, projection = D2._target_p9_d1_projection()
        self.assertEqual(projection, D2.D1_ALLOWED_PROJECTION)
        self.assertEqual(hashlib.sha256(driver).hexdigest(), D2.P9_DRIVER_SHA256)
        self.assertEqual(len(driver), D2.P9_DRIVER_SIZE)
        self.assertEqual(hashlib.sha256(d1_fixture).hexdigest(), D2.D1_FIXTURE_SHA256)
        self.assertEqual(len(d1_fixture), D2.D1_FIXTURE_SIZE)
        self.assertEqual(set(projection), set(D2.D1_ALLOWED_PROJECTION))

    def test_static_nine_stage_schedule_language_is_complete(self) -> None:
        mapping = self.fixture["step3_schedule_marker_map"]
        protocol = self.fixture["phase_event_protocol"]
        labels = list("ABCDEFGHI")
        self.assertEqual(mapping["stage_order"], labels)
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
        expected = [
            f"STEP3_SEGMENT_{label}_{suffix}"
            for label in labels
            for suffix in (
                "STARTED", "CHECKPOINT_1_REACHED", "CHECKPOINT_2_REACHED", "RETURNED",
            )
        ]
        parameterized = protocol["parameterized_step3_engine_return_terminal"]
        self.assertEqual(parameterized["internal_schedule_event_sequence"], expected)
        self.assertEqual(parameterized["full_schedule_internal_event_count"], 36)
        self.assertEqual(
            parameterized["fixed_prefix_through_step3_schedule_entered"][-3:],
            ["STEP3_ENGINE_STARTED", "STEP3_STATE_INITIALIZED", "STEP3_SCHEDULE_ENTERED"],
        )
        early_counts = [
            1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15,
            17, 18, 19, 21, 22, 23, 25, 26, 27, 29, 30, 31,
            33, 34, 35,
        ]
        self.assertEqual(parameterized["allowed_partial_internal_prefix_event_counts"], early_counts)
        self.assertEqual(
            parameterized["forbidden_partial_internal_prefix_event_counts"],
            [0, 4, 8, 12, 16, 20, 24, 28, 32],
        )
        self.assertEqual(
            parameterized["partial_schedule_suffix"],
            ["STEP3_SCHEDULE_RETURNED", "STEP3_ENGINE_RETURNED", "D2_DIAGNOSTIC_COMPLETED"],
        )
        self.assertEqual(
            parameterized["full_schedule_suffix"],
            ["STEP3_SCHEDULE_RETURNED", "STEP3_ENGINE_RETURNED", "D2_DIAGNOSTIC_COMPLETED"],
        )
        self.assertEqual(protocol["maximum_event_count"], 48)
        for event in (
            "STEP3_STATE_INITIALIZED", "STEP3_SCHEDULE_ENTERED", "STEP3_SCHEDULE_RETURNED",
        ):
            self.assertIn(event, protocol["allowed_events"])
        self.assertEqual(
            self.policy["D2_execution_contract"]["phase_event_protocol_maximum_event_count"],
            48,
        )
        self.assertEqual(
            self.policy["D2_execution_contract"]["allowed_early_schedule_prefix_event_counts"],
            early_counts,
        )
        self.assertEqual(
            self.policy["D2_execution_contract"]["early_and_full_schedule_return_suffix"],
            ["STEP3_SCHEDULE_RETURNED", "STEP3_ENGINE_RETURNED", "D2_DIAGNOSTIC_COMPLETED"],
        )

    def test_every_precommitted_terminal_language_is_accepted(self) -> None:
        self.assertEqual(len(D2.TERMINALS), 29)
        self.assertEqual(
            len([
                branch for branch in D2.TERMINALS
                if branch.startswith("STEP3_ENGINE_RETURNED_AFTER_SCHEDULE_PREFIX_")
            ]),
            27,
        )
        for branch, sequence in D2.TERMINALS.items():
            events, terminal = D2._validate_phase_trace(
                self._collector(sequence), self.fixture,
            )
            self.assertEqual(terminal, branch)
            self.assertEqual([row["event"] for row in events], sequence)
        self.assertEqual(
            len(D2.TERMINALS["STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"]),
            48,
        )

    def test_schedule_boundary_early_returns_are_rejected(self) -> None:
        prefix = D2._step3_schedule_common_prefix()
        suffix = [
            "STEP3_SCHEDULE_RETURNED",
            "STEP3_ENGINE_RETURNED",
            "D2_DIAGNOSTIC_COMPLETED",
        ]
        for count in [0, *range(4, len(D2.SCHEDULE_EVENTS), 4)]:
            invalid = prefix + list(D2.SCHEDULE_EVENTS[:count]) + suffix
            with self.subTest(internal_schedule_event_count=count):
                with self.assertRaises(D2.ProbeError):
                    D2._validate_phase_trace(self._collector(invalid), self.fixture)

    def test_interruption_must_retain_a_legal_dfa_prefix(self) -> None:
        for branch, sequence in D2.TERMINALS.items():
            for count in range(len(sequence)):
                with self.subTest(branch=branch, prefix_event_count=count):
                    legal_prefix = sequence[:count]
                    events, terminal = D2._validate_phase_trace(
                        self._collector(legal_prefix), self.fixture,
                    )
                    self.assertIsNone(terminal)
                    self.assertEqual(
                        [row["event"] for row in events], legal_prefix,
                    )
        with self.assertRaises(D2.ProbeError):
            D2._validate_phase_trace(
                self._collector([
                    "D2_RUNNER_STARTED",
                    "D2_STATIC_SETUP_COMPLETED",
                ]),
                self.fixture,
            )

    def test_phase_wire_rejects_noncanonical_or_unbounded_records(self) -> None:
        collector = self._collector(["D2_RUNNER_STARTED"])
        collector.lines[0] = b'{"sequence": 0, "event": "D2_RUNNER_STARTED"}\n'
        with self.assertRaises(D2.ProbeError):
            D2._validate_phase_trace(collector, self.fixture)

        collector = self._collector(["D2_RUNNER_STARTED"])
        collector.lines[0] = D2.canonical_bytes({
            "event": "D2_RUNNER_STARTED", "sequence": 1,
        }) + b"\n"
        with self.assertRaises(D2.ProbeError):
            D2._validate_phase_trace(collector, self.fixture)

        collector = self._collector([
            "D2_RUNNER_STARTED",
            "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        ])
        collector.lines[1] = D2.canonical_bytes({
            "event": "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
            "sequence": True,
        }) + b"\n"
        with self.assertRaises(D2.ProbeError):
            D2._validate_phase_trace(collector, self.fixture)

        for flag in ("overflow", "partial", "failure"):
            collector = self._collector(["D2_RUNNER_STARTED"])
            setattr(collector, flag, True)
            with self.subTest(transport_flag=flag):
                with self.assertRaises(D2.ProbeError):
                    D2._validate_phase_trace(collector, self.fixture)

    def test_static_clone_is_exactly_forward_and_reverse_derived(self) -> None:
        relation = D2._validate_static_clone(self.fixture)
        self.assertTrue(relation["forward_byte_construction_matches"])
        self.assertTrue(relation["reverse_deletion_matches_frozen_P9"])
        self.assertEqual(relation["exact_marker_insertion_block_count"], 12)
        self.assertEqual(relation["outer_phase_marker_block_count"], 8)
        self.assertEqual(relation["schedule_marker_block_count"], 4)
        self.assertTrue(relation["marker_blocks_contain_no_forbidden_live_state_tokens"])
        self.assertTrue(
            relation["D1_artifacts_are_not_included_opened_or_staged_by_the_D2_driver"]
        )

    def test_schedule_and_engine_return_markers_have_distinct_control_points(self) -> None:
        clone_path = BASE / D2.CLONE_DRIVER
        source = clone_path.read_text(encoding="utf-8")
        wrapper = source[
            source.index("function p9_execute_bit_order_step("):
            source.index("function p9_execute_prefix(")
        ]
        self.assertLess(
            wrapper.index("execution = execute_p9_step3_bitorder("),
            wrapper.index('p9_d2_emit("STEP3_SCHEDULE_RETURNED")'),
        )
        self.assertLess(
            wrapper.index('p9_d2_emit("STEP3_SCHEDULE_RETURNED")'),
            wrapper.index("final_cap = execution.cap_event"),
        )

        schedule = source[
            source.index("function execute_p9_step3_bitorder("):
            source.index("function main_p9_d0()")
        ]
        self.assertLess(
            schedule.index("cap_event = nothing"),
            schedule.index('p9_d2_emit("STEP3_STATE_INITIALIZED")'),
        )
        self.assertLess(
            schedule.index('p9_d2_emit("STEP3_SCHEDULE_ENTERED")'),
            schedule.index("try\n        for stage in stages"),
        )

        main = source[source.index("function main_p9_d0()") :]
        self.assertLess(
            main.index("step3_run = p9_execute_bit_order_step("),
            main.index('p9_d2_emit("STEP3_ENGINE_RETURNED")'),
        )
        self.assertNotIn('p9_d2_emit("STEP3_SCHEDULE_RETURNED")', main)

    def test_phase_contract_excludes_measurement_and_scientific_data(self) -> None:
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8").lower()
        for forbidden in (
            "outer_receive_elapsed", "outer_monotonic_elapsed", "maximum_resident",
            "process_returncode", "stderr_sha256", "stdout_sha256",
            "time_diagnostics", "phase_channel_sha256",
        ):
            self.assertNotIn(forbidden, fixture_text)
        self.assertTrue(
            self.fixture["phase_channel_custody"]
            ["child_emits_no_timestamp_term_count_index_mask_coefficient_tick_budget_cap_resource_or_free_text"]
        )
        self.assertTrue(
            self.fixture["step3_schedule_marker_map"]
            ["constituent_boundary_selection_callback_and_hot_loop_markers_are_forbidden"]
        )
        self.assertTrue(
            self.policy["phase_report_contract"]
            ["no_D0_D1_or_D2_timing_RSS_stderr_stdout_returncode_or_resource_measurement_is_persisted"]
        )
        self.assertTrue(
            self.policy["phase_report_contract"]
            ["no_raw_phase_channel_bytes_hash_byte_count_or_receive_times_are_persisted"]
        )
        self.assertTrue(
            self.policy["D2_execution_contract"]
            ["stdout_and_stderr_are_drained_without_unbounded_outer_buffering_and_limit_violation_stops_the_scope"]
        )

        full_branch = "STEP3_ENGINE_RETURNED_AFTER_ALL_FIXED_SCHEDULE_SEGMENTS"
        full = D2.TERMINALS[full_branch]
        completed = self._observation(
            full,
            status="COMPLETED_PHASE_DIAGNOSTIC",
            branch=full_branch,
            trace_status="COMPLETE_TERMINAL_SEQUENCE",
            host_failed=False,
        )
        D2._validate_observation(completed, self.fixture)
        forbidden = {
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
        self.assertTrue(forbidden.isdisjoint(completed))
        contaminated = dict(completed)
        contaminated["process_returncode"] = 0
        with self.assertRaises(D2.ProbeError):
            D2._validate_observation(contaminated, self.fixture)
        noninteger_count = dict(completed)
        noninteger_count["phase_event_count"] = float(len(full))
        with self.assertRaises(D2.ProbeError):
            D2._validate_observation(noninteger_count, self.fixture)

        interrupted_names = D2.TERMINALS[full_branch][:24]
        interrupted = self._observation(
            interrupted_names,
            status="INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            branch=None,
            trace_status="LEGAL_PREFIX_INTERRUPTED",
            host_failed=True,
            outer_timeout=True,
        )
        D2._validate_observation(interrupted, self.fixture)

        exact_with_host_failure = self._observation(
            full,
            status="INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            branch=full_branch,
            trace_status="COMPLETE_TERMINAL_SEQUENCE",
            host_failed=True,
        )
        D2._validate_observation(exact_with_host_failure, self.fixture)
        contradictory = dict(exact_with_host_failure)
        contradictory["phase_trace_status"] = "LEGAL_PREFIX_INTERRUPTED"
        with self.assertRaises(D2.ProbeError):
            D2._validate_observation(contradictory, self.fixture)

    def test_child_stdout_and_stderr_collectors_are_memory_bounded(self) -> None:
        def collect(
            payload: bytes, *, maximum: int, reject_any: bool,
        ) -> tuple[object, threading.Event]:
            read_fd, write_fd = os.pipe()
            stream = os.fdopen(read_fd, "rb", buffering=0)
            violation = threading.Event()
            collector = D2._BoundedStreamCollector(
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

    def test_parent_projection_does_not_read_suppressed_d1_measurements(self) -> None:
        source = inspect.getsource(D2._target_p9_d1_projection)
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

    def test_no_runtime_source_or_ast_transform_route_exists(self) -> None:
        source = D2_MODULE_PATH.read_text(encoding="utf-8")
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
        self.assertNotIn("ast.parse(", inspect.getsource(D2._build_expected_clone))
        self.assertTrue(all("p9_d1" not in path.lower() for path in D2.STAGED_PATHS))
        self.assertNotIn(D2.D1_REPORT, D2.STAGED_PATHS)

    def test_b0_and_b1_path_gates_are_explicit(self) -> None:
        lifecycle = self.policy["preprobe_and_result_lifecycle"]
        self.assertEqual(len(B0_PATHS), 5)
        self.assertNotIn(B1_REPORT_PATH, B0_PATHS)
        self.assertTrue(lifecycle["B0_has_exactly_five_new_paths_and_is_a_direct_child_of_D1_B1"])
        self.assertTrue(lifecycle["B0_cannot_contain_a_D2_report_or_execution_claim"])
        self.assertTrue(lifecycle["B1_has_exactly_one_new_path_the_canonical_D2_report_and_is_a_direct_child_of_B0"])
        self.assertTrue(lifecycle["B1_report_Git_blob_must_equal_canonical_report_bytes_and_the_clean_worktree_file"])
        self.assertTrue(lifecycle["B1_verification_must_reject_any_extra_changed_path_or_dirty_worktree"])
        self.assertTrue(
            lifecycle[
                "claimed_B0_HEAD_and_worktree_are_reverified_before_report_write_and_claim_release"
            ]
        )
        self.assertIn(
            '"--untracked-files=all"', inspect.getsource(D2._status_paths),
        )
        self.assertIn(
            "_fsync_directory(BASE)", inspect.getsource(D2._acquire_claim),
        )

    def test_staging_and_source_pin_manifest_are_explicit(self) -> None:
        custody = self.policy["staged_source_custody"]
        self.assertEqual(custody["staged_path_order"], STAGED_PATHS)
        self.assertEqual(custody["exact_staged_path_count"], 14)
        self.assertTrue(custody["D1_report_policy_fixture_Python_and_clone_are_outer_checker_only_and_not_staged"])
        self.assertTrue(custody["original_P9_driver_is_outer_checker_only_and_not_staged"])

        rows = self.policy["source_files"]
        self.assertEqual(self.policy["exact_source_file_count"], 18)
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row["relative_path"] for row in rows}), 18)
        self.assertEqual(self.policy["source_pins_status"], "FROZEN_EXACT")
        for row in rows:
            relative = row["relative_path"]
            body = (BASE / relative).read_bytes()
            self.assertEqual(row["size_bytes"], len(body), relative)
            self.assertEqual(
                row["sha256"], hashlib.sha256(body).hexdigest(), relative,
            )

    def test_d1_projection_compatibility_alias_is_published(self) -> None:
        self.assertIs(D2._target_p9_d1_projection, D2._target_d1_b1_projection)

    def test_frozen_preprobe_or_report_is_verifiable_after_commit(self) -> None:
        report_path = BASE / D2.REPORT_NAME
        head = D2._git_text("rev-parse", "HEAD").strip()
        if report_path.exists():
            report = D2.verify_report(report_path)
            self.assertEqual(report["report_type"], D2.REPORT_TYPE)
            self.assertEqual(D2.RESULT_CHANGED_PATHS, (D2.ROOT + D2.REPORT_NAME,))
        elif head != D2.D1_RESULT_COMMIT:
            receipt = D2.verify_preprobe()
            self.assertEqual(
                receipt["status"], "VERIFIED_P9_D2_STATIC_SCHEDULE_PREPROBE",
            )
        else:
            self.skipTest("P9-D2 B0 is not yet committed")


if __name__ == "__main__":
    unittest.main()
