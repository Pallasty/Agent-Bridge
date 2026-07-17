#!/usr/bin/env python3
"""Exact-result tests for the non-authoritative Majorana P7 D3 report."""

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
REPORT_SHA256 = "8374dff73a0753f95eba1fb1bcf3612e269095b33a223717293b33ef5f65f0db"
REPORT_SIZE_BYTES = 11888
PREPROBE_COMMIT = "55453f7fb0251f676a71220eb7b090d78ba6d8c5"
D2_PARENT_COMMIT = "937065e0a576ba7615d48e389fb8e75e3e3aa677"

EXPECTED_EVENT_NAMES = (
    "D3_RUNNER_STARTED",
    "D3_INPUT_AND_RUNTIME_CUSTODY_VALIDATED",
    "D3_STATIC_SETUP_COMPLETED",
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
    "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
)


def _load_probe():
    path = BASE / "majorana_certificate_p7_d3_e_subgrid_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p7_d3_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D3 = _load_probe()


class MajoranaP7D3ESubgridProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = BASE / D3.REPORT_NAME
        cls.report = D3.validate_report(D3.load_json(cls.report_path))
        cls.policy = D3.validate_policy(
            D3.load_json(BASE / D3.POLICY_NAME), require_report_absent=False,
        )
        cls.fixture = D3._validate_fixture(
            D3.load_json(BASE / D3.FIXTURE_NAME),
        )
        cls.observation = cls.report["observation"]

    def test_report_hash_canonical_identity_and_authority_are_exact(self) -> None:
        self.assertTrue(self.report_path.is_file())
        self.assertFalse(self.report_path.is_symlink())
        self.assertEqual(self.report_path.stat().st_size, REPORT_SIZE_BYTES)
        self.assertEqual(D3.file_sha256(self.report_path), REPORT_SHA256)
        self.assertEqual(
            self.report_path.read_bytes(),
            D3.canonical_bytes(self.report) + b"\n",
        )
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["report_type"],
            "majorana_p7_step3_e768_max_lazy37_e_subgrid_report_d3_v1",
        )
        self.assertEqual(
            self.report["policy_id"],
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D3-E-SUBGRID-V1",
        )
        self.assertEqual(self.report["fixture_id"], self.report["policy_id"])
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertFalse(self.report["result_contract_eligible"])

    def test_preprobe_parent_candidate_and_kernel_custody_are_exact(self) -> None:
        self.assertEqual(self.report["preprobe_commit_sha"], PREPROBE_COMMIT)
        D3._validate_preprobe_commit_identity(PREPROBE_COMMIT)
        self.assertEqual(
            self.report["D2_parent_result_commit_sha"], D2_PARENT_COMMIT,
        )
        self.assertEqual(
            self.report["D2_parent_report_sha256"],
            "94c8cc4bd9487f14d598d92dd96153ae9e631c8c232d484952b91eab3e5fd0dc",
        )
        self.assertEqual(
            self.report["policy_sha256"],
            "2eafd0d76a0095975ca52e514f8d02ec6ecf469a8dca720d5a4f9eab23ccd04a",
        )
        self.assertEqual(
            self.report["fixture_sha256"],
            "e1d87b4b6177ff7eeb51210379ad6aa1764e68f5bd2ebfd16a538a9e2623896c",
        )
        self.assertEqual(
            self.report["fixture_canonical_sha256"],
            "796b10d38dd5081a146c050aedbb0a96565841720fd802785a1fbe66852a2acf",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "e56c875b514aa142ba2c4b5adb6529b3cb4976b8fc3ba7a7fcd8ac8fdbfe818c",
        )
        semantic_policy = {
            key: value for key, value in self.policy.items()
            if key != "source_files"
        }
        self.assertEqual(
            D3.canonical_sha256(semantic_policy),
            "b16343e2526b9e918b07a6b5a9d83fd58d802cbb8d11bdc52b11da74b7ce2419",
        )
        self.assertEqual(
            D3.canonical_sha256(self.fixture["phase_event_protocol"]),
            "db9797fc5e508a26f0ec98f8052184a58f0e1c037c78f16368bf804b63cb5783",
        )
        self.assertEqual(self.report["candidate"], {
            "D3_diagnostic_mode": "E768_MAX_LAZY37_STEP3_D3_E_SUBGRID_V1",
            "D3_does_not_define_a_new_scientific_candidate": True,
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
            "instrumented_D3_function_slice_sha256": (
                "0f0dcc5b0bc50b740cd8c9eeccdf7b7a134ed0b99c70e96efd9b046dce4b6787"
            ),
            "marker_blocks_contain_no_live_scientific_state_tokens": True,
            "reverse_deletion_matches_frozen_P6_function": True,
        })

    def test_staging_manifest_is_exactly_bound_to_the_25_source_pins(self) -> None:
        pins = D3._source_pins(self.policy)
        self.assertEqual(len(pins), 25)
        self.assertEqual(set(pins), set(D3.SOURCE_PATHS))
        manifest = self.report["staging_manifest"]
        self.assertEqual(len(manifest), 15)
        self.assertEqual(
            [row["relative_path"] for row in manifest], list(D3.STAGED_PATHS),
        )
        for row in manifest:
            pin = pins[row["relative_path"]]
            self.assertEqual(row["repository_sha256"], pin["sha256"])
            self.assertEqual(row["staged_sha256"], pin["sha256"])
            self.assertEqual(row["staged_size_bytes"], pin["size_bytes"])
            self.assertTrue(row["byte_identical_to_repository"])
        self.assertNotIn(D3.REPORT_NAME, D3.STAGED_PATHS)
        self.assertNotIn(D3.REPORT_NAME, D3.SOURCE_PATHS)

    def test_trace_is_the_exact_33_event_legal_interrupted_prefix(self) -> None:
        events = self.observation["phase_events"]
        names = [row["event"] for row in events]
        self.assertEqual(self.observation["phase_event_count"], 33)
        self.assertEqual(len(events), 33)
        self.assertEqual(names, list(EXPECTED_EVENT_NAMES))
        self.assertEqual(
            names, D3.FIXED_TERMINAL_SEQUENCES["FULL_PATH_RETURNED"][:33],
        )
        self.assertEqual(names[15:], list(D3.INTERNAL_SCHEDULE_EVENTS[:18]))
        self.assertEqual(
            [row["sequence"] for row in events], list(range(33)),
        )
        legal, terminal = D3._classify_event_names(names)
        self.assertTrue(legal)
        self.assertIsNone(terminal)
        self.assertIsNone(self.observation["diagnostic_terminal_branch"])
        self.assertEqual(
            self.observation["phase_trace_status"], "LEGAL_PREFIX_INTERRUPTED",
        )
        self.assertTrue(self.observation["phase_channel_eof"])

        wire = b"".join(
            D3.canonical_bytes({
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
            "fdb08ed555118f8eb4772fff884c3cef530470b2c8046cf65c48b16cc48fa206",
        )
        self.assertEqual(
            self.observation["phase_channel_sha256"],
            hashlib.sha256(wire).hexdigest(),
        )
        self.assertEqual(
            D3.canonical_sha256(protocol_rows),
            "dcca24ef0be0919784590857f8d3cec5f077567044217357a578c9f756f32194",
        )
        self.assertEqual(
            self.observation["phase_trace_protocol_sha256"],
            D3.canonical_sha256(protocol_rows),
        )
        receive_times = [row["outer_receive_elapsed_ns"] for row in events]
        self.assertEqual(receive_times, sorted(receive_times))
        self.assertTrue(all(
            0 <= value <= self.observation["outer_monotonic_elapsed_ns"]
            for value in receive_times
        ))

    def test_last_committed_marker_is_E_CP1_and_all_subgrid_markers_are_absent(self) -> None:
        names = [row["event"] for row in self.observation["phase_events"]]
        for label in "ABCD":
            self.assertIn(f"STEP3_SEGMENT_{label}_RETURNED", names)
        self.assertEqual(names[-2:], [
            "STEP3_SEGMENT_E_STARTED",
            "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
        ])
        self.assertEqual(
            self.observation["last_phase_event"],
            "STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",
        )
        for ordinal in (26, 30, 34, 38):
            self.assertNotIn(
                f"STEP3_SEGMENT_E_SUBGRID_{ordinal}_REACHED", names,
            )
        for absent in (
            "STEP3_SEGMENT_E_CHECKPOINT_2_REACHED",
            "STEP3_SEGMENT_E_RETURNED",
            "STEP3_SEGMENT_F_STARTED",
            "STEP3_ENGINE_RETURNED",
            "STEP3_FINALIZER_STARTED",
            "STEP3_FINALIZER_RETURNED",
        ):
            self.assertNotIn(absent, names)
        segment_e = self.fixture["step3_schedule_marker_map"]["segments"][4]
        self.assertEqual(
            segment_e["D3_subgrid_completed_composite_ordinals"],
            [26, 30, 34, 38],
        )
        self.assertEqual(segment_e["checkpoint_1_completed_composites"], 22)
        self.assertTrue(
            self.observation["host_failure_has_no_mathematical_authority"],
        )

    def test_static_subgrid_mapping_narrows_only_the_unresolved_window(self) -> None:
        segments = self.fixture["step3_schedule_marker_map"]["segments"]
        prior_composites = sum(
            segment["frozen_composite_count"] for segment in segments[:4]
        )
        checkpoint_1 = segments[4]["checkpoint_1_completed_composites"]
        first_subgrid = segments[4][
            "D3_subgrid_completed_composite_ordinals"
        ][0]
        self.assertEqual(prior_composites, 224)
        self.assertEqual(checkpoint_1, 22)
        self.assertEqual(first_subgrid, 26)

        unresolved_local_ordinals = tuple(
            range(checkpoint_1 + 1, first_subgrid + 1)
        )
        self.assertEqual(unresolved_local_ordinals, (23, 24, 25, 26))
        self.assertEqual(
            tuple(
                prior_composites + ordinal - 1
                for ordinal in unresolved_local_ordinals
            ),
            (246, 247, 248, 249),
        )
        confirmed_completion_count = prior_composites + checkpoint_1
        possible_runtime_completion_counts = tuple(range(
            confirmed_completion_count, prior_composites + first_subgrid + 1,
        ))
        self.assertEqual(confirmed_completion_count, 246)
        self.assertEqual(
            possible_runtime_completion_counts, (246, 247, 248, 249, 250),
        )

        # The scientific completion counter advances before the ordinal-26
        # marker block executes, so an interruption may leave count 250 even
        # though the subgrid-26 marker is absent.
        driver = (BASE / D3.PROBE_DRIVER).read_bytes()
        function = D3._extract_function(
            driver, D3.D3_FUNCTION_NAME,
            following_name=b"p7_d3_execute_adaptive_step",
        )
        completion = b"                completed_composites += 1\n"
        marker = b"                # P7_D3_E_SUBGRID_MARKER_BLOCK_3_BEGIN\n"
        self.assertEqual(function.count(completion), 1)
        self.assertEqual(function.count(marker), 1)
        self.assertLess(function.index(completion), function.index(marker))

    def test_returncode_is_only_a_host_observation_and_S0_is_not_established(self) -> None:
        self.assertEqual(
            self.observation["status"],
            "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertTrue(self.observation["process_started"])
        self.assertEqual(self.observation["process_returncode"], -15)
        self.assertFalse(self.observation["outer_timeout_triggered"])
        self.assertEqual(
            self.observation["outer_monotonic_elapsed_ns"], 1_800_488_401_583,
        )
        self.assertEqual(self.observation["stdout_bytes"], 0)
        self.assertEqual(
            self.observation["stdout_sha256"], hashlib.sha256(b"").hexdigest(),
        )
        self.assertEqual(self.observation["stderr_bytes"], 3994)
        self.assertEqual(
            self.observation["stderr_sha256"],
            "1eb7d6d2774b74bfc3b3bc5b38d3fc880dc47b094ca5cbc2ce34bfdfd89d3bcf",
        )
        self.assertEqual(self.observation["time_diagnostics"], {})
        self.assertIsNone(self.observation["resource_witness"])
        self.assertTrue(
            self.observation["host_failure_has_no_mathematical_authority"],
        )
        self.assertEqual(
            self.report["host_caps"], self.fixture["host_supervisor_caps"],
        )
        self.assertEqual(self.report["S0_admission"], {
            "D2_status_unchanged": "NOT_ESTABLISHED_BY_D2_SCHEDULE_DIAGNOSTIC",
            "derived_from_D3": False,
            "same_host_admission_as_D0_D1_and_D2": True,
            "status": "NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC",
        })
        self.assertEqual(
            self.report["authority_exclusions"],
            self.policy["authority_exclusions"],
        )
        D3.D0._reject_public_scientific_vocabulary(self.observation)
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
                str(BASE / "majorana_certificate_p7_d3_e_subgrid_probe.py"),
                "--verify-report",
            ],
            cwd=BASE, env=environment, check=False, capture_output=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertEqual(process.stderr, b"")
        self.assertEqual(process.stdout, (
            b'{"S0_admission_status":"NOT_ESTABLISHED_BY_D3_E_SUBGRID_DIAGNOSTIC",'
            b'"last_phase_event":"STEP3_SEGMENT_E_CHECKPOINT_1_REACHED",'
            b'"observation_status":"INDETERMINATE_HOST_OR_RUNTIME_FAILURE",'
            b'"report_sha256":"8374dff73a0753f95eba1fb1bcf3612e269095b33a223717293b33ef5f65f0db",'
            b'"status":"VERIFIED_P7_D3_E_SUBGRID_REPORT"}\n'
        ))
        claim = BASE / D3.EXECUTION_CLAIM_NAME
        self.assertFalse(claim.exists())
        self.assertFalse(claim.is_symlink())
        self.assertEqual(list(BASE.glob(f".{D3.REPORT_NAME}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
