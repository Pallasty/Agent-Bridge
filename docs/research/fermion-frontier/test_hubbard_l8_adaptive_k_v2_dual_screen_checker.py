#!/usr/bin/env python3
"""Custody, policy, ledger, tamper, scope, and opt-in replay tests for the v2 screens."""

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


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_module(
    "hubbard_l8_adaptive_k_v2_dual_screen_checker",
    "hubbard_l8_adaptive_k_v2_dual_screen_checker.py",
)


def load_json(filename: str):
    return CHECKER.strict_json_bytes((HERE / filename).read_bytes(), filename)


CONTRACT = load_json(CHECKER.CONTRACT_NAME)
CERTIFICATE = load_json(CHECKER.CERTIFICATE_NAME)
POLICIES = {
    "magnetization": load_json("hubbard_l8_magnetization_adaptive_k_policy_v2.json"),
    "double_occupancy": load_json(
        "hubbard_l8_double_occupancy_adaptive_k_policy_v2.json"
    ),
}
TRANSCRIPTS = {
    "magnetization": load_json(
        "hubbard_l8_magnetization_adaptive_k_v2_design_transcript.json"
    ),
    "double_occupancy": load_json(
        "hubbard_l8_double_occupancy_adaptive_k_v2_design_transcript.json"
    ),
}


class AdaptiveKV2DualScreenTests(unittest.TestCase):
    def test_01_checker_contract_and_witness_sha_are_exact(self):
        checker_sha = hashlib.sha256((HERE / CHECKER.SELF_NAME).read_bytes()).hexdigest()
        self.assertEqual(
            checker_sha,
            "3a3fb88b52640b18ca96aa1afcf3bc9b2851bda51a217207b4ba03bd217d7ce8",
        )
        self.assertEqual(CONTRACT["checker_source_sha256"], checker_sha)
        witness_sha = CHECKER.canonical_sha256(CERTIFICATE["witness_claim"])
        self.assertEqual(
            witness_sha,
            "79f5cfeebfe87ea45af1c29eefe9b1468af0099d9cd3501dc732cbff0ca8fcf5",
        )
        self.assertEqual(CONTRACT["expected_witness_sha256"], witness_sha)

    def test_02_all_dependency_bytes_match_source_pins(self):
        self.assertEqual(len(CHECKER.SOURCE_PINS), CHECKER.RESOURCE_LIMITS["max_dependency_files"])
        for pin in CHECKER.SOURCE_PINS:
            observed = hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest()
            self.assertEqual(observed, pin["sha256"], pin["relative_path"])
        self.assertEqual(CONTRACT["source_pins"], list(CHECKER.SOURCE_PINS))

    def test_03_contract_and_certificate_fixed_fields_match_checker(self):
        self.assertEqual(CONTRACT["contract_fingerprint"], CHECKER.CONTRACT_FINGERPRINT)
        self.assertEqual(CONTRACT["maximum_positive_status"], CHECKER.MAXIMUM_POSITIVE_STATUS)
        self.assertEqual(CONTRACT["workload_identity"], CHECKER.WORKLOAD_IDENTITY)
        self.assertEqual(CONTRACT["screen_policy"], CHECKER.SCREEN_POLICY)
        self.assertEqual(CONTRACT["scope_claims"], CHECKER.SCOPE_CLAIMS)
        self.assertEqual(CERTIFICATE["certificate_type"], CHECKER.CERTIFICATE_TYPE)
        self.assertEqual(CERTIFICATE["workload_identity"], CHECKER.WORKLOAD_IDENTITY)
        self.assertEqual(CERTIFICATE["screen_policy"], CHECKER.SCREEN_POLICY)
        self.assertEqual(CERTIFICATE["scope_claims"], CHECKER.SCOPE_CLAIMS)

    def test_04_policy_canonical_semantics_are_exact(self):
        sources = CHECKER._read_pinned_sources()
        probe = CHECKER._compile_module(
            "probe_for_policy_test",
            CHECKER.SOURCE_PINS[0]["relative_path"],
            sources[CHECKER.SOURCE_PINS[0]["relative_path"]],
        )
        for mode, policy in POLICIES.items():
            self.assertEqual(
                CHECKER.canonical_sha256(policy),
                CHECKER.EXPECTED[mode]["policy_canonical_sha256"],
            )
            CHECKER._validate_policy(policy, mode, probe, sources)

    def test_05_verified_loader_uses_only_prehashed_module_bytes(self):
        sources = CHECKER._read_pinned_sources()
        probe = CHECKER._compile_module(
            "probe_for_loader_test",
            CHECKER.SOURCE_PINS[0]["relative_path"],
            sources[CHECKER.SOURCE_PINS[0]["relative_path"]],
        )
        CHECKER._install_verified_replay_loader(probe, sources)
        allowed = (
            "hubbard_l8_adaptive_k_arithmetic_v2.py",
            "hubbard_l8_observable_interval_step_checker.py",
            "hubbard_l8_magnetization_interval_step3_checker.py",
            "hubbard_l8_observable_interval_two_step_checker.py",
        )
        for filename in allowed:
            module = probe.load_module("ignored", HERE / filename)
            self.assertEqual(pathlib.Path(module.__file__).name, filename)
        for bad in (pathlib.Path("/tmp/evil.py"), "hubbard_l8_adaptive_k_arithmetic_v2.py"):
            with self.assertRaises(ValueError):
                probe.load_module("ignored", bad)

    def test_06_public_verifier_ignores_live_module_monkeypatch(self):
        forged = {"status": CHECKER.MAXIMUM_POSITIVE_STATUS, "verified": True}
        with mock.patch.object(CHECKER, "_verify_certificate_impl", return_value=forged):
            with self.assertRaises(ValueError):
                CHECKER.verify_certificate(CONTRACT, {})

    def test_07_stored_ledgers_recompute_budget_and_first_feasible(self):
        for mode in ("magnetization", "double_occupancy"):
            failure, candidates = CHECKER._validate_formal_records(
                mode, TRANSCRIPTS[mode], POLICIES[mode]
            )
            expected = CHECKER.EXPECTED[mode]
            self.assertEqual(
                failure["checkpoint_number_one_based"],
                expected["failure_checkpoint_number_one_based"],
            )
            self.assertTrue(
                all(item["feasible_under_current_prefix_cap"] is False for item in candidates)
            )

    def test_08_candidate_or_budget_tamper_is_rejected(self):
        tampered = copy.deepcopy(TRANSCRIPTS["double_occupancy"])
        tampered["records"][0]["candidate_records"][0]["drop_ticks"] = "0"
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._validate_formal_records(
                "double_occupancy", tampered, POLICIES["double_occupancy"]
            )
        tampered = copy.deepcopy(TRANSCRIPTS["magnetization"])
        tampered["records"][0]["budget_prefix_cap_ticks"] = "0"
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER._validate_formal_records(
                "magnetization", tampered, POLICIES["magnetization"]
            )

    def test_09_compact_route_witnesses_bind_exact_resources_and_no_child(self):
        stored = CERTIFICATE["witness_claim"]["screen_results"]
        self.assertEqual(len(stored), 2)
        for route in stored:
            mode = (
                "magnetization"
                if route["observable_id"] == "staggered_magnetization"
                else "double_occupancy"
            )
            expected = CHECKER.EXPECTED[mode]
            self.assertEqual(route["checkpoint_ledger_sha256"], expected["records_sha256"])
            self.assertEqual(route["failure_record_sha256"], expected["failure_record_sha256"])
            resources = route["resource_summary"]
            self.assertEqual(resources["peak_single_expansion_terms"], expected["peak"])
            self.assertEqual(resources["term_gate_visits_including_failure"], expected["visits"])
            self.assertEqual(
                resources["maximum_expansion_coefficient_tick_bits"],
                expected["coefficient_bits"],
            )
            self.assertEqual(resources["maximum_product_bits"], expected["product_bits"])
            self.assertEqual(
                resources["rounding_cumulative_scaled_ticks_squared"], expected["rounding"]
            )
            self.assertFalse(route["child_boundary_committed"])
            self.assertFalse(route["child_transition_committed"])
            self.assertFalse(route["positive_child_artifact_generated"])

    def test_10_design_transcript_is_provenance_not_result_authority(self):
        custody = CERTIFICATE["witness_claim"]["arithmetic_custody"]
        self.assertFalse(custody["design_transcript_records_parsed_or_used_as_result_input"])
        self.assertFalse(custody["root_new_step_arithmetic_helpers_used"])
        self.assertFalse(custody["root_globals_monkeypatched"])
        self.assertFalse(CHECKER.SCREEN_POLICY["formal_replay_uses_design_transcript_records"])

    def test_11_inner_contract_verification_rejects_witness_tamper_without_full_replay(self):
        with mock.patch.object(
            CHECKER, "recompute_witness", return_value=CERTIFICATE["witness_claim"]
        ):
            result = CHECKER._verify_certificate_impl(CONTRACT, CERTIFICATE)
            self.assertTrue(result["verified"])
            tampered = copy.deepcopy(CERTIFICATE)
            tampered["witness_claim"]["decision"][
                "magnetization_certified_mapped_depth"
            ] = 4
            with self.assertRaises(CHECKER.VerificationError):
                CHECKER._verify_certificate_impl(CONTRACT, tampered)

    def test_12_cli_malformed_contract_is_structured_fail_closed_exit_one(self):
        malformed = copy.deepcopy(CONTRACT)
        malformed["checker_source_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "bad.json"
            path.write_text(json.dumps(malformed))
            result = subprocess.run(
                [
                    "python3",
                    str(HERE / CHECKER.SELF_NAME),
                    "--contract",
                    str(path),
                    "--certificate",
                    str(HERE / CHECKER.CERTIFICATE_NAME),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "FAILED")
        self.assertFalse(payload["verified"])

    @unittest.skipUnless(
        os.environ.get("RUN_L8_ADAPTIVE_K_V2_FULL") == "1",
        "set RUN_L8_ADAPTIVE_K_V2_FULL=1 for the ~13 minute same-byte replay",
    )
    def test_99_full_public_replay(self):
        result = CHECKER.verify_certificate(CONTRACT, CERTIFICATE)
        self.assertEqual(result["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)
        self.assertTrue(result["verified"])
        self.assertEqual(
            result["expected_witness_sha256"], CONTRACT["expected_witness_sha256"]
        )


if __name__ == "__main__":
    unittest.main()
