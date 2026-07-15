#!/usr/bin/env python3
"""Exact-result and fail-closed tests for the formal Majorana P1 certificate."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "majorana_certificate_p1_checker_result",
    BASE / "majorana_certificate_p1_checker.py",
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)

PRECOMMIT_COMMIT = "0b3e766814442c1f4186335b50d19f78c043e527"
PARENT_COMMIT = "87a47403bb84a52cdbe5c741cf8e14d5f7204bb1"
WITNESS_SHA256 = "12b01c0aa89d71107f9acc5e4866f0b2998a84783aa1e255c9f462ac2a13b7f5"
TRANSCRIPT_SHA256 = "8b0b1cc063adf5914c78cfbb2a88721c9623ec90a47dab087ea21c124c3badb7"
REPLAY_PACKAGE_SHA256 = "e1161b9cb6c49144f56ea5fe4c1963beeb1a7974d18ea01c02a1f264ff37cff2"
STAGING_MANIFEST_SHA256 = "510a8bfe09c140ac94418c21186326d43967632a9ec07b91bfb7c1386f01b393"
STAGING_TREE_SHA256 = "8dbf0db16f0566bb90c6511b2e6a23741db1899e919d2fea05e638cc4580d61b"
RESULT_CONTRACT_SHA256 = "73c5e423b7ed5d234b5be4f78a107843e0d29365791c9475373971f7f88714b4"
CERTIFICATE_SHA256 = "368be66beac326d8d409550c95731eb02fcb756bb3bfc396b20376d45af99e34"

EXPECTED_CLAIMS = (
    "pinned_Julia_1.11.9_MajoranaPropagation_0.3.0_and_PauliPropagation_0.7.3_runtime_and_loaded_source_custody",
    "fixed_L2_L3_square_OBC_Hubbard_operator_term_and_candidate_action_conformance",
    "L2_all_1179648_bra_ket_entries_evaluated_by_upstream_overlapwithfock",
    "L3_all_11534336_operator_ket_candidate_actions_evaluated_at_term_derived_support",
    "sorted_certificate_wrapper_R2_apply_merge_truncate_execution_probe_conformance",
    "omitted_identity_phase_exponents_8_and_18_accounted_as_fixture_conventions",
    "two_fresh_network_isolated_processes_produced_byte_identical_canonical_transcripts",
)
EXPECTED_EXCLUSIONS = (
    "upstream_native_unsorted_FermionicRotation_execution_order",
    "L3_outside_candidate_support_entries_individually_executed",
    "L8_full_propagation",
    "1152_gate_or_100_mapped_step_workload",
    "product_formula_to_exact_Hubbard_error",
    "exact_time_evolution",
    "paper_figure_parameter_or_convergence_reproduction",
    "arbitrary_lattice_constructor_circuit_or_product_formula_generalization",
    "physical_reference_qualification",
    "READY",
)


class MajoranaP1FormalResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = CHECKER.validate_fixture(
            CHECKER.load_json(BASE / CHECKER.FIXTURE_NAME)
        )
        cls.runtime_lock = CHECKER.validate_runtime_lock(
            CHECKER.load_json(BASE / CHECKER.RUNTIME_LOCK_NAME)
        )
        cls.precommit = CHECKER.load_json(BASE / CHECKER.PRECOMMIT_CONTRACT_NAME)
        cls.result = CHECKER.load_json(BASE / CHECKER.RESULT_CONTRACT_NAME)
        cls.certificate = CHECKER.load_json(BASE / CHECKER.CERTIFICATE_NAME)
        cls.repo = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=BASE,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        cls.base_relative = BASE.resolve().relative_to(cls.repo.resolve())

        # Run the complete final verifier once.  The wrapper records, but does
        # not replace, the independently generated exact-CAR oracle object so
        # later adversarial cases need not repeat its expensive enumeration.
        oracle_objects: list[object] = []
        real_expected_witness = CHECKER.expected_witness

        def record_oracle(*args: object, **kwargs: object) -> object:
            expected = real_expected_witness(*args, **kwargs)
            oracle_objects.append(expected)
            return expected

        with mock.patch.object(
            CHECKER, "expected_witness", side_effect=record_oracle
        ):
            cls.final_summary = CHECKER.verify_final()
        if len(oracle_objects) != 1:
            raise AssertionError("formal verifier did not invoke the independent oracle once")
        cls.independent_expected = oracle_objects[0]

    @classmethod
    def _reconstruct_committed_staging(cls) -> tuple[dict[str, object], str]:
        rows_by_path = {
            row["relative_path"]: row for row in cls.precommit["source_files"]
        }
        paths = sorted([*rows_by_path, cls.precommit["self_relative_path"]])
        manifest_rows: list[dict[str, object]] = []
        tree_rows: list[dict[str, object]] = []
        for relative in paths:
            repo_relative = (cls.base_relative / relative).as_posix()
            listing = subprocess.run(
                ["git", "ls-tree", "-z", PRECOMMIT_COMMIT, "--", repo_relative],
                cwd=cls.repo,
                check=True,
                capture_output=True,
            ).stdout
            records = [record for record in listing.split(b"\0") if record]
            if len(records) != 1:
                raise AssertionError(f"ambiguous committed input: {repo_relative}")
            metadata, encoded_path = records[0].split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            if (
                encoded_path.decode("utf-8") != repo_relative
                or mode != "100644"
                or object_type != "blob"
            ):
                raise AssertionError(f"non-regular committed input: {repo_relative}")
            body = subprocess.run(
                ["git", "cat-file", "blob", object_id],
                cwd=cls.repo,
                check=True,
                capture_output=True,
            ).stdout
            digest = hashlib.sha256(body).hexdigest()
            if relative in rows_by_path:
                pin = rows_by_path[relative]
                if (
                    mode != pin["mode"]
                    or len(body) != pin["size_bytes"]
                    or digest != pin["sha256"]
                ):
                    raise AssertionError(f"committed source pin mismatch: {relative}")
            elif body != (BASE / CHECKER.PRECOMMIT_CONTRACT_NAME).read_bytes():
                raise AssertionError("committed precommit contract differs from active bytes")
            manifest_rows.append(
                {
                    "relative_path": repo_relative,
                    "git_mode": mode,
                    "git_blob": object_id,
                    "size_bytes": len(body),
                    "sha256": digest,
                }
            )
            tree_rows.append(
                {"path": repo_relative, "size": len(body), "sha256": digest}
            )
        manifest: dict[str, object] = {
            "files": manifest_rows,
            "files_sha256": CHECKER.canonical_sha256(manifest_rows),
            "file_count": len(manifest_rows),
        }
        return manifest, CHECKER.canonical_sha256(tree_rows)

    def _assert_final_rejects(
        self,
        mutate_result: object | None = None,
        mutate_certificate: object | None = None,
    ) -> None:
        result = copy.deepcopy(self.result)
        certificate = copy.deepcopy(self.certificate)
        if mutate_result is not None:
            mutate_result(result)
        if mutate_certificate is not None:
            mutate_certificate(certificate)
        real_load_json = CHECKER.load_json

        def substituted_load(path: Path) -> object:
            name = Path(path).name
            if name == CHECKER.RESULT_CONTRACT_NAME:
                return result
            if name == CHECKER.CERTIFICATE_NAME:
                return certificate
            return real_load_json(path)

        # The real independent oracle was exercised in setUpClass and is
        # checked directly below.  Bypass only that repeated enumeration here.
        with (
            mock.patch.object(CHECKER, "load_json", side_effect=substituted_load),
            mock.patch.object(
                CHECKER, "validate_witness", side_effect=lambda witness, *_: witness
            ),
            self.assertRaises((CHECKER.SchemaError, CHECKER.VerificationError)),
        ):
            CHECKER.verify_final()

    def test_01_formal_result_verifier_accepts_the_complete_closure(self) -> None:
        self.assertEqual(
            self.final_summary,
            {
                "status": CHECKER.MAXIMUM_STATUS,
                "precommit_commit_sha": PRECOMMIT_COMMIT,
                "canonical_witness_sha256": WITNESS_SHA256,
                "result_contract_sha256": RESULT_CONTRACT_SHA256,
                "certificate_sha256": CERTIFICATE_SHA256,
                "policy_id": "MAJORANA-P1-S0",
                "required_parent_commit": PARENT_COMMIT,
            },
        )

    def test_02_commit_witness_transcript_replay_and_staging_pins_are_exact(self) -> None:
        self.assertEqual(self.result["precommit_commit_sha"], PRECOMMIT_COMMIT)
        self.assertEqual(self.precommit["required_parent_commit"], PARENT_COMMIT)
        parent = subprocess.run(
            ["git", "show", "-s", "--format=%P", PRECOMMIT_COMMIT],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(parent, PARENT_COMMIT)
        self.assertEqual(self.result["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(
            self.result["transcript_sha256_in_order"],
            [TRANSCRIPT_SHA256, TRANSCRIPT_SHA256],
        )
        self.assertEqual(self.result["replay_package_sha256"], REPLAY_PACKAGE_SHA256)
        self.assertEqual(
            self.result["staging_manifest_sha256"], STAGING_MANIFEST_SHA256
        )
        self.assertEqual(self.result["staging_tree_sha256"], STAGING_TREE_SHA256)
        witness_bytes = CHECKER.canonical_bytes(self.result["witness"])
        self.assertEqual(hashlib.sha256(witness_bytes).hexdigest(), WITNESS_SHA256)
        self.assertEqual(
            hashlib.sha256(witness_bytes + b"\n").hexdigest(), TRANSCRIPT_SHA256
        )

    def test_03_l2_l3_counts_and_scope_are_exact(self) -> None:
        profiles = {
            row["profile_id"]: row for row in self.result["witness"]["profiles"]
        }
        expected_counts = {
            "L2_OBC": {
                "linear_size": 2,
                "n_sites": 4,
                "n_modes": 8,
                "basis_dimension": 256,
                "operator_instance_count": 18,
                "occupation_action_column_count": 4608,
                "logical_dense_matrix_entry_count": 1179648,
                "explicit_dense_matrix_entry_count": 1179648,
                "support_candidate_entry_count": 4608,
                "algebraically_implied_outside_support_zero_entry_count": 0,
                "action_nonzero_output_count": 2153,
                "dense_matrix_enumeration": True,
                "unique_composite_count": 12,
                "unique_constituent_count": 28,
                "unique_truncation_boundary_count": 20,
            },
            "L3_OBC": {
                "linear_size": 3,
                "n_sites": 9,
                "n_modes": 18,
                "basis_dimension": 262144,
                "operator_instance_count": 44,
                "occupation_action_column_count": 11534336,
                "logical_dense_matrix_entry_count": 3023656976384,
                "explicit_dense_matrix_entry_count": 0,
                "support_candidate_entry_count": 11534336,
                "algebraically_implied_outside_support_zero_entry_count": 3023645442048,
                "action_nonzero_output_count": 5371185,
                "dense_matrix_enumeration": False,
                "unique_composite_count": 33,
                "unique_constituent_count": 75,
                "unique_truncation_boundary_count": 51,
            },
        }
        self.assertEqual(set(profiles), set(expected_counts))
        for profile_id, expected in expected_counts.items():
            for field, value in expected.items():
                self.assertEqual(profiles[profile_id][field], value, (profile_id, field))
        self.assertEqual(
            self.result["witness"]["aggregate"],
            {
                "campaign_observable_instance_count": 4,
                "explicit_dense_matrix_entry_count": 1179648,
                "hubbard_generator_instance_count": 45,
                "local_Sz_observable_instance_count": 13,
                "occupation_action_column_count": 11538944,
                "operator_instance_count": 62,
                "profile_count": 2,
                "profiles_sha256": "56ca2e8afef7e7e887ff4e45936676796c6e9beab9ac3c9269a720e848f23aaa",
                "r2_composite_occurrence_count": 180,
                "r2_constituent_occurrence_count": 412,
                "r2_truncation_boundary_count": 284,
            },
        )
        scope = self.result["scope"]
        self.assertEqual(scope, self.result["witness"]["scope"])
        self.assertTrue(scope["fixed_L2_L3_square_OBC_Hubbard_workload_only"])
        self.assertTrue(scope["L2_all_bra_ket_dense_entries_verified"])
        self.assertTrue(scope["L3_all_ket_sparse_candidate_actions_verified"])
        self.assertFalse(scope["L3_outside_support_entries_individually_executed"])
        self.assertEqual(scope["L8_full_propagation"], "NOT_ASSESSED")
        self.assertEqual(scope["exact_time_evolution"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_04_sorted_cadence_execution_probes_and_r2_counts_are_exact(self) -> None:
        cadence_count = 0
        r2_totals = [0, 0, 0]
        for profile in self.result["witness"]["profiles"]:
            profile_cadence_count = 0
            for operator in profile["operator_records"]:
                cadence = operator["cadence"]
                if cadence is None:
                    continue
                cadence_count += 1
                profile_cadence_count += 1
                probe = cadence["execution_probe"]
                masks = [row["mask"] for row in cadence["constituents"]]
                self.assertEqual(masks, sorted(masks))
                self.assertEqual(probe["applied_masks"], masks)
                self.assertEqual(
                    probe["applied_masks_sha256"], CHECKER.canonical_sha256(masks)
                )
                boundaries = probe["observed_boundaries"]
                self.assertEqual(
                    probe["observed_truncation_call_count"],
                    cadence["truncation_boundary_count"],
                )
                self.assertEqual(len(boundaries), cadence["truncation_boundary_count"])
                self.assertEqual(
                    probe["observed_boundaries_sha256"],
                    CHECKER.canonical_sha256(boundaries),
                )
                self.assertEqual(
                    cadence["execution_probe_sha256"], CHECKER.canonical_sha256(probe)
                )
                self.assertEqual(
                    probe["wrapper_id"],
                    "sorted_zero_angle_identity_truncation_callback_v1",
                )
                self.assertEqual(probe["final_identity_coefficient"], "1")
                self.assertTrue(
                    all(row["identity_callback_delta"] == 1 for row in boundaries)
                )
                if operator["symbol"] == "nupndn":
                    self.assertTrue(cadence["truncate_after_each_constituent"])
                    self.assertEqual(
                        [row["after_constituent_index"] for row in boundaries],
                        list(range(len(masks))),
                    )
                else:
                    self.assertFalse(cadence["truncate_after_each_constituent"])
                    self.assertEqual(len(boundaries), 1)
                    self.assertIsNone(boundaries[0]["after_constituent_index"])
            self.assertEqual(profile_cadence_count, profile["unique_composite_count"])
            r2 = profile["r2_cadence"]
            self.assertEqual(r2["group_order"], list(CHECKER.GROUP_ORDER))
            self.assertEqual(r2["trotter_steps"], 2)
            r2_totals[0] += r2["composite_occurrence_count"]
            r2_totals[1] += r2["constituent_occurrence_count"]
            r2_totals[2] += r2["truncation_boundary_count"]
        self.assertEqual(cadence_count, 45)
        self.assertEqual(r2_totals, [180, 412, 284])

    def test_05_git_blobs_reconstruct_manifest_tree_and_replay_package(self) -> None:
        manifest, tree_sha256 = self._reconstruct_committed_staging()
        self.assertEqual(manifest["file_count"], 10)
        self.assertEqual(CHECKER.canonical_sha256(manifest), STAGING_MANIFEST_SHA256)
        self.assertEqual(tree_sha256, STAGING_TREE_SHA256)
        replay_package = {
            "schema_version": 1,
            "package_type": "majorana_p1_formal_fresh_replay_package_v1",
            "precommit_commit_sha": self.result["precommit_commit_sha"],
            "precommit_contract_sha256": self.result[
                "precommit_contract_sha256"
            ],
            "staging_manifest": manifest,
            "staging_tree_sha256": tree_sha256,
            "depot_custody": self.result["depot_custody"],
            "network_isolation": self.result["network_isolation"],
            "fresh_process_count": self.result["fresh_process_count"],
            "stdout_byte_identical": self.result["stdout_byte_identical"],
            "transcript_sha256_in_order": self.result[
                "transcript_sha256_in_order"
            ],
            "canonical_witness_sha256": self.result[
                "canonical_witness_sha256"
            ],
            "witness": self.result["witness"],
            "status": self.result["status"],
        }
        replay_sha256 = hashlib.sha256(
            CHECKER.canonical_bytes(replay_package) + b"\n"
        ).hexdigest()
        self.assertEqual(replay_sha256, REPLAY_PACKAGE_SHA256)

    def test_06_all_result_artifacts_are_absent_from_the_precommit(self) -> None:
        self.assertEqual(
            tuple(self.precommit["result_artifacts_required_absent"]),
            CHECKER.RESULT_ARTIFACTS,
        )
        for artifact in CHECKER.RESULT_ARTIFACTS:
            repo_relative = (self.base_relative / artifact).as_posix()
            absent = subprocess.run(
                ["git", "cat-file", "-e", f"{PRECOMMIT_COMMIT}:{repo_relative}"],
                cwd=self.repo,
                capture_output=True,
            )
            self.assertNotEqual(absent.returncode, 0, artifact)

    def test_07_certificate_exact_claims_exclusions_and_hash_dag_are_closed(self) -> None:
        self.assertEqual(tuple(CHECKER.CERTIFICATE_CLAIMS), EXPECTED_CLAIMS)
        self.assertEqual(tuple(CHECKER.CERTIFICATE_EXCLUSIONS), EXPECTED_EXCLUSIONS)
        self.assertEqual(tuple(self.certificate["claims"]), EXPECTED_CLAIMS)
        self.assertEqual(
            tuple(self.certificate["explicit_exclusions"]), EXPECTED_EXCLUSIONS
        )
        self.assertEqual(
            self.certificate["authority"],
            "fixed_L2_L3_square_OBC_Hubbard_fixture_subcertificate_only",
        )
        self.assertIs(self.certificate["ready_gate_eligible"], False)
        self.assertEqual(
            self.certificate["result_contract_sha256"], RESULT_CONTRACT_SHA256
        )
        self.assertEqual(
            CHECKER.file_sha256(BASE / CHECKER.RESULT_CONTRACT_NAME),
            RESULT_CONTRACT_SHA256,
        )
        self.assertEqual(
            CHECKER.file_sha256(BASE / CHECKER.CERTIFICATE_NAME), CERTIFICATE_SHA256
        )
        expected_hashes = {
            "precommit_commit_sha": PRECOMMIT_COMMIT,
            "policy_sha256": "64b1afb6790172b705f4be06c659fdc33909fb0741f9954f10dc70c83516e561",
            "runtime_lock_sha256": "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17",
            "fixture_sha256": "49924e42549d1cb7bbafd27b80effd2fc3610c08c554b326934676790a1b4a6c",
            "runner_sha256": "54cda433aac87676fbae1f5a27259eeba472232997f9762553f0fab2b995823f",
            "checker_sha256": "4325ce276e8bdf91ab511444b90f47c39bad9b7f33ae8df027b21eea00c4bfd0",
            "canonical_witness_sha256": WITNESS_SHA256,
        }
        for field, expected in expected_hashes.items():
            self.assertEqual(self.certificate[field], expected, field)

    def test_08_result_matches_the_independent_exact_car_oracle(self) -> None:
        self.assertEqual(
            CHECKER.canonical_bytes(self.result["witness"]),
            CHECKER.canonical_bytes(self.independent_expected),
        )
        with mock.patch.object(
            CHECKER, "expected_witness", return_value=self.independent_expected
        ):
            CHECKER.validate_witness(
                self.result["witness"], self.fixture, self.runtime_lock
            )
            mutant = copy.deepcopy(self.result["witness"])
            mutant["profiles"][0]["basis_dimension"] = True
            with self.assertRaises(CHECKER.VerificationError):
                CHECKER.validate_witness(mutant, self.fixture, self.runtime_lock)

    def test_09_result_and_certificate_mutations_fail_closed(self) -> None:
        zero_sha = "0" * 64
        cases = (
            (
                "transcript no longer binds witness stdout",
                lambda result: result.__setitem__(
                    "transcript_sha256_in_order", [zero_sha, zero_sha]
                ),
                None,
            ),
            (
                "replay package digest",
                lambda result: result.__setitem__("replay_package_sha256", zero_sha),
                None,
            ),
            (
                "staging manifest digest",
                lambda result: result.__setitem__(
                    "staging_manifest_sha256", zero_sha
                ),
                None,
            ),
            (
                "staging tree digest",
                lambda result: result.__setitem__("staging_tree_sha256", zero_sha),
                None,
            ),
            (
                "precommit commit",
                lambda result: result.__setitem__("precommit_commit_sha", "0" * 40),
                None,
            ),
            (
                "depot custody closure",
                lambda result: result["depot_custody"]["MajoranaPropagation"].__setitem__(
                    "closure_sha256", zero_sha
                ),
                None,
            ),
            (
                "network namespace",
                lambda result: result.__setitem__("network_isolation", "host_network"),
                None,
            ),
            (
                "bool accepted as process integer",
                lambda result: result.__setitem__("fresh_process_count", True),
                None,
            ),
            (
                "integer accepted as stdout bool",
                lambda result: result.__setitem__("stdout_byte_identical", 1),
                None,
            ),
            (
                "result scope expansion",
                lambda result: result["scope"].__setitem__(
                    "ready_gate_eligible", True
                ),
                None,
            ),
            (
                "certificate claim expansion",
                None,
                lambda certificate: certificate["claims"].append(
                    "upstream_native_execution_order_verified"
                ),
            ),
            (
                "certificate exclusion contraction",
                None,
                lambda certificate: certificate["explicit_exclusions"].pop(),
            ),
            (
                "certificate checker hash DAG",
                None,
                lambda certificate: certificate.__setitem__(
                    "checker_sha256", zero_sha
                ),
            ),
            (
                "integer accepted as certificate READY bool",
                None,
                lambda certificate: certificate.__setitem__(
                    "ready_gate_eligible", 0
                ),
            ),
        )
        for label, mutate_result, mutate_certificate in cases:
            with self.subTest(label=label):
                self._assert_final_rejects(mutate_result, mutate_certificate)


if __name__ == "__main__":
    unittest.main()
