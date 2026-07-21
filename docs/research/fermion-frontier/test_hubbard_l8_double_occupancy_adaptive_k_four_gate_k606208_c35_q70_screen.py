#!/usr/bin/env python3
"""Static, synthetic, canonical and opt-in tests for the D C35 q70 screen."""

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
    "k606208_c35_q70_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "dffd720464566ef443909b5e7b01518ac82bf5defd68e72ce9de079422985068"
)
EXPECTED_CANONICAL = {
    "file_sha256": "55e9d305c90b62dea918071cd6ae383668c2ffb2f7dc108f7d4abcbcb772aa36",
    "candidate_sha256": "d69acf8cdc4e598e9734abe68a4d0a83cf7ea0618d38932b02c94c0aa8bfd161",
    "records_sha256": "9c22797b82cba9e41edbc117593e2cb364f3c6dd274c99c369a7f29ebbc95c39",
    "history_sha256": "d57dfeffe7e5e0056ad1b0294a015852af7788fe23187aad9d4484683f8f1cba",
    "components_sha256": "4d0a0a65781c24f0eb1835a46390ebfbfc9e500281c0f5fe584b670a385d1bd8",
    "configuration_reference_sha256": "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1",
    "configuration_override_sha256": "58a2164c967437fc1b1789d572fd043e6bbf594c8638b81a23c9bd279af69140",
    "kernel_override_sha256": "f7876b167475bdb18424e9cbd461506789ee59350b62302bf23146d0081fe4a3",
    "parent_horizon_override_sha256": "caabe92f91df1dc9daac6ab6ebafb384a7ada9f89b384229fe6e53a6e9b997cd",
    "route_reference_sha256": "2064d2784e3050b25709bcaeee6614d4e674f2d17bb7aaf389437a5eb85af111",
    "handoff_sha256": "b1577103103c44001832354c18439a303ff66e78ffba2881c676f9d5b8fdee53",
    "transform_sha256": "f4f9f9118cb1c2e75936f79122ee888d1f228bf7354ce282e4fa380e9349dce0",
    "last_E": "2288871542213247",
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


SCREEN = load_module("double_occupancy_k606208_c35_q70_for_tests", SCREEN_NAME)


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


class DoubleOccupancyK606208C35Q70Tests(unittest.TestCase):
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
        for checkpoint, old_record in enumerate(predecessor["records"][:69], 1):
            record = copy.deepcopy(old_record)
            pre_count = record["pretruncation_expansion_count"]
            effective = min(SCREEN.K606208, pre_count)
            E_before = int(record["E_before_ticks"])
            prefix_cap = int(record["budget_prefix_cap_ticks"])
            self.assertLessEqual(E_before, prefix_cap, checkpoint)
            record["candidate_records"].append({
                "candidate_index": 34,
                "configured_K": SCREEN.K606208,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": "0",
                "E_after_if_selected_ticks": str(E_before),
                "feasible_under_current_prefix_cap": True,
            })
            records.append(record)

        q70 = copy.deepcopy(predecessor["records"][69])
        for key in (
            "minimum_effective_K_to_meet_prefix",
            "required_K_excess_over_policy_maximum",
            "maximum_candidate_drop_excess_over_slack_ticks",
        ):
            q70.pop(key)
        pre_count = q70["pretruncation_expansion_count"]
        E_before = int(q70["E_before_ticks"])
        appended = {
            "candidate_index": 34,
            "configured_K": SCREEN.K606208,
            "effective_retained_count": SCREEN.K606208,
            "dropped_term_count": pre_count - SCREEN.K606208,
            "drop_ticks": "1",
            "E_after_if_selected_ticks": str(E_before + 1),
            "feasible_under_current_prefix_cap": True,
        }
        q70["candidate_records"].append(appended)
        q70.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 34,
            "selected_K": SCREEN.K606208,
            "selected_effective_retained_count": SCREEN.K606208,
            "selected_dropped_term_count": appended["dropped_term_count"],
            "selected_drop_ticks": appended["drop_ticks"],
            "selected_dropped_terms_sha256": "3" * 64,
            "retained_expansion_count": SCREEN.K606208,
            "retained_expansion_sha256": "4" * 64,
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": appended["E_after_if_selected_ticks"],
        })
        q70["removed_491520_counterfactual"]["actual_selected_K"] = (
            SCREEN.K606208
        )
        records.append(q70)
        history = predecessor["selected_K_history"] + [SCREEN.K606208]
        return records, history

    @staticmethod
    def rehash(result):
        result["records_sha256"] = sha256(canonical_bytes(result["records"]))
        result["selected_K_history_sha256"] = sha256(
            canonical_bytes(result["selected_K_history"])
        )

    def make_synthetic_parent_result(self, predecessor):
        records, history = self.make_synthetic_records(predecessor)
        components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        configuration = {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "source_sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        }
        transform = {"transform_id": "synthetic-original-four-gate-parent"}
        result = {
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
            "attempted_checkpoint_count": 70,
            "completed_checkpoint_count": 70,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "last_committed_cumulative_drop_ticks": records[69]["E_after_ticks"],
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
        for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS:
            if key not in result:
                result[key] = copy.deepcopy(predecessor[key])
        self.assertEqual(
            frozenset(result),
            SCREEN.EXPECTED_PARENT_RESULT_KEYS,
        )
        self.rehash(result)
        return result

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
        self.assertEqual(sha256(self_payload), EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            sha256(parent_payload), SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
        )
        self.assertEqual(
            sha256(v6_payload), SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
        )
        self.assertEqual(sha256(v2_payload), SCREEN.EXPECTED_V2_ARITHMETIC_SHA256)
        self.assertEqual(
            sha256(wrapper_payload), SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256
        )
        self.assertEqual(
            sha256(route_screen_payload),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        )
        self.assertEqual(
            sha256(route_raw),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(route_raw, canonical_bytes(json.loads(route_raw)))

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

    def test_02_D35_append_policy_kernel_and_D_only_horizon(self):
        SCREEN.validate_local_configuration()
        bundle = self.load_static_bundle()
        fresh, parent, configuration, baseline_d, kernel = bundle[:5]
        self.assertEqual(len(baseline_d), 32)
        self.assertEqual(
            SCREEN.PREDECESSOR_D_CANDIDATES,
            baseline_d[1:] + (
                SCREEN.K540672,
                SCREEN.K573440,
                SCREEN.K589824,
            ),
        )
        self.assertEqual(
            SCREEN.D_CANDIDATES,
            SCREEN.PREDECESSOR_D_CANDIDATES + (SCREEN.K606208,),
        )
        self.assertEqual(len(SCREEN.PREDECESSOR_D_CANDIDATES), 34)
        self.assertEqual(len(SCREEN.D_CANDIDATES), 35)
        self.assertEqual(
            sha256(canonical_bytes(list(SCREEN.D_CANDIDATES))),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            configuration.MODE_CONFIG[SCREEN.MODE]["candidates"],
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(
            kernel.validate_candidates(SCREEN.D_CANDIDATES),
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(kernel.validate_candidates((606_208,)), (606_208,))
        with self.assertRaises(kernel.SchemaError):
            kernel.validate_candidates((606_209,))
        with self.assertRaises(kernel.SchemaError):
            kernel.validate_candidates(tuple(range(1, 37)))

        explicit = {"max_candidate_K", "max_output_terms_if_successful"}
        for before in (
            SCREEN.EXPECTED_V6_POLICY_CAPS,
            SCREEN.EXPECTED_PREDECESSOR_POLICY_CAPS,
        ):
            self.assertEqual(
                SCREEN.changed_keys(before, SCREEN.POLICY_CAPS_BASE),
                explicit,
            )
        override = fresh.configuration_override(baseline_d)
        self.assertEqual(
            set(
                override["direct_execution_override_from_v6"]
                ["policy_cap_changes"]
            ),
            explicit,
        )
        self.assertEqual(
            set(
                override["incremental_route_override_from_k589824_c34_q70"]
                ["policy_cap_changes"]
            ),
            explicit,
        )
        self.assertEqual(
            override["derived_policy_cap"],
            {
                "field": "max_candidate_count",
                "derivation": "len(candidate_K_values)",
                "before_on_route": 34,
                "after": 35,
            },
        )
        self.assertEqual(
            kernel.RESOURCE_LIMITS,
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

        before = copy.deepcopy(parent.MODE_CONFIG)
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        self.assertEqual(
            horizon["changed_fields"],
            ["MODE_CONFIG.double_occupancy.horizon_checkpoint_count"],
        )
        self.assertEqual(before[SCREEN.MODE]["horizon_checkpoint_count"], 66)
        self.assertEqual(
            parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"],
            70,
        )
        self.assertEqual(
            parent.MODE_CONFIG["magnetization"],
            before["magnetization"],
        )
        pristine = fresh.load_control_flow_parent(HERE)
        self.assertEqual(
            pristine.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"],
            66,
        )

    def test_03_direct_parent_private_path_and_exception_identity(self):
        fresh = SCREEN.fresh_self_module()
        original_loader = fresh.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = original_loader(repo)
            parent.run = lambda *_args: self.fail("public parent entrypoint called")

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                observed["horizon"] = parent.MODE_CONFIG[mode][
                    "horizon_checkpoint_count"
                ]
                configured = parent.load_v6_configuration(inner_repo)
                observed["candidates"] = configured.MODE_CONFIG[mode]["candidates"]
                observed["caps"] = copy.deepcopy(configured.POLICY_CAPS_BASE)
                helper = parent.load_v2_helper(inner_repo)
                active, _root, _modules, _custody = parent.load_execution_sources(
                    inner_repo,
                    helper,
                    mode,
                )
                observed["limits"] = copy.deepcopy(active.RESOURCE_LIMITS)
                return {"direct_parent_private_result": True}

            parent._run_verified = private_sentinel
            return parent

        fresh.load_control_flow_parent = load_sentinel_parent
        fresh.validate_and_relabel = lambda result, *_args: result
        self.assertEqual(
            fresh._run_verified(HERE),
            {"direct_parent_private_result": True},
        )
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["horizon"], 70)
        self.assertEqual(observed["candidates"], SCREEN.D_CANDIDATES)
        self.assertEqual(observed["caps"], SCREEN.POLICY_CAPS_BASE)
        self.assertEqual(
            observed["limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

        resource_error = RuntimeError("D35 q70 resource sentinel")
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

    def test_04_route_refs_and_exact_component_schema_are_nonexecution(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, reference = fresh.load_route_reference(HERE)
        self.assertEqual(predecessor["attempted_checkpoint_count"], 70)
        self.assertEqual(predecessor["completed_checkpoint_count"], 69)
        q70 = predecessor["records"][-1]
        self.assertEqual(q70["checkpoint_number_one_based"], 70)
        self.assertEqual(q70["pretruncation_expansion_count"], 718_805)
        self.assertEqual(q70["minimum_effective_K_to_meet_prefix"], 597_272)
        self.assertEqual(q70["required_K_excess_over_policy_maximum"], 7_448)

        screen_reference = reference["screen"]
        for key in ("compiled", "executed", "execution_source_layer"):
            self.assertFalse(screen_reference[key], key)
        transcript = reference["canonical_transcript"]
        self.assertTrue(transcript["loaded_before_replay_as_exact_reference"])
        self.assertTrue(
            transcript["used_only_after_replay_for_result_prefix_validation"]
        )
        for key in (
            "propagation_input",
            "checkpoint_69_state_loaded",
            "checkpoint_70_state_loaded",
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
            "hubbard_l8_adaptive_k_arithmetic_k589824_c34.py",
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
        reordered = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        reordered[0], reordered[1] = reordered[1], reordered[0]
        with self.assertRaisesRegex(RuntimeError, "component schema drift"):
            fresh.execution_components(
                reordered,
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            )

    def test_05_q1_q69_exact_q70_success_ledger_and_tamper_rejection(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, _reference = fresh.load_route_reference(HERE)
        result = self.make_synthetic_parent_result(predecessor)
        validation = fresh.validate_replay_handoff(result, predecessor)
        self.assertTrue(validation["q1_through_q69_common_records_exact"])
        self.assertTrue(
            validation["q1_through_q69_first_34_candidate_rows_exact"]
        )
        self.assertTrue(validation["q1_through_q69_selected_history_exact"])
        self.assertTrue(validation["q70_shared_propagation_fields_exact"])
        self.assertTrue(validation["q70_first_34_candidate_rows_exact"])
        self.assertEqual(validation["q70_appended_candidate_index"], 34)
        self.assertEqual(
            validation["q70_appended_candidate_K"],
            SCREEN.K606208,
        )
        self.assertTrue(
            validation["q70_appended_candidate_is_first_feasible"]
        )
        self.assertTrue(
            validation["q70_terminal_success_validated_from_exact_ledger"]
        )
        self.assertFalse(validation["q70_outcome_precommitted"])
        self.assertEqual(
            sha256(canonical_bytes(result["selected_K_history"][:69])),
            SCREEN.EXPECTED_Q69_SELECTED_HISTORY_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(result["selected_K_history"])),
            SCREEN.EXPECTED_Q70_SELECTED_HISTORY_SHA256,
        )

        bad_common = copy.deepcopy(result)
        bad_common["records"][0]["E_before_ticks"] = "-1"
        self.rehash(bad_common)
        with self.assertRaisesRegex(RuntimeError, "q1 common record state"):
            fresh.validate_replay_handoff(bad_common, predecessor)

        bad_rows = copy.deepcopy(result)
        bad_rows["records"][1]["candidate_records"][0]["drop_ticks"] = "-1"
        self.rehash(bad_rows)
        with self.assertRaisesRegex(RuntimeError, "q2 predecessor rows"):
            fresh.validate_replay_handoff(bad_rows, predecessor)

        bad_shared = copy.deepcopy(result)
        bad_shared["records"][69]["gate_batch_sha256"] = "0" * 64
        self.rehash(bad_shared)
        with self.assertRaisesRegex(RuntimeError, "shared propagation fields"):
            fresh.validate_replay_handoff(bad_shared, predecessor)

        bad_q70_rows = copy.deepcopy(result)
        bad_q70_rows["records"][69]["candidate_records"][0]["drop_ticks"] = "-1"
        self.rehash(bad_q70_rows)
        with self.assertRaisesRegex(RuntimeError, "predecessor candidate rows"):
            fresh.validate_replay_handoff(bad_q70_rows, predecessor)

        bad_appended = copy.deepcopy(result)
        bad_appended["records"][69]["candidate_records"][34][
            "feasible_under_current_prefix_cap"
        ] = False
        self.rehash(bad_appended)
        with self.assertRaisesRegex(RuntimeError, "appended candidate drift"):
            fresh.validate_replay_handoff(bad_appended, predecessor)

        bad_selection = copy.deepcopy(result)
        bad_selection["records"][69]["selected_candidate_index"] = 33
        self.rehash(bad_selection)
        with self.assertRaisesRegex(RuntimeError, "success selection drift"):
            fresh.validate_replay_handoff(bad_selection, predecessor)

        bad_history = copy.deepcopy(result)
        bad_history["selected_K_history"][-1] = SCREEN.K589824
        self.rehash(bad_history)
        with self.assertRaisesRegex(RuntimeError, "success history drift"):
            fresh.validate_replay_handoff(bad_history, predecessor)

        bad_terminal = copy.deepcopy(result)
        bad_terminal["failure_checkpoint_included"] = True
        with self.assertRaisesRegex(RuntimeError, "success summary drift"):
            fresh.validate_replay_handoff(bad_terminal, predecessor)

        extra_q70_key = copy.deepcopy(result)
        extra_q70_key["records"][69]["untrusted_terminal_note"] = "accept"
        self.rehash(extra_q70_key)
        with self.assertRaisesRegex(
            RuntimeError,
            "transformed success record exact key-set drift",
        ):
            fresh.validate_replay_handoff(extra_q70_key, predecessor)

        missing_q70_key = copy.deepcopy(result)
        missing_q70_key["records"][69].pop("stage_group")
        self.rehash(missing_q70_key)
        with self.assertRaisesRegex(
            RuntimeError,
            "transformed success record exact key-set drift",
        ):
            fresh.validate_replay_handoff(missing_q70_key, predecessor)

        extra_q70_row_key = copy.deepcopy(result)
        extra_q70_row_key["records"][69]["candidate_records"][34][
            "untrusted_row_note"
        ] = "accept"
        self.rehash(extra_q70_row_key)
        with self.assertRaisesRegex(
            RuntimeError,
            "candidate row 34 exact key-set drift",
        ):
            fresh.validate_replay_handoff(extra_q70_row_key, predecessor)

        missing_q70_row_key = copy.deepcopy(result)
        missing_q70_row_key["records"][69]["candidate_records"][34].pop(
            "drop_ticks"
        )
        self.rehash(missing_q70_row_key)
        with self.assertRaisesRegex(
            RuntimeError,
            "candidate row 34 exact key-set drift",
        ):
            fresh.validate_replay_handoff(missing_q70_row_key, predecessor)

        extra_q1_appended_row_key = copy.deepcopy(result)
        extra_q1_appended_row_key["records"][0]["candidate_records"][34][
            "untrusted_row_note"
        ] = "accept"
        self.rehash(extra_q1_appended_row_key)
        with self.assertRaisesRegex(
            RuntimeError,
            "q1 appended candidate row exact key-set drift",
        ):
            fresh.validate_replay_handoff(
                extra_q1_appended_row_key,
                predecessor,
            )

        extra_top_level_key = copy.deepcopy(result)
        extra_top_level_key["untrusted_top_level_note"] = "accept"
        with self.assertRaisesRegex(
            RuntimeError,
            "top-level exact key-set drift",
        ):
            fresh.validate_replay_handoff(extra_top_level_key, predecessor)

        missing_top_level_key = copy.deepcopy(result)
        missing_top_level_key.pop("observable_id")
        with self.assertRaisesRegex(
            RuntimeError,
            "top-level exact key-set drift",
        ):
            fresh.validate_replay_handoff(missing_top_level_key, predecessor)

    def test_06_relabel_provenance_hashes_and_diagnostic_authority(self):
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
        ) = self.load_static_bundle()
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
            "k606208_c35_q70_screen_v1",
        )
        self.assertFalse(result["control_flow_owned_by_screen"])
        self.assertTrue(result["control_flow_owned_by_verified_parent"])
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertTrue(
            result["control_flow_parent_runtime_horizon_override_applied"]
        )
        roles = {
            item["relative_path"]: item["role"]
            for item in result["screen_execution_components"]
        }
        self.assertEqual(
            roles[SCREEN.SELF_NAME],
            "D_k606208_c35_q70_fresh_same_byte_screen",
        )
        self.assertEqual(
            roles[SCREEN.CONTROL_FLOW_PARENT_NAME],
            "four_gate_control_flow_parent_private_entrypoint",
        )
        self.assertEqual(
            roles[SCREEN.KERNEL_WRAPPER_NAME],
            "k606208_c35_capability_override_provider",
        )
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, roles)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, roles)
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
            (
                "screen_execution_components_sha256",
                result["screen_execution_components"],
            ),
            (
                "configuration_reference_sha256",
                result["configuration_reference"],
            ),
            (
                "configuration_override_sha256",
                result["configuration_override"],
            ),
            (
                "kernel_capability_override_sha256",
                result["kernel_capability_override"],
            ),
            (
                "parent_horizon_override_sha256",
                result["parent_horizon_override"],
            ),
            (
                "route_predecessor_reference_sha256",
                result["route_predecessor_reference"],
            ),
            (
                "predecessor_handoff_validation_sha256",
                result["predecessor_handoff_validation"],
            ),
            ("checkpoint_transform_sha256", result["checkpoint_transform"]),
        ):
            self.assertEqual(
                result[field],
                sha256(canonical_bytes(value)),
                field,
            )
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        self.assertTrue(
            result["diagnostic_candidate_ladder_precommitted_before_replay"]
        )
        self.assertTrue(
            result["diagnostic_horizon_precommitted_before_replay"]
        )
        self.assertFalse(result["checkpoint_transform"]["q70_outcome_precommitted"])
        self.assertEqual(
            result["screen_terminal_condition"],
            "DIAGNOSTIC_HORIZON_REACHED",
        )
        self.assertEqual(result["completed_checkpoint_count"], 70)
        self.assertFalse(result["failure_checkpoint_included"])

        extra_final_top_level = copy.deepcopy(result)
        extra_final_top_level["untrusted_top_level_note"] = "accept"
        with self.assertRaisesRegex(
            RuntimeError,
            "top-level exact key-set drift",
        ):
            fresh.validate_replay_handoff(
                extra_final_top_level,
                predecessor,
            )
        missing_final_top_level = copy.deepcopy(result)
        missing_final_top_level.pop("control_flow_parent_source_sha256")
        with self.assertRaisesRegex(
            RuntimeError,
            "top-level exact key-set drift",
        ):
            fresh.validate_replay_handoff(
                missing_final_top_level,
                predecessor,
            )

    def test_07_four_mib_atomic_output_is_failure_preserving(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "D35-q70.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"[]"))
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                SCREEN.write_atomic_bounded(
                    output,
                    b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1),
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

    def test_08_canonical_artifact_if_present_has_exact_success_contract(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical D K606208/C35 q70 transcript not generated")
        raw = path.read_bytes()
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(
            transcript["screen_source_sha256"],
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(
            transcript["candidate_K_values"],
            list(SCREEN.D_CANDIDATES),
        )
        self.assertEqual(
            transcript["candidate_K_values_sha256"],
            EXPECTED_CANONICAL["candidate_sha256"],
        )
        self.assertEqual(transcript["attempted_checkpoint_count"], 70)
        self.assertEqual(transcript["completed_checkpoint_count"], 70)
        self.assertEqual(
            transcript["screen_terminal_condition"],
            "DIAGNOSTIC_HORIZON_REACHED",
        )
        self.assertFalse(transcript["failure_checkpoint_included"])
        self.assertIsNone(transcript["failure_record_sha256"])
        self.assertTrue(
            transcript["horizon_reached_with_committed_checkpoint"]
        )
        self.assertEqual(len(transcript["records"]), 70)
        self.assertEqual(len(transcript["selected_K_history"]), 70)
        exact_fields = {
            "records_sha256": "records_sha256",
            "selected_K_history_sha256": "history_sha256",
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
        self.assertEqual(transcript["observed_peak_single_expansion_terms"],
                         EXPECTED_CANONICAL["peak"])
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            EXPECTED_CANONICAL["visits"],
        )
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            EXPECTED_CANONICAL["coefficient_bits"],
        )
        self.assertEqual(transcript["observed_maximum_product_bits"],
                         EXPECTED_CANONICAL["product_bits"])
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            EXPECTED_CANONICAL["rounding"],
        )
        for field in (
            "screen_execution_components",
            "configuration_reference",
            "configuration_override",
            "kernel_capability_override",
            "parent_horizon_override",
            "route_predecessor_reference",
            "predecessor_handoff_validation",
            "checkpoint_transform",
        ):
            self.assertEqual(
                transcript[f"{field}_sha256"],
                sha256(canonical_bytes(transcript[field])),
                field,
            )
        predecessor, _reference = SCREEN.load_route_reference(HERE)
        validation = SCREEN.validate_replay_handoff(transcript, predecessor)
        self.assertTrue(
            validation["q70_terminal_success_validated_from_exact_ledger"]
        )
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
        self.assertEqual(q70["selected_candidate_index"], 34)
        self.assertEqual(q70["selected_K"], SCREEN.K606208)
        self.assertEqual(q70["selected_drop_ticks"], "97846623202")
        self.assertEqual(q70["selected_dropped_term_count"], 112_597)
        self.assertEqual(q70["E_before_ticks"], "2288773695590045")
        self.assertEqual(q70["E_after_ticks"], EXPECTED_CANONICAL["last_E"])
        self.assertEqual(
            int(q70["budget_prefix_cap_ticks"]) - int(q70["E_after_ticks"]),
            53_451_620_700,
        )
        final_row = q70["candidate_records"][34]
        self.assertEqual(final_row["configured_K"], 606_208)
        self.assertEqual(final_row["drop_ticks"], "97846623202")
        self.assertEqual(final_row["dropped_term_count"], 112_597)
        self.assertTrue(
            final_row["feasible_under_current_prefix_cap"]
        )
        self.assertTrue(
            all(
                row["feasible_under_current_prefix_cap"] is False
                for row in q70["candidate_records"][:34]
            )
        )
        self.assertEqual(
            set(transcript["selected_K_history"]),
            set(SCREEN.D_CANDIDATES),
        )
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])

    def test_09_scope_is_D_only_diagnostic_and_replay_is_opt_in(self):
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

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_D_K606208_C35_Q70_REPLAY") == "1",
        "set RUN_HUBBARD_L8_D_K606208_C35_Q70_REPLAY=1 for replay",
    )
    def test_10_opt_in_full_replay(self):
        result = SCREEN.run(HERE)
        raw = canonical_bytes(result)
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(
            result["screen_source_sha256"],
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(result["attempted_checkpoint_count"], 70)
        self.assertEqual(result["completed_checkpoint_count"], 70)
        self.assertEqual(
            result["screen_terminal_condition"],
            "DIAGNOSTIC_HORIZON_REACHED",
        )
        canonical_path = HERE / SCREEN.OUTPUT_NAME
        if canonical_path.exists():
            self.assertEqual(raw, canonical_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
