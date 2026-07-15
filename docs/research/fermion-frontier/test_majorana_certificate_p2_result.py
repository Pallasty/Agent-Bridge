#!/usr/bin/env python3
"""Exact-result regression tests for the committed Majorana P2 replay."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parent
RESULT_SHA256 = "36071d1648d35f831436623b2b36d30b5f72dd9dafcddb991ea6083e7e4f1813"
CERTIFICATE_SHA256 = "2b700d70c75392777d3f756d06199d6e416351f894a8a58bdb0e2a181ff10e09"
PRECOMMIT_SHA256 = "dfa35363930c895f1baae9e117bc347f57d5ace95bdc0061863ba973c4f663fa"
CHECKER_SHA256 = "a495134b32545715ea9dd8044096d54ce477ba25ad1feca7d28034239cb11611"
RUNNER_SHA256 = "03edd9640bc3d83a61ea0c9c7d9e93af3fc683972c517af4a7691e21359e25ed"
FIXTURE_SHA256 = "252fa0c4ed26db5581bcd9ff0101d18d858faf6d31fb9b6cdcaa821bf318e82a"
POLICY_SHA256 = "255845f0e835dbfaf57dbda10bde3d0dd4fbfe0fd2564caf19a60a11e90752c9"
WITNESS_SHA256 = "ca382cd7cd8dd01dfcf7ea540809b32f89a5c512ce71484e76ed7e409cb7ae03"
TRANSCRIPT_SHA256 = "cf18113b82fd0348d2ae271630e59a67a1e9d73b3e09010f612cf89dbe09d0f5"
REPLAY_PACKAGE_SHA256 = "ada3465adcc9983e1f323778e3a826746986d6d272cdd19552b69e3bc6aa5325"
STAGING_MANIFEST_SHA256 = "81bc3689d038ed3bf7d5828fa52230106f81bef8d62dc9542036213d58bafaf0"
STAGING_TREE_SHA256 = "4e25ac066969b1623e82b149098e216127154207d6c1ac7a3dbc55534b960453"
FINAL_TERM_STREAM_SHA256 = "067f02a72d50f8061c746896d9eb02e3b60f7e5d6b42f21f0191b8e5887a9c9e"
TRANSITION_LEDGER_SHA256 = "9e9ee353993acf25b668cd22ccf20a9c221f805a63d384db715094cee30d25fd"
BOUNDARY_LEDGER_SHA256 = "20dfca26afcc4d41851e69deae7cabb3a2588212c5ed61235b454db5f4fd66d5"
STAGE_LEDGER_SHA256 = "76a55ef2aec9dc6fad74373bd9e94d9d55fd2aa5652bac54619ddac2624b1a1e"
PRECOMMIT_COMMIT = "65d0fe7778322b2bb83aabf65e7c12e989d73671"


def _load_checker():
    path = BASE / "majorana_certificate_p2_checker.py"
    spec = importlib.util.spec_from_file_location(
        "majorana_p2_checker_for_result_tests", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P2 = _load_checker()


class MajoranaP2ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = P2.load_json(BASE / P2.RESULT_CONTRACT_NAME)
        cls.certificate = P2.load_json(BASE / P2.CERTIFICATE_NAME)
        cls.witness = cls.result["witness"]
        cls.execution = cls.witness["execution"]
        cls.final_state = cls.witness["final_state"]

    def test_exact_artifact_hashes(self) -> None:
        expected = {
            P2.RESULT_CONTRACT_NAME: RESULT_SHA256,
            P2.CERTIFICATE_NAME: CERTIFICATE_SHA256,
            P2.PRECOMMIT_CONTRACT_NAME: PRECOMMIT_SHA256,
            P2.CHECKER_NAME: CHECKER_SHA256,
            P2.RUNNER_RELATIVE_PATH: RUNNER_SHA256,
            P2.FIXTURE_NAME: FIXTURE_SHA256,
            P2.POLICY_NAME: POLICY_SHA256,
        }
        for relative, digest in expected.items():
            self.assertEqual(P2.file_sha256(BASE / relative), digest, relative)

    def test_final_verifier_accepts_committed_result(self) -> None:
        summary = P2.verify_final()
        self.assertEqual(summary["status"], P2.MAXIMUM_STATUS)
        self.assertEqual(summary["terminal_branch"], "PREFIX_COMPLETED_UNDER_CAPS")
        self.assertEqual(summary["canonical_witness_sha256"], WITNESS_SHA256)

    def test_two_fresh_transcripts_are_byte_identical(self) -> None:
        self.assertTrue(self.result["stdout_byte_identical"])
        self.assertEqual(self.result["fresh_process_count"], 2)
        self.assertEqual(
            self.result["transcript_sha256_in_order"],
            [TRANSCRIPT_SHA256, TRANSCRIPT_SHA256],
        )
        self.assertEqual(self.result["canonical_witness_sha256"], WITNESS_SHA256)

    def test_replay_and_staging_custody_hashes(self) -> None:
        self.assertEqual(self.result["replay_package_sha256"], REPLAY_PACKAGE_SHA256)
        self.assertEqual(self.result["staging_manifest_sha256"], STAGING_MANIFEST_SHA256)
        self.assertEqual(self.result["staging_tree_sha256"], STAGING_TREE_SHA256)
        self.assertEqual(self.result["precommit_commit_sha"], PRECOMMIT_COMMIT)

    def test_kernel_host_caps_and_network_isolation(self) -> None:
        self.assertEqual(
            self.result["network_isolation"],
            "bubblewrap_unshared_network_namespace",
        )
        self.assertEqual(
            self.result["host_resource_enforcement"],
            {
                "cgroup_version": 2,
                "supervisor": "systemd_user_scope",
                "MemoryMax_bytes": 2**32,
                "RuntimeMaxSec": "300s",
                "observed_runtime_or_memory_peak_in_canonical_package": False,
            },
        )

    def test_full_one_step_schedule_completed(self) -> None:
        self.assertEqual(self.execution["completed_composite_count"], 512)
        self.assertEqual(self.execution["completed_constituent_count"], 1152)
        self.assertEqual(self.execution["completed_truncation_boundary_count"], 768)
        self.assertIsNone(self.execution["cap_event"])

    def test_observed_terms_remain_under_tight_caps(self) -> None:
        self.assertEqual(self.execution["peak_premerge_contribution_count"], 44_222)
        self.assertEqual(self.execution["peak_postmerge_unique_term_count"], 43_848)
        self.assertEqual(self.final_state["retained_term_count"], 42_704)
        caps = P2.load_json(BASE / P2.FIXTURE_NAME)["deterministic_resource_caps"]
        self.assertLess(
            self.execution["peak_premerge_contribution_count"],
            caps["maximum_premerge_terms"],
        )

    def test_exact_resource_visit_ledger(self) -> None:
        self.assertEqual(
            self.execution["counters"],
            {
                "cap_scan_term_visits": 15_113_342,
                "propagation_term_visits": 15_113_342,
                "truncation_term_visits": 9_989_760,
                "final_evaluation_term_visits": 42_704,
                "total_charged_term_visits": 40_259_148,
            },
        )
        self.assertEqual(self.execution["anticommuting_split_count"], 489_740)

    def test_threshold_drop_is_diagnostic_only(self) -> None:
        self.assertEqual(self.execution["threshold_dropped_term_count"], 328_956)
        self.assertEqual(self.execution["exact_zero_dropped_term_count"], 3_714)
        self.assertEqual(
            self.execution["cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex"],
            "3ead48fe92637265",
        )
        self.assertFalse(
            self.witness["scope"]["threshold_drop_is_a_certified_error_bound"]
        )

    def test_exact_ledger_and_final_state_digests(self) -> None:
        self.assertEqual(
            self.execution["transition_records_sha256"], TRANSITION_LEDGER_SHA256
        )
        self.assertEqual(
            self.execution["boundary_records_sha256"], BOUNDARY_LEDGER_SHA256
        )
        self.assertEqual(self.execution["stage_records_sha256"], STAGE_LEDGER_SHA256)
        self.assertEqual(self.final_state["term_stream_sha256"], FINAL_TERM_STREAM_SHA256)
        self.assertEqual(
            self.final_state[
                "checkerboard_Neel_expectation_Float64_diagnostic_bits_hex"
            ],
            "3feffa45912362b7",
        )
        self.assertTrue(
            self.final_state["expectation_is_diagnostic_not_scientific_authority"]
        )

    def test_certificate_has_only_resource_authority(self) -> None:
        self.assertEqual(self.certificate["status"], P2.MAXIMUM_STATUS)
        self.assertEqual(self.certificate["terminal_branch"], "PREFIX_COMPLETED_UNDER_CAPS")
        self.assertEqual(
            self.certificate["authority"],
            "fixed_L8_first_fused_mapped_step_Float64_execution_resource_feasibility_only",
        )
        self.assertFalse(self.certificate["ready_gate_eligible"])
        exclusions = " ".join(self.certificate["explicit_exclusions"])
        for token in ("accuracy", "full_R100", "exact_Hubbard", "READY"):
            self.assertIn(token, exclusions)

    def test_result_mutations_fail_closed(self) -> None:
        fixture = P2.validate_fixture(P2.load_json(BASE / P2.FIXTURE_NAME))
        runtime = P2.validate_runtime_lock(P2.load_json(BASE / P2.RUNTIME_LOCK_NAME))
        mutants = []
        peak = copy.deepcopy(self.witness)
        peak["execution"]["peak_premerge_contribution_count"] += 1
        mutants.append(peak)
        order = copy.deepcopy(self.witness)
        order["schedule"]["composites"][0]["constituents"].reverse()
        mutants.append(order)
        authority = copy.deepcopy(self.witness)
        authority["scope"]["ready_gate_eligible"] = True
        mutants.append(authority)
        counter = copy.deepcopy(self.witness)
        counter["execution"]["counters"]["total_charged_term_visits"] -= 1
        mutants.append(counter)
        for mutant in mutants:
            with self.assertRaises(P2.VerificationError):
                P2.validate_witness(mutant, fixture, runtime)


if __name__ == "__main__":
    unittest.main()
