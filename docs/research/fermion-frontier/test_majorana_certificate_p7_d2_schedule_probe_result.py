#!/usr/bin/env python3
"""Exact-result tests for the non-authoritative Majorana P7 D2 report."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
REPORT_SHA256 = "94c8cc4bd9487f14d598d92dd96153ae9e631c8c232d484952b91eab3e5fd0dc"
PREPROBE_COMMIT = "2692f10a266b635ef1942bc510801a7db952c0d9"


def _load_probe():
    path = BASE / "majorana_certificate_p7_d2_schedule_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p7_d2_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D2 = _load_probe()


class MajoranaP7D2ScheduleProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = BASE / D2.REPORT_NAME
        cls.report = D2.validate_report(D2.load_json(cls.report_path))
        cls.policy = D2.validate_policy(
            D2.load_json(BASE / D2.POLICY_NAME), require_report_absent=False,
        )
        cls.fixture = D2._validate_fixture(
            D2.load_json(BASE / D2.FIXTURE_NAME),
        )
        cls.observation = cls.report["observation"]

    def test_report_hash_canonical_identity_and_authority_are_exact(self) -> None:
        self.assertTrue(self.report_path.is_file())
        self.assertFalse(self.report_path.is_symlink())
        self.assertEqual(self.report_path.stat().st_size, 11874)
        self.assertEqual(D2.file_sha256(self.report_path), REPORT_SHA256)
        self.assertEqual(
            self.report_path.read_bytes(),
            D2.canonical_bytes(self.report) + b"\n",
        )
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["report_type"],
            "majorana_p7_step3_e768_max_lazy37_schedule_report_d2_v1",
        )
        self.assertEqual(
            self.report["policy_id"],
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D2-SCHEDULE-V1",
        )
        self.assertEqual(self.report["fixture_id"], self.report["policy_id"])
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertFalse(self.report["result_contract_eligible"])

    def test_preprobe_parent_policy_fixture_and_kernel_custody_are_exact(self) -> None:
        self.assertEqual(self.report["preprobe_commit_sha"], PREPROBE_COMMIT)
        D2._validate_preprobe_commit_identity(PREPROBE_COMMIT)
        self.assertEqual(
            self.report["D1_parent_result_commit_sha"],
            "29911a8ac46c068c550504f8b4a57d27a9441c0c",
        )
        self.assertEqual(
            self.report["D1_parent_report_sha256"],
            "9d37609c51f9149baf347fbf801338cc0abe7c7323c187fe71a4932099f8f713",
        )
        self.assertEqual(
            self.report["policy_sha256"],
            "1c507fb4e5e5789461ff5ff210bd740657783b98f8ce63d48da01e427ab92f32",
        )
        self.assertEqual(
            self.report["fixture_sha256"],
            "8bae19d2be2e9e58fd6fffe6f9c7c5b1fff4de3e71d8f4fc4fd6ff880dfe6a2d",
        )
        self.assertEqual(
            self.report["fixture_canonical_sha256"],
            "417600f82e46086adde81a632cae1da5c0dc1235c3f7a8d83875394d81a64dee",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "a13c83edcdf37c222e50a11c2fd98c025a72a793ab14caeb0dd488c9850fe4a2",
        )
        semantic_policy = {
            key: value for key, value in self.policy.items()
            if key != "source_files"
        }
        self.assertEqual(
            D2.canonical_sha256(semantic_policy),
            "bafc90b40a1dc1de3d95cd9e7e4d6eb9861a46b73e92c09eb697a671a3868277",
        )
        self.assertEqual(
            D2.canonical_sha256(self.fixture["phase_event_protocol"]),
            "b27caef5156aaae8946da2705c9a1956faa54e123aee341686449129c8da0e97",
        )
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
            "instrumented_D2_function_slice_sha256": (
                "f1f6dd4e0a114918d50df4e03ffb41fef683fee0393d158c8d77ea7e0c3f1f29"
            ),
            "marker_blocks_contain_no_live_scientific_state_tokens": True,
            "reverse_deletion_matches_frozen_P6_function": True,
        })

        pins = D2._source_pins(self.policy)
        self.assertEqual(len(pins), 22)
        self.assertEqual(set(pins), set(D2.SOURCE_PATHS))
        self.assertEqual(len(self.report["staging_manifest"]), 15)
        self.assertEqual(
            [row["relative_path"] for row in self.report["staging_manifest"]],
            list(D2.STAGED_PATHS),
        )
        for row in self.report["staging_manifest"]:
            pin = pins[row["relative_path"]]
            self.assertEqual(row["repository_sha256"], pin["sha256"])
            self.assertEqual(row["staged_sha256"], pin["sha256"])
            self.assertEqual(row["staged_size_bytes"], pin["size_bytes"])
            self.assertTrue(row["byte_identical_to_repository"])

    def test_candidate_and_exact_indeterminate_observation_are_frozen(self) -> None:
        self.assertEqual(self.report["candidate"], {
            "D2_diagnostic_mode": "E768_MAX_LAZY37_STEP3_D2_SCHEDULE_V1",
            "D2_does_not_define_a_new_scientific_candidate": True,
            "algorithm_id": "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1",
            "candidate_id": "E768-MAX-LAZY37-STEP3-V1",
            "scientific_probe_mode": "E768_MAX_LAZY37_STEP3_V1",
        })
        expected_events = [
            (0, "D2_RUNNER_STARTED", 206788907),
            (1, "D2_INPUT_AND_RUNTIME_CUSTODY_VALIDATED", 33360696970),
            (2, "D2_STATIC_SETUP_COMPLETED", 35470835013),
            (3, "STEP1_ENGINE_STARTED", 36239593537),
            (4, "STEP1_ENGINE_RETURNED", 64852694370),
            (5, "STEP1_FINALIZER_STARTED", 64852698468),
            (6, "STEP1_FINALIZER_RETURNED", 65848524301),
            (7, "STEP1_TO_STEP2_HANDOFF_COMPLETED", 65983174655),
            (8, "STEP2_ENGINE_STARTED", 66571828274),
            (9, "STEP2_ENGINE_RETURNED", 657167326390),
            (10, "STEP2_FINALIZER_STARTED", 657187984013),
            (11, "STEP2_FINALIZER_RETURNED", 660658183368),
            (12, "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED", 660801840022),
            (13, "STEP2_TO_STEP3_HANDOFF_COMPLETED", 660916298757),
            (14, "STEP3_ENGINE_STARTED", 660944943001),
            (15, "STEP3_SEGMENT_A_STARTED", 660944946021),
            (16, "STEP3_SEGMENT_A_CHECKPOINT_1_REACHED", 702670751345),
            (17, "STEP3_SEGMENT_A_CHECKPOINT_2_REACHED", 751301142265),
            (18, "STEP3_SEGMENT_A_RETURNED", 788810161597),
            (19, "STEP3_SEGMENT_B_STARTED", 788810163906),
            (20, "STEP3_SEGMENT_B_CHECKPOINT_1_REACHED", 820976491305),
            (21, "STEP3_SEGMENT_B_CHECKPOINT_2_REACHED", 866984011959),
            (22, "STEP3_SEGMENT_B_RETURNED", 906968759578),
            (23, "STEP3_SEGMENT_C_STARTED", 906968762399),
            (24, "STEP3_SEGMENT_C_CHECKPOINT_1_REACHED", 1001080619643),
            (25, "STEP3_SEGMENT_C_CHECKPOINT_2_REACHED", 1151783107375),
            (26, "STEP3_SEGMENT_C_RETURNED", 1309914244627),
            (27, "STEP3_SEGMENT_D_STARTED", 1309914247979),
            (28, "STEP3_SEGMENT_D_CHECKPOINT_1_REACHED", 1387581283212),
            (29, "STEP3_SEGMENT_D_CHECKPOINT_2_REACHED", 1484880970221),
            (30, "STEP3_SEGMENT_D_RETURNED", 1585779304266),
            (31, "STEP3_SEGMENT_E_STARTED", 1585779306765),
            (32, "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED", 1737307683340),
        ]
        events = [
            {
                "sequence": sequence,
                "event": event,
                "outer_receive_elapsed_ns": elapsed,
            }
            for sequence, event, elapsed in expected_events
        ]
        self.assertEqual(self.observation, {
            "diagnostic_terminal_branch": None,
            "host_failure_has_no_mathematical_authority": True,
            "last_phase_event": "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
            "outer_monotonic_elapsed_ns": 1800611541745,
            "outer_timeout_triggered": False,
            "phase_channel_bytes": 1793,
            "phase_channel_eof": True,
            "phase_channel_sha256": (
                "67e6e1110f624982913d1b4ab8d9956a290c146aa3d77cf41b800b7d7b117a53"
            ),
            "phase_event_count": 33,
            "phase_events": events,
            "phase_trace_protocol_sha256": (
                "9fb19ab0659529a4e8b5c773417de243eaac2b95a791f06bad666a4efd012903"
            ),
            "phase_trace_status": "LEGAL_PREFIX_INTERRUPTED",
            "process_returncode": -15,
            "process_started": True,
            "resource_witness": None,
            "status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            "stderr_bytes": 4224,
            "stderr_sha256": (
                "30362101f627652dfe31ae88aefd53f7c426dd7207db5a0036c7f336f51d5e11"
            ),
            "stdout_bytes": 0,
            "stdout_sha256": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            "time_diagnostics": {},
        })

        wire = b"".join(
            D2.canonical_bytes({
                "event": row["event"], "sequence": row["sequence"],
            }) + b"\n"
            for row in events
        )
        protocol_rows = [
            {"sequence": row["sequence"], "event": row["event"]}
            for row in events
        ]
        self.assertEqual(len(wire), 1793)
        self.assertEqual(
            hashlib.sha256(wire).hexdigest(),
            self.observation["phase_channel_sha256"],
        )
        self.assertEqual(
            D2.canonical_sha256(protocol_rows),
            self.observation["phase_trace_protocol_sha256"],
        )

    def test_trace_localizes_the_unmarked_window_to_E_composites_23_through_43(self) -> None:
        names = [row["event"] for row in self.observation["phase_events"]]
        self.assertEqual(
            names,
            D2.FIXED_TERMINAL_SEQUENCES["FULL_PATH_RETURNED"][:33],
        )
        self.assertEqual(
            names[15:], list(D2.INTERNAL_SCHEDULE_EVENTS[:18]),
        )
        legal, terminal = D2._classify_event_names(names)
        self.assertTrue(legal)
        self.assertIsNone(terminal)
        for label in "ABCD":
            self.assertIn(f"STEP3_SEGMENT_{label}_RETURNED", names)
        self.assertEqual(names[-2:], [
            "STEP3_SEGMENT_E_STARTED",
            "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
        ])
        for absent in (
            "STEP3_SEGMENT_E_CHECKPOINT_2_REACHED",
            "STEP3_SEGMENT_E_RETURNED", "STEP3_ENGINE_RETURNED",
            "STEP3_FINALIZER_STARTED", "STEP3_FINALIZER_RETURNED",
        ):
            self.assertNotIn(absent, names)

        segments = self.fixture["step3_schedule_marker_map"]["segments"]
        segment_e = segments[4]
        completed_before_e = sum(
            row["frozen_composite_count"] for row in segments[:4]
        )
        self.assertEqual(completed_before_e, 224)
        self.assertEqual(segment_e["frozen_group"], "H4")
        self.assertEqual(segment_e["checkpoint_1_completed_composites"], 22)
        self.assertEqual(segment_e["checkpoint_2_completed_composites"], 43)
        minimum_confirmed_completed_count = completed_before_e + 22
        maximum_possible_completed_count = completed_before_e + 43
        first_unmarked_zero_based_index = minimum_confirmed_completed_count
        last_unmarked_zero_based_index = maximum_possible_completed_count - 1
        self.assertEqual(minimum_confirmed_completed_count, 246)
        self.assertEqual(maximum_possible_completed_count, 267)
        self.assertEqual(first_unmarked_zero_based_index, 246)
        self.assertEqual(last_unmarked_zero_based_index, 266)

        elapsed = {
            row["event"]: row["outer_receive_elapsed_ns"]
            for row in self.observation["phase_events"]
        }
        self.assertEqual(
            elapsed["STEP3_SEGMENT_E_STARTED"]
            - elapsed["STEP3_ENGINE_STARTED"],
            924834363764,
        )
        self.assertEqual(
            elapsed["STEP3_SEGMENT_E_CHECKPOINT_1_REACHED"]
            - elapsed["STEP3_SEGMENT_E_STARTED"],
            151528376575,
        )
        self.assertEqual(
            self.observation["outer_monotonic_elapsed_ns"]
            - elapsed["STEP3_SEGMENT_E_CHECKPOINT_1_REACHED"],
            63303858405,
        )

    def test_same_host_caps_do_not_establish_S0_admission(self) -> None:
        self.assertEqual(
            self.report["host_caps"], self.fixture["host_supervisor_caps"],
        )
        self.assertEqual(self.report["host_caps"]["MemoryMax_bytes"], 2147483648)
        self.assertEqual(self.report["host_caps"]["MemorySwapMax_bytes"], 0)
        self.assertEqual(self.report["host_caps"]["RuntimeMaxSec"], "1800s")
        self.assertEqual(self.report["S0_admission"], {
            "D1_status_unchanged": "NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC",
            "derived_from_D2": False,
            "same_host_admission_as_D0_and_D1": True,
            "status": "NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC",
        })
        self.assertEqual(
            self.observation["status"],
            "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertEqual(self.observation["process_returncode"], -15)
        self.assertFalse(self.observation["outer_timeout_triggered"])
        self.assertGreater(
            self.observation["outer_monotonic_elapsed_ns"], 1_800_000_000_000,
        )
        self.assertLess(
            self.observation["outer_monotonic_elapsed_ns"], 1_830_000_000_000,
        )

    def test_report_exposes_no_scientific_witness_or_result_fields(self) -> None:
        self.assertIsNone(self.observation["resource_witness"])
        D2.D0._reject_public_scientific_vocabulary(self.observation)
        self.assertEqual(
            self.report["authority_exclusions"],
            self.policy["authority_exclusions"],
        )
        forbidden_exact_keys = {
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
        self.assertTrue(forbidden_exact_keys.isdisjoint(seen_keys))
        for content_key in (
            "stdout_content", "stderr_content", "phase_channel_content",
        ):
            self.assertNotIn(content_key, seen_keys)
        for row in self.observation["phase_events"]:
            lowered = row["event"].lower()
            for fragment in (
                "tick", "budget", "mask", "coefficient", "digest", "neel",
                "term_count", "state", "observable",
            ):
                self.assertNotIn(fragment, lowered)

        claim = BASE / D2.EXECUTION_CLAIM_NAME
        self.assertFalse(claim.exists())
        self.assertFalse(claim.is_symlink())
        self.assertEqual(list(BASE.glob(f".{D2.REPORT_NAME}.*.tmp")), [])
        self.assertNotIn(D2.REPORT_NAME, D2.STAGED_PATHS)
        self.assertNotIn(D2.REPORT_NAME, D2.SOURCE_PATHS)

    def test_report_cli_verifier_is_canonical_and_exact(self) -> None:
        process = subprocess.run(
            [sys.executable, str(BASE / "majorana_certificate_p7_d2_schedule_probe.py"),
             "--verify-report"],
            cwd=BASE, check=False, capture_output=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertEqual(process.stderr, b"")
        self.assertEqual(process.stdout, (
            b'{"S0_admission_status":"NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC",'
            b'"last_phase_event":"STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",'
            b'"observation_status":"INDETERMINATE_HOST_OR_RUNTIME_FAILURE",'
            b'"report_sha256":"94c8cc4bd9487f14d598d92dd96153ae9e631c8c232d484952b91eab3e5fd0dc",'
            b'"status":"VERIFIED_P7_D2_SCHEDULE_REPORT"}\n'
        ))


if __name__ == "__main__":
    unittest.main()
