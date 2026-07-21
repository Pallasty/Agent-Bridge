#!/usr/bin/env python3
"""Exact-result tests for the non-authoritative Majorana P7 D4 V2 report."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
REPORT_SHA256 = "269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19"
REPORT_SIZE_BYTES = 11822
PREPROBE_COMMIT = "75371cf32b31e09ae255a1aafc2a98b2bf9d0a5a"
D3_PARENT_COMMIT = "70b5095fde9fdb743d1e5910b80bbcac88de4fca"

EXPECTED_EVENT_NAMES = (
    "D4_RUNNER_STARTED",
    "D4_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D4_STATIC_SETUP_COMPLETED",
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
    "STEP3_SEGMENT_A_STARTED",
    "STEP3_SEGMENT_A_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_A_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_A_RETURNED",
    "STEP3_SEGMENT_B_STARTED",
    "STEP3_SEGMENT_B_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_B_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_B_RETURNED",
    "STEP3_SEGMENT_C_STARTED",
    "STEP3_SEGMENT_C_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_C_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_C_RETURNED",
    "STEP3_SEGMENT_D_STARTED",
    "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED",
    "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED",
    "STEP3_SEGMENT_D_RETURNED",
    "STEP3_SEGMENT_E_STARTED",
)


def _load_probe():
    path = BASE / "majorana_certificate_p7_d4_e_per_composite_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p7_d4_v2_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D4 = _load_probe()


class MajoranaP7D4EPerCompositeProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = BASE / D4.REPORT_NAME
        cls.report = D4.validate_report(D4.load_json(cls.report_path))
        cls.policy = D4.validate_policy(
            D4.load_json(BASE / D4.POLICY_NAME), require_report_absent=False,
        )
        cls.fixture = D4._validate_fixture(
            D4.load_json(BASE / D4.FIXTURE_NAME),
        )
        cls.observation = cls.report["observation"]

    def test_report_hash_canonical_identity_and_authority_are_exact(self) -> None:
        self.assertTrue(self.report_path.is_file())
        self.assertFalse(self.report_path.is_symlink())
        self.assertEqual(self.report_path.stat().st_size, REPORT_SIZE_BYTES)
        self.assertEqual(D4.file_sha256(self.report_path), REPORT_SHA256)
        self.assertEqual(
            self.report_path.read_bytes(),
            D4.canonical_bytes(self.report) + b"\n",
        )
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["report_type"],
            "majorana_p7_step3_e768_max_lazy37_e_per_composite_report_d4_v2",
        )
        self.assertEqual(
            self.report["policy_id"],
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D4-E-PER-COMPOSITE-V2",
        )
        self.assertEqual(self.report["fixture_id"], self.report["policy_id"])
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertFalse(self.report["result_contract_eligible"])

    def test_preprobe_parent_candidate_and_kernel_custody_are_exact(self) -> None:
        self.assertEqual(self.report["preprobe_commit_sha"], PREPROBE_COMMIT)
        D4._validate_preprobe_commit_identity(PREPROBE_COMMIT)
        self.assertEqual(
            self.report["D3_parent_result_commit_sha"], D3_PARENT_COMMIT,
        )
        self.assertEqual(
            self.report["D3_parent_report_sha256"],
            "8374dff73a0753f95eba1fb1bcf3612e269095b33a223717293b33ef5f65f0db",
        )
        self.assertEqual(
            self.report["policy_sha256"],
            "7d0ebf419f61d5732c8cc1edf438e1187df771a151d772ea0cf020b03f3f19a7",
        )
        self.assertEqual(
            self.report["fixture_sha256"],
            "ea70e70dbb8f732aa84a10e153baf2feb1a553e077cad6547ebdbc9795a466cf",
        )
        self.assertEqual(
            self.report["fixture_canonical_sha256"],
            "b2a71a2cb338fde55c740d837d922ab301f4a25aaf8da1edd490197070483c52",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "fc0501fc88047af6e05f7d94c08b215d09c5f74b4abe74a3c8833249aea87e58",
        )
        semantic_policy = {
            key: value for key, value in self.policy.items()
            if key != "source_files"
        }
        self.assertEqual(
            D4.canonical_sha256(semantic_policy),
            "dd9eccb413212780c95726c9209c0ba6ad1299a7a465dd0fdf48d756c1a50a8d",
        )
        self.assertEqual(
            D4.canonical_sha256(self.fixture["phase_event_protocol"]),
            "006cdc5b779e3632dffa5a2e1efcd57ba5b246fa88046d8f7dcbaba9cac3e53b",
        )
        self.assertEqual(self.report["candidate"], {
            "D4_diagnostic_mode": "E768_MAX_LAZY37_STEP3_D4_E_PER_COMPOSITE_V2",
            "D4_does_not_define_a_new_scientific_candidate": True,
            "algorithm_id": "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1",
            "candidate_id": "E768-MAX-LAZY37-STEP3-V1",
            "scientific_probe_mode": "E768_MAX_LAZY37_STEP3_V1",
        })
        self.assertEqual(self.report["instrumented_kernel_custody"], {
            "exact_function_name_substitution_count": 1,
            "exact_marker_insertion_block_count": 4,
            "forward_byte_construction_matches": True,
            "frozen_P6_function_slice_sha256": (
                "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
            ),
            "frozen_P6_runner_sha256": (
                "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
            ),
            "instrumented_D4_function_slice_sha256": (
                "c7443273a6edff6f637d3e3fa7274b299fc04c31889be84e02b0e90ec80b8972"
            ),
            "marker_blocks_contain_no_live_scientific_state_tokens": True,
            "reverse_deletion_matches_frozen_P6_function": True,
        })

    def test_staging_manifest_is_exactly_bound_to_the_28_source_pins(self) -> None:
        pins = D4._source_pins(self.policy)
        self.assertEqual(len(pins), 28)
        self.assertEqual(set(pins), set(D4.SOURCE_PATHS))
        manifest = self.report["staging_manifest"]
        self.assertEqual(len(manifest), 15)
        self.assertEqual(
            [row["relative_path"] for row in manifest], list(D4.STAGED_PATHS),
        )
        for row in manifest:
            pin = pins[row["relative_path"]]
            self.assertEqual(row["repository_sha256"], pin["sha256"])
            self.assertEqual(row["staged_sha256"], pin["sha256"])
            self.assertEqual(row["staged_size_bytes"], pin["size_bytes"])
            self.assertTrue(row["byte_identical_to_repository"])
        self.assertNotIn(D4.REPORT_NAME, D4.STAGED_PATHS)
        self.assertNotIn(D4.REPORT_NAME, D4.SOURCE_PATHS)

    def test_trace_is_the_exact_32_event_legal_interrupted_prefix(self) -> None:
        events = self.observation["phase_events"]
        names = [row["event"] for row in events]
        self.assertEqual(self.observation["phase_event_count"], 32)
        self.assertEqual(len(events), 32)
        self.assertEqual(names, list(EXPECTED_EVENT_NAMES))
        self.assertEqual(
            names, D4.FIXED_TERMINAL_SEQUENCES["FULL_PATH_RETURNED"][:32],
        )
        self.assertEqual(names[15:], list(D4.INTERNAL_SCHEDULE_EVENTS[:17]))
        self.assertEqual(
            [row["sequence"] for row in events], list(range(32)),
        )
        legal, terminal = D4._classify_event_names(names)
        self.assertTrue(legal)
        self.assertIsNone(terminal)
        self.assertIsNone(self.observation["diagnostic_terminal_branch"])
        self.assertEqual(
            self.observation["phase_trace_status"], "LEGAL_PREFIX_INTERRUPTED",
        )
        self.assertTrue(self.observation["phase_channel_eof"])

        wire = b"".join(
            D4.canonical_bytes({
                "event": row["event"], "sequence": row["sequence"],
            }) + b"\n"
            for row in events
        )
        protocol_rows = [
            {"sequence": row["sequence"], "event": row["event"]}
            for row in events
        ]
        self.assertEqual(len(wire), 1730)
        self.assertEqual(
            hashlib.sha256(wire).hexdigest(),
            "613cdeab70c3eeeed067ffa0518dc056e5fbd07728bb66d8eeafc0c593d0929c",
        )
        self.assertEqual(
            self.observation["phase_channel_sha256"],
            hashlib.sha256(wire).hexdigest(),
        )
        self.assertEqual(
            D4.canonical_sha256(protocol_rows),
            "67a75de40a826d989fb14f47df37960bbda81201fc896ce278e4d5a260862590",
        )
        self.assertEqual(
            self.observation["phase_trace_protocol_sha256"],
            D4.canonical_sha256(protocol_rows),
        )
        receive_times = [row["outer_receive_elapsed_ns"] for row in events]
        self.assertEqual(receive_times, sorted(receive_times))
        self.assertTrue(all(
            0 <= value <= self.observation["outer_monotonic_elapsed_ns"]
            for value in receive_times
        ))

    def test_D4_did_not_reproduce_D3_CP1_or_subdivide_the_23_to_26_window(self) -> None:
        names = [row["event"] for row in self.observation["phase_events"]]
        for label in "ABCD":
            self.assertIn(f"STEP3_SEGMENT_{label}_RETURNED", names)
        self.assertEqual(names[-1], "STEP3_SEGMENT_E_STARTED")
        self.assertEqual(
            self.observation["last_phase_event"], "STEP3_SEGMENT_E_STARTED",
        )

        absent_E_events = (
            "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
            *(f"STEP3_SEGMENT_E_COMPOSITE_{ordinal}_REACHED"
              for ordinal in D4.E_PER_COMPOSITE_ORDINALS),
            "STEP3_SEGMENT_E_CHECKPOINT_2_REACHED",
            "STEP3_SEGMENT_E_RETURNED",
        )
        for event in absent_E_events:
            self.assertNotIn(event, names)
        for absent in (
            "STEP3_SEGMENT_F_STARTED",
            "STEP3_ENGINE_RETURNED",
            "STEP3_FINALIZER_STARTED",
            "STEP3_FINALIZER_RETURNED",
        ):
            self.assertNotIn(absent, names)

        parent = self.fixture["D3_parent_custody"]
        self.assertTrue(parent["segment_E_checkpoint_1_marker_reached"])
        self.assertTrue(parent["segment_E_started_marker_reached"])
        self.assertTrue(parent["segments_A_through_D_returned_markers_reached"])
        self.assertEqual(
            parent["future_S0_admission_status"],
            "NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC",
        )
        marker_map = self.fixture["step3_schedule_marker_map"]
        self.assertEqual(
            marker_map["segments"][4][
                "D4_per_composite_completed_composite_ordinals"
            ],
            [23, 24, 25, 26],
        )
        reached_ordinals = [
            ordinal for ordinal in D4.E_PER_COMPOSITE_ORDINALS
            if f"STEP3_SEGMENT_E_COMPOSITE_{ordinal}_REACHED" in names
        ]
        self.assertEqual(reached_ordinals, [])

        # D4 stopped before re-observing the D3 CP1 boundary.  It therefore
        # supplies no observed per-composite boundary inside the D3-local
        # 23--26 window and cannot overturn the earlier D3 prefix.
        self.assertEqual(tuple(D4.E_PER_COMPOSITE_ORDINALS), (23, 24, 25, 26))
        self.assertTrue(
            self.fixture["frozen_execution_relation"][
                "D4_refines_only_the_D3_local_E_23_through_26_window_with_per_composite_markers"
            ],
        )
        self.assertTrue(
            self.fixture["observation_scope"][
                "per_composite_progress_through_E_ordinal_26_does_not_establish_prefix_or_step3_scientific_truth"
            ],
        )

    def test_signal_exit_is_only_a_host_diagnostic_and_not_a_resource_no_go(self) -> None:
        self.assertEqual(
            self.observation["status"],
            "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertTrue(self.observation["process_started"])
        self.assertEqual(self.observation["process_returncode"], -15)
        self.assertFalse(self.observation["outer_timeout_triggered"])
        self.assertEqual(
            self.observation["outer_monotonic_elapsed_ns"], 1_800_351_788_777,
        )
        self.assertEqual(self.observation["stdout_bytes"], 0)
        self.assertEqual(
            self.observation["stdout_sha256"], hashlib.sha256(b"").hexdigest(),
        )
        self.assertEqual(self.observation["stderr_bytes"], 375)
        self.assertEqual(
            self.observation["stderr_sha256"],
            "0456aeda4063d9d3d990b1ba4de7db2ef7e38d23c92da89ca21681cb6e579677",
        )
        self.assertEqual(self.observation["time_diagnostics"], {})
        self.assertIsNone(self.observation["resource_witness"])
        self.assertTrue(
            self.observation["host_failure_has_no_mathematical_authority"],
        )
        self.assertEqual(
            self.report["host_caps"], self.fixture["host_supervisor_caps"],
        )
        self.assertEqual(
            self.report["host_caps"][
                "host_timeout_OOM_cgroup_supervisor_environment_or_sandbox_failure_branch"
            ],
            "INDETERMINATE",
        )
        self.assertTrue(
            self.report["host_caps"][
                "host_failure_has_no_mathematical_resource_no_go_or_candidate_selection_authority"
            ],
        )
        self.assertEqual(self.report["S0_admission"], {
            "D3_status_unchanged": "NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC",
            "derived_from_D4": False,
            "same_host_admission_as_D0_D1_D2_and_D3": True,
            "status": "NOT_ESTABLISHED_BY_D4_E_PER_COMPOSITE_DIAGNOSTIC",
        })
        self.assertEqual(
            self.report["authority_exclusions"],
            self.policy["authority_exclusions"],
        )
        D4.D0._reject_public_scientific_vocabulary(self.observation)

        forbidden_keys = {
            "operator_error_ticks", "product_defect_ticks",
            "merge_defect_ticks", "drop_defect_ticks", "allocation_pass",
            "allocation_slack", "coefficient_bits", "mask_hex", "drop_rows",
            "term_stream_sha256", "checkerboard_Neel_exact_dyadic_center",
            "declared_expectation_interval", "candidate_winner",
            "resource_witness_sha256", "final_state", "selected_mask",
        }
        seen_keys: set[str] = set()

        def collect_keys(value) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    seen_keys.add(str(key))
                    collect_keys(child)
            elif isinstance(value, list):
                for child in value:
                    collect_keys(child)

        collect_keys(self.report)
        self.assertTrue(forbidden_keys.isdisjoint(seen_keys))

    def test_report_cli_and_post_execution_lifecycle_are_exact(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.run(
            [
                sys.executable, "-B",
                str(BASE / "majorana_certificate_p7_d4_e_per_composite_probe.py"),
                "--verify-report",
            ],
            cwd=BASE, env=environment, check=False, capture_output=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertEqual(process.stderr, b"")
        self.assertEqual(process.stdout, (
            b'{"S0_admission_status":"NOT_ESTABLISHED_BY_D4_E_PER_COMPOSITE_DIAGNOSTIC",'
            b'"last_phase_event":"STEP3_SEGMENT_E_STARTED",'
            b'"observation_status":"INDETERMINATE_HOST_OR_RUNTIME_FAILURE",'
            b'"report_sha256":"269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19",'
            b'"status":"VERIFIED_P7_D4_E_PER_COMPOSITE_REPORT"}\n'
        ))
        claim = BASE / D4.EXECUTION_CLAIM_NAME
        self.assertFalse(claim.exists())
        self.assertFalse(claim.is_symlink())
        self.assertEqual(list(BASE.glob(f".{D4.REPORT_NAME}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
