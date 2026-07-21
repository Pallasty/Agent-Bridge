#!/usr/bin/env python3
"""Precommit and adversarial tests for the result-unpinned Majorana P2 route."""

from __future__ import annotations

import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent


def _load_checker():
    path = BASE / "majorana_certificate_p2_checker.py"
    spec = importlib.util.spec_from_file_location("majorana_p2_checker_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P2 = _load_checker()


class MajoranaP2PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = P2.load_json(BASE / P2.FIXTURE_NAME)
        cls.policy = P2.load_json(BASE / P2.POLICY_NAME)
        cls.runtime_lock = P2.load_json(BASE / P2.RUNTIME_LOCK_NAME)
        cls.precommit = P2.load_json(BASE / P2.PRECOMMIT_CONTRACT_NAME)
        cls.schedule = P2.expected_schedule()

    def test_fixture_is_exact_and_result_unpinned(self) -> None:
        self.assertEqual(P2.validate_fixture(self.fixture)["schema_version"], 1)
        self.assertEqual(P2.canonical_sha256(self.fixture), P2.FIXTURE_CANONICAL_SHA256)
        encoded = P2.canonical_bytes(self.fixture)
        for forbidden in (
            b"observed_final_term_count",
            b"observed_peak_term_count",
            b"observed_final_expansion_sha256",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_policy_is_exact_and_has_no_result_keys(self) -> None:
        P2.validate_policy(self.policy, self.runtime_lock)
        self.assertEqual(P2.canonical_sha256(self.policy), P2.POLICY_CANONICAL_SHA256)
        encoded = P2.canonical_bytes(self.policy)
        for forbidden in self.policy["forbidden_formal_result_pins"]:
            self.assertNotIn(f'"{forbidden}":'.encode(), encoded)

    def test_precommit_contract_pins_every_input(self) -> None:
        validated = P2.validate_precommit_contract(self.precommit)
        self.assertEqual(
            tuple(row["relative_path"] for row in validated["source_files"]),
            P2.PRECOMMIT_SOURCE_PATHS,
        )

    def test_result_artifacts_are_absent(self) -> None:
        result_path = BASE / P2.RESULT_CONTRACT_NAME
        if not result_path.exists():
            for artifact in P2.RESULT_ARTIFACTS:
                self.assertFalse((BASE / artifact).exists(), artifact)
            return

        result = P2.load_json(result_path)
        precommit_commit = result["precommit_commit_sha"]
        repo = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=BASE,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout.decode().strip()
        ).resolve()
        base_relative = BASE.resolve().relative_to(repo)
        for artifact in P2.RESULT_ARTIFACTS:
            relative = (base_relative / artifact).as_posix()
            probe = subprocess.run(
                ["git", "cat-file", "-e", f"{precommit_commit}:{relative}"],
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(probe.returncode, 0, artifact)

    def test_verify_precommit_closes_parent_and_static_oracle(self) -> None:
        result_paths = {(BASE / name).resolve() for name in P2.RESULT_ARTIFACTS}
        original_exists = Path.exists

        def precommit_phase_exists(path: Path) -> bool:
            if path.resolve() in result_paths:
                return False
            return original_exists(path)

        if any(original_exists(path) for path in result_paths):
            with mock.patch.object(Path, "exists", new=precommit_phase_exists):
                summary = P2.verify_precommit()
        else:
            summary = P2.verify_precommit()
        self.assertEqual(summary["scope_ceiling"], P2.MAXIMUM_STATUS)
        self.assertEqual(summary["required_parent_commit"], P2.REQUIRED_PARENT_COMMIT)
        self.assertEqual(summary["required_parent_status"], P2.P1_STATUS)

    def test_schedule_exact_totals(self) -> None:
        self.assertEqual(self.schedule["stage_count"], 9)
        self.assertEqual(self.schedule["composite_count"], 512)
        self.assertEqual(self.schedule["constituent_count"], 1152)
        self.assertEqual(self.schedule["truncation_boundary_count"], 768)
        self.assertEqual(tuple(self.schedule["stage_groups"]), P2.STAGE_GROUPS)

    def test_stage_composite_partition(self) -> None:
        counts = []
        for stage_index in range(9):
            rows = [
                row for row in self.schedule["composites"] if row["stage_index"] == stage_index
            ]
            counts.append(len(rows))
        self.assertEqual(counts, [64, 48, 64, 48, 64, 48, 64, 48, 64])

    def test_constituent_and_boundary_partition(self) -> None:
        constituent_counts = [0] * 9
        boundary_counts = [0] * 9
        for composite in self.schedule["composites"]:
            stage = composite["stage_index"]
            constituent_counts[stage] += len(composite["constituents"])
            boundary_counts[stage] += sum(
                row["boundary_after"] for row in composite["constituents"]
            )
        self.assertEqual(constituent_counts, [128, 96, 192, 96, 128, 96, 192, 96, 128])
        self.assertEqual(boundary_counts, [64, 48, 192, 48, 64, 48, 192, 48, 64])

    def test_angle_histogram_and_binary64_bits(self) -> None:
        self.assertEqual(
            self.schedule["theta_histogram"],
            {
                "-1/100": 64,
                "-1/200": 320,
                "-1/50": 128,
                "1/100": 64,
                "1/200": 320,
                "1/50": 256,
            },
        )
        for composite in self.schedule["composites"]:
            for row in composite["constituents"]:
                value = float(Fraction(row["applied_angle"]))
                self.assertEqual(row["applied_angle_Float64_bits_hex"], struct.pack(">d", value).hex())

    def test_threshold_is_exact_binary64_and_strict(self) -> None:
        execution = self.fixture["execution_semantics"]
        epsilon = 2.0**-34
        self.assertEqual(struct.pack(">d", epsilon).hex(), "3dd0000000000000")
        self.assertEqual(execution["threshold_comparison"], "strict_less_than")
        self.assertEqual(Fraction(execution["threshold_rational"]), Fraction(1, 2**34))

    def test_every_stage_is_pairwise_commuting(self) -> None:
        for row in self.schedule["stage_commutation"]:
            self.assertTrue(row["all_pairs_commute"])
            self.assertEqual(
                row["unordered_pair_count"],
                row["generator_count"] * (row["generator_count"] - 1) // 2,
            )

    def test_h4_is_fused_but_raw_threshold_path_is_not_claimed_equal(self) -> None:
        self.assertTrue(self.schedule["central_H4_fused_before_execution"])
        self.assertTrue(
            self.schedule["raw_and_fused_exact_stage_unitary_equal_from_internal_commutation"]
        )
        self.assertFalse(self.schedule["raw_and_fused_threshold_paths_identical"])

    def test_heisenberg_reverses_composites_within_each_stage(self) -> None:
        first = self.schedule["composites"][0]
        last_forward = P2._forward_group_specs("H1")[-1]
        self.assertEqual(first["operator_id"], last_forward["operator_id"])
        self.assertEqual(first["occurrence_in_stage"], 0)

    def test_constituents_are_unsigned_mask_sorted(self) -> None:
        for composite in self.schedule["composites"]:
            masks = [int(row["mask_hex"], 16) for row in composite["constituents"]]
            self.assertEqual(masks, sorted(masks))
            self.assertEqual(len(masks), len(set(masks)))

    def test_l8_uses_high_UInt256_bits(self) -> None:
        masks = [
            int(row["mask_hex"], 16)
            for composite in self.schedule["composites"]
            for row in composite["constituents"]
        ]
        self.assertGreater(max(mask.bit_length() for mask in masks), 64)
        self.assertLessEqual(max(mask.bit_length() for mask in masks), 256)

    def test_initial_observable_has_128_nonzero_terms(self) -> None:
        expected = P2.expected_initial_observable()
        self.assertEqual(expected["nonzero_term_count"], 128)
        self.assertEqual(expected["initial_exact_zero_identity_prune_count"], 1)
        P2.require_sha256(expected["term_stream_sha256"], "initial digest")

    def test_neel_mask_has_one_particle_per_site(self) -> None:
        mask = int(P2._neel_mask_hex(), 16)
        self.assertEqual(mask.bit_count(), 64)
        up = down = 0
        for site0 in range(64):
            row, column = divmod(site0, 8)
            site = site0 + 1
            if mask & (1 << (4 * site - 4)):
                up += 1
                self.assertEqual((row + column) % 2, 0)
            if mask & (1 << (4 * site - 2)):
                down += 1
                self.assertEqual((row + column) % 2, 1)
        self.assertEqual((up, down), (32, 32))

    def test_caps_are_tight_and_preallocation_oriented(self) -> None:
        caps = self.fixture["deterministic_resource_caps"]
        self.assertEqual(caps["maximum_premerge_terms"], 2**16)
        self.assertEqual(caps["maximum_cap_scan_term_visits"], 2**25)
        self.assertEqual(caps["maximum_propagation_term_visits"], 2**25)
        self.assertEqual(caps["maximum_truncation_term_visits"], 2**24)
        self.assertEqual(caps["maximum_total_charged_term_visits"], 2**26)

    def test_host_caps_use_kernel_cgroup_not_sampled_RSS(self) -> None:
        host = self.fixture["host_supervisor_caps"]
        self.assertTrue(host["systemd_user_scope_cgroup_v2_required"])
        self.assertEqual(host["MemoryMax_bytes"], 2**32)
        self.assertEqual(host["RuntimeMaxSec"], "300s")
        self.assertNotIn("sampled", json.dumps(host).lower())

    def test_host_cap_failure_is_indeterminate(self) -> None:
        legal = {row["branch"]: row for row in self.policy["legal_terminal_branches"]}
        self.assertIn("timeout_OOM_RSS_host_environment_or_sandbox", legal["INDETERMINATE"]["authority"])
        self.assertIn("not_a_deterministic_policy_cap", json.dumps(self.policy["resource_enforcement"]))

    def test_status_map_has_narrow_cap_negative(self) -> None:
        self.assertEqual(P2._status_for_outcome("PREFIX_COMPLETED_UNDER_CAPS"), P2.MAXIMUM_STATUS)
        self.assertEqual(
            P2._status_for_outcome("DETERMINISTIC_POLICY_CAP_EXCEEDED"), P2.CAP_STATUS
        )
        with self.assertRaises(P2.VerificationError):
            P2._status_for_outcome("INDETERMINATE")

    def test_scope_excludes_accuracy_R100_reference_and_ready(self) -> None:
        scope = self.policy["scope_boundary"]
        self.assertEqual(scope["binary64_roundoff_or_coefficient_error"], "NOT_ASSESSED")
        self.assertEqual(scope["remaining_99_mapped_steps"], "NOT_ASSESSED")
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_scope_excludes_double_occupancy_raw_and_python_equality(self) -> None:
        scope = self.policy["scope_boundary"]
        self.assertEqual(scope["double_occupancy"], "NOT_ASSESSED")
        self.assertEqual(scope["raw_1280_constituent_threshold_path"], "NOT_EXECUTED")
        self.assertEqual(scope["existing_Python_eight_gate_topL1_route_result_equality"], "NOT_CLAIMED")

    def test_runner_uses_explicit_sorted_wrapper_and_callback(self) -> None:
        source = (BASE / P2.RUNNER_RELATIVE_PATH).read_text()
        self.assertIn("sort!(pairs; by=row -> row.rotation.ms_int)", source)
        self.assertIn("min_abs_coeff=0.0", source)
        self.assertIn("customtruncfunc=callback", source)
        self.assertIn("predicted_premerge", source)
        self.assertNotIn("applymergetruncate!", source)
        self.assertNotIn("propagate!", source)

    def test_runner_never_serializes_float_tokens(self) -> None:
        source = (BASE / P2.RUNNER_RELATIVE_PATH).read_text()
        self.assertNotIn("elseif value isa AbstractFloat", source)
        self.assertIn("Float64_diagnostic_bits_hex", source)

    def test_fixture_mutation_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.fixture)
        mutant["heisenberg_prefix"]["planned_constituent_count"] = 1151
        with self.assertRaises(P2.SchemaError):
            P2.validate_fixture(mutant)

    def test_policy_authority_mutation_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.policy)
        mutant["scope_boundary"]["ready_gate_eligible"] = True
        with self.assertRaises(P2.SchemaError):
            P2.validate_policy(mutant, self.runtime_lock)

    def test_precommit_hash_mutation_fails_closed(self) -> None:
        mutant = copy.deepcopy(self.precommit)
        mutant["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaises(P2.VerificationError):
            P2.validate_precommit_contract(mutant)

    def test_duplicate_and_float_json_are_rejected(self) -> None:
        with self.assertRaises(P2.SchemaError):
            P2.strict_json_loads(b'{"x":1,"x":2}', source="duplicate")
        with self.assertRaises(P2.SchemaError):
            P2.strict_json_loads(b'{"x":1.5}', source="float")

    def test_systemd_and_bubblewrap_are_available_for_formal_replay(self) -> None:
        self.assertIsNotNone(shutil.which("systemd-run"))
        self.assertIsNotNone(shutil.which("bwrap"))
        observed = subprocess.run(
            ["stat", "-fc", "%T", "/sys/fs/cgroup"],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        self.assertEqual(observed, b"cgroup2fs")

    def test_certificate_claims_remain_resource_only(self) -> None:
        joined = " ".join(P2.CERTIFICATE_CLAIMS).lower()
        excluded = " ".join(P2.CERTIFICATE_EXCLUSIONS).lower()
        self.assertNotIn("accuracy", joined)
        self.assertIn("accuracy", excluded)
        self.assertIn("ready", excluded)


if __name__ == "__main__":
    unittest.main()
