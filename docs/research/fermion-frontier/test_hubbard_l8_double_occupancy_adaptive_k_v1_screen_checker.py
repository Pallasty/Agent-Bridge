#!/usr/bin/env python3
"""Regression tests for the L=8 double-occupancy adaptive-K v1 screen."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import inspect
import io
import json
import pathlib
import types
import unittest
from fractions import Fraction
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
CHECKER_FILE = "hubbard_l8_double_occupancy_adaptive_k_v1_screen_checker.py"
CONTRACT_FILE = "hubbard_l8_double_occupancy_adaptive_k_v1_screen_contract.json"
CERTIFICATE_FILE = "hubbard_l8_double_occupancy_adaptive_k_v1_screen_template.json"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_module(
    "hubbard_l8_double_occupancy_adaptive_k_v1_screen_checker", CHECKER_FILE
)
ROOT = load_module(
    "hubbard_l8_interval_root_for_adaptive_screen_tests",
    "hubbard_l8_observable_interval_step_checker.py",
)


def canonical_bytes(value):
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def make_mock_attempt():
    """Build a light witness carrying every frozen screen result."""

    E2 = 2_283_149_854_538_588
    B = 4_611_686_018_427_387
    denominator = 14_112
    ledger = []
    previous = E2
    selected_history = []
    for checkpoint, selected_k, drop, after, retained_sha in (
        CHECKER.EXPECTED_COMMITTED_CHECKPOINTS
    ):
        cap = E2 + (checkpoint + 1) * (B - E2) // denominator
        selected_index = CHECKER.CANDIDATE_K_VALUES.index(selected_k)
        candidates = []
        for index, candidate_k in enumerate(CHECKER.CANDIDATE_K_VALUES):
            # Exact unselected drops live in the full fixture.  Mock records
            # preserve the required first-feasible ordering semantics.
            feasible = index >= selected_index
            candidates.append(
                {
                    "candidate_index": index,
                    "K": candidate_k,
                    "drop_ticks": drop if index == selected_index else None,
                    "feasible_under_current_prefix_cap": feasible,
                }
            )
        ledger.append(
            {
                "checkpoint_index_zero_based": checkpoint,
                "checkpoint_number_one_based": checkpoint + 1,
                "checkpoint_status": "SELECTED_FIRST_FEASIBLE_CANDIDATE_AND_COMMITTED",
                "budget_prefix_cap_ticks": str(cap),
                "E_before_ticks": str(previous),
                "prefix_slack_before_selection_ticks": str(cap - previous),
                "candidate_records": candidates,
                "selected_candidate_index": selected_index,
                "selected_K": selected_k,
                "selected_checkpoint_drop_ticks": drop,
                "E_after_ticks": after,
                "retained_expansion_sha256": retained_sha,
            }
        )
        previous = int(after)
        selected_history.append(selected_k)
    failure_candidates = [
        {
            "candidate_index": index,
            "K": K,
            "drop_ticks": drop,
            "E_after_if_selected_ticks": after,
            "feasible_under_current_prefix_cap": False,
        }
        for index, (K, drop, after) in enumerate(CHECKER.EXPECTED_FAILURE_CANDIDATES)
    ]
    failure = {
        "checkpoint_index_zero_based": 6,
        "checkpoint_number_one_based": 7,
        "checkpoint_status": "NO_CANDIDATE_FEASIBLE_CHILD_BOUNDARY_NOT_COMMITTED",
        "budget_prefix_cap_ticks": "2284304882397659",
        "E_before_ticks": "2284127014339880",
        "prefix_slack_before_selection_ticks": "177868057779",
        "candidate_records": failure_candidates,
        "selected_candidate_index": None,
        "selected_K": None,
        "E_after_ticks": None,
        "retained_expansion_sha256": None,
        "smallest_excess_at_max_K_ticks": "251431190419",
    }
    ledger.append(failure)
    return {
        "attempt_status": "INFEASIBLE_AT_CHECKPOINT_7_NO_CHILD_BOUNDARY",
        "input_certified_mapped_depth": 2,
        "output_certified_mapped_depth": 2,
        "attempted_child_step_index": 3,
        "child_boundary_committed": False,
        "completed_checkpoint_count": 6,
        "failure_checkpoint_included_in_ledger": True,
        "failure_checkpoint_index_zero_based": 6,
        "failure_checkpoint_number_one_based": 7,
        "input_boundary_state_sha256": CHECKER.BOUNDARY_STATE_SHA256,
        "input_boundary_expansion_sha256": CHECKER.BOUNDARY_EXPANSION_SHA256,
        "input_parent_transition_sha256": (
            "57b8396e446f01ee6467ea2dee54a25af8bc257dea58ee5ed2b5abe77647fb71"
        ),
        "selected_K_history": selected_history,
        "selected_K_history_sha256": CHECKER.EXPECTED_SELECTED_K_HISTORY_SHA256,
        "checkpoint_ledger": ledger,
        "checkpoint_ledger_sha256": CHECKER.EXPECTED_CHECKPOINT_LEDGER_SHA256,
        "failure_checkpoint_sha256": CHECKER.EXPECTED_FAILURE_CHECKPOINT_SHA256,
        "last_committed_cumulative_drop_ticks": "2284127014339880",
        "failure_prefix_cap_ticks": "2284304882397659",
        "failure_prefix_slack_ticks": "177868057779",
        "failure_smallest_excess_at_max_K_ticks": "251431190419",
        "resources": dict(CHECKER.EXPECTED_RESOURCES),
        "execution_invariants": {
            "same_positive_parent_boundary_used": True,
            "root_globals_monkeypatched": False,
            "single_propagation_per_checkpoint": True,
            "single_ranking_and_suffix_sum_per_checkpoint": True,
            "first_feasible_candidate_selected": True,
            "all_smaller_candidates_recorded_infeasible": True,
            "Neel_expectation_used_for_selection": False,
            "future_gate_or_final_interval_used_for_selection": False,
            "cross_step_fusion_used": False,
            "failed_checkpoint_committed": False,
        },
    }


def make_mock_witness():
    return {
        "profile_id": CHECKER.WORKLOAD_IDENTITY["profile_id"],
        "source_pinned_positive_parent": {
            "status": CHECKER.PARENT_POSITIVE_STATUS,
            "verified": True,
            "same_byte_checker_contract_certificate_executed": True,
            "checker_sha256": CHECKER.SOURCE_PINS[0]["sha256"],
            "contract_sha256": CHECKER.SOURCE_PINS[1]["sha256"],
            "certificate_sha256": CHECKER.SOURCE_PINS[2]["sha256"],
            "expected_witness_sha256": "0" * 64,
        },
        "adaptive_policy_precommit": {
            "policy_id": CHECKER.POLICY_ID,
            "policy_sha256": CHECKER.SOURCE_PINS[3]["sha256"],
            "output_pins_absent_from_policy": True,
            "candidate_K_values": list(CHECKER.CANDIDATE_K_VALUES),
        },
        "boundary_2_custody": {
            "relative_path": CHECKER.BOUNDARY_RELATIVE_PATH,
            "encoded_sha256": CHECKER.BOUNDARY_ENCODED_SHA256,
            "state_sha256": CHECKER.BOUNDARY_STATE_SHA256,
            "expansion_sha256": CHECKER.BOUNDARY_EXPANSION_SHA256,
            "semantic_expansion_loaded_and_verified": True,
        },
        "adaptive_infeasibility_attempt": make_mock_attempt(),
        "decision": {
            "adaptive_K_v1_infeasibility_screen_closed": True,
            "step_3_child_boundary_committed": False,
            "double_occupancy_certified_mapped_depth": 2,
            "new_policy_version_required_for_any_relaxation": True,
            "remaining_97_steps_certified": False,
            "full_R100_or_exact_Hubbard_error_certified": False,
            "physical_reference_qualified": False,
            "ready_gate_eligible": False,
        },
    }


def make_mock_contract_and_certificate(witness):
    contract = CHECKER.expected_contract_body()
    contract["checker_source_sha256"] = hashlib.sha256(
        (HERE / CHECKER_FILE).read_bytes()
    ).hexdigest()
    contract["expected_witness_sha256"] = CHECKER.canonical_sha256(witness)
    certificate = {
        "schema_version": 1,
        "certificate_type": CHECKER.CERTIFICATE_TYPE,
        "contract_fingerprint": CHECKER.CONTRACT_FINGERPRINT,
        "workload_identity": dict(CHECKER.WORKLOAD_IDENTITY),
        "screen_policy": dict(CHECKER.SCREEN_POLICY),
        "witness_claim": witness,
        "scope_claims": dict(CHECKER.SCOPE_CLAIMS),
    }
    return contract, certificate


class MinimalCounter:
    def __init__(self):
        self.term_gate_visits = 0
        self.peak_live_terms = 1
        self.window_peak_live_terms = 1
        self.maximum_expansion_coefficient_tick_bits = 64
        self.maximum_product_bits = 120
        self.multiplication_rounding_l1_scaled_ticks_squared = 0

    def observe(self, expansion):
        self.peak_live_terms = max(self.peak_live_terms, len(expansion))

    def observe_interval(self, _interval):
        return None

    def begin_window(self, expansion):
        self.window_peak_live_terms = len(expansion)


def fake_root_that_mutates(*, retained=False, resources=False):
    root = types.SimpleNamespace()
    root.RETAINED_TERM_CAP = 65_536
    root.RESOURCE_LIMITS = {
        key: CHECKER.RESOURCE_LIMITS[key]
        for key in (
            "max_single_expansion_terms",
            "max_term_gate_visits",
            "max_expansion_coefficient_tick_bits",
            "max_trigonometric_tick_bits",
            "max_product_bits",
        )
    }
    root._independent_bonds = lambda: []
    root._independent_groups = lambda _bonds: {}
    gates = [((0, 1), Fraction(0))] * 8
    stage = {
        "gate_count": 1_152,
        "gates": gates,
        "backprop_stage_index": 0,
        "forward_stage_index": 8,
        "group": "H1",
    }
    root._sequence_records = lambda _groups: (
        [],
        [],
        [stage],
        {"backprop_gate_records_sha256": CHECKER.BACKPROP_GATE_RECORDS_SHA256},
    )
    root._taylor_trig_record = lambda _theta: ((0, 0), (1, 1), {})
    root.PropagationCounter = MinimalCounter
    root._tick_digest = lambda expansion, keys=None: CHECKER.canonical_sha256(
        sorted(expansion if keys is None else keys)
    )
    root._format_fraction = lambda value: f"{value.numerator}/{value.denominator}"
    root._abs_upper = lambda value: max(abs(value[0]), abs(value[1]))

    def propagate(expansion, _generator, _sine, _cosine, counter):
        counter.term_gate_visits += len(expansion)
        if retained:
            root.RETAINED_TERM_CAP += 1
        if resources:
            root.RESOURCE_LIMITS["max_product_bits"] += 1
        return dict(expansion)

    root._propagate_gate = propagate
    return root


class HubbardL8DoubleOccupancyAdaptiveKScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = CHECKER.load_strict_json(
            HERE / "hubbard_l8_double_occupancy_adaptive_k_policy_v1.json"
        )
        cls.contract = CHECKER.load_strict_json(HERE / CONTRACT_FILE)
        cls.certificate = CHECKER.load_strict_json(HERE / CERTIFICATE_FILE)
        cls.full_verify_calls = 0
        cls.full_verify_calls += 1
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)
        if cls.positive.get("verified") is not True:
            raise AssertionError(cls.positive)
        cls.witness = cls.positive["recomputed_witness"]
        cls.attempt = cls.witness["adaptive_infeasibility_attempt"]

    def internal_verify(self, contract=None, certificate=None):
        with mock.patch.object(CHECKER, "recompute_witness", return_value=self.witness):
            return CHECKER._verify_certificate_impl(
                self.contract if contract is None else contract,
                self.certificate if certificate is None else certificate,
            )

    def test_01_public_full_verify_is_called_at_most_once(self):
        self.assertLessEqual(self.full_verify_calls, 1)
        self.assertEqual(self.full_verify_calls, 1)
        self.assertTrue(self.positive["verified"])
        self.assertEqual(self.positive["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)

    def test_02_policy_file_has_exact_source_pin(self):
        payload = (HERE / CHECKER.SOURCE_PINS[3]["relative_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), CHECKER.SOURCE_PINS[3]["sha256"])

    def test_03_all_source_pins_match_same_bytes(self):
        self.assertEqual(len(CHECKER.SOURCE_PINS), 5)
        for pin in CHECKER.SOURCE_PINS:
            payload = (HERE / pin["relative_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), pin["sha256"])

    def test_04_policy_schema_and_identity_validate(self):
        validated = CHECKER._validate_policy(copy.deepcopy(self.policy))
        self.assertEqual(validated["policy_id"], CHECKER.POLICY_ID)
        self.assertEqual(validated["observable_id"], CHECKER.OBSERVABLE_ID)

    def test_05_policy_forbids_output_dependent_selection(self):
        arithmetic = self.policy["arithmetic_and_sequence"]
        self.assertTrue(arithmetic["Neel_expectation_is_forbidden_as_a_K_selection_input"])
        self.assertTrue(arithmetic["future_gates_and_final_interval_are_forbidden_as_K_selection_inputs"])
        precommit = self.policy["precommit_boundary"]
        self.assertTrue(
            precommit[
                "formal_adaptive_step3_execution_started_after_this_policy_was_committed"
            ]
        )
        self.assertFalse(precommit["policy_contains_step3_output_pins"])

    def test_06_policy_candidate_tamper_is_rejected(self):
        policy = copy.deepcopy(self.policy)
        policy["candidate_policy"]["candidate_K_values_in_strict_ascending_order"][1] += 1
        with self.assertRaisesRegex(CHECKER.SchemaError, "candidate K list"):
            CHECKER._validate_policy(policy)

    def test_07_policy_parent_custody_tamper_is_rejected(self):
        policy = copy.deepcopy(self.policy)
        policy["immediate_parent"]["boundary_2_state_sha256"] = "0" * 64
        with self.assertRaisesRegex(CHECKER.SchemaError, "immediate_parent"):
            CHECKER._validate_policy(policy)

    def test_08_policy_budget_tamper_is_rejected(self):
        policy = copy.deepcopy(self.policy)
        policy["truncation_budget"]["maximum_cumulative_drop_ticks"] += 1
        with self.assertRaisesRegex(CHECKER.SchemaError, "truncation_budget"):
            CHECKER._validate_policy(policy)

    def test_09_same_byte_parent_triple_is_required(self):
        self.assertEqual(
            [pin["role"] for pin in CHECKER.SOURCE_PINS[:3]],
            [
                "positive_two_step_parent_checker",
                "positive_two_step_parent_contract",
                "positive_two_step_parent_certificate",
            ],
        )
        source = inspect.getsource(CHECKER._load_positive_parent_and_boundary)
        self.assertIn("two_step.verify_certificate(parent_contract, parent_certificate)", source)
        self.assertIn("same-byte two-step parent execution is not positive", source)

    def test_10_mock_parent_positive_and_boundary_path(self):
        parent_witness = {
            "child_witnesses": [
                {
                    "observable_id": CHECKER.OBSERVABLE_ID,
                    "transition_sha256": self.policy["immediate_parent"][
                        "boundary_2_transition_sha256"
                    ],
                }
            ],
            "root_parent": {
                "expected_witness_sha256": "1" * 64,
                "backprop_gate_records_sha256": CHECKER.BACKPROP_GATE_RECORDS_SHA256,
            },
        }
        parent_contract = {"expected_witness_sha256": CHECKER.canonical_sha256(parent_witness)}
        parent_certificate = {"witness_claim": parent_witness}
        boundary = {
            "state_sha256": CHECKER.BOUNDARY_STATE_SHA256,
            "state": {"expansion_sha256": CHECKER.BOUNDARY_EXPANSION_SHA256},
            "expansion": {},
        }
        two_step = types.SimpleNamespace(
            verify_certificate=mock.Mock(
                return_value={
                    "status": CHECKER.PARENT_POSITIVE_STATUS,
                    "verified": True,
                    "recomputed_witness": parent_witness,
                }
            ),
            CHECKPOINT_SPECS=[
                {
                    "observable_id": CHECKER.OBSERVABLE_ID,
                    "step_index": 2,
                    "relative_path": CHECKER.BOUNDARY_RELATIVE_PATH,
                    "encoded_sha256": CHECKER.BOUNDARY_ENCODED_SHA256,
                }
            ],
            SOURCE_PINS=({"sha256": "2" * 64},),
            _load_checkpoint=mock.Mock(return_value=boundary),
        )
        root = types.SimpleNamespace(
            RESOURCE_LIMITS={
                key: CHECKER.RESOURCE_LIMITS[key]
                for key in (
                    "max_single_expansion_terms",
                    "max_term_gate_visits",
                    "max_expansion_coefficient_tick_bits",
                    "max_trigonometric_tick_bits",
                    "max_product_bits",
                )
            },
            RETAINED_TERM_CAP=65_536,
        )
        sources = {
            CHECKER.SOURCE_PINS[0]["relative_path"]: b"parent",
            CHECKER.SOURCE_PINS[1]["relative_path"]: canonical_bytes(parent_contract),
            CHECKER.SOURCE_PINS[2]["relative_path"]: canonical_bytes(parent_certificate),
            CHECKER.SOURCE_PINS[4]["relative_path"]: b"root",
        }
        with mock.patch.object(
            CHECKER, "_load_module_from_pinned_source", side_effect=[two_step, root]
        ):
            observed = CHECKER._load_positive_parent_and_boundary(
                sources, self.policy
            )
        self.assertIs(observed[0], two_step)
        self.assertIs(observed[1], root)
        self.assertIs(observed[3], boundary)
        two_step.verify_certificate.assert_called_once_with(
            parent_contract, parent_certificate
        )

    def test_11_boundary_two_encoded_custody(self):
        payload = (HERE / CHECKER.BOUNDARY_RELATIVE_PATH).read_bytes()
        self.assertLessEqual(len(payload), CHECKER.RESOURCE_LIMITS["max_boundary_encoded_bytes"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), CHECKER.BOUNDARY_ENCODED_SHA256)
        CHECKER._preflight_boundary_sidecar()

    def test_12_boundary_two_policy_state_and_expansion_pins(self):
        parent = self.policy["immediate_parent"]
        self.assertEqual(parent["boundary_2_state_sha256"], CHECKER.BOUNDARY_STATE_SHA256)
        self.assertEqual(parent["boundary_2_expansion_sha256"], CHECKER.BOUNDARY_EXPANSION_SHA256)
        self.assertEqual(parent["boundary_2_encoded_sha256"], CHECKER.BOUNDARY_ENCODED_SHA256)

    def test_13_root_arithmetic_globals_match_screen_caps(self):
        self.assertEqual(ROOT.RETAINED_TERM_CAP, 65_536)
        for key in (
            "max_single_expansion_terms",
            "max_term_gate_visits",
            "max_expansion_coefficient_tick_bits",
            "max_trigonometric_tick_bits",
            "max_product_bits",
        ):
            self.assertEqual(ROOT.RESOURCE_LIMITS[key], CHECKER.RESOURCE_LIMITS[key])

    def _assert_mutation_detected(self, *, retained=False, resources=False, pattern=""):
        root = fake_root_that_mutates(retained=retained, resources=resources)
        boundary = {
            "expansion": {(0, 0): (10**18, 10**18)},
            "state": {"cumulative_dropped_l1_ticks": "2283149854538588"},
        }
        parent_witness = {
            "child_witnesses": [
                {"observable_id": CHECKER.OBSERVABLE_ID, "transition_sha256": "0" * 64}
            ]
        }
        with mock.patch.object(CHECKER, "CANDIDATE_K_VALUES", (0,)):
            with self.assertRaisesRegex(CHECKER.VerificationError, pattern):
                CHECKER._run_adaptive_screen(
                    types.SimpleNamespace(), root, self.policy, parent_witness, boundary
                )

    def test_14_root_retained_cap_mutation_is_detected(self):
        self._assert_mutation_detected(retained=True, pattern="retained-term global")

    def test_15_root_resource_global_mutation_is_detected(self):
        self._assert_mutation_detected(resources=True, pattern="resource-limit globals")

    def test_16_candidate_sequence_is_strict_and_bounded(self):
        values = CHECKER.CANDIDATE_K_VALUES
        self.assertEqual(len(values), CHECKER.RESOURCE_LIMITS["max_candidate_count"])
        self.assertTrue(all(left < right for left, right in zip(values, values[1:])))
        self.assertEqual(values[-1], CHECKER.RESOURCE_LIMITS["max_candidate_K"])

    def test_17_suffix_drop_and_first_feasible_selection(self):
        ranked_abs = [9, 5, 2, 1]
        suffix = [0] * (len(ranked_abs) + 1)
        for index in range(len(ranked_abs) - 1, -1, -1):
            suffix[index] = suffix[index + 1] + ranked_abs[index]
        candidates = (1, 2, 3, 4)
        cumulative, cap = 100, 102
        drops = [suffix[min(K, len(ranked_abs))] for K in candidates]
        feasible = [cumulative + drop <= cap for drop in drops]
        selected = next(index for index, value in enumerate(feasible) if value)
        self.assertEqual(drops, [8, 3, 1, 0])
        self.assertEqual(feasible, [False, False, True, True])
        self.assertEqual(candidates[selected], 3)

    def test_18_ranking_tie_break_is_numeric_x_then_z(self):
        expansion = {(2, 1): (-5, 5), (1, 3): (-5, 5), (1, 2): (-5, 5)}
        ranked = sorted(
            expansion,
            key=lambda key: (-ROOT._abs_upper(expansion[key]), key[0], key[1]),
        )
        self.assertEqual(ranked, [(1, 2), (1, 3), (2, 1)])

    def test_19_selected_history_exact(self):
        self.assertEqual(tuple(self.attempt["selected_K_history"]), CHECKER.EXPECTED_SELECTED_K_HISTORY)
        self.assertEqual(self.attempt["selected_K_history_sha256"], CHECKER.EXPECTED_SELECTED_K_HISTORY_SHA256)

    def test_20_checkpoint_ledger_digest_exact(self):
        self.assertEqual(self.attempt["checkpoint_ledger_sha256"], CHECKER.EXPECTED_CHECKPOINT_LEDGER_SHA256)

    def test_21_failure_checkpoint_digest_exact(self):
        self.assertEqual(self.attempt["failure_checkpoint_sha256"], CHECKER.EXPECTED_FAILURE_CHECKPOINT_SHA256)

    def test_22_checkpoint_zero_exact_pin(self):
        self._assert_committed_checkpoint(0)

    def test_23_checkpoint_one_exact_pin(self):
        self._assert_committed_checkpoint(1)

    def test_24_checkpoint_two_exact_pin(self):
        self._assert_committed_checkpoint(2)

    def test_25_checkpoint_three_exact_pin(self):
        self._assert_committed_checkpoint(3)

    def test_26_checkpoint_four_exact_pin(self):
        self._assert_committed_checkpoint(4)

    def test_27_checkpoint_five_exact_pin(self):
        self._assert_committed_checkpoint(5)

    def _assert_committed_checkpoint(self, index):
        record = self.attempt["checkpoint_ledger"][index]
        expected = CHECKER.EXPECTED_COMMITTED_CHECKPOINTS[index]
        observed = (
            record["checkpoint_index_zero_based"],
            record["selected_K"],
            record["selected_checkpoint_drop_ticks"],
            record["E_after_ticks"],
            record["retained_expansion_sha256"],
        )
        self.assertEqual(observed, expected)
        selected = record["selected_candidate_index"]
        self.assertTrue(all(not item["feasible_under_current_prefix_cap"] for item in record["candidate_records"][:selected]))

    def test_28_checkpoint_six_is_exact_failure(self):
        failure = self.attempt["checkpoint_ledger"][6]
        self.assertEqual(failure["checkpoint_index_zero_based"], 6)
        self.assertEqual(failure["checkpoint_number_one_based"], 7)
        self.assertIsNone(failure["selected_K"])
        self.assertIsNone(failure["E_after_ticks"])
        self.assertIn("NO_CANDIDATE_FEASIBLE", failure["checkpoint_status"])

    def test_29_all_failure_candidates_are_exact_and_infeasible(self):
        failure = self.attempt["checkpoint_ledger"][6]
        observed = tuple(
            (item["K"], item["drop_ticks"], item["E_after_if_selected_ticks"])
            for item in failure["candidate_records"]
        )
        self.assertEqual(observed, CHECKER.EXPECTED_FAILURE_CANDIDATES)
        self.assertTrue(all(not item["feasible_under_current_prefix_cap"] for item in failure["candidate_records"]))

    def test_30_prefix_budget_formula_exact(self):
        E2 = self.policy["truncation_budget"]["input_cumulative_drop_ticks"]
        B = self.policy["truncation_budget"]["maximum_cumulative_drop_ticks"]
        Q = self.policy["truncation_budget"]["remaining_checkpoint_count"]
        caps = [E2 + q * (B - E2) // Q for q in (1, 7, 144, Q)]
        self.assertEqual(caps[1], 2_284_304_882_397_659)
        self.assertEqual(caps[2], 2_306_910_427_639_494)
        self.assertEqual(caps[3], B)
        self.assertTrue(caps[0] < caps[1] < caps[2] < caps[3])

    def test_31_failure_prefix_slack_and_excess_exact(self):
        self.assertEqual(self.attempt["failure_prefix_cap_ticks"], "2284304882397659")
        self.assertEqual(self.attempt["failure_prefix_slack_ticks"], "177868057779")
        self.assertEqual(self.attempt["failure_smallest_excess_at_max_K_ticks"], "251431190419")

    def test_32_resource_fixture_exact_and_within_caps(self):
        resources = self.attempt["resources"]
        self.assertEqual(resources, CHECKER.EXPECTED_RESOURCES)
        self.assertLessEqual(resources["term_gate_visits_including_failed_checkpoint"], CHECKER.RESOURCE_LIMITS["max_term_gate_visits"])
        self.assertLessEqual(resources["peak_single_expansion_terms"], CHECKER.RESOURCE_LIMITS["max_single_expansion_terms"])
        self.assertLessEqual(resources["maximum_expansion_coefficient_tick_bits"], CHECKER.RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"])
        self.assertLessEqual(resources["maximum_product_bits"], CHECKER.RESOURCE_LIMITS["max_product_bits"])

    def test_33_cache_hit_rehashes_sources_and_boundary(self):
        original = CHECKER._WITNESS_CACHE_BYTES
        CHECKER._WITNESS_CACHE_BYTES = CHECKER._canonical_bytes(self.witness)
        try:
            with mock.patch.object(CHECKER, "_read_pinned_sources", return_value={}) as sources:
                with mock.patch.object(CHECKER, "_preflight_boundary_sidecar") as sidecar:
                    observed = CHECKER.recompute_witness()
            self.assertEqual(observed, self.witness)
            sources.assert_called_once_with()
            sidecar.assert_called_once_with()
        finally:
            CHECKER._WITNESS_CACHE_BYTES = original

    def test_34_cache_hit_fails_closed_on_sidecar_drift(self):
        original = CHECKER._WITNESS_CACHE_BYTES
        CHECKER._WITNESS_CACHE_BYTES = CHECKER._canonical_bytes(self.witness)
        try:
            with mock.patch.object(CHECKER, "_read_pinned_sources", return_value={}):
                with mock.patch.object(
                    CHECKER,
                    "_preflight_boundary_sidecar",
                    side_effect=CHECKER.SchemaError("boundary drift"),
                ):
                    with self.assertRaisesRegex(CHECKER.SchemaError, "boundary drift"):
                        CHECKER.recompute_witness()
        finally:
            CHECKER._WITNESS_CACHE_BYTES = original

    def test_35_contract_checker_hash_tamper_is_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["checker_source_sha256"] = "0" * 64
        result = self.internal_verify(contract=contract)
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_36_contract_policy_tamper_is_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["screen_policy"]["candidate_K_values"][0] += 1
        result = self.internal_verify(contract=contract)
        self.assertFalse(result["verified"])
        self.assertIn("fixed checker policy", result["errors"][0])

    def test_37_contract_exact_fixture_tamper_is_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["expected_screen_exact"]["failure_checkpoint_index_zero_based"] = 7
        result = self.internal_verify(contract=contract)
        self.assertFalse(result["verified"])

    def test_38_certificate_witness_tamper_is_rejected(self):
        certificate = copy.deepcopy(self.certificate)
        certificate["witness_claim"]["decision"]["step_3_child_boundary_committed"] = True
        result = self.internal_verify(certificate=certificate)
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "VERIFICATION_FAILED")

    def test_39_certificate_scope_tamper_is_rejected(self):
        certificate = copy.deepcopy(self.certificate)
        certificate["scope_claims"]["adaptive_step_3_child_boundary_committed"] = True
        result = self.internal_verify(certificate=certificate)
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "INVALID_SCHEMA")

    def test_40_certificate_extra_key_is_rejected(self):
        certificate = copy.deepcopy(self.certificate)
        certificate["unexpected"] = True
        result = self.internal_verify(certificate=certificate)
        self.assertFalse(result["verified"])
        self.assertIn("keys must exactly equal", result["errors"][0])

    def test_41_positive_and_failure_scopes_remain_narrow(self):
        scope = CHECKER.SCOPE_CLAIMS
        self.assertFalse(scope["adaptive_step_3_child_boundary_committed"])
        self.assertEqual(scope["double_occupancy_certified_mapped_depth"], 2)
        self.assertEqual(scope["remaining_97_mapped_steps"], "NOT_ASSESSED")
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED")
        self.assertFalse(scope["ready_gate_eligible"])
        self.assertEqual(CHECKER.UNVERIFIED_SCOPE_CLAIMS["double_occupancy_certified_mapped_depth"], "NOT_VERIFIED")

    def test_42_failure_does_not_commit_or_advance_depth(self):
        self.assertFalse(self.attempt["child_boundary_committed"])
        self.assertEqual(self.attempt["input_certified_mapped_depth"], 2)
        self.assertEqual(self.attempt["output_certified_mapped_depth"], 2)
        self.assertFalse(self.attempt["execution_invariants"]["failed_checkpoint_committed"])

    def test_43_cli_always_returns_one(self):
        result = {
            "status": CHECKER.MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
            "scope_claims": dict(CHECKER.SCOPE_CLAIMS),
            "errors": [],
        }
        with mock.patch.object(CHECKER, "load_strict_json", side_effect=[{}, {}]):
            with mock.patch.object(CHECKER, "verify_certificate", return_value=result):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    return_code = CHECKER.main(["contract.json", "certificate.json"])
        self.assertEqual(return_code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)


if __name__ == "__main__":
    unittest.main()
