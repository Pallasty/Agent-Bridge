#!/usr/bin/env python3
"""Regression tests for the fail-closed L=8 two-step child checker."""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import tempfile
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
    "hubbard_l8_observable_interval_two_step_checker",
    "hubbard_l8_observable_interval_two_step_checker.py",
)
PARENT = load_module(
    "hubbard_l8_observable_interval_step_checker_for_child_tests",
    "hubbard_l8_observable_interval_step_checker.py",
)


class HubbardL8ObservableIntervalTwoStepCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = CHECKER.load_strict_json(
            HERE / "hubbard_l8_observable_interval_two_step_contract.json"
        )
        cls.certificate = CHECKER.load_strict_json(
            HERE / "hubbard_l8_observable_interval_two_step_template.json"
        )
        # This is the sole public/full two-step recomputation in the process.
        # All certificate tamper tests below mock the already-computed witness.
        cls.positive = CHECKER.verify_certificate(cls.contract, cls.certificate)
        cls.witness = cls.positive["recomputed_witness"]
        cls.children = {
            item["observable_id"]: item
            for item in cls.witness["child_witnesses"]
        }
        cls.parent_contract = PARENT.load_strict_json(
            HERE / "hubbard_l8_observable_interval_step_contract.json"
        )
        cls.parent_certificate = PARENT.load_strict_json(
            HERE / "hubbard_l8_observable_interval_step_template.json"
        )
        cls.parent_claims = {
            item["observable_id"]: item
            for item in cls.parent_certificate["witness_claim"]["observable_claims"]
        }
        cls.sidecars = {}
        for spec in CHECKER.CHECKPOINT_SPECS:
            encoded = (HERE / spec["relative_path"]).read_bytes()
            compressed = CHECKER._canonical_b85_decode(
                encoded, pathlib.Path(spec["relative_path"]).name
            )
            raw = CHECKER._bounded_zlib_decompress(
                compressed, pathlib.Path(spec["relative_path"]).name
            )
            payload = CHECKER._strict_json_bytes(
                raw,
                pathlib.Path(spec["relative_path"]).name,
                CHECKER.RESOURCE_LIMITS["max_sidecar_raw_bytes"],
            )
            cls.sidecars[(spec["observable_id"], spec["step_index"])] = {
                "spec": spec,
                "encoded": encoded,
                "compressed": compressed,
                "raw": raw,
                "payload": payload,
            }

    def internal_verify(self, contract=None, certificate=None):
        with mock.patch.object(
            CHECKER, "recompute_witness", return_value=self.witness
        ):
            return CHECKER._verify_certificate_impl(
                self.contract if contract is None else contract,
                self.certificate if certificate is None else certificate,
            )

    @staticmethod
    def _wrap_b85(compressed: bytes) -> bytes:
        compact = base64.b85encode(compressed)
        width = CHECKER.CANONICAL_B85_LINE_LENGTH
        return b"\n".join(
            compact[index : index + width]
            for index in range(0, len(compact), width)
        ) + b"\n"

    def load_mini_checkpoint(
        self,
        terms=None,
        *,
        state_mutator=None,
        outer_mutator=None,
        raw_encoder=None,
    ):
        """Exercise the real loader cheaply with a two-term canonical fixture."""
        if terms is None:
            terms = [["0x0", "0x0", "1", "1"], ["0x0", "0x1", "2", "2"]]
        baseline = {(0, 0): (1, 1), (0, 1): (2, 2)}
        expectation = PARENT._expectation_ticks(baseline, PARENT._neel_basis())
        state = {
            "schema_version": 1,
            "state_fingerprint": CHECKER.STATE_FINGERPRINT,
            "profile_id": CHECKER.WORKLOAD_IDENTITY["root_profile_id"],
            "observable_id": "staggered_magnetization",
            "step_index": 2,
            "heisenberg_direction": CHECKER.HEISENBERG_DIRECTION,
            "producer_fingerprint": CHECKER.CHECKER_FINGERPRINT,
            "root_checker_source_sha256": CHECKER.SOURCE_PINS[0]["sha256"],
            "root_expected_witness_sha256": self.parent_contract[
                "expected_witness_sha256"
            ],
            "backprop_gate_records_sha256": self.witness["root_parent"][
                "backprop_gate_records_sha256"
            ],
            "tick_denominator": str(CHECKER.TICK_DENOMINATOR),
            "term_count": len(terms),
            "expansion_sha256": PARENT._tick_digest(baseline),
            "cumulative_dropped_l1_ticks": "3",
            "retained_Neel_expectation_lower_ticks": str(expectation[0]),
            "retained_Neel_expectation_upper_ticks": str(expectation[1]),
        }
        if state_mutator is not None:
            state_mutator(state)
        outer = {
            "format": CHECKER.CHECKPOINT_FORMAT,
            "state": state,
            "state_sha256": CHECKER.canonical_sha256(state),
            "terms": terms,
        }
        if outer_mutator is not None:
            outer_mutator(outer)
        raw = (
            CHECKER._canonical_bytes(outer)
            if raw_encoder is None
            else raw_encoder(outer)
        )
        compressed = zlib.compress(raw, 9)
        encoded = self._wrap_b85(compressed)
        spec = {
            "relative_path": (
                "hubbard_l8_interval_checkpoints/"
                "staggered_magnetization_boundary_002.b85"
            ),
            "observable_id": "staggered_magnetization",
            "step_index": 2,
            "encoded_sha256": hashlib.sha256(encoded).hexdigest(),
            "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / spec["relative_path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(encoded)
            with mock.patch.object(CHECKER, "HERE", root), mock.patch.object(
                CHECKER, "RETAINED_TERM_CAP", len(terms)
            ):
                return CHECKER._load_checkpoint(
                    spec,
                    parent=PARENT,
                    parent_source_sha256=CHECKER.SOURCE_PINS[0]["sha256"],
                    parent_expected_witness_sha256=self.parent_contract[
                        "expected_witness_sha256"
                    ],
                    backprop_gate_records_sha256=self.witness["root_parent"][
                        "backprop_gate_records_sha256"
                    ],
                )

    def test_01_positive_status_is_narrow(self) -> None:
        self.assertEqual(
            self.positive["status"],
            "VERIFIED_L8_TWO_STEP_MAPPED_INTERVAL_CHILD_CHAIN_SUBCERTIFICATE",
        )
        self.assertTrue(self.positive["verified"])
        self.assertFalse(self.positive["ready_gate_eligible"])
        self.assertEqual(self.positive["errors"], [])

    def test_02_scope_stops_before_remaining_steps_and_exact_Hubbard(self) -> None:
        scope = self.positive["scope_claims"]
        self.assertEqual(scope["remaining_98_mapped_steps"], "NOT_ASSESSED")
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED")
        self.assertEqual(scope["interval_box_optimality"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_03_decision_routes_step_three_without_R100_overclaim(self) -> None:
        decision = self.witness["decision"]
        self.assertTrue(decision["two_step_mapped_child_chain_closed"])
        self.assertTrue(decision["continue_magnetization_fixed_K_step3_resource_probe"])
        self.assertTrue(decision["double_occupancy_requires_cap_or_adaptive_policy_before_step3"])
        self.assertFalse(decision["remaining_98_parent_child_transitions_certified"])
        self.assertFalse(decision["full_R100_or_exact_Hubbard_error_certified"])

    def test_04_contract_pins_exact_checker_source(self) -> None:
        self.assertEqual(
            self.contract["checker_source_sha256"],
            hashlib.sha256(
                (HERE / "hubbard_l8_observable_interval_two_step_checker.py").read_bytes()
            ).hexdigest(),
        )

    def test_05_every_parent_dependency_is_source_pinned(self) -> None:
        self.assertEqual(len(self.contract["source_pins"]), 3)
        for pin in self.contract["source_pins"]:
            self.assertEqual(
                pin["sha256"],
                hashlib.sha256((HERE / pin["relative_path"]).read_bytes()).hexdigest(),
            )

    def test_06_witness_digest_matches_contract(self) -> None:
        self.assertEqual(
            CHECKER.canonical_sha256(self.witness),
            self.contract["expected_witness_sha256"],
        )

    def test_07_root_parent_status_and_hash_chain_are_exact(self) -> None:
        root = self.witness["root_parent"]
        self.assertEqual(root["status"], CHECKER.PARENT_POSITIVE_STATUS)
        self.assertTrue(root["verified"])
        self.assertEqual(root["checker_source_sha256"], CHECKER.SOURCE_PINS[0]["sha256"])
        self.assertEqual(root["contract_sha256"], CHECKER.SOURCE_PINS[1]["sha256"])
        self.assertEqual(root["certificate_sha256"], CHECKER.SOURCE_PINS[2]["sha256"])
        self.assertEqual(
            root["expected_witness_sha256"],
            self.parent_contract["expected_witness_sha256"],
        )

    def test_08_backprop_sequence_is_inherited_from_parent(self) -> None:
        digest = self.witness["root_parent"]["backprop_gate_records_sha256"]
        self.assertEqual(
            digest,
            self.parent_certificate["witness_claim"]["sequence_identity"][
                "backprop_gate_records_sha256"
            ],
        )
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_09_exactly_four_checkpoint_specs_are_contract_bound(self) -> None:
        self.assertEqual(len(CHECKER.CHECKPOINT_SPECS), 4)
        self.assertEqual(self.contract["checkpoint_specs"], list(CHECKER.CHECKPOINT_SPECS))
        self.assertEqual(
            {(item["observable_id"], item["step_index"]) for item in CHECKER.CHECKPOINT_SPECS},
            {(observable, step) for observable in CHECKER.OBSERVABLES for step in (1, 2)},
        )

    def test_10_checkpoint_codec_claims_are_narrow_and_complete(self) -> None:
        codec = self.witness["checkpoint_codec"]
        self.assertEqual(codec["format"], CHECKER.CHECKPOINT_FORMAT)
        self.assertEqual(codec["state_fingerprint"], CHECKER.STATE_FINGERPRINT)
        self.assertEqual(codec["canonical_b85_line_length"], 100)
        self.assertEqual(codec["checkpoint_count"], 4)
        self.assertTrue(codec["all_encoded_compressed_raw_state_and_expansion_hashes_verified"])
        self.assertTrue(codec["strict_numeric_x_then_z_term_order_verified"])

    def test_11_encoded_hashes_and_aggregate_size_are_exact(self) -> None:
        total = 0
        for item in self.sidecars.values():
            total += len(item["encoded"])
            self.assertEqual(
                hashlib.sha256(item["encoded"]).hexdigest(),
                item["spec"]["encoded_sha256"],
            )
        self.assertEqual(total, self.witness["checkpoint_codec"]["aggregate_encoded_bytes"])
        self.assertLessEqual(total, CHECKER.RESOURCE_LIMITS["max_total_sidecar_encoded_bytes"])

    def test_12_base85_wrapping_is_canonical(self) -> None:
        for item in self.sidecars.values():
            encoded = item["encoded"]
            self.assertTrue(encoded.endswith(b"\n"))
            lines = encoded[:-1].split(b"\n")
            self.assertTrue(all(len(line) == 100 for line in lines[:-1]))
            self.assertTrue(1 <= len(lines[-1]) <= 100)
            self.assertNotIn(b"\r", encoded)

    def test_13_compressed_hashes_and_caps_are_exact(self) -> None:
        for item in self.sidecars.values():
            self.assertEqual(
                hashlib.sha256(item["compressed"]).hexdigest(),
                item["spec"]["compressed_sha256"],
            )
            self.assertLessEqual(
                len(item["compressed"]),
                CHECKER.RESOURCE_LIMITS["max_sidecar_compressed_bytes"],
            )

    def test_14_raw_hashes_and_caps_are_exact(self) -> None:
        for item in self.sidecars.values():
            self.assertEqual(
                hashlib.sha256(item["raw"]).hexdigest(),
                item["spec"]["raw_sha256"],
            )
            self.assertLessEqual(
                len(item["raw"]), CHECKER.RESOURCE_LIMITS["max_sidecar_raw_bytes"]
            )

    def test_15_raw_payload_is_canonical_compact_sorted_key_JSON(self) -> None:
        for item in self.sidecars.values():
            self.assertEqual(CHECKER._canonical_bytes(item["payload"]), item["raw"])
            self.assertFalse(item["raw"].endswith(b"\n"))

    def test_16_outer_sidecar_schema_is_exact(self) -> None:
        for item in self.sidecars.values():
            payload = item["payload"]
            self.assertEqual(set(payload), {"format", "state", "state_sha256", "terms"})
            self.assertEqual(payload["format"], CHECKER.CHECKPOINT_FORMAT)

    def test_17_state_schema_and_digest_are_exact(self) -> None:
        expected_keys = {
            "schema_version", "state_fingerprint", "profile_id", "observable_id",
            "step_index", "heisenberg_direction", "producer_fingerprint",
            "root_checker_source_sha256", "root_expected_witness_sha256",
            "backprop_gate_records_sha256", "tick_denominator", "term_count",
            "expansion_sha256", "cumulative_dropped_l1_ticks",
            "retained_Neel_expectation_lower_ticks",
            "retained_Neel_expectation_upper_ticks",
        }
        for item in self.sidecars.values():
            payload = item["payload"]
            self.assertEqual(set(payload["state"]), expected_keys)
            self.assertEqual(
                CHECKER.canonical_sha256(payload["state"]), payload["state_sha256"]
            )

    def test_18_state_root_and_sequence_pins_do_not_drift(self) -> None:
        root = self.witness["root_parent"]
        for item in self.sidecars.values():
            state = item["payload"]["state"]
            self.assertEqual(state["root_checker_source_sha256"], root["checker_source_sha256"])
            self.assertEqual(state["root_expected_witness_sha256"], root["expected_witness_sha256"])
            self.assertEqual(state["backprop_gate_records_sha256"], root["backprop_gate_records_sha256"])
            self.assertEqual(state["heisenberg_direction"], CHECKER.HEISENBERG_DIRECTION)

    def test_19_terms_are_fixed_size_sorted_four_string_arrays(self) -> None:
        for item in self.sidecars.values():
            terms = item["payload"]["terms"]
            self.assertEqual(len(terms), CHECKER.RETAINED_TERM_CAP)
            previous = None
            for record in terms:
                self.assertEqual(len(record), 4)
                self.assertTrue(all(type(value) is str for value in record))
                key = int(record[0], 16), int(record[1], 16)
                if previous is not None:
                    self.assertLess(previous, key)
                previous = key

    def test_20_term_masks_intervals_and_sparse_form_are_canonical(self) -> None:
        for item in self.sidecars.values():
            for record in item["payload"]["terms"]:
                x_mask = CHECKER._canonical_mask(record[0], "x")
                z_mask = CHECKER._canonical_mask(record[1], "z")
                lower = CHECKER._canonical_integer(record[2], "lower")
                upper = CHECKER._canonical_integer(record[3], "upper")
                self.assertLess(x_mask.bit_length(), CHECKER.N_QUBITS + 1)
                self.assertLess(z_mask.bit_length(), CHECKER.N_QUBITS + 1)
                self.assertLessEqual(lower, upper)
                self.assertNotEqual((lower, upper), (0, 0))

    def test_21_semantic_expansion_hashes_match_state(self) -> None:
        for item in self.sidecars.values():
            expansion = {
                (int(record[0], 16), int(record[1], 16)): (int(record[2]), int(record[3]))
                for record in item["payload"]["terms"]
            }
            self.assertEqual(
                PARENT._tick_digest(expansion),
                item["payload"]["state"]["expansion_sha256"],
            )

    def test_22_retained_Neel_expectations_match_expansions(self) -> None:
        neel = PARENT._neel_basis()
        for item in self.sidecars.values():
            expansion = {
                (int(record[0], 16), int(record[1], 16)): (int(record[2]), int(record[3]))
                for record in item["payload"]["terms"]
            }
            expectation = PARENT._expectation_ticks(expansion, neel)
            state = item["payload"]["state"]
            self.assertEqual(
                expectation,
                (
                    int(state["retained_Neel_expectation_lower_ticks"]),
                    int(state["retained_Neel_expectation_upper_ticks"]),
                ),
            )

    def test_23_boundary_one_exactly_equals_positive_parent(self) -> None:
        for observable_id, parent_claim in self.parent_claims.items():
            state = self.sidecars[(observable_id, 1)]["payload"]["state"]
            self.assertEqual(state["term_count"], parent_claim["final_retained_term_count"])
            self.assertEqual(state["expansion_sha256"], parent_claim["final_retained_expansion_sha256"])
            self.assertEqual(state["cumulative_dropped_l1_ticks"], parent_claim["cumulative_dropped_l1_ticks"])
            retained = parent_claim["final_retained_Neel_expectation_interval"]
            self.assertEqual(state["retained_Neel_expectation_lower_ticks"], retained["lower_ticks"])
            self.assertEqual(state["retained_Neel_expectation_upper_ticks"], retained["upper_ticks"])

    def test_24_step_two_exact_ticks_and_drops_are_frozen(self) -> None:
        expected = {
            "staggered_magnetization": (
                "18395272017727884561", "18395272017727906158",
                "207375793741436", "211995779549182",
            ),
            "double_occupancy": (
                "25701301365444613", "25701301365486817",
                "2152392847533726", "2283149854538588",
            ),
        }
        for observable_id, values in expected.items():
            child = self.children[observable_id]
            retained = child["final_retained_Neel_expectation_interval"]
            self.assertEqual((retained["lower_ticks"], retained["upper_ticks"]), values[:2])
            self.assertEqual(child["child_dropped_l1_ticks"], values[2])
            self.assertEqual(child["output_cumulative_dropped_l1_ticks"], values[3])

    def test_25_drop_recurrence_is_exact_integer_addition(self) -> None:
        for child in self.children.values():
            self.assertEqual(
                int(child["output_cumulative_dropped_l1_ticks"]),
                int(child["input_cumulative_dropped_l1_ticks"])
                + int(child["child_dropped_l1_ticks"]),
            )
            self.assertTrue(child["drop_recurrence_E2_equals_E1_plus_d2"])

    def test_26_declared_intervals_expand_retained_by_cumulative_drop(self) -> None:
        for child in self.children.values():
            drop = int(child["output_cumulative_dropped_l1_ticks"])
            retained = child["final_retained_Neel_expectation_interval"]
            declared = child[
                "declared_two_step_untruncated_mapped_circuit_Neel_expectation_interval"
            ]
            self.assertEqual(int(declared["lower_ticks"]), int(retained["lower_ticks"]) - drop)
            self.assertEqual(int(declared["upper_ticks"]), int(retained["upper_ticks"]) + drop)

    def test_27_declared_two_step_exact_ticks_are_fixed(self) -> None:
        expected = {
            "staggered_magnetization": (
                "18395060021948335379", "18395484013507455340"
            ),
            "double_occupancy": (
                "23418151510906025", "27984451220025405"
            ),
        }
        for observable_id, ticks in expected.items():
            declared = self.children[observable_id][
                "declared_two_step_untruncated_mapped_circuit_Neel_expectation_interval"
            ]
            self.assertEqual((declared["lower_ticks"], declared["upper_ticks"]), ticks)

    def test_28_step_two_dynamic_resources_are_exact_and_bounded(self) -> None:
        expected = {
            "staggered_magnetization": (
                83_883_645, 103_720, 57, 121,
                "119781463396342627917444274",
            ),
            "double_occupancy": (
                85_249_194, 105_350, 63, 120,
                "129687503570104728826532097",
            ),
        }
        for observable_id, values in expected.items():
            usage = self.children[observable_id]["resource_usage"]
            observed = (
                usage["term_gate_visits"],
                usage["peak_single_expansion_term_count"],
                usage["maximum_expansion_coefficient_tick_bits"],
                usage["maximum_product_bits"],
                usage["multiplication_grid_rounding_L1_upper_scaled_ticks_squared"],
            )
            self.assertEqual(observed, values)
            self.assertLessEqual(values[0], CHECKER.RESOURCE_LIMITS["max_term_gate_visits_per_child"])
            self.assertLessEqual(values[1], CHECKER.RESOURCE_LIMITS["max_single_expansion_terms"])

    def test_29_stage_ledger_has_fixed_reverse_palindrome_order(self) -> None:
        groups = ["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"]
        for child in self.children.values():
            stages = child["stage_records"]
            self.assertEqual(len(stages), 9)
            self.assertEqual([stage["group"] for stage in stages], groups)
            self.assertEqual([stage["backprop_stage_index"] for stage in stages], list(range(9)))
            self.assertEqual([stage["forward_stage_index"] for stage in stages], list(reversed(range(9))))

    def test_30_stage_drop_ledger_sums_to_child_drop(self) -> None:
        for child in self.children.values():
            stages = child["stage_records"]
            self.assertEqual(
                sum(int(stage["dropped_l1_ticks"]) for stage in stages),
                int(child["child_dropped_l1_ticks"]),
            )
            self.assertEqual(
                stages[-1]["child_cumulative_dropped_l1_ticks"],
                child["child_dropped_l1_ticks"],
            )
            self.assertTrue(all(stage["start_term_count"] == 65_536 for stage in stages))
            self.assertTrue(all(stage["end_retained_term_count"] == 65_536 for stage in stages))

    def test_31_checkpoint_ledger_has_fixed_count_and_digest(self) -> None:
        expected = {
            "staggered_magnetization": "e2680540936980a16d05bfa06d9a2b12238a7b7b274e67a3e50c46308d9f7b16",
            "double_occupancy": "4c0a6880094ea3a414904cb6d151fa7cc3922924146cf235de89af3c5ced8a78",
        }
        for observable_id, digest in expected.items():
            child = self.children[observable_id]
            self.assertEqual(child["checkpoint_count"], 144)
            self.assertEqual(child["checkpoint_ledger_sha256"], digest)

    def test_32_transition_record_binds_parent_child_chain(self) -> None:
        for observable_id, child in self.children.items():
            transition = child["transition_record"]
            self.assertEqual(transition["input_state_sha256"], child["input_state_sha256"])
            self.assertEqual(transition["output_state_sha256"], child["output_state_sha256"])
            self.assertEqual(transition["input_expansion_sha256"], child["input_expansion_sha256"])
            self.assertEqual(transition["output_expansion_sha256"], child["output_expansion_sha256"])
            self.assertEqual(transition["input_step_index"], 1)
            self.assertEqual(transition["output_step_index"], 2)
            self.assertRegex(transition["previous_transition_anchor_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(transition["transition_policy_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(CHECKER.canonical_sha256(transition), child["transition_sha256"])

    def test_33_transition_forbids_cross_step_fusion(self) -> None:
        self.assertFalse(CHECKER.PROPAGATION_POLICY["cross_step_H1_half_stage_fusion"])
        for child in self.children.values():
            transition = child["transition_record"]
            self.assertFalse(transition["cross_step_fusion_used"])
            self.assertEqual(transition["gate_count"], 1_152)
            self.assertEqual(transition["checkpoint_count"], 144)

    def test_34_transition_exact_pins_match_contract(self) -> None:
        for observable_id, child in self.children.items():
            expected = self.contract["expected_step2_exact"][observable_id]
            self.assertEqual(child["output_expansion_sha256"], expected["expansion_sha256"])
            self.assertEqual(child["output_state_sha256"], expected["state_sha256"])
            self.assertEqual(child["child_dropped_l1_ticks"], expected["child_dropped_l1_ticks"])
            self.assertEqual(child["transition_sha256"], expected["transition_sha256"])

    def test_35_boundary_custody_records_pin_raw_files(self) -> None:
        for observable_id, child in self.children.items():
            custody = child["boundary_sidecar_custody"]
            self.assertEqual(
                custody["input_raw_sha256"],
                self.sidecars[(observable_id, 1)]["spec"]["raw_sha256"],
            )
            self.assertEqual(
                custody["output_raw_sha256"],
                self.sidecars[(observable_id, 2)]["spec"]["raw_sha256"],
            )

    def test_36_internal_contract_validation_succeeds(self) -> None:
        self.assertEqual(CHECKER._validate_contract_impl(self.contract), [])

    def test_37_warm_cache_returns_fresh_copy_and_rechecks_all_custody(self) -> None:
        cached = CHECKER._canonical_bytes(self.witness)
        with mock.patch.object(CHECKER, "_WITNESS_CACHE_BYTES", cached), mock.patch.object(
            CHECKER, "_read_pinned_sources"
        ) as sources, mock.patch.object(CHECKER, "_preflight_checkpoint_files") as sidecars:
            first = CHECKER.recompute_witness()
            second = CHECKER.recompute_witness()
        self.assertEqual(first, self.witness)
        self.assertEqual(second, self.witness)
        self.assertIsNot(first, second)
        self.assertEqual(sources.call_count, 2)
        self.assertEqual(sidecars.call_count, 2)

    def test_38_unresolved_placeholder_fails_before_sidecar_read(self) -> None:
        bad = copy.deepcopy(CHECKER.EXPECTED_STEP2_EXACT)
        bad["staggered_magnetization"]["transition_sha256"] = "__PLACEHOLDER_PROBE__"
        with mock.patch.object(CHECKER, "_WITNESS_CACHE_BYTES", None), mock.patch.object(
            CHECKER, "EXPECTED_STEP2_EXACT", bad
        ), mock.patch.object(CHECKER, "_preflight_checkpoint_files") as preflight:
            with self.assertRaisesRegex(CHECKER.SchemaError, "unresolved placeholder"):
                CHECKER.recompute_witness()
        preflight.assert_not_called()

    def test_39_sidecar_encoded_drift_is_rejected(self) -> None:
        bad = [dict(spec) for spec in CHECKER.CHECKPOINT_SPECS]
        bad[0]["encoded_sha256"] = "0" * 64
        with mock.patch.object(CHECKER, "CHECKPOINT_SPECS", tuple(bad)):
            with self.assertRaisesRegex(CHECKER.SchemaError, "encoded checkpoint hash mismatch"):
                CHECKER._preflight_checkpoint_files()

    def test_40_base85_requires_canonical_LF_wrapping(self) -> None:
        probes = (b"abc", b"abc\r\n", b"a\n\n", b"a" * 101 + b"\n")
        for payload in probes:
            with self.subTest(payload=payload[:8]):
                with self.assertRaises(CHECKER.SchemaError):
                    CHECKER._canonical_b85_decode(payload, "probe")

    def test_41_base85_rejects_noncanonical_or_invalid_payload(self) -> None:
        with self.assertRaises(CHECKER.SchemaError):
            CHECKER._canonical_b85_decode(b"~~~~~\n", "probe")

    def test_42_zlib_rejects_concatenated_streams(self) -> None:
        payload = zlib.compress(b"first") + zlib.compress(b"second")
        with self.assertRaisesRegex(CHECKER.SchemaError, "exactly one complete zlib stream"):
            CHECKER._bounded_zlib_decompress(payload, "probe")

    def test_43_zlib_decompression_cap_is_fail_closed(self) -> None:
        compressed = zlib.compress(b"x" * 20)
        limits = dict(CHECKER.RESOURCE_LIMITS)
        limits["max_sidecar_raw_bytes"] = 10
        with mock.patch.object(CHECKER, "RESOURCE_LIMITS", limits):
            with self.assertRaisesRegex(CHECKER.SchemaError, "exceed"):
                CHECKER._bounded_zlib_decompress(compressed, "probe")

    def test_44_noncanonical_JSON_sidecar_is_rejected(self) -> None:
        with self.assertRaisesRegex(CHECKER.SchemaError, "not canonical compact"):
            self.load_mini_checkpoint(
                raw_encoder=lambda value: json.dumps(value, indent=2, sort_keys=True).encode("ascii")
            )

    def test_45_strict_JSON_rejects_duplicates_nonfinite_and_oversize(self) -> None:
        probes = (
            (b'{"a":1,"a":2}', "duplicate JSON key"),
            (b'{"a":NaN}', "non-finite"),
            (b" " * (CHECKER.RESOURCE_LIMITS["max_json_bytes"] + 1), "byte cap"),
        )
        for payload, message in probes:
            with self.subTest(message=message):
                with self.assertRaisesRegex(CHECKER.SchemaError, message):
                    CHECKER._strict_json_bytes(payload, "probe")

    def test_46_duplicate_or_out_of_order_terms_are_rejected(self) -> None:
        probes = (
            [["0x0", "0x1", "2", "2"], ["0x0", "0x0", "1", "1"]],
            [["0x0", "0x0", "1", "1"], ["0x0", "0x0", "2", "2"]],
        )
        for terms in probes:
            with self.subTest(terms=terms):
                with self.assertRaisesRegex(CHECKER.SchemaError, "strict numeric"):
                    self.load_mini_checkpoint(terms)

    def test_47_noncanonical_or_oversized_masks_are_rejected(self) -> None:
        probes = ("0X0", "0x00", "0x" + "1" + "0" * 32)
        for mask in probes:
            terms = [[mask, "0x0", "1", "1"], ["0x0", "0x1", "2", "2"]]
            with self.subTest(mask=mask):
                with self.assertRaisesRegex(CHECKER.SchemaError, "hexadecimal|mask width"):
                    self.load_mini_checkpoint(terms)

    def test_48_noncanonical_tick_integers_are_rejected(self) -> None:
        for integer in ("01", "+1", "-0", "1.0"):
            terms = [["0x0", "0x0", integer, "1"], ["0x0", "0x1", "2", "2"]]
            with self.subTest(integer=integer):
                with self.assertRaisesRegex(CHECKER.SchemaError, "canonical decimal"):
                    self.load_mini_checkpoint(terms)

    def test_49_reversed_and_exact_zero_intervals_are_rejected(self) -> None:
        probes = (("2", "1", "reversed"), ("0", "0", "zero"))
        for lower, upper, message in probes:
            terms = [["0x0", "0x0", lower, upper], ["0x0", "0x1", "2", "2"]]
            with self.subTest(message=message):
                with self.assertRaisesRegex(CHECKER.SchemaError, message):
                    self.load_mini_checkpoint(terms)

    def test_50_state_semantic_and_expectation_digest_tampers_fail(self) -> None:
        probes = (
            (
                lambda state: state.__setitem__("expansion_sha256", "0" * 64),
                "semantic expansion digest mismatch",
            ),
            (
                lambda state: state.__setitem__("retained_Neel_expectation_lower_ticks", "999"),
                "retained Neel interval is reversed|retained Neel expectation mismatch",
            ),
        )
        for mutator, message in probes:
            with self.subTest(message=message):
                with self.assertRaisesRegex((CHECKER.SchemaError, CHECKER.VerificationError), message):
                    self.load_mini_checkpoint(state_mutator=mutator)

    def test_51_state_digest_tamper_fails(self) -> None:
        def mutate(outer):
            outer["state_sha256"] = "0" * 64

        with self.assertRaisesRegex(CHECKER.VerificationError, "state digest mismatch"):
            self.load_mini_checkpoint(outer_mutator=mutate)

    def test_52_contract_and_certificate_exact_shapes_are_enforced(self) -> None:
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["unexpected"] = None
        bad_certificate = copy.deepcopy(self.certificate)
        bad_certificate["schema_version"] = 1.0
        self.assertTrue(CHECKER._validate_contract_impl(bad_contract))
        self.assertEqual(self.internal_verify(certificate=bad_certificate)["status"], "INVALID_SCHEMA")

    def test_53_contract_pin_and_witness_tampers_fail_closed(self) -> None:
        source = copy.deepcopy(self.contract)
        source["source_pins"][0]["sha256"] = "0" * 64
        witness = copy.deepcopy(self.contract)
        witness["expected_witness_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(contract=source)["status"], "INVALID_SCHEMA")
        self.assertEqual(self.internal_verify(contract=witness)["status"], "VERIFICATION_FAILED")

    def test_54_scope_overclaim_is_invalid_schema(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["scope_claims"]["remaining_98_mapped_steps"] = True
        result = self.internal_verify(certificate=bad)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertFalse(result["ready_gate_eligible"])

    def test_55_well_shaped_transition_tamper_is_verification_failed(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["witness_claim"]["child_witnesses"][0]["transition_sha256"] = "0" * 64
        self.assertEqual(self.internal_verify(certificate=bad)["status"], "VERIFICATION_FAILED")

    def test_56_source_drift_is_rejected_before_compile_or_exec(self) -> None:
        with mock.patch.object(
            CHECKER, "_read_checker_source_bytes", return_value=b"drift"
        ), mock.patch.object(
            CHECKER.types, "ModuleType", side_effect=AssertionError("must not execute")
        ) as constructor:
            result = CHECKER.verify_certificate(self.contract, self.certificate)
        self.assertEqual(result["status"], "INVALID_SCHEMA")
        self.assertIn("before compile/exec", result["errors"][0])
        constructor.assert_not_called()

    def test_57_failure_clears_every_positive_scope_claim(self) -> None:
        bad = copy.deepcopy(self.certificate)
        bad["schema_version"] = 2
        result = self.internal_verify(certificate=bad)
        for key, expected in CHECKER.SCOPE_CLAIMS.items():
            if expected is True:
                self.assertFalse(result["scope_claims"][key])

    def test_58_CLI_always_returns_one_even_for_positive_result(self) -> None:
        fake = {
            "status": CHECKER.MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
        }
        stdout = io.StringIO()
        with mock.patch.object(CHECKER, "load_strict_json", return_value={}), mock.patch.object(
            CHECKER, "verify_certificate", return_value=fake
        ), contextlib.redirect_stdout(stdout):
            self.assertEqual(CHECKER.main(["contract.json", "certificate.json"]), 1)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["status"], CHECKER.MAXIMUM_POSITIVE_STATUS)
        self.assertFalse(output["ready_gate_eligible"])


if __name__ == "__main__":
    unittest.main()
