#!/usr/bin/env python3
"""Static, synthetic and opt-in tests for the M K606208/C33 q88 screen."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q88_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "d158d00275e78b33d0246e86bf9bc7bcaf4eb4f7fa4cb9afce2298e97cb5308d"
)
EXPECTED_SCREEN_SIZE = 109_288
CANONICAL_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q88_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 804_599,
    "file_sha256": (
        "f7ca4a1defd38472366c1cfcd112736f34b73e612002cce98a52f79daa5cc1b0"
    ),
    "records_sha256": (
        "8247f4f53a52d5e066f337fee6a5ef38055992f07c4efbaba08930bd390b1747"
    ),
    "history_sha256": (
        "e340ab1968faabaa070ba04a549ede8c7b27018897521e598ab5fd9714db3bb3"
    ),
    "q87_record_sha256": (
        "63182be225121402ee1bffa07be8ea074e6035eee08ce90ab32f120fc9d25e30"
    ),
    "q87_rows_sha256": (
        "c7819c1252415979ca87ada1578a141bed50c7b9a4e566c86e3e769ec430573a"
    ),
    "q88_failure_sha256": (
        "3a43eaaa48243694d21359595c82c4091733e7ed8c6cc2955997af4dd56610ce"
    ),
    "q88_rows_sha256": (
        "066028a4ed7119b5e584cc1bcdba5bd0d3c1e4a219c343281b42aa24a1ea2a2a"
    ),
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("m_k606208_c33_q88_for_tests", SCREEN_NAME)


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


class MagnetizationK606208C33Q88Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.anchor, self.route_reference = SCREEN.load_route_reference(HERE)

    @staticmethod
    def synthetic_sha(checkpoint: int, label: str) -> str:
        return hashlib.sha256(
            f"synthetic-M-q{checkpoint}-{label}".encode("ascii")
        ).hexdigest()

    def make_extended_record(self, previous, checkpoint, success):
        record = copy.deepcopy(self.anchor["records"][85])
        E_before = int(previous["E_after_ticks"])
        prefix_cap = int(
            SCREEN.EXPECTED_Q87_PREFIX_CAP_TICKS
            if checkpoint == 87
            else SCREEN.EXPECTED_Q88_PREFIX_CAP_TICKS
        )
        slack = prefix_cap - E_before
        pre_count = 700_000
        record.update({
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
            "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
            **SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "E_before_ticks": str(E_before),
            "budget_prefix_cap_ticks": str(prefix_cap),
            "prefix_slack_before_selection_ticks": str(slack),
            "pretruncation_expansion_count": pre_count,
            "pretruncation_expansion_sha256": self.synthetic_sha(
                checkpoint, "pretruncation"
            ),
            "ranked_suffix_sha256": self.synthetic_sha(checkpoint, "suffix"),
            "peak_live_terms_this_checkpoint": pre_count,
            "peak_live_terms_cumulative": max(
                previous["peak_live_terms_cumulative"], pre_count
            ),
            "term_gate_visits_increment": (
                4 * previous["retained_expansion_count"]
            ),
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"]
                + 4 * previous["retained_expansion_count"]
            ),
            "maximum_expansion_coefficient_tick_bits": previous[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": previous["maximum_product_bits"],
            "rounding_increment_scaled_ticks_squared": "1",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
        })
        rows = []
        for index, configured_K in enumerate(SCREEN.M_CANDIDATES):
            effective = min(configured_K, pre_count)
            width = len(SCREEN.M_CANDIDATES)
            drop = (width - index) if success else (slack + width - index)
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
        if success:
            selected = rows[0]
            for field in SCREEN.FAILURE_ONLY_RECORD_KEYS:
                record.pop(field, None)
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 0,
                "selected_K": SCREEN.M_CANDIDATES[0],
                "selected_effective_retained_count": selected[
                    "effective_retained_count"
                ],
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": self.synthetic_sha(
                    checkpoint, "dropped"
                ),
                "retained_expansion_count": selected[
                    "effective_retained_count"
                ],
                "retained_expansion_sha256": self.synthetic_sha(
                    checkpoint, "retained"
                ),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "1",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
        else:
            for field in SCREEN.SUCCESS_ONLY_RECORD_KEYS:
                record.pop(field, None)
            record.update({
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "selected_candidate_index": None,
                "selected_K": None,
                "minimum_effective_K_to_meet_prefix": SCREEN.K606208 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

    def make_resource_abort(self, previous, checkpoint, kind):
        policy_cap = SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"]
        kernel_cap = SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS[
            "max_single_expansion_terms"
        ]
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
                "enforced": policy_cap,
                "observed": policy_cap + 1,
                "pre_count": policy_cap + 1,
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
                "enforced": policy_cap,
                "observed": policy_cap + 1,
                "pre_count": policy_cap,
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
                    "observed_term_count>kernel_max_single_expansion_terms_"
                    "before_pretruncation_assignment"
                ),
                "enforced": kernel_cap,
                "observed": kernel_cap + 1,
                "pre_count": None,
            },
        }
        spec = specifications[kind]
        observed = spec["observed"]
        increment = previous["retained_expansion_count"]
        message = spec["exception_message"]
        abort = {
            "schema_version": 1,
            "abort_id": "M_k606208_c33_q88_policy_resource_abort_v1",
            "abort_kind": kind,
            "abort_frame_local_schema_id": spec[
                "abort_frame_local_schema_id"
            ],
            "exception_type": spec["exception_type"],
            "exception_message": message,
            "exception_args": [message],
            "exception_source_role": spec["exception_source_role"],
            "exception_chained_from_exact_parent_helper": spec[
                "exception_chained_from_exact_parent_helper"
            ],
            "control_flow_root_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256
            ),
            "helper_source_sha256": (
                "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
            ),
            "kernel_source_sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            "checkpoint_index_zero_based": checkpoint - 1,
            "checkpoint_number_one_based": checkpoint,
            **SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
            "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
            "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
            "input_expansion_count": previous["retained_expansion_count"],
            "input_expansion_sha256": previous["retained_expansion_sha256"],
            "pretruncation_expansion_count": spec["pre_count"],
            "observed_term_count": observed,
            "policy_max_single_expansion_terms": policy_cap,
            "kernel_max_single_expansion_terms": kernel_cap,
            "enforced_term_cap": spec["enforced"],
            "observed_excess_terms": observed - spec["enforced"],
            "policy_relation": spec["policy_relation"],
            "gate_batch_propagation_started": True,
            "gate_batch_propagation_completed": spec[
                "gate_batch_propagation_completed"
            ],
            "policy_cap_check_reached": spec["policy_cap_check_reached"],
            "kernel_cap_violation_triggered": spec[
                "kernel_cap_violation_triggered"
            ],
            "live_expansion_snapshot_available": spec[
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
            "term_gate_visits_increment": increment,
            "term_gate_visits_cumulative": (
                previous["term_gate_visits_cumulative"] + increment
            ),
            "rounding_increment_scaled_ticks_squared": "1",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
            "maximum_expansion_coefficient_tick_bits": previous[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": previous["maximum_product_bits"],
        }
        self.assertEqual(frozenset(abort), SCREEN.RESOURCE_POLICY_ABORT_KEYS)
        return abort

    def make_raw_result(self, branch, abort_kind="final_live_terms"):
        result = {
            key: copy.deepcopy(self.anchor[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        result.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_ROOT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_horizon_checkpoint_count": SCREEN.EXTENDED_HORIZON,
        })
        components = copy.deepcopy(
            list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
        )
        result["screen_execution_components"] = components
        result["screen_execution_components_sha256"] = digest(components)
        configuration = {"synthetic_raw_configuration_reference": True}
        result["configuration_reference"] = configuration
        result["configuration_reference_sha256"] = digest(configuration)
        transform = copy.deepcopy(
            self.anchor["checkpoint_transform"]
            ["physical_four_gate_control_flow_parent_transform"]
        )
        result["checkpoint_transform"] = transform
        result["checkpoint_transform_sha256"] = digest(transform)
        result["source_custody"] = copy.deepcopy(
            SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY
        )

        records = copy.deepcopy(self.anchor["records"])
        history = list(self.anchor["selected_K_history"])
        abort = None
        if branch == "q87_failure":
            q87 = self.make_extended_record(records[-1], 87, False)
            records.append(q87)
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            horizon_attempted = False
            horizon_committed = False
            last_E = SCREEN.EXPECTED_Q86_E_AFTER_TICKS
            attempted = 87
        elif branch == "q87_abort":
            abort = self.make_resource_abort(records[-1], 87, abort_kind)
            terminal = "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
            horizon_attempted = False
            horizon_committed = False
            last_E = SCREEN.EXPECTED_Q86_E_AFTER_TICKS
            attempted = 87
        elif branch in {"q88_failure", "q88_success", "q88_abort"}:
            q87 = self.make_extended_record(records[-1], 87, True)
            records.append(q87)
            history.append(q87["selected_K"])
            horizon_attempted = True
            attempted = 88
            if branch == "q88_abort":
                abort = self.make_resource_abort(q87, 88, abort_kind)
                terminal = "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
                horizon_committed = False
                last_E = q87["E_after_ticks"]
            else:
                q88 = self.make_extended_record(
                    records[-1], 88, branch == "q88_success"
                )
                records.append(q88)
            if branch == "q88_failure":
                terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                horizon_committed = False
                last_E = q87["E_after_ticks"]
            elif branch == "q88_success":
                terminal = "DIAGNOSTIC_HORIZON_REACHED"
                horizon_committed = True
                history.append(q88["selected_K"])
                last_E = q88["E_after_ticks"]
        else:
            raise AssertionError(branch)
        final = records[-1]
        failed = (
            abort is None
            and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        resource_source = abort if abort is not None else final
        result.update({
            "records": records,
            "records_sha256": digest(records),
            "selected_K_history": history,
            "selected_K_history_sha256": digest(history),
            "attempted_checkpoint_count": attempted,
            "completed_checkpoint_count": len(history),
            "screen_terminal_condition": terminal,
            "horizon_checkpoint_attempted": horizon_attempted,
            "horizon_reached_with_committed_checkpoint": horizon_committed,
            "failure_checkpoint_included": failed,
            "failure_record_sha256": digest(final) if failed else None,
            "last_committed_cumulative_drop_ticks": last_E,
            "observed_peak_single_expansion_terms": resource_source[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": resource_source[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": resource_source[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": resource_source[
                "maximum_product_bits"
            ],
            "observed_rounding_cumulative_scaled_ticks_squared": resource_source[
                "rounding_cumulative_scaled_ticks_squared"
            ],
            "resource_policy_abort": abort,
            "resource_policy_abort_sha256": (
                digest(abort) if abort is not None else None
            ),
        })
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return result

    def make_context(self, parent):
        _wrapper, wrapper_sha, manifest = parent.load_kernel_wrapper(HERE)
        return {
            "baseline_m": tuple(parent.V6_M_CANDIDATES),
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": copy.deepcopy(manifest),
            "raw_control_flow_horizon_override": {
                "changed_fields": [
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count"
                ],
                "semantic_delta": {
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                        "before": 80,
                        "after": 88,
                    }
                },
            },
            "execution_parent_private_entrypoint_called": True,
            "q86_canonical_loaded_before_replay": False,
            "execution_parent_route_loader_suppressed": True,
            "execution_parent_abort_adapter_installed": True,
        }

    def test_01_source_parent_and_q86_canonical_pins(self):
        self.assertEqual((HERE / SCREEN_NAME).stat().st_size, EXPECTED_SCREEN_SIZE)
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN_NAME).read_bytes()).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (HERE / SCREEN.EXECUTION_PARENT_NAME).read_bytes()
            ).hexdigest(),
            SCREEN.EXPECTED_EXECUTION_PARENT_SHA256,
        )
        route_raw = (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(len(route_raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE)
        self.assertEqual(
            hashlib.sha256(route_raw).hexdigest(),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(route_raw, canonical_bytes(json.loads(route_raw)))
        self.assertEqual(
            digest(self.anchor["records"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        )
        self.assertEqual(
            digest(self.anchor["selected_K_history"]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        )
        self.assertEqual(
            digest(self.anchor["records"][-1]),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q86_RECORD_SHA256,
        )
        canonical_reference = self.route_reference["canonical_transcript"]
        self.assertFalse(canonical_reference["compiled"])
        self.assertFalse(canonical_reference["executed"])
        self.assertFalse(canonical_reference["loaded_before_replay"])
        self.assertTrue(
            canonical_reference[
                "loaded_after_full_replay_as_exact_reference"
            ]
        )
        self.assertFalse(canonical_reference["propagation_input"])
        self.assertFalse(canonical_reference["state_resume_input"])
        parent_reference = self.route_reference["execution_parent_screen"]
        self.assertTrue(parent_reference["compiled"])
        self.assertTrue(parent_reference["executed"])
        self.assertTrue(parent_reference["private_entrypoint_called"])

    def test_02_exact_candidates_caps_schemas_and_parent_contract(self):
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.M_CANDIDATES), 33)
        self.assertEqual(SCREEN.M_CANDIDATES[-1], SCREEN.K606208)
        self.assertEqual(
            digest(list(SCREEN.M_CANDIDATES)),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_candidate_K"], SCREEN.K606208
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_output_terms_if_successful"],
            SCREEN.K606208,
        )
        self.assertEqual(
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS["max_retained_K"],
            SCREEN.K606208,
        )
        self.assertEqual(
            {
                "raw": len(SCREEN.EXPECTED_PARENT_RESULT_KEYS),
                "final": len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS),
                "success": len(SCREEN.SUCCESS_RECORD_KEYS),
                "failure": len(SCREEN.FAILURE_RECORD_KEYS),
                "row": len(SCREEN.CANDIDATE_RECORD_KEYS),
                "resource": len(SCREEN.RESOURCE_POLICY_ABORT_KEYS),
            },
            {
                "raw": 67,
                "final": 96,
                "success": 37,
                "failure": 31,
                "row": 7,
                "resource": 50,
            },
        )
        parent = SCREEN.load_execution_parent(HERE)
        self.assertIsInstance(parent, types.ModuleType)
        self.assertEqual(parent.EXTENDED_HORIZON, 86)
        self.assertEqual(parent.M_CANDIDATES, SCREEN.M_CANDIDATES)
        self.assertEqual(parent.POLICY_CAPS_BASE, SCREEN.POLICY_CAPS_BASE)
        self.assertEqual(
            parent.EXPECTED_WRAPPED_KERNEL_LIMITS,
            SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

    def test_03_q86_private_entrypoint_adapter_and_exception_identity(self):
        parent = SCREEN.load_execution_parent(HERE)
        observed = {}

        class Inner:
            def _run_verified(self, repo, mode):
                observed["repo"] = repo
                observed["mode"] = mode
                return {"raw": True}

        inner = Inner()
        configuration = object()
        wrapper = object()
        manifest = {"synthetic_manifest": True}
        parent.load_control_flow_parent = lambda _repo: inner
        parent.load_configured_v6_baseline = lambda _repo: (
            configuration,
            parent.V6_M_CANDIDATES,
        )
        parent.load_kernel_wrapper = lambda _repo: (
            wrapper,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            manifest,
        )
        parent.load_route_reference = lambda _repo: (_ for _ in ()).throw(
            AssertionError("q86 predecessor loader must be suppressed")
        )

        def configure(observed_inner, observed_configuration, observed_wrapper):
            self.assertIs(observed_inner, inner)
            self.assertIs(observed_configuration, configuration)
            self.assertIs(observed_wrapper, wrapper)
            observed["horizon"] = parent.EXTENDED_HORIZON
            return {
                "changed_fields": [
                    "MODE_CONFIG.magnetization.horizon_checkpoint_count"
                ]
            }

        parent.configure_parent_execution = configure
        original_execute = SCREEN.execute_control_parent_with_structured_abort
        SCREEN.execute_control_parent_with_structured_abort = (
            lambda _execution_parent, control_parent, _kernel, repo:
            control_parent._run_verified(repo, SCREEN.MODE)
        )
        try:
            result, context = SCREEN.execute_parent_replay(parent, HERE)
        finally:
            SCREEN.execute_control_parent_with_structured_abort = original_execute
        self.assertEqual(result, {"raw": True})
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["horizon"], 88)
        self.assertEqual(parent.EXTENDED_HORIZON, 86)
        self.assertTrue(context["execution_parent_private_entrypoint_called"])
        self.assertFalse(context["q86_canonical_loaded_before_replay"])
        self.assertTrue(context["execution_parent_route_loader_suppressed"])
        self.assertTrue(context["execution_parent_abort_adapter_installed"])
        self.assertEqual(context["wrapper_sha"], SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(context["wrapper_manifest"], manifest)

        resource_error = RuntimeError("resource identity")
        failing_parent = SCREEN.load_execution_parent(HERE)

        class FailingInner:
            @staticmethod
            def _run_verified(_repo, _mode):
                raise resource_error

        failing_parent.load_control_flow_parent = lambda _repo: FailingInner()
        failing_parent.load_configured_v6_baseline = lambda _repo: (
            object(),
            failing_parent.V6_M_CANDIDATES,
        )
        failing_parent.load_kernel_wrapper = lambda _repo: (
            object(),
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            manifest,
        )
        failing_parent.configure_parent_execution = lambda *_args: {
            "changed_fields": [
                "MODE_CONFIG.magnetization.horizon_checkpoint_count"
            ]
        }
        with self.assertRaises(RuntimeError) as caught:
            SCREEN.execute_parent_replay(failing_parent, HERE)
        self.assertIs(caught.exception, resource_error)
        self.assertEqual(failing_parent.EXTENDED_HORIZON, 86)

    def test_04_all_five_terminal_branches_are_closed(self):
        expected = {
            "q87_failure": (
                "Q87_FAILURE_Q88_NOT_ATTEMPTED",
                87,
                86,
                True,
                None,
            ),
            "q87_abort": (
                "Q87_RESOURCE_ABORT_Q88_NOT_ATTEMPTED",
                87,
                86,
                False,
                87,
            ),
            "q88_failure": (
                "Q87_SUCCESS_Q88_FAILURE",
                88,
                87,
                True,
                None,
            ),
            "q88_abort": (
                "Q87_SUCCESS_Q88_RESOURCE_ABORT",
                88,
                87,
                False,
                88,
            ),
            "q88_success": (
                "Q87_AND_Q88_SUCCESS_HORIZON_REACHED",
                88,
                88,
                False,
                None,
            ),
        }
        for branch, (
            expected_branch,
            attempted,
            completed,
            failure_included,
            abort_checkpoint,
        ) in expected.items():
            with self.subTest(branch=branch):
                result = self.make_raw_result(branch)
                handoff = SCREEN.validate_replay_handoff(result, self.anchor)
                self.assertEqual(handoff["terminal_branch"], expected_branch)
                self.assertTrue(handoff["q1_through_q86_records_exact"])
                self.assertTrue(
                    handoff["q1_through_q86_all_33_candidate_rows_exact"]
                )
                self.assertFalse(
                    handoff["q87_and_q88_outcomes_precommitted"]
                )
                self.assertEqual(result["attempted_checkpoint_count"], attempted)
                self.assertEqual(result["completed_checkpoint_count"], completed)
                self.assertIs(
                    result["failure_checkpoint_included"], failure_included
                )
                self.assertEqual(
                    handoff["resource_policy_abort_checkpoint"],
                    abort_checkpoint,
                )
                self.assertIs(
                    handoff["resource_policy_abort_structured"],
                    abort_checkpoint is not None,
                )

    def test_05_q87_q88_each_close_all_three_resource_abort_kinds(self):
        kinds = (
            "final_live_terms",
            "transient_live_terms",
            "kernel_single_expansion_terms",
        )
        for branch, checkpoint in (("q87_abort", 87), ("q88_abort", 88)):
            for kind in kinds:
                with self.subTest(branch=branch, kind=kind):
                    result = self.make_raw_result(branch, kind)
                    handoff = SCREEN.validate_replay_handoff(
                        result,
                        self.anchor,
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_checkpoint"],
                        checkpoint,
                    )
                    self.assertEqual(
                        handoff["resource_policy_abort_kind"],
                        kind,
                    )
                    self.assertEqual(
                        result["resource_policy_abort_sha256"],
                        digest(result["resource_policy_abort"]),
                    )

        tamper_cases = []
        extra = self.make_raw_result("q87_abort")
        extra["resource_policy_abort"]["untrusted"] = True
        extra["resource_policy_abort_sha256"] = digest(
            extra["resource_policy_abort"]
        )
        tamper_cases.append(extra)
        bad_digest = self.make_raw_result("q88_abort")
        bad_digest["resource_policy_abort_sha256"] = "0" * 64
        tamper_cases.append(bad_digest)
        bool_checkpoint = self.make_raw_result("q87_abort")
        bool_checkpoint["resource_policy_abort"][
            "checkpoint_number_one_based"
        ] = True
        bool_checkpoint["resource_policy_abort_sha256"] = digest(
            bool_checkpoint["resource_policy_abort"]
        )
        tamper_cases.append(bool_checkpoint)
        int_boolean = self.make_raw_result("q88_abort")
        int_boolean["resource_policy_abort"][
            "gate_batch_propagation_started"
        ] = 1
        int_boolean["resource_policy_abort_sha256"] = digest(
            int_boolean["resource_policy_abort"]
        )
        tamper_cases.append(int_boolean)
        unknown = self.make_raw_result("q88_abort")
        unknown["resource_policy_abort"]["abort_kind"] = "unknown"
        unknown["resource_policy_abort_sha256"] = digest(
            unknown["resource_policy_abort"]
        )
        tamper_cases.append(unknown)
        for result in tamper_cases:
            with self.assertRaises(RuntimeError):
                SCREEN.validate_replay_handoff(result, self.anchor)

    def test_05_terminal_shapes_prefix_and_digests_fail_closed(self):
        cases = {}
        extra_top = self.make_raw_result("q87_failure")
        extra_top["untrusted"] = True
        cases["top schema"] = extra_top
        prefix = self.make_raw_result("q87_failure")
        prefix["records"][0]["stage_index"] = 99
        prefix["records_sha256"] = digest(prefix["records"])
        cases["q1-q86 prefix"] = prefix
        history = self.make_raw_result("q88_success")
        history["selected_K_history"][0] = SCREEN.K606208
        history["selected_K_history_sha256"] = digest(
            history["selected_K_history"]
        )
        cases["history prefix"] = history
        missing_q88 = self.make_raw_result("q88_success")
        missing_q88["records"].pop()
        missing_q88["records_sha256"] = digest(missing_q88["records"])
        cases["q87 success missing q88"] = missing_q88
        extra_after_failure = self.make_raw_result("q87_failure")
        extra_after_failure["records"].append(
            copy.deepcopy(self.make_raw_result("q88_success")["records"][-1])
        )
        extra_after_failure["records_sha256"] = digest(
            extra_after_failure["records"]
        )
        cases["q87 failure continued"] = extra_after_failure
        bad_failure_sha = self.make_raw_result("q88_failure")
        bad_failure_sha["failure_record_sha256"] = "0" * 64
        cases["failure digest"] = bad_failure_sha
        bad_records_sha = self.make_raw_result("q88_success")
        bad_records_sha["records_sha256"] = "0" * 64
        cases["records digest"] = bad_records_sha
        bad_resource = self.make_raw_result("q87_failure")
        bad_resource["observed_maximum_product_bits"] += 1
        cases["resource summary"] = bad_resource
        synchronized_transform = self.make_raw_result("q88_success")
        synchronized_transform["checkpoint_transform"] = {
            "physical_gate_sequence_changed": True,
            "control_flow_changes": ["tampered"],
        }
        synchronized_transform["checkpoint_transform_sha256"] = digest(
            synchronized_transform["checkpoint_transform"]
        )
        cases["synchronized transform and digest"] = synchronized_transform
        bool_as_schema_version = self.make_raw_result("q87_failure")
        bool_as_schema_version["schema_version"] = True
        cases["bool as schema version"] = bool_as_schema_version
        int_as_invariant_bool = self.make_raw_result("q87_failure")
        int_as_invariant_bool["v2_run_entrypoint_called"] = 0
        cases["int as invariant bool"] = int_as_invariant_bool
        for field, forged in (
            ("horizon_checkpoint_attempted", 1),
            ("horizon_reached_with_committed_checkpoint", 1),
            ("failure_checkpoint_included", 0),
        ):
            terminal_bool = self.make_raw_result("q88_success")
            terminal_bool[field] = forged
            cases[f"int as terminal bool {field}"] = terminal_bool
        for label, result in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(result, self.anchor)

    def test_06_extension_record_ledger_and_schema_tamper_rejected(self):
        previous = self.anchor["records"][-1]
        good = self.make_extended_record(previous, 87, True)
        self.assertEqual(
            SCREEN.validate_extended_record(good, previous, 87),
            SCREEN.M_CANDIDATES[0],
        )
        failure = self.make_extended_record(previous, 87, False)
        self.assertIsNone(
            SCREEN.validate_extended_record(failure, previous, 87)
        )
        tamper_cases = {
            "extra record key": lambda item: item.__setitem__("untrusted", True),
            "pretruncation hash": lambda item: item.__setitem__(
                "pretruncation_expansion_sha256", "not-canonical"
            ),
            "ranked suffix hash": lambda item: item.__setitem__(
                "ranked_suffix_sha256", "A" * 64
            ),
            "cap": lambda item: item.__setitem__(
                "budget_prefix_cap_ticks", SCREEN.EXPECTED_Q88_PREFIX_CAP_TICKS
            ),
            "input continuity": lambda item: item.__setitem__(
                "input_expansion_count", 1
            ),
            "rounding recurrence": lambda item: item.__setitem__(
                "rounding_cumulative_scaled_ticks_squared", "0"
            ),
            "visit recurrence": lambda item: item.__setitem__(
                "term_gate_visits_cumulative",
                item["term_gate_visits_cumulative"] + 1,
            ),
            "peak recurrence": lambda item: item.__setitem__(
                "peak_live_terms_cumulative",
                item["peak_live_terms_cumulative"] + 1,
            ),
            "coefficient maximum decrease": lambda item: item.__setitem__(
                "maximum_expansion_coefficient_tick_bits",
                previous["maximum_expansion_coefficient_tick_bits"] - 1,
            ),
            "product maximum decrease": lambda item: item.__setitem__(
                "maximum_product_bits", previous["maximum_product_bits"] - 1
            ),
            "row schema": lambda item: item["candidate_records"][0].__setitem__(
                "untrusted", True
            ),
            "row identity": lambda item: item["candidate_records"][0].__setitem__(
                "configured_K", SCREEN.K606208
            ),
            "false as row index": lambda item: item["candidate_records"][0].__setitem__(
                "candidate_index", False
            ),
            "true as row index": lambda item: item["candidate_records"][1].__setitem__(
                "candidate_index", True
            ),
            "bool as configured K": lambda item: item["candidate_records"][0].__setitem__(
                "configured_K", True
            ),
            "bool as effective count": lambda item: item["candidate_records"][0].__setitem__(
                "effective_retained_count", True
            ),
            "bool as dropped count": lambda item: item["candidate_records"][0].__setitem__(
                "dropped_term_count", True
            ),
            "row E recurrence": lambda item: item["candidate_records"][0].__setitem__(
                "E_after_if_selected_ticks", "0"
            ),
            "row feasibility": lambda item: item["candidate_records"][0].__setitem__(
                "feasible_under_current_prefix_cap", False
            ),
            "selected index": lambda item: item.__setitem__(
                "selected_candidate_index", 1
            ),
            "false as selected index": lambda item: item.__setitem__(
                "selected_candidate_index", False
            ),
            "bool as checkpoint index": lambda item: item.__setitem__(
                "checkpoint_index_zero_based", True
            ),
            "retained digest": lambda item: item.__setitem__(
                "retained_expansion_sha256", "0"
            ),
        }
        for label, mutate in tamper_cases.items():
            with self.subTest(label=label):
                tampered = copy.deepcopy(good)
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_extended_record(tampered, previous, 87)

        forged_zero_drop = copy.deepcopy(good)
        forged_zero_drop["pretruncation_expansion_count"] = 81_920
        forged_zero_drop["peak_live_terms_this_checkpoint"] = previous[
            "retained_expansion_count"
        ]
        forged_zero_drop["peak_live_terms_cumulative"] = previous[
            "peak_live_terms_cumulative"
        ]
        E_before = int(forged_zero_drop["E_before_ticks"])
        for row in forged_zero_drop["candidate_records"]:
            row.update({
                "effective_retained_count": 81_920,
                "dropped_term_count": 0,
                "drop_ticks": "1",
                "E_after_if_selected_ticks": str(E_before + 1),
                "feasible_under_current_prefix_cap": True,
            })
        forged_zero_drop.update({
            "selected_candidate_index": 0,
            "selected_K": 81_920,
            "selected_effective_retained_count": 81_920,
            "selected_dropped_term_count": 0,
            "selected_drop_ticks": "1",
            "retained_expansion_count": 81_920,
            "E_after_ticks": str(E_before + 1),
        })
        with self.assertRaisesRegex(RuntimeError, "zero equivalence"):
            SCREEN.validate_extended_record(forged_zero_drop, previous, 87)

        failure_tampers = {
            "feasible failure row": lambda item: item["candidate_records"][-1].update({
                "drop_ticks": "0",
                "E_after_if_selected_ticks": item["E_before_ticks"],
                "feasible_under_current_prefix_cap": True,
            }),
            "minimum K": lambda item: item.__setitem__(
                "minimum_effective_K_to_meet_prefix", SCREEN.K606208
            ),
            "excess": lambda item: item.__setitem__(
                "required_K_excess_over_policy_maximum", 2
            ),
        }
        for label, mutate in failure_tampers.items():
            with self.subTest(failure_tamper=label):
                tampered = copy.deepcopy(failure)
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_extended_record(tampered, previous, 87)

    def test_07_relabel_closes_provenance_components_custody_and_digests(self):
        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_execution_parent(HERE)
        context = self.make_context(parent)
        result = fresh.validate_and_relabel(
            self.make_raw_result("q88_success"),
            self.anchor,
            self.route_reference,
            parent,
            context,
        )
        self.assertEqual(
            frozenset(result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k606208_c33_q88_screen_v1",
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["control_flow_parent_relative_path"],
            SCREEN.EXECUTION_PARENT_NAME,
        )
        self.assertEqual(
            result["control_flow_parent_source_sha256"],
            SCREEN.EXPECTED_EXECUTION_PARENT_SHA256,
        )
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(result["control_flow_owned_by_screen"])
        self.assertTrue(result["control_flow_owned_by_verified_parent"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        self.assertEqual(
            result["predecessor_handoff_validation"]["terminal_branch"],
            "Q87_AND_Q88_SUCCESS_HORIZON_REACHED",
        )
        delta = result["checkpoint_transform"][
            "incremental_route_semantic_delta"
        ]
        self.assertEqual(delta, {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 86, "after": 88},
        })
        self.assertEqual(
            result["checkpoint_transform"]["overridden_semantics"],
            ["magnetization_horizon_checkpoint_count"],
        )
        components = result["screen_execution_components"]
        self.assertEqual(len(components), 11)
        paths = [item["relative_path"] for item in components]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(SCREEN.SELF_NAME, paths)
        self.assertIn(SCREEN.EXECUTION_PARENT_NAME, paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.CONTROL_FLOW_ROOT_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        custody = result["source_custody"]
        self.assertEqual(len(custody), 10)
        self.assertEqual(
            custody,
            SCREEN.expected_final_source_custody(EXPECTED_SCREEN_SHA256),
        )
        self.assertNotIn(SCREEN.CONTROL_FLOW_ROOT_NAME, custody)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, custody)
        for path, expected_sha in custody.items():
            self.assertEqual(
                hashlib.sha256((HERE / path).read_bytes()).hexdigest(),
                expected_sha,
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
            "resource_policy_abort",
        ):
            if result[field] is None:
                self.assertIsNone(result[f"{field}_sha256"])
            else:
                self.assertEqual(
                    result[f"{field}_sha256"],
                    digest(result[field]),
                )
        horizon = result["parent_horizon_override"]
        self.assertEqual(
            horizon["changed_fields"], ["screen_horizon_checkpoint_count"]
        )
        self.assertFalse(horizon["candidate_K_values_changed"])
        self.assertFalse(horizon["policy_caps_changed"])
        self.assertFalse(horizon["kernel_capability_limits_changed"])
        self.assertFalse(horizon["q86_canonical_loaded_before_replay"])
        self.assertTrue(horizon["execution_parent_route_loader_suppressed"])
        self.assertTrue(horizon["execution_parent_abort_adapter_installed"])
        incremental = result["configuration_override"][
            "incremental_route_override_from_k606208_c33_q86"
        ]
        self.assertEqual(incremental["candidate_count"], {
            "before": 33,
            "after": 33,
        })
        self.assertEqual(incremental["candidate_ladder_added"], [])
        self.assertEqual(incremental["candidate_ladder_removed"], [])
        self.assertEqual(incremental["policy_cap_changes"], {})

    def test_08_custody_components_and_nested_digests_fail_closed(self):
        raw = self.make_raw_result("q87_failure")
        custody_cases = {}
        missing = copy.deepcopy(raw)
        missing["source_custody"].pop(next(iter(missing["source_custody"])))
        custody_cases["missing"] = missing
        extra = copy.deepcopy(raw)
        extra["source_custody"]["untrusted.py"] = "0" * 64
        custody_cases["extra"] = extra
        wrong = copy.deepcopy(raw)
        first = next(iter(wrong["source_custody"]))
        wrong["source_custody"][first] = "0" * 64
        custody_cases["wrong hash"] = wrong
        for label, item in custody_cases.items():
            with self.subTest(custody=label):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(item, self.anchor)

        duplicate = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaises(RuntimeError):
            SCREEN.execution_components(duplicate, EXPECTED_SCREEN_SHA256)
        injected = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        injected[0]["untrusted"] = True
        with self.assertRaises(RuntimeError):
            SCREEN.execution_components(injected, EXPECTED_SCREEN_SHA256)

        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_execution_parent(HERE)
        context = self.make_context(parent)
        bad_component_digest = self.make_raw_result("q87_failure")
        bad_component_digest["screen_execution_components_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "digest drift: screen_execution_components"
        ):
            fresh.validate_and_relabel(
                bad_component_digest,
                self.anchor,
                self.route_reference,
                parent,
                context,
            )
        bad_configuration_digest = self.make_raw_result("q87_failure")
        bad_configuration_digest["configuration_reference_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "digest drift: configuration_reference"
        ):
            fresh.validate_and_relabel(
                bad_configuration_digest,
                self.anchor,
                self.route_reference,
                parent,
                context,
            )
        bad_transform_digest = self.make_raw_result("q87_failure")
        bad_transform_digest["checkpoint_transform_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "digest drift: checkpoint_transform"
        ):
            fresh.validate_and_relabel(
                bad_transform_digest,
                self.anchor,
                self.route_reference,
                parent,
                context,
            )

    def test_09_run_order_is_replay_then_post_replay_q86_reference(self):
        fresh = SCREEN.fresh_self_module()
        parent = types.SimpleNamespace(parent=True)
        raw = {"raw": True}
        context = {"context": True}
        predecessor = {"predecessor": True}
        route = {"route": True}
        final = {"final": True}
        order = []
        fresh.load_execution_parent = lambda repo: (
            order.append(("load_parent", repo)),
            parent,
        )[1]
        fresh.execute_parent_replay = lambda observed_parent, repo: (
            order.append(("replay", observed_parent, repo)),
            (raw, context),
        )[1]
        fresh.load_route_reference = lambda repo: (
            order.append(("load_q86_after_replay", repo)),
            (predecessor, route),
        )[1]

        def relabel(*args):
            order.append(("relabel", args))
            return final

        fresh.validate_and_relabel = relabel
        self.assertIs(fresh._run_verified(HERE), final)
        self.assertEqual(
            [event[0] for event in order],
            ["load_parent", "replay", "load_q86_after_replay", "relabel"],
        )
        self.assertEqual(order[1][1], parent)
        self.assertEqual(order[3][1], (raw, predecessor, route, parent, context))

    def test_10_atomic_output_is_bounded_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "transcript.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"{}"))
            with self.assertRaisesRegex(RuntimeError, "byte"):
                SCREEN.write_atomic_bounded(
                    output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1)
                )
            original_replace = SCREEN.os.replace

            def fail_replace(_source, _destination):
                raise OSError("synthetic replace failure")

            try:
                SCREEN.os.replace = fail_replace
                with self.assertRaisesRegex(OSError, "synthetic replace"):
                    SCREEN.write_atomic_bounded(output, b'{"new":true}')
            finally:
                SCREEN.os.replace = original_replace
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(
                list(pathlib.Path(temporary).glob("transcript.json.*.tmp")), []
            )

    def test_11_canonical_exact_bytes_terminal_ledgers_and_closure(self):
        self.assertEqual(SCREEN.OUTPUT_NAME, CANONICAL_NAME)
        raw = (HERE / CANONICAL_NAME).read_bytes()
        transcript = json.loads(raw)
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            EXPECTED_CANONICAL["file_sha256"],
        )
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(
            frozenset(transcript), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(transcript), 96)

        records = transcript["records"]
        history = transcript["selected_K_history"]
        self.assertEqual((len(records), len(history)), (88, 87))
        self.assertEqual(
            sum(len(record["candidate_records"]) for record in records),
            2_904,
        )
        self.assertEqual(digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(
            transcript["records_sha256"],
            EXPECTED_CANONICAL["records_sha256"],
        )
        self.assertEqual(digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            EXPECTED_CANONICAL["history_sha256"],
        )
        self.assertEqual(records[:86], self.anchor["records"])
        self.assertEqual(history[:86], self.anchor["selected_K_history"])
        self.assertEqual(history[86], SCREEN.K606208)
        self.assertTrue(
            all(len(record["candidate_records"]) == 33 for record in records)
        )

        q87, q88 = records[86:88]
        self.assertEqual(
            digest(q87), EXPECTED_CANONICAL["q87_record_sha256"]
        )
        self.assertEqual(
            digest(q87["candidate_records"]),
            EXPECTED_CANONICAL["q87_rows_sha256"],
        )
        q87_exact = {
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "checkpoint_index_zero_based": 86,
            "checkpoint_number_one_based": 87,
            "gate_occurrence_first_zero_based": 344,
            "gate_occurrence_last_zero_based": 347,
            "gate_batch_sha256": (
                "4b60608343a13e9927dd20cd4bb7314e67b1432465e27d186c117935402801e7"
            ),
            "input_expansion_count": 589_824,
            "input_expansion_sha256": (
                "81892d7c339a3094dbe40a531b23ddcfe642804e1c6e8f1da6ca57fa4915a59e"
            ),
            "E_before_ticks": "1700472573422099",
            "budget_prefix_cap_ticks": "1700590901881716",
            "prefix_slack_before_selection_ticks": "118328459617",
            "pretruncation_expansion_count": 645_618,
            "selected_candidate_index": 32,
            "selected_K": 606_208,
            "selected_effective_retained_count": 606_208,
            "selected_dropped_term_count": 39_410,
            "selected_drop_ticks": "28631843222",
            "retained_expansion_count": 606_208,
            "retained_expansion_sha256": (
                "1dbf1803c6909f90aa3afffc024986aefde98d7580c1675bb6e717063c90b262"
            ),
            "E_after_ticks": "1700501205265321",
        }
        for field, expected in q87_exact.items():
            with self.subTest(q87_field=field):
                self.assertEqual(q87[field], expected)
        self.assertEqual(
            int(q87["prefix_slack_before_selection_ticks"])
            - int(q87["selected_drop_ticks"]),
            89_696_616_395,
        )
        q87_max_row = q87["candidate_records"][32]
        self.assertEqual(q87_max_row, {
            "candidate_index": 32,
            "configured_K": 606_208,
            "effective_retained_count": 606_208,
            "dropped_term_count": 39_410,
            "drop_ticks": "28631843222",
            "E_after_if_selected_ticks": "1700501205265321",
            "feasible_under_current_prefix_cap": True,
        })

        self.assertEqual(
            digest(q88), EXPECTED_CANONICAL["q88_failure_sha256"]
        )
        self.assertEqual(
            digest(q88["candidate_records"]),
            EXPECTED_CANONICAL["q88_rows_sha256"],
        )
        q88_exact = {
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "checkpoint_index_zero_based": 87,
            "checkpoint_number_one_based": 88,
            "gate_occurrence_first_zero_based": 348,
            "gate_occurrence_last_zero_based": 351,
            "gate_batch_sha256": (
                "7f8c6a2dd155412a27369e1fa8402c37127c6eadf12e4fa59ba442d345e8eaf7"
            ),
            "input_expansion_count": 606_208,
            "input_expansion_sha256": (
                "1dbf1803c6909f90aa3afffc024986aefde98d7580c1675bb6e717063c90b262"
            ),
            "E_before_ticks": "1700501205265321",
            "budget_prefix_cap_ticks": "1700695433287388",
            "prefix_slack_before_selection_ticks": "194228022067",
            "pretruncation_expansion_count": 689_242,
            "minimum_effective_K_to_meet_prefix": 607_993,
            "required_K_excess_over_policy_maximum": 1_785,
            "maximum_candidate_drop_excess_over_slack_ticks": "24511950557",
            "selected_candidate_index": None,
            "selected_K": None,
        }
        for field, expected in q88_exact.items():
            with self.subTest(q88_field=field):
                self.assertEqual(q88[field], expected)
        q88_max_row = q88["candidate_records"][32]
        self.assertEqual(q88_max_row, {
            "candidate_index": 32,
            "configured_K": 606_208,
            "effective_retained_count": 606_208,
            "dropped_term_count": 83_034,
            "drop_ticks": "218739972624",
            "E_after_if_selected_ticks": "1700719945237945",
            "feasible_under_current_prefix_cap": False,
        })
        self.assertEqual(
            int(q88_max_row["drop_ticks"])
            - int(q88["prefix_slack_before_selection_ticks"]),
            24_511_950_557,
        )

        terminal_exact = {
            "screen_horizon_checkpoint_count": 88,
            "attempted_checkpoint_count": 88,
            "completed_checkpoint_count": 87,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
            "failure_record_sha256": EXPECTED_CANONICAL[
                "q88_failure_sha256"
            ],
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "last_committed_cumulative_drop_ticks": "1700501205265321",
            "observed_peak_single_expansion_terms": 694_130,
            "observed_term_gate_visits_including_terminal_attempt": 106_375_865,
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
        }
        for field, expected in terminal_exact.items():
            with self.subTest(terminal_field=field):
                self.assertEqual(transcript[field], expected)

        handoff = transcript["predecessor_handoff_validation"]
        legal_branches = [
            "Q87_FAILURE_Q88_NOT_ATTEMPTED",
            "Q87_RESOURCE_ABORT_Q88_NOT_ATTEMPTED",
            "Q87_SUCCESS_Q88_FAILURE",
            "Q87_SUCCESS_Q88_RESOURCE_ABORT",
            "Q87_AND_Q88_SUCCESS_HORIZON_REACHED",
        ]
        self.assertEqual(handoff["legal_terminal_branches"], legal_branches)
        self.assertEqual(handoff["terminal_branch"], legal_branches[2])
        self.assertTrue(handoff["q1_through_q86_records_exact"])
        self.assertTrue(
            handoff["q1_through_q86_all_33_candidate_rows_exact"]
        )
        self.assertTrue(handoff["q1_through_q86_selected_history_exact"])
        self.assertTrue(handoff["q88_checkpoint_record_constructed"])
        self.assertFalse(handoff["resource_policy_abort_structured"])
        self.assertIsNone(handoff["resource_policy_abort_checkpoint"])
        self.assertIsNone(handoff["resource_policy_abort_kind"])
        self.assertIsNone(handoff["resource_policy_abort_sha256"])

        components = transcript["screen_execution_components"]
        custody = transcript["source_custody"]
        self.assertEqual(len(components), 11)
        self.assertEqual(len(custody), 10)
        self.assertEqual(
            components,
            SCREEN.execution_components(
                copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)),
                EXPECTED_SCREEN_SHA256,
            ),
        )
        self.assertEqual(
            custody,
            SCREEN.expected_final_source_custody(EXPECTED_SCREEN_SHA256),
        )
        component_paths = [item["relative_path"] for item in components]
        self.assertEqual(len(component_paths), len(set(component_paths)))
        self.assertNotIn(CANONICAL_NAME, component_paths)
        self.assertNotIn(CANONICAL_NAME, custody)
        self.assertEqual(
            digest(components), transcript["screen_execution_components_sha256"]
        )
        self.assertEqual(
            digest(handoff),
            transcript["predecessor_handoff_validation_sha256"],
        )
        for relative_path, expected_sha in custody.items():
            self.assertEqual(
                hashlib.sha256((HERE / relative_path).read_bytes()).hexdigest(),
                expected_sha,
            )

    @unittest.skipUnless(
        os.environ.get("FERMION_RUN_M606208_C33_Q88_REPLAY") == "1",
        "expensive deterministic q88 replay is opt-in",
    )
    def test_12_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        raw = canonical_bytes(result)
        canonical_path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(canonical_path.is_file())
        self.assertEqual(raw, canonical_path.read_bytes())
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            EXPECTED_CANONICAL["file_sha256"],
        )
        self.assertEqual(len(result["records"]), 88)
        self.assertEqual(result["records"][:86], self.anchor["records"])
        self.assertEqual(
            result["predecessor_handoff_validation"]["terminal_branch"],
            "Q87_SUCCESS_Q88_FAILURE",
        )


if __name__ == "__main__":
    unittest.main(module=types.SimpleNamespace(**globals()))
