#!/usr/bin/env python3
"""Static, synthetic, canonical and opt-in tests for the D C33 q68 screen."""

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
    "k573440_c33_q68_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "3c4dfb8aca29b6a5903d2aedd52f85409941d1c16050760f6b24453d9585d67b"
)
EXPECTED_KERNEL_SHA256 = (
    "811a16b6a47bca60281fb4afe8280783146e6f4ee28955dde7907b47fc65bb49"
)
EXPECTED_KERNEL_MANIFEST_SHA256 = (
    "c2787b105553b80ee9a1e5e1d925d6cac2ab819b0cdfab305484bf89bbba32c5"
)
EXPECTED_CANONICAL = {
    "file_sha256": (
        "b1f072c84cc676151fe3cddbb8a0db445df946f299dbb81f41e34f765d30dfc8"
    ),
    "records_sha256": (
        "e26a869b24da95eb586604a36dadc23371f82961a9b5f76723bdbf6377891d3f"
    ),
    "history_sha256": (
        "e2d036fab34ed4a6d1b9e09309a2a83c8a9e69afaff2ca9add92505b72557607"
    ),
    "components_sha256": (
        "f0396c53c43fce70a5db4dfc2773e8e581c885407d5eafdd655eccf8a410d430"
    ),
    "configuration_reference_sha256": (
        "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1"
    ),
    "configuration_override_sha256": (
        "0adef0f97fecd987da077815194a1a1258d4b832de045b275eaf6f0f40216aa4"
    ),
    "kernel_override_sha256": (
        "a3ad822405707e687ac6408ec10dfce559118f073fa7868291dbce25954af1dd"
    ),
    "horizon_override_sha256": (
        "40f1547dad3ce237b6676c80df7bb9ee1ef1d6b7030b47a4f7de447dca0207d4"
    ),
    "route_reference_sha256": (
        "6bed98a407a7c05e1ae8883678421e1ede7a18d1998a8eea65ab49458ec10685"
    ),
    "handoff_sha256": (
        "bd212a7d175c58e598807de8541accc6df1f39546f2d2521cf96ce44e2bccd26"
    ),
    "transform_sha256": (
        "ae19cf9376d99da42bda9684c675ac2e8b769e914acac1e8ff9f2fe3170f1ac1"
    ),
    "last_E": "2288712409577855",
    "peak": 688_548,
    "visits": 82_618_707,
    "coefficient_bits": 63,
    "product_bits": 120,
    "rounding": "109841801738477555399508152",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("double_occupancy_k573440_c33_q68_for_tests", SCREEN_NAME)


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


class DoubleOccupancyK573440C33Q68Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def load_static_bundle(self):
        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_control_flow_parent(HERE)
        configuration, baseline_d = fresh.load_configured_v6_baseline(HERE)
        kernel, kernel_sha, manifest = fresh.load_kernel_wrapper(HERE)
        predecessor, predecessor_reference = (
            fresh.load_route_predecessor_reference(HERE)
        )
        return (
            fresh,
            parent,
            configuration,
            baseline_d,
            kernel,
            kernel_sha,
            manifest,
            predecessor,
            predecessor_reference,
        )

    def make_synthetic_records(self, predecessor):
        records = []
        for old_record in predecessor["records"][:65]:
            record = copy.deepcopy(old_record)
            pre_count = record["pretruncation_expansion_count"]
            effective = min(SCREEN.K573440, pre_count)
            record["candidate_records"].append({
                "candidate_index": 32,
                "configured_K": SCREEN.K573440,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": "0",
                "E_after_if_selected_ticks": record["E_before_ticks"],
                "feasible_under_current_prefix_cap": True,
            })
            records.append(record)

        q66 = copy.deepcopy(predecessor["records"][65])
        for key in (
            "minimum_effective_K_to_meet_prefix",
            "required_K_excess_over_policy_maximum",
            "maximum_candidate_drop_excess_over_slack_ticks",
        ):
            q66.pop(key)
        q66["candidate_records"].append({
            "candidate_index": 32,
            "configured_K": SCREEN.K573440,
            "effective_retained_count": SCREEN.K573440,
            "dropped_term_count": 105_845,
            "drop_ticks": "0",
            "E_after_if_selected_ticks": q66["E_before_ticks"],
            "feasible_under_current_prefix_cap": True,
        })
        q66.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 32,
            "selected_K": SCREEN.K573440,
            "selected_effective_retained_count": SCREEN.K573440,
            "selected_dropped_term_count": 105_845,
            "selected_drop_ticks": "0",
            "selected_dropped_terms_sha256": "1" * 64,
            "retained_expansion_count": SCREEN.K573440,
            "retained_expansion_sha256": "2" * 64,
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": q66["E_before_ticks"],
        })
        q66["removed_491520_counterfactual"]["actual_selected_K"] = (
            SCREEN.K573440
        )
        records.append(q66)
        records.append({
            "checkpoint_number_one_based": 67,
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        })
        history = predecessor["selected_K_history"] + [SCREEN.K573440]
        return records, history

    def make_synthetic_parent_result(self, predecessor):
        records, history = self.make_synthetic_records(predecessor)
        components = [
            {
                "relative_path": SCREEN.CONTROL_FLOW_PARENT_NAME,
                "role": "four_gate_screen_execution_source",
                "sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            },
            {
                "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
                "role": "v6_candidates_and_caps_reference_only",
                "sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            },
            {
                "relative_path": SCREEN.V2_ARITHMETIC_NAME,
                "role": "v2_arithmetic_kernel",
                "sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            },
        ]
        configuration = {
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
                SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
            ),
            "records": records,
            "selected_K_history": history,
            "records_sha256": sha256(canonical_bytes(records)),
            "selected_K_history_sha256": sha256(canonical_bytes(history)),
            "attempted_checkpoint_count": 67,
            "completed_checkpoint_count": 66,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
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
                SCREEN.V2_ARITHMETIC_NAME: (
                    SCREEN.EXPECTED_V2_ARITHMETIC_SHA256
                ),
            },
        }

    def test_01_exact_source_pins_and_isolated_loaders(self):
        self_payload = (HERE / SCREEN.SELF_NAME).read_bytes()
        parent_payload = (HERE / SCREEN.CONTROL_FLOW_PARENT_NAME).read_bytes()
        v6_payload = (HERE / SCREEN.V6_BASELINE_CONFIGURATION_NAME).read_bytes()
        v2_payload = (HERE / SCREEN.V2_ARITHMETIC_NAME).read_bytes()
        kernel_payload = (HERE / SCREEN.KERNEL_WRAPPER_NAME).read_bytes()
        predecessor_screen_payload = (
            HERE / SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME
        ).read_bytes()
        predecessor_raw = (
            HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME
        ).read_bytes()
        self.assertEqual(sha256(self_payload), EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            sha256(parent_payload), SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
        )
        self.assertEqual(
            sha256(v6_payload), SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
        )
        self.assertEqual(sha256(v2_payload), SCREEN.EXPECTED_V2_ARITHMETIC_SHA256)
        self.assertEqual(sha256(kernel_payload), EXPECTED_KERNEL_SHA256)
        self.assertEqual(
            sha256(predecessor_screen_payload),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        )
        self.assertEqual(
            sha256(predecessor_raw),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(predecessor_raw, canonical_bytes(json.loads(predecessor_raw)))

        first = SCREEN.fresh_self_module()
        second = SCREEN.fresh_self_module()
        self.assertIsNot(first, second)
        self.assertEqual(first._VERIFIED_SELF_SOURCE_BYTES, self_payload)
        first_parent = first.load_control_flow_parent(HERE)
        second_parent = first.load_control_flow_parent(HERE)
        self.assertIsNot(first_parent, second_parent)
        self.assertEqual(first_parent._VERIFIED_SELF_SOURCE_BYTES, parent_payload)

        kernel, observed, manifest = first.load_kernel_wrapper(HERE)
        self.assertEqual(observed, EXPECTED_KERNEL_SHA256)
        self.assertEqual(kernel._VERIFIED_SELF_SOURCE_BYTES, kernel_payload)
        self.assertEqual(kernel._VERIFIED_BASE_KERNEL_SOURCE_BYTES, v2_payload)
        self.assertEqual(
            kernel.capability_manifest_sha256(), EXPECTED_KERNEL_MANIFEST_SHA256
        )
        self.assertEqual(
            sha256(canonical_bytes(manifest)), EXPECTED_KERNEL_MANIFEST_SHA256
        )
        pinned = kernel.load_pinned_capability(EXPECTED_KERNEL_SHA256)
        self.assertIsNot(pinned, kernel)
        with self.assertRaisesRegex(RuntimeError, "source pin drift"):
            kernel.load_pinned_capability("0" * 64)
        for invalid in (None, b"0" * 64, "A" * 64, "0" * 63):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaisesRegex(RuntimeError, "canonical lowercase hex"):
                    kernel.load_pinned_capability(invalid)

    def test_02_D33_exact_append_candidate_digest_and_kernel_boundary(self):
        SCREEN.validate_local_configuration()
        fresh, _parent, configuration, baseline_d, kernel, *_rest = (
            self.load_static_bundle()
        )
        self.assertEqual(len(baseline_d), 32)
        self.assertEqual(baseline_d[0], 65_536)
        self.assertEqual(
            SCREEN.PREDECESSOR_D_CANDIDATES,
            baseline_d[1:] + (540_672,),
        )
        self.assertEqual(
            SCREEN.D_CANDIDATES,
            SCREEN.PREDECESSOR_D_CANDIDATES + (573_440,),
        )
        self.assertEqual(len(SCREEN.D_CANDIDATES), 33)
        self.assertTrue(all(
            left < right
            for left, right in zip(SCREEN.D_CANDIDATES, SCREEN.D_CANDIDATES[1:])
        ))
        self.assertEqual(
            sha256(canonical_bytes(list(SCREEN.D_CANDIDATES))),
            "461517a4e7d5f6ffbb610b53240f01071cc7f7a9ac1b2dfdbc6e4b0addd59a27",
        )
        self.assertEqual(
            configuration.MODE_CONFIG[SCREEN.MODE]["candidates"],
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(
            kernel.validate_candidates(SCREEN.D_CANDIDATES),
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(kernel.validate_candidates((573_440,)), (573_440,))
        with self.assertRaises(kernel.SchemaError):
            kernel.validate_candidates((573_441,))
        with self.assertRaises(kernel.SchemaError):
            kernel.validate_candidates(tuple(range(1, 35)))
        self.assertEqual(
            fresh.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS["max_candidate_count"],
            33,
        )

    def test_03_policy_has_two_explicit_K_changes_and_one_derived_count(self):
        explicit = {"max_candidate_K", "max_output_terms_if_successful"}
        for before in (
            SCREEN.EXPECTED_V6_POLICY_CAPS,
            SCREEN.EXPECTED_PREDECESSOR_POLICY_CAPS,
        ):
            changed = {
                key for key in set(before) | set(SCREEN.POLICY_CAPS_BASE)
                if before.get(key) != SCREEN.POLICY_CAPS_BASE.get(key)
            }
            self.assertEqual(changed, explicit)
            for key in before:
                if key not in explicit:
                    self.assertEqual(SCREEN.POLICY_CAPS_BASE[key], before[key])
        self.assertEqual(SCREEN.POLICY_CAPS_BASE["max_candidate_K"], 573_440)
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_output_terms_if_successful"],
            573_440,
        )
        fresh, _parent, configuration, baseline_d, *_rest = self.load_static_bundle()
        self.assertEqual(configuration.POLICY_CAPS_BASE, SCREEN.POLICY_CAPS_BASE)
        override = fresh.configuration_override(baseline_d)
        self.assertEqual(
            set(override["direct_execution_override_from_v6"]["policy_cap_changes"]),
            explicit,
        )
        self.assertEqual(
            set(
                override["incremental_route_override_from_k540672"]
                ["policy_cap_changes"]
            ),
            explicit,
        )
        self.assertEqual(
            override["derived_policy_cap"],
            {
                "field": "max_candidate_count",
                "derivation": "len(candidate_K_values)",
                "before_on_route": 32,
                "after": 33,
            },
        )
        self.assertEqual(
            {
                **configuration.POLICY_CAPS_BASE,
                "max_candidate_count": len(SCREEN.D_CANDIDATES),
            }["max_candidate_count"],
            33,
        )

    def test_04_parent_only_changes_D_horizon_and_pristine_parent_stays_66(self):
        bundle = self.load_static_bundle()
        fresh, parent, configuration, _baseline_d, kernel = bundle[:5]
        before = copy.deepcopy(parent.MODE_CONFIG)
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        after = parent.MODE_CONFIG
        changed = []
        for mode, before_mode in before.items():
            for key, before_value in before_mode.items():
                if after[mode].get(key) != before_value:
                    changed.append(f"MODE_CONFIG.{mode}.{key}")
        self.assertEqual(
            changed,
            ["MODE_CONFIG.double_occupancy.horizon_checkpoint_count"],
        )
        self.assertEqual(before[SCREEN.MODE]["horizon_checkpoint_count"], 66)
        self.assertEqual(after[SCREEN.MODE]["horizon_checkpoint_count"], 68)
        self.assertEqual(before["magnetization"], after["magnetization"])
        self.assertEqual(horizon["changed_fields"], changed)
        self.assertEqual(
            horizon["parent_mode_config_before_sha256"],
            sha256(canonical_bytes(before)),
        )
        self.assertEqual(
            horizon["parent_mode_config_after_sha256"],
            sha256(canonical_bytes(after)),
        )
        self.assertIs(parent.load_v6_configuration(HERE), configuration)
        pristine = fresh.load_control_flow_parent(HERE)
        self.assertEqual(
            pristine.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 66
        )
        self.assertEqual(
            pristine.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"],
            80,
        )

    def test_05_public_fresh_path_real_private_sentinel_and_exception_identity(self):
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

        fresh = SCREEN.fresh_self_module()
        original_loader = fresh.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = original_loader(repo)

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                observed["D_horizon"] = parent.MODE_CONFIG[mode][
                    "horizon_checkpoint_count"
                ]
                observed["M_config"] = copy.deepcopy(
                    parent.MODE_CONFIG["magnetization"]
                )
                configured = parent.load_v6_configuration(inner_repo)
                observed["candidates"] = configured.MODE_CONFIG[mode]["candidates"]
                observed["caps"] = copy.deepcopy(configured.POLICY_CAPS_BASE)
                helper = parent.load_v2_helper(inner_repo)
                active_kernel, _root, _modules, _custody = (
                    parent.load_execution_sources(inner_repo, helper, mode)
                )
                observed["kernel_limits"] = copy.deepcopy(
                    active_kernel.RESOURCE_LIMITS
                )
                return {"private_parent_result": True}

            parent._run_verified = private_sentinel
            return parent

        fresh.load_control_flow_parent = load_sentinel_parent
        fresh.validate_and_relabel = lambda result, *_args: result
        result = fresh._run_verified(HERE)
        self.assertEqual(result, {"private_parent_result": True})
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["D_horizon"], 68)
        self.assertEqual(observed["M_config"]["horizon_checkpoint_count"], 80)
        self.assertEqual(observed["candidates"], SCREEN.D_CANDIDATES)
        self.assertEqual(observed["caps"], SCREEN.POLICY_CAPS_BASE)
        self.assertEqual(
            observed["kernel_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

        resource_error = RuntimeError("D q68 resource sentinel")
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

    def test_06_predecessor_is_reference_only_and_never_state_resume(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, reference = fresh.load_route_predecessor_reference(HERE)
        screen_reference = reference["screen"]
        transcript_reference = reference["canonical_transcript"]
        self.assertFalse(screen_reference["compiled"])
        self.assertFalse(screen_reference["executed"])
        self.assertFalse(screen_reference["execution_source_layer"])
        self.assertTrue(
            transcript_reference["loaded_before_replay_as_exact_reference"]
        )
        self.assertTrue(
            transcript_reference[
                "used_only_after_replay_for_result_prefix_validation"
            ]
        )
        for key in (
            "propagation_input",
            "checkpoint_65_state_loaded",
            "checkpoint_66_state_loaded",
            "state_resume_input",
            "execution_source_layer",
        ):
            self.assertFalse(transcript_reference[key], key)
        self.assertEqual(predecessor["attempted_checkpoint_count"], 66)
        self.assertEqual(predecessor["completed_checkpoint_count"], 65)
        q66 = predecessor["records"][-1]
        self.assertEqual(q66["minimum_effective_K_to_meet_prefix"], 558_598)
        self.assertEqual(q66["required_K_excess_over_policy_maximum"], 17_926)
        self.assertEqual(558_598 - 557_056, 1_542)
        self.assertEqual(573_440 - 557_056, 16_384)

        components = fresh.execution_components(
            [
                {
                    "relative_path": SCREEN.CONTROL_FLOW_PARENT_NAME,
                    "sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
                },
                {
                    "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
                    "sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
                },
                {
                    "relative_path": SCREEN.V2_ARITHMETIC_NAME,
                    "sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
                },
            ],
            EXPECTED_SCREEN_SHA256,
            EXPECTED_KERNEL_SHA256,
        )
        paths = [item["relative_path"] for item in components]
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        self.assertEqual(
            paths,
            [
                SCREEN.SELF_NAME,
                SCREEN.CONTROL_FLOW_PARENT_NAME,
                SCREEN.V6_BASELINE_CONFIGURATION_NAME,
                SCREEN.V2_ARITHMETIC_NAME,
                SCREEN.KERNEL_WRAPPER_NAME,
            ],
        )

    def test_07_synthetic_prefix_and_q66_handoff_accepts_exact_fixture(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, _reference = fresh.load_route_predecessor_reference(HERE)
        records, history = self.make_synthetic_records(predecessor)
        result = {
            "records": records,
            "selected_K_history": history,
            "records_sha256": sha256(canonical_bytes(records)),
            "selected_K_history_sha256": sha256(canonical_bytes(history)),
            "attempted_checkpoint_count": 67,
            "completed_checkpoint_count": 66,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
        }
        validation = fresh.validate_replay_handoff(result, predecessor)
        self.assertTrue(validation["q1_through_q65_common_records_exact"])
        self.assertTrue(validation["q1_through_q65_first_32_candidate_rows_exact"])
        self.assertTrue(validation["q66_shared_propagation_fields_exact"])
        self.assertTrue(validation["q66_first_32_candidate_rows_exact"])
        self.assertEqual(validation["q66_selected_candidate_index"], 32)
        self.assertEqual(validation["q66_selected_K"], 573_440)
        self.assertFalse(validation["q67_and_q68_outcomes_precommitted"])
        self.assertEqual(
            sha256(canonical_bytes(history[:66])),
            SCREEN.EXPECTED_Q66_SELECTED_HISTORY_PREFIX_SHA256,
        )

        bad_common = copy.deepcopy(result)
        bad_common["records"][0]["E_before_ticks"] = "-1"
        bad_common["records_sha256"] = sha256(
            canonical_bytes(bad_common["records"])
        )
        with self.assertRaisesRegex(RuntimeError, "q1 common record state"):
            fresh.validate_replay_handoff(bad_common, predecessor)

        bad_rows = copy.deepcopy(result)
        bad_rows["records"][1]["candidate_records"][0]["drop_ticks"] = "-1"
        bad_rows["records_sha256"] = sha256(canonical_bytes(bad_rows["records"]))
        with self.assertRaisesRegex(RuntimeError, "q2 predecessor candidate rows"):
            fresh.validate_replay_handoff(bad_rows, predecessor)

        bad_q66 = copy.deepcopy(result)
        bad_q66["records"][65]["selected_K"] = 573_439
        bad_q66["records_sha256"] = sha256(canonical_bytes(bad_q66["records"]))
        with self.assertRaisesRegex(RuntimeError, "q66 handoff drift: selected_K"):
            fresh.validate_replay_handoff(bad_q66, predecessor)

    def test_08_synthetic_outer_provenance_hashes_roles_and_authority(self):
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
            predecessor_reference,
        ) = bundle
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        result = fresh.validate_and_relabel(
            self.make_synthetic_parent_result(predecessor),
            predecessor,
            predecessor_reference,
            baseline_d,
            kernel_sha,
            manifest,
            horizon,
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q68_screen_v1",
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
            roles[SCREEN.SELF_NAME],
            "D_k573440_c33_q68_fresh_same_byte_screen",
        )
        self.assertEqual(
            roles[SCREEN.CONTROL_FLOW_PARENT_NAME],
            "four_gate_control_flow_parent_private_entrypoint",
        )
        self.assertEqual(
            roles[SCREEN.KERNEL_WRAPPER_NAME],
            "k573440_c33_capability_override_provider",
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
        self.assertEqual(
            result["parent_horizon_override"]["changed_fields"],
            ["MODE_CONFIG.double_occupancy.horizon_checkpoint_count"],
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

    def test_09_four_mib_atomic_output_is_failure_preserving(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "D-q68.json"
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

    def test_10_scope_is_D_only_and_diagnostic_only(self):
        self.assertEqual(SCREEN.MODE, "double_occupancy")
        self.assertEqual(SCREEN.BASE_PARENT_HORIZON, 66)
        self.assertEqual(SCREEN.EXTENDED_HORIZON, 68)
        source = (HERE / SCREEN.SELF_NAME).read_text()
        for forbidden in (
            "READY_FOR_BENCHMARK",
            "formal_witness",
            "child_boundary_sidecar",
            "positive_certificate",
        ):
            self.assertNotIn(forbidden, source)

    def assert_full_canonical_ledger(self, transcript, predecessor):
        candidates = list(SCREEN.D_CANDIDATES)
        records = transcript["records"]
        history = transcript["selected_K_history"]
        E_input = int(transcript["input_cumulative_drop_ticks"])
        maximum_drop = int(transcript["maximum_cumulative_drop_ticks"])
        denominator = transcript["future_checkpoint_denominator"]
        cumulative = E_input
        visits = 0
        rounding = 0
        peak = 0
        coefficient_bits = 0
        product_bits = 0
        selected_history = []
        previous = None

        parent = SCREEN.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        base_kernel, root, _modules, _custody = parent.load_execution_sources(
            HERE,
            helper,
            SCREEN.MODE,
        )
        stages, _trig, sequence, _transform = parent.build_four_gate_sequence(
            helper,
            root,
            base_kernel,
        )
        gates = [gate for stage in stages for gate in stage["gates"]]
        self.assertEqual(len(gates), sequence["gate_count"])

        for index, record in enumerate(records):
            checkpoint = index + 1
            self.assertEqual(record["checkpoint_index_zero_based"], index)
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint)
            self.assertEqual(record["gate_occurrence_first_zero_based"], 4 * index)
            self.assertEqual(record["gate_occurrence_last_zero_based"], 4 * index + 3)
            self.assertEqual(
                record["gate_batch_sha256"],
                helper.gate_batch_sha256(gates[4 * index:4 * index + 4]),
            )
            if previous is not None:
                self.assertEqual(
                    record["input_expansion_count"],
                    previous["retained_expansion_count"],
                )
                self.assertEqual(
                    record["input_expansion_sha256"],
                    previous["retained_expansion_sha256"],
                )
            cap = E_input + checkpoint * (maximum_drop - E_input) // denominator
            self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
            self.assertEqual(int(record["E_before_ticks"]), cumulative)
            slack = cap - cumulative
            self.assertEqual(int(record["prefix_slack_before_selection_ticks"]), slack)

            visits += record["term_gate_visits_increment"]
            self.assertEqual(record["term_gate_visits_cumulative"], visits)
            rounding += int(record["rounding_increment_scaled_ticks_squared"])
            self.assertEqual(
                int(record["rounding_cumulative_scaled_ticks_squared"]),
                rounding,
            )
            peak = max(peak, record["peak_live_terms_this_checkpoint"])
            self.assertEqual(record["peak_live_terms_cumulative"], peak)
            self.assertGreaterEqual(
                record["maximum_expansion_coefficient_tick_bits"], coefficient_bits
            )
            self.assertGreaterEqual(record["maximum_product_bits"], product_bits)
            coefficient_bits = record["maximum_expansion_coefficient_tick_bits"]
            product_bits = record["maximum_product_bits"]

            rows = record["candidate_records"]
            self.assertEqual([row["configured_K"] for row in rows], candidates)
            drops = []
            feasible_indices = []
            for candidate_index, row in enumerate(rows):
                self.assertEqual(row["candidate_index"], candidate_index)
                effective = min(
                    row["configured_K"], record["pretruncation_expansion_count"]
                )
                self.assertEqual(row["effective_retained_count"], effective)
                self.assertEqual(
                    row["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                drop = int(row["drop_ticks"])
                drops.append(drop)
                self.assertEqual(
                    int(row["E_after_if_selected_ticks"]), cumulative + drop
                )
                feasible = cumulative + drop <= cap
                self.assertIs(row["feasible_under_current_prefix_cap"], feasible)
                if feasible:
                    feasible_indices.append(candidate_index)
            self.assertEqual(drops, sorted(drops, reverse=True))

            counterfactual = record["removed_491520_counterfactual"]
            cf_effective = min(491_520, record["pretruncation_expansion_count"])
            self.assertEqual(counterfactual["configured_K"], 491_520)
            self.assertEqual(counterfactual["effective_retained_count"], cf_effective)
            self.assertEqual(
                counterfactual["dropped_term_count"],
                record["pretruncation_expansion_count"] - cf_effective,
            )
            self.assertEqual(
                int(counterfactual["E_after_if_selected_ticks"]),
                cumulative + int(counterfactual["drop_ticks"]),
            )
            cf_feasible = (
                cumulative + int(counterfactual["drop_ticks"]) <= cap
            )
            self.assertIs(
                counterfactual["feasible_under_current_prefix_cap"], cf_feasible
            )

            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                self.assertTrue(feasible_indices)
                selected_index = feasible_indices[0]
                selected_row = rows[selected_index]
                self.assertEqual(record["selected_candidate_index"], selected_index)
                self.assertEqual(record["selected_K"], candidates[selected_index])
                self.assertEqual(
                    int(record["selected_drop_ticks"]), drops[selected_index]
                )
                self.assertEqual(
                    record["selected_effective_retained_count"],
                    selected_row["effective_retained_count"],
                )
                self.assertEqual(
                    record["selected_dropped_term_count"],
                    selected_row["dropped_term_count"],
                )
                self.assertEqual(
                    record["retained_expansion_count"],
                    selected_row["effective_retained_count"],
                )
                cumulative += drops[selected_index]
                self.assertEqual(int(record["E_after_ticks"]), cumulative)
                selected_history.append(candidates[selected_index])
                previous = record
            else:
                self.assertEqual(
                    record["status"],
                    "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                )
                self.assertFalse(feasible_indices)
                self.assertIsNone(record["selected_candidate_index"])
                self.assertIsNone(record["selected_K"])
                self.assertEqual(index, len(records) - 1)
                self.assertEqual(
                    record["required_K_excess_over_policy_maximum"],
                    max(
                        0,
                        record["minimum_effective_K_to_meet_prefix"]
                        - candidates[-1],
                    ),
                )
                self.assertEqual(
                    int(record["maximum_candidate_drop_excess_over_slack_ticks"]),
                    drops[-1] - slack,
                )
            self.assertEqual(
                counterfactual["actual_selected_K"], record["selected_K"]
            )

        self.assertEqual(selected_history, history)
        self.assertEqual(transcript["attempted_checkpoint_count"], len(records))
        self.assertEqual(transcript["completed_checkpoint_count"], len(history))
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"], str(cumulative)
        )
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            visits,
        )
        self.assertEqual(transcript["observed_peak_single_expansion_terms"], peak)
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            coefficient_bits,
        )
        self.assertEqual(transcript["observed_maximum_product_bits"], product_bits)
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            str(rounding),
        )
        self.assertEqual(transcript["root_globals_before"], transcript["root_globals_after"])
        self.assertTrue(transcript["root_globals_unchanged"])
        SCREEN.validate_replay_handoff(transcript, predecessor)

    def assert_canonical_when_available(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical D K573440/C33 q68 transcript not generated yet")
        raw = path.read_bytes()
        transcript = json.loads(raw)
        predecessor, predecessor_reference = SCREEN.load_route_predecessor_reference(
            HERE
        )
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            transcript["transcript_fingerprint"],
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q68_screen_v1",
        )
        self.assertEqual(
            transcript["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
        )
        self.assertEqual(transcript["screen_horizon_checkpoint_count"], 68)
        self.assertGreaterEqual(len(transcript["records"]), 67)
        self.assertLessEqual(len(transcript["records"]), 68)
        self.assertEqual(transcript["candidate_K_values"], list(SCREEN.D_CANDIDATES))
        self.assertEqual(
            transcript["candidate_K_values_sha256"],
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            transcript["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 33},
        )
        self.assertEqual(
            transcript["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )
        self.assertEqual(
            transcript["route_predecessor_reference"], predecessor_reference
        )
        paths = [
            item["relative_path"]
            for item in transcript["screen_execution_components"]
        ]
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        self.assertEqual(
            transcript["source_custody"][SCREEN.SELF_NAME], EXPECTED_SCREEN_SHA256
        )
        self.assertEqual(
            transcript["source_custody"][SCREEN.CONTROL_FLOW_PARENT_NAME],
            SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        )
        self.assertEqual(
            transcript["source_custody"][SCREEN.KERNEL_WRAPPER_NAME],
            EXPECTED_KERNEL_SHA256,
        )
        for field, value in (
            ("records_sha256", transcript["records"]),
            ("selected_K_history_sha256", transcript["selected_K_history"]),
            ("screen_execution_components_sha256", transcript["screen_execution_components"]),
            ("configuration_reference_sha256", transcript["configuration_reference"]),
            ("configuration_override_sha256", transcript["configuration_override"]),
            ("kernel_capability_override_sha256", transcript["kernel_capability_override"]),
            ("parent_horizon_override_sha256", transcript["parent_horizon_override"]),
            ("route_predecessor_reference_sha256", transcript["route_predecessor_reference"]),
            ("predecessor_handoff_validation_sha256", transcript["predecessor_handoff_validation"]),
            ("checkpoint_transform_sha256", transcript["checkpoint_transform"]),
        ):
            self.assertEqual(transcript[field], sha256(canonical_bytes(value)), field)
        frozen_hashes = {
            "records_sha256": "records_sha256",
            "selected_K_history_sha256": "history_sha256",
            "screen_execution_components_sha256": "components_sha256",
            "configuration_reference_sha256": "configuration_reference_sha256",
            "configuration_override_sha256": "configuration_override_sha256",
            "kernel_capability_override_sha256": "kernel_override_sha256",
            "parent_horizon_override_sha256": "horizon_override_sha256",
            "route_predecessor_reference_sha256": "route_reference_sha256",
            "predecessor_handoff_validation_sha256": "handoff_sha256",
            "checkpoint_transform_sha256": "transform_sha256",
        }
        for transcript_field, expected_field in frozen_hashes.items():
            self.assertEqual(
                transcript[transcript_field],
                EXPECTED_CANONICAL[expected_field],
                transcript_field,
            )
        self.assertIsNone(transcript["failure_record_sha256"])
        self.assertEqual(transcript["attempted_checkpoint_count"], 68)
        self.assertEqual(transcript["completed_checkpoint_count"], 68)
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
        expected_tail = {
            66: (679_285, 573_440, 105_845, "75084546988"),
            67: (688_548, 573_440, 115_108, "128389336170"),
            68: (630_616, 573_440, 57_176, "62098539389"),
        }
        for checkpoint, expected in expected_tail.items():
            record = transcript["records"][checkpoint - 1]
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint)
            self.assertEqual(
                (
                    record["pretruncation_expansion_count"],
                    record["selected_K"],
                    record["selected_dropped_term_count"],
                    record["selected_drop_ticks"],
                ),
                expected,
            )
            self.assertEqual(record["selected_candidate_index"], 32)
        if transcript["failure_checkpoint_included"]:
            self.assertEqual(
                transcript["failure_record_sha256"],
                sha256(canonical_bytes(transcript["records"][-1])),
            )
        else:
            self.assertIsNone(transcript["failure_record_sha256"])
        self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])
        self.assert_full_canonical_ledger(transcript, predecessor)

    def test_11_canonical_transcript_when_available(self):
        self.assert_canonical_when_available()

    @unittest.skipUnless(
        os.environ.get(
            "RUN_HUBBARD_L8_DOUBLE_OCCUPANCY_K573440_C33_Q68_REPLAY"
        ) == "1",
        "expensive deterministic D K573440/C33 q68 replay is opt-in",
    )
    def test_12_real_canonical_replay_is_opt_in(self):
        path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(path.exists(), "missing canonical D C33 q68 transcript")
        self.assertEqual(canonical_bytes(SCREEN.run(HERE)), path.read_bytes())


if __name__ == "__main__":
    unittest.main()
