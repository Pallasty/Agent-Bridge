#!/usr/bin/env python3
"""Exact-result tests for the formal Majorana P0 subcertificate."""

from __future__ import annotations

import copy
from fractions import Fraction
import importlib.util
from pathlib import Path
import subprocess
import unittest


BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "majorana_certificate_p0_checker_result",
    BASE / "majorana_certificate_p0_checker.py",
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class MajoranaP0FormalResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = CHECKER.validate_fixture(
            CHECKER.load_json(BASE / CHECKER.FIXTURE_NAME)
        )
        cls.runtime_lock = CHECKER.validate_runtime_lock(
            CHECKER.load_json(BASE / CHECKER.RUNTIME_LOCK_NAME)
        )
        cls.contract = CHECKER.load_json(BASE / CHECKER.RESULT_CONTRACT_NAME)
        cls.certificate = CHECKER.load_json(BASE / CHECKER.CERTIFICATE_NAME)

    def test_01_formal_result_verifier_accepts_the_complete_closure(self) -> None:
        summary = CHECKER.verify_final()
        self.assertEqual(summary["status"], CHECKER.MAXIMUM_STATUS)
        self.assertEqual(
            summary["canonical_witness_sha256"],
            "b06a7a16bc6697b92e6d3fa05a33089a2437195d5d12133346b68438177d13f8",
        )

    def test_02_result_binds_the_pushed_result_unpinned_commit(self) -> None:
        commit = self.contract["precommit_commit_sha"]
        self.assertEqual(commit, "c6050be2fcc0beb1454465aa77240f6b1f88c71b")
        repo = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=BASE,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        parent = subprocess.run(
            ["git", "show", "-s", "--format=%P", commit],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(parent, "fc9cf278876d2f053cda707f0aa529cdc8001c50")
        for artifact in CHECKER.RESULT_ARTIFACTS:
            absent = subprocess.run(
                ["git", "cat-file", "-e", f"{commit}:docs/research/fermion-frontier/{artifact}"],
                cwd=repo,
                capture_output=True,
            )
            self.assertNotEqual(absent.returncode, 0)

    def test_03_two_fresh_transcripts_are_byte_identical(self) -> None:
        transcripts = self.contract["transcript_sha256_in_order"]
        self.assertEqual(
            transcripts,
            [
                "ff7a6f420e9ddadcba32df575c6b9e653a1ef703b3299b5a95e3b51442f5344c",
                "ff7a6f420e9ddadcba32df575c6b9e653a1ef703b3299b5a95e3b51442f5344c",
            ],
        )
        self.assertTrue(self.contract["stdout_byte_identical"])
        self.assertEqual(self.contract["fresh_process_count"], 2)
        self.assertEqual(
            self.contract["network_isolation"],
            "bubblewrap_unshared_network_namespace",
        )

    def test_04_replay_package_and_git_object_staging_are_pinned(self) -> None:
        self.assertEqual(
            self.contract["replay_package_sha256"],
            "49c18950666bc5299d752521e8dc534fdb90e4c0006976352fe39d516e690ad6",
        )
        self.assertEqual(
            self.contract["staging_manifest_sha256"],
            "fa7b5c060da63e676bc866984bbba058762e5becef550cc9eb6f636114f0aa6a",
        )
        self.assertEqual(
            self.contract["staging_tree_sha256"],
            "cbe57fb7b87ede2add4d2fbe849391012d19d36554b3ac8d6f4440f17d54c04c",
        )

    def test_05_runtime_and_loaded_source_custody_match(self) -> None:
        witness = self.contract["witness"]
        self.assertEqual(witness["runtime"]["julia_version"], "1.11.9")
        self.assertEqual(witness["runtime"]["threads"], 1)
        self.assertEqual(
            witness["upstream"]["majorana_source_closure"]["closure_sha256"],
            "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5",
        )
        self.assertEqual(
            witness["upstream"]["pauli_source_closure"]["closure_sha256"],
            "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783",
        )
        self.assertEqual(
            self.contract["depot_custody"]["MajoranaPropagation"]["closure_sha256"],
            witness["upstream"]["majorana_source_closure"]["closure_sha256"],
        )

    def test_06_exhaustive_small_algebra_and_rotation_counts_are_exact(self) -> None:
        witness = self.contract["witness"]
        self.assertEqual(witness["primitive_algebra"]["pair_count"], 4096)
        self.assertEqual(witness["primitive_rotations"]["case_count"], 17856)
        self.assertEqual(
            witness["primitive_algebra"]["records_sha256"],
            "d793d40af68726c7e096c5575ee5067952c2765feb2a984d889afa451fc13cc8",
        )
        self.assertEqual(
            witness["primitive_rotations"]["records_sha256"],
            "a589c6b951d5d91192f765fa7b65ea13269407ea9b21fe8e3fd1d2b0646434b0",
        )

    def test_07_composite_ledger_and_expectation_are_exact(self) -> None:
        composite = self.contract["witness"]["composite"]
        self.assertEqual(len(composite["ledger_events"]), 5)
        self.assertEqual(len(composite["final_retained_terms"]), 26)
        self.assertEqual(
            composite["ledger_events_sha256"],
            "6b31e669c1bee45f3494415c081e535b8bd3f8035b61620aa249265566909cad",
        )
        self.assertEqual(
            composite["final_retained_terms_sha256"],
            "9e363f9e7ac7fad0a2a26a17f74c2b1b043ba19f4707cd0d0178e81aef790acc",
        )
        self.assertEqual(
            composite["cumulative_dropped_l1"],
            "45769830242595739/1152921504606846976",
        )
        retained = composite["retained_expectation_interval"]
        declared = composite["declared_circuit_expectation_interval"]
        self.assertEqual(
            retained,
            {
                "lower": "276704759118530155/4611686018427387904",
                "upper": "1106819036474125325/18446744073709551616",
            },
        )
        self.assertEqual(
            declared,
            {
                "lower": "93625438148147199/4611686018427387904",
                "upper": "1839136320355657149/18446744073709551616",
            },
        )
        exact_jw_diagnostic = Fraction("0.05879284133454183")
        self.assertLessEqual(CHECKER.parse_q(declared["lower"]), exact_jw_diagnostic)
        self.assertGreaterEqual(CHECKER.parse_q(declared["upper"]), exact_jw_diagnostic)

    def test_08_result_is_recomputed_by_the_independent_python_oracle(self) -> None:
        CHECKER.validate_witness(
            self.contract["witness"], self.fixture, self.runtime_lock
        )
        mutant = copy.deepcopy(self.contract["witness"])
        mutant["primitive_algebra"]["pair_count"] -= 1
        with self.assertRaises(CHECKER.VerificationError):
            CHECKER.validate_witness(mutant, self.fixture, self.runtime_lock)

    def test_09_certificate_hash_dag_is_closed(self) -> None:
        self.assertEqual(
            self.certificate["result_contract_sha256"],
            CHECKER.file_sha256(BASE / CHECKER.RESULT_CONTRACT_NAME),
        )
        self.assertEqual(
            self.certificate["canonical_witness_sha256"],
            self.contract["canonical_witness_sha256"],
        )
        self.assertEqual(
            self.certificate["checker_sha256"],
            CHECKER.file_sha256(BASE / "majorana_certificate_p0_checker.py"),
        )

    def test_10_authority_ceiling_remains_fixture_specific_and_fail_closed(self) -> None:
        scope = self.contract["scope"]
        self.assertEqual(self.certificate["authority"], "fixed_small_fixture_subcertificate_only")
        self.assertTrue(scope["small_fixture_conformance_only"])
        self.assertEqual(scope["L8_full_propagation"], "NOT_ASSESSED")
        self.assertEqual(
            scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED"
        )
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])
        self.assertFalse(self.certificate["ready_gate_eligible"])
        self.assertIn("L8_full_propagation", self.certificate["explicit_exclusions"])
        self.assertIn("physical_reference_qualification", self.certificate["explicit_exclusions"])


if __name__ == "__main__":
    unittest.main()
