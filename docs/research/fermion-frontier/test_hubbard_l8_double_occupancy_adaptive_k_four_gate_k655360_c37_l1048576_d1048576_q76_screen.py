#!/usr/bin/env python3
"""Static and synthetic tests for the same-cap D K655360/C37 q76 route."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import os
import tempfile
import textwrap
import types
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q76_screen.py"
)
EXPECTED_SCREEN_SIZE = 58_178
EXPECTED_SCREEN_SHA256 = (
    "621f9c97b72c3582314d360b9b29b46a9cb40bf60298776adfc52849300bd14e"
)
CANONICAL_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q76_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 798_861,
    "file_sha256": (
        "856ede1f5774795c25ca2c36eafa8ac0696402194c6bf4e17ea5e8874efc22e0"
    ),
    "records_sha256": (
        "5ba16ae933ae9a17633a1c3c4d7edba28b2c115bef475480272fa2cf9df39274"
    ),
    "history_sha256": (
        "b72e24b2dbe1d8eff88ff9ad1e1bc47cebeb59807168603cd86ff91c218c604a"
    ),
    "q75_record_sha256": (
        "34d47968dc15b92bcd0ac8c13325f0630f73763fb85c470315507f1d2ce3fa26"
    ),
    "q75_rows_sha256": (
        "2e23c61e3f62bf9abfd28bae3a60fea62f47d6614320ba4f9f3df066597ab1af"
    ),
    "q76_record_sha256": (
        "4369195a70e029f2dd81d6f276856cc6a06e1624de6240892a9022eaff4887f4"
    ),
    "q76_rows_sha256": (
        "df34276e849152f9b91a18130b01acb842093736c36e4bb41d297aa8ca11e0bf"
    ),
    "handoff_sha256": (
        "65a8c72561385fcb8078f628638ab068c33426d9e26039db19aa54ec12e0af0e"
    ),
    "components_sha256": (
        "23b6132f3ac8beabfa62c33c37651736a6483407e67e582861b24ab7d1c5256a"
    ),
    "custody_sha256": (
        "4a1d9c85bb83e6c8e9e22139536e39d61cc5d2afa6968d338fe6172d0d6b51ae"
    ),
}
SCREEN_PATH = HERE / SCREEN_NAME
SCREEN_RAW = SCREEN_PATH.read_bytes()
SCREEN = types.ModuleType("tested_d_k655360_c37_q76_screen")
SCREEN.__file__ = str(SCREEN_PATH)
SCREEN.__package__ = ""
SCREEN.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = SCREEN_RAW
exec(compile(SCREEN_RAW, str(SCREEN_PATH), "exec"), SCREEN.__dict__)


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def digest(value):
    payload = value if type(value) is bytes else canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def marker(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


class DQ76ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = SCREEN.load_execution_parent(HERE)
        cls.predecessor, cls.route_reference = SCREEN.load_route_reference(
            HERE,
            cls.parent,
        )
        cls.canonical_raw = (HERE / CANONICAL_NAME).read_bytes()
        cls.canonical = json.loads(cls.canonical_raw)

    def make_record(self, previous, checkpoint, success):
        pre_count = 700_000
        E_before = int(previous["E_after_ticks"])
        prefix_cap = int(
            SCREEN.EXPECTED_Q75_PREFIX_CAP_TICKS
            if checkpoint == 75
            else SCREEN.EXPECTED_Q76_PREFIX_CAP_TICKS
        )
        slack = prefix_cap - E_before
        rows = []
        for index, configured_K in enumerate(self.parent.D_CANDIDATES):
            effective = min(configured_K, pre_count)
            drop = (
                (len(self.parent.D_CANDIDATES) - index) * 100
                if success
                else slack + (len(self.parent.D_CANDIDATES) - index) * 100
            )
            rows.append({
                "candidate_index": index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(E_before + drop),
                "feasible_under_current_prefix_cap": success,
            })
        selected_index = 0 if success else None
        selected_K = (
            self.parent.D_CANDIDATES[selected_index]
            if selected_index is not None
            else None
        )
        counterfactual_drop = 50 if success else slack + 50
        anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
        common = {
            "E_before_ticks": str(E_before),
            "batch_in_stage": anchor["batch_in_stage"],
            "budget_prefix_cap_ticks": str(prefix_cap),
            "candidate_records": rows,
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            "gate_batch_sha256": anchor["gate_batch_sha256"],
            "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
            "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "maximum_expansion_coefficient_tick_bits": previous[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": previous["maximum_product_bits"],
            "peak_live_terms_cumulative": max(
                previous["peak_live_terms_cumulative"], pre_count
            ),
            "peak_live_terms_this_checkpoint": pre_count,
            "prefix_slack_before_selection_ticks": str(slack),
            "pretruncation_expansion_count": pre_count,
            "pretruncation_expansion_sha256": marker(
                f"pre-{checkpoint}-{success}"
            ),
            "ranked_suffix_sha256": marker(f"rank-{checkpoint}-{success}"),
            "removed_491520_counterfactual": {
                "configured_K": 491_520,
                "effective_retained_count": 491_520,
                "dropped_term_count": pre_count - 491_520,
                "drop_ticks": str(counterfactual_drop),
                "E_after_if_selected_ticks": str(
                    E_before + counterfactual_drop
                ),
                "feasible_under_current_prefix_cap": success,
                "actual_selected_K": selected_K,
                "would_precede_selected": False,
                "would_be_selected_if_inserted": False,
            },
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
            "rounding_increment_scaled_ticks_squared": "1",
            "selected_K": selected_K,
            "selected_candidate_index": selected_index,
            "stage_group": anchor["stage_group"],
            "stage_index": anchor["stage_index"],
            "status": (
                "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
                if success
                else "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"]
                + previous["retained_expansion_count"]
            ),
            "term_gate_visits_increment": previous[
                "retained_expansion_count"
            ],
        }
        if success:
            selected = rows[0]
            common.update({
                "selected_effective_retained_count": selected[
                    "effective_retained_count"
                ],
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": marker(
                    f"dropped-{checkpoint}"
                ),
                "retained_expansion_count": selected[
                    "effective_retained_count"
                ],
                "retained_expansion_sha256": marker(f"retained-{checkpoint}"),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "0",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
        else:
            common.update({
                "minimum_effective_K_to_meet_prefix": SCREEN.K655360 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "100",
            })
        return common

    def make_abort(self, previous, checkpoint, kind):
        policy_cap = self.parent.POLICY_CAPS_BASE[
            "max_single_expansion_terms"
        ]
        kernel_cap = self.parent.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS[
            "max_single_expansion_terms"
        ]
        observed = policy_cap + 1
        specs = {
            "final_live_terms": {
                "exception_type": "RuntimeError",
                "exception_message": "design policy live-term cap exceeded",
                "exception_source_role": "exact_parent_helper",
                "exception_chained_from_exact_parent_helper": True,
                "abort_frame_local_schema_id": "helper_final_live_terms_v1",
                "gate_batch_propagation_completed": True,
                "policy_cap_check_reached": True,
                "kernel_cap_violation_triggered": False,
                "live_expansion_snapshot_available": True,
                "policy_relation": (
                    "pretruncation_expansion_count>"
                    "policy_max_single_expansion_terms"
                ),
                "pretruncation_expansion_count": observed,
                "enforced_term_cap": policy_cap,
            },
            "transient_live_terms": {
                "exception_type": "RuntimeError",
                "exception_message": (
                    "design policy transient live-term cap exceeded"
                ),
                "exception_source_role": "exact_parent_helper",
                "exception_chained_from_exact_parent_helper": True,
                "abort_frame_local_schema_id": "helper_transient_live_terms_v1",
                "gate_batch_propagation_completed": True,
                "policy_cap_check_reached": True,
                "kernel_cap_violation_triggered": False,
                "live_expansion_snapshot_available": True,
                "policy_relation": (
                    "peak_live_terms_this_checkpoint>"
                    "policy_max_single_expansion_terms>="
                    "pretruncation_expansion_count"
                ),
                "pretruncation_expansion_count": policy_cap,
                "enforced_term_cap": policy_cap,
            },
            "kernel_single_expansion_terms": {
                "exception_type": "SchemaError",
                "exception_message": "v2 single-expansion term cap exceeded",
                "exception_source_role": "exact_wrapped_v2_kernel",
                "exception_chained_from_exact_parent_helper": False,
                "abort_frame_local_schema_id": (
                    "kernel_observe_count_before_pre_count_assignment_v1"
                ),
                "gate_batch_propagation_completed": False,
                "policy_cap_check_reached": False,
                "kernel_cap_violation_triggered": True,
                "live_expansion_snapshot_available": False,
                "policy_relation": (
                    "observed_term_count>"
                    "kernel_max_single_expansion_terms_"
                    "before_pretruncation_assignment"
                ),
                "pretruncation_expansion_count": None,
                "enforced_term_cap": kernel_cap,
            },
        }
        spec = specs[kind]
        message = spec["exception_message"]
        anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
        abort = {
            "schema_version": 1,
            "abort_id": (
                "D_k655360_c37_l1048576_d1048576_"
                "q76_policy_resource_abort_v1"
            ),
            "abort_kind": kind,
            "exception_args": [message],
            "control_flow_root_source_sha256": (
                self.parent.EXPECTED_CONTROL_FLOW_ROOT_SHA256
            ),
            "helper_source_sha256": self.parent.EXPECTED_V2_HELPER_SHA256,
            "kernel_source_sha256": self.parent.EXPECTED_V2_ARITHMETIC_SHA256,
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            "stage_index": anchor["stage_index"],
            "stage_group": anchor["stage_group"],
            "batch_in_stage": anchor["batch_in_stage"],
            "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
            "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
            "gate_batch_sha256": anchor["gate_batch_sha256"],
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "observed_term_count": observed,
            "policy_max_single_expansion_terms": policy_cap,
            "kernel_max_single_expansion_terms": kernel_cap,
            "observed_excess_terms": observed - spec["enforced_term_cap"],
            "gate_batch_propagation_started": True,
            "attempted_checkpoint_pretruncation_digest_computed": False,
            "attempted_checkpoint_ranking_performed": False,
            "attempted_checkpoint_candidate_rows_constructed": False,
            "attempted_checkpoint_selection_performed": False,
            "attempted_checkpoint_commit_performed": False,
            "attempted_checkpoint_record_constructed": False,
            "attempted_checkpoint_partial_expansion_committed": False,
            "last_committed_record_sha256": digest(previous),
            "peak_live_terms_this_checkpoint": observed,
            "peak_live_terms_cumulative": max(
                previous["peak_live_terms_cumulative"], observed
            ),
            "term_gate_visits_increment": previous[
                "retained_expansion_count"
            ],
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"]
                + previous["retained_expansion_count"]
            ),
            "rounding_increment_scaled_ticks_squared": "1",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
            "maximum_expansion_coefficient_tick_bits": previous[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": previous["maximum_product_bits"],
            **spec,
        }
        self.assertEqual(
            frozenset(abort), self.parent.RESOURCE_POLICY_ABORT_KEYS
        )
        return abort

    def make_raw_result(
        self,
        branch,
        abort_kind="kernel_single_expansion_terms",
    ):
        raw = {
            key: copy.deepcopy(self.predecessor[key])
            for key in self.parent.UPSTREAM_PARENT_RESULT_KEYS
        }
        records = copy.deepcopy(self.predecessor["records"])
        history = list(self.predecessor["selected_K_history"])
        q74 = records[-1]
        abort = None
        if branch == "q75_failure":
            records.append(self.make_record(q74, 75, False))
        elif branch == "q75_abort":
            abort = self.make_abort(q74, 75, abort_kind)
        else:
            q75 = self.make_record(q74, 75, True)
            records.append(q75)
            history.append(q75["selected_K"])
            if branch == "q76_failure":
                records.append(self.make_record(q75, 76, False))
            elif branch == "q76_abort":
                abort = self.make_abort(q75, 76, abort_kind)
            elif branch == "q76_success":
                q76 = self.make_record(q75, 76, True)
                records.append(q76)
                history.append(q76["selected_K"])
            else:
                raise AssertionError(branch)
        attempted = (
            abort["checkpoint_number_one_based"]
            if abort is not None
            else records[-1]["checkpoint_number_one_based"]
        )
        final = records[-1]
        failed = (
            abort is None
            and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        completed = len(history)
        raw.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": self.parent.EXPECTED_CONTROL_FLOW_ROOT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_execution_components": copy.deepcopy(
                list(self.parent.EXPECTED_PARENT_EXECUTION_COMPONENTS)
            ),
            "configuration_reference": {"synthetic": True},
            "checkpoint_transform": copy.deepcopy(
                self.predecessor["checkpoint_transform"][
                    "execution_parent_q74_transform"
                ]
                if "execution_parent_q74_transform"
                in self.predecessor["checkpoint_transform"]
                else self.predecessor["checkpoint_transform"][
                    "physical_four_gate_control_flow_parent_transform"
                ]
            ),
            "source_custody": dict(self.parent.EXPECTED_PARENT_SOURCE_CUSTODY),
            "screen_horizon_checkpoint_count": 76,
            "horizon_checkpoint_attempted": attempted == 76,
            "horizon_reached_with_committed_checkpoint": branch == "q76_success",
            "attempted_checkpoint_count": attempted,
            "completed_checkpoint_count": completed,
            "failure_checkpoint_included": failed,
            "selected_K_history": history,
            "records": records,
            "failure_record_sha256": digest(final) if failed else None,
            "last_committed_cumulative_drop_ticks": records[
                completed - 1
            ]["E_after_ticks"],
            "screen_terminal_condition": (
                "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
                if abort is not None
                else (
                    "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                    if failed
                    else "DIAGNOSTIC_HORIZON_REACHED"
                )
            ),
            "resource_policy_abort": abort,
            "resource_policy_abort_sha256": (
                digest(abort) if abort is not None else None
            ),
        })
        raw["screen_execution_components_sha256"] = digest(
            raw["screen_execution_components"]
        )
        raw["configuration_reference_sha256"] = digest(
            raw["configuration_reference"]
        )
        raw["checkpoint_transform_sha256"] = digest(raw["checkpoint_transform"])
        raw["selected_K_history_sha256"] = digest(history)
        raw["records_sha256"] = digest(records)
        resource = abort if abort is not None else final
        raw["observed_peak_single_expansion_terms"] = resource[
            "peak_live_terms_cumulative"
        ]
        raw["observed_term_gate_visits_including_terminal_attempt"] = resource[
            "term_gate_visits_cumulative"
        ]
        raw["observed_maximum_expansion_coefficient_tick_bits"] = resource[
            "maximum_expansion_coefficient_tick_bits"
        ]
        raw["observed_maximum_product_bits"] = resource["maximum_product_bits"]
        raw["observed_rounding_cumulative_scaled_ticks_squared"] = resource[
            "rounding_cumulative_scaled_ticks_squared"
        ]
        raw["child_boundary_committed"] = False
        raw["positive_artifact_generated"] = False
        self.assertEqual(frozenset(raw), self.parent.EXPECTED_PARENT_RESULT_KEYS)
        return raw

    def replay_context(self):
        return {
            "execution_parent_private_entrypoint_called": True,
            "q74_canonical_loaded_before_replay": False,
            "q74_route_loader_suppressed": True,
            "q74_relabel_suppressed": True,
            "q72_inner_eight_attributes_restored": True,
            "q75_q76_abort_adapter_installed": True,
            "q74_replay_context": {
                "raw_control_flow_horizon_override": {
                    "changed_fields": [
                        "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
                    ],
                    "semantic_delta": {
                        "MODE_CONFIG.double_occupancy.horizon_checkpoint_count": {
                            "before": 66,
                            "after": 76,
                        }
                    },
                }
            },
        }

    def test_01_static_pins_caps_schema_and_parent(self):
        SCREEN.validate_local_configuration(self.parent)
        self.assertEqual(len(SCREEN_RAW), EXPECTED_SCREEN_SIZE)
        self.assertEqual(digest(SCREEN_RAW), EXPECTED_SCREEN_SHA256)
        self.assertLessEqual(len(SCREEN_RAW), SCREEN.MAX_SELF_SOURCE_BYTES)
        self.assertEqual(len(self.parent.D_CANDIDATES), 37)
        self.assertNotIn(638_976, self.parent.D_CANDIDATES)
        self.assertEqual(
            {
                "raw": len(self.parent.EXPECTED_PARENT_RESULT_KEYS),
                "final": len(self.parent.EXPECTED_RELABELLED_RESULT_KEYS),
                "success": len(self.parent.SUCCESS_RECORD_KEYS),
                "failure": len(self.parent.FAILURE_RECORD_KEYS),
                "row": len(self.parent.CANDIDATE_RECORD_KEYS),
                "abort": len(self.parent.RESOURCE_POLICY_ABORT_KEYS),
            },
            {
                "raw": 67,
                "final": 96,
                "success": 38,
                "failure": 32,
                "row": 7,
                "abort": 50,
            },
        )
        builder = SCREEN._derived_q75_q76_abort_builder(self.parent)
        self.assertEqual(builder.__code__.co_consts.count((75, 76)), 1)
        self.assertEqual(
            {
                "self": SCREEN.MAX_SELF_SOURCE_BYTES,
                "pinned": SCREEN.MAX_PINNED_SOURCE_BYTES,
                "route": SCREEN.MAX_ROUTE_TRANSCRIPT_BYTES,
                "boundary": SCREEN.MAX_BOUNDARY_INPUT_BYTES,
                "output": SCREEN.MAX_OUTPUT_BYTES,
            },
            {
                "self": 131_072,
                "pinned": 262_144,
                "route": 1_048_576,
                "boundary": 1_048_576,
                "output": 4_194_304,
            },
        )
        route_source = inspect.getsource(SCREEN.load_route_reference)
        self.assertEqual(route_source.count("MAX_PINNED_SOURCE_BYTES"), 3)
        self.assertEqual(route_source.count("MAX_ROUTE_TRANSCRIPT_BYTES"), 1)
        self.assertEqual(route_source.count("MAX_BOUNDARY_INPUT_BYTES"), 1)

    def test_02_q74_reference_is_exact_post_only_and_flattened(self):
        raw = (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(len(raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE)
        self.assertEqual(
            digest(raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256
        )
        self.assertEqual(raw, canonical_bytes(self.predecessor))
        self.assertEqual(len(self.predecessor["records"]), 74)
        self.assertEqual(len(self.predecessor["selected_K_history"]), 74)
        reference = self.route_reference["canonical_transcript"]
        self.assertFalse(reference["loaded_before_replay"])
        self.assertTrue(reference["loaded_after_full_replay_as_exact_reference"])
        self.assertFalse(reference["propagation_input"])
        self.assertFalse(reference["state_resume_input"])
        predecessor_components = self.predecessor["screen_execution_components"]
        boundary_components = [
            item for item in predecessor_components
            if item["relative_path"] == SCREEN.BOUNDARY_INPUT_NAME
            or item["role"] == SCREEN.EXPECTED_BOUNDARY_INPUT_ROLE
        ]
        self.assertEqual(boundary_components, [{
            "relative_path": SCREEN.BOUNDARY_INPUT_NAME,
            "role": SCREEN.EXPECTED_BOUNDARY_INPUT_ROLE,
            "sha256": SCREEN.EXPECTED_BOUNDARY_INPUT_SHA256,
        }])
        boundary_path = HERE / SCREEN.BOUNDARY_INPUT_NAME
        self.assertEqual(
            boundary_path.stat().st_size,
            SCREEN.EXPECTED_BOUNDARY_INPUT_FILE_SIZE,
        )
        self.assertEqual(
            digest(boundary_path.read_bytes()),
            SCREEN.EXPECTED_BOUNDARY_INPUT_SHA256,
        )
        for item in predecessor_components:
            if item["relative_path"] != SCREEN.BOUNDARY_INPUT_NAME:
                self.assertLessEqual(
                    (HERE / item["relative_path"]).stat().st_size,
                    SCREEN.MAX_PINNED_SOURCE_BYTES,
                )
        for relative_path in self.predecessor["source_custody"]:
            self.assertLessEqual(
                (HERE / relative_path).stat().st_size,
                SCREEN.MAX_PINNED_SOURCE_BYTES,
            )
        components = SCREEN._flatten_components(
            self.predecessor,
            EXPECTED_SCREEN_SHA256,
        )
        custody = SCREEN._flatten_custody(
            self.predecessor,
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(len(components), 11)
        self.assertEqual(len(custody), 10)
        self.assertNotIn(SCREEN.NESTED_Q72_PARENT_NAME, custody)

    def make_fake_q72(self, failure=None):
        q72 = types.ModuleType("fake_q72")
        q72.EXTENDED_HORIZON = 72
        q72.validate_local_configuration = lambda: None
        q72.load_configured_v6_baseline = lambda repo: (
            object(), self.parent.D_CANDIDATES
        )
        kernel = types.SimpleNamespace()
        q72.load_kernel_wrapper = lambda repo: (
            kernel,
            self.parent.EXPECTED_KERNEL_WRAPPER_SHA256,
            {"synthetic": True},
        )
        q72.load_route_reference = lambda repo, replay_completed: ({}, {})
        q72.configure_parent_execution = lambda control, config, wrapper: {
            "changed_fields": [
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
            ],
            "semantic_delta": {
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count": {
                    "before": 66,
                    "after": 76,
                }
            },
        }
        q72.execute_parent_fail_closed = lambda control, repo: {}
        q72.validate_and_relabel = lambda result, *args: result
        q72.normalize_completed_parent_result = lambda value: value
        control = types.ModuleType("fake_control")
        control.run_four_gate = lambda *args: {}
        if failure is None:
            control._run_verified = lambda repo, mode: {}
        else:
            control._run_verified = lambda repo, mode: (
                (_ for _ in ()).throw(failure)
            )

        def fake_verified(repo):
            config, _ = q72.load_configured_v6_baseline(repo)
            wrapped, _, _ = q72.load_kernel_wrapper(repo)
            q72.configure_parent_execution(control, config, wrapped)
            result = q72.execute_parent_fail_closed(control, repo)
            predecessor, reference = q72.load_route_reference(
                repo,
                replay_completed=True,
            )
            return q72.validate_and_relabel(
                result,
                predecessor,
                reference,
                None,
                {},
            )

        q72._run_verified = fake_verified
        return q72

    def test_03_outer_six_and_inner_eight_restore_success_and_exception(self):
        for failure in (None, RuntimeError("synthetic replay failure")):
            with self.subTest(failure=failure):
                parent = SCREEN.load_execution_parent(HERE)
                q72 = self.make_fake_q72(failure)
                outer_names = (
                    "EXTENDED_HORIZON", "validate_local_configuration",
                    "execute_parent_replay", "load_route_reference",
                    "validate_and_relabel", "build_resource_abort_parent_result",
                )
                inner_names = (
                    "EXTENDED_HORIZON", "validate_local_configuration",
                    "load_configured_v6_baseline", "load_kernel_wrapper",
                    "load_route_reference", "configure_parent_execution",
                    "execute_parent_fail_closed", "validate_and_relabel",
                )
                outer = {name: getattr(parent, name) for name in outer_names}
                inner = {name: getattr(q72, name) for name in inner_names}
                old_loader = parent.load_execution_parent
                parent.load_execution_parent = lambda repo: q72
                try:
                    if failure is None:
                        result, context = SCREEN.execute_parent_replay(
                            parent, HERE
                        )
                        self.assertEqual(result, {})
                        self.assertTrue(
                            context["q72_inner_eight_attributes_restored"]
                        )
                        self.assertTrue(context["q74_route_loader_suppressed"])
                        self.assertTrue(context["q74_relabel_suppressed"])
                        self.assertTrue(
                            context["q74_replay_context"][
                                "execution_parent_route_loader_suppressed"
                            ]
                        )
                    else:
                        with self.assertRaises(RuntimeError) as caught:
                            SCREEN.execute_parent_replay(parent, HERE)
                        self.assertIs(caught.exception, failure)
                finally:
                    parent.load_execution_parent = old_loader
                for name, value in outer.items():
                    self.assertIs(getattr(parent, name), value)
                for name, value in inner.items():
                    self.assertIs(getattr(q72, name), value)

    def test_04_all_five_terminal_branches_and_counts(self):
        expected = {
            "q75_failure": (
                "Q75_FAILURE_Q76_NOT_ATTEMPTED", 75, 74, 2775
            ),
            "q75_abort": (
                "Q75_RESOURCE_ABORT_Q76_NOT_ATTEMPTED", 74, 74, 2738
            ),
            "q76_failure": (
                "Q75_SUCCESS_Q76_FAILURE", 76, 75, 2812
            ),
            "q76_abort": (
                "Q75_SUCCESS_Q76_RESOURCE_ABORT", 75, 75, 2775
            ),
            "q76_success": (
                "Q75_AND_Q76_SUCCESS_HORIZON_REACHED", 76, 76, 2812
            ),
        }
        for branch, (terminal, records, history, rows) in expected.items():
            with self.subTest(branch=branch):
                raw = self.make_raw_result(branch)
                handoff = SCREEN.validate_replay_handoff(
                    raw,
                    self.predecessor,
                    self.parent,
                )
                self.assertEqual(handoff["terminal_branch"], terminal)
                self.assertEqual(len(raw["records"]), records)
                self.assertEqual(len(raw["selected_K_history"]), history)
                self.assertEqual(
                    sum(len(item["candidate_records"]) for item in raw["records"]),
                    rows,
                )

    def test_05_q75_q76_each_close_three_abort_kinds(self):
        for branch, checkpoint in (("q75_abort", 75), ("q76_abort", 76)):
            for kind in (
                "final_live_terms",
                "transient_live_terms",
                "kernel_single_expansion_terms",
            ):
                with self.subTest(branch=branch, kind=kind):
                    raw = self.make_raw_result(branch, kind)
                    handoff = SCREEN.validate_replay_handoff(
                        raw,
                        self.predecessor,
                        self.parent,
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_checkpoint"], checkpoint
                    )
                    self.assertEqual(handoff["resource_policy_abort_kind"], kind)
                    abort = raw["resource_policy_abort"]
                    self.assertEqual(len(abort), 50)
                    for field in (
                        "attempted_checkpoint_pretruncation_digest_computed",
                        "attempted_checkpoint_ranking_performed",
                        "attempted_checkpoint_candidate_rows_constructed",
                        "attempted_checkpoint_selection_performed",
                        "attempted_checkpoint_commit_performed",
                        "attempted_checkpoint_record_constructed",
                        "attempted_checkpoint_partial_expansion_committed",
                    ):
                        self.assertFalse(abort[field])

    def test_06_unknown_exception_identity_and_known_dispatch(self):
        class KernelSchemaError(ValueError):
            pass

        class RuntimeSubclass(RuntimeError):
            pass

        class KernelSubclass(KernelSchemaError):
            pass

        kernel = types.SimpleNamespace(SchemaError=KernelSchemaError)
        execution_parent = types.SimpleNamespace(
            normalize_completed_parent_result=lambda value: value
        )
        control = types.SimpleNamespace()
        old_builder = self.parent.build_resource_abort_parent_result
        try:
            self.parent.build_resource_abort_parent_result = (
                lambda *args: {"structured": type(args[-1]).__name__}
            )
            for exception in (
                RuntimeError("design policy live-term cap exceeded"),
                RuntimeError("design policy transient live-term cap exceeded"),
                KernelSchemaError("v2 single-expansion term cap exceeded"),
            ):
                control._run_verified = lambda repo, mode, exc=exception: (
                    (_ for _ in ()).throw(exc)
                )
                observed = self.parent.execute_control_parent_with_structured_abort(
                    execution_parent, control, kernel, HERE
                )
                self.assertIn("structured", observed)
            unknowns = (
                RuntimeError("unknown resource error"),
                RuntimeSubclass("design policy live-term cap exceeded"),
                KernelSchemaError("wrong kernel message"),
                KernelSubclass("v2 single-expansion term cap exceeded"),
                ValueError("unrelated"),
            )
            for unknown in unknowns:
                control._run_verified = lambda repo, mode, exc=unknown: (
                    (_ for _ in ()).throw(exc)
                )
                with self.assertRaises(type(unknown)) as caught:
                    self.parent.execute_control_parent_with_structured_abort(
                        execution_parent, control, kernel, HERE
                    )
                self.assertIs(caught.exception, unknown)
        finally:
            self.parent.build_resource_abort_parent_result = old_builder

    def test_07_prefix_and_extended_record_tamper_fail_closed(self):
        cases = []
        record = self.make_raw_result("q76_success")
        record["records"][0]["status"] = "tampered"
        record["records_sha256"] = digest(record["records"])
        cases.append(record)
        history = self.make_raw_result("q76_success")
        history["selected_K_history"][0] += 1
        history["selected_K_history_sha256"] = digest(
            history["selected_K_history"]
        )
        cases.append(history)
        row = self.make_raw_result("q76_success")
        row["records"][73]["candidate_records"][0]["drop_ticks"] = "1"
        row["records_sha256"] = digest(row["records"])
        cases.append(row)
        anchor = self.make_raw_result("q76_success")
        anchor["records"][74]["gate_batch_sha256"] = "0" * 64
        anchor["records_sha256"] = digest(anchor["records"])
        cases.append(anchor)
        boundary = self.make_raw_result("q76_success")
        boundary["records"][74]["minimum_retained_abs_upper_ticks"] = "0"
        boundary["records"][74]["maximum_dropped_abs_upper_ticks"] = "1"
        boundary["records_sha256"] = digest(boundary["records"])
        cases.append(boundary)
        feasibility = self.make_raw_result("q76_success")
        feasibility["records"][74]["candidate_records"][0][
            "feasible_under_current_prefix_cap"
        ] = False
        feasibility["records_sha256"] = digest(feasibility["records"])
        cases.append(feasibility)
        arithmetic = self.make_raw_result("q76_success")
        arithmetic["records"][74]["candidate_records"][0]["drop_ticks"] = "1"
        arithmetic["records_sha256"] = digest(arithmetic["records"])
        cases.append(arithmetic)
        excluded = self.make_raw_result("q76_success")
        excluded["records"][74]["candidate_records"][0][
            "configured_K"
        ] = 638_976
        excluded["records_sha256"] = digest(excluded["records"])
        cases.append(excluded)
        prefix = self.make_raw_result("q76_success")
        prefix["records"][74]["budget_prefix_cap_ticks"] = "0"
        prefix["records_sha256"] = digest(prefix["records"])
        cases.append(prefix)
        for case in cases:
            with self.subTest():
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(
                        case,
                        self.predecessor,
                        self.parent,
                    )

    def test_08_relabel_closes_11_components_10_custody_and_nested(self):
        result = SCREEN.validate_and_relabel(
            self.make_raw_result("q76_success"),
            self.predecessor,
            self.route_reference,
            self.parent,
            self.replay_context(),
        )
        self.assertEqual(len(result), 96)
        self.assertEqual(len(result["screen_execution_components"]), 11)
        self.assertEqual(len(result["source_custody"]), 10)
        paths = {
            item["relative_path"]
            for item in result["screen_execution_components"]
        }
        self.assertNotIn(SCREEN.NESTED_Q72_PARENT_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        for value, digest_field in (
            ("screen_execution_components", "screen_execution_components_sha256"),
            ("configuration_reference", "configuration_reference_sha256"),
            ("configuration_override", "configuration_override_sha256"),
            ("kernel_capability_override", "kernel_capability_override_sha256"),
            ("parent_horizon_override", "parent_horizon_override_sha256"),
            ("route_predecessor_reference", "route_predecessor_reference_sha256"),
            ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
        ):
            self.assertEqual(digest(result[value]), result[digest_field])

    def test_09_run_order_is_replay_then_q74_reference(self):
        fresh = SCREEN.fresh_self_module()
        events = []
        parent = object()
        originals = (
            fresh.load_execution_parent,
            fresh.execute_parent_replay,
            fresh.load_route_reference,
            fresh.validate_and_relabel,
        )
        try:
            fresh.load_execution_parent = lambda repo: parent
            fresh.execute_parent_replay = lambda observed, repo: (
                events.append("replay") or ({}, {})
            )
            fresh.load_route_reference = lambda repo, observed: (
                events.append("reference") or ({}, {})
            )
            fresh.validate_and_relabel = lambda *args: (
                events.append("relabel") or {"ok": True}
            )
            self.assertEqual(fresh._run_verified(HERE), {"ok": True})
            self.assertEqual(events, ["replay", "reference", "relabel"])
            events.clear()
            sentinel = RuntimeError("replay failed")
            fresh.execute_parent_replay = lambda observed, repo: (
                (_ for _ in ()).throw(sentinel)
            )
            with self.assertRaises(RuntimeError) as caught:
                fresh._run_verified(HERE)
            self.assertIs(caught.exception, sentinel)
            self.assertEqual(events, [])
        finally:
            (
                fresh.load_execution_parent,
                fresh.execute_parent_replay,
                fresh.load_route_reference,
                fresh.validate_and_relabel,
            ) = originals

    def test_10_atomic_output_is_bounded_and_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaises(RuntimeError):
                SCREEN.write_atomic_bounded(output, bytearray(b"{}"))
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaises(RuntimeError):
                SCREEN.write_atomic_bounded(
                    output,
                    b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1),
                )
            self.assertEqual(output.read_bytes(), b"{}")

    def test_11_default_suite_has_no_run_calls(self):
        replay_name = "test_13_real_replay_is_opt_in"

        def run_calls(method):
            tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
            return [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
            ]

        default_names = sorted(
            name
            for name in dir(type(self))
            if name.startswith("test_") and name != replay_name
        )
        for name in default_names:
            self.assertEqual(run_calls(getattr(type(self), name)), [], name)

        replay_method = getattr(type(self), replay_name)
        self.assertEqual(len(run_calls(replay_method)), 1)
        self.assertEqual(
            bool(getattr(replay_method, "__unittest_skip__", False)),
            os.environ.get("FERMION_RUN_D655360_C37_Q76_REPLAY") != "1",
        )

    def test_12_canonical_exact_bytes_failure_and_provenance_closure(self):
        raw = self.canonical_raw
        canonical = self.canonical
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(digest(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertEqual(raw, canonical_bytes(canonical))
        self.assertEqual(
            frozenset(canonical), self.parent.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(canonical), 96)

        expected_top = {
            "transcript_fingerprint": (
                "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
                "k655360_c37_l1048576_d1048576_q76_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "screen_horizon_checkpoint_count": 76,
            "attempted_checkpoint_count": 76,
            "completed_checkpoint_count": 75,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "failure_checkpoint_included": True,
            "failure_record_sha256": EXPECTED_CANONICAL[
                "q76_record_sha256"
            ],
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "last_committed_cumulative_drop_ticks": "2289318681442732",
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
            "positive_artifact_generated": False,
            "child_boundary_committed": False,
            "observed_peak_single_expansion_terms": 799_279,
            "observed_term_gate_visits_including_terminal_attempt": (
                103_932_519
            ),
            "observed_maximum_expansion_coefficient_tick_bits": 63,
            "observed_maximum_product_bits": 120,
            "observed_rounding_cumulative_scaled_ticks_squared": (
                "147992458621100020494474752"
            ),
        }
        for field, expected in expected_top.items():
            self.assertEqual(canonical[field], expected, field)

        records = canonical["records"]
        history = canonical["selected_K_history"]
        self.assertEqual(len(records), 76)
        self.assertEqual(len(history), 75)
        self.assertEqual(
            sum(len(record["candidate_records"]) for record in records),
            2_812,
        )
        self.assertEqual(records[:74], self.predecessor["records"])
        self.assertEqual(
            history[:74], self.predecessor["selected_K_history"]
        )
        self.assertEqual(history[74:], [SCREEN.K655360])
        self.assertEqual(
            canonical["records_sha256"],
            EXPECTED_CANONICAL["records_sha256"],
        )
        self.assertEqual(
            digest(records), EXPECTED_CANONICAL["records_sha256"]
        )
        self.assertEqual(
            canonical["selected_K_history_sha256"],
            EXPECTED_CANONICAL["history_sha256"],
        )
        self.assertEqual(
            digest(history), EXPECTED_CANONICAL["history_sha256"]
        )

        q74, q75, q76 = records[73:76]
        self.assertEqual(frozenset(q75), self.parent.SUCCESS_RECORD_KEYS)
        self.assertEqual(frozenset(q76), self.parent.FAILURE_RECORD_KEYS)
        self.assertEqual(
            digest(q75), EXPECTED_CANONICAL["q75_record_sha256"]
        )
        self.assertEqual(
            digest(q75["candidate_records"]),
            EXPECTED_CANONICAL["q75_rows_sha256"],
        )
        self.assertEqual(
            digest(q76), EXPECTED_CANONICAL["q76_record_sha256"]
        )
        self.assertEqual(
            digest(q76["candidate_records"]),
            EXPECTED_CANONICAL["q76_rows_sha256"],
        )
        self.assertEqual(
            {key: q75[key] for key in (
                "checkpoint_number_one_based",
                "checkpoint_index_zero_based",
                "stage_index",
                "stage_group",
                "batch_in_stage",
                "gate_occurrence_first_zero_based",
                "gate_occurrence_last_zero_based",
                "gate_batch_sha256",
                "budget_prefix_cap_ticks",
                "pretruncation_expansion_count",
                "selected_K",
                "selected_candidate_index",
                "selected_drop_ticks",
                "retained_expansion_count",
                "retained_expansion_sha256",
                "E_after_ticks",
                "status",
            )},
            {
                "checkpoint_number_one_based": 75,
                "checkpoint_index_zero_based": 74,
                "stage_index": 2,
                "stage_group": "HU",
                "batch_in_stage": 18,
                "gate_occurrence_first_zero_based": 296,
                "gate_occurrence_last_zero_based": 299,
                "gate_batch_sha256": (
                    "d2bc2f79ddb0b0f03897e0e8705e4d2bcc63c7653b04988c17f54a4fbd95e70f"
                ),
                "budget_prefix_cap_ticks": "2289337503783615",
                "pretruncation_expansion_count": 733_965,
                "selected_K": 655_360,
                "selected_candidate_index": 36,
                "selected_drop_ticks": "127874290338",
                "retained_expansion_count": 655_360,
                "retained_expansion_sha256": (
                    "1a0c6aae47e81c4473b43ca5c27f8580a8754c72f9332e761bbddc1b31722def"
                ),
                "E_after_ticks": "2289318681442732",
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            },
        )
        self.assertEqual(
            {key: q76[key] for key in (
                "checkpoint_number_one_based",
                "checkpoint_index_zero_based",
                "stage_index",
                "stage_group",
                "batch_in_stage",
                "gate_occurrence_first_zero_based",
                "gate_occurrence_last_zero_based",
                "gate_batch_sha256",
                "budget_prefix_cap_ticks",
                "pretruncation_expansion_count",
                "minimum_effective_K_to_meet_prefix",
                "required_K_excess_over_policy_maximum",
                "maximum_candidate_drop_excess_over_slack_ticks",
                "selected_K",
                "selected_candidate_index",
                "status",
            )},
            {
                "checkpoint_number_one_based": 76,
                "checkpoint_index_zero_based": 75,
                "stage_index": 2,
                "stage_group": "HU",
                "batch_in_stage": 19,
                "gate_occurrence_first_zero_based": 300,
                "gate_occurrence_last_zero_based": 303,
                "gate_batch_sha256": (
                    "7ed21993d3a203f135c12b0b7f658c6a966c7aa62cd98f276559dce4213bfc63"
                ),
                "budget_prefix_cap_ticks": "2289420005773549",
                "pretruncation_expansion_count": 789_691,
                "minimum_effective_K_to_meet_prefix": 665_836,
                "required_K_excess_over_policy_maximum": 10_476,
                "maximum_candidate_drop_excess_over_slack_ticks": (
                    "58984624003"
                ),
                "selected_K": None,
                "selected_candidate_index": None,
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            },
        )

        self.assertEqual(q75["E_before_ticks"], q74["E_after_ticks"])
        self.assertEqual(
            q75["input_expansion_count"], q74["retained_expansion_count"]
        )
        self.assertEqual(
            q75["input_expansion_sha256"],
            q74["retained_expansion_sha256"],
        )
        self.assertEqual(q76["E_before_ticks"], q75["E_after_ticks"])
        self.assertEqual(
            q76["input_expansion_count"], q75["retained_expansion_count"]
        )
        self.assertEqual(
            q76["input_expansion_sha256"],
            q75["retained_expansion_sha256"],
        )
        self.assertEqual(len(q75["candidate_records"]), 37)
        self.assertEqual(len(q76["candidate_records"]), 37)
        for record, selected_index in ((q75, 36), (q76, None)):
            rows = record["candidate_records"]
            for index, (row, configured_K) in enumerate(zip(
                rows, self.parent.D_CANDIDATES
            )):
                self.assertEqual(
                    frozenset(row), self.parent.CANDIDATE_RECORD_KEYS
                )
                self.assertEqual(row["candidate_index"], index)
                self.assertEqual(row["configured_K"], configured_K)
                effective = min(
                    configured_K, record["pretruncation_expansion_count"]
                )
                self.assertEqual(row["effective_retained_count"], effective)
                self.assertEqual(
                    row["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                self.assertEqual(
                    int(row["E_after_if_selected_ticks"]),
                    int(record["E_before_ticks"]) + int(row["drop_ticks"]),
                )
                self.assertIs(
                    row["feasible_under_current_prefix_cap"],
                    index == selected_index,
                )

        route = canonical["route_predecessor_reference"]
        reference = route["canonical_transcript"]
        self.assertEqual(reference["file_sha256"], digest(
            (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        ))
        for field in (
            "loaded_before_replay",
            "checkpoint_74_state_loaded",
            "propagation_input",
            "state_resume_input",
            "compiled",
            "executed",
            "execution_source_layer",
        ):
            self.assertFalse(reference[field], field)
        self.assertTrue(
            reference["loaded_after_full_replay_as_exact_reference"]
        )
        self.assertTrue(
            reference["used_only_for_post_replay_q1_q74_prefix_validation"]
        )
        self.assertTrue(route["execution_parent_screen"]["executed"])
        self.assertTrue(
            route["execution_parent_screen"]["private_entrypoint_called"]
        )
        self.assertFalse(route["q75_q76_K638976_threshold_or_drop_asserted"])
        self.assertFalse(
            canonical["checkpoint_transform"][
                "q75_and_q76_outcomes_precommitted"
            ]
        )

        handoff = canonical["predecessor_handoff_validation"]
        self.assertEqual(
            handoff["terminal_branch"], "Q75_SUCCESS_Q76_FAILURE"
        )
        self.assertFalse(handoff["resource_policy_abort_structured"])
        self.assertIsNone(handoff["resource_policy_abort_checkpoint"])
        self.assertIsNone(handoff["resource_policy_abort_kind"])
        self.assertIsNone(handoff["resource_policy_abort_sha256"])
        self.assertTrue(handoff["q76_checkpoint_record_constructed"])
        self.assertFalse(handoff["q75_and_q76_outcomes_precommitted"])
        self.assertEqual(
            canonical["predecessor_handoff_validation_sha256"],
            EXPECTED_CANONICAL["handoff_sha256"],
        )
        self.assertEqual(
            digest(handoff), EXPECTED_CANONICAL["handoff_sha256"]
        )

        self.assertEqual(
            canonical["candidate_K_values"], list(self.parent.D_CANDIDATES)
        )
        self.assertEqual(
            canonical["proposed_policy_caps"],
            {**self.parent.POLICY_CAPS_BASE, "max_candidate_count": 37},
        )
        self.assertEqual(
            canonical["kernel_capability_limits"],
            self.parent.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )
        self.assertEqual(
            canonical["proposed_policy_caps"]["max_single_expansion_terms"],
            1_048_576,
        )
        self.assertEqual(
            canonical["kernel_capability_limits"][
                "max_single_expansion_terms"
            ],
            1_048_576,
        )
        self.assertFalse(
            route["incremental_semantic_delta"]["policy_caps_changed"]
        )
        self.assertFalse(
            route["incremental_semantic_delta"][
                "kernel_capability_limits_changed"
            ]
        )

        for field, digest_field in (
            ("configuration_reference", "configuration_reference_sha256"),
            ("configuration_override", "configuration_override_sha256"),
            ("kernel_capability_override", "kernel_capability_override_sha256"),
            ("parent_horizon_override", "parent_horizon_override_sha256"),
            ("route_predecessor_reference", "route_predecessor_reference_sha256"),
            ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
        ):
            self.assertEqual(digest(canonical[field]), canonical[digest_field])

        components = canonical["screen_execution_components"]
        custody = canonical["source_custody"]
        self.assertEqual(
            components,
            SCREEN._flatten_components(
                self.predecessor, EXPECTED_SCREEN_SHA256
            ),
        )
        self.assertEqual(
            custody,
            SCREEN._flatten_custody(self.predecessor, EXPECTED_SCREEN_SHA256),
        )
        self.assertEqual(len(components), 11)
        self.assertEqual(len(custody), 10)
        self.assertEqual(
            canonical["screen_execution_components_sha256"],
            EXPECTED_CANONICAL["components_sha256"],
        )
        self.assertEqual(
            digest(components), EXPECTED_CANONICAL["components_sha256"]
        )
        self.assertEqual(
            digest(custody), EXPECTED_CANONICAL["custody_sha256"]
        )
        component_paths = {
            item["relative_path"] for item in components
        }
        self.assertNotIn(SCREEN.NESTED_Q72_PARENT_NAME, component_paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, component_paths)
        self.assertNotIn(SCREEN.NESTED_Q72_PARENT_NAME, custody)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, custody)
        for component in components:
            self.assertEqual(
                digest((HERE / component["relative_path"]).read_bytes()),
                component["sha256"],
                component["relative_path"],
            )
        for relative_path, expected_sha in custody.items():
            self.assertEqual(
                digest((HERE / relative_path).read_bytes()),
                expected_sha,
                relative_path,
            )

    @unittest.skipUnless(
        os.environ.get("FERMION_RUN_D655360_C37_Q76_REPLAY") == "1",
        "full q1--q76 replay is explicit opt-in only",
    )
    def test_13_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertEqual(result, self.canonical)
        self.assertEqual(canonical_bytes(result), self.canonical_raw)


if __name__ == "__main__":
    unittest.main()
