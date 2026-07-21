#!/usr/bin/env python3
"""Preprobe tests for the non-authoritative Majorana P7 D3 diagnostic."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p7_d3_e_subgrid_probe.py"
SPEC = importlib.util.spec_from_file_location("majorana_p7_d3", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P7 D3 E-subgrid-probe module")
D3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D3)


def collector_for(
    names: list[str], *, eof: bool = True, read_failure: bool = False,
) -> D3._PhaseCollector:
    protocol = D3.load_json(BASE / D3.FIXTURE_NAME)["phase_event_protocol"]
    collector = D3._PhaseCollector(
        -1, 0,
        max_line_bytes=protocol["maximum_line_bytes_including_newline"],
        max_total_bytes=protocol["maximum_total_channel_bytes"],
        max_events=protocol["maximum_event_count"],
    )
    raw = b""
    for sequence, event in enumerate(names):
        line = D3.canonical_bytes({"event": event, "sequence": sequence}) + b"\n"
        raw += line
        collector.lines.append((line, 100 + sequence))
    collector.total_bytes = len(raw)
    collector.digest.update(raw)
    collector.eof = eof
    collector.read_failure = read_failure
    return collector


def complete_time_stderr() -> bytes:
    return b"\n".join((
        b"User time (seconds): 1.00",
        b"System time (seconds): 0.10",
        b"Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.10",
        b"Maximum resident set size (kbytes): 1234",
        b"Minor (reclaiming a frame) page faults: 3",
        b"Major (requiring I/O) page faults: 0",
        b"",
    ))


def stream_fields(stdout: bytes = b"", stderr: bytes = b"") -> dict[str, object]:
    return {
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stderr_for_time": stderr,
    }


class P7D3ESubgridPreprobeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = D3.load_json(BASE / D3.FIXTURE_NAME)
        cls.policy = D3.load_json(BASE / D3.POLICY_NAME)

    def test_fixture_protocol_and_static_marker_map_are_exact(self) -> None:
        fixture = D3._validate_fixture(self.fixture)
        self.assertEqual(
            D3.canonical_sha256(fixture), D3.FIXTURE_CANONICAL_SHA256,
        )
        protocol = fixture["phase_event_protocol"]
        self.assertEqual(
            D3.canonical_sha256(protocol), D3.PHASE_PROTOCOL_CANONICAL_SHA256,
        )
        self.assertEqual(len(protocol["allowed_events"]), 65)
        self.assertEqual(len(protocol["step3_internal_event_sequence"]), 40)
        self.assertEqual(len(protocol["full_success_sequence"]), 61)
        self.assertEqual(protocol["maximum_event_count"], 61)
        self.assertEqual(protocol["maximum_successful_trace_event_count"], 61)
        self.assertEqual(protocol["maximum_total_channel_bytes"], 8192)
        grammar = protocol["parameterized_step3_deterministic_cap_terminal"]
        self.assertEqual(
            grammar["allowed_internal_prefix_event_counts"],
            list(D3.STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS),
        )
        self.assertEqual(
            grammar[
                "forbidden_segment_returned_prefix_event_counts_without_next_segment_started"
            ],
            list(D3.UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS),
        )
        self.assertEqual(
            grammar["exact_reachable_internal_prefix_event_count_cardinality"],
            32,
        )
        self.assertEqual(
            D3.UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS,
            (4, 8, 12, 16, 24, 28, 32, 36),
        )
        self.assertIn(40, D3.STEP3_CAP_INTERNAL_PREFIX_EVENT_COUNTS)
        marker = fixture["step3_schedule_marker_map"]
        segments = marker["segments"]
        self.assertEqual(marker["segment_order"], list("ABCDEFGHI"))
        self.assertEqual([row["frozen_group"] for row in segments], [
            "H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1",
        ])
        counts = [row["frozen_composite_count"] for row in segments]
        self.assertEqual(counts, [64, 48, 64, 48, 64, 48, 64, 48, 64])
        self.assertEqual(sum(counts), 512)
        self.assertEqual(
            [row["checkpoint_1_completed_composites"] for row in segments],
            [22, 16, 22, 16, 22, 16, 22, 16, 22],
        )
        self.assertEqual(
            [row["checkpoint_2_completed_composites"] for row in segments],
            [43, 32, 43, 32, 43, 32, 43, 32, 43],
        )
        segment_e = segments[4]
        self.assertEqual(
            segment_e["D3_subgrid_completed_composite_ordinals"],
            list(D3.E_SUBGRID_COMPLETED_COMPOSITES),
        )
        self.assertEqual(marker["E_subgrid_marker_map"], [
            {
                "completed_composite_ordinal": ordinal,
                "event": f"STEP3_SEGMENT_E_SUBGRID_{ordinal}_REACHED",
            }
            for ordinal in D3.E_SUBGRID_COMPLETED_COMPOSITES
        ])

    def test_policy_semantics_sources_and_staging_are_frozen(self) -> None:
        policy = D3.validate_policy(self.policy, require_report_absent=True)
        semantic = {
            key: value for key, value in policy.items() if key != "source_files"
        }
        self.assertEqual(
            D3.canonical_sha256(semantic), D3.POLICY_SEMANTIC_SHA256,
        )
        self.assertEqual(policy["source_file_pins_status"], "FROZEN_EXACT")
        self.assertEqual(policy["exact_source_file_count"], 25)
        pins = D3._source_pins(policy)
        self.assertEqual(set(pins), set(D3.SOURCE_PATHS))
        self.assertEqual(len(pins), 25)
        self.assertEqual(len(D3.STAGED_PATHS), 15)
        self.assertEqual(tuple(D3.STAGED_PATHS[:13]), tuple(D3.D0.STAGED_PATHS))
        self.assertEqual(D3.STAGED_PATHS[-2:], (D3.FIXTURE_NAME, D3.PROBE_DRIVER))
        self.assertNotIn(D3.D2_REPORT_NAME, D3.STAGED_PATHS)
        self.assertNotIn(D3.D2_REPORT_NAME, D3.SOURCE_PATHS)
        self.assertEqual(
            policy["staged_source_custody"]["staged_path_order"],
            list(D3.STAGED_PATHS),
        )
        self.assertEqual(
            policy["static_schedule_marker_policy"][
                "segment_E_fixed_subgrid_completed_composite_ordinals"
            ],
            list(D3.E_SUBGRID_COMPLETED_COMPOSITES),
        )

    def test_D2_parent_firewall_uses_only_frozen_coarse_facts(self) -> None:
        report = D3._validate_d2_parent(self.fixture)
        report_path = BASE / D3.D2_REPORT_NAME
        self.assertEqual(D3.file_sha256(report_path), D3.D2_REPORT_SHA256)
        self.assertEqual(report_path.stat().st_size, D3.D2_REPORT_SIZE_BYTES)
        self.assertEqual(report["scientific_authority"], "NONE")
        self.assertIsNone(report["observation"]["resource_witness"])
        firewall = self.policy["hindsight_firewall"]
        self.assertTrue(firewall["allowed_D2_result_facts_are_exhaustive"])
        self.assertEqual(firewall["allowed_D2_result_facts"], [
            "D2_report_identity_and_scientific_authority_NONE",
            "D2_trace_was_a_legal_interrupted_protocol_prefix",
            "D2_segments_A_through_D_returned",
            "D2_segment_E_started_and_checkpoint_1_reached",
            "D2_segment_E_checkpoint_2_and_returned_markers_were_absent",
            "D2_later_segment_step3_engine_return_and_step3_finalizer_markers_were_absent",
            "D2_resource_witness_is_null",
            "D2_future_S0_admission_is_not_established",
        ])
        forbidden = " ".join(
            firewall["forbidden_D2_or_suppressed_inputs"]
        ).lower()
        for fragment in (
            "exact_times", "return_code", "stderr", "phase_channel",
            "event_count", "rss", "tick", "mask", "coefficient",
            "digest", "neel", "final_state",
        ):
            self.assertIn(fragment, forbidden)
        dependency = self.policy["frozen_D2_dependency"]
        self.assertEqual(dependency, self.fixture["D2_parent_custody"])
        self.assertEqual(set(dependency), {
            "result_commit_sha", "report_relative_path", "report_size_bytes",
            "report_sha256", "report_type", "scientific_authority",
            "certificate_eligible", "result_contract_eligible",
            "phase_trace_status",
            "segments_A_through_D_returned_markers_reached",
            "segment_E_started_marker_reached",
            "segment_E_checkpoint_1_marker_reached",
            "segment_E_checkpoint_2_marker_reached",
            "segment_E_returned_marker_reached", "later_segment_markers_reached",
            "step3_engine_returned_marker_reached",
            "step3_finalizer_started_marker_reached",
            "step3_finalizer_returned_marker_reached",
            "resource_witness_is_null", "future_S0_admission_status",
            "allowed_result_informed_facts_are_exhaustive",
        })
        self.assertFalse({
            "observation", "process_returncode", "outer_monotonic_elapsed_ns",
            "stderr_sha256", "phase_channel_sha256", "time_diagnostics",
        } & set(dependency))

        # Read the D2 result dynamically so this test itself never freezes an
        # exact timing, return code, stderr/channel digest, or event count.
        observation = report["observation"]
        design_text = "\n".join((
            MODULE_PATH.read_text(encoding="utf-8"),
            (BASE / D3.PROBE_DRIVER).read_text(encoding="utf-8"),
            D3.canonical_bytes(self.fixture).decode("utf-8"),
            D3.canonical_bytes(self.policy).decode("utf-8"),
        ))
        exact_forbidden_values = [
            observation["outer_monotonic_elapsed_ns"],
            observation["process_returncode"],
            observation["stderr_bytes"], observation["stderr_sha256"],
            observation["phase_channel_bytes"],
            observation["phase_channel_sha256"],
            observation["phase_trace_protocol_sha256"],
            *(
                row["outer_receive_elapsed_ns"]
                for row in observation["phase_events"]
            ),
        ]
        for exact_value in exact_forbidden_values:
            with self.subTest(D2_forbidden_exact_value=exact_value):
                self.assertNotIn(str(exact_value), design_text)
        self.assertIn(D3.D2_REPORT_SHA256, design_text)
        self.assertIn(str(D3.D2_REPORT_SIZE_BYTES), design_text)

        assigned_D2_names = {
            target.id
            for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding="utf-8")))
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name) and target.id.startswith("D2_")
        }
        self.assertEqual(assigned_D2_names, {
            "D2_ORCHESTRATOR_NAME", "D2_POLICY_NAME", "D2_FIXTURE_NAME",
            "D2_REPORT_NAME", "D2_REPORT_SHA256", "D2_REPORT_SIZE_BYTES",
            "D2_LAST_PHASE_EVENT", "D2_ADMISSION_STATUS",
        })

    def test_candidate_algorithm_caps_and_S0_nonadmission_are_unchanged(self) -> None:
        identity = self.fixture["frozen_candidate_identity"]
        self.assertEqual(identity["candidate_id"], D3.CANDIDATE_ID)
        self.assertEqual(identity["scientific_probe_mode"], D3.SCIENTIFIC_PROBE_MODE)
        self.assertEqual(identity["algorithm_id"], D3.ALGORITHM_ID)
        self.assertTrue(identity["D3_does_not_define_a_new_scientific_candidate"])
        d0_fixture = D3.D0._validate_fixture(D3.load_json(BASE / D3.D0_FIXTURE_NAME))
        self.assertEqual(self.fixture["host_supervisor_caps"], d0_fixture["host_supervisor_caps"])
        self.assertEqual(self.fixture["runtime_custody"], d0_fixture["runtime_custody"])
        self.assertEqual(self.fixture["host_supervisor_caps"]["MemoryMax_bytes"], 2 * 1024**3)
        self.assertEqual(self.fixture["host_supervisor_caps"]["MemorySwapMax_bytes"], 0)
        self.assertEqual(self.fixture["host_supervisor_caps"]["RuntimeMaxSec"], "1800s")
        self.assertEqual(D3.S0_ADMISSION, {
            "status": "NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC",
            "derived_from_D3": False,
            "D2_status_unchanged": "NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC",
            "same_host_admission_as_D0_D1_and_D2": True,
        })

    def test_all_fixed_and_parameterized_terminal_sequences_are_exact(self) -> None:
        terminal_paths = D3._terminal_paths()
        self.assertEqual(len(terminal_paths), 36)
        self.assertEqual(len(D3._step3_cap_sequences()), 32)
        branch_counts: dict[str, int] = {}
        for branch, sequence in terminal_paths:
            branch_counts[branch] = branch_counts.get(branch, 0) + 1
            legal, terminal = D3._classify_event_names(sequence)
            self.assertTrue(legal)
            self.assertEqual(terminal, branch)
            events, actual = D3._validate_phase_trace(
                collector_for(sequence), self.fixture,
            )
            self.assertEqual(actual, branch)
            self.assertEqual([row["event"] for row in events], sequence)
            for size in range(len(sequence)):
                prefix_legal, _ = D3._classify_event_names(sequence[:size])
                self.assertTrue(prefix_legal)
        self.assertEqual(branch_counts, {
            "FULL_PATH_RETURNED": 1,
            "STEP1_DETERMINISTIC_CAP": 1,
            "STEP2_DETERMINISTIC_CAP": 1,
            "P6_PREFIX_RESOURCE_CONFORMANCE_FAILURE": 1,
            "STEP3_DETERMINISTIC_CAP": 32,
        })

    def test_zero_internal_cap_gap_duplicate_and_unknown_are_rejected(self) -> None:
        zero_internal_cap = list(D3._COMMON_TO_STEP3 + (
            "STEP3_ENGINE_RETURNED", "STEP3_DETERMINISTIC_CAP_TERMINAL",
        ) + D3._SERIALIZATION_SUFFIX)
        legal, terminal = D3._classify_event_names(zero_internal_cap)
        self.assertFalse(legal)
        self.assertIsNone(terminal)

        for size in D3.UNREACHABLE_SEGMENT_RETURNED_CAP_PREFIX_COUNTS:
            unreachable_cap = list(
                D3._COMMON_TO_STEP3 + D3.INTERNAL_SCHEDULE_EVENTS[:size] + (
                    "STEP3_ENGINE_RETURNED",
                    "STEP3_DETERMINISTIC_CAP_TERMINAL",
                ) + D3._SERIALIZATION_SUFFIX
            )
            with self.subTest(unreachable_cap_prefix=size):
                legal, terminal = D3._classify_event_names(unreachable_cap)
                self.assertFalse(legal)
                self.assertIsNone(terminal)

        internal = list(D3.INTERNAL_SCHEDULE_EVENTS)
        invalid_sequences = (
            list(D3._COMMON_TO_STEP3) + internal[:1] + internal[2:3],
            list(D3._COMMON_TO_STEP3) + [internal[0], internal[0]],
            list(D3._COMMON_TO_STEP3) + ["UNKNOWN"],
        )
        for names in invalid_sequences:
            with self.subTest(names=names[-2:]), self.assertRaises(D3.ProbeError):
                D3._validate_phase_trace(collector_for(names), self.fixture)

    def test_complete_cap_and_interrupted_observations_are_classified(self) -> None:
        completed = D3._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(stderr=complete_time_stderr()),
            elapsed_ns=1_000_000_000,
            collector=collector_for(D3.FIXED_TERMINAL_SEQUENCES["FULL_PATH_RETURNED"]),
            fixture=self.fixture,
        )
        self.assertEqual(completed["status"], "COMPLETED_E_SUBGRID_DIAGNOSTIC")
        self.assertEqual(completed["diagnostic_terminal_branch"], "FULL_PATH_RETURNED")
        self.assertIsNone(completed["resource_witness"])

        cap_sequence = D3._step3_cap_sequences()[17]
        cap = D3._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(stderr=complete_time_stderr()),
            elapsed_ns=1_000_000_000,
            collector=collector_for(cap_sequence), fixture=self.fixture,
        )
        self.assertEqual(cap["diagnostic_terminal_branch"], "STEP3_DETERMINISTIC_CAP")

        prefix = list(D3._COMMON_TO_STEP3) + list(D3.INTERNAL_SCHEDULE_EVENTS[:9])
        interrupted = D3._observation_from_process(
            process_started=True, returncode=70, timed_out=False,
            **stream_fields(), elapsed_ns=1_800_000_000_000,
            collector=collector_for(prefix), fixture=self.fixture,
        )
        self.assertEqual(interrupted["status"], "INDETERMINATE_HOST_OR_RUNTIME_FAILURE")
        self.assertEqual(interrupted["phase_trace_status"], "LEGAL_PREFIX_INTERRUPTED")
        self.assertEqual(interrupted["last_phase_event"], prefix[-1])

        transport = D3._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(), elapsed_ns=1000,
            collector=collector_for(prefix, eof=False, read_failure=True),
            fixture=self.fixture,
        )
        self.assertEqual(transport["status"], "INDETERMINATE_HOST_OR_RUNTIME_FAILURE")

    def test_nonempty_stdout_exit66_and_incomplete_clean_exit_are_invalid(self) -> None:
        prefix = list(D3._COMMON_TO_STEP3)
        with self.assertRaises(D3.ProbeError):
            D3._observation_from_process(
                process_started=True, returncode=0, timed_out=False,
                **stream_fields(stdout=b"x"), elapsed_ns=1000,
                collector=collector_for(prefix), fixture=self.fixture,
            )
        with self.assertRaises(D3.ProbeError):
            D3._observation_from_process(
                process_started=True, returncode=66, timed_out=False,
                **stream_fields(), elapsed_ns=1000,
                collector=collector_for(prefix), fixture=self.fixture,
            )
        with self.assertRaises(D3.ProbeError):
            D3._observation_from_process(
                process_started=True, returncode=0, timed_out=False,
                **stream_fields(), elapsed_ns=1000,
                collector=collector_for(prefix), fixture=self.fixture,
            )

    def test_process_not_started_observation_has_one_reachable_shape(self) -> None:
        unstarted = D3._observation_from_process(
            process_started=False, returncode=-1, timed_out=False,
            **stream_fields(), elapsed_ns=1000,
            collector=collector_for([]), fixture=self.fixture,
        )
        self.assertEqual(
            unstarted["status"], "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertEqual(unstarted["phase_events"], [])
        self.assertIsNone(unstarted["diagnostic_terminal_branch"])

        invalid_cases = (
            (0, False, b"", []),
            (-1, True, b"", []),
            (-1, False, b"x", []),
            (-1, False, b"", ["D3_RUNNER_STARTED"]),
        )
        for returncode, timed_out, stderr, events in invalid_cases:
            with self.subTest(
                returncode=returncode, timed_out=timed_out,
                stderr=stderr, events=events,
            ), self.assertRaises(D3.ProbeError):
                D3._observation_from_process(
                    process_started=False, returncode=returncode,
                    timed_out=timed_out, **stream_fields(stderr=stderr),
                    elapsed_ns=1000, collector=collector_for(events),
                    fixture=self.fixture,
                )

    def test_pipe_records_are_canonical_contiguous_and_bounded(self) -> None:
        collector = collector_for(["D3_RUNNER_STARTED"])
        bad = D3.canonical_bytes({
            "event": "D3_INPUT_AND_RUNTIME_CUSTODY_VALIDATED", "sequence": 7,
        }) + b"\n"
        collector.lines.append((bad, 102))
        collector.total_bytes += len(bad)
        collector.digest.update(bad)
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(collector, self.fixture)

        noncanonical = collector_for([])
        line = b'{"sequence":0,"event":"D3_RUNNER_STARTED"}\n'
        noncanonical.lines.append((line, 1))
        noncanonical.total_bytes = len(line)
        noncanonical.digest.update(line)
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(noncanonical, self.fixture)

        overflow = collector_for(["D3_RUNNER_STARTED"])
        overflow.overflow = True
        with self.assertRaises(D3.ProbeError):
            D3._validate_phase_trace(overflow, self.fixture)

    def test_instrumented_kernel_is_exactly_derived_and_reverse_equal(self) -> None:
        relation = D3._validate_instrumented_kernel()
        self.assertEqual(relation, {
            "frozen_P6_runner_sha256": D3.P6_RUNNER_SHA256,
            "frozen_P6_function_slice_sha256": D3.P6_FUNCTION_SLICE_SHA256,
            "instrumented_D3_function_slice_sha256": (
                "0f0dcc5b0bc50b740cd8c9eeccdf7b7a134ed0b99c70e96efd9b046dce4b6787"
            ),
            "exact_function_name_substitution_count": 1,
            "exact_marker_insertion_block_count": 4,
            "forward_byte_construction_matches": True,
            "reverse_deletion_matches_frozen_P6_function": True,
            "marker_blocks_contain_no_live_scientific_state_tokens": True,
        })
        contract = self.fixture["scientific_kernel_byte_equivalence"]
        self.assertEqual(
            contract["normalization_contract"]["D3_function_name"],
            "execute_p6_step2_d3",
        )

    def test_scientific_or_marker_mutations_fail_byte_equivalence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p7-d3-kernel-") as temporary:
            root = Path(temporary)
            frozen = root / D3.P6_RUNNER_NAME
            driver = root / D3.PROBE_DRIVER
            frozen.parent.mkdir(parents=True)
            driver.parent.mkdir(parents=True)
            shutil.copyfile(BASE / D3.P6_RUNNER_NAME, frozen)
            shutil.copyfile(BASE / D3.PROBE_DRIVER, driver)
            with mock.patch.object(D3, "BASE", root):
                D3._validate_instrumented_kernel()
                body = driver.read_bytes()
                old = b"    maximum_combined = Int(caps["
                self.assertEqual(body.count(old), 1)
                driver.write_bytes(body.replace(
                    old, b"    maximum_combined = 0 + Int(caps[", 1,
                ))
                with self.assertRaises(D3.ProbeError):
                    D3._validate_instrumented_kernel()

        insertion = D3.MARKER_INSERTIONS[0]
        bad_insertions = (
            (insertion[0], insertion[1] + b"    cache\n", insertion[2]),
            *D3.MARKER_INSERTIONS[1:],
        )
        with mock.patch.object(D3, "MARKER_INSERTIONS", bad_insertions):
            with self.assertRaises(D3.ProbeError):
                D3._validate_instrumented_kernel()

    def test_Julia_driver_instruments_only_step3_and_reads_no_D2_artifact(self) -> None:
        source = (BASE / D3.PROBE_DRIVER).read_text(encoding="utf-8")
        self.assertIn("function execute_p6_step2_d3(", source)
        self.assertEqual(source.count("execute_p6_step2_d3("), 2)
        self.assertIn("if mapped_step_index == 2", source)
        self.assertIn("execution = execute_p6_step2(\n", source)
        self.assertIn("execution = execute_p6_step2_d3(\n", source)
        self.assertIn("3 <= phase_fd <= typemax(Cint)", source)
        self.assertEqual(source.count("include(joinpath("), 1)
        self.assertIn(
            '"majorana_certificate_p7_design_probe",\n'
            '    "majorana_p7_step3_resource_probe.jl",',
            source,
        )
        d2_report = "majorana_certificate_p7_d2_schedule_probe_report.json"
        self.assertEqual(source.count(d2_report), 1)
        self.assertIn(
            '"report_relative_path" =>\n            "' + d2_report + '",',
            source,
        )
        self.assertEqual(source.count("JSON.parsefile("), 7)
        for fixture_variable in (
            "d3_fixture_path", "d0_fixture_path", "p6_fixture_path",
            "p5_fixture_path", "p4_fixture_path", "p3_fixture_path",
            "p2_fixture_path",
        ):
            self.assertIn(f"JSON.parsefile({fixture_variable})", source)
        for excluded_artifact in (
            D3.D2_ORCHESTRATOR_NAME, D3.D2_POLICY_NAME, D3.D2_FIXTURE_NAME,
        ):
            self.assertNotIn(excluded_artifact, source)
        self.assertNotIn(f'JSON.parsefile("{d2_report}")', source)
        self.assertNotIn("time_ns(", source)
        self.assertNotIn("@elapsed", source)
        self.assertNotIn("@timed", source)
        declared = source.split("const P7_D3_PHASE_EVENTS = (", 1)[1].split("\n)", 1)[0]
        names = [line.split('"')[1] for line in declared.splitlines() if '"' in line]
        self.assertEqual(names, self.fixture["phase_event_protocol"]["allowed_events"])

    def test_standard_and_phase_file_descriptors_are_fail_closed(self) -> None:
        D3._validate_standard_fds_open()
        real_fstat = os.fstat
        for closed_descriptor in (0, 1, 2):
            def checked_fstat(
                descriptor: int, *, closed: int = closed_descriptor,
            ) -> os.stat_result:
                if descriptor == closed:
                    raise OSError("closed for test")
                return real_fstat(descriptor)

            with self.subTest(closed_descriptor=closed_descriptor), mock.patch.object(
                D3.os, "fstat", side_effect=checked_fstat,
            ), self.assertRaises(D3.ProbeError):
                D3._validate_standard_fds_open()

        for pipe_fds in ((0, 3), (3, 2)):
            with self.subTest(pipe_fds=pipe_fds), tempfile.TemporaryDirectory(
                prefix="p7-d3-low-fd-",
            ) as temporary, mock.patch.object(
                D3.os, "pipe", return_value=pipe_fds,
            ), mock.patch.object(D3.os, "close") as close_mock, mock.patch.object(
                D3.subprocess, "Popen",
            ) as popen_mock, self.assertRaises(D3.ProbeError):
                root = Path(temporary)
                D3._run_candidate(
                    root, root, root, self.fixture, root,
                )
            popen_mock.assert_not_called()
            close_mock.assert_has_calls(
                [mock.call(descriptor) for descriptor in set(pipe_fds)],
                any_order=True,
            )

        run_source = MODULE_PATH.read_text(encoding="utf-8").split(
            "def run_probe(", 1,
        )[1].split("def _validate_staging_manifest(", 1)[0]
        self.assertLess(
            run_source.index("_validate_standard_fds_open()"),
            run_source.index("_acquire_execution_claim("),
        )

    def test_stage_excludes_D2_results_drivers_and_sidecars(self) -> None:
        joined = " ".join(D3.STAGED_PATHS).lower()
        for fragment in (
            "d1_phase", "d2_schedule", "_report.json", "_certificate.json",
            "_contract.json",
            "replay_package", "sidecar", "checkpoint",
        ):
            self.assertNotIn(fragment, joined)
        with tempfile.TemporaryDirectory(prefix="p7-d3-stage-") as temporary:
            rows = D3.stage_probe_tree(Path(temporary), self.policy)
            self.assertEqual(len(rows), 15)
            self.assertTrue(all(row["byte_identical_to_repository"] for row in rows))

    def test_preprobe_path_allowlist_parent_and_result_absence_are_exact(self) -> None:
        self.assertEqual(D3.DIRECT_PARENT, "937065e0a576ba7615d48e389fb8e75e3e3aa677")
        self.assertEqual(len(D3.PREPROBE_CHANGED_PATHS), 5)
        self.assertEqual(D3.PREPROBE_CHANGED_PATHS, frozenset({
            f"docs/research/fermion-frontier/{D3.POLICY_NAME}",
            f"docs/research/fermion-frontier/{D3.FIXTURE_NAME}",
            f"docs/research/fermion-frontier/{MODULE_PATH.name}",
            f"docs/research/fermion-frontier/{D3.PROBE_DRIVER}",
            f"docs/research/fermion-frontier/{D3.TEST_NAME}",
        }))
        self.assertFalse((BASE / D3.REPORT_NAME).exists())
        self.assertFalse((BASE / D3.EXECUTION_CLAIM_NAME).exists())
        self.assertIsNone(self.fixture["observation_scope"]["resource_witness"])

    def test_plain_cli_import_creates_no_local_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p7-d3-pycache-") as temporary:
            environment = os.environ.copy()
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment["PYTHONPYCACHEPREFIX"] = temporary
            process = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--verify-preprobe"],
                cwd=BASE, env=environment, capture_output=True, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr.decode())
            local_caches = [
                path for path in Path(temporary).rglob("*.pyc")
                if "majorana_certificate_p7" in path.name
            ]
            self.assertEqual(local_caches, [])

    def test_run_output_is_canonical_and_repeat_claim_is_exclusive(self) -> None:
        with self.assertRaises(D3.ProbeError):
            D3._canonical_output_path(Path("/tmp/p7-d3-repeat.json"))
        with tempfile.TemporaryDirectory(prefix="p7-d3-claim-") as temporary:
            root = Path(temporary)
            with mock.patch.object(D3, "BASE", root):
                claim = D3._acquire_execution_claim("a" * 40)
                self.assertEqual(claim.read_text(), "a" * 40 + "\n")
                with self.assertRaises(D3.ProbeError):
                    D3._acquire_execution_claim("a" * 40)


if __name__ == "__main__":
    unittest.main()
