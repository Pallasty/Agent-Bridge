#!/usr/bin/env python3
"""Preprobe tests for the non-authoritative Majorana P7 D1 diagnostic."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest


sys.dont_write_bytecode = True


BASE = Path(__file__).resolve().parent
MODULE_PATH = BASE / "majorana_certificate_p7_d1_phase_probe.py"
SPEC = importlib.util.spec_from_file_location("majorana_p7_d1", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load P7 D1 phase-probe module")
D1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D1)


def collector_for(names: list[str], *, eof: bool = True) -> D1._PhaseCollector:
    protocol = D1.load_json(BASE / D1.FIXTURE_NAME)["phase_event_protocol"]
    collector = D1._PhaseCollector(
        -1, 0,
        max_line_bytes=protocol["maximum_line_bytes_including_newline"],
        max_total_bytes=protocol["maximum_total_channel_bytes"],
        max_events=protocol["maximum_event_count"],
    )
    raw = b""
    for sequence, event in enumerate(names):
        line = D1.canonical_bytes({"event": event, "sequence": sequence}) + b"\n"
        raw += line
        collector.lines.append((line, 100 + sequence))
    collector.total_bytes = len(raw)
    collector.digest.update(raw)
    collector.eof = eof
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


class P7D1PhasePreprobeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = D1.load_json(BASE / D1.FIXTURE_NAME)
        cls.policy = D1.load_json(BASE / D1.POLICY_NAME)

    def test_fixture_is_the_frozen_semantic_object(self) -> None:
        validated = D1._validate_fixture(self.fixture)
        self.assertEqual(
            D1.canonical_sha256(validated), D1.FIXTURE_CANONICAL_SHA256,
        )
        self.assertEqual(validated["scientific_authority"], "NONE")
        self.assertFalse(validated["certificate_eligible"])
        self.assertFalse(validated["result_contract_eligible"])

    def test_policy_is_the_frozen_semantic_object_and_sources_are_pinned(self) -> None:
        semantic = {
            key: value for key, value in self.policy.items()
            if key != "source_files"
        }
        self.assertEqual(
            D1.canonical_sha256(semantic), D1.POLICY_SEMANTIC_SHA256,
        )
        validated = D1.validate_policy(
            self.policy,
            require_report_absent=not (BASE / D1.REPORT_NAME).exists(),
        )
        self.assertEqual(validated["policy_id"], D1.POLICY_ID)
        pins = D1._source_pins(validated)
        self.assertEqual(set(pins), set(D1.SOURCE_PATHS))

    def test_D0_parent_is_exact_and_only_allowed_terminal_facts_are_used(self) -> None:
        report = D1._validate_d0_parent(self.fixture)
        self.assertEqual(D1.file_sha256(BASE / D1.D0_REPORT_NAME),
                         D1.D0_REPORT_SHA256)
        self.assertEqual(report["scientific_authority"], "NONE")
        self.assertEqual(report["observations"][0]["status"],
                         D1.D0_TERMINAL_STATUS)
        self.assertIsNone(report["observations"][0]["resource_witness"])
        self.assertEqual(report["fixed_formal_admission"]["status"],
                         D1.D0_ADMISSION_STATUS)
        firewall = self.policy["hindsight_firewall"]
        self.assertEqual(len(firewall["allowed_D0_result_facts"]), 4)
        forbidden = " ".join(firewall["forbidden_D0_or_suppressed_inputs"])
        for fragment in (
            "exact_elapsed", "returncode", "stderr", "RSS", "tick",
            "mask", "coefficient", "digest", "Neel", "final_state",
        ):
            self.assertIn(fragment, forbidden)

    def test_candidate_algorithm_and_host_admission_are_unchanged(self) -> None:
        identity = self.fixture["frozen_candidate_identity"]
        self.assertEqual(identity["candidate_id"], D1.CANDIDATE_ID)
        self.assertEqual(identity["scientific_probe_mode"],
                         D1.SCIENTIFIC_PROBE_MODE)
        self.assertEqual(identity["algorithm_id"], D1.ALGORITHM_ID)
        self.assertTrue(identity["D1_does_not_define_a_new_scientific_candidate"])
        d0_fixture = D1.D0._validate_fixture(
            D1.load_json(BASE / D1.D0_FIXTURE_NAME),
        )
        self.assertEqual(self.fixture["host_supervisor_caps"],
                         d0_fixture["host_supervisor_caps"])
        self.assertEqual(self.fixture["runtime_custody"],
                         d0_fixture["runtime_custody"])
        self.assertEqual(self.fixture["host_supervisor_caps"]["MemoryMax_bytes"],
                         2 * 1024**3)
        self.assertEqual(self.fixture["host_supervisor_caps"]["MemorySwapMax_bytes"],
                         0)
        self.assertEqual(self.fixture["host_supervisor_caps"]["RuntimeMaxSec"],
                         "1800s")

    def test_every_terminal_sequence_and_every_prefix_is_accepted(self) -> None:
        terminals = self.fixture["phase_event_protocol"][
            "legal_terminal_sequences"
        ]
        for branch, sequence in terminals.items():
            events, actual = D1._validate_phase_trace(
                collector_for(sequence), self.fixture,
            )
            self.assertEqual(actual, branch)
            self.assertEqual([row["event"] for row in events], sequence)
            for size in range(len(sequence)):
                prefix_events, prefix_terminal = D1._validate_phase_trace(
                    collector_for(sequence[:size]), self.fixture,
                )
                self.assertIsNone(prefix_terminal)
                self.assertEqual(len(prefix_events), size)

    def test_phase_language_rejects_unknown_gap_duplicate_and_noncanonical(self) -> None:
        full = self.fixture["phase_event_protocol"][
            "legal_terminal_sequences"
        ]["FULL_PATH_RETURNED"]
        unknown = collector_for(full[:2])
        record = {"event": "UNKNOWN", "sequence": 2}
        line = D1.canonical_bytes(record) + b"\n"
        unknown.lines.append((line, 102))
        unknown.total_bytes += len(line)
        unknown.digest.update(line)
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(unknown, self.fixture)

        duplicate = collector_for([full[0], full[0]])
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(duplicate, self.fixture)

        gap = collector_for(full[:2])
        wrong = D1.canonical_bytes({"event": full[2], "sequence": 7}) + b"\n"
        gap.lines.append((wrong, 102))
        gap.total_bytes += len(wrong)
        gap.digest.update(wrong)
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(gap, self.fixture)

        noncanonical = collector_for([])
        bad = b'{"sequence":0,"event":"D1_RUNNER_STARTED"}\n'
        noncanonical.lines.append((bad, 1))
        noncanonical.total_bytes = len(bad)
        noncanonical.digest.update(bad)
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(noncanonical, self.fixture)

    def test_phase_language_rejects_partial_and_overflow(self) -> None:
        collector = collector_for(["D1_RUNNER_STARTED"])
        collector.trailing_partial = True
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(collector, self.fixture)
        collector = collector_for(["D1_RUNNER_STARTED"])
        collector.overflow = True
        with self.assertRaises(D1.ProbeError):
            D1._validate_phase_trace(collector, self.fixture)

    def test_concurrent_pipe_collector_frames_only_complete_records(self) -> None:
        protocol = self.fixture["phase_event_protocol"]
        read_fd, write_fd = os.pipe()
        started = time.monotonic_ns()
        collector = D1._PhaseCollector(
            read_fd, started,
            max_line_bytes=protocol["maximum_line_bytes_including_newline"],
            max_total_bytes=protocol["maximum_total_channel_bytes"],
            max_events=protocol["maximum_event_count"],
        )
        thread = threading.Thread(target=collector.run)
        thread.start()
        raw = b"".join(
            D1.canonical_bytes({"event": event, "sequence": sequence}) + b"\n"
            for sequence, event in enumerate((
                "D1_RUNNER_STARTED",
                "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
            ))
        )
        os.write(write_fd, raw)
        os.close(write_fd)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(collector.eof)
        events, branch = D1._validate_phase_trace(collector, self.fixture)
        self.assertEqual(len(events), 2)
        self.assertIsNone(branch)

    def test_complete_and_interrupted_observation_classification(self) -> None:
        full = self.fixture["phase_event_protocol"][
            "legal_terminal_sequences"
        ]["FULL_PATH_RETURNED"]
        completed = D1._observation_from_process(
            process_started=True, returncode=0, timed_out=False,
            **stream_fields(stderr=complete_time_stderr()),
            elapsed_ns=1_000_000,
            collector=collector_for(full), fixture=self.fixture,
        )
        self.assertEqual(completed["status"], "COMPLETED_PHASE_DIAGNOSTIC")
        self.assertEqual(completed["diagnostic_terminal_branch"],
                         "FULL_PATH_RETURNED")
        self.assertIsNone(completed["resource_witness"])

        interrupted = D1._observation_from_process(
            process_started=True, returncode=70, timed_out=False,
            **stream_fields(), elapsed_ns=1_800_000_000_000,
            collector=collector_for(full[:15]), fixture=self.fixture,
        )
        self.assertEqual(interrupted["status"],
                         "INDETERMINATE_HOST_OR_RUNTIME_FAILURE")
        self.assertEqual(interrupted["phase_trace_status"],
                         "LEGAL_PREFIX_INTERRUPTED")
        self.assertEqual(interrupted["last_phase_event"], full[14])

    def test_nonempty_stdout_exit66_and_incomplete_clean_exit_are_invalid(self) -> None:
        runner = collector_for(["D1_RUNNER_STARTED"])
        with self.assertRaises(D1.ProbeError):
            D1._observation_from_process(
                process_started=True, returncode=0, timed_out=False,
                **stream_fields(stdout=b"x"), elapsed_ns=1,
                collector=runner, fixture=self.fixture,
            )
        with self.assertRaises(D1.ProbeError):
            D1._observation_from_process(
                process_started=True, returncode=66, timed_out=False,
                **stream_fields(), elapsed_ns=1,
                collector=collector_for(["D1_RUNNER_STARTED"]),
                fixture=self.fixture,
            )
        with self.assertRaises(D1.ProbeError):
            D1._observation_from_process(
                process_started=True, returncode=0, timed_out=False,
                **stream_fields(stderr=complete_time_stderr()), elapsed_ns=1,
                collector=collector_for(["D1_RUNNER_STARTED"]),
                fixture=self.fixture,
            )

    def test_report_validator_rejects_exit66_and_retains_transport_prefix(self) -> None:
        collector = collector_for([
            "D1_RUNNER_STARTED",
            "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
        ], eof=False)
        collector.read_failure = True
        observation = D1._observation_from_process(
            process_started=True, returncode=70, timed_out=False,
            **stream_fields(), elapsed_ns=10_000,
            collector=collector, fixture=self.fixture,
        )
        self.assertEqual(observation["phase_event_count"], 2)
        self.assertEqual(observation["last_phase_event"],
                         "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED")
        self.assertEqual(observation["status"],
                         "INDETERMINATE_HOST_OR_RUNTIME_FAILURE")
        forged = dict(observation)
        forged["process_returncode"] = 66
        with self.assertRaises(D1.ProbeError):
            D1._validate_observation(forged, self.fixture)

    def test_bounded_stream_and_phase_collectors_do_not_retain_overflow(self) -> None:
        read_fd, write_fd = os.pipe()
        stream = D1._BoundedStreamCollector(os.fdopen(read_fd, "rb"), 32)
        thread = threading.Thread(target=stream.run)
        thread.start()
        payload = b"x" * 100_000
        os.write(write_fd, payload)
        os.close(write_fd)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(stream.total_bytes, len(payload))
        self.assertEqual(len(stream.payload), 32)
        self.assertEqual(stream.sha256, hashlib.sha256(payload).hexdigest())

        read_fd, write_fd = os.pipe()
        stream = D1._BoundedStreamCollector(os.fdopen(read_fd, "rb"), 32)
        thread = threading.Thread(target=stream.run)
        thread.start()
        stream.request_stop()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertTrue(stream.read_failure)
        self.assertFalse(stream.eof)
        os.close(write_fd)

        protocol = self.fixture["phase_event_protocol"]
        read_fd, write_fd = os.pipe()
        phase = D1._PhaseCollector(
            read_fd, time.monotonic_ns(),
            max_line_bytes=protocol["maximum_line_bytes_including_newline"],
            max_total_bytes=protocol["maximum_total_channel_bytes"],
            max_events=protocol["maximum_event_count"],
        )
        thread = threading.Thread(target=phase.run)
        thread.start()
        os.write(write_fd, b"x" * 100_000)
        os.close(write_fd)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(phase.overflow)
        self.assertEqual(phase.lines, [])
        self.assertEqual(phase.total_bytes, 100_000)

    def test_plain_cli_import_creates_no_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p7-d1-pycache-") as temporary:
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

    def test_run_output_is_canonical(self) -> None:
        with self.assertRaises(D1.ProbeError):
            D1._canonical_output_path(Path("/tmp/p7-d1-repeat.json"))

    def test_source_stage_is_exact_and_excludes_results_and_sidecars(self) -> None:
        self.assertEqual(len(D1.STAGED_PATHS), 15)
        self.assertEqual(tuple(D1.STAGED_PATHS[:13]), tuple(D1.D0.STAGED_PATHS))
        self.assertEqual(D1.STAGED_PATHS[-2:],
                         (D1.FIXTURE_NAME, D1.PROBE_DRIVER))
        joined = " ".join(D1.STAGED_PATHS).lower()
        for fragment in (
            "_report.json", "_certificate.json", "_contract.json",
            "replay_package", "sidecar",
        ):
            self.assertNotIn(fragment, joined)
        self.assertNotIn(D1.D0_POLICY_NAME, D1.STAGED_PATHS)
        self.assertNotIn(D1.D0_ORCHESTRATOR_NAME, D1.STAGED_PATHS)
        self.assertIn(D1.TEST_NAME, D1.SOURCE_PATHS)

    def test_Julia_driver_only_adds_outer_constant_count_events(self) -> None:
        source = (BASE / D1.PROBE_DRIVER).read_text(encoding="utf-8")
        self.assertIn("majorana_p7_step3_resource_probe.jl", source)
        self.assertIn("ccall(\n        :write", source)
        self.assertIn("function p7_d1_execute_adaptive_step", source)
        self.assertIn("function p7_d1_execute_prefix", source)
        self.assertNotIn("time_ns(", source)
        self.assertNotIn("@elapsed", source)
        self.assertNotIn("@timed", source)
        self.assertNotIn("include_string", source)
        self.assertNotIn("eval(", source)
        for forbidden_definition in (
            "function execute_p3(", "function execute_p6_step2(",
            "function finalize_p3_state!(", "function p6_should_drop(",
            "function p6_prepare_boundary_drop!(",
        ):
            self.assertNotIn(forbidden_definition, source)
        declared_block = re.search(
            r"const P7_D1_PHASE_EVENTS = \((.*?)\n\)", source, re.S,
        )
        self.assertIsNotNone(declared_block)
        declared = re.findall(r'"([A-Z0-9_]+)"', declared_block.group(1))
        self.assertEqual(declared,
                         self.fixture["phase_event_protocol"]["allowed_events"])

    def test_report_and_S0_authority_are_absent_from_preprobe(self) -> None:
        self.assertEqual(D1.S0_ADMISSION["status"],
                         "NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC")
        self.assertFalse(D1.S0_ADMISSION["derived_from_D1"])
        self.assertEqual(D1.S0_ADMISSION["D0_status_unchanged"],
                         D1.D0_ADMISSION_STATUS)
        self.assertIsNone(self.fixture["observation_scope"]["resource_witness"])
        if (BASE / D1.REPORT_NAME).exists():
            report = D1.load_json(BASE / D1.REPORT_NAME)
            self.assertEqual(report["scientific_authority"], "NONE")
            self.assertIsNone(report["observation"]["resource_witness"])


if __name__ == "__main__":
    unittest.main()
