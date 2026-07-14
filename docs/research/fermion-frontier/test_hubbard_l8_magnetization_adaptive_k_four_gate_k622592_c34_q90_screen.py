#!/usr/bin/env python3
"""Static, synthetic, and opt-in tests for same-cap M q88 -> q90."""

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
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q90_screen.py"
)
EXPECTED_SCREEN_SHA256 = "f880e851bb16df5e659d7c0e6aa237d1836b17b4ad010d5676557ade2ba9140a"
EXPECTED_SCREEN_SIZE = 89_527
CANONICAL_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q90_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 842_060,
    "file_sha256": (
        "d30359d9dd38c8e3a1461a0c7048645e35f478fa66920711871b3dc1c44bbd49"
    ),
    "records_sha256": (
        "8978329b712168dce39991af25f6903deaf69c45f236521bb0e08e74f3d8741f"
    ),
    "history_sha256": (
        "c6755c7655d6b2ff37da7b1a8ac8c16cfc4295ef9ad0b687ddaa3dcd3c785d53"
    ),
    "q89_record_sha256": (
        "75b7faa4353f7b7ab2183e8fe7f056c07fcb9b68329ab93f45ad95a475e4d3ea"
    ),
    "q89_rows_sha256": (
        "71b18b40417956ffbafb9a7976deb84d85327668d00ebb4adc4efc0f32c7506c"
    ),
    "q90_record_sha256": (
        "74b3d8201861663339f5465ae8bbfdb0fcb80433524f8f318aae591045665a14"
    ),
    "q90_rows_sha256": (
        "9dcdefdcc4e7c80d2a2ff9a5471aebcd50e85b731fff98f6b204a8930c7b7d63"
    ),
    "all_candidate_rows_sha256": (
        "8fa83aa57724f8fa80211d393d570fc5d38e79fc671d37c70ee4e3c5829f224c"
    ),
    "components_sha256": (
        "64bb47fe62885a395d132e11230a879fcc76c2644af372995def5a149d582971"
    ),
    "custody_sha256": (
        "1e4b90be77ae9004bdbbb325cf7f4e3f3f8334b6ca91f5e14073eaf8015ae88c"
    ),
    "handoff_sha256": (
        "269328e4be6d39e66eef62885d33a89ec8ea453751471617b38b268f40072eed"
    ),
}


def canonical_bytes(value):
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True,
        separators=(",", ":"), sort_keys=True,
    ).encode("ascii")


def digest(value):
    payload = value if type(value) is bytes else canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


SCREEN_PATH = HERE / SCREEN_NAME
SCREEN_RAW = SCREEN_PATH.read_bytes()
SCREEN = types.ModuleType("tested_m_k622592_c34_q90_screen")
SCREEN.__file__ = str(SCREEN_PATH)
SCREEN.__package__ = ""
SCREEN.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = SCREEN_RAW
exec(compile(SCREEN_RAW, str(SCREEN_PATH), "exec"), SCREEN.__dict__)


class MQ90ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = SCREEN.load_execution_parent(HERE)
        cls.predecessor, cls.route_reference = SCREEN.load_route_reference(
            HERE, cls.parent
        )
        cls.canonical_raw = (HERE / CANONICAL_NAME).read_bytes()
        cls.canonical = json.loads(cls.canonical_raw)

    def make_record(self, previous, checkpoint, status):
        anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
        pre_count = 700_000 if checkpoint == 89 else 90_000
        E_before = int(previous["E_after_ticks"])
        prefix = int(anchor["budget_prefix_cap_ticks"])
        slack = prefix - E_before
        rows = []
        for index, configured_K in enumerate(SCREEN.M_CANDIDATES):
            effective = min(configured_K, pre_count)
            if status == "success":
                drop = 3_400 - 100 * index
            else:
                drop = slack + 3_400 - 100 * index
            rows.append({
                "candidate_index": index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(E_before + drop),
                "feasible_under_current_prefix_cap": drop <= slack,
            })
        record = {
            "E_before_ticks": str(E_before),
            "batch_in_stage": anchor["batch_in_stage"],
            "budget_prefix_cap_ticks": anchor["budget_prefix_cap_ticks"],
            "candidate_records": rows,
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            "gate_batch_sha256": anchor["gate_batch_sha256"],
            "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
            "gate_occurrence_last_zero_based": 4 * (checkpoint - 1) + 3,
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "maximum_expansion_coefficient_tick_bits": 57,
            "maximum_product_bits": 121,
            "peak_live_terms_cumulative": max(
                previous["peak_live_terms_cumulative"], pre_count
            ),
            "peak_live_terms_this_checkpoint": pre_count,
            "prefix_slack_before_selection_ticks": str(slack),
            "pretruncation_expansion_count": pre_count,
            "pretruncation_expansion_sha256": digest([checkpoint, "pre"]),
            "ranked_suffix_sha256": digest([checkpoint, "ranked"]),
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 100
            ),
            "rounding_increment_scaled_ticks_squared": "100",
            "selected_K": None,
            "selected_candidate_index": None,
            "stage_group": anchor["stage_group"],
            "stage_index": anchor["stage_index"],
            "status": (
                "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
                if status == "success"
                else "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"] + 1_000
            ),
            "term_gate_visits_increment": 1_000,
        }
        if status == "success":
            selected = rows[0]
            record.update({
                "selected_candidate_index": 0,
                "selected_K": SCREEN.M_CANDIDATES[0],
                "selected_effective_retained_count": selected[
                    "effective_retained_count"
                ],
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": digest([checkpoint, "dropped"]),
                "retained_expansion_count": selected[
                    "effective_retained_count"
                ],
                "retained_expansion_sha256": digest([checkpoint, "retained"]),
                "minimum_retained_abs_upper_ticks": "200",
                "maximum_dropped_abs_upper_ticks": "100",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
        else:
            record.update({
                "minimum_effective_K_to_meet_prefix": SCREEN.K622592 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "100",
            })
        return record

    def make_abort(self, previous, checkpoint, kind):
        anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
        kinds = {
            "final_live_terms": {
                "abort_frame_local_schema_id": "helper_final_live_terms_v1",
                "exception_type": "RuntimeError",
                "exception_message": "design policy live-term cap exceeded",
                "exception_source_role": "exact_parent_helper",
                "exception_chained_from_exact_parent_helper": True,
                "pretruncation_expansion_count": 786_433,
                "observed_term_count": 786_433,
                "enforced_term_cap": 786_432,
                "policy_relation": (
                    "pretruncation_expansion_count>"
                    "policy_max_single_expansion_terms"
                ),
                "gate_batch_propagation_completed": True,
                "policy_cap_check_reached": True,
                "kernel_cap_violation_triggered": False,
                "live_expansion_snapshot_available": True,
            },
            "transient_live_terms": {
                "abort_frame_local_schema_id": "helper_transient_live_terms_v1",
                "exception_type": "RuntimeError",
                "exception_message": (
                    "design policy transient live-term cap exceeded"
                ),
                "exception_source_role": "exact_parent_helper",
                "exception_chained_from_exact_parent_helper": True,
                "pretruncation_expansion_count": 786_432,
                "observed_term_count": 786_433,
                "enforced_term_cap": 786_432,
                "policy_relation": (
                    "peak_live_terms_this_checkpoint>"
                    "policy_max_single_expansion_terms>="
                    "pretruncation_expansion_count"
                ),
                "gate_batch_propagation_completed": True,
                "policy_cap_check_reached": True,
                "kernel_cap_violation_triggered": False,
                "live_expansion_snapshot_available": True,
            },
            "kernel_single_expansion_terms": {
                "abort_frame_local_schema_id": (
                    "kernel_observe_count_before_pre_count_assignment_v1"
                ),
                "exception_type": "SchemaError",
                "exception_message": "v2 single-expansion term cap exceeded",
                "exception_source_role": "exact_wrapped_v2_kernel",
                "exception_chained_from_exact_parent_helper": False,
                "pretruncation_expansion_count": None,
                "observed_term_count": 1_048_577,
                "enforced_term_cap": 1_048_576,
                "policy_relation": (
                    "observed_term_count>kernel_max_single_expansion_terms_"
                    "before_pretruncation_assignment"
                ),
                "gate_batch_propagation_completed": False,
                "policy_cap_check_reached": False,
                "kernel_cap_violation_triggered": True,
                "live_expansion_snapshot_available": False,
            },
        }
        values = kinds[kind]
        observed = values["observed_term_count"]
        abort = {
            "schema_version": 1,
            "abort_id": "M_k622592_c34_q90_policy_resource_abort_v1",
            "abort_kind": kind,
            "abort_frame_local_schema_id": values[
                "abort_frame_local_schema_id"
            ],
            "exception_type": values["exception_type"],
            "exception_message": values["exception_message"],
            "exception_args": [values["exception_message"]],
            "exception_source_role": values["exception_source_role"],
            "exception_chained_from_exact_parent_helper": values[
                "exception_chained_from_exact_parent_helper"
            ],
            "control_flow_parent_source_sha256": (
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
            "gate_occurrence_last_zero_based": 4 * (checkpoint - 1) + 3,
            "gate_batch_sha256": anchor["gate_batch_sha256"],
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "pretruncation_expansion_count": values[
                "pretruncation_expansion_count"
            ],
            "observed_term_count": observed,
            "policy_max_single_expansion_terms": 786_432,
            "kernel_max_single_expansion_terms": 1_048_576,
            "enforced_term_cap": values["enforced_term_cap"],
            "observed_excess_terms": observed - values["enforced_term_cap"],
            "policy_relation": values["policy_relation"],
            "gate_batch_propagation_started": True,
            "gate_batch_propagation_completed": values[
                "gate_batch_propagation_completed"
            ],
            "policy_cap_check_reached": values["policy_cap_check_reached"],
            "kernel_cap_violation_triggered": values[
                "kernel_cap_violation_triggered"
            ],
            "live_expansion_snapshot_available": values[
                "live_expansion_snapshot_available"
            ],
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
            "term_gate_visits_increment": 1_000,
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"] + 1_000
            ),
            "rounding_increment_scaled_ticks_squared": "100",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 100
            ),
            "maximum_expansion_coefficient_tick_bits": 57,
            "maximum_product_bits": 121,
        }
        self.assertEqual(frozenset(abort), SCREEN.RESOURCE_POLICY_ABORT_KEYS)
        return abort

    def make_raw_result(self, branch, abort_kind="kernel_single_expansion_terms"):
        raw = {
            key: copy.deepcopy(self.predecessor[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        raw["screen_horizon_checkpoint_count"] = 90
        raw["screen_execution_components"] = copy.deepcopy(
            list(self.parent.EXPECTED_PARENT_EXECUTION_COMPONENTS)
        )
        raw["screen_execution_components_sha256"] = digest(
            raw["screen_execution_components"]
        )
        raw["source_custody"] = copy.deepcopy(
            dict(self.parent.EXPECTED_PARENT_SOURCE_CUSTODY)
        )
        records = copy.deepcopy(self.predecessor["records"])
        history = list(self.predecessor["selected_K_history"])
        q88 = records[-1]
        failure = abort = None
        if branch == "q89_failure":
            failure = self.make_record(q88, 89, "failure")
            records.append(failure)
        elif branch == "q89_abort":
            abort = self.make_abort(q88, 89, abort_kind)
        else:
            q89 = self.make_record(q88, 89, "success")
            records.append(q89)
            history.append(q89["selected_K"])
            if branch == "q90_failure":
                failure = self.make_record(q89, 90, "failure")
                records.append(failure)
            elif branch == "q90_abort":
                abort = self.make_abort(q89, 90, abort_kind)
            elif branch == "q90_success":
                q90 = self.make_record(q89, 90, "success")
                records.append(q90)
                history.append(q90["selected_K"])
            else:
                raise AssertionError(branch)
        if branch in ("q89_failure", "q89_abort"):
            attempted, completed, horizon_attempted, reached = 89, 88, False, False
            final_success = q88
        elif branch in ("q90_failure", "q90_abort"):
            attempted, completed, horizon_attempted, reached = 90, 89, True, False
            final_success = records[88]
        else:
            attempted, completed, horizon_attempted, reached = 90, 90, True, True
            final_success = records[-1]
        terminal = (
            "DIAGNOSTIC_RESOURCE_POLICY_ABORT" if abort is not None
            else "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            if failure is not None else "DIAGNOSTIC_HORIZON_REACHED"
        )
        resource = abort if abort is not None else records[-1]
        raw.update({
            "records": records,
            "records_sha256": digest(records),
            "selected_K_history": history,
            "selected_K_history_sha256": digest(history),
            "attempted_checkpoint_count": attempted,
            "completed_checkpoint_count": completed,
            "horizon_checkpoint_attempted": horizon_attempted,
            "horizon_reached_with_committed_checkpoint": reached,
            "screen_terminal_condition": terminal,
            "failure_checkpoint_included": failure is not None,
            "failure_record_sha256": digest(failure) if failure is not None else None,
            "last_committed_cumulative_drop_ticks": final_success["E_after_ticks"],
            "resource_policy_abort": abort,
            "resource_policy_abort_sha256": digest(abort) if abort is not None else None,
            "observed_peak_single_expansion_terms": resource[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": resource[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": resource[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": resource["maximum_product_bits"],
            "observed_rounding_cumulative_scaled_ticks_squared": resource[
                "rounding_cumulative_scaled_ticks_squared"
            ],
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "root_globals_unchanged": True,
        })
        self.assertEqual(frozenset(raw), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return raw

    def make_context(self):
        _, baseline_m = self.parent.load_configured_v6_baseline(HERE)
        _, wrapper_sha, manifest = self.parent.load_kernel_wrapper(HERE)
        return {
            "execution_parent_private_entrypoint_called": True,
            "raw_replay_completed": True,
            "q88_internal_c33_loader_suppressed": True,
            "q88_internal_relabel_suppressed": True,
            "execution_parent_abort_adapter_installed": True,
            "baseline_m": tuple(baseline_m),
            "kernel": object(),
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": manifest,
            "raw_control_flow_horizon_override": {
                "semantic_delta": {
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                        "before": 80, "after": 90,
                    }
                }
            },
        }

    def test_01_exact_source_parent_and_closed_schemas(self):
        self.assertEqual(len(SCREEN_RAW), EXPECTED_SCREEN_SIZE)
        self.assertEqual(digest(SCREEN_RAW), EXPECTED_SCREEN_SHA256)
        self.assertLessEqual(len(SCREEN_RAW), SCREEN.MAX_SELF_SOURCE_BYTES)
        self.assertEqual(len(SCREEN.EXPECTED_PARENT_RESULT_KEYS), 67)
        self.assertEqual(len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS), 96)
        self.assertEqual(len(SCREEN.RECORD_SUCCESS_RECORD_KEYS), 37)
        self.assertEqual(len(SCREEN.RECORD_FAILURE_RECORD_KEYS), 31)
        self.assertEqual(len(SCREEN.CANDIDATE_RECORD_KEYS), 7)
        self.assertEqual(len(SCREEN.RESOURCE_POLICY_ABORT_KEYS), 50)
        SCREEN.validate_local_configuration()
        parent_raw = (HERE / SCREEN.EXECUTION_PARENT_NAME).read_bytes()
        self.assertEqual(len(parent_raw), 78_218)
        self.assertEqual(
            digest(parent_raw), SCREEN.EXPECTED_EXECUTION_PARENT_SHA256
        )
        canonical_path = HERE / CANONICAL_NAME
        if canonical_path.exists():
            canonical_raw = canonical_path.read_bytes()
            self.assertLessEqual(len(canonical_raw), SCREEN.MAX_OUTPUT_BYTES)
            self.assertEqual(canonical_raw, canonical_bytes(json.loads(canonical_raw)))

    def test_02_q88_post_only_reference_is_exact(self):
        predecessor = self.predecessor
        self.assertEqual(len(predecessor["records"]), 88)
        self.assertEqual(len(predecessor["selected_K_history"]), 88)
        self.assertEqual(
            digest(predecessor["records"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        )
        self.assertEqual(
            digest(predecessor["selected_K_history"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        )
        q88 = predecessor["records"][-1]
        self.assertEqual(digest(q88), SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q88_RECORD_SHA256)
        self.assertEqual(
            digest(q88["candidate_records"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q88_ROWS_SHA256,
        )
        canonical = self.route_reference["canonical_transcript"]
        self.assertFalse(canonical["loaded_before_replay"])
        self.assertTrue(canonical["loaded_after_full_replay_as_exact_reference"])
        for key in (
            "compiled", "executed", "propagation_input", "state_resume_input",
            "execution_source_layer",
        ):
            self.assertFalse(canonical[key])

    def test_03_exact_geometry_prefix_and_unchanged_caps(self):
        E3 = 1_691_496_669_588_296
        bound = 4_611_686_018_427_387
        denominator = 27_936
        expected = {
            89: (352, 355, 1_700_799_964_693_059),
            90: (356, 359, 1_700_904_496_098_731),
        }
        for checkpoint, (first, last, prefix) in expected.items():
            anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
            self.assertEqual(first, 4 * (checkpoint - 1))
            self.assertEqual(last, first + 3)
            self.assertEqual(
                prefix,
                E3 + checkpoint * (bound - E3) // denominator,
            )
            self.assertEqual(str(prefix), anchor["budget_prefix_cap_ticks"])
            self.assertEqual(anchor["stage_index"], 2)
            self.assertEqual(anchor["stage_group"], "HU")
        self.assertEqual(
            digest(list(SCREEN.M_CANDIDATES)), SCREEN.EXPECTED_CANDIDATE_SHA256
        )
        self.assertEqual(
            self.predecessor["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 34},
        )
        self.assertEqual(
            self.predecessor["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

    def test_04_five_terminal_branches_and_exact_counts(self):
        expected = {
            "q89_failure": (
                "Q89_FAILURE_Q90_NOT_ATTEMPTED", 89, 88, 3_026
            ),
            "q89_abort": (
                "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED", 88, 88, 2_992
            ),
            "q90_failure": (
                "Q89_SUCCESS_Q90_FAILURE", 90, 89, 3_060
            ),
            "q90_abort": (
                "Q89_SUCCESS_Q90_RESOURCE_ABORT", 89, 89, 3_026
            ),
            "q90_success": (
                "Q89_AND_Q90_SUCCESS_HORIZON_REACHED", 90, 90, 3_060
            ),
        }
        for synthetic, values in expected.items():
            with self.subTest(synthetic=synthetic):
                raw = self.make_raw_result(synthetic)
                handoff = SCREEN.validate_replay_handoff(raw, self.predecessor)
                self.assertEqual(handoff["terminal_branch"], values[0])
                self.assertEqual(handoff["record_count"], values[1])
                self.assertEqual(handoff["selected_history_count"], values[2])
                self.assertEqual(handoff["candidate_row_count"], values[3])
                self.assertTrue(handoff["q1_through_q88_records_exact"])
                self.assertTrue(handoff["q1_through_q88_all_34_candidate_rows_exact"])

    def test_05_each_checkpoint_closes_three_abort_kinds(self):
        for branch, checkpoint in (("q89_abort", 89), ("q90_abort", 90)):
            for kind in (
                "final_live_terms", "transient_live_terms",
                "kernel_single_expansion_terms",
            ):
                with self.subTest(branch=branch, kind=kind):
                    raw = self.make_raw_result(branch, kind)
                    handoff = SCREEN.validate_replay_handoff(
                        raw, self.predecessor
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_checkpoint"], checkpoint
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_kind"], kind
                    )

    def test_06_known_dispatch_and_unknown_exception_identity(self):
        class KernelSchemaError(ValueError):
            pass

        kernel = types.SimpleNamespace(SchemaError=KernelSchemaError)
        execution_parent = types.SimpleNamespace(
            normalize_completed_parent_result=lambda value: value
        )
        control = types.SimpleNamespace()
        original = SCREEN.build_resource_abort_parent_result
        try:
            SCREEN.build_resource_abort_parent_result = (
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
            SCREEN.build_resource_abort_parent_result = original

    def test_07_prefix_anchor_row_abort_and_digest_tamper_fail_closed(self):
        cases = []
        prefix = self.make_raw_result("q90_success")
        prefix["records"][0]["status"] = "tampered"
        prefix["records_sha256"] = digest(prefix["records"])
        cases.append(prefix)
        anchor = self.make_raw_result("q90_success")
        anchor["records"][88]["gate_batch_sha256"] = "0" * 64
        anchor["records_sha256"] = digest(anchor["records"])
        cases.append(anchor)
        row = self.make_raw_result("q90_success")
        row["records"][88]["candidate_records"][0]["configured_K"] += 1
        row["records_sha256"] = digest(row["records"])
        cases.append(row)
        abort = self.make_raw_result("q89_abort")
        abort["resource_policy_abort"]["abort_kind"] = "unknown"
        abort["resource_policy_abort_sha256"] = digest(
            abort["resource_policy_abort"]
        )
        cases.append(abort)
        nested = self.make_raw_result("q90_success")
        nested["configuration_reference"]["role"] = "tampered"
        cases.append(nested)
        for case in cases:
            with self.subTest():
                with self.assertRaises(RuntimeError):
                    if case is nested:
                        SCREEN.validate_and_relabel(
                            case, self.predecessor, self.route_reference,
                            self.parent, self.make_context(),
                        )
                    else:
                        SCREEN.validate_replay_handoff(case, self.predecessor)

    def test_08_relabel_closes_11_components_10_custody_and_nested_root(self):
        result = SCREEN.validate_and_relabel(
            self.make_raw_result("q90_success"),
            self.predecessor,
            self.route_reference,
            self.parent,
            self.make_context(),
        )
        self.assertEqual(len(result), 96)
        self.assertEqual(len(result["screen_execution_components"]), 11)
        self.assertEqual(len(result["source_custody"]), 10)
        component_paths = {
            item["relative_path"] for item in result["screen_execution_components"]
        }
        self.assertIn(SCREEN.EXECUTION_PARENT_NAME, component_paths)
        self.assertNotIn(SCREEN.CONTROL_FLOW_ROOT_NAME, component_paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, component_paths)
        self.assertTrue(
            result["checkpoint_transform"][
                "q88_execution_parent_replaces_raw_root_component_at_outer_boundary"
            ]
        )
        self.assertEqual(
            result["checkpoint_transform"]["execution_parent_q88_transform_sha256"],
            SCREEN.EXPECTED_ROUTE_TRANSFORM_SHA256,
        )
        for value_key, digest_key in (
            ("screen_execution_components", "screen_execution_components_sha256"),
            ("configuration_override", "configuration_override_sha256"),
            ("kernel_capability_override", "kernel_capability_override_sha256"),
            ("parent_horizon_override", "parent_horizon_override_sha256"),
            ("route_predecessor_reference", "route_predecessor_reference_sha256"),
            ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
        ):
            self.assertEqual(result[digest_key], digest(result[value_key]))

    def test_09_outer_order_is_replay_then_q88_reference(self):
        fresh = SCREEN.fresh_self_module()
        events = []
        parent = object()
        originals = {
            "load_execution_parent": fresh.load_execution_parent,
            "execute_parent_replay": fresh.execute_parent_replay,
            "load_route_reference": fresh.load_route_reference,
            "validate_and_relabel": fresh.validate_and_relabel,
        }
        try:
            fresh.load_execution_parent = lambda repo: parent
            fresh.execute_parent_replay = lambda observed, repo: (
                events.append("replay") or ({}, {})
            )
            fresh.load_route_reference = lambda repo, observed: (
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
            for key, value in originals.items():
                setattr(fresh, key, value)

    def make_fake_execution_parent(self):
        parent = types.ModuleType("fake_q88_parent")
        parent.EXTENDED_HORIZON = 88
        parent.validate_local_configuration = lambda: None
        parent.load_configured_v6_baseline = lambda repo: (object(), (1,))
        parent.load_kernel_wrapper = lambda repo: (
            object(), SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256, {"manifest": True}
        )
        parent.load_route_reference = lambda repo: ({"not": "called"}, {})
        parent.configure_parent_execution = lambda control, config, wrapper: {
            "semantic_delta": {
                "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                    "before": 80, "after": 90,
                }
            }
        }
        parent.execute_parent_fail_closed = lambda control, repo: {}
        parent.validate_and_relabel = lambda *args: {"old": True}
        parent.normalize_completed_parent_result = lambda value: value

        def private(repo):
            configuration, _ = parent.load_configured_v6_baseline(repo)
            wrapper, _, _ = parent.load_kernel_wrapper(repo)
            control = types.SimpleNamespace(run_four_gate=lambda: None)
            parent.configure_parent_execution(control, configuration, wrapper)
            result = parent.execute_parent_fail_closed(control, repo)
            predecessor, reference = parent.load_route_reference(repo)
            return parent.validate_and_relabel(
                result, predecessor, reference, (), "", {}, {}
            )

        parent._run_verified = private
        return parent

    def test_10_eight_parent_attributes_restore_on_success_and_exception(self):
        fields = (
            "EXTENDED_HORIZON", "validate_local_configuration",
            "load_configured_v6_baseline", "load_kernel_wrapper",
            "load_route_reference", "configure_parent_execution",
            "execute_parent_fail_closed", "validate_and_relabel",
        )
        original_dispatch = SCREEN.execute_control_parent_with_structured_abort
        try:
            for fail in (False, True):
                parent = self.make_fake_execution_parent()
                originals = {field: getattr(parent, field) for field in fields}
                sentinel = RuntimeError("synthetic replay failure")
                if fail:
                    SCREEN.execute_control_parent_with_structured_abort = (
                        lambda *args: (_ for _ in ()).throw(sentinel)
                    )
                    with self.assertRaises(RuntimeError) as caught:
                        SCREEN.execute_parent_replay(parent, HERE)
                    self.assertIs(caught.exception, sentinel)
                else:
                    SCREEN.execute_control_parent_with_structured_abort = (
                        lambda *args: self.make_raw_result("q90_success")
                    )
                    result, context = SCREEN.execute_parent_replay(parent, HERE)
                    self.assertEqual(len(result["records"]), 90)
                    self.assertTrue(context["q88_internal_c33_loader_suppressed"])
                for field, value in originals.items():
                    self.assertIs(getattr(parent, field), value)
        finally:
            SCREEN.execute_control_parent_with_structured_abort = original_dispatch

    def test_11_atomic_output_is_bounded_and_nonclobbering(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaises(RuntimeError):
                SCREEN.write_atomic_bounded(
                    output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1)
                )
            self.assertEqual(output.read_bytes(), b"{}")

    def test_12_canonical_exact_bytes_failure_branch_and_closure(self):
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
                "hubbard_l8_magnetization_adaptive_k_four_gate_"
                "k622592_c34_q90_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "screen_horizon_checkpoint_count": 90,
            "attempted_checkpoint_count": 90,
            "completed_checkpoint_count": 89,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "failure_checkpoint_included": True,
            "failure_record_sha256": EXPECTED_CANONICAL[
                "q90_record_sha256"
            ],
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "last_committed_cumulative_drop_ticks": "1700709292382471",
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
            "positive_artifact_generated": False,
            "child_boundary_committed": False,
            "observed_peak_single_expansion_terms": 741_376,
            "observed_term_gate_visits_including_terminal_attempt": (
                111_667_095
            ),
            "observed_maximum_expansion_coefficient_tick_bits": 57,
            "observed_maximum_product_bits": 121,
            "observed_rounding_cumulative_scaled_ticks_squared": (
                "158998426224482340534477790"
            ),
        }
        for field, value in expected_top.items():
            self.assertEqual(canonical[field], value, field)
        self.assertEqual(
            canonical["candidate_K_values"], list(SCREEN.M_CANDIDATES)
        )
        self.assertEqual(
            canonical["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 34},
        )
        self.assertEqual(
            canonical["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

        records = canonical["records"]
        history = canonical["selected_K_history"]
        self.assertEqual(len(records), 90)
        self.assertEqual(len(history), 89)
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
        self.assertEqual(records[:88], self.predecessor["records"])
        self.assertEqual(
            history[:88], self.predecessor["selected_K_history"]
        )
        self.assertEqual(history[88:], [SCREEN.K622592])
        self.assertEqual(
            digest(records[:88]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        )
        self.assertEqual(
            digest(history[:88]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        )

        all_rows = [
            row for record in records for row in record["candidate_records"]
        ]
        self.assertEqual(len(all_rows), 3_060)
        self.assertEqual(
            digest(all_rows),
            EXPECTED_CANONICAL["all_candidate_rows_sha256"],
        )
        q89 = records[88]
        q90 = records[89]
        expected_fields = {
            89: {
                "E_after_ticks": "1700709292382471",
                "E_before_ticks": "1700535038508063",
                "batch_in_stage": 32,
                "budget_prefix_cap_ticks": "1700799964693059",
                "checkpoint_index_zero_based": 88,
                "checkpoint_number_one_based": 89,
                "gate_batch_sha256": (
                    "c08d8485b35b6ab2b1df14e8d1c60d57836e263fee5649a4095052e42f6fbbab"
                ),
                "gate_occurrence_first_zero_based": 352,
                "gate_occurrence_last_zero_based": 355,
                "input_expansion_count": 622_592,
                "input_expansion_sha256": (
                    "8afaf7ce7e55c64f6c89e43929bb2df7d3c9229ccbf0193b171519c703829561"
                ),
                "maximum_dropped_abs_upper_ticks": "13718154",
                "maximum_expansion_coefficient_tick_bits": 57,
                "maximum_product_bits": 121,
                "minimum_retained_abs_upper_ticks": "13718154",
                "peak_live_terms_cumulative": 718_896,
                "peak_live_terms_this_checkpoint": 718_896,
                "prefix_slack_before_selection_ticks": "264926184996",
                "pretruncation_expansion_count": 718_896,
                "pretruncation_expansion_sha256": (
                    "7cc35e0ccc617c5cc1a0f1ad3e2765c922f7b9b9e6b0b84d70d3bbe2bf0a6ffe"
                ),
                "ranked_suffix_sha256": (
                    "6aa5c4e6e4e7f5cce604d381267011c0995f4ef485cd7c65184309187e714378"
                ),
                "retained_expansion_count": 622_592,
                "retained_expansion_sha256": (
                    "b7d1e16a3f344eb1353593fd66c379d36272c49d1ebfe5c5c2b3e6958ed98c19"
                ),
                "rounding_cumulative_scaled_ticks_squared": (
                    "154115336843269965996071494"
                ),
                "rounding_increment_scaled_ticks_squared": (
                    "4889681465847675190574371"
                ),
                "selected_K": 622_592,
                "selected_candidate_index": 33,
                "selected_drop_ticks": "174253874408",
                "selected_dropped_term_count": 96_304,
                "selected_dropped_terms_sha256": (
                    "c1c01a91dc13002ff6b412bdb0bda15dfc32588d26fa307409537e96e8dbfe45"
                ),
                "selected_effective_retained_count": 622_592,
                "stage_group": "HU",
                "stage_index": 2,
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "term_gate_visits_cumulative": 109_015_567,
                "term_gate_visits_increment": 2_639_702,
            },
            90: {
                "E_before_ticks": "1700709292382471",
                "batch_in_stage": 33,
                "budget_prefix_cap_ticks": "1700904496098731",
                "checkpoint_index_zero_based": 89,
                "checkpoint_number_one_based": 90,
                "gate_batch_sha256": (
                    "ec44bb3afa96f4d843a813f612af51c5478148a2e323a9601861b4ffa88acb8c"
                ),
                "gate_occurrence_first_zero_based": 356,
                "gate_occurrence_last_zero_based": 359,
                "input_expansion_count": 622_592,
                "input_expansion_sha256": (
                    "b7d1e16a3f344eb1353593fd66c379d36272c49d1ebfe5c5c2b3e6958ed98c19"
                ),
                "maximum_candidate_drop_excess_over_slack_ticks": (
                    "174337896824"
                ),
                "maximum_expansion_coefficient_tick_bits": 57,
                "maximum_product_bits": 121,
                "minimum_effective_K_to_meet_prefix": 635_284,
                "peak_live_terms_cumulative": 741_376,
                "peak_live_terms_this_checkpoint": 741_376,
                "prefix_slack_before_selection_ticks": "195203716260",
                "pretruncation_expansion_count": 741_376,
                "pretruncation_expansion_sha256": (
                    "ad6cae010e1842133d4cb4841a10d6386e09b891156472c71a0ea37e462a48bb"
                ),
                "ranked_suffix_sha256": (
                    "36ffaedc905a46998d4469170496ca3cb591dc9a95fc3ca3fd377cc1b8fe12f6"
                ),
                "required_K_excess_over_policy_maximum": 12_692,
                "rounding_cumulative_scaled_ticks_squared": (
                    "158998426224482340534477790"
                ),
                "rounding_increment_scaled_ticks_squared": (
                    "4883089381212374538406296"
                ),
                "selected_K": None,
                "selected_candidate_index": None,
                "stage_group": "HU",
                "stage_index": 2,
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "term_gate_visits_cumulative": 111_667_095,
                "term_gate_visits_increment": 2_651_528,
            },
        }
        expected_record_digests = {
            89: EXPECTED_CANONICAL["q89_record_sha256"],
            90: EXPECTED_CANONICAL["q90_record_sha256"],
        }
        expected_row_digests = {
            89: EXPECTED_CANONICAL["q89_rows_sha256"],
            90: EXPECTED_CANONICAL["q90_rows_sha256"],
        }
        for checkpoint, record in ((89, q89), (90, q90)):
            rows = record["candidate_records"]
            expected_schema = (
                SCREEN.RECORD_SUCCESS_RECORD_KEYS
                if checkpoint == 89 else SCREEN.RECORD_FAILURE_RECORD_KEYS
            )
            with self.subTest(checkpoint=checkpoint):
                self.assertEqual(frozenset(record), expected_schema)
                self.assertEqual(
                    {key: value for key, value in record.items()
                     if key != "candidate_records"},
                    expected_fields[checkpoint],
                )
                self.assertEqual(
                    digest(record), expected_record_digests[checkpoint]
                )
                self.assertEqual(len(rows), 34)
                self.assertEqual(
                    digest(rows), expected_row_digests[checkpoint]
                )
                for index, (row, configured_K) in enumerate(zip(
                    rows, SCREEN.M_CANDIDATES
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
                        row["feasible_under_current_prefix_cap"],
                        checkpoint == 89 and index == 33,
                    )
        selected = q89["candidate_records"][33]
        self.assertEqual(q89["selected_K"], selected["configured_K"])
        self.assertEqual(
            q89["selected_drop_ticks"], selected["drop_ticks"]
        )
        self.assertEqual(
            q89["E_after_ticks"], selected["E_after_if_selected_ticks"]
        )

        q88 = records[87]
        self.assertEqual(q89["E_before_ticks"], q88["E_after_ticks"])
        self.assertEqual(
            q89["input_expansion_count"], q88["retained_expansion_count"]
        )
        self.assertEqual(
            q89["input_expansion_sha256"], q88["retained_expansion_sha256"]
        )
        self.assertEqual(q90["E_before_ticks"], q89["E_after_ticks"])
        self.assertEqual(
            q90["input_expansion_count"], q89["retained_expansion_count"]
        )
        self.assertEqual(
            q90["input_expansion_sha256"], q89["retained_expansion_sha256"]
        )
        for checkpoint, record in ((89, q89), (90, q90)):
            anchor = SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
            self.assertEqual(
                record["budget_prefix_cap_ticks"],
                anchor["budget_prefix_cap_ticks"],
            )
            self.assertEqual(
                record["gate_batch_sha256"], anchor["gate_batch_sha256"]
            )

        handoff = canonical["predecessor_handoff_validation"]
        self.assertEqual(
            canonical["predecessor_handoff_validation_sha256"],
            EXPECTED_CANONICAL["handoff_sha256"],
        )
        self.assertEqual(
            digest(handoff), EXPECTED_CANONICAL["handoff_sha256"]
        )
        self.assertEqual(handoff["terminal_branch"], "Q89_SUCCESS_Q90_FAILURE")
        self.assertEqual(handoff["record_count"], 90)
        self.assertEqual(handoff["selected_history_count"], 89)
        self.assertEqual(handoff["candidate_row_count"], 3_060)
        self.assertTrue(handoff["q1_through_q88_records_exact"])
        self.assertTrue(handoff["q88_committed_state_exact"])
        self.assertFalse(handoff["q89_and_q90_outcomes_precommitted"])
        self.assertFalse(handoff["resource_policy_abort_structured"])
        self.assertIsNone(handoff["resource_policy_abort_checkpoint"])
        self.assertIsNone(handoff["resource_policy_abort_kind"])

        route = canonical["route_predecessor_reference"]
        route_canonical = route["canonical_transcript"]
        self.assertFalse(route["q89_and_q90_outcomes_precommitted"])
        self.assertFalse(route_canonical["loaded_before_replay"])
        self.assertTrue(
            route_canonical["loaded_after_full_replay_as_exact_reference"]
        )
        for key in (
            "compiled", "executed", "propagation_input", "state_resume_input",
            "execution_source_layer",
        ):
            self.assertFalse(route_canonical[key])
        self.assertFalse(
            canonical["checkpoint_transform"][
                "q89_and_q90_outcomes_precommitted"
            ]
        )
        self.assertFalse(handoff["K607993_execution_row_constructed"])
        self.assertFalse(handoff["K607993_q89_q90_extrapolation_permitted"])

        components = canonical["screen_execution_components"]
        expected_components = SCREEN.execution_components(
            list(self.parent.EXPECTED_PARENT_EXECUTION_COMPONENTS),
            self.parent,
            EXPECTED_SCREEN_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
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
        expected_custody = SCREEN.final_source_custody(
            dict(self.parent.EXPECTED_PARENT_SOURCE_CUSTODY),
            self.parent,
            EXPECTED_SCREEN_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        )
        self.assertEqual(custody, expected_custody)
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

    def test_13_default_suite_never_calls_run(self):
        opt_in_name = "test_14_real_replay_is_opt_in"
        for name in dir(type(self)):
            if not name.startswith("test_"):
                continue
            method = getattr(type(self), name)
            tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
            calls = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
            ]
            self.assertEqual(len(calls), 1 if name == opt_in_name else 0)

    @unittest.skipUnless(
        os.environ.get("FERMION_RUN_M622592_C34_Q90_REPLAY") == "1",
        "full M q90 replay is opt-in",
    )
    def test_14_real_replay_is_opt_in(self):
        canonical_raw = self.canonical_raw
        canonical = self.canonical
        result = SCREEN.run(HERE)
        self.assertEqual(result, canonical)
        self.assertEqual(canonical_bytes(result), canonical_raw)


if __name__ == "__main__":
    unittest.main()
