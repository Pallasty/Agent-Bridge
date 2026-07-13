#!/usr/bin/env python3
"""Output-pin, custody, budget, candidate, and resource tests for v2 policies."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import pathlib
import unittest
import zlib


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


KERNEL = load_module(
    "hubbard_l8_adaptive_k_arithmetic_v2_for_policy_tests",
    "hubbard_l8_adaptive_k_arithmetic_v2.py",
)

EXPECTED_TOP_KEYS = {
    "schema_version",
    "policy_id",
    "policy_fingerprint",
    "policy_role",
    "workload_identity",
    "precommit_boundary",
    "immediate_parent",
    "arithmetic_kernel",
    "design_transcript",
    "sequence_and_arithmetic",
    "truncation_budget",
    "candidate_policy",
    "resource_limits",
    "output_schema_policy",
    "required_checkpoint_ledger_bindings",
    "forbidden_output_pins",
    "scope_boundary",
}

EXPECTED = {
    "magnetization": {
        "policy_file": "hubbard_l8_magnetization_adaptive_k_policy_v2.json",
        "policy_sha256": "c1300af91ed28c69b309e19ffdb0e772e3e256432b08e1b17adfcea58700dd16",
        "policy_id": "hubbard_l8_magnetization_step4_adaptive_k_v2",
        "observable_id": "staggered_magnetization",
        "input_step": 3,
        "child_step": 4,
        "parent_checker": "hubbard_l8_magnetization_interval_step3_checker.py",
        "parent_contract": "hubbard_l8_magnetization_interval_step3_contract.json",
        "parent_certificate": "hubbard_l8_magnetization_interval_step3_template.json",
        "parent_status": "VERIFIED_L8_MAGNETIZATION_STEP3_MAPPED_INTERVAL_CHILD_SUBCERTIFICATE",
        "parent_depth": 3,
        "transcript": "hubbard_l8_magnetization_adaptive_k_v2_design_transcript.json",
        "transcript_sha256": "aaed027aa212f60a40eea93c0826c45cfe5ffa23ef94b0b616213d794e83fd12",
        "boundary": "hubbard_l8_interval_checkpoints/staggered_magnetization_boundary_003.b85",
        "input_transition": "a02d636d4e511f2399ddaa069ba443225bb8259dd8a9e3e5203ca2e21aa7a73d",
        "E_input": 1_691_496_669_588_296,
        "remaining_steps": 97,
        "candidate_count": 17,
        "candidate_sha256": "8b53b080c84e4cabd85f41293d03cf3dd4678b4c9e0cf2497e70adeb602fa9f5",
    },
    "double_occupancy": {
        "policy_file": "hubbard_l8_double_occupancy_adaptive_k_policy_v2.json",
        "policy_sha256": "5099b6e29e52c1dc4ff26b9b4fd408fbd4483e7e4b7a554aa718226336e9c07b",
        "policy_id": "hubbard_l8_double_occupancy_step3_adaptive_k_v2",
        "observable_id": "double_occupancy",
        "input_step": 2,
        "child_step": 3,
        "parent_checker": "hubbard_l8_observable_interval_two_step_checker.py",
        "parent_contract": "hubbard_l8_observable_interval_two_step_contract.json",
        "parent_certificate": "hubbard_l8_observable_interval_two_step_template.json",
        "parent_status": "VERIFIED_L8_TWO_STEP_MAPPED_INTERVAL_CHILD_CHAIN_SUBCERTIFICATE",
        "parent_depth": 2,
        "transcript": "hubbard_l8_double_occupancy_adaptive_k_v2_design_transcript.json",
        "transcript_sha256": "4223155009f7dc4c8fe883a75ac71116ddaff82492e1e1602685e893c4c2368c",
        "boundary": "hubbard_l8_interval_checkpoints/double_occupancy_boundary_002.b85",
        "input_transition": "57b8396e446f01ee6467ea2dee54a25af8bc257dea58ee5ed2b5abe77647fb71",
        "E_input": 2_283_149_854_538_588,
        "remaining_steps": 98,
        "candidate_count": 21,
        "candidate_sha256": "46a2b282201c7b1ca01305c49426a00bcd2bb443e63a662408bd2654768cbfb8",
    },
}


def strict_json_bytes(raw: bytes):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise ValueError(f"duplicate key: {key}")
            output[key] = value
        return output

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def load_policy(mode: str):
    expected = EXPECTED[mode]
    raw = (HERE / expected["policy_file"]).read_bytes()
    return raw, strict_json_bytes(raw)


def file_sha256(filename: str) -> str:
    return hashlib.sha256((HERE / filename).read_bytes()).hexdigest()


def collect_keys(value, *, skip_forbidden_list=False):
    output = []
    if type(value) is dict:
        for key, child in value.items():
            output.append(key)
            if not (skip_forbidden_list and key == "forbidden_output_pins"):
                output.extend(collect_keys(child, skip_forbidden_list=skip_forbidden_list))
    elif type(value) is list:
        for child in value:
            output.extend(collect_keys(child, skip_forbidden_list=skip_forbidden_list))
    return output


class AdaptiveKV2PolicyTests(unittest.TestCase):
    def test_01_policy_transport_and_exact_top_schema(self):
        for mode, expected in EXPECTED.items():
            raw, policy = load_policy(mode)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["policy_sha256"])
            self.assertEqual(set(policy), EXPECTED_TOP_KEYS)
            self.assertEqual(policy["schema_version"], 2)
            self.assertEqual(policy["policy_id"], expected["policy_id"])
            self.assertEqual(
                policy["policy_fingerprint"],
                "hubbard_l8_adaptive_k_v2_precommit_policy_v1",
            )

    def test_02_kernel_and_design_provenance_are_same_byte_pinned(self):
        kernel_sha = file_sha256("hubbard_l8_adaptive_k_arithmetic_v2.py")
        capability_sha = KERNEL.canonical_sha256(KERNEL.RESOURCE_LIMITS)
        for mode, expected in EXPECTED.items():
            _raw, policy = load_policy(mode)
            kernel = policy["arithmetic_kernel"]
            self.assertEqual(kernel["sha256"], kernel_sha)
            self.assertEqual(kernel["fingerprint"], KERNEL.KERNEL_FINGERPRINT)
            self.assertEqual(kernel["certificate_authority"], "NONE")
            self.assertEqual(kernel["capability_limits"], KERNEL.RESOURCE_LIMITS)
            self.assertEqual(kernel["capability_limits_sha256"], capability_sha)
            self.assertFalse(kernel["root_globals_may_be_monkeypatched"])
            transcript_pin = policy["design_transcript"]
            self.assertEqual(transcript_pin["relative_path"], expected["transcript"])
            self.assertEqual(transcript_pin["sha256"], expected["transcript_sha256"])
            self.assertEqual(file_sha256(expected["transcript"]), expected["transcript_sha256"])
            transcript = strict_json_bytes((HERE / expected["transcript"]).read_bytes())
            self.assertEqual(transcript_pin["status"], transcript["status"])
            self.assertTrue(transcript_pin["diagnostic_only"])
            self.assertTrue(transcript_pin["formal_checker_must_independently_replay"])
            self.assertTrue(
                transcript_pin["not_accepted_as_a_certificate_witness_sidecar_or_transition"]
            )

    def test_03_immediate_parent_and_boundary_custody(self):
        for mode, expected in EXPECTED.items():
            _raw, policy = load_policy(mode)
            parent = policy["immediate_parent"]
            self.assertEqual(parent["checker_relative_path"], expected["parent_checker"])
            self.assertEqual(parent["checker_sha256"], file_sha256(expected["parent_checker"]))
            self.assertEqual(parent["contract_relative_path"], expected["parent_contract"])
            self.assertEqual(parent["contract_sha256"], file_sha256(expected["parent_contract"]))
            self.assertEqual(parent["certificate_relative_path"], expected["parent_certificate"])
            self.assertEqual(
                parent["certificate_sha256"], file_sha256(expected["parent_certificate"])
            )
            contract = strict_json_bytes((HERE / expected["parent_contract"]).read_bytes())
            self.assertEqual(parent["expected_witness_sha256"], contract["expected_witness_sha256"])
            self.assertEqual(parent["required_positive_status"], expected["parent_status"])
            self.assertEqual(parent["required_certified_depth"], expected["parent_depth"])
            certificate = strict_json_bytes(
                (HERE / expected["parent_certificate"]).read_bytes()
            )
            self.assertEqual(
                parent["required_profile_id"], certificate["workload_identity"]["profile_id"]
            )
            boundary = parent["boundary"]
            self.assertEqual(boundary["relative_path"], expected["boundary"])
            encoded = (HERE / expected["boundary"]).read_bytes()
            compressed = base64.b85decode(b"".join(encoded.splitlines()))
            raw = zlib.decompress(compressed)
            payload = strict_json_bytes(raw)
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), boundary["encoded_sha256"])
            self.assertEqual(
                hashlib.sha256(compressed).hexdigest(), boundary["compressed_sha256"]
            )
            self.assertEqual(hashlib.sha256(raw).hexdigest(), boundary["raw_sha256"])
            self.assertEqual(payload["state_sha256"], boundary["state_sha256"])
            self.assertEqual(payload["state"]["expansion_sha256"], boundary["expansion_sha256"])
            self.assertEqual(payload["state"]["term_count"], boundary["term_count"])
            self.assertEqual(
                payload["state"].get("previous_transition_sha256"),
                boundary["previous_transition_recorded_inside_state_sha256"],
            )
            self.assertEqual(
                int(payload["state"]["cumulative_dropped_l1_ticks"]),
                boundary["cumulative_dropped_l1_ticks"],
            )
            self.assertEqual(boundary["input_transition_sha256"], expected["input_transition"])
            if mode == "magnetization":
                transition_sha = certificate["witness_claim"]["transition_sha256"]
            else:
                claims = [
                    item for item in certificate["witness_claim"]["child_witnesses"]
                    if item["observable_id"] == expected["observable_id"]
                ]
                self.assertEqual(len(claims), 1)
                transition_sha = claims[0]["transition_sha256"]
            self.assertEqual(boundary["input_transition_sha256"], transition_sha)

    def test_04_candidate_ladders_are_exact_and_bounded(self):
        for mode, expected in EXPECTED.items():
            _raw, policy = load_policy(mode)
            candidate = policy["candidate_policy"]
            values = candidate["candidate_K_values_in_strict_ascending_order"]
            self.assertEqual(len(values), expected["candidate_count"])
            self.assertTrue(values and all(type(value) is int for value in values))
            self.assertTrue(all(left < right for left, right in zip(values, values[1:])))
            self.assertEqual(values[-1], 327_680)
            self.assertEqual(candidate["configured_maximum_K"], values[-1])
            self.assertEqual(candidate["configured_candidate_count"], len(values))
            self.assertEqual(KERNEL.canonical_sha256(values), expected["candidate_sha256"])
            self.assertEqual(candidate["candidate_K_values_sha256"], expected["candidate_sha256"])
            limits = policy["resource_limits"]
            self.assertEqual(limits["max_candidate_count"], len(values))
            self.assertEqual(limits["max_candidate_K"], values[-1])

    def test_05_budget_prefixes_and_scope_are_exact(self):
        B = (1 << 64) // 4000
        for mode, expected in EXPECTED.items():
            _raw, policy = load_policy(mode)
            budget = policy["truncation_budget"]
            E_input = expected["E_input"]
            remaining = expected["remaining_steps"]
            denominator = remaining * 144
            child_cap = E_input + 144 * (B - E_input) // denominator
            self.assertEqual(budget["input_cumulative_drop_ticks"], E_input)
            self.assertEqual(budget["maximum_cumulative_drop_ticks"], B)
            self.assertEqual(budget["remaining_checkpoint_count"], denominator)
            self.assertEqual(budget["remaining_drop_ticks_after_step" + str(expected["input_step"])], B - E_input)
            self.assertEqual(budget["child_final_prefix_cap_ticks"], child_cap)
            self.assertEqual(
                budget["maximum_child_incremental_drop_ticks"], child_cap - E_input
            )
            scope = policy["scope_boundary"]
            self.assertEqual(scope["certified_mapped_depth_before_attempt"], expected["input_step"])
            self.assertEqual(scope["attempted_child_step_index"], expected["child_step"])
            self.assertTrue(scope["failure_leaves_certified_depth_unchanged"])
            self.assertFalse(scope["physical_reference_qualified"])
            self.assertFalse(scope["ready_gate_eligible"])

    def test_06_policy_resources_fit_kernel_capabilities(self):
        mapping = {
            "max_candidate_count": "max_candidate_count",
            "max_candidate_K": "max_retained_K",
            "max_digest_terms": "max_digest_terms",
            "max_expansion_coefficient_tick_bits": "max_expansion_coefficient_tick_bits",
            "max_product_bits": "max_product_bits",
            "max_single_expansion_terms": "max_single_expansion_terms",
            "max_suffix_accumulator_bits": "max_suffix_accumulator_bits",
            "max_term_gate_visits": "max_term_gate_visits",
            "max_trigonometric_tick_bits": "max_trigonometric_tick_bits",
        }
        for mode in EXPECTED:
            _raw, policy = load_policy(mode)
            limits = policy["resource_limits"]
            for policy_key, kernel_key in mapping.items():
                self.assertLessEqual(limits[policy_key], KERNEL.RESOURCE_LIMITS[kernel_key])
            self.assertEqual(
                limits["max_output_sidecar_terms_if_successful"], limits["max_candidate_K"]
            )

    def test_07_formal_outputs_are_not_precommitted(self):
        forbidden_exact_keys = {
            "formal_child_encoded_sha256",
            "formal_child_compressed_sha256",
            "formal_child_raw_sha256",
            "formal_child_state_sha256",
            "formal_child_expansion_sha256",
            "formal_child_transition_sha256",
            "formal_checkpoint_ledger_sha256",
            "formal_child_drop_ticks",
            "formal_child_cumulative_drop_ticks",
            "formal_child_retained_expectation_interval",
            "formal_child_declared_interval",
            "formal_selected_K_history",
            "formal_selected_K_history_sha256",
            "formal_observed_resource_values",
            "formal_failure_checkpoint",
            "formal_witness_sha256",
            "formal_child_checker_sha256",
            "formal_child_contract_sha256",
            "formal_child_template_sha256",
            "formal_positive_status",
            "formal_child_boundary_committed",
        }
        diagnostic_result_hashes = {
            "30c538ed5faee21fe92a547ead1e3e2f1726f9ebebaad6f7fa815b64f36ca6fa",
            "504964a8ab8cb0d68ccf203f8c70876bbf21b5bd631d621bdaef8500c479b051",
            "1a8ec75243bc2e3134c1df4586ebcbbbc4f12b9d5b286d5bb0801f37f5702894",
            "f3e78409683eb88c21861a0ae4b1029b8247629d458eb836b30edeaeb2e50820",
        }
        for mode in EXPECTED:
            raw, policy = load_policy(mode)
            self.assertEqual(set(policy["forbidden_output_pins"]), forbidden_exact_keys)
            observed_keys = set(collect_keys(policy, skip_forbidden_list=True))
            self.assertTrue(forbidden_exact_keys.isdisjoint(observed_keys))
            text = raw.decode("utf-8")
            self.assertTrue(all(value not in text for value in diagnostic_result_hashes))
            boundary = policy["precommit_boundary"]
            self.assertFalse(boundary["formal_v2_attempt_started_before_this_policy_commit"])
            self.assertFalse(boundary["policy_contains_formal_child_output_pins"])
            self.assertTrue(boundary["policy_does_not_promise_success"])
            self.assertTrue(boundary["formal_v2_attempt_must_start_only_after_this_policy_is_committed"])


if __name__ == "__main__":
    unittest.main()
