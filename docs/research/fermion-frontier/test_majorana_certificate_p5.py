#!/usr/bin/env python3
"""Result-blind lifecycle and adversarial tests for Majorana P5 S0.

These tests exercise only frozen inputs, integer allocation logic, custody,
and lightweight independent oracles.  They do not launch a Julia replay or
materialize any P5 result artifact.
"""

from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent
REQUIRED_PARENT_COMMIT = "0265c7a4d726bf5b875247d0412e6a1d2f909973"
D0_POLICY_SHA256 = "e47ad24291f217b0b5d54ba6aa120c479d522bd23c74faf41b5bde6da2413aa2"
D0_REPORT_SHA256 = "602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5"
FIXTURE_CANONICAL_SHA256 = "bbac5a9281198ba87b336c6e45741d1468f85bb2997317943f1a45b6ac90de91"
POLICY_CANONICAL_SHA256 = "6fdce5556d5e226ece5b51608a1632bbc9120347ee4fbd9d757cba118862b4ff"
SIGNED_ZERO_STREAM_SHA256 = "323caca70bb0131db1ac554beaa99ffe4b4d9927ec448c83db5a9b11dd9d70c4"

RESULT_ARTIFACTS = (
    "majorana_certificate_p5_contract.json",
    "majorana_certificate_p5_certificate.json",
    "test_majorana_certificate_p5_result.py",
)

EXPECTED_STAGED_FILES = (
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4/majorana_p4_runner.jl",
    "majorana_certificate_p4_fixture.json",
    "majorana_certificate_p5/majorana_p5_runner.jl",
    "majorana_certificate_p5_fixture.json",
)

EXPECTED_STEP2_CAPS = {
    "maximum_step2_current_terms_before_constituent": 524288,
    "maximum_step2_premerge_terms": 524288,
    "maximum_step2_boundary_retained_terms": 524288,
    "maximum_step2_cap_scan_term_visits": 536870912,
    "maximum_step2_propagation_term_visits": 536870912,
    "maximum_step2_truncation_term_visits": 268435456,
    "maximum_step2_final_retained_terms": 524288,
    "maximum_step2_total_P2_charged_term_visits": 1073741824,
    "maximum_step2_anticommuting_events": 16777216,
    "maximum_step2_product_defect_events": 33554432,
    "maximum_step2_merge_defect_events": 4194304,
    "maximum_step2_drop_defect_events": 8388608,
    "maximum_step2_accuracy_charged_events": 33554432,
    "maximum_step2_total_P2_plus_accuracy_charged_events": 1073741824,
}

EXPECTED_BRANCHES = {
    "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE": (
        "VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K36_SELECTED_LOCAL_AND_"
        "CUMULATIVE_ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE"
    ),
    "K37_SELECTED_AFTER_K36_NOT_WITHIN_BOTH_ALLOCATIONS_AND_ALL_CANDIDATES_COMPLETE": (
        "VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K37_SELECTED_LOCAL_AND_"
        "CUMULATIVE_ERROR_BOUNDS_WITHIN_ALLOCATIONS_SUBCERTIFICATE"
    ),
    "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE": (
        "VERIFIED_MAJORANA_P5_L8_CONDITIONAL_STEP2_K36_K37_ERROR_BOUNDS_"
        "NO_SELECTION_SUBCERTIFICATE"
    ),
    "REQUIRED_CANDIDATE_DETERMINISTIC_POLICY_CAP_EXCEEDED": (
        "VERIFIED_MAJORANA_P5_L8_REQUIRED_THRESHOLD_CANDIDATE_POLICY_CAP_"
        "EXCEEDED_SUBCERTIFICATE"
    ),
    "FAILED_P3_POST_REPLAY_CONFORMANCE": (
        "FAILED_MAJORANA_P5_STEP1_P3_POST_REPLAY_CONFORMANCE"
    ),
    "INDETERMINATE": "INDETERMINATE_MAJORANA_P5_REPLAY",
    "INVALID_REPLAY": "INVALID_MAJORANA_P5_REPLAY",
}


def _load_checker():
    path = BASE / "majorana_certificate_p5_checker.py"
    spec = importlib.util.spec_from_file_location("majorana_p5_checker_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5 = _load_checker()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo() -> Path:
    return Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=BASE,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
    ).resolve()


def _next_power_of_two_at_least_twice(value: int) -> int:
    target = 2 * value
    return 1 << (target - 1).bit_length()


def _candidate_positive(local_ticks: int, parent_ticks: int, grid: int) -> bool:
    local = local_ticks * 400000 < grid
    cumulative = (parent_ticks + local_ticks) * 200000 < grid
    return local and cumulative


def _select(k36_positive: bool, k37_positive: bool) -> str:
    if k36_positive:
        return "K36"
    if k37_positive:
        return "K37"
    return "NONE"


class MajoranaP5PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = P5.load_json(BASE / P5.FIXTURE_NAME)
        cls.policy = P5.load_json(BASE / P5.POLICY_NAME)
        cls.runtime_lock = P5.load_json(BASE / P5.RUNTIME_LOCK_NAME)
        cls.d0_report = P5.load_json(BASE / P5.D0_REPORT_NAME)
        cls.parent_result = P5.load_json(BASE / P5.P3_RESULT_CONTRACT_NAME)
        cls.parent_ticks = int(
            cls.parent_result["witness"]["accuracy_ledger"][
                "total_operator_error_ticks"
            ]
        )

    def _precommit(self):
        path = BASE / P5.PRECOMMIT_CONTRACT_NAME
        self.assertTrue(path.is_file(), "P5 precommit contract is not materialized")
        return P5.load_json(path)

    def test_public_validators_accept_the_frozen_inputs(self) -> None:
        self.assertIs(P5.validate_fixture(self.fixture, BASE), self.fixture)
        self.assertIs(
            P5.validate_policy(self.policy, self.fixture, self.runtime_lock),
            self.policy,
        )
        self.assertEqual(self.fixture["fixture_id"], P5.FIXTURE_ID)
        self.assertEqual(self.policy["required_fixture_id"], P5.FIXTURE_ID)
        for name in (
            "validate_fixture",
            "validate_policy",
            "validate_precommit_contract",
            "verify_precommit",
        ):
            self.assertTrue(callable(getattr(P5, name, None)), name)

    def test_fixture_canonical_identity_and_runner_pin_are_exact(self) -> None:
        canonical = P5.canonical_bytes(self.fixture)
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), FIXTURE_CANONICAL_SHA256)
        self.assertEqual(P5.FIXTURE_CANONICAL_SHA256, FIXTURE_CANONICAL_SHA256)
        policy_canonical = P5.canonical_bytes(self.policy)
        self.assertEqual(
            hashlib.sha256(policy_canonical).hexdigest(), POLICY_CANONICAL_SHA256
        )
        self.assertEqual(P5.POLICY_CANONICAL_SHA256, POLICY_CANONICAL_SHA256)
        self.assertEqual(
            (BASE / P5.FIXTURE_NAME).read_bytes(), canonical + b"\n"
        )
        runner = (BASE / P5.RUNNER_RELATIVE_PATH).read_text()
        self.assertIn(FIXTURE_CANONICAL_SHA256, runner)
        self.assertIn(REQUIRED_PARENT_COMMIT, runner)

    def test_direct_design_parent_and_D0_custody_are_exact(self) -> None:
        parent = self.fixture["direct_design_parent"]
        self.assertEqual(parent["commit_sha"], REQUIRED_PARENT_COMMIT)
        self.assertEqual(parent["D0_policy_sha256"], D0_POLICY_SHA256)
        self.assertEqual(parent["D0_report_sha256"], D0_REPORT_SHA256)
        self.assertEqual(_sha256(BASE / P5.D0_POLICY_NAME), D0_POLICY_SHA256)
        self.assertEqual(_sha256(BASE / P5.D0_REPORT_NAME), D0_REPORT_SHA256)
        self.assertFalse(parent["D0_report_available_to_runner"])
        self.assertEqual(self.d0_report["scientific_authority"], "NONE")
        self.assertFalse(self.d0_report["certificate_eligible"])

    def test_candidate_matrix_and_common_step1_are_frozen(self) -> None:
        rows = self.fixture["candidate_thresholds"]
        self.assertEqual([row["candidate_id"] for row in rows], ["K36", "K37"])
        self.assertEqual([row["threshold_exponent"] for row in rows], [36, 37])
        self.assertEqual([row["fresh_process_count"] for row in rows], [2, 2])
        design = self.policy["conditional_candidate_design"]
        self.assertTrue(design["all_four_candidate_processes_must_complete_before_selection"])
        self.assertTrue(design["K36_completion_or_pass_does_not_permit_skipping_K37"])
        self.assertTrue(design["every_candidate_replay_starts_from_O0_in_a_fresh_process"])
        for row in design["candidates"]:
            self.assertEqual(row["step1_threshold_exponent"], 34)
            self.assertEqual(row["step1_threshold_Float64_bits_hex"], "3dd0000000000000")

    def test_D0_observations_derive_the_exact_common_formal_caps(self) -> None:
        observations = {
            row["step2_threshold_exponent"]: row
            for row in self.d0_report["observations"]
        }
        candidates = [observations[k]["resource_witness"]["step2"] for k in (36, 37)]
        maximum = lambda getter: max(getter(row) for row in candidates)
        derived = {
            "maximum_step2_current_terms_before_constituent": _next_power_of_two_at_least_twice(maximum(lambda row: row["peak_postmerge_unique_term_count"])),
            "maximum_step2_premerge_terms": _next_power_of_two_at_least_twice(maximum(lambda row: row["peak_premerge_contribution_count"])),
            "maximum_step2_boundary_retained_terms": _next_power_of_two_at_least_twice(maximum(lambda row: row["peak_postmerge_unique_term_count"])),
            "maximum_step2_cap_scan_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["cap_scan_term_visits"])),
            "maximum_step2_propagation_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["propagation_term_visits"])),
            "maximum_step2_truncation_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["truncation_term_visits"])),
            "maximum_step2_final_retained_terms": _next_power_of_two_at_least_twice(maximum(lambda row: row["final_retained_term_count"])),
            "maximum_step2_total_P2_charged_term_visits": _next_power_of_two_at_least_twice(maximum(lambda row: row["P2_resource_counters"]["total_charged_term_visits"])),
            "maximum_step2_anticommuting_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["anticommuting_event_count"])),
            "maximum_step2_product_defect_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["product_defect_event_count"])),
            "maximum_step2_merge_defect_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["merge_defect_event_count"])),
            "maximum_step2_drop_defect_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["drop_defect_event_count"])),
            "maximum_step2_accuracy_charged_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["accuracy_event_counters"]["accuracy_charged_event_count"])),
            "maximum_step2_total_P2_plus_accuracy_charged_events": _next_power_of_two_at_least_twice(maximum(lambda row: row["total_P2_plus_accuracy_charged_event_count"])),
        }
        self.assertEqual(derived, EXPECTED_STEP2_CAPS)
        fixture_caps = self.fixture["deterministic_resource_caps"]
        self.assertEqual({key: fixture_caps[key] for key in derived}, derived)

    def test_D0_boundary_cap_uses_the_precommitted_postmerge_observable(self) -> None:
        report = copy.deepcopy(self.d0_report)
        for row in report["observations"]:
            if row["step2_threshold_exponent"] in (36, 37):
                row["resource_witness"]["step2"]["final_retained_term_count"] = 1
        derived = P5._derive_step2_caps_from_d0(report)
        self.assertEqual(derived["maximum_boundary_retained_terms"], 524288)
        self.assertEqual(derived["maximum_current_terms_before_constituent"], 524288)
        self.assertEqual(derived["maximum_final_evaluation_term_visits"], 2)

    def test_resource_caps_are_common_and_the_host_envelope_is_frozen(self) -> None:
        _step1, step2, cumulative, trig = P5._resource_cap_sections(self.fixture, BASE)
        self.assertEqual(trig, 6)
        self.assertEqual(step2["maximum_premerge_terms"], 524288)
        self.assertEqual(step2["maximum_total_charged_term_visits"], 1073741824)
        self.assertEqual(cumulative["maximum_total_charged_term_visits"], 1140850688)
        host = self.fixture["host_supervisor_caps"]
        self.assertEqual(host["MemoryMax_bytes"], 4 * 1024**3)
        self.assertEqual(host["MemorySwapMax_bytes"], 0)
        self.assertEqual(host["RuntimeMaxSec"], "1200s")
        self.assertEqual(host["outer_safety_timeout_seconds"], 1230)

    def test_parent_E1_is_inherited_exactly_once_and_never_from_P4(self) -> None:
        parent = self.policy["parent_authority_and_telescoping"]
        self.assertEqual(parent["P3_E1_charge_multiplicity_per_candidate"], 1)
        self.assertTrue(parent["P4_E12_or_step2_error_is_not_inherited"])
        self.assertTrue(parent["parent_ticks_are_not_requantized_rounded_or_outward_widened_again"])
        local = 123456789
        self.assertEqual(self.parent_ticks + local, self.parent_ticks + local)
        self.assertNotEqual(2 * self.parent_ticks + local, self.parent_ticks + local)

    def test_strict_allocation_boundaries_and_impossible_truth_combination(self) -> None:
        grid = P5.GRID
        local_last_pass = (grid - 1) // 400000
        local_first_fail = (grid + 400000 - 1) // 400000
        cumulative_last_pass = (grid - 1) // 200000
        self.assertLess(local_last_pass * 400000, grid)
        self.assertGreaterEqual(local_first_fail * 400000, grid)
        self.assertTrue(_candidate_positive(local_last_pass, self.parent_ticks, grid))
        self.assertFalse(_candidate_positive(local_first_fail, self.parent_ticks, grid))
        self.assertLess(self.parent_ticks + local_last_pass, cumulative_last_pass)
        self.assertEqual(
            cumulative_last_pass - self.parent_ticks - local_last_pass,
            553719370910752292541903267624045,
        )

    def test_selector_truth_table_is_K36_priority_after_all_complete(self) -> None:
        self.assertEqual(_select(True, True), "K36")
        self.assertEqual(_select(True, False), "K36")
        self.assertEqual(_select(False, True), "K37")
        self.assertEqual(_select(False, False), "NONE")
        truth = self.policy["selection_and_terminal_truth_table"]
        self.assertTrue(truth["K36_is_selected_when_both_candidates_pass"])
        self.assertTrue(truth["smaller_observed_bound_does_not_override_frozen_K36_priority"])
        self.assertTrue(
            truth["a_required_candidate_cap_host_failure_invalid_replay_or_missing_replay_forbids_a_winner"]
        )

    def test_branch_status_map_is_exact_and_fail_closed(self) -> None:
        rows = self.policy["selection_and_terminal_truth_table"]["legal_terminal_branches"]
        actual = {row["branch"]: row["maximum_status"] for row in rows}
        self.assertEqual(actual, EXPECTED_BRANCHES)
        self.assertEqual(actual, P5._BRANCH_STATUS_DEFAULTS)
        precedence = self.policy["terminal_branch_precedence"]
        self.assertLess(
            precedence.index("host_or_generation_failure_to_INDETERMINATE"),
            precedence.index("complete_all_four_raw_candidate_replays"),
        )

    def test_certificate_authority_is_narrowed_for_every_materializable_branch(self) -> None:
        selected = {
            "terminal_branch": "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE",
            "witness": {"selected_candidate_id": "K36"},
        }
        authority, claims = P5._certificate_authority_and_claims(selected)
        self.assertIn("selected_conditional_K36", authority)
        self.assertIn("selected_candidate_passes_both_strict_allocations", claims)

        no_selection = {
            "terminal_branch": (
                "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE"
            ),
            "witness": {"selected_candidate_id": None},
        }
        authority, claims = P5._certificate_authority_and_claims(no_selection)
        self.assertIn("no_selection", authority)
        self.assertNotIn("selected_candidate_passes_both_strict_allocations", claims)

        cap = {
            "terminal_branch": "REQUIRED_CANDIDATE_DETERMINISTIC_POLICY_CAP_EXCEEDED",
            "witness": {"selected_candidate_id": None},
        }
        authority, claims = P5._certificate_authority_and_claims(cap)
        self.assertIn("resource_guard_event_only", authority)
        self.assertIn("P3_E1_not_inherited_on_the_cap_only_branch", claims)
        self.assertNotIn(
            "complete_fieldwise_conformance_of_each_candidate_step1_to_certified_P3",
            claims,
        )

        failed = {
            "terminal_branch": "FAILED_P3_POST_REPLAY_CONFORMANCE",
            "witness": {"selected_candidate_id": None},
        }
        authority, claims = P5._certificate_authority_and_claims(failed)
        self.assertIn("conformance_failed_without_E1_inheritance", authority)
        self.assertIn("P3_E1_not_inherited_after_conformance_failure", claims)

    def test_production_composer_implements_selector_and_single_E1_charge(self) -> None:
        parent_witness = {
            "accuracy_ledger": {
                "grid_denominator": str(P5.GRID),
                "total_operator_error_ticks": str(self.parent_ticks),
            }
        }
        parent_result = {
            "status": P5.P4.PARENT_STATUS,
            "terminal_branch": "P3_PARENT",
            "canonical_witness_sha256": "1" * 64,
        }
        authority = (
            {"report_type": "majorana_p5_conditional_step2_threshold_resource_report_d0_v1"},
            {"status": P5.P4.EXCEEDS_STATUS},
            parent_result,
            parent_witness,
        )
        first_local_fail = (P5.GRID + 400000 - 1) // 400000
        cases = (
            (0, 0, "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE", "K36"),
            (0, first_local_fail, "K36_SELECTED_AFTER_ALL_CANDIDATES_COMPLETE", "K36"),
            (
                first_local_fail,
                0,
                "K37_SELECTED_AFTER_K36_NOT_WITHIN_BOTH_ALLOCATIONS_AND_ALL_CANDIDATES_COMPLETE",
                "K37",
            ),
            (
                first_local_fail,
                first_local_fail,
                "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE",
                None,
            ),
        )

        for k36_ticks, k37_ticks, expected_branch, expected_selected in cases:
            raws = {}
            for candidate_id, local_ticks in (("K36", k36_ticks), ("K37", k37_ticks)):
                raws[candidate_id] = {
                    "candidate_marker": candidate_id,
                    "step1": {
                        "execution": {"cap_event": None},
                        "accuracy_ledger": {
                            "total_operator_error_ticks": str(self.parent_ticks)
                        },
                    },
                    "step2": {
                        "execution": {"cap_event": None},
                        "accuracy_ledger": {
                            "grid_denominator": str(P5.GRID),
                            "total_operator_error_ticks": str(local_ticks),
                            "product_defect_ticks": "0",
                            "merge_defect_ticks": "0",
                            "drop_defect_ticks": str(local_ticks),
                        },
                        "final_state": {"marker": candidate_id},
                    },
                    "candidate_local_allocation_pass": local_ticks * 400000 < P5.GRID,
                }
            with (
                mock.patch.object(P5, "_verify_design_parent_and_authority", return_value=authority),
                mock.patch.object(P5, "_step1_p3_projection", return_value=parent_witness),
                mock.patch.object(
                    P5,
                    "_authoritative_final_state",
                    side_effect=lambda state, ticks: {"marker": state["marker"], "ticks": ticks},
                ),
            ):
                witness = P5._compose_authoritative_witness(
                    raws, self.fixture, self.policy, BASE
                )
            with self.subTest(k36=k36_ticks, k37=k37_ticks):
                self.assertEqual(witness["terminal_branch"], expected_branch)
                self.assertEqual(witness["selected_candidate_id"], expected_selected)
                self.assertEqual(
                    witness["parent_P3_authority"][
                        "E1_charge_multiplicity_per_completed_candidate"
                    ],
                    1,
                )
                for row, local_ticks in zip(
                    witness["candidate_results"], (k36_ticks, k37_ticks)
                ):
                    ledger = row["telescoping_ledger"]
                    self.assertTrue(row["parent_P3_E1_inherited"])
                    self.assertEqual(ledger["parent_step1_error_charge_multiplicity"], 1)
                    self.assertEqual(
                        int(ledger["candidate_cumulative_two_step_operator_error_ticks"]),
                        self.parent_ticks + local_ticks,
                    )

    def test_production_composer_materializes_conformance_failure_without_E1(self) -> None:
        parent_witness = {
            "accuracy_ledger": {
                "grid_denominator": str(P5.GRID),
            },
            "marker": "certified-parent",
        }
        authority = (
            {"report_type": "majorana_p5_conditional_step2_threshold_resource_report_d0_v1"},
            {"status": P5.P4.EXCEEDS_STATUS},
            {
                "status": P5.P4.PARENT_STATUS,
                "terminal_branch": "P3_PARENT",
                "canonical_witness_sha256": "2" * 64,
            },
            parent_witness,
        )
        raws = {
            candidate_id: {
                "candidate_marker": candidate_id,
                "step1": {"execution": {"cap_event": None}},
                "step2": {"execution": {"cap_event": None}},
            }
            for candidate_id in P5.CANDIDATE_ORDER
        }

        def projection(raw, _base):
            return {
                "accuracy_ledger": parent_witness["accuracy_ledger"],
                "marker": raw["candidate_marker"],
            }

        with (
            mock.patch.object(P5, "_verify_design_parent_and_authority", return_value=authority),
            mock.patch.object(P5, "_step1_p3_projection", side_effect=projection),
        ):
            witness = P5._compose_authoritative_witness(
                raws, self.fixture, self.policy, BASE
            )
        self.assertEqual(witness["terminal_branch"], "FAILED_P3_POST_REPLAY_CONFORMANCE")
        self.assertEqual(witness["status"], P5.FAILED_CONFORMANCE_STATUS)
        self.assertIsNone(witness["selected_candidate_id"])
        self.assertEqual(
            witness["parent_P3_authority"][
                "E1_charge_multiplicity_per_completed_candidate"
            ],
            0,
        )
        for row in witness["candidate_results"]:
            self.assertFalse(row["step1_P3_fieldwise_conformance"])
            self.assertFalse(row["parent_P3_E1_inherited"])
            self.assertIsNone(row["telescoping_ledger"])

    def test_runner_and_staging_are_result_blind(self) -> None:
        self.assertEqual(P5.RUNNER_STAGED_PATHS, EXPECTED_STAGED_FILES)
        self.assertFalse(set(P5.RUNNER_STAGED_PATHS) & set(P5.RUNNER_FORBIDDEN_PATHS))
        self.assertIn(P5.D0_POLICY_NAME, P5.RUNNER_FORBIDDEN_PATHS)
        self.assertIn(P5.D0_REPORT_NAME, P5.RUNNER_FORBIDDEN_PATHS)
        runner = (BASE / P5.RUNNER_RELATIVE_PATH).read_bytes()
        numeric_parent = str(self.parent_ticks).encode()
        self.assertNotIn(numeric_parent, runner)
        for name in (
            P5.P3_RESULT_CONTRACT_NAME,
            P5.P3_CERTIFICATE_NAME,
            P5.P4_RESULT_CONTRACT_NAME,
            P5.P4_CERTIFICATE_NAME,
            P5.D0_POLICY_NAME,
            P5.D0_REPORT_NAME,
        ):
            self.assertNotIn(name.encode(), runner)
        for relative in P5.RUNNER_STAGED_PATHS:
            self.assertNotIn(numeric_parent, (BASE / relative).read_bytes())

    def test_precommit_changed_path_allowlist_rejects_any_extra_file(self) -> None:
        self.assertEqual(
            P5.PRECOMMIT_CHANGED_PATHS,
            tuple(sorted((
                P5.RUNNER_RELATIVE_PATH,
                P5.CHECKER_NAME,
                P5.FIXTURE_NAME,
                P5.POLICY_NAME,
                P5.PRECOMMIT_TEST_NAME,
                P5.PRECOMMIT_CONTRACT_NAME,
            ))),
        )
        base_relative = Path("docs/research/fermion-frontier")
        expected = b"".join(
            f"{(base_relative / relative).as_posix()}\n".encode()
            for relative in P5.PRECOMMIT_CHANGED_PATHS
        )
        completed = subprocess.CompletedProcess([], 0, stdout=expected, stderr=b"")
        with mock.patch.object(P5.P2, "_run_git", return_value=completed):
            actual = P5._verify_precommit_changed_path_allowlist(
                Path("/repo"), base_relative, "a" * 40
            )
        self.assertEqual(len(actual), 6)

        extra = subprocess.CompletedProcess(
            [], 0, stdout=expected + b"renamed-raw-witness.json\n", stderr=b""
        )
        with (
            mock.patch.object(P5.P2, "_run_git", return_value=extra),
            self.assertRaises(P5.VerificationError),
        ):
            P5._verify_precommit_changed_path_allowlist(
                Path("/repo"), base_relative, "a" * 40
            )

    def test_runner_declares_same_process_live_link_and_candidate_only_threshold(self) -> None:
        runner = (BASE / P5.RUNNER_RELATIVE_PATH).read_text()
        for fragment in (
            "execution1 = execute_p3(",
            "step2_input_sum = deepcopy(live_step1_sum)",
            "execute_p5_step2(",
            "same_process=true",
            "no_serialization=true",
            "P5_ALLOWED_STEP2_EXPONENTS = (36, 37)",
        ):
            self.assertIn(fragment, runner)
        self.assertRegex(runner, r"function execute_p5_step2\([^\n]*threshold::Float64\)")

    def test_step2_kernel_is_exact_P3_except_the_explicit_threshold_parameter(self) -> None:
        p3_source = (BASE / "majorana_certificate_p3/majorana_p3_runner.jl").read_text()
        p5_source = (BASE / P5.RUNNER_RELATIVE_PATH).read_text()
        p3_kernel = p3_source[
            p3_source.index("function execute_p3"):
            p3_source.index("\nfunction finalize_p3_state!")
        ]
        p5_kernel = p5_source[
            p5_source.index("function execute_p5_step2"):
            p5_source.index("\nfunction main_p5")
        ]
        p3_kernel = p3_kernel.replace(
            "function execute_p3(stages, fixture, observable, trig_lookup)",
            "function EXEC(stages, fixture, observable, trig_lookup)",
        )
        p5_kernel = p5_kernel.replace(
            "function execute_p5_step2(stages, fixture, observable, trig_lookup, threshold::Float64)",
            "function EXEC(stages, fixture, observable, trig_lookup)",
        ).replace(
            '    isfinite(threshold) && threshold > 0.0 || error("invalid P5 step-2 threshold")\n',
            "",
        ).replace(
            "abs(coefficient) < threshold", "abs(coefficient) < EPSILON"
        )
        self.assertEqual(p5_kernel, p3_kernel)

    def test_scope_excludes_deferred_routes_and_READY(self) -> None:
        scope = self.policy["scope_boundary"]
        self.assertEqual(scope["uniform_2^-36_or_2^-37_threshold_across_both_steps"], "NOT_ASSESSED")
        self.assertEqual(scope["budget_constrained_drop"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])
        self.assertFalse(self.fixture["scope"]["ready_gate_eligible"])

    def test_required_adversarial_mutations_cover_P5_specific_risks(self) -> None:
        mutations = set(self.policy["required_adversarial_mutations"])
        required_fragments = (
            "RETHRESHOLD_STEP1",
            "DOUBLE_CHARGE",
            "INHERIT_P4_E12",
            "SKIP_K37",
            "SELECT_K37",
            "SHARE_A_PROCESS_STATE",
            "SIGNED_ZERO",
            "BUDGET_CONSTRAINED_DROP",
            "RESULT_UNPINNED_PRECOMMIT",
        )
        for fragment in required_fragments:
            self.assertTrue(any(fragment in row for row in mutations), fragment)

    def test_fixture_and_policy_mutations_fail_closed(self) -> None:
        bad_fixture = copy.deepcopy(self.fixture)
        bad_fixture["candidate_thresholds"][0]["threshold_exponent"] = 35
        with self.assertRaises(P5.VerificationError):
            P5.validate_fixture(bad_fixture, BASE)
        bad_policy = copy.deepcopy(self.policy)
        bad_policy["conditional_candidate_design"][
            "K36_completion_or_pass_does_not_permit_skipping_K37"
        ] = False
        with self.assertRaises(P5.VerificationError):
            P5.validate_policy(bad_policy, self.fixture, self.runtime_lock)

        bad_fingerprint = copy.deepcopy(self.policy)
        bad_fingerprint["policy_fingerprint"] = "semantic-drift"
        with self.assertRaises(P5.VerificationError):
            P5.validate_policy(bad_fingerprint, self.fixture, self.runtime_lock)

        bad_proof = copy.deepcopy(self.policy)
        bad_proof["proof_obligations"] = []
        with self.assertRaises(P5.VerificationError):
            P5.validate_policy(bad_proof, self.fixture, self.runtime_lock)

        bad_host = copy.deepcopy(self.fixture)
        bad_host["host_supervisor_caps"]["maximum_stderr_bytes"] += 1
        with self.assertRaises(P5.VerificationError):
            P5.validate_fixture(bad_host, BASE)

    def test_legacy_module_BASE_is_scoped_and_restored(self) -> None:
        poison = BASE / "this-directory-must-not-be-read"
        previous = P5.P4.BASE
        with mock.patch.object(P5.P4, "BASE", poison):
            self.assertIs(P5.validate_fixture(self.fixture, BASE), self.fixture)
            self.assertEqual(P5.P4.BASE, poison)
        self.assertEqual(P5.P4.BASE, previous)

    def test_candidate_oracle_sets_each_threshold_and_restores_the_global(self) -> None:
        state: dict[int, int] = {}
        descriptor = P5._state_descriptor(state)
        seen: list[int] = []

        def fake_step(*, step_index, state, **_kwargs):
            seen.append(P5.P4.EPSILON_BITS)
            if step_index == 1:
                return (
                    {
                        "execution": {"cap_event": None},
                        "final_state": {
                            "retained_term_count": descriptor["term_count"],
                            "term_stream_sha256": descriptor["term_stream_sha256"],
                        },
                    },
                    dict(state),
                )
            return (
                {"execution": {"cap_event": {"cap_name": "mock"}}, "final_state": None},
                dict(state),
            )

        sentinel = 0x123456789ABCDEF
        previous = P5.P4.EPSILON_BITS
        P5.P4.EPSILON_BITS = sentinel
        try:
            with (
                mock.patch.object(P5.P3, "_validate_trig_table", return_value={str(i): {} for i in range(6)}),
                mock.patch.object(P5.P3, "expected_schedule", return_value=[]),
                mock.patch.object(P5.P3, "_initial_state", return_value=state),
                mock.patch.object(P5, "_resource_cap_sections", return_value=({}, {}, {}, 6)),
                mock.patch.object(P5.P4, "_run_step_oracle", side_effect=fake_step),
            ):
                P5.replay_candidate_oracle({}, self.fixture, "K37", BASE)
            self.assertEqual(seen, [P5.STEP1_THRESHOLD_BITS, P5.CANDIDATE_BITS["K37"]])
            self.assertEqual(P5.P4.EPSILON_BITS, sentinel)
        finally:
            P5.P4.EPSILON_BITS = previous

    def test_signed_zero_micro_oracle_and_policy_regression_are_frozen(self) -> None:
        self.assertIsNone(P5._verify_signed_zero_micro_oracle())
        policy_bytes = P5.canonical_bytes(self.policy)
        self.assertIn(b"signed_zero", policy_bytes)
        checker_source = (BASE / P5.CHECKER_NAME).read_text()
        self.assertIn(SIGNED_ZERO_STREAM_SHA256, checker_source)

    def test_precommit_contract_closes_outer_and_runner_inputs(self) -> None:
        precommit = self._precommit()
        self.assertIs(
            P5.validate_precommit_contract(precommit, BASE),
            precommit,
        )
        self.assertEqual(precommit["required_parent_commit"], REQUIRED_PARENT_COMMIT)
        self.assertEqual(tuple(precommit["runner_staged_files"]), EXPECTED_STAGED_FILES)
        self.assertEqual(tuple(precommit["result_artifacts_required_absent"]), RESULT_ARTIFACTS)
        paths = tuple(row["relative_path"] for row in precommit["source_files"])
        self.assertEqual(paths, P5.PRECOMMIT_SOURCE_PATHS)
        self.assertNotIn(P5.PRECOMMIT_CONTRACT_NAME, paths)

    def test_precommit_source_pins_are_exact_and_have_no_placeholders(self) -> None:
        precommit = self._precommit()
        for row in precommit["source_files"]:
            path = BASE / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["size_bytes"])
            self.assertEqual(_sha256(path), row["sha256"])
        encoded = P5.canonical_bytes(precommit)
        self.assertNotRegex(encoded.decode(), r"(?i)placeholder|todo|tbd")
        for forbidden_key in (
            "P5_result_contract_sha256",
            "P5_certificate_sha256",
            "P5_exact_result_test_sha256",
        ):
            self.assertNotIn(f'"{forbidden_key}":'.encode(), encoded)

    def test_verify_precommit_is_read_only_and_never_starts_replay(self) -> None:
        result_paths = {(BASE / name).resolve() for name in RESULT_ARTIFACTS}
        original_exists = Path.exists

        def precommit_phase_exists(path: Path) -> bool:
            if path.resolve() in result_paths:
                return False
            return original_exists(path)

        status_before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=_repo(), check=True, stdout=subprocess.PIPE,
        ).stdout
        with (
            mock.patch.object(P5, "fresh_replay", side_effect=AssertionError("replay called")),
            mock.patch.object(P5, "materialize_result", side_effect=AssertionError("materialization called")),
            mock.patch.object(P5, "_run_one_isolated_replay", side_effect=AssertionError("process started")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("file written")),
            mock.patch.object(P5.os, "replace", side_effect=AssertionError("file replaced")),
            mock.patch.object(Path, "exists", new=precommit_phase_exists),
        ):
            summary = P5.verify_precommit(BASE)
        self.assertEqual(summary["required_parent_commit"], REQUIRED_PARENT_COMMIT)
        self.assertEqual(summary["candidate_order"], ["K36", "K37"])
        self.assertEqual(summary["fresh_process_count"], 4)
        status_after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=_repo(), check=True, stdout=subprocess.PIPE,
        ).stdout
        self.assertEqual(status_after, status_before)

    def test_precommit_identity_custody_and_stage_mutations_fail_closed(self) -> None:
        precommit = self._precommit()
        mutations = []

        wrong_parent = copy.deepcopy(precommit)
        wrong_parent["required_parent_commit"] = "0" * 40
        mutations.append(wrong_parent)

        duplicate_source = copy.deepcopy(precommit)
        duplicate_source["source_files"].append(
            copy.deepcopy(duplicate_source["source_files"][-1])
        )
        mutations.append(duplicate_source)

        traversal = copy.deepcopy(precommit)
        traversal["source_files"][0]["relative_path"] = "../escape"
        mutations.append(traversal)

        exposed_D0 = copy.deepcopy(precommit)
        exposed_D0["runner_staged_files"].append(P5.D0_REPORT_NAME)
        mutations.append(exposed_D0)

        result_set = copy.deepcopy(precommit)
        result_set["result_artifacts_required_absent"] = list(RESULT_ARTIFACTS[:-1])
        mutations.append(result_set)

        for index, candidate in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(
                (P5.SchemaError, P5.VerificationError)
            ):
                P5.validate_precommit_contract(
                    candidate, BASE, verify_source_files=False
                )

    def test_strict_JSON_rejects_duplicate_keys_and_float_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            duplicate = Path(temporary) / "duplicate.json"
            duplicate.write_bytes(b'{"schema_version":1,"schema_version":1}\n')
            floating = Path(temporary) / "float.json"
            floating.write_bytes(b'{"schema_version":1.0}\n')
            for path in (duplicate, floating):
                with self.subTest(path=path.name), self.assertRaises(P5.SchemaError):
                    P5.load_json(path)

    def test_persisted_result_parser_has_a_separate_result_blind_cap(self) -> None:
        self.assertEqual(P5.P3.MAX_STDOUT_BYTES, 8_388_608)
        derived_cap = P5._persisted_result_byte_cap(BASE)
        self.assertEqual(
            derived_cap,
            4 * self.fixture["host_supervisor_caps"]["maximum_stdout_bytes"],
        )
        payload = b'{"padding":"' + b"x" * P5.P3.MAX_STDOUT_BYTES + b'"}'
        with self.assertRaises(P5.SchemaError):
            P5.P3.strict_json_loads(payload, source="synthetic Julia stdout")
        parsed = P5._strict_persisted_json_loads(
            payload, source="synthetic persisted P5 package",
            maximum_bytes=derived_cap,
        )
        self.assertEqual(len(parsed["padding"]), P5.P3.MAX_STDOUT_BYTES)
        for malformed in (b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":-0}'):
            with self.subTest(malformed=malformed), self.assertRaises(P5.SchemaError):
                P5._strict_persisted_json_loads(
                    malformed, source="malformed persisted P5 package",
                    maximum_bytes=derived_cap,
                )
        with self.assertRaises(P5.SchemaError):
            P5._strict_persisted_json_loads(
                b"{}", source="over-cap persisted P5 package", maximum_bytes=1,
            )

    def test_result_artifacts_are_absent_at_recorded_precommit_commit(self) -> None:
        precommit = self._precommit()
        repo = _repo()
        commit = subprocess.run(
            ["git", "log", "--format=%H", "--", str((BASE / P5.PRECOMMIT_CONTRACT_NAME).relative_to(repo))],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().splitlines()[0]
        parent = subprocess.run(
            ["git", "rev-parse", f"{commit}^"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        self.assertEqual(parent, REQUIRED_PARENT_COMMIT)
        real_repo, base_relative = P5.P2._repo_and_base_relative(BASE)
        changed = P5._verify_precommit_changed_path_allowlist(
            real_repo, base_relative, commit
        )
        self.assertEqual(len(changed), 6)
        tree = set(
            subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", commit],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout.decode().splitlines()
        )
        prefix = str(BASE.relative_to(repo))
        for name in precommit["result_artifacts_required_absent"]:
            self.assertNotIn(f"{prefix}/{name}", tree)


if __name__ == "__main__":
    unittest.main()
