#!/usr/bin/env python3
"""Static and synthetic tests for the same-cap D K655360/C37 q74 route."""

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
    "k655360_c37_l1048576_d1048576_q74_screen.py"
)
EXPECTED_SCREEN_SIZE = 117_108
EXPECTED_SCREEN_SHA256 = (
    "5e2e077a9cab2a2b83f9830d755bafb7cc6dfa1d1c8a1ffade840d09e5016376"
)
CANONICAL_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q74_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 773_489,
    "file_sha256": (
        "4421f5973253968167b1c8bd77e024b18450325ea9581ed39dbe975ec8163ec9"
    ),
    "records_sha256": (
        "f765797dad4f6892524fc651a259786dff9c10187a6c634fc088fd3508c1e89f"
    ),
    "history_sha256": (
        "d521cdf189b54254cf3ca3d0e9033b52c90ea6ec91dc571d95a605e520972ff8"
    ),
    "q73_record_sha256": (
        "2d70d69ae2148926c6115e226ed48489f3a7c34f8602c797b0ce3fd1b788a8e9"
    ),
    "q73_rows_sha256": (
        "107626e388366bd8e25b6d782325a55ee5ed68a4f7b99148af5ee3fee3f2d8e0"
    ),
    "q73_counterfactual_sha256": (
        "63f5c15222570852e1e1b4404c4560c4999b6e5c53012c573f4f0f40c2531edf"
    ),
    "q74_record_sha256": (
        "e9c61283eb88cf956cf53f29697a3296dafe9195113684d7ad6144fb8661f9ed"
    ),
    "q74_rows_sha256": (
        "9f3984d041510c48064c611a36d43423fe80c2eeeb2e08abe23a7ad077327ce1"
    ),
    "q74_counterfactual_sha256": (
        "0a1b270928af93d4905f73f62379f6bb64c2bff62573747c4f5796913ed65678"
    ),
    "all_candidate_rows_sha256": (
        "0188a245385cd11ad15972881fefd916061dd4eb73f413c8fa1acc2e47bac8d3"
    ),
    "q1_through_q72_candidate_rows_sha256": (
        "abcdbc805ed2c0c47bed32a432c7675f2033001f7ae9df387780764effad915a"
    ),
    "components_sha256": (
        "3f40762d324339d3d377f5c311ad8cfe43b4511feef4a04b3e472794a0dfc7d3"
    ),
    "custody_sha256": (
        "258df717b7a66b3e215a8e2691351ab79055b73390787f603c432ccb458547a0"
    ),
    "handoff_sha256": (
        "fb3c11fe23bbcbf54df6e5fc512ae16cce7934dbb39dab13bf1df87e931d7f03"
    ),
    "configuration_reference_sha256": (
        "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1"
    ),
    "configuration_override_sha256": (
        "f1ac8585c499b4091190e18736227900545207f370b3969447a6b5af89837280"
    ),
    "kernel_capability_override_sha256": (
        "6c7e4917b069b7ea788852cb0a8ede4837825843a937ede6d79bacadd7b436a8"
    ),
    "parent_horizon_override_sha256": (
        "b9e810a02c07915f6fca3711cb82b6c18f63734d9e41ce55e6fe662dd7597ef6"
    ),
    "route_predecessor_reference_sha256": (
        "63143480366c1c72d2618dbf7e5b6fb136757b00276fb58594827e9f2a7ef8c5"
    ),
    "checkpoint_transform_sha256": (
        "6fea7915627245dc6318107f929ba0efc1596d8ecbba039d9312bf82a20ea080"
    ),
}
SCREEN_PATH = HERE / SCREEN_NAME
SCREEN_RAW = SCREEN_PATH.read_bytes()
SCREEN = types.ModuleType("tested_d_k655360_c37_q74_screen")
SCREEN.__file__ = str(SCREEN_PATH)
SCREEN.__package__ = ""
SCREEN.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = SCREEN_RAW
exec(compile(SCREEN_RAW, str(SCREEN_PATH), "exec"), SCREEN.__dict__)


def canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def digest(value):
    payload = value if type(value) is bytes else canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def marker(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


class DQ74ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predecessor, cls.route_reference = SCREEN.load_route_reference(HERE)
        cls.canonical_raw = (HERE / CANONICAL_NAME).read_bytes()
        cls.canonical = json.loads(cls.canonical_raw)

    def make_record(self, previous, checkpoint, success):
        pre_count = 700_000
        E_before = int(previous["E_after_ticks"])
        prefix_cap = int(
            SCREEN.EXPECTED_Q73_PREFIX_CAP_TICKS
            if checkpoint == 73
            else SCREEN.EXPECTED_Q74_PREFIX_CAP_TICKS
        )
        slack = prefix_cap - E_before
        rows = []
        for index, configured_K in enumerate(SCREEN.D_CANDIDATES):
            effective = min(configured_K, pre_count)
            drop = (
                (len(SCREEN.D_CANDIDATES) - index) * 100
                if success
                else slack + (len(SCREEN.D_CANDIDATES) - index) * 100
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
            SCREEN.D_CANDIDATES[selected_index]
            if selected_index is not None
            else None
        )
        counterfactual_drop = 50 if success else slack + 50
        common = {
            "E_before_ticks": str(E_before),
            "batch_in_stage": SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[
                checkpoint
            ]["batch_in_stage"],
            "budget_prefix_cap_ticks": str(prefix_cap),
            "candidate_records": rows,
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            "gate_batch_sha256": (
                SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint][
                    "gate_batch_sha256"
                ]
            ),
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
            "ranked_suffix_sha256": marker(
                f"rank-{checkpoint}-{success}"
            ),
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
            "stage_group": "HU",
            "stage_index": 2,
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
                "selected_dropped_term_count": selected[
                    "dropped_term_count"
                ],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": marker(
                    f"dropped-{checkpoint}"
                ),
                "retained_expansion_count": selected[
                    "effective_retained_count"
                ],
                "retained_expansion_sha256": marker(
                    f"retained-{checkpoint}"
                ),
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
        policy_cap = SCREEN.POLICY_CAPS_BASE[
            "max_single_expansion_terms"
        ]
        kernel_cap = SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS[
            "max_single_expansion_terms"
        ]
        observed = policy_cap + 1
        specifications = {
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
                "abort_frame_local_schema_id": (
                    "helper_transient_live_terms_v1"
                ),
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
                "exception_message": (
                    "v2 single-expansion term cap exceeded"
                ),
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
        spec = specifications[kind]
        message = spec["exception_message"]
        anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
        abort = {
            "schema_version": 1,
            "abort_id": (
                "D_k655360_c37_l1048576_d1048576_"
                "q74_policy_resource_abort_v1"
            ),
            "abort_kind": kind,
            "exception_args": [message],
            "control_flow_root_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256
            ),
            "helper_source_sha256": SCREEN.EXPECTED_V2_HELPER_SHA256,
            "kernel_source_sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
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
            frozenset(abort), SCREEN.RESOURCE_POLICY_ABORT_KEYS
        )
        return abort

    def make_raw_result(self, branch, abort_kind="kernel_single_expansion_terms"):
        predecessor = self.predecessor
        raw = {
            key: copy.deepcopy(predecessor[key])
            for key in SCREEN.UPSTREAM_PARENT_RESULT_KEYS
        }
        records = copy.deepcopy(predecessor["records"])
        history = list(predecessor["selected_K_history"])
        q72 = records[-1]
        abort = None
        if branch == "q73_failure":
            records.append(self.make_record(q72, 73, False))
        elif branch == "q73_abort":
            abort = self.make_abort(q72, 73, abort_kind)
        else:
            q73 = self.make_record(q72, 73, True)
            records.append(q73)
            history.append(q73["selected_K"])
            if branch == "q74_failure":
                records.append(self.make_record(q73, 74, False))
            elif branch == "q74_abort":
                abort = self.make_abort(q73, 74, abort_kind)
            elif branch == "q74_success":
                q74 = self.make_record(q73, 74, True)
                records.append(q74)
                history.append(q74["selected_K"])
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
                "hubbard_l8_adaptive_k_four_gate_"
                "granularity_screen_v1"
            ),
            "screen_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256
            ),
            "control_flow_owned_by_screen": True,
            "screen_execution_components": copy.deepcopy(
                list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
            ),
            "configuration_reference": {"synthetic": True},
            "checkpoint_transform": copy.deepcopy(
                predecessor["checkpoint_transform"][
                    "physical_four_gate_control_flow_parent_transform"
                ]
            ),
            "source_custody": dict(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY),
            "screen_horizon_checkpoint_count": 74,
            "horizon_checkpoint_attempted": attempted == 74,
            "horizon_reached_with_committed_checkpoint": (
                branch == "q74_success"
            ),
            "attempted_checkpoint_count": attempted,
            "completed_checkpoint_count": completed,
            "failure_checkpoint_included": failed,
            "selected_K_history": history,
            "records": records,
            "failure_record_sha256": digest(final) if failed else None,
            "last_committed_cumulative_drop_ticks": history and (
                records[completed - 1]["E_after_ticks"]
            ),
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
        raw["checkpoint_transform_sha256"] = digest(
            raw["checkpoint_transform"]
        )
        raw["selected_K_history_sha256"] = digest(history)
        raw["records_sha256"] = digest(records)
        resource = abort if abort is not None else final
        raw["observed_peak_single_expansion_terms"] = resource[
            "peak_live_terms_cumulative"
        ]
        raw["observed_term_gate_visits_including_terminal_attempt"] = (
            resource["term_gate_visits_cumulative"]
        )
        raw["observed_maximum_expansion_coefficient_tick_bits"] = (
            resource["maximum_expansion_coefficient_tick_bits"]
        )
        raw["observed_maximum_product_bits"] = resource[
            "maximum_product_bits"
        ]
        raw["observed_rounding_cumulative_scaled_ticks_squared"] = (
            resource["rounding_cumulative_scaled_ticks_squared"]
        )
        raw["child_boundary_committed"] = False
        raw["positive_artifact_generated"] = False
        self.assertEqual(frozenset(raw), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return raw

    def test_01_static_pins_caps_schema_and_parent(self):
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN_RAW), EXPECTED_SCREEN_SIZE)
        self.assertEqual(digest(SCREEN_RAW), EXPECTED_SCREEN_SHA256)
        self.assertLessEqual(len(SCREEN_RAW), SCREEN.MAX_SELF_SOURCE_BYTES)
        self.assertEqual(len(SCREEN.D_CANDIDATES), 37)
        self.assertNotIn(638_976, SCREEN.D_CANDIDATES)
        self.assertEqual(
            digest(list(SCREEN.D_CANDIDATES)),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            {
                "raw": len(SCREEN.EXPECTED_PARENT_RESULT_KEYS),
                "final": len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS),
                "success": len(SCREEN.SUCCESS_RECORD_KEYS),
                "failure": len(SCREEN.FAILURE_RECORD_KEYS),
                "row": len(SCREEN.CANDIDATE_RECORD_KEYS),
                "abort": len(SCREEN.RESOURCE_POLICY_ABORT_KEYS),
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
        parent = SCREEN.load_execution_parent(HERE)
        self.assertEqual(parent.EXTENDED_HORIZON, 72)
        self.assertEqual(tuple(parent.D_CANDIDATES), SCREEN.D_CANDIDATES)

    def test_02_q72_reference_is_exact_and_post_only(self):
        raw = (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(len(raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE)
        self.assertEqual(digest(raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256)
        self.assertEqual(raw, canonical_bytes(self.predecessor))
        canonical = self.route_reference["canonical_transcript"]
        self.assertFalse(canonical["loaded_before_replay"])
        self.assertTrue(canonical["loaded_after_full_replay_as_exact_reference"])
        self.assertFalse(canonical["propagation_input"])
        self.assertFalse(canonical["state_resume_input"])
        self.assertEqual(len(self.predecessor["records"]), 72)
        self.assertEqual(len(self.predecessor["selected_K_history"]), 72)

    def test_03_adapter_restores_every_patched_attribute(self):
        parent = types.ModuleType("fake_d72_parent")
        parent.EXTENDED_HORIZON = 72
        parent.validate_local_configuration = lambda: None
        parent.load_configured_v6_baseline = lambda repo: (
            object(), SCREEN.D_CANDIDATES
        )
        kernel = types.SimpleNamespace()
        parent.load_kernel_wrapper = lambda repo: (
            kernel,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            {"synthetic": True},
        )
        parent.load_route_reference = lambda repo, replay_completed: ({}, {})
        parent.configure_parent_execution = lambda control, config, wrapper: {
            "changed_fields": [
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
            ],
            "semantic_delta": {
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count": {
                    "before": 66,
                    "after": 74,
                }
            },
        }
        parent.execute_parent_fail_closed = lambda control, repo: {}
        parent.validate_and_relabel = lambda result, *args: result
        control = types.ModuleType("fake_control")
        control.run_four_gate = lambda: None
        def fake_verified(repo):
            config, _ = parent.load_configured_v6_baseline(repo)
            wrapped, _, _ = parent.load_kernel_wrapper(repo)
            parent.configure_parent_execution(control, config, wrapped)
            result = parent.execute_parent_fail_closed(control, repo)
            parent.load_route_reference(repo, replay_completed=True)
            return parent.validate_and_relabel(result)
        parent._run_verified = fake_verified
        names = (
            "EXTENDED_HORIZON",
            "validate_local_configuration",
            "load_configured_v6_baseline",
            "load_kernel_wrapper",
            "load_route_reference",
            "configure_parent_execution",
            "execute_parent_fail_closed",
            "validate_and_relabel",
        )
        originals = {name: getattr(parent, name) for name in names}
        old_executor = SCREEN.execute_control_parent_with_structured_abort
        try:
            SCREEN.execute_control_parent_with_structured_abort = (
                lambda execution_parent, control_parent, observed_kernel, repo: {}
            )
            result, context = SCREEN.execute_parent_replay(parent, HERE)
        finally:
            SCREEN.execute_control_parent_with_structured_abort = old_executor
        self.assertEqual(result, {})
        self.assertTrue(context["execution_parent_abort_adapter_installed"])
        self.assertTrue(context["execution_parent_route_loader_suppressed"])
        for name, value in originals.items():
            self.assertIs(getattr(parent, name), value)
        sentinel = RuntimeError("synthetic adapter failure")
        def failing_verified(repo):
            config, _ = parent.load_configured_v6_baseline(repo)
            wrapped, _, _ = parent.load_kernel_wrapper(repo)
            parent.configure_parent_execution(control, config, wrapped)
            raise sentinel
        parent._run_verified = failing_verified
        with self.assertRaises(RuntimeError) as caught:
            SCREEN.execute_parent_replay(parent, HERE)
        self.assertIs(caught.exception, sentinel)
        for name, value in originals.items():
            self.assertIs(getattr(parent, name), value)

    def test_04_all_five_terminal_branches(self):
        expected = {
            "q73_failure": "Q73_FAILURE_Q74_NOT_ATTEMPTED",
            "q73_abort": "Q73_RESOURCE_ABORT_Q74_NOT_ATTEMPTED",
            "q74_failure": "Q73_SUCCESS_Q74_FAILURE",
            "q74_abort": "Q73_SUCCESS_Q74_RESOURCE_ABORT",
            "q74_success": "Q73_AND_Q74_SUCCESS_HORIZON_REACHED",
        }
        for branch, terminal in expected.items():
            with self.subTest(branch=branch):
                handoff = SCREEN.validate_replay_handoff(
                    self.make_raw_result(branch), self.predecessor
                )
                self.assertEqual(handoff["terminal_branch"], terminal)

    def test_05_each_checkpoint_closes_three_abort_kinds(self):
        for branch, checkpoint in (("q73_abort", 73), ("q74_abort", 74)):
            for kind in (
                "final_live_terms",
                "transient_live_terms",
                "kernel_single_expansion_terms",
            ):
                with self.subTest(branch=branch, kind=kind):
                    result = self.make_raw_result(branch, kind)
                    handoff = SCREEN.validate_replay_handoff(
                        result, self.predecessor
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_checkpoint"],
                        checkpoint,
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_kind"], kind
                    )

    def test_06_prefix_record_and_abort_tamper_fail_closed(self):
        cases = []
        prefix = self.make_raw_result("q74_success")
        prefix["records"][0]["status"] = "tampered"
        prefix["records_sha256"] = digest(prefix["records"])
        cases.append(prefix)
        anchor = self.make_raw_result("q74_success")
        anchor["records"][72]["gate_batch_sha256"] = "0" * 64
        anchor["records_sha256"] = digest(anchor["records"])
        cases.append(anchor)
        abort = self.make_raw_result("q73_abort")
        abort["resource_policy_abort"]["abort_kind"] = "unknown"
        abort["resource_policy_abort_sha256"] = digest(
            abort["resource_policy_abort"]
        )
        cases.append(abort)
        for case in cases:
            with self.subTest():
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(case, self.predecessor)

    def test_07_known_dispatch_and_unknown_exception_identity(self):
        class KernelSchemaError(ValueError):
            pass
        kernel = types.SimpleNamespace(SchemaError=KernelSchemaError)
        execution_parent = types.SimpleNamespace(
            normalize_completed_parent_result=lambda value: value
        )
        control = types.SimpleNamespace()
        old_builder = SCREEN.build_resource_abort_parent_result
        try:
            SCREEN.build_resource_abort_parent_result = (
                lambda *args: {"structured": type(args[-1]).__name__}
            )
            for exception in (
                RuntimeError("design policy live-term cap exceeded"),
                RuntimeError(
                    "design policy transient live-term cap exceeded"
                ),
                KernelSchemaError(
                    "v2 single-expansion term cap exceeded"
                ),
            ):
                control._run_verified = lambda repo, mode, exc=exception: (
                    (_ for _ in ()).throw(exc)
                )
                result = SCREEN.execute_control_parent_with_structured_abort(
                    execution_parent, control, kernel, HERE
                )
                self.assertIn("structured", result)
            unknown = RuntimeError("unknown resource error")
            control._run_verified = lambda repo, mode: (
                (_ for _ in ()).throw(unknown)
            )
            with self.assertRaises(RuntimeError) as caught:
                SCREEN.execute_control_parent_with_structured_abort(
                    execution_parent, control, kernel, HERE
                )
            self.assertIs(caught.exception, unknown)
        finally:
            SCREEN.build_resource_abort_parent_result = old_builder

    def test_08_relabel_closes_11_components_and_10_custody(self):
        parent = SCREEN.load_execution_parent(HERE)
        _, baseline_d = parent.load_configured_v6_baseline(HERE)
        _, wrapper_sha, manifest = parent.load_kernel_wrapper(HERE)
        context = {
            "baseline_d": tuple(baseline_d),
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": manifest,
            "raw_control_flow_horizon_override": {
                "changed_fields": [
                    "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
                ],
                "semantic_delta": {
                    "MODE_CONFIG.double_occupancy.horizon_checkpoint_count": {
                        "before": 66,
                        "after": 74,
                    }
                },
            },
            "execution_parent_private_entrypoint_called": True,
            "q72_canonical_loaded_before_replay": False,
            "execution_parent_route_loader_suppressed": True,
            "execution_parent_abort_adapter_installed": True,
        }
        result = SCREEN.validate_and_relabel(
            self.make_raw_result("q74_success"),
            self.predecessor,
            self.route_reference,
            parent,
            context,
        )
        self.assertEqual(len(result), 96)
        self.assertEqual(len(result["screen_execution_components"]), 11)
        self.assertEqual(len(result["source_custody"]), 10)
        self.assertNotIn(
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            result["source_custody"],
        )

    def test_09_run_order_is_replay_then_post_reference(self):
        fresh = SCREEN.fresh_self_module()
        events = []
        parent = object()
        old_load = fresh.load_execution_parent
        old_execute = fresh.execute_parent_replay
        old_route = fresh.load_route_reference
        old_relabel = fresh.validate_and_relabel
        try:
            fresh.load_execution_parent = lambda repo: parent
            fresh.execute_parent_replay = lambda observed, repo: (
                events.append("replay") or ({}, {})
            )
            fresh.load_route_reference = lambda repo: (
                events.append("route") or ({}, {})
            )
            fresh.validate_and_relabel = lambda *args: {"ok": True}
            self.assertEqual(fresh._run_verified(HERE), {"ok": True})
            self.assertEqual(events, ["replay", "route"])
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
            fresh.load_execution_parent = old_load
            fresh.execute_parent_replay = old_execute
            fresh.load_route_reference = old_route
            fresh.validate_and_relabel = old_relabel

    def test_10_atomic_output_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaises(RuntimeError):
                SCREEN.write_atomic_bounded(
                    output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1)
                )
            self.assertEqual(output.read_bytes(), b"{}")

    def test_11_default_suite_never_calls_run(self):
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
            os.environ.get("FERMION_RUN_D655360_C37_Q74_REPLAY") != "1",
        )

    def test_12_canonical_exact_bytes_terminal_ledgers_and_closure(self):
        raw = self.canonical_raw
        canonical = self.canonical
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(digest(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertEqual(raw, canonical_bytes(canonical))
        self.assertEqual(
            frozenset(canonical), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(canonical), 96)

        expected_top = {
            "transcript_fingerprint": (
                "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
                "k655360_c37_l1048576_d1048576_q74_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "screen_horizon_checkpoint_count": 74,
            "attempted_checkpoint_count": 74,
            "completed_checkpoint_count": 74,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "last_committed_cumulative_drop_ticks": "2289190807152394",
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
            "positive_artifact_generated": False,
            "child_boundary_committed": False,
            "observed_peak_single_expansion_terms": 799_279,
            "observed_term_gate_visits_including_terminal_attempt": 98_440_976,
            "observed_maximum_expansion_coefficient_tick_bits": 63,
            "observed_maximum_product_bits": 120,
            "observed_rounding_cumulative_scaled_ticks_squared": (
                "139630115477628218221266668"
            ),
        }
        for field, value in expected_top.items():
            self.assertEqual(canonical[field], value, field)
        self.assertEqual(
            canonical["candidate_K_values"], list(SCREEN.D_CANDIDATES)
        )
        self.assertEqual(
            canonical["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 37},
        )
        self.assertEqual(
            canonical["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

        records = canonical["records"]
        history = canonical["selected_K_history"]
        self.assertEqual(len(records), 74)
        self.assertEqual(len(history), 74)
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
        self.assertEqual(records[:72], self.predecessor["records"])
        self.assertEqual(
            history[:72], self.predecessor["selected_K_history"]
        )
        self.assertEqual(history[72:], [SCREEN.K655360, SCREEN.K655360])
        self.assertEqual(
            digest(records[:72]),
            "dae3378038fbe6b8514782b5f177adeab679b0255a4180a2b1c6dd11f5a6b06a",
        )
        self.assertEqual(
            digest(history[:72]),
            "a9f584aa28bc4cfff053d804e743f05c73a966b4e6ef53d43fd38bac2136245a",
        )
        self.assertEqual(
            digest(records[71]),
            "326b47e8c6f292f3938585676bcda2cf27a4e33fd815dec727b9c9357cb4578c",
        )
        self.assertEqual(
            digest(records[71]["candidate_records"]),
            "5c95784865298c8aff971a5245497d8503ebcfd7edefeac13d3f901f47a12550",
        )

        prefix_rows = [
            row for record in records[:72]
            for row in record["candidate_records"]
        ]
        all_rows = [
            row for record in records for row in record["candidate_records"]
        ]
        self.assertEqual(len(prefix_rows), 72 * 37)
        self.assertEqual(len(all_rows), 74 * 37)
        self.assertEqual(
            digest(prefix_rows),
            EXPECTED_CANONICAL["q1_through_q72_candidate_rows_sha256"],
        )
        self.assertEqual(
            digest(all_rows),
            EXPECTED_CANONICAL["all_candidate_rows_sha256"],
        )

        expected_success_fields = {
            73: {
                "E_after_ticks": "2289146735930407",
                "E_before_ticks": "2289046235933480",
                "batch_in_stage": 16,
                "budget_prefix_cap_ticks": "2289172499803748",
                "checkpoint_index_zero_based": 72,
                "checkpoint_number_one_based": 73,
                "gate_batch_sha256": (
                    "38a96cc5ddee7486052b93b1fcaf8e8582455fb728b0f82bb7574b1c34637df0"
                ),
                "gate_occurrence_first_zero_based": 288,
                "gate_occurrence_last_zero_based": 291,
                "input_expansion_count": 655_360,
                "input_expansion_sha256": (
                    "fae098c2e1b746413885371ec4b6c1cfce32f8948c6421a4118aee1707c43cc1"
                ),
                "maximum_dropped_abs_upper_ticks": "3667375",
                "maximum_expansion_coefficient_tick_bits": 63,
                "maximum_product_bits": 120,
                "minimum_retained_abs_upper_ticks": "3668234",
                "peak_live_terms_cumulative": 799_279,
                "peak_live_terms_this_checkpoint": 794_529,
                "prefix_slack_before_selection_ticks": "126263870268",
                "pretruncation_expansion_count": 794_529,
                "pretruncation_expansion_sha256": (
                    "88362a79131ca4b228c7d174b4bbfdab8ac06d938ce389d2fc6b9ba32b6ceb11"
                ),
                "ranked_suffix_sha256": (
                    "8aed774d428f1ad456259d62f738b57f4675bea7d4063c6a43d05ee2a0653c89"
                ),
                "removed_491520_counterfactual": {
                    "E_after_if_selected_ticks": "2292779755222927",
                    "actual_selected_K": 655_360,
                    "configured_K": 491_520,
                    "drop_ticks": "3733519289447",
                    "dropped_term_count": 303_009,
                    "effective_retained_count": 491_520,
                    "feasible_under_current_prefix_cap": False,
                    "would_be_selected_if_inserted": False,
                    "would_precede_selected": False,
                },
                "retained_expansion_count": 655_360,
                "retained_expansion_sha256": (
                    "240667edd279b5f67af2bccf0906fd231159f0cd22e5559d9306b99f326a53d9"
                ),
                "rounding_cumulative_scaled_ticks_squared": (
                    "136290628976676318744951606"
                ),
                "rounding_increment_scaled_ticks_squared": (
                    "5961583753587817268088118"
                ),
                "selected_K": 655_360,
                "selected_candidate_index": 36,
                "selected_drop_ticks": "100499996927",
                "selected_dropped_term_count": 139_169,
                "selected_dropped_terms_sha256": (
                    "7365da465c89f15f326e06596f242101056a867ba22cb0fcf12c50bd70cb69d4"
                ),
                "selected_effective_retained_count": 655_360,
                "stage_group": "HU",
                "stage_index": 2,
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "term_gate_visits_cumulative": 95_695_512,
                "term_gate_visits_increment": 2_826_079,
            },
            74: {
                "E_after_ticks": "2289190807152394",
                "E_before_ticks": "2289146735930407",
                "batch_in_stage": 17,
                "budget_prefix_cap_ticks": "2289255001793681",
                "checkpoint_index_zero_based": 73,
                "checkpoint_number_one_based": 74,
                "gate_batch_sha256": (
                    "20a8ce48c96ca7a148445df3401608ed7b5186c6e35ba43642b84f97435dbdf2"
                ),
                "gate_occurrence_first_zero_based": 292,
                "gate_occurrence_last_zero_based": 295,
                "input_expansion_count": 655_360,
                "input_expansion_sha256": (
                    "240667edd279b5f67af2bccf0906fd231159f0cd22e5559d9306b99f326a53d9"
                ),
                "maximum_dropped_abs_upper_ticks": "4009413",
                "maximum_expansion_coefficient_tick_bits": 63,
                "maximum_product_bits": 120,
                "minimum_retained_abs_upper_ticks": "4009413",
                "peak_live_terms_cumulative": 799_279,
                "peak_live_terms_this_checkpoint": 726_450,
                "prefix_slack_before_selection_ticks": "108265863274",
                "pretruncation_expansion_count": 726_450,
                "pretruncation_expansion_sha256": (
                    "8f4096ea3559c6b513eb21c717065018409af9b8c6989b8ae302a2a7f10eb856"
                ),
                "ranked_suffix_sha256": (
                    "6cc2675ff08c13ff0ec8a24dfac71de78df2ed42ca7740c3fe5652d16445c73d"
                ),
                "removed_491520_counterfactual": {
                    "E_after_if_selected_ticks": "2292793752053693",
                    "actual_selected_K": 655_360,
                    "configured_K": 491_520,
                    "drop_ticks": "3647016123286",
                    "dropped_term_count": 234_930,
                    "effective_retained_count": 491_520,
                    "feasible_under_current_prefix_cap": False,
                    "would_be_selected_if_inserted": False,
                    "would_precede_selected": False,
                },
                "retained_expansion_count": 655_360,
                "retained_expansion_sha256": (
                    "99fb342059ee6627a8b51b4230945237bdfdcaa7f65a20dab6898e8af0ed48eb"
                ),
                "rounding_cumulative_scaled_ticks_squared": (
                    "139630115477628218221266668"
                ),
                "rounding_increment_scaled_ticks_squared": (
                    "3339486500951899476315062"
                ),
                "selected_K": 655_360,
                "selected_candidate_index": 36,
                "selected_drop_ticks": "44071221987",
                "selected_dropped_term_count": 71_090,
                "selected_dropped_terms_sha256": (
                    "fa3c263702223a1d2a998376188fdd40062295733b6d7781ffb49083c7176cb7"
                ),
                "selected_effective_retained_count": 655_360,
                "stage_group": "HU",
                "stage_index": 2,
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "term_gate_visits_cumulative": 98_440_976,
                "term_gate_visits_increment": 2_745_464,
            },
        }
        expected_record_digests = {
            73: EXPECTED_CANONICAL["q73_record_sha256"],
            74: EXPECTED_CANONICAL["q74_record_sha256"],
        }
        expected_row_digests = {
            73: EXPECTED_CANONICAL["q73_rows_sha256"],
            74: EXPECTED_CANONICAL["q74_rows_sha256"],
        }
        expected_counterfactual_digests = {
            73: EXPECTED_CANONICAL["q73_counterfactual_sha256"],
            74: EXPECTED_CANONICAL["q74_counterfactual_sha256"],
        }
        for checkpoint in (73, 74):
            record = records[checkpoint - 1]
            rows = record["candidate_records"]
            with self.subTest(checkpoint=checkpoint):
                self.assertEqual(frozenset(record), SCREEN.SUCCESS_RECORD_KEYS)
                self.assertEqual(
                    {key: value for key, value in record.items()
                     if key != "candidate_records"},
                    expected_success_fields[checkpoint],
                )
                self.assertEqual(
                    digest(record), expected_record_digests[checkpoint]
                )
                self.assertEqual(len(rows), 37)
                self.assertEqual(digest(rows), expected_row_digests[checkpoint])
                self.assertEqual(
                    digest(record["removed_491520_counterfactual"]),
                    expected_counterfactual_digests[checkpoint],
                )
                for index, (row, configured_K) in enumerate(zip(
                    rows, SCREEN.D_CANDIDATES
                )):
                    self.assertEqual(
                        frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                    )
                    self.assertEqual(row["candidate_index"], index)
                    self.assertEqual(row["configured_K"], configured_K)
                    effective = min(
                        configured_K,
                        record["pretruncation_expansion_count"],
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
                        row["feasible_under_current_prefix_cap"], index == 36
                    )
                selected = rows[36]
                self.assertEqual(record["selected_candidate_index"], 36)
                self.assertEqual(record["selected_K"], selected["configured_K"])
                self.assertEqual(
                    record["selected_effective_retained_count"],
                    selected["effective_retained_count"],
                )
                self.assertEqual(
                    record["selected_dropped_term_count"],
                    selected["dropped_term_count"],
                )
                self.assertEqual(
                    record["selected_drop_ticks"], selected["drop_ticks"]
                )
                self.assertEqual(
                    record["E_after_ticks"],
                    selected["E_after_if_selected_ticks"],
                )

        self.assertEqual(
            records[72]["E_before_ticks"], records[71]["E_after_ticks"]
        )
        self.assertEqual(
            records[72]["input_expansion_sha256"],
            records[71]["retained_expansion_sha256"],
        )
        self.assertEqual(
            records[73]["E_before_ticks"], records[72]["E_after_ticks"]
        )
        self.assertEqual(
            records[73]["input_expansion_sha256"],
            records[72]["retained_expansion_sha256"],
        )

        nested_digests = {
            "configuration_reference": "configuration_reference_sha256",
            "configuration_override": "configuration_override_sha256",
            "kernel_capability_override": "kernel_capability_override_sha256",
            "parent_horizon_override": "parent_horizon_override_sha256",
            "route_predecessor_reference": (
                "route_predecessor_reference_sha256"
            ),
            "checkpoint_transform": "checkpoint_transform_sha256",
        }
        for field, digest_field in nested_digests.items():
            with self.subTest(nested=field):
                expected = EXPECTED_CANONICAL[digest_field]
                self.assertEqual(canonical[digest_field], expected)
                self.assertEqual(digest(canonical[field]), expected)
        self.assertFalse(
            canonical["checkpoint_transform"][
                "q73_and_q74_outcomes_precommitted"
            ]
        )
        self.assertFalse(
            canonical["route_predecessor_reference"][
                "q73_q74_K638976_threshold_or_drop_asserted"
            ]
        )

        handoff = canonical["predecessor_handoff_validation"]
        expected_handoff = {
            "validation_id": (
                "D_k655360_c37_l1048576_d1048576_q74_same_cap_handoff_v1"
            ),
            "q1_through_q72_records_exact": True,
            "q1_through_q72_all_37_candidate_rows_exact": True,
            "q1_through_q72_selected_history_exact": True,
            "q72_records_sha256": (
                "dae3378038fbe6b8514782b5f177adeab679b0255a4180a2b1c6dd11f5a6b06a"
            ),
            "q72_selected_history_sha256": (
                "a9f584aa28bc4cfff053d804e743f05c73a966b4e6ef53d43fd38bac2136245a"
            ),
            "q72_terminal_record_sha256": (
                "326b47e8c6f292f3938585676bcda2cf27a4e33fd815dec727b9c9357cb4578c"
            ),
            "q72_terminal_candidate_rows_sha256": (
                "5c95784865298c8aff971a5245497d8503ebcfd7edefeac13d3f901f47a12550"
            ),
            "q72_excluded_K638976_evidence_historical_only": True,
            "q73_q74_K638976_threshold_or_drop_asserted": False,
            "q73_input_retained_count": 655_360,
            "q73_input_retained_sha256": (
                "fae098c2e1b746413885371ec4b6c1cfce32f8948c6421a4118aee1707c43cc1"
            ),
            "q73_input_E_before_ticks": "2289046235933480",
            "q73_prefix_cap_ticks": "2289172499803748",
            "q74_prefix_cap_ticks_if_attempted": "2289255001793681",
            "legal_terminal_branches": [
                "Q73_FAILURE_Q74_NOT_ATTEMPTED",
                "Q73_RESOURCE_ABORT_Q74_NOT_ATTEMPTED",
                "Q73_SUCCESS_Q74_FAILURE",
                "Q73_SUCCESS_Q74_RESOURCE_ABORT",
                "Q73_AND_Q74_SUCCESS_HORIZON_REACHED",
            ],
            "terminal_branch": "Q73_AND_Q74_SUCCESS_HORIZON_REACHED",
            "resource_policy_abort_structured": False,
            "resource_policy_abort_checkpoint": None,
            "resource_policy_abort_kind": None,
            "resource_policy_abort_sha256": None,
            "q74_checkpoint_record_constructed": True,
            "q73_and_q74_outcomes_precommitted": False,
        }
        self.assertEqual(handoff, expected_handoff)
        self.assertEqual(
            canonical["predecessor_handoff_validation_sha256"],
            EXPECTED_CANONICAL["handoff_sha256"],
        )
        self.assertEqual(
            digest(handoff), EXPECTED_CANONICAL["handoff_sha256"]
        )
        self.assertEqual(
            handoff["terminal_branch"],
            "Q73_AND_Q74_SUCCESS_HORIZON_REACHED",
        )

        components = canonical["screen_execution_components"]
        expected_components = SCREEN.execution_components(
            list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS),
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(components, expected_components)
        self.assertEqual(len(components), 11)
        self.assertEqual(
            canonical["screen_execution_components_sha256"],
            EXPECTED_CANONICAL["components_sha256"],
        )
        self.assertEqual(
            digest(components), EXPECTED_CANONICAL["components_sha256"]
        )
        custody = canonical["source_custody"]
        self.assertEqual(
            custody,
            SCREEN.expected_final_source_custody(EXPECTED_SCREEN_SHA256),
        )
        self.assertEqual(len(custody), 10)
        self.assertEqual(
            digest(custody), EXPECTED_CANONICAL["custody_sha256"]
        )
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
        os.environ.get("FERMION_RUN_D655360_C37_Q74_REPLAY") == "1",
        "full q1--q74 replay is explicit opt-in only",
    )
    def test_13_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertEqual(result, self.canonical)
        self.assertEqual(canonical_bytes(result), self.canonical_raw)


if __name__ == "__main__":
    unittest.main()
