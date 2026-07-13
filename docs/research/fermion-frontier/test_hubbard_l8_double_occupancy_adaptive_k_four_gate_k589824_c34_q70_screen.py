#!/usr/bin/env python3
"""Static, synthetic, canonical and opt-in tests for the D C34 q70 screen."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k589824_c34_q70_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "af4257d505bcebcafa80fa184bd83065fae1b5151fd9bdc28a5f5b9ccf9ecb32"
)
EXPECTED_CANONICAL = {
    "file_sha256": "65d6f5ba3e45b5b57b12d1b9e1daadb17064f8aece7dc914697191f822b3a8d7",
    "candidate_sha256": "a15306f3ca1f770baeac58bd8d3d48e64bb677e9fb10b6177c30be60bc735774",
    "records_sha256": "738ab268f6dc3f4a79ed17bcaf0c5400130a541bc823a8edbabfa42f34f09fb0",
    "history_sha256": "f41c9984a1f7d076f1f0148f2a37b2be3b7ba55fa9adff91a1e9753c7989daa0",
    "failure_sha256": "5cbadf7fdfab27f651713dbd62b7d7497475bbdb9ebb7a03026330a6333b5a6e",
    "components_sha256": "09b44b34d96b9674fa5905d1db17669d56336f8261a8e6d3c94a794474ce92f4",
    "configuration_reference_sha256": "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1",
    "configuration_override_sha256": "f93f946e08a5189503ff970e944556db26cb0dfceb8d3fb76866b0255356bde9",
    "kernel_override_sha256": "c764fdbd18e2da1f74312f5b3eb1930890e3f1f1a8d7b8027cbd3f7168585078",
    "parent_horizon_override_sha256": "caabe92f91df1dc9daac6ab6ebafb384a7ada9f89b384229fe6e53a6e9b997cd",
    "route_reference_sha256": "82755d88d7a11a8e7aa328672c4970d356e37c7f32cf902821a974a6005d1fe3",
    "handoff_sha256": "99e64f15ea1f2f0b30eabbdb5979a118d24c1d5e68fae08ead656a4a211ae28c",
    "transform_sha256": "088ec77c061a5fd87797245c3fe005462474e5c56ac1df3f52ba5cc17ff0810b",
    "last_E": "2288773695590045",
    "peak": 718_805,
    "visits": 87_505_002,
    "coefficient_bits": 63,
    "product_bits": 120,
    "rounding": "117439184637462075559402711",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("double_occupancy_k589824_c34_q70_for_tests", SCREEN_NAME)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


class DoubleOccupancyK589824C34Q70Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def load_static_bundle(self):
        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_control_flow_parent(HERE)
        configuration, baseline_d = fresh.load_configured_v6_baseline(HERE)
        kernel, kernel_sha, manifest = fresh.load_kernel_wrapper(HERE)
        predecessor, route_reference = fresh.load_route_reference(HERE)
        return (
            fresh,
            parent,
            configuration,
            baseline_d,
            kernel,
            kernel_sha,
            manifest,
            predecessor,
            route_reference,
        )

    def make_synthetic_records(self, predecessor):
        records = []
        for old_record in predecessor["records"][:68]:
            record = copy.deepcopy(old_record)
            pre_count = record["pretruncation_expansion_count"]
            effective = min(SCREEN.K589824, pre_count)
            record["candidate_records"].append({
                "candidate_index": 33,
                "configured_K": SCREEN.K589824,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": "0",
                "E_after_if_selected_ticks": record["E_before_ticks"],
                "feasible_under_current_prefix_cap": True,
            })
            records.append(record)

        q69 = copy.deepcopy(predecessor["records"][68])
        for key in (
            "minimum_effective_K_to_meet_prefix",
            "required_K_excess_over_policy_maximum",
            "maximum_candidate_drop_excess_over_slack_ticks",
        ):
            q69.pop(key)
        q69["candidate_records"].append({
            "candidate_index": 33,
            "configured_K": SCREEN.K589824,
            "effective_retained_count": SCREEN.K589824,
            "dropped_term_count": 54_680,
            "drop_ticks": "0",
            "E_after_if_selected_ticks": q69["E_before_ticks"],
            "feasible_under_current_prefix_cap": True,
        })
        q69.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 33,
            "selected_K": SCREEN.K589824,
            "selected_effective_retained_count": SCREEN.K589824,
            "selected_dropped_term_count": 54_680,
            "selected_drop_ticks": "0",
            "selected_dropped_terms_sha256": "1" * 64,
            "retained_expansion_count": SCREEN.K589824,
            "retained_expansion_sha256": "2" * 64,
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": q69["E_before_ticks"],
        })
        q69["removed_491520_counterfactual"]["actual_selected_K"] = (
            SCREEN.K589824
        )
        records.append(q69)
        E_before = int(q69["E_after_ticks"])
        pre_count = 600_000
        q70_rows = []
        for candidate_index, configured_K in enumerate(SCREEN.D_CANDIDATES):
            effective = min(configured_K, pre_count)
            q70_rows.append({
                "candidate_index": candidate_index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": "1",
                "E_after_if_selected_ticks": str(E_before + 1),
                "feasible_under_current_prefix_cap": False,
            })
        records.append({
            "checkpoint_index_zero_based": 69,
            "checkpoint_number_one_based": 70,
            "input_expansion_count": q69["retained_expansion_count"],
            "input_expansion_sha256": q69["retained_expansion_sha256"],
            "E_before_ticks": q69["E_after_ticks"],
            "pretruncation_expansion_count": pre_count,
            "budget_prefix_cap_ticks": str(E_before),
            "prefix_slack_before_selection_ticks": "0",
            "candidate_records": q70_rows,
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "selected_candidate_index": None,
            "selected_K": None,
            "minimum_effective_K_to_meet_prefix": SCREEN.K589824 + 1,
            "required_K_excess_over_policy_maximum": 1,
            "maximum_candidate_drop_excess_over_slack_ticks": "1",
            "removed_491520_counterfactual": {"actual_selected_K": None},
        })
        history = predecessor["selected_K_history"] + [SCREEN.K589824]
        return records, history

    def make_synthetic_parent_result(self, predecessor):
        records, history = self.make_synthetic_records(predecessor)
        components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        configuration = {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "source_sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        }
        transform = {"transform_id": "synthetic-original-four-gate-parent"}
        return {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "same_byte_self_execution": True,
            "v2_run_entrypoint_called": False,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
            "control_flow_owned_by_screen": True,
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "screen_horizon_checkpoint_count": SCREEN.EXTENDED_HORIZON,
            "candidate_K_values": list(SCREEN.D_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": len(SCREEN.D_CANDIDATES),
            },
            "kernel_capability_limits": copy.deepcopy(
                SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS
            ),
            "records": records,
            "selected_K_history": history,
            "records_sha256": sha256(canonical_bytes(records)),
            "selected_K_history_sha256": sha256(canonical_bytes(history)),
            "attempted_checkpoint_count": 70,
            "completed_checkpoint_count": 69,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
            "failure_record_sha256": sha256(canonical_bytes(records[-1])),
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "last_committed_cumulative_drop_ticks": records[68]["E_after_ticks"],
            "screen_execution_components": components,
            "screen_execution_components_sha256": sha256(
                canonical_bytes(components)
            ),
            "configuration_reference": configuration,
            "configuration_reference_sha256": sha256(
                canonical_bytes(configuration)
            ),
            "checkpoint_transform": transform,
            "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
            "source_custody": {
                SCREEN.V6_BASELINE_CONFIGURATION_NAME: (
                    SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
                ),
                SCREEN.V2_ARITHMETIC_NAME: SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            },
        }

    def test_01_exact_source_route_and_capability_pins(self):
        self_payload = (HERE / SCREEN.SELF_NAME).read_bytes()
        parent_payload = (HERE / SCREEN.CONTROL_FLOW_PARENT_NAME).read_bytes()
        v6_payload = (HERE / SCREEN.V6_BASELINE_CONFIGURATION_NAME).read_bytes()
        v2_payload = (HERE / SCREEN.V2_ARITHMETIC_NAME).read_bytes()
        wrapper_payload = (HERE / SCREEN.KERNEL_WRAPPER_NAME).read_bytes()
        route_screen_payload = (
            HERE / SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME
        ).read_bytes()
        route_raw = (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        q68_screen_payload = (HERE / SCREEN.ROUTE_Q68_SCREEN_NAME).read_bytes()
        q68_raw = (HERE / SCREEN.ROUTE_Q68_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(sha256(self_payload), EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            sha256(parent_payload), SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
        )
        self.assertEqual(
            sha256(v6_payload), SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
        )
        self.assertEqual(sha256(v2_payload), SCREEN.EXPECTED_V2_ARITHMETIC_SHA256)
        self.assertEqual(sha256(wrapper_payload), SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(
            sha256(route_screen_payload),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        )
        self.assertEqual(
            sha256(route_raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256
        )
        self.assertEqual(
            sha256(q68_screen_payload), SCREEN.EXPECTED_ROUTE_Q68_SCREEN_SHA256
        )
        self.assertEqual(
            sha256(q68_raw), SCREEN.EXPECTED_ROUTE_Q68_TRANSCRIPT_SHA256
        )
        self.assertEqual(route_raw, canonical_bytes(json.loads(route_raw)))
        self.assertEqual(q68_raw, canonical_bytes(json.loads(q68_raw)))

        first = SCREEN.fresh_self_module()
        second = SCREEN.fresh_self_module()
        self.assertIsNot(first, second)
        self.assertEqual(first._VERIFIED_SELF_SOURCE_BYTES, self_payload)
        first_parent = first.load_control_flow_parent(HERE)
        second_parent = first.load_control_flow_parent(HERE)
        self.assertIsNot(first_parent, second_parent)
        self.assertEqual(first_parent._VERIFIED_SELF_SOURCE_BYTES, parent_payload)

        kernel, observed, manifest = first.load_kernel_wrapper(HERE)
        self.assertEqual(observed, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(kernel._VERIFIED_SELF_SOURCE_BYTES, wrapper_payload)
        self.assertEqual(kernel._VERIFIED_BASE_KERNEL_SOURCE_BYTES, v2_payload)
        self.assertEqual(
            sha256(canonical_bytes(manifest)),
            SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(manifest["source_layers"])),
            SCREEN.EXPECTED_KERNEL_SOURCE_LAYERS_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(manifest["route_predecessor_reference"])),
            SCREEN.EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256,
        )

    def test_02_D34_append_policy_kernel_and_D_only_horizon(self):
        SCREEN.validate_local_configuration()
        bundle = self.load_static_bundle()
        fresh, parent, configuration, baseline_d, kernel = bundle[:5]
        self.assertEqual(len(baseline_d), 32)
        self.assertEqual(
            SCREEN.PREDECESSOR_D_CANDIDATES,
            baseline_d[1:] + (SCREEN.K540672, SCREEN.K573440),
        )
        self.assertEqual(
            SCREEN.D_CANDIDATES,
            SCREEN.PREDECESSOR_D_CANDIDATES + (SCREEN.K589824,),
        )
        self.assertEqual(len(SCREEN.D_CANDIDATES), 34)
        self.assertEqual(
            sha256(canonical_bytes(list(SCREEN.D_CANDIDATES))),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            configuration.MODE_CONFIG[SCREEN.MODE]["candidates"],
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(kernel.validate_candidates(SCREEN.D_CANDIDATES), SCREEN.D_CANDIDATES)
        self.assertEqual(kernel.validate_candidates((589_824,)), (589_824,))
        with self.assertRaises(kernel.SchemaError):
            kernel.validate_candidates((589_825,))
        with self.assertRaises(kernel.SchemaError):
            kernel.validate_candidates(tuple(range(1, 36)))

        explicit = {"max_candidate_K", "max_output_terms_if_successful"}
        for before in (
            SCREEN.EXPECTED_V6_POLICY_CAPS,
            SCREEN.EXPECTED_PREDECESSOR_POLICY_CAPS,
        ):
            self.assertEqual(SCREEN.changed_keys(before, SCREEN.POLICY_CAPS_BASE), explicit)
        override = fresh.configuration_override(baseline_d)
        self.assertEqual(
            set(override["direct_execution_override_from_v6"]["policy_cap_changes"]),
            explicit,
        )
        self.assertEqual(
            set(
                override["incremental_route_override_from_k573440_c33_q70"]
                ["policy_cap_changes"]
            ),
            explicit,
        )
        self.assertEqual(
            override["derived_policy_cap"],
            {
                "field": "max_candidate_count",
                "derivation": "len(candidate_K_values)",
                "before_on_route": 33,
                "after": 34,
            },
        )
        self.assertEqual(kernel.RESOURCE_LIMITS, SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS)

        before = copy.deepcopy(parent.MODE_CONFIG)
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        self.assertEqual(
            horizon["changed_fields"],
            ["MODE_CONFIG.double_occupancy.horizon_checkpoint_count"],
        )
        self.assertEqual(before[SCREEN.MODE]["horizon_checkpoint_count"], 66)
        self.assertEqual(parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 70)
        self.assertEqual(parent.MODE_CONFIG["magnetization"], before["magnetization"])
        self.assertEqual(
            configuration.MODE_CONFIG["magnetization"],
            fresh.load_configured_v6_baseline(HERE)[0].MODE_CONFIG["magnetization"],
        )
        pristine = fresh.load_control_flow_parent(HERE)
        self.assertEqual(pristine.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 66)

    def test_03_direct_parent_private_path_and_exception_identity(self):
        fresh = SCREEN.fresh_self_module()
        original_loader = fresh.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = original_loader(repo)

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                observed["horizon"] = parent.MODE_CONFIG[mode][
                    "horizon_checkpoint_count"
                ]
                observed["M_config"] = copy.deepcopy(
                    parent.MODE_CONFIG["magnetization"]
                )
                configured = parent.load_v6_configuration(inner_repo)
                observed["candidates"] = configured.MODE_CONFIG[mode]["candidates"]
                observed["caps"] = copy.deepcopy(configured.POLICY_CAPS_BASE)
                helper = parent.load_v2_helper(inner_repo)
                active, _root, _modules, _custody = parent.load_execution_sources(
                    inner_repo, helper, mode
                )
                observed["limits"] = copy.deepcopy(active.RESOURCE_LIMITS)
                return {"direct_parent_private_result": True}

            parent._run_verified = private_sentinel
            return parent

        fresh.load_control_flow_parent = load_sentinel_parent
        fresh.validate_and_relabel = lambda result, *_args: result
        self.assertEqual(
            fresh._run_verified(HERE), {"direct_parent_private_result": True}
        )
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["horizon"], 70)
        self.assertEqual(observed["M_config"]["horizon_checkpoint_count"], 80)
        self.assertEqual(observed["candidates"], SCREEN.D_CANDIDATES)
        self.assertEqual(observed["caps"], SCREEN.POLICY_CAPS_BASE)
        self.assertEqual(observed["limits"], SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS)

        resource_error = RuntimeError("D q70 resource sentinel")
        failing = SCREEN.fresh_self_module()
        failing_original_loader = failing.load_control_flow_parent

        def load_failing_parent(repo):
            parent = failing_original_loader(repo)

            def private_failure(_repo, _mode):
                raise resource_error

            parent._run_verified = private_failure
            return parent

        failing.load_control_flow_parent = load_failing_parent
        with self.assertRaises(RuntimeError) as caught:
            failing._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

    def test_04_public_entrypoint_always_uses_fresh_same_byte_module(self):
        sentinel = {"fresh": True}

        class Inner:
            @staticmethod
            def _run_verified(repo):
                self.assertEqual(repo, HERE)
                return sentinel

        original_fresh = SCREEN.fresh_self_module
        original_private = SCREEN._run_verified
        try:
            SCREEN._run_verified = lambda *_args: self.fail("live outer path used")
            SCREEN.fresh_self_module = lambda: Inner()
            self.assertIs(SCREEN.run(HERE), sentinel)
        finally:
            SCREEN.fresh_self_module = original_fresh
            SCREEN._run_verified = original_private

    def test_05_route_refs_are_exact_nonexecution_handoff_only(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, reference = fresh.load_route_reference(HERE)
        self.assertEqual(predecessor["attempted_checkpoint_count"], 69)
        self.assertEqual(predecessor["completed_checkpoint_count"], 68)
        q69 = predecessor["records"][-1]
        self.assertEqual(q69["checkpoint_number_one_based"], 69)
        self.assertEqual(q69["pretruncation_expansion_count"], 644_504)
        self.assertEqual(q69["minimum_effective_K_to_meet_prefix"], 579_098)
        self.assertEqual(q69["required_K_excess_over_policy_maximum"], 5_658)

        for group in (reference["screen"], reference["q68_ancestry"]):
            self.assertFalse(group["compiled"])
            self.assertFalse(group["executed"])
            self.assertFalse(group["execution_source_layer"])
        transcript = reference["canonical_transcript"]
        self.assertTrue(transcript["loaded_before_replay_as_exact_reference"])
        self.assertTrue(
            transcript["used_only_after_replay_for_result_prefix_validation"]
        )
        for key in (
            "propagation_input",
            "checkpoint_68_state_loaded",
            "checkpoint_69_state_loaded",
            "state_resume_input",
            "execution_source_layer",
        ):
            self.assertFalse(transcript[key], key)

        components = fresh.execution_components(
            copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)),
            EXPECTED_SCREEN_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        )
        paths = [item["relative_path"] for item in components]
        expected_paths = [SCREEN.SELF_NAME]
        for item in SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS:
            expected_paths.append(item["relative_path"])
            if item["relative_path"] == SCREEN.V2_ARITHMETIC_NAME:
                expected_paths.append(SCREEN.KERNEL_WRAPPER_NAME)
        self.assertEqual(paths, expected_paths)
        for forbidden in (
            SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME,
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            SCREEN.ROUTE_Q68_SCREEN_NAME,
            SCREEN.ROUTE_Q68_TRANSCRIPT_NAME,
        ):
            self.assertNotIn(forbidden, paths)
        injected = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        injected.append({
            "relative_path": "untrusted_execution_parent.py",
            "role": "execution_source",
            "sha256": "0" * 64,
        })
        with self.assertRaisesRegex(RuntimeError, "component schema drift"):
            fresh.execution_components(
                injected,
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            )
        duplicated = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        duplicated.append(copy.deepcopy(duplicated[0]))
        with self.assertRaisesRegex(RuntimeError, "component schema drift"):
            fresh.execution_components(
                duplicated,
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            )

    def test_06_synthetic_q1_q68_and_q69_handoff_with_tamper_rejection(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, _reference = fresh.load_route_reference(HERE)
        records, history = self.make_synthetic_records(predecessor)
        result = {
            "records": records,
            "selected_K_history": history,
            "records_sha256": sha256(canonical_bytes(records)),
            "selected_K_history_sha256": sha256(canonical_bytes(history)),
            "attempted_checkpoint_count": 70,
            "completed_checkpoint_count": 69,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
            "failure_record_sha256": sha256(canonical_bytes(records[-1])),
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "last_committed_cumulative_drop_ticks": records[68]["E_after_ticks"],
        }
        validation = fresh.validate_replay_handoff(result, predecessor)
        self.assertTrue(validation["q1_through_q68_common_records_exact"])
        self.assertTrue(validation["q1_through_q68_first_33_candidate_rows_exact"])
        self.assertTrue(validation["q69_shared_propagation_fields_exact"])
        self.assertTrue(validation["q69_first_33_candidate_rows_exact"])
        self.assertEqual(validation["q69_selected_candidate_index"], 33)
        self.assertEqual(validation["q69_selected_K"], SCREEN.K589824)
        self.assertFalse(validation["q70_outcome_precommitted"])
        self.assertEqual(
            sha256(canonical_bytes(history[:69])),
            SCREEN.EXPECTED_Q69_SELECTED_HISTORY_PREFIX_SHA256,
        )

        bad_common = copy.deepcopy(result)
        bad_common["records"][0]["E_before_ticks"] = "-1"
        bad_common["records_sha256"] = sha256(canonical_bytes(bad_common["records"]))
        with self.assertRaisesRegex(RuntimeError, "q1 common record state"):
            fresh.validate_replay_handoff(bad_common, predecessor)

        bad_rows = copy.deepcopy(result)
        bad_rows["records"][1]["candidate_records"][0]["drop_ticks"] = "-1"
        bad_rows["records_sha256"] = sha256(canonical_bytes(bad_rows["records"]))
        with self.assertRaisesRegex(RuntimeError, "q2 predecessor rows"):
            fresh.validate_replay_handoff(bad_rows, predecessor)

        bad_q69 = copy.deepcopy(result)
        bad_q69["records"][68]["selected_K"] = SCREEN.K589824 - 1
        bad_q69["records_sha256"] = sha256(canonical_bytes(bad_q69["records"]))
        with self.assertRaisesRegex(RuntimeError, "q69 handoff drift: selected_K"):
            fresh.validate_replay_handoff(bad_q69, predecessor)

        successful = copy.deepcopy(result)
        q70 = successful["records"][69]
        for key in (
            "minimum_effective_K_to_meet_prefix",
            "required_K_excess_over_policy_maximum",
            "maximum_candidate_drop_excess_over_slack_ticks",
        ):
            q70.pop(key)
        selected = q70["candidate_records"][33]
        selected["drop_ticks"] = "0"
        selected["E_after_if_selected_ticks"] = q70["E_before_ticks"]
        selected["feasible_under_current_prefix_cap"] = True
        q70.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 33,
            "selected_K": SCREEN.K589824,
            "selected_effective_retained_count": selected[
                "effective_retained_count"
            ],
            "selected_dropped_term_count": selected["dropped_term_count"],
            "selected_drop_ticks": "0",
            "selected_dropped_terms_sha256": "3" * 64,
            "retained_expansion_count": selected["effective_retained_count"],
            "retained_expansion_sha256": "4" * 64,
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": q70["E_before_ticks"],
        })
        q70["removed_491520_counterfactual"]["actual_selected_K"] = (
            SCREEN.K589824
        )
        successful["selected_K_history"].append(SCREEN.K589824)
        successful["records_sha256"] = sha256(canonical_bytes(successful["records"]))
        successful["selected_K_history_sha256"] = sha256(
            canonical_bytes(successful["selected_K_history"])
        )
        successful["completed_checkpoint_count"] = 70
        successful["screen_terminal_condition"] = "DIAGNOSTIC_HORIZON_REACHED"
        successful["failure_checkpoint_included"] = False
        successful["failure_record_sha256"] = None
        successful["horizon_reached_with_committed_checkpoint"] = True
        successful["last_committed_cumulative_drop_ticks"] = q70["E_after_ticks"]
        self.assertFalse(
            fresh.validate_replay_handoff(successful, predecessor)[
                "q70_outcome_precommitted"
            ]
        )

        forged_failure = copy.deepcopy(result)
        forged_failure["failure_checkpoint_included"] = False
        with self.assertRaisesRegex(RuntimeError, "failure summary drift"):
            fresh.validate_replay_handoff(forged_failure, predecessor)

        forged_success = copy.deepcopy(result)
        forged_success["records"][69] = {
            "checkpoint_index_zero_based": 69,
            "checkpoint_number_one_based": 70,
            "input_expansion_count": records[68]["retained_expansion_count"],
            "input_expansion_sha256": records[68]["retained_expansion_sha256"],
            "E_before_ticks": records[68]["E_after_ticks"],
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        }
        forged_success["selected_K_history"].append(123)
        forged_success["records_sha256"] = sha256(
            canonical_bytes(forged_success["records"])
        )
        forged_success["selected_K_history_sha256"] = sha256(
            canonical_bytes(forged_success["selected_K_history"])
        )
        forged_success["completed_checkpoint_count"] = 70
        forged_success["screen_terminal_condition"] = "DIAGNOSTIC_HORIZON_REACHED"
        with self.assertRaisesRegex(RuntimeError, "expansion count type drift"):
            fresh.validate_replay_handoff(forged_success, predecessor)

    def test_07_synthetic_relabel_provenance_hashes_and_authority(self):
        bundle = self.load_static_bundle()
        (
            fresh,
            parent,
            configuration,
            baseline_d,
            kernel,
            kernel_sha,
            manifest,
            predecessor,
            route_reference,
        ) = bundle
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        result = fresh.validate_and_relabel(
            self.make_synthetic_parent_result(predecessor),
            predecessor,
            route_reference,
            baseline_d,
            kernel_sha,
            manifest,
            horizon,
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k589824_c34_q70_screen_v1",
        )
        self.assertFalse(result["control_flow_owned_by_screen"])
        self.assertTrue(result["control_flow_owned_by_verified_parent"])
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertTrue(result["control_flow_parent_runtime_horizon_override_applied"])
        self.assertTrue(result["v6_configuration_source_used_as_baseline_only"])
        self.assertTrue(result["v6_runtime_configuration_override_applied"])
        roles = {
            item["relative_path"]: item["role"]
            for item in result["screen_execution_components"]
        }
        self.assertEqual(
            roles[SCREEN.SELF_NAME], "D_k589824_c34_q70_fresh_same_byte_screen"
        )
        self.assertEqual(
            roles[SCREEN.CONTROL_FLOW_PARENT_NAME],
            "four_gate_control_flow_parent_private_entrypoint",
        )
        self.assertEqual(
            roles[SCREEN.KERNEL_WRAPPER_NAME],
            "k589824_c34_capability_override_provider",
        )
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, roles)
        self.assertNotIn(SCREEN.ROUTE_Q68_SCREEN_NAME, roles)
        self.assertEqual(
            result["kernel_capability_override"]["execution_source_layers"],
            [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME],
        )
        self.assertFalse(
            result["kernel_capability_override"]
            ["route_predecessor_is_execution_source"]
        )
        self.assertFalse(
            result["route_predecessor_reference"]["canonical_transcript"]
            ["state_resume_input"]
        )
        for field, value in (
            ("screen_execution_components_sha256", result["screen_execution_components"]),
            ("configuration_reference_sha256", result["configuration_reference"]),
            ("configuration_override_sha256", result["configuration_override"]),
            ("kernel_capability_override_sha256", result["kernel_capability_override"]),
            ("parent_horizon_override_sha256", result["parent_horizon_override"]),
            ("route_predecessor_reference_sha256", result["route_predecessor_reference"]),
            ("predecessor_handoff_validation_sha256", result["predecessor_handoff_validation"]),
            ("checkpoint_transform_sha256", result["checkpoint_transform"]),
        ):
            self.assertEqual(result[field], sha256(canonical_bytes(value)), field)
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        self.assertTrue(result["diagnostic_candidate_ladder_precommitted_before_replay"])
        self.assertTrue(result["diagnostic_horizon_precommitted_before_replay"])
        self.assertFalse(
            result["predecessor_handoff_validation"]["q70_outcome_precommitted"]
        )

    def test_08_four_mib_atomic_output_is_failure_preserving(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "D-q70.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"[]"))
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                SCREEN.write_atomic_bounded(
                    output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1)
                )
            self.assertEqual(output.read_bytes(), b"{}")
            replace_error = OSError("replace sentinel")
            original_replace = SCREEN.os.replace
            try:
                SCREEN.os.replace = lambda *_args: (_ for _ in ()).throw(
                    replace_error
                )
                with self.assertRaises(OSError) as caught:
                    SCREEN.write_atomic_bounded(output, b"[]")
                self.assertIs(caught.exception, replace_error)
            finally:
                SCREEN.os.replace = original_replace
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(list(pathlib.Path(directory).glob("*.tmp")), [])

    def test_09_scope_is_D_only_diagnostic_only_and_no_outcome_claim(self):
        self.assertEqual(SCREEN.MODE, "double_occupancy")
        self.assertEqual(SCREEN.BASE_PARENT_HORIZON, 66)
        self.assertEqual(SCREEN.EXTENDED_HORIZON, 70)
        source = (HERE / SCREEN.SELF_NAME).read_text()
        for forbidden in (
            "READY_FOR_BENCHMARK",
            "formal_witness",
            "child_boundary_sidecar",
            "positive_certificate",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"q70_outcome_precommitted": False', source)

    def test_10_canonical_artifact_if_present_has_exact_contract_and_ledger(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical D K589824/C34 q70 transcript not generated")
        raw = path.read_bytes()
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(transcript["attempted_checkpoint_count"], 70)
        self.assertEqual(transcript["completed_checkpoint_count"], 69)
        self.assertEqual(
            transcript["screen_terminal_condition"],
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        )
        self.assertTrue(transcript["failure_checkpoint_included"])
        self.assertFalse(transcript["horizon_reached_with_committed_checkpoint"])
        self.assertEqual(len(transcript["records"]), 70)
        self.assertEqual(len(transcript["selected_K_history"]), 69)
        exact_fields = {
            "candidate_K_values_sha256": "candidate_sha256",
            "records_sha256": "records_sha256",
            "selected_K_history_sha256": "history_sha256",
            "failure_record_sha256": "failure_sha256",
            "screen_execution_components_sha256": "components_sha256",
            "configuration_reference_sha256": "configuration_reference_sha256",
            "configuration_override_sha256": "configuration_override_sha256",
            "kernel_capability_override_sha256": "kernel_override_sha256",
            "parent_horizon_override_sha256": "parent_horizon_override_sha256",
            "route_predecessor_reference_sha256": "route_reference_sha256",
            "predecessor_handoff_validation_sha256": "handoff_sha256",
            "checkpoint_transform_sha256": "transform_sha256",
        }
        for transcript_field, expected_field in exact_fields.items():
            self.assertEqual(
                transcript[transcript_field],
                EXPECTED_CANONICAL[expected_field],
                transcript_field,
            )
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"],
            EXPECTED_CANONICAL["last_E"],
        )
        self.assertEqual(
            transcript["observed_peak_single_expansion_terms"],
            EXPECTED_CANONICAL["peak"],
        )
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            EXPECTED_CANONICAL["visits"],
        )
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            EXPECTED_CANONICAL["coefficient_bits"],
        )
        self.assertEqual(
            transcript["observed_maximum_product_bits"],
            EXPECTED_CANONICAL["product_bits"],
        )
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            EXPECTED_CANONICAL["rounding"],
        )
        self.assertEqual(
            transcript["candidate_K_values"], list(SCREEN.D_CANDIDATES)
        )
        self.assertEqual(
            transcript["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )
        predecessor, _reference = SCREEN.load_route_reference(HERE)
        SCREEN.validate_replay_handoff(transcript, predecessor)
        for new_record, old_record in zip(
            transcript["records"][:68], predecessor["records"][:68]
        ):
            new_common = copy.deepcopy(new_record)
            old_common = copy.deepcopy(old_record)
            new_rows = new_common.pop("candidate_records")
            old_rows = old_common.pop("candidate_records")
            self.assertEqual(new_common, old_common)
            self.assertEqual(new_rows[:33], old_rows)
        self.assertEqual(
            transcript["selected_K_history"][:68],
            predecessor["selected_K_history"],
        )
        self.assertEqual(set(transcript["selected_K_history"]),
                         set(SCREEN.D_CANDIDATES))
        q69 = transcript["records"][68]
        self.assertEqual(q69["checkpoint_number_one_based"], 69)
        self.assertEqual(q69["pretruncation_expansion_count"], 644_504)
        self.assertEqual(q69["prefix_slack_before_selection_ticks"],
                         "130082266158")
        self.assertEqual(q69["selected_candidate_index"], 33)
        self.assertEqual(q69["selected_K"], 589_824)
        self.assertEqual(q69["selected_drop_ticks"], "61286012190")
        self.assertEqual(q69["selected_dropped_term_count"], 54_680)
        self.assertEqual(q69["E_after_ticks"], EXPECTED_CANONICAL["last_E"])
        q70 = transcript["records"][69]
        self.assertEqual(q70["checkpoint_number_one_based"], 70)
        self.assertEqual(q70["gate_occurrence_first_zero_based"], 276)
        self.assertEqual(q70["gate_occurrence_last_zero_based"], 279)
        self.assertEqual(q70["stage_group"], "HU")
        self.assertEqual(q70["stage_index"], 2)
        self.assertEqual(q70["batch_in_stage"], 13)
        self.assertEqual(q70["input_expansion_count"], 589_824)
        self.assertEqual(q70["pretruncation_expansion_count"], 718_805)
        self.assertEqual(q70["budget_prefix_cap_ticks"], "2288924993833947")
        self.assertEqual(q70["prefix_slack_before_selection_ticks"],
                         "151298243902")
        self.assertEqual(q70["minimum_effective_K_to_meet_prefix"], 597_272)
        self.assertEqual(q70["required_K_excess_over_policy_maximum"], 7_448)
        self.assertEqual(
            q70["maximum_candidate_drop_excess_over_slack_ticks"],
            "49409820450",
        )
        final_row = q70["candidate_records"][-1]
        self.assertEqual(final_row["candidate_index"], 33)
        self.assertEqual(final_row["configured_K"], 589_824)
        self.assertEqual(final_row["drop_ticks"], "200708064352")
        self.assertEqual(final_row["dropped_term_count"], 128_981)
        self.assertFalse(final_row["feasible_under_current_prefix_cap"])
        self.assertEqual(
            transcript["records_sha256"],
            sha256(canonical_bytes(transcript["records"])),
        )
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            sha256(canonical_bytes(transcript["selected_K_history"])),
        )
        for checkpoint, record in enumerate(transcript["records"], start=1):
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint)
            rows = record["candidate_records"]
            self.assertEqual(
                [row["configured_K"] for row in rows], list(SCREEN.D_CANDIDATES)
            )
            self.assertEqual(
                [row["candidate_index"] for row in rows], list(range(34))
            )
            for row in rows:
                effective = min(
                    row["configured_K"], record["pretruncation_expansion_count"]
                )
                self.assertEqual(row["effective_retained_count"], effective)
                self.assertEqual(
                    row["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_D_K589824_C34_Q70_REPLAY") == "1",
        "set RUN_HUBBARD_L8_D_K589824_C34_Q70_REPLAY=1 for the expensive replay",
    )
    def test_11_opt_in_full_replay(self):
        result = SCREEN.run(HERE)
        raw = canonical_bytes(result)
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(result["attempted_checkpoint_count"], 70)
        self.assertIn(result["completed_checkpoint_count"], (69, 70))
        canonical_path = HERE / SCREEN.OUTPUT_NAME
        if canonical_path.exists():
            self.assertEqual(raw, canonical_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
