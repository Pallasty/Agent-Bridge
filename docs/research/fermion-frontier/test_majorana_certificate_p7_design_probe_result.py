#!/usr/bin/env python3
"""Exact-result tests for the non-authoritative Majorana P7 D0 report."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parent
REPORT_SHA256 = "4bf4be7f77fd499ffc9bd975f07353fd14ee7403cd6fc7759974dda37f8588cf"
PREPROBE_COMMIT = "8cfbd7869b38e7e0d20f72e7550b59c845bfb43a"


def _load_probe():
    path = BASE / "majorana_certificate_p7_design_probe.py"
    spec = importlib.util.spec_from_file_location("majorana_p7_d0_result", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P7 = _load_probe()


class MajoranaP7DesignProbeResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = BASE / P7.REPORT_NAME
        cls.report = P7.validate_report(P7.load_json(cls.report_path))
        cls.policy = P7.validate_policy(
            P7.load_json(BASE / P7.POLICY_NAME), require_report_absent=False,
        )
        cls.fixture = P7._validate_fixture(
            P7.load_json(BASE / P7.FIXTURE_NAME)
        )
        cls.observation = cls.report["observations"][0]

    def test_report_hash_canonical_identity_and_authority_are_exact(self) -> None:
        self.assertEqual(P7.file_sha256(self.report_path), REPORT_SHA256)
        self.assertEqual(
            self.report_path.read_bytes(),
            P7.canonical_bytes(self.report) + b"\n",
        )
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["report_type"],
            "majorana_p7_step3_e768_max_lazy37_resource_report_d0_v1",
        )
        self.assertEqual(
            self.report["policy_id"],
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D0-V1",
        )
        self.assertEqual(
            self.report["fixture_id"],
            "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D0-V1",
        )
        self.assertEqual(self.report["scientific_authority"], "NONE")
        self.assertFalse(self.report["certificate_eligible"])
        self.assertEqual(
            self.report["formal_candidate_was_frozen_before_probe"],
            "E768-MAX-LAZY37-STEP3-V1",
        )

    def test_preprobe_policy_and_fixture_custody_are_exact(self) -> None:
        self.assertEqual(self.report["preprobe_commit_sha"], PREPROBE_COMMIT)
        P7._validate_preprobe_commit_identity(PREPROBE_COMMIT)
        self.assertEqual(
            self.report["policy_sha256"],
            "895e27cc30ee60d7f02877c8e4fa26258785fce5c640873f6319fa10b9ac564e",
        )
        self.assertEqual(
            self.report["fixture_sha256"],
            "d81af9a8e49e283c63a33b6af71f164497fe77a507f6dbfe4db7339d43fb52b2",
        )
        self.assertEqual(
            self.report["fixture_canonical_sha256"],
            "eddf6de4f36c142dfc6d725b128c3be5bab4dd2be38fb2d0a2a0143240ca82bb",
        )
        self.assertEqual(
            self.report["staging_manifest_sha256"],
            "531060a4480501f8f547e4106a941cd36dc3813971ef41a186ae467f333e7231",
        )

    def test_thirteen_staged_and_fourteen_pinned_source_rows_are_exact(self) -> None:
        expected_sources = (
            (
                "majorana_certificate_p0/Project.toml", 235,
                "62810ce02db16bf25cb74941f27f58ee556ee0826abc4aa47296ce8188a5048f",
            ),
            (
                "majorana_certificate_p0/Manifest.toml", 15336,
                "987572a908176b21cfbe80c385acdd0b4ab47b6c6dcd3ea9a33dd8eb22559406",
            ),
            (
                "majorana_certificate_p2/majorana_p2_runner.jl", 33888,
                "03edd9640bc3d83a61ea0c9c7d9e93af3fc683972c517af4a7691e21359e25ed",
            ),
            (
                "majorana_certificate_p3/majorana_p3_runner.jl", 59318,
                "958de8886bb8e56cda26eb6c45029c7016e886caae26c598c7e6b5c595257fe2",
            ),
            (
                "majorana_certificate_p4/majorana_p4_runner.jl", 24880,
                "f425dbab80d60c49fceefc2b3e805fd3a4b29037f0e95491c50891ed7b7b9f47",
            ),
            (
                "majorana_certificate_p6/majorana_p6_runner.jl", 74471,
                "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c",
            ),
            (
                "majorana_certificate_p2_fixture.json", 5891,
                "252fa0c4ed26db5581bcd9ff0101d18d858faf6d31fb9b6cdcaa821bf318e82a",
            ),
            (
                "majorana_certificate_p3_fixture.json", 6033,
                "a478b783ae4005f7ef79572a4b34eee72299da262e439bdc35eca13496bdc236",
            ),
            (
                "majorana_certificate_p4_fixture.json", 17259,
                "b020b6bcc0ed56010af9ed3b1836469c084b9244a9303a8101cf7657adb79964",
            ),
            (
                "majorana_certificate_p5_fixture.json", 4763,
                "fd8b46c8761f548d615042b24f8ec85b32891e4f42dbafdd9bd70d58379a8afb",
            ),
            (
                "majorana_certificate_p6_fixture.json", 14267,
                "fb381c613d675551d33680484a88870020a494e4a356dafd9fd869714c9d475d",
            ),
            (
                "majorana_certificate_p7_design_probe_fixture.json", 20111,
                "d81af9a8e49e283c63a33b6af71f164497fe77a507f6dbfe4db7339d43fb52b2",
            ),
            (
                "majorana_certificate_p7_design_probe/"
                "majorana_p7_step3_resource_probe.jl", 33680,
                "12b3883309e64e49baa6b05c9d42ef6b311fa3c692daeccb90ab52849845723c",
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
        self.assertEqual(len(expected_manifest), 13)
        self.assertEqual(self.report["staging_manifest"], expected_manifest)
        self.assertEqual(
            P7.canonical_sha256(expected_manifest),
            self.report["staging_manifest_sha256"],
        )

        pins = P7._source_pins(self.policy)
        self.assertEqual(len(pins), 14)
        self.assertEqual(set(P7.STAGED_PATHS), set(pins) - {
            "majorana_certificate_p7_design_probe.py",
        })
        orchestrator = pins["majorana_certificate_p7_design_probe.py"]
        self.assertEqual(orchestrator, {
            "relative_path": "majorana_certificate_p7_design_probe.py",
            "size_bytes": 88555,
            "sha256": (
                "fbd6aefeffac3f7bfa83da42d25d1f59f2a35fd71c2a6ecd0b0cd227b51df568"
            ),
        })

    def test_sole_observation_is_the_exact_indeterminate_terminal(self) -> None:
        self.assertEqual(len(self.report["observations"]), 1)
        self.assertEqual(self.observation, {
            "candidate_id": "E768-MAX-LAZY37-STEP3-V1",
            "host_failure_has_no_mathematical_authority": True,
            "outer_monotonic_elapsed_ns": 1800604540675,
            "outer_timeout_triggered": False,
            "probe_mode": "E768_MAX_LAZY37_STEP3_V1",
            "process_returncode": -15,
            "resource_witness": None,
            "status": "INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
            "stderr_bytes": 4041,
            "stderr_sha256": (
                "121d12aca3ff132c2d13aa31160e5b5e3b1423186bc2bfd9f375e8ebaeaa5199"
            ),
            "stdout_bytes": 0,
            "stdout_sha256": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            "time_diagnostics": {},
        })
        self.assertGreater(
            self.observation["outer_monotonic_elapsed_ns"], 1_800_000_000_000,
        )
        self.assertLess(
            self.observation["outer_monotonic_elapsed_ns"], 1_830_000_000_000,
        )
        self.assertNotIn("resource_witness_sha256", self.observation)

    def test_host_caps_and_nonestablished_fixed_admission_are_exact(self) -> None:
        expected_host = {
            "D0_and_future_S0_use_the_same_memory_swap_and_runtime_admission":
                True,
            "MemoryMax_bytes": 2147483648,
            "MemorySwapMax_bytes": 0,
            "RuntimeMaxSec": "1800s",
            "caps_cannot_be_relaxed_in_place_after_a_failure": True,
            "fresh_writable_scratch_and_depot_prefix_per_process": True,
            "host_caps_are_fixed_before_P7_D0_and_are_not_derived_from_"
            "observations": True,
            "host_failure_has_no_mathematical_resource_no_go_or_candidate_"
            "selection_authority": True,
            "host_timeout_OOM_cgroup_supervisor_environment_or_sandbox_failure_"
            "branch": "INDETERMINATE",
            "maximum_stderr_bytes": 1048576,
            "maximum_stdout_bytes": 1048576,
            "network_PID_and_private_proc_namespace_isolation": (
                "not_required_for_this_non_authoritative_D0_resource_probe_but_"
                "required_again_for_future_S0"
            ),
            "outer_safety_timeout_seconds": 1830,
            "systemd_user_scope_cgroup_v2_required": True,
        }
        self.assertEqual(self.report["host_caps"], expected_host)
        admission = self.report["fixed_formal_admission"]
        self.assertEqual(set(admission), {
            "status", "formal_step3_caps", "formal_step3_selection_caps",
            "formal_host_caps", "derived_from_observation",
            "same_as_D0_admission",
        })
        self.assertEqual(
            admission["status"],
            "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE",
        )
        self.assertEqual(admission["formal_host_caps"], expected_host)
        self.assertEqual(
            admission["formal_step3_caps"],
            self.fixture["deterministic_step3_probe_caps"],
        )
        self.assertEqual(
            admission["formal_step3_selection_caps"],
            self.fixture["deterministic_step3_selection_probe_caps"],
        )
        self.assertFalse(admission["derived_from_observation"])
        self.assertTrue(admission["same_as_D0_admission"])
        self.assertEqual(
            admission,
            P7._fixed_formal_admission(self.observation, self.policy),
        )

    def test_indeterminate_report_exposes_no_scientific_witness_fields(self) -> None:
        self.assertIsNone(self.observation["resource_witness"])
        P7._reject_public_scientific_vocabulary(self.observation)
        forbidden_exact_keys = {
            "operator_error_ticks", "product_defect_ticks",
            "merge_defect_ticks", "drop_defect_ticks", "allocation_pass",
            "allocation_slack", "coefficient_bits", "mask_hex", "drop_rows",
            "term_stream_sha256", "checkerboard_Neel_exact_dyadic_center",
            "declared_expectation_interval", "candidate_winner",
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
        self.assertEqual(
            self.report["authority_exclusions"],
            self.policy["authority_exclusions"],
        )
        self.assertIn(
            "D0_complete_formal_finalizer_execution_and_its_public_resource_"
            "counts_have_no_scientific_authority",
            self.report["authority_exclusions"],
        )


if __name__ == "__main__":
    unittest.main()
