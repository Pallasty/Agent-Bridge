#!/usr/bin/env python3
"""Exact-result tests for the non-authoritative Majorana P7 D1 report."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
REPORT_SHA256 = "9d37609c51f9149baf347fbf801338cc0abe7c7323c187fe71a4932099f8f713"
PREPROBE_COMMIT = "48a1be6932331e2925261965c783e6b40b555747"


def _load_probe():
    path = BASE / "majorana_certificate_p7_d1_phase_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p7_d1_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D1 = _load_probe()


class MajoranaP7D1PhaseProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = BASE / D1.REPORT_NAME
        cls.report = D1.validate_report(D1.load_json(cls.report_path))
        cls.policy = D1.validate_policy(
            D1.load_json(BASE / D1.POLICY_NAME), require_report_absent=False,
        )
        cls.fixture = D1._validate_fixture(
            D1.load_json(BASE / D1.FIXTURE_NAME)
        )
        cls.observation = cls.report["observation"]

    def test_report_hash_canonical_identity_and_authority_are_exact(self) -> None:
        self.assertTrue(self.report_path.is_file())
        self.assertFalse(self.report_path.is_symlink())
        self.assertEqual(self.report_path.stat().st_size, 9523)
        self.assertEqual(D1.file_sha256(self.report_path), REPORT_SHA256)
        self.assertEqual(
            self.report_path.read_bytes(),
            D1.canonical_bytes(self.report) + b"\n",
        )
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["report_type"],
            "majorana_p7_step3_e768_max_lazy37_phase_report_d1_v1",
        )
        self.assertEqual(
            self.report["policy_id"],
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D1-PHASE-V1",
        )
        self.assertEqual(self.report["fixture_id"], self.report["policy_id"])
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertFalse(self.report["result_contract_eligible"])

    def test_preprobe_parent_policy_and_fixture_custody_are_exact(self) -> None:
        self.assertEqual(self.report["preprobe_commit_sha"], PREPROBE_COMMIT)
        D1._validate_preprobe_commit_identity(PREPROBE_COMMIT)
        self.assertEqual(
            self.report["D0_parent_result_commit_sha"],
            "4ebed6b651e3c9605f84939d6a9efff8281bc38b",
        )
        self.assertEqual(
            self.report["D0_parent_report_sha256"],
            "4bf4be7f77fd499ffc9bd975f07353fd14ee7403cd6fc7759974dda37f8588cf",
        )
        self.assertEqual(
            self.report["policy_sha256"],
            "ff04d0e637508dd2b4b1927c6fe3a8be357412f052cc0bdc2bc328a5cba28218",
        )
        self.assertEqual(
            self.report["fixture_sha256"],
            "b8f83bb8f5fc08cbdfa048c67a0fbd7f854371aded9dfb17a4432c0a057ca2cb",
        )
        self.assertEqual(
            self.report["fixture_canonical_sha256"],
            "7b1f52866315cb241dbb24263d95fc0d61fc3fda83b2c05720bc89d2ca35c36d",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "970190d9e8b871bce985887d87ad08e62e55027b7602ce508dd382d9d2594dc7",
        )
        semantic_policy = {
            key: value for key, value in self.policy.items()
            if key != "source_files"
        }
        self.assertEqual(
            D1.canonical_sha256(semantic_policy),
            "160263d1646965c2919a1cb09a0b339ffe04933ff865fe6890bd43d591758b24",
        )
        self.assertEqual(
            D1.canonical_sha256(self.fixture["phase_event_protocol"]),
            "ed1b72ebef7f432725585d0efddff4373bd7cc9e54deea12973ab67101236d6c",
        )
        parent = D1._validate_d0_parent(self.fixture)
        self.assertEqual(parent["scientific_authority"], "NONE")
        self.assertIsNone(parent["observations"][0]["resource_witness"])

    def test_fifteen_staged_and_nineteen_pinned_source_rows_are_exact(self) -> None:
        expected_sources = (
            ("majorana_certificate_p0/Project.toml", 235,
             "62810ce02db16bf25cb74941f27f58ee556ee0826abc4aa47296ce8188a5048f"),
            ("majorana_certificate_p0/Manifest.toml", 15336,
             "987572a908176b21cfbe80c385acdd0b4ab47b6c6dcd3ea9a33dd8eb22559406"),
            ("majorana_certificate_p2/majorana_p2_runner.jl", 33888,
             "03edd9640bc3d83a61ea0c9c7d9e93af3fc683972c517af4a7691e21359e25ed"),
            ("majorana_certificate_p3/majorana_p3_runner.jl", 59318,
             "958de8886bb8e56cda26eb6c45029c7016e886caae26c598c7e6b5c595257fe2"),
            ("majorana_certificate_p4/majorana_p4_runner.jl", 24880,
             "f425dbab80d60c49fceefc2b3e805fd3a4b29037f0e95491c50891ed7b7b9f47"),
            ("majorana_certificate_p6/majorana_p6_runner.jl", 74471,
             "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"),
            ("majorana_certificate_p2_fixture.json", 5891,
             "252fa0c4ed26db5581bcd9ff0101d18d858faf6d31fb9b6cdcaa821bf318e82a"),
            ("majorana_certificate_p3_fixture.json", 6033,
             "a478b783ae4005f7ef79572a4b34eee72299da262e439bdc35eca13496bdc236"),
            ("majorana_certificate_p4_fixture.json", 17259,
             "b020b6bcc0ed56010af9ed3b1836469c084b9244a9303a8101cf7657adb79964"),
            ("majorana_certificate_p5_fixture.json", 4763,
             "fd8b46c8761f548d615042b24f8ec85b32891e4f42dbafdd9bd70d58379a8afb"),
            ("majorana_certificate_p6_fixture.json", 14267,
             "fb381c613d675551d33680484a88870020a494e4a356dafd9fd869714c9d475d"),
            ("majorana_certificate_p7_design_probe_fixture.json", 20111,
             "d81af9a8e49e283c63a33b6af71f164497fe77a507f6dbfe4db7339d43fb52b2"),
            (
                "majorana_certificate_p7_design_probe/"
                "majorana_p7_step3_resource_probe.jl",
                33680,
                "12b3883309e64e49baa6b05c9d42ef6b311fa3c692daeccb90ab52849845723c",
            ),
            ("majorana_certificate_p7_d1_phase_probe_fixture.json", 11336,
             "b8f83bb8f5fc08cbdfa048c67a0fbd7f854371aded9dfb17a4432c0a057ca2cb"),
            (
                "majorana_certificate_p7_d1_phase_probe/"
                "majorana_p7_step3_phase_probe.jl",
                20058,
                "aee3eb4d87b5b2b847185b1c0bb162fc6f65963de10e76edf7b534ba7e03cb4c",
            ),
        )
        expected_manifest = [
            {
                "relative_path": relative,
                "repository_sha256": digest,
                "staged_size_bytes": size,
                "staged_sha256": digest,
                "byte_identical_to_repository": True,
            }
            for relative, size, digest in expected_sources
        ]
        self.assertEqual(len(expected_manifest), 15)
        self.assertEqual(self.report["staging_manifest"], expected_manifest)
        self.assertEqual(
            D1.canonical_sha256(expected_manifest),
            self.report["staging_manifest_sha256"],
        )

        pins = D1._source_pins(self.policy)
        self.assertEqual(len(pins), 19)
        self.assertEqual(set(pins), set(D1.SOURCE_PATHS))
        self.assertEqual(pins["majorana_certificate_p7_d1_phase_probe.py"], {
            "relative_path": "majorana_certificate_p7_d1_phase_probe.py",
            "size_bytes": 55630,
            "sha256": (
                "bfb9dedd7fe5efa24f4421a6b5b07d2f4d90c60efc912d25669736499ab43cbd"
            ),
        })
        self.assertEqual(
            pins["test_majorana_certificate_p7_d1_phase_probe.py"],
            {
                "relative_path": "test_majorana_certificate_p7_d1_phase_probe.py",
                "size_bytes": 18400,
                "sha256": (
                    "e8e58b55eeb127fdddb6d9dec0a075dcbabed25c66eaf141234dec5ad7734b4a"
                ),
            },
        )

    def test_candidate_and_exact_indeterminate_observation_are_frozen(self) -> None:
        self.assertEqual(self.report["candidate"], {
            "D1_diagnostic_mode": "E768_MAX_LAZY37_STEP3_D1_PHASE_V1",
            "D1_does_not_define_a_new_scientific_candidate": True,
            "algorithm_id": "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1",
            "candidate_id": "E768-MAX-LAZY37-STEP3-V1",
            "scientific_probe_mode": "E768_MAX_LAZY37_STEP3_V1",
        })
        expected_events = [
            (0, "D1_RUNNER_STARTED", 198650566),
            (1, "D1_INPUT_AND_RUNTIME_CUSTODY_VALIDATED", 32991838264),
            (2, "D1_STATIC_SETUP_COMPLETED", 35102795611),
            (3, "STEP1_ENGINE_STARTED", 35832014616),
            (4, "STEP1_ENGINE_RETURNED", 64460311537),
            (5, "STEP1_FINALIZER_STARTED", 64460314835),
            (6, "STEP1_FINALIZER_RETURNED", 65437886723),
            (7, "STEP1_TO_STEP2_HANDOFF_COMPLETED", 65569337108),
            (8, "STEP2_ENGINE_STARTED", 65869497654),
            (9, "STEP2_ENGINE_RETURNED", 657005582005),
            (10, "STEP2_FINALIZER_STARTED", 657026454714),
            (11, "STEP2_FINALIZER_RETURNED", 660275027765),
            (12, "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED", 660422891266),
            (13, "STEP2_TO_STEP3_HANDOFF_COMPLETED", 660560118161),
            (14, "STEP3_ENGINE_STARTED", 660589519616),
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
            "last_phase_event": "STEP3_ENGINE_STARTED",
            "outer_monotonic_elapsed_ns": 1800381352338,
            "outer_timeout_triggered": False,
            "phase_channel_bytes": 772,
            "phase_channel_eof": True,
            "phase_channel_sha256": (
                "7dd93f1e00e9432a7e3c47588db36c81c189ea8570215decabf08b3685bda106"
            ),
            "phase_event_count": 15,
            "phase_events": events,
            "phase_trace_protocol_sha256": (
                "15939fe745dc36fe3ce5a8f4ed6f2bb6e7dd4fb4075f880c3f6d7a62b239f67b"
            ),
            "phase_trace_status": "LEGAL_PREFIX_INTERRUPTED",
            "process_returncode": -15,
            "process_started": True,
            "resource_witness": None,
            "status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            "stderr_bytes": 3156,
            "stderr_sha256": (
                "4304ac93b4d76aec590e0564e2c32edc6851cb2ed7c3af424d4f986a58510e29"
            ),
            "stdout_bytes": 0,
            "stdout_sha256": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            "time_diagnostics": {},
        })
        wire = b"".join(
            D1.canonical_bytes({
                "event": row["event"], "sequence": row["sequence"],
            }) + b"\n"
            for row in events
        )
        protocol_rows = [
            {"sequence": row["sequence"], "event": row["event"]}
            for row in events
        ]
        self.assertEqual(len(wire), 772)
        self.assertEqual(
            hashlib.sha256(wire).hexdigest(),
            self.observation["phase_channel_sha256"],
        )
        self.assertEqual(
            D1.canonical_sha256(protocol_rows),
            self.observation["phase_trace_protocol_sha256"],
        )

    def test_trace_localizes_the_envelope_failure_to_step3_engine(self) -> None:
        events = self.observation["phase_events"]
        names = [row["event"] for row in events]
        elapsed = {
            row["event"]: row["outer_receive_elapsed_ns"] for row in events
        }
        self.assertEqual(names[-3:], [
            "P6_PREFIX_RESOURCE_CONFORMANCE_PASSED",
            "STEP2_TO_STEP3_HANDOFF_COMPLETED",
            "STEP3_ENGINE_STARTED",
        ])
        self.assertNotIn("STEP3_ENGINE_RETURNED", names)
        self.assertNotIn("STEP3_FINALIZER_STARTED", names)
        self.assertNotIn("STEP3_FINALIZER_RETURNED", names)
        matching = {
            branch
            for branch, sequence in self.fixture["phase_event_protocol"][
                "legal_terminal_sequences"
            ].items()
            if names == sequence[:len(names)]
        }
        self.assertEqual(
            matching, {"FULL_PATH_RETURNED", "STEP3_DETERMINISTIC_CAP"},
        )
        self.assertEqual(
            elapsed["STEP1_ENGINE_RETURNED"] - elapsed["STEP1_ENGINE_STARTED"],
            28628296921,
        )
        self.assertEqual(
            elapsed["STEP2_ENGINE_RETURNED"] - elapsed["STEP2_ENGINE_STARTED"],
            591136084351,
        )
        self.assertEqual(
            elapsed["P6_PREFIX_RESOURCE_CONFORMANCE_PASSED"], 660422891266,
        )
        self.assertEqual(elapsed["STEP3_ENGINE_STARTED"], 660589519616)
        self.assertEqual(
            self.observation["outer_monotonic_elapsed_ns"]
            - elapsed["STEP3_ENGINE_STARTED"],
            1139791832722,
        )

    def test_same_host_caps_do_not_establish_S0_admission(self) -> None:
        self.assertEqual(self.report["host_caps"], self.fixture[
            "host_supervisor_caps"
        ])
        self.assertEqual(self.report["host_caps"]["MemoryMax_bytes"], 2147483648)
        self.assertEqual(self.report["host_caps"]["MemorySwapMax_bytes"], 0)
        self.assertEqual(self.report["host_caps"]["RuntimeMaxSec"], "1800s")
        self.assertEqual(self.report["S0_admission"], {
            "D0_status_unchanged": (
                "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
            ),
            "derived_from_D1": False,
            "same_host_admission_as_D0": True,
            "status": "NOT_ESTABLISHED_BY_D1_PHASE_DIAGNOSTIC",
        })
        self.assertGreater(
            self.observation["outer_monotonic_elapsed_ns"], 1_800_000_000_000,
        )
        self.assertLess(
            self.observation["outer_monotonic_elapsed_ns"], 1_830_000_000_000,
        )

    def test_report_exposes_no_scientific_witness_or_result_fields(self) -> None:
        self.assertIsNone(self.observation["resource_witness"])
        D1.D0._reject_public_scientific_vocabulary(self.observation)
        self.assertEqual(self.report["authority_exclusions"], self.policy[
            "authority_exclusions"
        ])
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
        self.assertNotIn("stdout_content", seen_keys)
        self.assertNotIn("stderr_content", seen_keys)
        self.assertNotIn("phase_channel_content", seen_keys)
        for row in self.observation["phase_events"]:
            lowered = row["event"].lower()
            for fragment in (
                "tick", "budget", "mask", "coefficient", "digest", "neel",
                "term_count", "state", "observable",
            ):
                self.assertNotIn(fragment, lowered)

        claim = BASE / D1.EXECUTION_CLAIM_NAME
        self.assertFalse(claim.exists())
        self.assertFalse(claim.is_symlink())
        self.assertEqual(list(BASE.glob(f".{D1.REPORT_NAME}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
