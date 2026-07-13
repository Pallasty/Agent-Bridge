#!/usr/bin/env python3
"""Regression tests for the fail-closed L=8 magnetization step-3 child."""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import unittest
import zlib
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = load_module(
    "hubbard_l8_magnetization_interval_step3_checker",
    "hubbard_l8_magnetization_interval_step3_checker.py",
)
IMMEDIATE = load_module(
    "hubbard_l8_observable_interval_two_step_checker_for_step3_tests",
    "hubbard_l8_observable_interval_two_step_checker.py",
)
ROOT = load_module(
    "hubbard_l8_observable_interval_step_checker_for_step3_tests",
    "hubbard_l8_observable_interval_step_checker.py",
)


class HubbardL8MagnetizationIntervalStep3CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        contract_path = HERE / "hubbard_l8_magnetization_interval_step3_contract.json"
        certificate_path = HERE / "hubbard_l8_magnetization_interval_step3_template.json"
        cls.contract = CHECKER.load_strict_json(contract_path)
        cls.certificate = CHECKER.load_strict_json(certificate_path)
        # The sole public/full verification in this test process.  Every
        # adversarial certificate test below calls the internal verifier with
        # this already-established witness mocked in.
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)
        if cls.positive.get("verified") is not True:
            raise AssertionError(cls.positive)
        cls.witness = cls.positive["recomputed_witness"]

        cls.immediate_contract = IMMEDIATE.load_strict_json(
            HERE / "hubbard_l8_observable_interval_two_step_contract.json"
        )
        cls.immediate_certificate = IMMEDIATE.load_strict_json(
            HERE / "hubbard_l8_observable_interval_two_step_template.json"
        )
        cls.parent_claim = next(
            item
            for item in cls.immediate_certificate["witness_claim"]["child_witnesses"]
            if item["observable_id"] == CHECKER.OBSERVABLE_ID
        )
        cls.input_spec = next(
            spec
            for spec in IMMEDIATE.CHECKPOINT_SPECS
            if spec["observable_id"] == CHECKER.OBSERVABLE_ID
            and spec["step_index"] == CHECKER.INPUT_STEP_INDEX
        )
        cls.output_spec = dict(CHECKER.OUTPUT_CHECKPOINT_SPEC)
        cls.sidecars = {
            2: cls.decode_sidecar(cls.input_spec),
            3: cls.decode_sidecar(cls.output_spec),
        }

    @classmethod
    def decode_sidecar(cls, spec):
        encoded = (HERE / spec["relative_path"]).read_bytes()
        compressed = IMMEDIATE._canonical_b85_decode(
            encoded, pathlib.Path(spec["relative_path"]).name
        )
        raw = IMMEDIATE._bounded_zlib_decompress(
            compressed, pathlib.Path(spec["relative_path"]).name
        )
        payload = IMMEDIATE._strict_json_bytes(
            raw,
            pathlib.Path(spec["relative_path"]).name,
            CHECKER.RESOURCE_LIMITS["max_sidecar_raw_bytes"],
        )
        expansion = {
            (int(record[0], 16), int(record[1], 16)): (
                int(record[2]),
                int(record[3]),
            )
            for record in payload["terms"]
        }
        return {
            "spec": spec,
            "encoded": encoded,
            "compressed": compressed,
            "raw": raw,
            "payload": payload,
            "expansion": expansion,
        }

    def internal_verify(self, contract=None, certificate=None):
        with mock.patch.object(
            CHECKER, "recompute_witness", return_value=self.witness
        ):
            return CHECKER._verify_certificate_impl(
                self.contract if contract is None else contract,
                self.certificate if certificate is None else certificate,
            )

    def test_01_positive_status_is_narrow(self) -> None:
        self.assertEqual(
            self.positive["status"],
            "VERIFIED_L8_MAGNETIZATION_STEP3_MAPPED_INTERVAL_CHILD_SUBCERTIFICATE",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])
        self.assertEqual(self.positive["errors"], [])

    def test_02_scope_stops_at_one_magnetization_child(self) -> None:
        scope = self.positive["scope_claims"]
        self.assertEqual(scope["double_occupancy_step_three"], "NOT_ASSESSED")
        self.assertEqual(scope["remaining_97_mapped_steps"], "NOT_ASSESSED")
        self.assertEqual(
            scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED"
        )
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_03_decision_does_not_promote_other_observables_or_steps(self) -> None:
        decision = self.witness["decision"]
        self.assertTrue(decision["magnetization_step3_fixed_K_child_closed"])
        self.assertFalse(decision["double_occupancy_step3_certified"])
        self.assertFalse(decision["remaining_97_steps_certified"])
        self.assertFalse(decision["full_R100_or_exact_Hubbard_error_certified"])

    def test_04_contract_pins_exact_checker_source(self) -> None:
        source = (HERE / "hubbard_l8_magnetization_interval_step3_checker.py").read_bytes()
        self.assertEqual(self.contract["checker_source_sha256"], hashlib.sha256(source).hexdigest())

    def test_05_immediate_parent_triple_is_same_byte_pinned(self) -> None:
        self.assertEqual(len(CHECKER.SOURCE_PINS), 3)
        self.assertEqual(
            CHECKER.RESOURCE_LIMITS["max_dependency_files"], len(CHECKER.SOURCE_PINS)
        )
        for pin in CHECKER.SOURCE_PINS:
            payload = (HERE / pin["relative_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), pin["sha256"])

    def test_06_dependency_DAG_excludes_self_and_has_depth_two_parent(self) -> None:
        paths = [pin["relative_path"] for pin in CHECKER.SOURCE_PINS]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertNotIn(CHECKER.SELF_NAME, paths)
        self.assertEqual(
            IMMEDIATE.WORKLOAD_IDENTITY["certified_repeated_step_count"],
            CHECKER.INPUT_STEP_INDEX,
        )
        self.assertNotEqual(IMMEDIATE.CHECKER_FINGERPRINT, CHECKER.CHECKER_FINGERPRINT)

    def test_07_immediate_parent_positive_identity_is_exact(self) -> None:
        parent = self.witness["immediate_parent"]
        self.assertEqual(parent["status"], CHECKER.IMMEDIATE_PARENT_POSITIVE_STATUS)
        self.assertTrue(parent["verified"])
        self.assertEqual(parent["checker_source_sha256"], CHECKER.SOURCE_PINS[0]["sha256"])
        self.assertEqual(parent["contract_sha256"], CHECKER.SOURCE_PINS[1]["sha256"])
        self.assertEqual(parent["certificate_sha256"], CHECKER.SOURCE_PINS[2]["sha256"])
        self.assertEqual(
            parent["expected_witness_sha256"],
            self.immediate_contract["expected_witness_sha256"],
        )

    def test_08_parent_selection_is_exclusively_magnetization_depth_two(self) -> None:
        parent = self.witness["immediate_parent"]
        self.assertEqual(parent["selected_parent_observable_id"], "staggered_magnetization")
        self.assertEqual(parent["selected_parent_depth"], 2)
        self.assertEqual(self.witness["observable_id"], "staggered_magnetization")
        self.assertEqual((self.witness["input_step_index"], self.witness["output_step_index"]), (2, 3))

    def test_09_wrong_parent_observable_or_depth_is_rejected(self) -> None:
        wrong_observable = copy.deepcopy(self.immediate_certificate["witness_claim"])
        wrong_observable["child_witnesses"] = [
            item for item in wrong_observable["child_witnesses"]
            if item["observable_id"] != CHECKER.OBSERVABLE_ID
        ]
        with self.assertRaisesRegex(CHECKER.VerificationError, "magnetization claim"):
            CHECKER._select_parent_magnetization_claim(wrong_observable)
        wrong_depth = copy.deepcopy(self.immediate_certificate["witness_claim"])
        claim = next(
            item for item in wrong_depth["child_witnesses"]
            if item["observable_id"] == CHECKER.OBSERVABLE_ID
        )
        claim["child_step_index"] = 1
        with self.assertRaisesRegex(CHECKER.VerificationError, "wrong depth"):
            CHECKER._select_parent_magnetization_claim(wrong_depth)

    def test_10_witness_digest_matches_contract(self) -> None:
        self.assertEqual(
            CHECKER.canonical_sha256(self.witness),
            self.contract["expected_witness_sha256"],
        )

    def test_11_both_boundary_transports_have_exact_hashes(self) -> None:
        total = 0
        for sidecar in self.sidecars.values():
            spec = sidecar["spec"]
            total += len(sidecar["encoded"])
            self.assertEqual(hashlib.sha256(sidecar["encoded"]).hexdigest(), spec["encoded_sha256"])
            self.assertEqual(hashlib.sha256(sidecar["compressed"]).hexdigest(), spec["compressed_sha256"])
            self.assertEqual(hashlib.sha256(sidecar["raw"]).hexdigest(), spec["raw_sha256"])
        self.assertLessEqual(total, CHECKER.RESOURCE_LIMITS["max_total_sidecar_encoded_bytes"])

    def test_12_both_boundary_codecs_are_canonical_and_bounded(self) -> None:
        for sidecar in self.sidecars.values():
            encoded = sidecar["encoded"]
            lines = encoded[:-1].split(b"\n")
            self.assertTrue(encoded.endswith(b"\n"))
            self.assertNotIn(b"\r", encoded)
            self.assertTrue(all(len(line) == 100 for line in lines[:-1]))
            self.assertTrue(1 <= len(lines[-1]) <= 100)
            self.assertEqual(base64.b85encode(sidecar["compressed"]), b"".join(lines))
            self.assertLessEqual(len(encoded), CHECKER.RESOURCE_LIMITS["max_sidecar_encoded_bytes"])
            self.assertLessEqual(len(sidecar["raw"]), CHECKER.RESOURCE_LIMITS["max_sidecar_raw_bytes"])

    def test_13_both_boundary_payloads_are_canonical_and_exact_shape(self) -> None:
        for sidecar in self.sidecars.values():
            payload = sidecar["payload"]
            self.assertEqual(set(payload), {"format", "state", "state_sha256", "terms"})
            self.assertEqual(payload["format"], CHECKER.CHECKPOINT_FORMAT)
            self.assertEqual(IMMEDIATE._canonical_bytes(payload), sidecar["raw"])
            self.assertEqual(len(payload["terms"]), 65_536)

    def test_14_state_digests_and_semantic_expansions_are_exact(self) -> None:
        for sidecar in self.sidecars.values():
            payload = sidecar["payload"]
            self.assertEqual(
                CHECKER.canonical_sha256(payload["state"]), payload["state_sha256"]
            )
            self.assertEqual(
                ROOT._tick_digest(sidecar["expansion"]),
                payload["state"]["expansion_sha256"],
            )

    def test_15_terms_are_strictly_sorted_canonical_sparse_intervals(self) -> None:
        for sidecar in self.sidecars.values():
            records = sidecar["payload"]["terms"]
            keys = [(int(record[0], 16), int(record[1], 16)) for record in records]
            self.assertEqual(keys, sorted(keys))
            self.assertEqual(len(keys), len(set(keys)))
            for x_mask, z_mask, lower, upper in records:
                self.assertEqual(hex(int(x_mask, 16)), x_mask)
                self.assertEqual(hex(int(z_mask, 16)), z_mask)
                self.assertLessEqual(int(lower), int(upper))
                self.assertNotEqual((int(lower), int(upper)), (0, 0))

    def test_16_boundary_expectations_match_semantic_expansions(self) -> None:
        neel = ROOT._neel_basis()
        for sidecar in self.sidecars.values():
            expectation = ROOT._expectation_ticks(sidecar["expansion"], neel)
            state = sidecar["payload"]["state"]
            self.assertEqual(
                expectation,
                (
                    int(state["retained_Neel_expectation_lower_ticks"]),
                    int(state["retained_Neel_expectation_upper_ticks"]),
                ),
            )

    def test_17_boundary_two_equals_immediate_parent_output(self) -> None:
        sidecar = self.sidecars[2]["payload"]
        state = sidecar["state"]
        self.assertEqual(sidecar["state_sha256"], self.parent_claim["output_state_sha256"])
        self.assertEqual(state["expansion_sha256"], self.parent_claim["output_expansion_sha256"])
        self.assertEqual(
            state["cumulative_dropped_l1_ticks"],
            self.parent_claim["output_cumulative_dropped_l1_ticks"],
        )
        self.assertEqual(
            self.input_spec["encoded_sha256"],
            self.parent_claim["transition_record"]["output_encoded_file_sha256"],
        )

    def test_18_boundary_three_uses_exact_state_v2_schema(self) -> None:
        state = self.sidecars[3]["payload"]["state"]
        expected_keys = {
            "schema_version", "state_fingerprint", "profile_id", "observable_id",
            "step_index", "heisenberg_direction", "producer_fingerprint",
            "root_checker_source_sha256", "root_expected_witness_sha256",
            "immediate_parent_checker_source_sha256",
            "immediate_parent_expected_witness_sha256",
            "previous_transition_sha256", "transition_policy_sha256",
            "backprop_gate_records_sha256", "tick_denominator", "term_count",
            "expansion_sha256", "cumulative_dropped_l1_ticks",
            "retained_Neel_expectation_lower_ticks",
            "retained_Neel_expectation_upper_ticks",
        }
        self.assertEqual(set(state), expected_keys)
        self.assertEqual(state["schema_version"], 2)
        self.assertEqual(state["state_fingerprint"], CHECKER.STATE_FINGERPRINT)
        self.assertEqual(state["producer_fingerprint"], CHECKER.CHECKER_FINGERPRINT)
        self.assertEqual(state["step_index"], 3)
        self.assertEqual(state["term_count"], 65_536)

    def test_19_state_v2_binds_parent_transition_policy_and_root(self) -> None:
        state = self.sidecars[3]["payload"]["state"]
        self.assertEqual(state["root_checker_source_sha256"], CHECKER.TRANSITION_POLICY["root_arithmetic_checker_sha256"])
        self.assertEqual(state["immediate_parent_checker_source_sha256"], CHECKER.SOURCE_PINS[0]["sha256"])
        self.assertEqual(state["immediate_parent_expected_witness_sha256"], self.immediate_contract["expected_witness_sha256"])
        self.assertEqual(state["previous_transition_sha256"], self.parent_claim["transition_sha256"])
        self.assertEqual(state["transition_policy_sha256"], CHECKER.TRANSITION_POLICY_SHA256)
        self.assertEqual(state["backprop_gate_records_sha256"], CHECKER.TRANSITION_POLICY["backprop_gate_records_sha256"])

    def test_20_boundary_three_exact_hashes_are_frozen(self) -> None:
        state = self.sidecars[3]["payload"]["state"]
        self.assertEqual(self.output_spec["encoded_sha256"], "91aecef5a3b79279e394c8995072d19565f4898e0ba29ddd7685ea9e535d9c84")
        self.assertEqual(self.output_spec["compressed_sha256"], "b235497f28f79aaed6e2266a5d45e11539893bcbf0aebc495ca30cab9558867f")
        self.assertEqual(self.output_spec["raw_sha256"], "61fc4fb5d65c18ae64134ff829f6de184786a8f86671760b78433e54a542137a")
        self.assertEqual(self.sidecars[3]["payload"]["state_sha256"], "093e4ccd1df0170afa357a93fd64656ff98e978192f9dc1dc35ef6a4d1a26add")
        self.assertEqual(state["expansion_sha256"], "3ce27ae55f05b8c2a71577a99f47af8b50563aaf7221f9f4e48b551d902e86ff")

    def test_21_transition_policy_digest_is_canonical_and_everywhere(self) -> None:
        self.assertEqual(CHECKER.canonical_sha256(CHECKER.TRANSITION_POLICY), CHECKER.TRANSITION_POLICY_SHA256)
        self.assertEqual(self.contract["transition_policy_sha256"], CHECKER.TRANSITION_POLICY_SHA256)
        self.assertEqual(self.witness["transition_policy_sha256"], CHECKER.TRANSITION_POLICY_SHA256)
        self.assertEqual(self.witness["transition_record"]["transition_policy_sha256"], CHECKER.TRANSITION_POLICY_SHA256)

    def test_22_previous_transition_anchor_is_exact_and_adjacent(self) -> None:
        expected = self.parent_claim["transition_sha256"]
        self.assertEqual(expected, "019b813fcd2ff64b419d091785b78a9cb57dc3ccd4c35140059fc5e0279fed27")
        self.assertEqual(self.witness["immediate_parent"]["previous_transition_sha256"], expected)
        transition = self.witness["transition_record"]
        self.assertEqual(transition["previous_transition_sha256"], expected)
        self.assertEqual((transition["input_step_index"], transition["output_step_index"]), (2, 3))
        self.assertEqual(transition["observable_id"], CHECKER.OBSERVABLE_ID)

    def test_23_transition_binds_both_boundaries_and_parent(self) -> None:
        transition = self.witness["transition_record"]
        for field in ("input_state_sha256", "output_state_sha256", "input_expansion_sha256", "output_expansion_sha256"):
            self.assertEqual(transition[field], self.witness[field])
        self.assertEqual(transition["input_encoded_file_sha256"], self.input_spec["encoded_sha256"])
        self.assertEqual(transition["output_encoded_file_sha256"], self.output_spec["encoded_sha256"])
        self.assertEqual(transition["immediate_parent_checker_source_sha256"], CHECKER.SOURCE_PINS[0]["sha256"])
        self.assertEqual(transition["immediate_parent_expected_witness_sha256"], self.immediate_contract["expected_witness_sha256"])
        self.assertEqual(CHECKER.canonical_sha256(transition), self.witness["transition_sha256"])

    def test_24_step_three_is_one_complete_unfused_boundary_step(self) -> None:
        transition = self.witness["transition_record"]
        self.assertEqual(CHECKER.EXPECTED_STAGE_COUNT, 9)
        self.assertEqual(transition["gate_count"], 1_152)
        self.assertEqual(transition["checkpoint_count"], 144)
        self.assertFalse(transition["cross_step_fusion_used"])
        self.assertFalse(CHECKER.TRANSITION_POLICY["cross_step_H1_half_stage_fusion"])
        self.assertEqual(transition["backprop_gate_records_sha256"], "8504eae718b7a670fa71b79c789691e70a59365f0876f8acfdd4ea8dceee2df5")

    def test_25_stage_records_have_fixed_reverse_palindrome_order(self) -> None:
        stages = self.witness["stage_records"]
        self.assertEqual([stage["group"] for stage in stages], ["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"])
        self.assertEqual([stage["backprop_stage_index"] for stage in stages], list(range(9)))
        self.assertEqual([stage["forward_stage_index"] for stage in stages], list(reversed(range(9))))
        self.assertTrue(all(stage["child_step_index"] == 3 for stage in stages))

    def test_26_stage_ledger_sums_exactly_to_d3(self) -> None:
        stages = self.witness["stage_records"]
        self.assertEqual(sum(int(stage["dropped_l1_ticks"]) for stage in stages), int(self.witness["child_dropped_l1_ticks"]))
        self.assertEqual(stages[-1]["child_cumulative_dropped_l1_ticks"], self.witness["child_dropped_l1_ticks"])
        self.assertTrue(all(stage["start_term_count"] == 65_536 for stage in stages))
        self.assertTrue(all(stage["end_retained_term_count"] == 65_536 for stage in stages))

    def test_27_checkpoint_ledger_is_fixed_and_transition_bound(self) -> None:
        self.assertEqual(self.witness["checkpoint_count"], 144)
        self.assertEqual(
            self.witness["checkpoint_ledger_sha256"],
            "4a9bc1f38fbe21ad355b254d47db06ac6fabb1aab973cda11245fde896825ad2",
        )
        self.assertEqual(self.witness["transition_record"]["checkpoint_ledger_sha256"], self.witness["checkpoint_ledger_sha256"])
        self.assertEqual(
            self.witness["transition_sha256"],
            "a02d636d4e511f2399ddaa069ba443225bb8259dd8a9e3e5203ca2e21aa7a73d",
        )

    def test_28_exact_step_three_ticks_and_drops_are_frozen(self) -> None:
        self.assertEqual(self.witness["input_cumulative_dropped_l1_ticks"], "211995779549182")
        self.assertEqual(self.witness["child_dropped_l1_ticks"], "1479500890039114")
        self.assertEqual(self.witness["output_cumulative_dropped_l1_ticks"], "1691496669588296")
        self.assertEqual(
            self.witness["final_retained_Neel_expectation_interval"],
            {"lower_ticks": "18331393468073024166", "upper_ticks": "18331393468073066674"},
        )

    def test_29_E3_recurrence_is_exact_integer_addition(self) -> None:
        self.assertEqual(
            int(self.witness["output_cumulative_dropped_l1_ticks"]),
            int(self.witness["input_cumulative_dropped_l1_ticks"])
            + int(self.witness["child_dropped_l1_ticks"]),
        )
        self.assertTrue(self.witness["drop_recurrence_E3_equals_E2_plus_d3"])

    def test_30_declared_interval_is_retained_expanded_by_E3(self) -> None:
        retained = self.witness["final_retained_Neel_expectation_interval"]
        declared = self.witness["declared_three_step_untruncated_mapped_circuit_Neel_expectation_interval"]
        error = int(self.witness["output_cumulative_dropped_l1_ticks"])
        self.assertEqual(int(declared["lower_ticks"]), int(retained["lower_ticks"]) - error)
        self.assertEqual(int(declared["upper_ticks"]), int(retained["upper_ticks"]) + error)
        self.assertEqual(
            declared,
            {"lower_ticks": "18329701971403435870", "upper_ticks": "18333084964742654970"},
        )

    def test_31_dynamic_resources_are_exact_and_bounded(self) -> None:
        usage = self.witness["resource_usage"]
        self.assertEqual(usage["term_gate_visits"], 83_365_144)
        self.assertEqual(usage["peak_single_expansion_term_count"], 92_964)
        self.assertEqual(usage["maximum_expansion_coefficient_tick_bits"], 57)
        self.assertEqual(usage["maximum_product_bits"], 121)
        self.assertEqual(usage["multiplication_grid_rounding_L1_upper_scaled_ticks_squared"], "109647786942732119112169677")
        self.assertLessEqual(usage["term_gate_visits"], CHECKER.RESOURCE_LIMITS["max_term_gate_visits_per_child"])
        self.assertLessEqual(usage["peak_single_expansion_term_count"], CHECKER.RESOURCE_LIMITS["max_single_expansion_terms"])

    def test_32_boundary_custody_record_pins_both_raw_files(self) -> None:
        custody = self.witness["boundary_sidecar_custody"]
        self.assertEqual(custody["input_relative_path"], self.input_spec["relative_path"])
        self.assertEqual(custody["output_relative_path"], self.output_spec["relative_path"])
        self.assertEqual(custody["input_raw_sha256"], self.input_spec["raw_sha256"])
        self.assertEqual(custody["output_raw_sha256"], self.output_spec["raw_sha256"])
        self.assertEqual(custody["input_encoded_bytes"], 764_408)
        self.assertEqual(custody["output_encoded_bytes"], 805_953)
        self.assertEqual(custody["aggregate_encoded_bytes"], 1_570_361)

    def test_33_internal_contract_validation_succeeds(self) -> None:
        self.assertEqual(CHECKER._validate_contract_impl(self.contract), [])

    def test_34_warm_cache_returns_fresh_copy_and_rechecks_custody(self) -> None:
        cached = CHECKER._canonical_bytes(self.witness)
        with mock.patch.object(CHECKER, "_WITNESS_CACHE_BYTES", cached), mock.patch.object(
            CHECKER, "_read_pinned_sources", wraps=CHECKER._read_pinned_sources
        ) as sources, mock.patch.object(
            CHECKER,
            "_preflight_checkpoint_files",
            wraps=CHECKER._preflight_checkpoint_files,
        ) as sidecars:
            first = CHECKER.recompute_witness()
            second = CHECKER.recompute_witness()
        self.assertEqual(first, self.witness)
        self.assertEqual(second, self.witness)
        self.assertIsNot(first, second)
        self.assertEqual(sources.call_count, 2)
        self.assertEqual(sidecars.call_count, 2)

    def test_35_warm_cache_rejects_sidecar_drift(self) -> None:
        cached = CHECKER._canonical_bytes(self.witness)
        with mock.patch.object(CHECKER, "_WITNESS_CACHE_BYTES", cached), mock.patch.object(
            CHECKER, "_preflight_checkpoint_files",
            side_effect=CHECKER.SchemaError("checkpoint drift"),
        ):
            with self.assertRaisesRegex(CHECKER.SchemaError, "checkpoint drift"):
                CHECKER.recompute_witness()

    def test_36_placeholder_fails_before_dependency_or_sidecar_IO(self) -> None:
        bad = dict(CHECKER.OUTPUT_CHECKPOINT_SPEC)
        bad["encoded_sha256"] = "__PLACEHOLDER_PROBE__"
        with mock.patch.object(CHECKER, "OUTPUT_CHECKPOINT_SPEC", bad), mock.patch.object(
            CHECKER, "_WITNESS_CACHE_BYTES", None
        ), mock.patch.object(CHECKER, "_read_pinned_sources") as sources, mock.patch.object(
            CHECKER, "_preflight_checkpoint_files"
        ) as sidecars:
            with self.assertRaisesRegex(CHECKER.SchemaError, "unresolved placeholder"):
                CHECKER.recompute_witness()
        sources.assert_not_called()
        sidecars.assert_not_called()

    def test_37_dependency_self_cycle_fails_before_IO(self) -> None:
        bad = list(copy.deepcopy(CHECKER.SOURCE_PINS))
        bad[0]["relative_path"] = CHECKER.SELF_NAME
        with mock.patch.object(CHECKER, "SOURCE_PINS", tuple(bad)), mock.patch.object(
            CHECKER, "_read_pinned_sources"
        ) as reader:
            with self.assertRaisesRegex(CHECKER.SchemaError, "self-cycle"):
                CHECKER._preflight_resolved_pins()
        reader.assert_not_called()

    def test_38_output_sidecar_encoded_pin_tamper_is_rejected(self) -> None:
        bad = dict(CHECKER.OUTPUT_CHECKPOINT_SPEC)
        bad["encoded_sha256"] = "0" * 64
        expected_state = self.sidecars[3]["payload"]["state"]
        with mock.patch.object(CHECKER, "OUTPUT_CHECKPOINT_SPEC", bad):
            with self.assertRaisesRegex(CHECKER.SchemaError, "encoded sidecar hash mismatch"):
                CHECKER._load_boundary_three(IMMEDIATE, ROOT, expected_state)

    def test_39_output_state_v2_tamper_is_rejected(self) -> None:
        expected_state = copy.deepcopy(self.sidecars[3]["payload"]["state"])
        expected_state["previous_transition_sha256"] = "0" * 64
        with self.assertRaisesRegex(CHECKER.VerificationError, "state metadata mismatch"):
            CHECKER._load_boundary_three(IMMEDIATE, ROOT, expected_state)

    def test_40_contract_and_certificate_exact_shapes_are_enforced(self) -> None:
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["unexpected"] = None
        bad_certificate = copy.deepcopy(self.certificate)
        bad_certificate["schema_version"] = 1.0
        self.assertTrue(CHECKER._validate_contract_impl(bad_contract))
        self.assertEqual(self.internal_verify(certificate=bad_certificate)["status"], "INVALID_SCHEMA")

    def test_41_contract_policy_and_source_tampers_are_invalid_schema(self) -> None:
        bad_source = copy.deepcopy(self.contract)
        bad_source["source_pins"][0]["sha256"] = "0" * 64
        bad_policy = copy.deepcopy(self.contract)
        bad_policy["transition_policy_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(contract=bad_source)["status"], "INVALID_SCHEMA")
        self.assertEqual(self.internal_verify(contract=bad_policy)["status"], "INVALID_SCHEMA")

    def test_42_witness_and_transition_tampers_are_verification_failed(self) -> None:
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["expected_witness_sha256"] = "0" * 64
        bad_certificate = copy.deepcopy(self.certificate)
        bad_certificate["witness_claim"]["transition_record"]["previous_transition_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(contract=bad_contract)["status"], "VERIFICATION_FAILED")
        self.assertEqual(self.internal_verify(certificate=bad_certificate)["status"], "VERIFICATION_FAILED")

    def test_43_scope_overclaim_is_invalid_schema(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["remaining_97_mapped_steps"] = True
        result = self.internal_verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_44_source_drift_is_rejected_before_compile_or_exec(self) -> None:
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", return_value=b"drift"
        ), mock.patch.object(
            CHECKER.types, "ModuleType", side_effect=AssertionError("must not execute")
        ) as constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        constructor.assert_not_called()

    def test_45_failure_clears_every_positive_scope_claim(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 2
        result = self.internal_verify(certificate=bad)
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])

    def test_46_CLI_always_returns_one_even_for_positive_result(self) -> None:
        fake = {
            "status": CHECKER.MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
        }
        stdout = io.StringIO()
        with mock.patch.object(CHECKER, "_preflight_resolved_pins"), mock.patch.object(
            CHECKER, "load_strict_json", return_value={}
        ), mock.patch.object(
            CHECKER, "verify_certificate", return_value=fake
        ), contextlib.redirect_stdout(stdout):
            self.assertEqual(CHECKER.main(["contract.json", "certificate.json"]), 1)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)
        self.assertFalse(output["ready_gate_eligible"])


if __name__ == "__main__":
    unittest.main()
