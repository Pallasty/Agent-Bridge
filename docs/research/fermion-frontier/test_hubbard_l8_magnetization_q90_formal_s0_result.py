#!/usr/bin/env python3
"""Post-run result, provenance, tamper, and opt-in replay tests for M q90 S0."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
DIAGNOSTIC_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q90_transcript.json"
)


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_module(
    "hubbard_l8_magnetization_q90_formal_s0_checker_result_test",
    "hubbard_l8_magnetization_q90_formal_s0_checker.py",
)


def raw(filename: str) -> bytes:
    return (HERE / filename).read_bytes()


def load_json(filename: str):
    return CHECKER.strict_json_bytes(raw(filename), filename)


POLICY = load_json(CHECKER.POLICY_NAME)
PRECOMMIT_CONTRACT = load_json(CHECKER.PRECOMMIT_CONTRACT_NAME)
CONTRACT = load_json(CHECKER.FINAL_CONTRACT_NAME)
CERTIFICATE = load_json(CHECKER.CERTIFICATE_NAME)
DIAGNOSTIC = load_json(DIAGNOSTIC_NAME)
STAGING_MANIFEST = CERTIFICATE["witness_claim"]["execution_custody"][
    "allowlist_staging_manifest"
]


class MQ90FormalS0ResultTests(unittest.TestCase):
    def test_01_final_contract_binds_precommit_checker_policy_result_and_witness(self):
        self.assertEqual(
            CONTRACT["checker_source_sha256"],
            hashlib.sha256(raw(CHECKER.SELF_NAME)).hexdigest(),
        )
        self.assertEqual(
            CONTRACT["policy_file_sha256"],
            hashlib.sha256(raw(CHECKER.POLICY_NAME)).hexdigest(),
        )
        self.assertEqual(
            CONTRACT["precommit_contract_sha256"],
            hashlib.sha256(raw(CHECKER.PRECOMMIT_CONTRACT_NAME)).hexdigest(),
        )
        self.assertEqual(
            CHECKER.canonical_sha256(CERTIFICATE["witness_claim"]),
            CONTRACT["expected_witness_sha256"],
        )

    def test_02_precommit_commit_is_ancestor_and_lacks_all_result_artifacts(self):
        commit = CHECKER._verify_precommit_history(CONTRACT["precommit_commit_sha"])
        self.assertEqual(commit, "d3e58a62c1ca8c7c33512acfc3db141c329490fd")

    def test_03_post_only_diagnostic_bytes_match_fresh_result_digest(self):
        self.assertEqual(
            hashlib.sha256(raw(DIAGNOSTIC_NAME)).hexdigest(),
            CONTRACT["expected_fresh_replay_result_sha256"],
        )
        self.assertEqual(CONTRACT["expected_fresh_replay_result_sha256"],
                         "d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49")

    def test_04_post_only_surrogate_recomputes_the_stored_witness(self):
        recomputed = CHECKER._build_witness(DIAGNOSTIC, POLICY, STAGING_MANIFEST)
        self.assertEqual(recomputed, CERTIFICATE["witness_claim"])
        self.assertEqual(
            CHECKER.canonical_sha256(recomputed),
            "26d4996bc8977f8e9cfa0a62817166cd5b122a1355bdb455e77b9cd87382deda",
        )

    def test_05_exact_negative_branch_and_ledger_counts_are_bound(self):
        screen = CERTIFICATE["witness_claim"]["screen_result"]
        self.assertEqual(screen["terminal_branch"], "Q89_SUCCESS_Q90_FAILURE")
        self.assertEqual(screen["record_count"], 90)
        self.assertEqual(screen["selected_K_history_count"], 89)
        self.assertEqual(screen["candidate_row_count"], 3060)
        self.assertEqual(
            screen["checkpoint_ledger_sha256"],
            "8978329b712168dce39991af25f6903deaf69c45f236521bb0e08e74f3d8741f",
        )
        self.assertIsNone(screen["resource_policy_abort"])
        self.assertTrue(screen["scientific_negative_authority"])

    def test_06_q89_commit_and_q90_failure_details_are_exact(self):
        q89, q90 = CERTIFICATE["witness_claim"]["screen_result"][
            "q89_q90_record_summaries"
        ]
        self.assertEqual(q89["checkpoint_number_one_based"], 89)
        self.assertEqual(q89["selected_K"], 622592)
        self.assertEqual(q89["retained_expansion_count"], 622592)
        self.assertEqual(q90["checkpoint_number_one_based"], 90)
        self.assertEqual(q90["pretruncation_expansion_count"], 741376)
        self.assertEqual(q90["prefix_slack_before_selection_ticks"], "195203716260")
        self.assertEqual(q90["policy_max_K_candidate_drop_ticks"], "369541613084")
        self.assertEqual(q90["minimum_effective_K_diagnostic_only"], 635284)
        self.assertEqual(q90["required_K_excess_diagnostic_only"], 12692)

    def test_07_all_34_q90_candidate_rows_are_infeasible_and_max_K_exceeds_slack(self):
        screen = CERTIFICATE["witness_claim"]["screen_result"]
        rows = screen["terminal_failure_candidate_evaluations"]
        self.assertEqual(len(rows), 34)
        self.assertTrue(
            all(row["feasible_under_current_prefix_cap"] is False for row in rows)
        )
        self.assertEqual(rows[-1]["configured_K"], 622592)
        q90 = screen["q89_q90_record_summaries"][-1]
        self.assertGreater(
            int(rows[-1]["drop_ticks"]),
            int(q90["prefix_slack_before_selection_ticks"]),
        )

    def test_08_scope_remains_M3_without_child_M4_reference_or_READY(self):
        scope = CERTIFICATE["scope_claims"]
        decision = CERTIFICATE["witness_claim"]["decision"]
        self.assertEqual(scope["certified_mapped_depth"], 3)
        self.assertFalse(scope["M4_certified"])
        self.assertFalse(scope["child_boundary_transition_or_sidecar_generated"])
        self.assertFalse(scope["ready_gate_eligible"])
        self.assertEqual(
            scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED"
        )
        self.assertTrue(scope["retrospective_replication_only"])
        self.assertFalse(scope["prospective_discovery_authority"])
        self.assertFalse(decision["M4_certified"])

    def test_09_fast_final_verifier_accepts_post_only_exact_surrogate(self):
        with mock.patch.object(
            CHECKER,
            "_run_fresh_replay",
            return_value=(DIAGNOSTIC, STAGING_MANIFEST),
        ):
            result = CHECKER._verify_certificate_impl(
                CONTRACT, CERTIFICATE, PRECOMMIT_CONTRACT, POLICY
            )
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)

    def test_10_ledger_or_certificate_tamper_is_rejected(self):
        tampered_result = copy.deepcopy(DIAGNOSTIC)
        tampered_result["records"][-1]["candidate_records"][-1][
            "feasible_under_current_prefix_cap"
        ] = True
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._build_witness(tampered_result, POLICY, STAGING_MANIFEST)

        tampered_certificate = copy.deepcopy(CERTIFICATE)
        tampered_certificate["witness_claim"]["decision"]["M4_certified"] = True
        with mock.patch.object(
            CHECKER,
            "_run_fresh_replay",
            return_value=(DIAGNOSTIC, STAGING_MANIFEST),
        ):
            with self.assertRaises(CHECKER.VerificationError):
                CHECKER._verify_certificate_impl(
                    CONTRACT, tampered_certificate, PRECOMMIT_CONTRACT, POLICY
                )

    def test_11_runtime_RSS_timestamp_and_float_fields_are_not_in_witness(self):
        resource = CERTIFICATE["witness_claim"]["resource_summary"]
        self.assertFalse(resource["host_runtime_RSS_timestamp_or_float_fields_included"])
        encoded = json.dumps(CERTIFICATE["witness_claim"], sort_keys=True)
        for forbidden in ("wall_seconds", "peak_RSS_KiB", "host_timestamp"):
            self.assertNotIn(forbidden, encoded)

    def test_12_malformed_final_contract_fails_before_replay(self):
        malformed = copy.deepcopy(CONTRACT)
        malformed["checker_source_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "bad.json"
            path.write_text(json.dumps(malformed))
            result = subprocess.run(
                [
                    "python3",
                    str(HERE / CHECKER.SELF_NAME),
                    "--verify-final",
                    "--final-contract",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["verified"])

    @unittest.skipUnless(
        os.environ.get("RUN_M_Q90_FORMAL_S0_FULL") == "1",
        "set RUN_M_Q90_FORMAL_S0_FULL=1 for the ~14 minute isolated replay",
    )
    def test_99_full_public_certificate_replay(self):
        result = CHECKER.verify_certificate(
            CONTRACT, CERTIFICATE, PRECOMMIT_CONTRACT, POLICY
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)


if __name__ == "__main__":
    unittest.main()
