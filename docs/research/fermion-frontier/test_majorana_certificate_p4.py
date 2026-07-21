#!/usr/bin/env python3
"""Lifecycle, custody, arithmetic, and adversarial tests for Majorana P4.

These are precommit tests.  They validate only frozen inputs and lightweight
integer helpers; they never generate a precommit manifest and never start the
two-step Julia replay or the full Python oracle.
"""

from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
import inspect
import math
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent

PARENT_COMMIT = "d5b63abe941ff0a723dd7c15a61b9ab8298286ab"
PARENT_STATUS = (
    "VERIFIED_MAJORANA_P3_L8_STAGGERED_MAGNETIZATION_ONE_FUSED_STEP_"
    "LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_"
    "SUBCERTIFICATE"
)
P4_RESULT_ARTIFACTS = (
    "majorana_certificate_p4_contract.json",
    "majorana_certificate_p4_certificate.json",
    "test_majorana_certificate_p4_result.py",
)
P3_RUNNER_FORBIDDEN = (
    "majorana_certificate_p3_contract.json",
    "majorana_certificate_p3_certificate.json",
    "test_majorana_certificate_p3_result.py",
)
PARENT_ARTIFACTS = {
    "precommit_contract_sha256": "majorana_certificate_p3_precommit_contract.json",
    "result_contract_sha256": "majorana_certificate_p3_contract.json",
    "certificate_sha256": "majorana_certificate_p3_certificate.json",
    "fixture_sha256": "majorana_certificate_p3_fixture.json",
    "policy_sha256": "majorana_certificate_p3_policy.json",
    "runner_sha256": "majorana_certificate_p3/majorana_p3_runner.jl",
    "checker_sha256": "majorana_certificate_p3_checker.py",
    "exact_result_test_sha256": "test_majorana_certificate_p3_result.py",
    "runtime_lock_sha256": "majorana_certificate_p0_runtime_lock.json",
}
EXPECTED_BRANCHES = {
    "STEP2_AND_TWO_STEP_BOUND_WITHIN_ALLOCATIONS": (
        "VERIFIED_MAJORANA_P4_L8_STAGGERED_MAGNETIZATION_TWO_FUSED_STEPS_"
        "LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_"
        "SUBCERTIFICATE"
    ),
    "STEP2_BOUND_EXCEEDS_INCREMENT_ALLOCATION_BUT_TWO_STEP_BOUND_WITHIN_CUMULATIVE_ALLOCATION": (
        "VERIFIED_MAJORANA_P4_L8_SECOND_STEP_ERROR_BOUND_EXCEEDS_INCREMENT_"
        "ALLOCATION_SUBCERTIFICATE"
    ),
    "TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION": (
        "VERIFIED_MAJORANA_P4_L8_TWO_STEP_CUMULATIVE_ERROR_BOUND_EXCEEDS_"
        "ALLOCATION_SUBCERTIFICATE"
    ),
    "STEP1_P3_DETERMINISTIC_POLICY_CAP_EXCEEDED": (
        "VERIFIED_MAJORANA_P4_L8_STEP1_RECONSTRUCTION_POLICY_CAP_EXCEEDED_"
        "SUBCERTIFICATE"
    ),
    "STEP2_DETERMINISTIC_POLICY_CAP_EXCEEDED": (
        "VERIFIED_MAJORANA_P4_L8_SECOND_STEP_POLICY_CAP_EXCEEDED_SUBCERTIFICATE"
    ),
    "FAILED_P3_POST_REPLAY_CONFORMANCE": (
        "FAILED_MAJORANA_P4_STEP1_P3_POST_REPLAY_CONFORMANCE"
    ),
    "INDETERMINATE": "INDETERMINATE_MAJORANA_P4_REPLAY",
    "INVALID_REPLAY": "INVALID_MAJORANA_P4_REPLAY",
}


def _load_checker():
    path = BASE / "majorana_certificate_p4_checker.py"
    spec = importlib.util.spec_from_file_location("majorana_p4_checker_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P4 = _load_checker()


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


def _floor_scaled(value: Fraction, denominator: int) -> int:
    return (value.numerator * denominator) // value.denominator


def _ceil_scaled(value: Fraction, denominator: int) -> int:
    return -((-value.numerator * denominator) // value.denominator)


def _expected_trig_ticks(
    theta: Fraction, kind: str, *, order: int = 7, denominator: int = 2**128
) -> tuple[int, int]:
    if kind == "sin":
        point = sum(
            (
                Fraction(
                    (-1) ** index * theta ** (2 * index + 1),
                    math.factorial(2 * index + 1),
                )
                for index in range(order + 1)
            ),
            Fraction(0),
        )
        remainder = Fraction(
            abs(theta) ** (2 * order + 3), math.factorial(2 * order + 3)
        )
    elif kind == "cos":
        point = sum(
            (
                Fraction(
                    (-1) ** index * theta ** (2 * index),
                    math.factorial(2 * index),
                )
                for index in range(order + 1)
            ),
            Fraction(0),
        )
        remainder = Fraction(
            abs(theta) ** (2 * order + 2), math.factorial(2 * order + 2)
        )
    else:
        raise AssertionError(f"unsupported trigonometric kind: {kind}")
    return (
        _floor_scaled(point - remainder, denominator),
        _ceil_scaled(point + remainder, denominator),
    )


def _allocation_branch(parent_ticks: int, step2_ticks: int, grid: int) -> str:
    step2_within = step2_ticks * 400000 < grid
    cumulative_within = (parent_ticks + step2_ticks) * 200000 < grid
    if step2_within and not cumulative_within:
        return "INVALID_TRUTH_COMBINATION"
    if not cumulative_within:
        return "TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION"
    if not step2_within:
        return (
            "STEP2_BOUND_EXCEEDS_INCREMENT_ALLOCATION_BUT_TWO_STEP_BOUND_"
            "WITHIN_CUMULATIVE_ALLOCATION"
        )
    return "STEP2_AND_TWO_STEP_BOUND_WITHIN_ALLOCATIONS"


class MajoranaP4PrecommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = P4.load_json(BASE / P4.FIXTURE_NAME)
        cls.policy = P4.load_json(BASE / P4.POLICY_NAME)
        cls.runtime_lock = P4.load_json(BASE / P4.RUNTIME_LOCK_NAME)
        cls.parent_result = P4.load_json(BASE / P4.P3_RESULT_CONTRACT_NAME)
        cls.parent_certificate = P4.load_json(BASE / P4.P3_CERTIFICATE_NAME)
        cls.parent_ticks = int(
            cls.parent_result["witness"]["accuracy_ledger"][
                "total_operator_error_ticks"
            ]
        )

    def _precommit(self):
        path = BASE / P4.PRECOMMIT_CONTRACT_NAME
        self.assertTrue(path.is_file(), "P4 precommit contract has not been materialized")
        return P4.load_json(path)

    def test_public_fixture_and_policy_validators_accept_the_frozen_inputs(self) -> None:
        self.assertIs(P4.validate_fixture(self.fixture), self.fixture)
        self.assertIs(P4.validate_policy(self.policy, self.runtime_lock), self.policy)
        self.assertEqual(
            self.fixture["fixture_id"],
            "MAJORANA-P4-L8-FUSED-TWO-STEP-LOCAL-DEFECT-V2",
        )
        self.assertEqual(self.policy["policy_id"], "MAJORANA-P4-S0V2")
        for name in (
            "validate_fixture",
            "validate_policy",
            "validate_precommit_contract",
            "verify_precommit",
        ):
            self.assertTrue(callable(getattr(P4, name, None)), name)

    def test_probe_disclosure_is_complete_non_authoritative_and_allocation_blind(self) -> None:
        fixture_probe = self.fixture["design_probe_disclosure"]
        policy_probe = self.policy["design_probe_disclosure"]
        for probe in (fixture_probe, policy_probe):
            self.assertEqual(
                probe["status"], "DESIGN_PROBE_OBSERVED_HOST_RUNTIME_CAP_ONLY"
            )
            self.assertTrue(probe["caps_are_probe_informed"])
            self.assertTrue(probe["allocations_are_campaign_derived_not_probe_informed"])
            self.assertFalse(probe["authoritative_P4_result_generated"])
            self.assertTrue(probe["probe_outputs_are_non_authoritative"])
            observed = probe["observed_fields"]
            self.assertTrue(observed["process_reached_step2"])
            self.assertFalse(
                observed[
                    "scientific_step2_counters_ticks_term_digest_Neel_center_and_allocation_branch_observed"
                ]
            )
            self.assertEqual(observed["stdout_bytes"], 0)
            self.assertEqual(observed["cgroup_terminal_event"], "SIGTERM_AT_RuntimeMaxSec_300s")
        self.assertEqual(fixture_probe["observed_fields"], policy_probe["observed_fields"])
        self.assertTrue(
            fixture_probe[
                "formal_replay_must_use_fresh_processes_and_must_not_reuse_the_probe_process_state_or_bytes"
            ]
        )

    def test_failed_v1_formal_attempt_is_disclosed_without_result_pins(self) -> None:
        fixture_attempt = self.fixture["failed_formal_replay_disclosure"]
        policy_attempt = self.policy["failed_formal_replay_disclosure"]
        for attempt in (fixture_attempt, policy_attempt):
            self.assertEqual(attempt["failed_precommit_commit"], P4.FAILED_V1_PRECOMMIT_COMMIT)
            self.assertEqual(attempt["failed_checker_sha256"], P4.FAILED_V1_CHECKER_SHA256)
            self.assertTrue(attempt["outer_oracle_failed_closed_before_package_materialization"])
            self.assertFalse(attempt["authoritative_P4_result_generated"])
            self.assertEqual(
                attempt["first_rejected_field"],
                "steps[1].final_state.checkerboard_Neel_contribution_stream_sha256",
            )
        self.assertEqual(fixture_attempt["fresh_raw_processes_completed"], 2)
        self.assertTrue(fixture_attempt["raw_stdout_was_byte_identical"])
        self.assertFalse(fixture_attempt["replay_package_materialized"])
        self.assertTrue(
            policy_attempt[
                "diagnostic_checker_fix_requires_a_new_precommit_and_fresh_replays"
            ]
        )
        self.assertFalse(policy_attempt["scientific_workload_allocations_and_caps_changed"])

    def test_runner_visible_fixture_and_policy_do_not_embed_numeric_parent_E1(self) -> None:
        numeric = str(self.parent_ticks).encode()
        self.assertNotIn(numeric, P4.canonical_bytes(self.fixture))
        self.assertNotIn(numeric, P4.canonical_bytes(self.policy))
        parent = self.fixture["required_parent_P3"]
        self.assertNotIn("E1_ticks", parent)
        self.assertNotIn("total_operator_error_ticks", parent)
        visibility = self.fixture["runner_visibility_and_parent_inheritance"]
        self.assertTrue(
            visibility[
                "runner_must_not_receive_the_numeric_parent_E1_ticks_or_any_equivalent_numeric_parent_error_bound"
            ]
        )

    def test_parent_artifact_lineage_hashes_match_active_published_bytes(self) -> None:
        parent = self.fixture["required_parent_P3"]
        self.assertEqual(parent["direct_parent_commit"], PARENT_COMMIT)
        self.assertEqual(parent["status"], PARENT_STATUS)
        for field, relative in PARENT_ARTIFACTS.items():
            self.assertEqual(_sha256(BASE / relative), parent[field], relative)

    def test_parent_witness_ledger_and_transcript_lineage_is_exact(self) -> None:
        parent = self.fixture["required_parent_P3"]
        self.assertEqual(
            parent["canonical_witness_sha256"],
            self.parent_result["canonical_witness_sha256"],
        )
        self.assertEqual(
            parent["accuracy_ledger_sha256"],
            self.parent_certificate["accuracy_ledger_sha256"],
        )
        self.assertEqual(
            self.parent_result["transcript_sha256_in_order"],
            [parent["canonical_transcript_sha256"]] * 2,
        )
        projection = self.fixture["P3_post_replay_conformance_projection"]
        self.assertEqual(
            projection["step1_full_witness_sha256_must_match_published_parent"],
            parent["canonical_witness_sha256"],
        )
        self.assertEqual(
            projection["step1_accuracy_ledger_sha256_must_match_published_parent"],
            parent["accuracy_ledger_sha256"],
        )

    def test_direct_parent_commit_contains_the_same_published_parent_bytes(self) -> None:
        repo = _repo()
        base_relative = BASE.resolve().relative_to(repo)
        resolved = subprocess.run(
            ["git", "rev-parse", PARENT_COMMIT],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode().strip()
        self.assertEqual(resolved, PARENT_COMMIT)
        for relative in PARENT_ARTIFACTS.values():
            active = (BASE / relative).read_bytes()
            committed = subprocess.run(
                ["git", "show", f"{PARENT_COMMIT}:{(base_relative / relative).as_posix()}"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertEqual(active, committed, relative)

    def test_two_step_schedule_counts_angles_threshold_and_target_are_frozen(self) -> None:
        relation = self.fixture["frozen_execution_relation"]
        self.assertEqual(relation["mapped_step_indices"], [1, 2])
        self.assertEqual(
            (
                relation["composite_count_per_step"],
                relation["constituent_count_per_step"],
                relation["truncation_boundary_count_per_step"],
            ),
            (512, 1152, 768),
        )
        self.assertEqual(relation["total_composite_count_if_completed"], 1024)
        self.assertEqual(relation["total_constituent_count_if_completed"], 2304)
        self.assertEqual(relation["total_truncation_boundary_count_if_completed"], 1536)
        self.assertEqual(relation["threshold_Float64_bits_hex"], "3dd0000000000000")
        self.assertEqual(
            set(self.fixture["exact_two_step_target"]["allowed_exact_applied_angles"]),
            {"-1/50", "-1/100", "-1/200", "1/200", "1/100", "1/50"},
        )
        self.assertTrue(
            self.fixture["exact_two_step_target"][
                "exact_target_is_untruncated_two_step_product_formula_not_exact_Hubbard_time_evolution"
            ]
        )

    def test_same_process_in_memory_step_link_is_mandatory(self) -> None:
        link = self.fixture["same_process_fresh_two_step_replay"]
        self.assertTrue(link["fresh_process_starts_from_O0"])
        self.assertTrue(link["step1_and_step2_execute_in_the_same_Julia_process"])
        self.assertTrue(link["step2_input_is_a_deepcopy_of_the_in_memory_step1_retained_mainsum"])
        self.assertTrue(link["step1_final_term_count_must_equal_step2_input_term_count"])
        self.assertTrue(
            link[
                "step1_final_canonical_term_stream_sha256_must_equal_step2_input_canonical_term_stream_sha256"
            ]
        )
        self.assertTrue(link["checkpoint_resume_serialization_and_cross_process_step_link_are_forbidden"])
        determinism = self.policy["result_determinism"]
        self.assertEqual(determinism["fresh_process_count"], 2)
        self.assertTrue(determinism["each_process_runs_both_steps_from_O0_in_one_Julia_process"])

    def test_raw_runner_ledger_is_local_and_outer_composition_is_cumulative(self) -> None:
        ledger = self.fixture["step2_local_ledger"]
        link = self.fixture["same_process_fresh_two_step_replay"]
        self.assertTrue(ledger["each_record_carries_step2_local_ticks_starting_at_zero"])
        self.assertTrue(ledger["raw_records_must_not_carry_parent_E1_or_any_two_step_cumulative_numeric_bound"])
        self.assertTrue(
            ledger[
                "outer_composed_aggregate_carries_inherited_parent_E1_plus_step2_local_ticks_after_post_replay_conformance"
            ]
        )
        self.assertTrue(link["raw_runner_step2_error_counter_contains_local_ticks_only_and_starts_at_zero"])
        self.assertTrue(
            link[
                "outer_composed_two_step_cumulative_error_counter_starts_at_the_post_conformance_inherited_parent_E1"
            ]
        )

    def test_parent_error_is_inherited_exactly_once_without_requantization(self) -> None:
        fixture_rules = self.fixture["runner_visibility_and_parent_inheritance"]
        policy_rules = self.policy["error_inheritance_and_telescoping_rules"]
        self.assertEqual(fixture_rules["step1_semantic_charge_multiplicity"], 1)
        self.assertEqual(policy_rules["step1_semantic_charge_multiplicity"], 1)
        self.assertEqual(
            fixture_rules["authoritative_cumulative_recurrence"],
            "E12_ticks_equals_inherited_parent_E1_ticks_plus_step2_local_increment_ticks",
        )
        self.assertEqual(policy_rules["parent_error_exact_unitary_propagation_factor"], "1")
        self.assertTrue(fixture_rules["inherited_parent_ticks_are_not_requantized_rounded_or_outward_widened_again"])
        forbidden = " ".join(fixture_rules["forbidden_recurrences"])
        for canary in ("fresh_step1_E1", "two_times_parent_E1", "one_hundred_times_parent_E1", "step_ratio"):
            self.assertIn(canary, forbidden)

    def test_strict_integer_allocations_fail_at_the_first_nonpassing_tick(self) -> None:
        grid = 2**128
        allocation = self.fixture["allocation"]
        self.assertEqual(Fraction(allocation["step2_local_increment_allocation"]), Fraction(1, 400000))
        self.assertEqual(Fraction(allocation["two_step_cumulative_allocation"]), Fraction(1, 200000))
        self.assertTrue(allocation["equality_fails_both_strict_comparisons"])
        step2_last_pass = (grid - 1) // 400000
        cumulative_last_pass = (grid - 1) // 200000
        self.assertLess(step2_last_pass * 400000, grid)
        self.assertGreaterEqual((step2_last_pass + 1) * 400000, grid)
        self.assertLess(cumulative_last_pass * 200000, grid)
        self.assertGreaterEqual((cumulative_last_pass + 1) * 200000, grid)
        self.assertNotIn("Float", allocation["step2_strict_integer_comparison"])
        self.assertNotIn("Float", allocation["two_step_strict_integer_comparison"])

    def test_allocation_truth_table_matches_exact_cross_multiplication(self) -> None:
        grid = 2**128
        step2_first_fail = (grid - 1) // 400000 + 1
        cumulative_first_fail_delta = (grid - 1) // 200000 - self.parent_ticks + 1
        observed = [
            _allocation_branch(self.parent_ticks, 0, grid),
            _allocation_branch(self.parent_ticks, step2_first_fail, grid),
            _allocation_branch(self.parent_ticks, cumulative_first_fail_delta, grid),
        ]
        declared = [row["allocation_branch"] for row in self.fixture["allocation"]["legal_completed_truth_table"]]
        self.assertEqual(observed, declared)
        self.assertLess(self.parent_ticks * 400000, grid)
        self.assertNotEqual(
            _allocation_branch(self.parent_ticks, step2_last_pass := (grid - 1) // 400000, grid),
            "INVALID_TRUTH_COMBINATION",
        )
        self.assertGreaterEqual(step2_last_pass, 0)

    def test_step2_resource_caps_are_exact_and_additive(self) -> None:
        caps = self.fixture["deterministic_resource_caps"]
        self.assertEqual(caps["maximum_step2_current_terms_before_constituent"], 2**18)
        self.assertEqual(caps["maximum_step2_boundary_retained_terms"], 2**18)
        self.assertEqual(caps["maximum_step2_final_retained_terms"], 2**18)
        self.assertEqual(caps["maximum_step2_premerge_terms"], 2**19)
        for field in ("cap_scan", "propagation", "truncation"):
            self.assertEqual(caps[f"maximum_step2_{field}_term_visits"], 2**28)
        self.assertEqual(
            caps["maximum_step2_total_P2_charged_term_visits"],
            sum(caps[f"maximum_step2_{field}_term_visits"] for field in ("cap_scan", "propagation", "truncation"))
            + caps["maximum_step2_final_retained_terms"],
        )
        self.assertEqual(caps["maximum_step2_product_defect_events"], 2**24)
        self.assertEqual(caps["maximum_step2_merge_defect_events"], 2**23)
        self.assertEqual(caps["maximum_step2_drop_defect_events"], 2**23)
        self.assertEqual(
            caps["maximum_step2_accuracy_charged_events"],
            caps["maximum_step2_product_defect_events"]
            + caps["maximum_step2_merge_defect_events"]
            + caps["maximum_step2_drop_defect_events"],
        )
        self.assertEqual(caps["maximum_step2_total_P2_plus_accuracy_charged_events"], 2**30)
        self.assertEqual(caps["maximum_BigInt_bit_length"], 2048)
        self.assertEqual(caps["maximum_trig_table_entries"], 6)

    def test_cumulative_caps_are_derived_only_from_frozen_step_caps(self) -> None:
        step1, step2, cumulative, maximum_trig = P4._resource_cap_sections(self.fixture)
        instantaneous = {
            "maximum_current_terms_before_constituent",
            "maximum_premerge_terms",
            "maximum_boundary_retained_terms",
        }
        for key in P4._CUMULATIVE_CAP_KEYS:
            expected = max(step1[key], step2[key]) if key in instantaneous else step1[key] + step2[key]
            self.assertEqual(cumulative[key], expected, key)
        caps = self.fixture["deterministic_resource_caps"]
        self.assertEqual(cumulative["maximum_total_charged_term_visits"], caps["maximum_two_step_total_P2_charged_term_visits"])
        self.assertEqual(cumulative["maximum_accuracy_charged_events"], caps["maximum_two_step_accuracy_charged_events"])
        self.assertEqual(cumulative["maximum_total_P2_plus_accuracy_charged_events"], caps["maximum_two_step_total_P2_plus_accuracy_charged_events"])
        self.assertEqual(maximum_trig, 6)

    def test_operation_before_cap_checks_leave_counters_unmodified(self) -> None:
        _step1, step2, cumulative_caps, _trig = P4._resource_cap_sections(self.fixture)
        p2_local = {"cap_scan": 0, "propagation": 0, "truncation": 0, "final": 0}
        p2_cumulative = copy.deepcopy(p2_local)
        local = {"anticommuting": 0, "product": step2["maximum_product_defect_events"], "merge": 0, "drop": 0}
        cumulative = copy.deepcopy(local)
        before = (copy.deepcopy(local), copy.deepcopy(cumulative))
        with self.assertRaises(P4._CapExceeded) as captured:
            P4._charge_accuracy(
                step_index=2,
                field="product",
                cap_name="maximum_product_defect_events",
                amount=1,
                local=local,
                cumulative=cumulative,
                step_caps=step2,
                cumulative_caps=cumulative_caps,
                p2_local=p2_local,
                p2_cumulative=p2_cumulative,
                context={"operation": "test_rejected_product_row"},
            )
        self.assertEqual((local, cumulative), before)
        self.assertTrue(captured.exception.event["rejected_operation_was_not_executed_after_cap_detection"])
        self.assertEqual(captured.exception.event["cap_scope"], "step")

    def test_host_caps_and_indeterminate_failure_branch_are_frozen(self) -> None:
        host = self.fixture["host_supervisor_caps"]
        self.assertTrue(host["systemd_user_scope_cgroup_v2_required"])
        self.assertEqual(host["MemoryMax_bytes"], 2**32)
        self.assertEqual(host["RuntimeMaxSec"], "600s")
        self.assertEqual(host["subprocess_safety_timeout_seconds"], 630)
        self.assertEqual(host["maximum_stdout_bytes"], 2**24)
        self.assertEqual(host["maximum_stderr_bytes"], 2**20)
        self.assertEqual(host["host_cap_failure_branch"], "INDETERMINATE")
        self.assertTrue(self.policy["resource_enforcement"]["host_cap_failure_is_indeterminate_not_a_deterministic_policy_or_allocation_result"])

    def test_scope_cannot_expand_to_R100_Hubbard_reference_or_READY(self) -> None:
        scope = self.policy["scope_boundary"]
        self.assertTrue(scope["fixed_L8_first_two_adjacent_fused_mapped_steps_exact_product_formula_target_only"])
        self.assertEqual(scope["remaining_98_mapped_steps_or_full_R100"], "NOT_ASSESSED")
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error_or_exact_time_evolution"], "NOT_ASSESSED")
        self.assertEqual(scope["double_occupancy"], "NOT_ASSESSED")
        self.assertEqual(scope["global_coefficientwise_interval_state"], "NOT_CLAIMED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])
        self.assertTrue(scope["P4_does_not_retroactively_expand_P3_authority"])

    def test_branch_status_map_and_failure_authority_are_fail_closed(self) -> None:
        branches = {row["branch"]: row for row in self.policy["legal_terminal_branches"]}
        self.assertEqual({key: row["maximum_status"] for key, row in branches.items()}, EXPECTED_BRANCHES)
        for branch in ("FAILED_P3_POST_REPLAY_CONFORMANCE", "INDETERMINATE", "INVALID_REPLAY"):
            self.assertTrue(branches[branch]["authority"].startswith("none"), branch)
            self.assertNotEqual(branches[branch]["maximum_status"], P4.MAXIMUM_STATUS)
        step2_cap = branches["STEP2_DETERMINISTIC_POLICY_CAP_EXCEEDED"]
        self.assertIn("after_complete_P3_step1_post_replay_conformance", step2_cap["authority"])
        precedence = self.policy["terminal_branch_precedence"]
        self.assertLess(precedence.index("complete_step1_P3_post_replay_conformance_gate"), precedence.index("deterministic_step2_cap_after_successful_P3_conformance"))

    def test_required_adversarial_mutation_classes_cover_P4_specific_risks(self) -> None:
        mutations = set(self.policy["required_adversarial_mutations"])
        required = {
            "READ_NUMERIC_PARENT_E1_OR_A_P3_RESULT_ARTIFACT_IN_THE_JULIA_RUNNER",
            "DOUBLE_CHARGE_REPLAYED_STEP1_OR_OMIT_PARENT_E1",
            "REPLACE_E1_PLUS_DELTA2_WITH_TWO_E1_ONE_HUNDRED_E1_OR_STEP_RATIO_EXTRAPOLATION",
            "RUN_STEP2_FROM_A_CHECKPOINT_SERIALIZED_OR_CROSS_PROCESS_STEP1_STATE",
            "CHANGE_THE_STEP1_FINAL_TO_STEP2_INPUT_TERM_COUNT_OR_TERM_STREAM_DIGEST",
            "RESET_THE_TWO_STEP_CUMULATIVE_COUNTER_TO_ZERO_OR_FAIL_TO_RESET_STEP2_LOCAL_COUNTERS",
            "ROUND_ONE_STEP2_DEFECT_ROW_DOWN_BY_ONE_TICK",
            "USE_NONSTRICT_OR_FLOATING_POINT_ALLOCATION_COMPARISON",
            "TREAT_ALLOCATION_EXCESS_AS_A_CAP_OR_HOST_FAILURE",
            "EXECUTE_THE_OPERATION_REJECTED_BY_A_DETERMINISTIC_CAP",
            "ALLOW_A_P4_FORMAL_RESULT_ARTIFACT_IN_THE_FINAL_PRECOMMIT_TREE",
            "EXPAND_AUTHORITY_TO_REMAINING_R100_EXACT_HUBBARD_REFERENCE_OR_READY",
        }
        self.assertTrue(required.issubset(mutations))

    def test_fixture_mutations_fail_closed(self) -> None:
        mutants = []
        candidate = copy.deepcopy(self.fixture)
        candidate["required_parent_P3"]["E1_ticks"] = "1"
        mutants.append(candidate)
        candidate = copy.deepcopy(self.fixture)
        candidate["allocation"]["step2_local_increment_allocation"] = "1/399999"
        mutants.append(candidate)
        candidate = copy.deepcopy(self.fixture)
        candidate["deterministic_resource_caps"]["maximum_two_step_accuracy_charged_events"] -= 1
        mutants.append(candidate)
        candidate = copy.deepcopy(self.fixture)
        candidate["same_process_fresh_two_step_replay"]["step1_and_step2_execute_in_the_same_Julia_process"] = False
        mutants.append(candidate)
        candidate = copy.deepcopy(self.fixture)
        candidate["step2_local_ledger"]["raw_records_must_not_carry_parent_E1_or_any_two_step_cumulative_numeric_bound"] = False
        mutants.append(candidate)
        for candidate in mutants:
            with self.assertRaises((P4.SchemaError, P4.VerificationError)):
                P4.validate_fixture(candidate)

    def test_policy_mutations_fail_closed(self) -> None:
        mutants = []
        candidate = copy.deepcopy(self.policy)
        candidate["scope_boundary"]["ready_gate_eligible"] = True
        mutants.append(candidate)
        candidate = copy.deepcopy(self.policy)
        candidate["legal_terminal_branches"][0]["maximum_status"] = "READY"
        mutants.append(candidate)
        candidate = copy.deepcopy(self.policy)
        candidate["replay_environment_custody"]["PID_namespace_unshared"] = False
        mutants.append(candidate)
        candidate = copy.deepcopy(self.policy)
        candidate["runner_parent_visibility_policy"]["runner_staging_must_exclude_numeric_parent_E1_and_equivalent_numeric_bounds"] = False
        mutants.append(candidate)
        candidate = copy.deepcopy(self.policy)
        candidate["design_probe_disclosure"]["authoritative_P4_result_generated"] = True
        mutants.append(candidate)
        for candidate in mutants:
            with self.assertRaises((P4.SchemaError, P4.VerificationError)):
                P4.validate_policy(candidate, self.runtime_lock)

    def test_binary64_decode_and_RNE_rounding_are_exact(self) -> None:
        helper = P4.P3
        self.assertEqual(helper.decode_binary64_bits("0000000000000001"), Fraction(1, 2**1074))
        self.assertEqual(helper.decode_binary64_bits("c004000000000000"), Fraction(-5, 2))
        for bits in ("7ff0000000000000", "fff0000000000000", "7ff8000000000001"):
            with self.assertRaises((P4.SchemaError, P4.VerificationError)):
                helper.decode_binary64_bits(bits)
        round_bits = helper.round_fraction_to_binary64_bits
        self.assertEqual(round_bits(Fraction(1) + Fraction(1, 2**53)), "3ff0000000000000")
        self.assertEqual(round_bits(Fraction(1) + Fraction(3, 2**53)), "3ff0000000000002")
        self.assertEqual(round_bits(Fraction(3, 2**1075)), "0000000000000002")

    def test_binary64_add_multiply_and_signed_zero_rules_are_bit_exact(self) -> None:
        helper = P4.P3
        self.assertEqual(helper.binary64_add_bits("3ff0000000000000", "3cb0000000000000"), "3ff0000000000001")
        self.assertEqual(helper.binary64_mul_bits("3ff8000000000000", "4000000000000000"), "4008000000000000")
        self.assertEqual(helper.binary64_add_bits("8000000000000000", "8000000000000000"), "8000000000000000")
        self.assertEqual(helper.binary64_mul_bits("8000000000000000", "c000000000000000"), "0000000000000000")

    def test_fock_diagnostic_tracks_complex_signed_zero_history(self) -> None:
        occupied = P4.P3._neel_gamma_mask()
        # This is the smallest mask for which the old phase-only shortcut says
        # +0 while the pinned Julia overlapwithfock loop returns -0.  The sign
        # comes from the intervening ComplexF64 × Complex{Int64} unit products.
        self.assertEqual(
            P4.P3._upstream_fock_real_bits(0x17C, occupied),
            0x0000000000000000,
        )
        self.assertEqual(
            P4._upstream_fock_real_bits(0x17C, occupied),
            0x8000000000000000,
        )
        for mask, expected in (
            (0x1, 0), (0x7, 0), (0x17, 0),
            (0x1C, P4.SIGN_MASK), (0x1DC, P4.SIGN_MASK), (0x53C, 0),
        ):
            self.assertEqual(P4._upstream_fock_real_bits(mask, occupied), expected)
        self.assertEqual(P4.P3._fock_diagonal_mask(0x17C, occupied), 0)
        self.assertEqual(
            P4._complex_mul_bits(
                (P4.SIGN_MASK, 0xBFF0000000000000),
                (0x3FF0000000000000, 0),
            ),
            (0, 0xBFF0000000000000),
        )
        digest = hashlib.sha256()
        for mask in range(1 << 16):
            bits = P4._upstream_fock_real_bits(mask, occupied)
            digest.update(f"{mask:x}\t{bits:016x}\n".encode("ascii"))
        self.assertEqual(
            digest.hexdigest(),
            "323caca70bb0131db1ac554beaa99ffe4b4d9927ec448c83db5a9b11dd9d70c4",
        )

    def test_trig_intervals_match_an_independent_order7_fraction_oracle(self) -> None:
        for encoded in self.fixture["exact_two_step_target"]["allowed_exact_applied_angles"]:
            theta = Fraction(encoded)
            for kind in ("sin", "cos"):
                self.assertEqual(
                    P4.P3.trig_interval_ticks(theta, kind, order=7, denominator=2**128),
                    _expected_trig_ticks(theta, kind),
                    (encoded, kind),
                )

    def test_local_product_merge_and_drop_helpers_round_outward(self) -> None:
        helper = P4.P3
        grid = 2**128
        one = "3ff0000000000000"
        half = "3fe0000000000000"
        two_to_minus_53 = "3ca0000000000000"
        self.assertEqual(helper.local_product_defect_upper_ticks(one, one, (grid - 1, grid)), 1)
        self.assertEqual(helper.merge_defect_upper_ticks(half, half, one), 0)
        self.assertEqual(helper.merge_defect_upper_ticks(one, two_to_minus_53, one), 2**75)
        self.assertEqual(helper.drop_defect_upper_ticks("3dd0000000000000"), 2**94)

    def test_runner_source_declares_same_process_step_link_and_raw_local_schema(self) -> None:
        source = (BASE / P4.RUNNER_RELATIVE_PATH).read_text()
        self.assertIn("deepcopy", source)
        self.assertRegex(source, re.compile(r"length\(ARGS\)\s*==\s*3"))
        for canary in ("step1", "step_link", "step2", "term_stream_sha256", "term_count"):
            self.assertRegex(source, re.compile(rf'(?i)(?:"{canary}"|\b{canary}\b)'))
        self.assertIn("checkpoint_or_serialized_state_used=false", source)
        for forbidden in ("Serialization", "deserialize(", "read_checkpoint", "resume_from"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn('"cumulative_two_step_ticks"', source)
        self.assertNotIn('"inherited_parent_E1_ticks"', source)

    def test_runner_source_and_staged_bytes_cannot_see_parent_results_or_numeric_E1(self) -> None:
        source = (BASE / P4.RUNNER_RELATIVE_PATH).read_bytes()
        numeric = str(self.parent_ticks).encode()
        self.assertNotIn(numeric, source)
        for forbidden in (*P3_RUNNER_FORBIDDEN, *P4_RESULT_ARTIFACTS):
            self.assertNotIn(forbidden.encode(), source)
        for relative in P4.RUNNER_STAGED_PATHS:
            payload = (BASE / relative).read_bytes()
            self.assertNotIn(numeric, payload, relative)
        self.assertTrue(set(P4.RUNNER_STAGED_PATHS).isdisjoint(P4.RUNNER_FORBIDDEN_PATHS))

    def test_bubblewrap_custody_and_runner_allowlist_do_not_expose_host_root(self) -> None:
        replay_helper = getattr(P4, "_run_one_isolated_replay", P4.P3._run_one_isolated_replay)
        source = inspect.getsource(replay_helper)
        normalized = " ".join(source.replace("\n", " ").split())
        self.assertIn('"--unshare-net"', source)
        self.assertIn('"--unshare-pid"', source)
        self.assertNotIn('"--ro-bind", "/", "/"', normalized)
        for broad_mount in ("/usr", "/usr/lib", "/lib", "/lib64", "/etc", "/Data"):
            self.assertNotIn(f'"--ro-bind", "{broad_mount}", "{broad_mount}"', normalized)
        custody = self.policy["replay_environment_custody"]
        self.assertEqual(custody["exact_sandbox_regular_file_target_count"], 18)
        self.assertEqual(tuple(P4.REPLAY_ENVIRONMENT_TARGETS), tuple(P4.P3.REPLAY_ENVIRONMENT_TARGETS))
        self.assertEqual(custody["only_writable_host_backed_bind_mount_target"], "/scratch")
        self.assertEqual(custody["private_kernel_virtual_mount_targets"], ["/dev", "/proc"])

    def test_precommit_contract_closes_outer_and_runner_inputs(self) -> None:
        precommit = self._precommit()
        validated = P4.validate_precommit_contract(precommit)
        self.assertEqual(
            validated["contract_type"],
            "majorana_p4_result_unpinned_adjacent_step_replay_input_and_isolation_contract_v2",
        )
        self.assertEqual(validated["required_parent_commit"], PARENT_COMMIT)
        self.assertEqual(
            tuple(row["relative_path"] for row in validated["source_files"]),
            P4.PRECOMMIT_SOURCE_PATHS,
        )
        self.assertEqual(tuple(validated["runner_staged_files"]), P4.RUNNER_STAGED_PATHS)
        self.assertEqual(tuple(validated["runner_forbidden_paths"]), P4.RUNNER_FORBIDDEN_PATHS)
        self.assertEqual(tuple(validated["result_artifacts_required_absent"]), P4_RESULT_ARTIFACTS)

    def test_precommit_source_pins_and_staged_runtime_canary_are_exact(self) -> None:
        precommit = self._precommit()
        paths = []
        for row in precommit["source_files"]:
            relative = row["relative_path"]
            paths.append(relative)
            path = BASE / relative
            self.assertTrue(path.is_file(), relative)
            self.assertFalse(path.is_symlink(), relative)
            self.assertEqual(path.stat().st_size, row["size_bytes"], relative)
            self.assertEqual(_sha256(path), row["sha256"], relative)
        self.assertEqual(paths, sorted(paths))
        with tempfile.TemporaryDirectory(prefix="majorana-p4-stage-canary-") as directory:
            root = Path(directory)
            for relative in precommit["runner_staged_files"]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
            staged = tuple(sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()))
            self.assertEqual(staged, P4.RUNNER_STAGED_PATHS)
            for forbidden in P4.RUNNER_FORBIDDEN_PATHS:
                self.assertFalse((root / forbidden).exists(), forbidden)

    def test_result_artifacts_are_absent_at_the_recorded_precommit_boundary(self) -> None:
        result_path = BASE / P4.RESULT_CONTRACT_NAME
        if not result_path.exists():
            for artifact in P4_RESULT_ARTIFACTS:
                self.assertFalse((BASE / artifact).exists(), artifact)
            return
        result = P4.load_json(result_path)
        precommit_commit = result["precommit_commit_sha"]
        repo = _repo()
        base_relative = BASE.resolve().relative_to(repo)
        for artifact in P4_RESULT_ARTIFACTS:
            relative = (base_relative / artifact).as_posix()
            probe = subprocess.run(
                ["git", "cat-file", "-e", f"{precommit_commit}:{relative}"],
                cwd=repo,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(probe.returncode, 0, artifact)

    def test_verify_precommit_is_read_only_lifecycle_aware_and_replay_free(self) -> None:
        verify_precommit = getattr(P4, "verify_precommit")
        result_paths = {(BASE / name).resolve() for name in P4_RESULT_ARTIFACTS}
        original_exists = Path.exists

        def precommit_phase_exists(path: Path) -> bool:
            if path.resolve() in result_paths:
                return False
            return original_exists(path)

        patches = (
            mock.patch.object(P4, "fresh_replay", side_effect=AssertionError("replay called"), create=True),
            mock.patch.object(P4, "run_formal_replay", side_effect=AssertionError("formal replay called"), create=True),
            mock.patch.object(P4, "generate_precommit_contract", side_effect=AssertionError("manifest generation called"), create=True),
        )
        with patches[0], patches[1], patches[2]:
            if any(original_exists(path) for path in result_paths):
                with mock.patch.object(Path, "exists", new=precommit_phase_exists):
                    summary = verify_precommit()
            else:
                summary = verify_precommit()
        self.assertEqual(summary["scope_ceiling"], P4.MAXIMUM_STATUS)
        self.assertEqual(summary["required_parent_commit"], PARENT_COMMIT)
        self.assertEqual(summary["required_parent_status"], PARENT_STATUS)

    def test_precommit_mutations_duplicate_keys_float_tokens_and_placeholders_fail(self) -> None:
        precommit = self._precommit()
        candidate = copy.deepcopy(precommit)
        candidate["required_parent_commit"] = "0" * 40
        with self.assertRaises((P4.SchemaError, P4.VerificationError)):
            P4.validate_precommit_contract(candidate, verify_source_files=False)
        candidate = copy.deepcopy(precommit)
        candidate["runner_staged_files"].append(P4.P3_RESULT_CONTRACT_NAME)
        with self.assertRaises((P4.SchemaError, P4.VerificationError)):
            P4.validate_precommit_contract(candidate, verify_source_files=False)
        with self.assertRaises(P4.SchemaError):
            P4.P3.strict_json_loads(b'{"x":1,"x":2}', source="duplicate")
        with self.assertRaises(P4.SchemaError):
            P4.P3.strict_json_loads(b'{"x":1.5}', source="float")
        raw = (BASE / P4.PRECOMMIT_CONTRACT_NAME).read_bytes()
        self.assertNotIn(b"PENDING_SHA256", raw)
        self.assertNotIn(b"PLACEHOLDER", raw)
        for forbidden in self.policy["forbidden_formal_result_pins"]:
            self.assertNotRegex(raw, re.compile(rb'"' + re.escape(forbidden.encode()) + rb'"\s*:'))


if __name__ == "__main__":
    unittest.main()
