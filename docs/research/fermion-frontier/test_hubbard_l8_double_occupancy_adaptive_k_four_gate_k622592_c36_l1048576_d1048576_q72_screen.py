#!/usr/bin/env python3
"""Static and synthetic tests for the D q72 two-cap policy route.

No test in this file performs the expensive four-gate replay.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "57a68b3086cd2ed2d484d0f835a190dc768b12bbb2b8d6a3c99c86f6ea6bda8d"
)
EXPECTED_SCREEN_SIZE_BYTES = 44_391
CANONICAL_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 739_189,
    "file_sha256": (
        "4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd"
    ),
    "records_sha256": (
        "21d7ff35dc1a6dc725eda9b16ecde3e64dd8b683c0a830fbc7e75e8d146733be"
    ),
    "history_sha256": (
        "18e76e6b8a2eb970bf5930c79901f97d24e9e5cfed865d5a8c8e27bee5bec807"
    ),
    "q72_failure_sha256": (
        "caeeb5a3854abdfb4fe2100ce0d5df20cc757dc6e153b5099efa8bd25ee648c7"
    ),
    "q72_rows_sha256": (
        "8ec5b4b4ab3bc981f81cefb8f8ba4e8b86394918242f21cddc18861db369ddd9"
    ),
    "q72_counterfactual_sha256": (
        "2fb269169a452f6290e19568f3ee647ed8f64698215c7e354f73e36c9c897b2c"
    ),
    "components_sha256": (
        "c944b2a5949a8277368fa77661c62d44a16633acc662fde360bbee001c148ca3"
    ),
    "source_custody_sha256": (
        "c979c5a4fa53d9ef4c55d21a7a75a522e1a8ac490083c38110a5c2893f17a76e"
    ),
    "configuration_reference_sha256": (
        "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1"
    ),
    "configuration_override_sha256": (
        "5ab17c2bb62a5b86ef55bbea54353d21b023f03497d590f73775e3edaddd522d"
    ),
    "kernel_override_sha256": (
        "3fb44fe999a8f5745b0eb8aa9a326d4bafda499ed9e576fe0a118571e998b3ea"
    ),
    "parent_horizon_override_sha256": (
        "927db7ca5d269edc666f97d7fca6a0bc3b02933c98a55e5a8994c9efbb49e589"
    ),
    "route_reference_sha256": (
        "038150c686da0a3eb2615ebcc02e44d0c2c1c7f6e0fabaa5d0fa62b8e5629dc0"
    ),
    "handoff_sha256": (
        "1a555b346b9b719cf206de929a155aa03694cce6b1dd36b295c8ae37c8ef020d"
    ),
    "transform_sha256": (
        "9a28d63449e1f870a1c0c4f1b9e6a78de5e7176c3cc99074aa42011787614ac2"
    ),
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("d_q72_policy_route_for_tests", SCREEN_NAME)


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class DQ72PolicyOnlyTests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.provider = SCREEN.load_code_provider(HERE)
        self.frozen, self.route_reference = (
            SCREEN.load_frozen_abort_evidence(HERE, self.provider)
        )

    @staticmethod
    def synthetic_sha(label):
        return hashlib.sha256(label.encode("ascii")).hexdigest()

    def make_raw_base(self):
        provider = self.provider
        raw = {
            key: copy.deepcopy(self.frozen[key])
            for key in provider.UPSTREAM_PARENT_RESULT_KEYS
        }
        raw["resource_policy_abort"] = None
        raw["resource_policy_abort_sha256"] = None
        raw.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_horizon_checkpoint_count": SCREEN.HORIZON,
            "candidate_K_values": list(provider.D_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": len(provider.D_CANDIDATES),
            },
            "kernel_capability_limits": SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
            "source_custody": copy.deepcopy(
                provider.EXPECTED_PARENT_SOURCE_CUSTODY
            ),
        })
        components = copy.deepcopy(
            list(provider.EXPECTED_PARENT_EXECUTION_COMPONENTS)
        )
        raw["screen_execution_components"] = components
        raw["screen_execution_components_sha256"] = digest(components)
        configuration = {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "source_sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            "role": "candidates_and_caps_reference_only",
            "fields_adopted": [
                f"MODE_CONFIG.{SCREEN.MODE}.candidates",
                "POLICY_CAPS_BASE",
            ],
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "policy_caps_base_sha256": provider.EXPECTED_V6_POLICY_CAPS_SHA256,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
        }
        raw["configuration_reference"] = configuration
        raw["configuration_reference_sha256"] = digest(configuration)
        transform = copy.deepcopy(
            self.frozen["checkpoint_transform"]
            ["physical_four_gate_control_flow_parent_transform"]
        )
        raw["checkpoint_transform"] = transform
        raw["checkpoint_transform_sha256"] = digest(transform)
        return raw

    def load_canonical(self):
        raw = (HERE / CANONICAL_NAME).read_bytes()
        canonical = json.loads(raw)
        self.assertIs(type(canonical), dict)
        self.assertEqual(raw, canonical_bytes(canonical))
        return raw, canonical

    def reverse_canonical_to_raw(self, canonical):
        """Remove only this screen's relabel fields from a final96 object."""

        provider = self.provider
        raw = {
            key: copy.deepcopy(canonical[key])
            for key in provider.UPSTREAM_PARENT_RESULT_KEYS
        }
        raw["resource_policy_abort"] = copy.deepcopy(
            canonical["resource_policy_abort"]
        )
        raw["resource_policy_abort_sha256"] = canonical[
            "resource_policy_abort_sha256"
        ]
        raw_authority = self.make_raw_base()
        for field in (
            "transcript_fingerprint",
            "screen_source_sha256",
            "control_flow_owned_by_screen",
            "screen_execution_components",
            "screen_execution_components_sha256",
            "configuration_reference",
            "configuration_reference_sha256",
            "checkpoint_transform",
            "checkpoint_transform_sha256",
            "source_custody",
        ):
            raw[field] = copy.deepcopy(raw_authority[field])
        self.assertEqual(
            frozenset(raw),
            frozenset(provider.EXPECTED_PARENT_RESULT_KEYS),
        )
        return raw

    def make_q72_record(self, success):
        provider = self.provider
        previous = self.frozen["records"][70]
        frozen_abort = self.frozen["resource_policy_abort"]
        record = copy.deepcopy(self.frozen["records"][69])
        prefix_cap = int(provider.EXPECTED_Q72_PREFIX_CAP_TICKS)
        E_before = int(previous["E_after_ticks"])
        slack = prefix_cap - E_before
        pre_count = frozen_abort["pretruncation_expansion_count"]
        record.update({
            "checkpoint_index_zero_based": 71,
            "checkpoint_number_one_based": 72,
            "stage_index": frozen_abort["stage_index"],
            "stage_group": frozen_abort["stage_group"],
            "batch_in_stage": frozen_abort["batch_in_stage"],
            "gate_occurrence_first_zero_based": 284,
            "gate_occurrence_last_zero_based": 287,
            "gate_batch_sha256": frozen_abort["gate_batch_sha256"],
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "pretruncation_expansion_count": pre_count,
            "pretruncation_expansion_sha256": self.synthetic_sha("q72-pre"),
            "ranked_suffix_sha256": self.synthetic_sha("q72-ranked"),
            "E_before_ticks": str(E_before),
            "budget_prefix_cap_ticks": str(prefix_cap),
            "prefix_slack_before_selection_ticks": str(slack),
            "peak_live_terms_this_checkpoint": frozen_abort[
                "peak_live_terms_this_checkpoint"
            ],
            "peak_live_terms_cumulative": frozen_abort[
                "peak_live_terms_cumulative"
            ],
            "term_gate_visits_increment": frozen_abort[
                "term_gate_visits_increment"
            ],
            "term_gate_visits_cumulative": frozen_abort[
                "term_gate_visits_cumulative"
            ],
            "rounding_increment_scaled_ticks_squared": frozen_abort[
                "rounding_increment_scaled_ticks_squared"
            ],
            "rounding_cumulative_scaled_ticks_squared": frozen_abort[
                "rounding_cumulative_scaled_ticks_squared"
            ],
            "maximum_expansion_coefficient_tick_bits": frozen_abort[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": frozen_abort["maximum_product_bits"],
        })
        rows = []
        for index, configured_K in enumerate(provider.D_CANDIDATES):
            effective = min(configured_K, pre_count)
            drop = (36 - index) if success else (slack + 36 - index)
            rows.append({
                "candidate_index": index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(E_before + drop),
                "feasible_under_current_prefix_cap": drop <= slack,
            })
        record["candidate_records"] = rows
        counterfactual_drop = int(rows[29]["drop_ticks"])
        counterfactual_feasible = counterfactual_drop <= slack
        record["removed_491520_counterfactual"] = {
            "configured_K": 491_520,
            "effective_retained_count": 491_520,
            "dropped_term_count": pre_count - 491_520,
            "drop_ticks": str(counterfactual_drop),
            "E_after_if_selected_ticks": str(E_before + counterfactual_drop),
            "feasible_under_current_prefix_cap": counterfactual_feasible,
            "actual_selected_K": provider.D_CANDIDATES[0] if success else None,
            "would_precede_selected": False,
            "would_be_selected_if_inserted": False,
        }
        if success:
            for key in provider.Q70_FAILURE_ONLY_KEYS:
                record.pop(key, None)
            selected = rows[0]
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 0,
                "selected_K": provider.D_CANDIDATES[0],
                "selected_effective_retained_count": selected[
                    "effective_retained_count"
                ],
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": self.synthetic_sha(
                    "q72-dropped"
                ),
                "retained_expansion_count": selected[
                    "effective_retained_count"
                ],
                "retained_expansion_sha256": self.synthetic_sha(
                    "q72-retained"
                ),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "1",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
        else:
            for key in provider.Q70_SUCCESS_ONLY_KEYS:
                record.pop(key, None)
            record.update({
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "selected_candidate_index": None,
                "selected_K": None,
                "minimum_effective_K_to_meet_prefix": SCREEN.K622592 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

    def make_normal_raw(self, success):
        raw = self.make_raw_base()
        q72 = self.make_q72_record(success)
        records = copy.deepcopy(self.frozen["records"]) + [q72]
        history = list(self.frozen["selected_K_history"])
        if success:
            history.append(q72["selected_K"])
        raw.update({
            "records": records,
            "records_sha256": digest(records),
            "selected_K_history": history,
            "selected_K_history_sha256": digest(history),
            "attempted_checkpoint_count": 72,
            "completed_checkpoint_count": 72 if success else 71,
            "screen_terminal_condition": (
                "DIAGNOSTIC_HORIZON_REACHED"
                if success
                else "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": success,
            "failure_checkpoint_included": not success,
            "failure_record_sha256": None if success else digest(q72),
            "last_committed_cumulative_drop_ticks": (
                q72["E_after_ticks"]
                if success
                else self.frozen["records"][70]["E_after_ticks"]
            ),
            "observed_peak_single_expansion_terms": q72[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": q72[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": q72[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": q72["maximum_product_bits"],
            "observed_rounding_cumulative_scaled_ticks_squared": q72[
                "rounding_cumulative_scaled_ticks_squared"
            ],
        })
        self.assertEqual(
            frozenset(raw),
            frozenset(self.provider.EXPECTED_PARENT_RESULT_KEYS),
        )
        return raw

    def make_resource_abort_raw(self, old_cap=False):
        raw = self.make_raw_base()
        q71 = self.frozen["records"][70]
        cap = 786_432 if old_cap else SCREEN.LIVE_AND_DIGEST_CAP
        pre_count = cap + 1
        visit_increment = 4 * q71["retained_expansion_count"]
        abort = {
            "schema_version": 1,
            "abort_id": "D_k622592_c36_q72_live_term_policy_abort_v1",
            "exception_type": "RuntimeError",
            "exception_message": "design policy live-term cap exceeded",
            "exception_args": ["design policy live-term cap exceeded"],
            "exception_chained_from_exact_parent_helper": True,
            "control_flow_parent_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256
            ),
            "helper_source_sha256": self.provider.EXPECTED_V2_HELPER_SHA256,
            "checkpoint_index_zero_based": 71,
            "checkpoint_number_one_based": 72,
            **self.provider.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[72],
            "gate_occurrence_first_zero_based": 284,
            "gate_occurrence_last_zero_based": 287,
            "input_expansion_count": q71["retained_expansion_count"],
            "input_expansion_sha256": q71["retained_expansion_sha256"],
            "pretruncation_expansion_count": pre_count,
            "max_single_expansion_terms": cap,
            "observed_excess_terms": 1,
            "policy_relation": (
                "pretruncation_expansion_count>max_single_expansion_terms"
            ),
            "attempted_gate_batch_propagated": True,
            "policy_cap_check_reached": True,
            "q72_pretruncation_digest_computed": False,
            "q72_ranking_performed": False,
            "q72_candidate_rows_constructed": False,
            "q72_selection_performed": False,
            "q72_commit_performed": False,
            "q72_checkpoint_record_constructed": False,
            "q72_partial_expansion_committed": False,
            "q71_committed_record_sha256": digest(q71),
            "peak_live_terms_this_checkpoint": pre_count,
            "peak_live_terms_cumulative": max(
                q71["peak_live_terms_cumulative"], pre_count
            ),
            "term_gate_visits_increment": visit_increment,
            "term_gate_visits_cumulative": (
                q71["term_gate_visits_cumulative"] + visit_increment
            ),
            "rounding_increment_scaled_ticks_squared": "1",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(q71["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
            "maximum_expansion_coefficient_tick_bits": q71[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": q71["maximum_product_bits"],
        }
        self.assertEqual(
            frozenset(abort),
            frozenset(self.provider.RESOURCE_POLICY_ABORT_KEYS),
        )
        records = copy.deepcopy(self.frozen["records"])
        history = list(self.frozen["selected_K_history"])
        raw.update({
            "resource_policy_abort": abort,
            "resource_policy_abort_sha256": digest(abort),
            "records": records,
            "records_sha256": digest(records),
            "selected_K_history": history,
            "selected_K_history_sha256": digest(history),
            "attempted_checkpoint_count": 72,
            "completed_checkpoint_count": 71,
            "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "last_committed_cumulative_drop_ticks": q71["E_after_ticks"],
            "observed_peak_single_expansion_terms": abort[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": abort[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": abort[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": abort["maximum_product_bits"],
            "observed_rounding_cumulative_scaled_ticks_squared": abort[
                "rounding_cumulative_scaled_ticks_squared"
            ],
        })
        return raw

    def replay_context(self):
        _wrapper, wrapper_sha, manifest = self.provider.load_kernel_wrapper(HERE)
        return {
            "baseline_d": tuple(self.provider.V6_D_CANDIDATES),
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": manifest,
            "raw_control_flow_horizon_override": copy.deepcopy(
                self.frozen["parent_horizon_override"]
            ),
        }

    def test_01_exact_two_cap_delta_and_all_other_limits_unchanged(self):
        screen_payload = (HERE / SCREEN_NAME).read_bytes()
        self.assertEqual(len(screen_payload), EXPECTED_SCREEN_SIZE_BYTES)
        self.assertLessEqual(len(screen_payload), SCREEN.MAX_SELF_SOURCE_BYTES)
        self.assertEqual(
            hashlib.sha256(screen_payload).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        fresh = SCREEN.fresh_self_module()
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, screen_payload)
        self.assertEqual(
            hashlib.sha256(fresh._VERIFIED_SELF_SOURCE_BYTES).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        self.assertIs(fresh._run_verified.__globals__, fresh.__dict__)
        self.assertEqual(fresh._run_verified.__code__.co_filename, fresh.__file__)
        SCREEN.validate_local_configuration()
        self.assertEqual(
            SCREEN.changed_keys(
                SCREEN.OLD_POLICY_CAPS_BASE,
                SCREEN.POLICY_CAPS_BASE,
            ),
            SCREEN.POLICY_CHANGED_FIELDS,
        )
        unchanged = set(SCREEN.OLD_POLICY_CAPS_BASE) - SCREEN.POLICY_CHANGED_FIELDS
        for field in unchanged:
            self.assertEqual(
                SCREEN.POLICY_CAPS_BASE[field],
                SCREEN.OLD_POLICY_CAPS_BASE[field],
            )
        self.assertEqual(
            digest(SCREEN.POLICY_CAPS_BASE),
            SCREEN.EXPECTED_POLICY_CAPS_SHA256,
        )
        self.assertEqual(
            digest({**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 36}),
            SCREEN.EXPECTED_TRANSCRIPT_POLICY_CAPS_SHA256,
        )
        self.assertEqual(
            self.provider.EXPECTED_KERNEL_WRAPPER_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        )
        self.assertEqual(self.provider.EXTENDED_HORIZON, 72)
        self.assertEqual(len(self.provider.D_CANDIDATES), 36)

    def test_02_code_provider_is_exact_and_private_entrypoint_is_not_called(self):
        source = (HERE / SCREEN_NAME).read_text(encoding="utf-8")
        tree = ast.parse(source)
        execute = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "execute_fresh_replay"
        )
        calls = [
            ast.unparse(node.func)
            for node in ast.walk(execute)
            if isinstance(node, ast.Call)
        ]
        self.assertNotIn("provider._run_verified", calls)
        self.assertNotIn("provider.validate_and_relabel", calls)
        for expected in (
            "provider.load_control_flow_parent",
            "provider.load_configured_v6_baseline",
            "provider.load_kernel_wrapper",
            "provider.configure_parent_execution",
            "provider.execute_parent_with_structured_abort",
        ):
            self.assertIn(expected, calls)
        assignments = [
            ast.unparse(target)
            for node in ast.walk(execute)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
        ]
        provider_assignments = [
            value for value in assignments if value.startswith("provider.")
        ]
        self.assertEqual(
            provider_assignments,
            ["provider.POLICY_CAPS_BASE", "provider.POLICY_CAPS_BASE"],
        )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN.CODE_PROVIDER_NAME).read_bytes()).hexdigest(),
            SCREEN.EXPECTED_CODE_PROVIDER_SHA256,
        )

    def test_03_manual_adapter_changes_only_caps_and_restores_provider(self):
        provider = types.ModuleType("synthetic_provider")
        provider.POLICY_CAPS_BASE = copy.deepcopy(SCREEN.OLD_POLICY_CAPS_BASE)
        provider.D_CANDIDATES = tuple(self.provider.D_CANDIDATES)
        observed = []

        def validate():
            observed.append(("validate", copy.deepcopy(provider.POLICY_CAPS_BASE)))

        def load_parent(_repo):
            observed.append(("load_parent", copy.deepcopy(provider.POLICY_CAPS_BASE)))
            return object()

        configuration = types.SimpleNamespace(
            POLICY_CAPS_BASE=copy.deepcopy(SCREEN.POLICY_CAPS_BASE),
            MODE_CONFIG={
                SCREEN.MODE: {"candidates": tuple(provider.D_CANDIDATES)}
            },
        )

        def load_configuration(_repo):
            observed.append(("load_configuration", copy.deepcopy(provider.POLICY_CAPS_BASE)))
            return configuration, tuple(self.provider.V6_D_CANDIDATES)

        manifest = {"synthetic": True}
        wrapper = object()
        provider.validate_local_configuration = validate
        provider.load_control_flow_parent = load_parent
        provider.load_configured_v6_baseline = load_configuration
        provider.load_kernel_wrapper = lambda _repo: (
            wrapper,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            manifest,
        )
        provider.configure_parent_execution = lambda *_args: {"horizon": 72}
        provider.execute_parent_with_structured_abort = lambda *_args: {"raw": True}
        result, context = SCREEN.execute_fresh_replay(provider, HERE)
        self.assertEqual(result, {"raw": True})
        self.assertEqual(provider.POLICY_CAPS_BASE, SCREEN.OLD_POLICY_CAPS_BASE)
        for label, caps in observed[1:]:
            self.assertEqual(caps, SCREEN.POLICY_CAPS_BASE, label)
        self.assertFalse(context["code_provider_private_entrypoint_called"])
        self.assertFalse(context["code_provider_relabeller_called"])
        self.assertFalse(context["frozen_abort_loaded_before_replay"])
        self.assertEqual(
            context["changed_policy_fields"],
            sorted(SCREEN.POLICY_CHANGED_FIELDS),
        )

    def test_04_frozen_abort_is_closed_post_replay_evidence_only(self):
        frozen_reference = self.route_reference["frozen_abort_transcript"]
        self.assertFalse(frozen_reference["loaded_before_replay"])
        self.assertTrue(
            frozen_reference["loaded_after_fresh_replay_as_exact_evidence"]
        )
        for field in (
            "propagation_input",
            "checkpoint_71_state_loaded",
            "checkpoint_72_state_loaded",
            "state_resume_input",
            "execution_source_layer",
            "source_custody_layer",
        ):
            self.assertFalse(frozen_reference[field])
        abort = self.frozen["resource_policy_abort"]
        self.assertEqual(abort["max_single_expansion_terms"], 786_432)
        self.assertEqual(abort["pretruncation_expansion_count"], 799_279)
        self.assertLess(
            abort["pretruncation_expansion_count"],
            SCREEN.LIVE_AND_DIGEST_CAP,
        )
        secondary = self.route_reference[
            "secondary_provider_route_validation_reference"
        ]
        self.assertFalse(secondary["loaded_before_replay"])
        self.assertTrue(
            secondary[
                "loaded_after_fresh_replay_inside_validate_raw_replay"
            ]
        )
        for field in (
            "propagation_input",
            "state_resume_input",
            "execution_source_layer",
            "source_custody_layer",
        ):
            self.assertFalse(secondary[field])

    def test_05_q72_success_and_failure_are_closed_with_exact_propagation(self):
        for success, expected in (
            (True, "Q72_SUCCESS_HORIZON_REACHED"),
            (False, "Q72_POLICY_FAILURE"),
        ):
            with self.subTest(success=success):
                raw = self.make_normal_raw(success)
                handoff = SCREEN.validate_raw_replay(
                    raw,
                    self.provider,
                    HERE,
                    self.frozen,
                )
                self.assertEqual(handoff["terminal_branch"], expected)
                self.assertTrue(
                    handoff[
                        "q72_propagation_matches_post_replay_frozen_evidence"
                    ]
                )
                self.assertIsNone(raw["resource_policy_abort"])
                self.assertIsNone(raw["resource_policy_abort_sha256"])

    def test_06_every_resource_exception_fails_closed_without_artifact(self):
        new_cap_object = self.make_resource_abort_raw()
        with self.assertRaisesRegex(RuntimeError, "fail closed without artifact"):
            SCREEN.validate_raw_replay(
                new_cap_object,
                self.provider,
                HERE,
                self.frozen,
            )
        old = self.make_resource_abort_raw(old_cap=True)
        with self.assertRaisesRegex(RuntimeError, "old 786432"):
            SCREEN.validate_raw_replay(
                old,
                self.provider,
                HERE,
                self.frozen,
            )

        class SyntheticKernelSchemaError(ValueError):
            pass

        provider = types.ModuleType("synthetic_resource_provider")
        provider.POLICY_CAPS_BASE = copy.deepcopy(SCREEN.OLD_POLICY_CAPS_BASE)
        provider.D_CANDIDATES = tuple(self.provider.D_CANDIDATES)
        provider.validate_local_configuration = lambda: None
        provider.load_control_flow_parent = lambda _repo: object()
        configuration = types.SimpleNamespace(
            POLICY_CAPS_BASE=copy.deepcopy(SCREEN.POLICY_CAPS_BASE),
            MODE_CONFIG={
                SCREEN.MODE: {"candidates": tuple(provider.D_CANDIDATES)}
            },
        )
        provider.load_configured_v6_baseline = lambda _repo: (
            configuration,
            tuple(self.provider.V6_D_CANDIDATES),
        )
        provider.load_kernel_wrapper = lambda _repo: (
            object(),
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            {"synthetic": True},
        )
        provider.configure_parent_execution = lambda *_args: {"horizon": 72}

        def raise_kernel_resource(*_args):
            raise SyntheticKernelSchemaError(
                "v2 suffix accumulator bit cap exceeded"
            )

        provider.execute_parent_with_structured_abort = raise_kernel_resource
        with self.assertRaisesRegex(
            SyntheticKernelSchemaError,
            "suffix accumulator",
        ):
            SCREEN.execute_fresh_replay(provider, HERE)
        self.assertEqual(provider.POLICY_CAPS_BASE, SCREEN.OLD_POLICY_CAPS_BASE)
        self.assertEqual(
            self.route_reference["terminal_contract"]["artifact_branches"],
            ["Q72_POLICY_FAILURE", "Q72_SUCCESS_HORIZON_REACHED"],
        )
        self.assertTrue(
            self.route_reference["terminal_contract"]
            ["resource_policy_abort_pair_null_on_every_artifact"]
        )

    def test_07_q1_q71_or_q72_propagation_tampering_is_rejected(self):
        raw = self.make_normal_raw(True)
        raw["records"][70]["E_after_ticks"] = str(
            int(raw["records"][70]["E_after_ticks"]) + 1
        )
        raw["records_sha256"] = digest(raw["records"])
        with self.assertRaisesRegex(RuntimeError, "q1-q71"):
            SCREEN.validate_raw_replay(
                raw,
                self.provider,
                HERE,
                self.frozen,
            )
        raw = self.make_normal_raw(False)
        raw["records"][71]["pretruncation_expansion_count"] += 1
        raw["records_sha256"] = digest(raw["records"])
        with self.assertRaises(RuntimeError):
            SCREEN.validate_raw_replay(
                raw,
                self.provider,
                HERE,
                self.frozen,
            )

    def test_08_synthetic_relabel_has_uniform_96_key_authority(self):
        raw = self.make_normal_raw(True)
        old_verified = SCREEN._VERIFIED_SELF_SOURCE_BYTES
        try:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = (HERE / SCREEN_NAME).read_bytes()
            final = SCREEN.validate_and_relabel(
                raw,
                self.provider,
                HERE,
                self.frozen,
                self.route_reference,
                self.replay_context(),
            )
        finally:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = old_verified
        self.assertEqual(
            frozenset(final),
            frozenset(self.provider.EXPECTED_RELABELLED_RESULT_KEYS),
        )
        self.assertEqual(len(final), 96)
        self.assertEqual(len(final["screen_execution_components"]), 12)
        self.assertEqual(len(final["source_custody"]), 11)
        component_paths = {
            item["relative_path"] for item in final["screen_execution_components"]
        }
        self.assertIn(SCREEN.SELF_NAME, component_paths)
        self.assertIn(SCREEN.CODE_PROVIDER_NAME, component_paths)
        self.assertNotIn(SCREEN.FROZEN_ABORT_TRANSCRIPT_NAME, component_paths)
        self.assertNotIn(
            SCREEN.FROZEN_ABORT_TRANSCRIPT_NAME,
            final["source_custody"],
        )
        incremental = final["configuration_override"][
            "incremental_route_from_frozen_k622592_c36_q72"
        ]
        self.assertEqual(
            incremental["changed_fields"],
            [
                "POLICY_CAPS_BASE.max_digest_terms",
                "POLICY_CAPS_BASE.max_single_expansion_terms",
            ],
        )
        self.assertTrue(
            final["configuration_override"][
                "direct_v6_delta_includes_inherited_candidate_K_and_horizon_overrides"
            ]
        )

    def test_09_run_order_is_replay_then_frozen_evidence(self):
        events = []
        saved = {
            name: getattr(SCREEN, name)
            for name in (
                "validate_local_configuration",
                "load_code_provider",
                "execute_fresh_replay",
                "load_frozen_abort_evidence",
                "validate_and_relabel",
                "_VERIFIED_SELF_SOURCE_BYTES",
            )
        }
        provider = object()
        try:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = b"synthetic-self"
            SCREEN.validate_local_configuration = lambda: events.append("config")
            SCREEN.load_code_provider = lambda _repo: (
                events.append("provider") or provider
            )
            SCREEN.execute_fresh_replay = lambda *_args: (
                events.append("replay") or ({"raw": True}, {"context": True})
            )

            def evidence(*_args):
                self.assertIn("replay", events)
                events.append("frozen_evidence")
                return {"frozen": True}, {"reference": True}

            SCREEN.load_frozen_abort_evidence = evidence
            SCREEN.validate_and_relabel = lambda *_args: (
                events.append("relabel") or {"done": True}
            )
            self.assertEqual(SCREEN._run_verified(HERE), {"done": True})
        finally:
            for name, value in saved.items():
                setattr(SCREEN, name, value)
        self.assertEqual(
            events,
            ["config", "provider", "replay", "frozen_evidence", "relabel"],
        )

    def test_10_no_replay_test_contract_and_atomic_output(self):
        source = pathlib.Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        ]
        self.assertIn("SCREEN.run", calls)
        run_call_owners = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            function_calls = {
                ast.unparse(item.func)
                for item in ast.walk(node)
                if isinstance(item, ast.Call)
            }
            if "SCREEN.run" in function_calls:
                run_call_owners.append(node.name)
        self.assertEqual(
            run_call_owners,
            ["test_13_full_replay_opt_in_matches_canonical_exact_bytes"],
        )
        payload = canonical_bytes({"policy": "synthetic"})
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "out.json"
            SCREEN.write_atomic_bounded(output, payload)
            self.assertEqual(output.read_bytes(), payload)

    def test_11_canonical_is_exhaustively_closed_without_replay(self):
        raw, canonical = self.load_canonical()
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            EXPECTED_CANONICAL["file_sha256"],
        )
        self.assertEqual(
            frozenset(canonical),
            frozenset(self.provider.EXPECTED_RELABELLED_RESULT_KEYS),
        )
        self.assertEqual(len(canonical), 96)

        expected_top = {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
                "k622592_c36_l1048576_d1048576_q72_screen_v1"
            ),
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "screen_horizon_checkpoint_count": 72,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "attempted_checkpoint_count": 72,
            "completed_checkpoint_count": 71,
            "failure_checkpoint_included": True,
            "failure_record_sha256": EXPECTED_CANONICAL[
                "q72_failure_sha256"
            ],
            "last_committed_cumulative_drop_ticks": "2288967389826722",
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
        }
        for field, value in expected_top.items():
            self.assertEqual(canonical[field], value, field)
        self.assertEqual(
            canonical["candidate_K_values"],
            list(self.provider.D_CANDIDATES),
        )
        self.assertEqual(
            canonical["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 36},
        )
        self.assertEqual(
            digest(canonical["proposed_policy_caps"]),
            SCREEN.EXPECTED_TRANSCRIPT_POLICY_CAPS_SHA256,
        )
        self.assertEqual(
            canonical["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

        nested = {
            "candidate_K_values": (
                "candidate_K_values_sha256",
                SCREEN.EXPECTED_CANDIDATE_SHA256,
            ),
            "records": (
                "records_sha256",
                EXPECTED_CANONICAL["records_sha256"],
            ),
            "selected_K_history": (
                "selected_K_history_sha256",
                EXPECTED_CANONICAL["history_sha256"],
            ),
            "screen_execution_components": (
                "screen_execution_components_sha256",
                EXPECTED_CANONICAL["components_sha256"],
            ),
            "configuration_reference": (
                "configuration_reference_sha256",
                EXPECTED_CANONICAL["configuration_reference_sha256"],
            ),
            "configuration_override": (
                "configuration_override_sha256",
                EXPECTED_CANONICAL["configuration_override_sha256"],
            ),
            "kernel_capability_override": (
                "kernel_capability_override_sha256",
                EXPECTED_CANONICAL["kernel_override_sha256"],
            ),
            "parent_horizon_override": (
                "parent_horizon_override_sha256",
                EXPECTED_CANONICAL["parent_horizon_override_sha256"],
            ),
            "route_predecessor_reference": (
                "route_predecessor_reference_sha256",
                EXPECTED_CANONICAL["route_reference_sha256"],
            ),
            "predecessor_handoff_validation": (
                "predecessor_handoff_validation_sha256",
                EXPECTED_CANONICAL["handoff_sha256"],
            ),
            "checkpoint_transform": (
                "checkpoint_transform_sha256",
                EXPECTED_CANONICAL["transform_sha256"],
            ),
        }
        for value_field, (digest_field, expected_digest) in nested.items():
            with self.subTest(nested=value_field):
                self.assertEqual(canonical[digest_field], expected_digest)
                self.assertEqual(digest(canonical[value_field]), expected_digest)

        records = canonical["records"]
        history = canonical["selected_K_history"]
        self.assertEqual(len(records), 72)
        self.assertEqual(len(history), 71)
        self.assertEqual(records[:71], self.frozen["records"])
        self.assertEqual(history, self.frozen["selected_K_history"])
        self.assertEqual(
            digest(records[:71]),
            SCREEN.EXPECTED_FROZEN_RECORDS_SHA256,
        )
        self.assertEqual(
            digest(history),
            SCREEN.EXPECTED_FROZEN_HISTORY_SHA256,
        )

        q71 = records[70]
        q72 = records[71]
        self.assertEqual(
            frozenset(q72),
            frozenset(self.provider.Q70_FAILURE_RECORD_KEYS),
        )
        self.assertEqual(digest(q72), EXPECTED_CANONICAL["q72_failure_sha256"])
        q72_expected = {
            "checkpoint_index_zero_based": 71,
            "checkpoint_number_one_based": 72,
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 15,
            "gate_occurrence_first_zero_based": 284,
            "gate_occurrence_last_zero_based": 287,
            "gate_batch_sha256": (
                "18438c6e92238d37c833e1df5a341bbc17ec0a129a735e11719a586b2b74a4a3"
            ),
            "input_expansion_count": 622_592,
            "input_expansion_sha256": (
                "50969113d522dadfedced0960548674551acd1ddf56024bb673ce4ee1272b0f4"
            ),
            "E_before_ticks": "2288967389826722",
            "budget_prefix_cap_ticks": "2289089997813814",
            "prefix_slack_before_selection_ticks": "122607987092",
            "pretruncation_expansion_count": 799_279,
            "pretruncation_expansion_sha256": (
                "c9a791a2fd9eb9caf971b87917973afe300d1839b0a2bb0b01e315f8b6d06f96"
            ),
            "ranked_suffix_sha256": (
                "9e9bbc7b188fe28962229358a07b68c5e38c0f9f15921e3505f4e3a27a1fe7a4"
            ),
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "selected_candidate_index": None,
            "selected_K": None,
            "minimum_effective_K_to_meet_prefix": 642_206,
            "required_K_excess_over_policy_maximum": 19_614,
            "maximum_candidate_drop_excess_over_slack_ticks": "111121545012",
            "peak_live_terms_this_checkpoint": 799_279,
            "peak_live_terms_cumulative": 799_279,
            "term_gate_visits_increment": 2_727_652,
            "term_gate_visits_cumulative": 92_869_433,
            "rounding_increment_scaled_ticks_squared": (
                "6664243193452502336570705"
            ),
            "rounding_cumulative_scaled_ticks_squared": (
                "130329045223088501476863488"
            ),
            "maximum_expansion_coefficient_tick_bits": 63,
            "maximum_product_bits": 120,
        }
        for field, value in q72_expected.items():
            self.assertEqual(q72[field], value, field)
        self.assertEqual(q72["input_expansion_count"], q71["retained_expansion_count"])
        self.assertEqual(q72["input_expansion_sha256"], q71["retained_expansion_sha256"])
        self.assertEqual(q72["E_before_ticks"], q71["E_after_ticks"])
        self.assertEqual(
            int(q72["prefix_slack_before_selection_ticks"]),
            int(q72["budget_prefix_cap_ticks"]) - int(q72["E_before_ticks"]),
        )
        self.assertEqual(
            q72["peak_live_terms_cumulative"],
            max(q71["peak_live_terms_cumulative"], q72["peak_live_terms_this_checkpoint"]),
        )
        self.assertEqual(
            q72["term_gate_visits_cumulative"],
            q71["term_gate_visits_cumulative"] + q72["term_gate_visits_increment"],
        )
        self.assertEqual(
            int(q72["rounding_cumulative_scaled_ticks_squared"]),
            int(q71["rounding_cumulative_scaled_ticks_squared"])
            + int(q72["rounding_increment_scaled_ticks_squared"]),
        )

        rows = q72["candidate_records"]
        self.assertEqual(len(rows), 36)
        self.assertEqual(digest(rows), EXPECTED_CANONICAL["q72_rows_sha256"])
        drops = []
        for index, (configured_K, row) in enumerate(
            zip(self.provider.D_CANDIDATES, rows)
        ):
            with self.subTest(candidate=index):
                self.assertEqual(
                    frozenset(row),
                    frozenset(self.provider.CANDIDATE_RECORD_KEYS),
                )
                effective = min(configured_K, q72["pretruncation_expansion_count"])
                self.assertEqual(row["candidate_index"], index)
                self.assertEqual(row["configured_K"], configured_K)
                self.assertEqual(row["effective_retained_count"], effective)
                self.assertEqual(
                    row["dropped_term_count"],
                    q72["pretruncation_expansion_count"] - effective,
                )
                drop = int(row["drop_ticks"])
                drops.append(drop)
                self.assertEqual(
                    int(row["E_after_if_selected_ticks"]),
                    int(q72["E_before_ticks"]) + drop,
                )
                self.assertFalse(row["feasible_under_current_prefix_cap"])
                self.assertGreater(
                    int(row["E_after_if_selected_ticks"]),
                    int(q72["budget_prefix_cap_ticks"]),
                )
        self.assertEqual(drops, sorted(drops, reverse=True))
        self.assertEqual(
            q72["required_K_excess_over_policy_maximum"],
            q72["minimum_effective_K_to_meet_prefix"] - SCREEN.K622592,
        )
        self.assertLessEqual(
            q72["minimum_effective_K_to_meet_prefix"],
            q72["pretruncation_expansion_count"],
        )
        self.assertEqual(
            int(q72["maximum_candidate_drop_excess_over_slack_ticks"]),
            drops[-1] - int(q72["prefix_slack_before_selection_ticks"]),
        )

        counterfactual = q72["removed_491520_counterfactual"]
        self.assertEqual(
            frozenset(counterfactual),
            frozenset(self.provider.REMOVED_COUNTERFACTUAL_KEYS),
        )
        self.assertEqual(
            digest(counterfactual),
            EXPECTED_CANONICAL["q72_counterfactual_sha256"],
        )
        self.assertEqual(counterfactual["configured_K"], 491_520)
        self.assertEqual(counterfactual["effective_retained_count"], 491_520)
        self.assertEqual(counterfactual["dropped_term_count"], 307_759)
        self.assertFalse(counterfactual["feasible_under_current_prefix_cap"])
        self.assertIsNone(counterfactual["actual_selected_K"])
        self.assertFalse(counterfactual["would_precede_selected"])
        self.assertFalse(counterfactual["would_be_selected_if_inserted"])
        counterfactual_drop = int(counterfactual["drop_ticks"])
        self.assertGreaterEqual(int(rows[28]["drop_ticks"]), counterfactual_drop)
        self.assertGreaterEqual(counterfactual_drop, int(rows[29]["drop_ticks"]))

        resource_ledger = {
            "observed_peak_single_expansion_terms": q72[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": q72[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": q72[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": q72["maximum_product_bits"],
            "observed_rounding_cumulative_scaled_ticks_squared": q72[
                "rounding_cumulative_scaled_ticks_squared"
            ],
        }
        for field, value in resource_ledger.items():
            self.assertEqual(canonical[field], value, field)

        expected_components = SCREEN.execution_components(
            self.provider,
            list(self.provider.EXPECTED_PARENT_EXECUTION_COMPONENTS),
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(canonical["screen_execution_components"], expected_components)
        self.assertEqual(len(expected_components), 12)
        self.assertNotIn(
            SCREEN.FROZEN_ABORT_TRANSCRIPT_NAME,
            {item["relative_path"] for item in expected_components},
        )
        expected_custody = SCREEN.expected_final_source_custody(
            self.provider,
            self.provider.EXPECTED_PARENT_SOURCE_CUSTODY,
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(canonical["source_custody"], expected_custody)
        self.assertEqual(len(expected_custody), 11)
        self.assertEqual(
            digest(expected_custody),
            EXPECTED_CANONICAL["source_custody_sha256"],
        )
        self.assertNotIn(SCREEN.FROZEN_ABORT_TRANSCRIPT_NAME, expected_custody)
        for component in expected_components:
            path = HERE / component["relative_path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                component["sha256"],
                component["relative_path"],
            )

        self.assertEqual(canonical["root_globals_before"], canonical["root_globals_after"])
        self.assertTrue(canonical["root_globals_unchanged"])
        config = canonical["configuration_override"]
        self.assertEqual(
            config["incremental_route_from_frozen_k622592_c36_q72"]
            ["changed_fields"],
            [
                "POLICY_CAPS_BASE.max_digest_terms",
                "POLICY_CAPS_BASE.max_single_expansion_terms",
            ],
        )
        handoff = canonical["predecessor_handoff_validation"]
        self.assertEqual(handoff["terminal_branch"], "Q72_POLICY_FAILURE")
        self.assertTrue(
            handoff["q72_propagation_matches_post_replay_frozen_evidence"]
        )
        self.assertEqual(
            canonical["route_predecessor_reference"]["terminal_contract"]
            ["artifact_branches"],
            ["Q72_POLICY_FAILURE", "Q72_SUCCESS_HORIZON_REACHED"],
        )

    def test_12_canonical_reverses_to_raw67_and_relabels_to_exact_final96(self):
        expected_raw, canonical = self.load_canonical()
        raw = self.reverse_canonical_to_raw(canonical)
        handoff = SCREEN.validate_raw_replay(
            copy.deepcopy(raw),
            self.provider,
            HERE,
            self.frozen,
        )
        self.assertEqual(handoff["terminal_branch"], "Q72_POLICY_FAILURE")
        old_verified = SCREEN._VERIFIED_SELF_SOURCE_BYTES
        try:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = (HERE / SCREEN_NAME).read_bytes()
            relabelled = SCREEN.validate_and_relabel(
                raw,
                self.provider,
                HERE,
                self.frozen,
                self.route_reference,
                self.replay_context(),
            )
        finally:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = old_verified
        self.assertEqual(relabelled, canonical)
        self.assertEqual(canonical_bytes(relabelled), expected_raw)
        self.assertEqual(
            hashlib.sha256(canonical_bytes(relabelled)).hexdigest(),
            EXPECTED_CANONICAL["file_sha256"],
        )

    @unittest.skipUnless(
        os.environ.get("HUBBARD_L8_RUN_D_POLICY_Q72_REPLAY") == "1",
        "set HUBBARD_L8_RUN_D_POLICY_Q72_REPLAY=1 for the expensive replay",
    )
    def test_13_full_replay_opt_in_matches_canonical_exact_bytes(self):
        expected = (HERE / CANONICAL_NAME).read_bytes()
        observed = canonical_bytes(SCREEN.run(HERE))
        self.assertEqual(observed, expected)
        self.assertEqual(len(observed), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(
            hashlib.sha256(observed).hexdigest(),
            EXPECTED_CANONICAL["file_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
