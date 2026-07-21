#!/usr/bin/env python3
"""Static, synthetic and opt-in tests for the D K606208/C35 q72 screen."""

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
    "k606208_c35_q72_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "54601418ab5aa2b6c887d928ad6c87fa0cff558c0558d106961201d291cc33fe"
)
EXPECTED_CANONICAL = {
    "file_sha256": "f21288cf0c37dc86fedc9ac195f4efe390dcc913640caa7ca79f02e6297d20f8",
    "file_size": 708_344,
    "candidate_sha256": "d69acf8cdc4e598e9734abe68a4d0a83cf7ea0618d38932b02c94c0aa8bfd161",
    "records_sha256": "d1a76c90065cead72388d0ce0712273fe3184dd06d25ecbea24c7b03f04d165f",
    "history_sha256": "d57dfeffe7e5e0056ad1b0294a015852af7788fe23187aad9d4484683f8f1cba",
    "failure_sha256": "ca1558715a87ca8d728bf511cce4a3d63c06828572d835f6005214d0ae021749",
    "components_sha256": "420da6713b0b837d25b54275724810054a12d3e3680f64398805b7c6e267ae22",
    "configuration_reference_sha256": "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1",
    "configuration_override_sha256": "b2b55b96b9f29a2731e60625ca6c40ffc254901740f8ef66aaf7b3e906411e35",
    "kernel_override_sha256": "41be637814a62b1b8f122aa113ce2be575f00cf21322b9d137e292d186e461a7",
    "parent_horizon_override_sha256": "6260d69cff7e23c4f725e81f1db2d2edd057a2a2b73bbf2b5fc99382003db6b7",
    "route_reference_sha256": "f661416c9751b50f6bd9753fca8c1b4d57e743ee9b4556a103d296417fffc861",
    "handoff_sha256": "2b218fd138d85c06a59b94736ecd3a1b093fef7d729e8409e7daa55a060f05c2",
    "transform_sha256": "7767fa4b9bc3c1e9de5fa898d0c46bcb65fa26598678e3c8234f6f08ee61278e",
    "parent_witness_sha256": "b63bcf3b6b8b920630e639215281cd04c065e5226aa430dd417a5515df8ad623",
    "q71_rows_sha256": "3685bc6658c10da59d18e38a1502942f9dc6b3c2f33cd67d75aadf655c1dba5f",
    "q71_max_row_sha256": "e5d7823d68c5b8f4c9f3fc1aba4402c283d0e49b48b6722c15c7b5d21cd99731",
    "q71_counterfactual_sha256": "82d3b40703933412fcf9699477b288b0849649a420da3d34803ddfb1fef30210",
    "last_E": "2288871542213247",
    "peak": 761_190,
    "visits": 90_141_781,
    "coefficient_bits": 63,
    "product_bits": 120,
    "rounding": "123664802029635999140292783",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("double_occupancy_k606208_c35_q72_for_tests", SCREEN_NAME)


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


class DoubleOccupancyK606208C35Q72Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.anchor, self.route_reference = SCREEN.load_route_reference(HERE)

    @staticmethod
    def _record_sha(checkpoint: int, label: str) -> str:
        return sha256(f"synthetic-q{checkpoint}-{label}".encode("ascii"))

    def make_extended_record(self, previous, checkpoint, success):
        record = copy.deepcopy(self.anchor["records"][69])
        E_before = int(previous["E_after_ticks"])
        prefix_cap = int(
            SCREEN.EXPECTED_Q71_PREFIX_CAP_TICKS
            if checkpoint == 71
            else SCREEN.EXPECTED_Q72_PREFIX_CAP_TICKS
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
            "pretruncation_expansion_sha256": self._record_sha(
                checkpoint, "pretruncation"
            ),
            "ranked_suffix_sha256": self._record_sha(checkpoint, "suffix"),
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
            "maximum_expansion_coefficient_tick_bits": (
                previous["maximum_expansion_coefficient_tick_bits"]
            ),
            "maximum_product_bits": previous["maximum_product_bits"],
            "rounding_increment_scaled_ticks_squared": "1",
            "rounding_cumulative_scaled_ticks_squared": str(
                int(previous["rounding_cumulative_scaled_ticks_squared"]) + 1
            ),
        })
        rows = []
        for index, configured_K in enumerate(SCREEN.D_CANDIDATES):
            effective = min(configured_K, pre_count)
            drop = (35 - index) if success else (slack + 35 - index)
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
        counterfactual_drop = (
            int(rows[28]["drop_ticks"]) + int(rows[29]["drop_ticks"])
        ) // 2
        record["removed_491520_counterfactual"] = {
            "configured_K": 491_520,
            "effective_retained_count": 491_520,
            "dropped_term_count": pre_count - 491_520,
            "drop_ticks": str(counterfactual_drop),
            "E_after_if_selected_ticks": str(E_before + counterfactual_drop),
            "feasible_under_current_prefix_cap": counterfactual_drop <= slack,
            "actual_selected_K": None,
            "would_precede_selected": False,
            "would_be_selected_if_inserted": False,
        }

        if success:
            selected = rows[0]
            for key in SCREEN.Q70_FAILURE_ONLY_KEYS:
                record.pop(key, None)
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 0,
                "selected_K": SCREEN.D_CANDIDATES[0],
                "selected_effective_retained_count": (
                    selected["effective_retained_count"]
                ),
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": self._record_sha(
                    checkpoint, "dropped"
                ),
                "retained_expansion_count": selected["effective_retained_count"],
                "retained_expansion_sha256": self._record_sha(
                    checkpoint, "retained"
                ),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "1",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
            record["removed_491520_counterfactual"]["actual_selected_K"] = (
                SCREEN.D_CANDIDATES[0]
            )
        else:
            for key in SCREEN.Q70_SUCCESS_ONLY_KEYS:
                record.pop(key, None)
            record.update({
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "selected_candidate_index": None,
                "selected_K": None,
                "minimum_effective_K_to_meet_prefix": SCREEN.K606208 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

    def make_raw_result(self, branch):
        result = {
            key: copy.deepcopy(self.anchor[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        result.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_horizon_checkpoint_count": SCREEN.EXTENDED_HORIZON,
        })
        components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        result["screen_execution_components"] = components
        result["screen_execution_components_sha256"] = sha256(
            canonical_bytes(components)
        )
        configuration = {"synthetic_raw_configuration_reference": True}
        result["configuration_reference"] = configuration
        result["configuration_reference_sha256"] = sha256(
            canonical_bytes(configuration)
        )
        transform = copy.deepcopy(
            self.anchor["checkpoint_transform"]
            ["physical_four_gate_control_flow_parent_transform"]
        )
        result["checkpoint_transform"] = transform
        result["checkpoint_transform_sha256"] = sha256(
            canonical_bytes(transform)
        )
        result["source_custody"] = copy.deepcopy(
            SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY
        )

        records = copy.deepcopy(self.anchor["records"])
        history = list(self.anchor["selected_K_history"])
        if branch == "q71_failure":
            q71 = self.make_extended_record(records[-1], 71, False)
            records.append(q71)
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            horizon_attempted = False
            horizon_committed = False
            last_E = SCREEN.EXPECTED_Q70_E_AFTER_TICKS
        elif branch in {"q72_failure", "q72_success"}:
            q71 = self.make_extended_record(records[-1], 71, True)
            records.append(q71)
            history.append(q71["selected_K"])
            q72 = self.make_extended_record(
                records[-1], 72, branch == "q72_success"
            )
            records.append(q72)
            horizon_attempted = True
            if branch == "q72_failure":
                terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                horizon_committed = False
                last_E = q71["E_after_ticks"]
            else:
                terminal = "DIAGNOSTIC_HORIZON_REACHED"
                horizon_committed = True
                history.append(q72["selected_K"])
                last_E = q72["E_after_ticks"]
        else:
            raise AssertionError(branch)

        final = records[-1]
        failed = final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        result.update({
            "records": records,
            "records_sha256": sha256(canonical_bytes(records)),
            "selected_K_history": history,
            "selected_K_history_sha256": sha256(canonical_bytes(history)),
            "attempted_checkpoint_count": len(records),
            "completed_checkpoint_count": len(history),
            "screen_terminal_condition": terminal,
            "horizon_checkpoint_attempted": horizon_attempted,
            "horizon_reached_with_committed_checkpoint": horizon_committed,
            "failure_checkpoint_included": failed,
            "failure_record_sha256": (
                sha256(canonical_bytes(final)) if failed else None
            ),
            "last_committed_cumulative_drop_ticks": last_E,
            "observed_peak_single_expansion_terms": final[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": final[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": max(
                record["maximum_expansion_coefficient_tick_bits"]
                for record in records
            ),
            "observed_maximum_product_bits": max(
                record["maximum_product_bits"] for record in records
            ),
            "observed_rounding_cumulative_scaled_ticks_squared": final[
                "rounding_cumulative_scaled_ticks_squared"
            ],
        })
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return result

    def load_static_bundle(self):
        fresh = SCREEN.fresh_self_module()
        parent = fresh.load_control_flow_parent(HERE)
        configuration, baseline_d = fresh.load_configured_v6_baseline(HERE)
        kernel, wrapper_sha, manifest = fresh.load_kernel_wrapper(HERE)
        predecessor, route_reference = fresh.load_route_reference(HERE)
        return (
            fresh,
            parent,
            configuration,
            baseline_d,
            kernel,
            wrapper_sha,
            manifest,
            predecessor,
            route_reference,
        )

    def test_01_exact_source_and_q70_route_pins(self):
        self_payload = (HERE / SCREEN.SELF_NAME).read_bytes()
        route_screen = (HERE / SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME).read_bytes()
        route_raw = (HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(sha256(self_payload), EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            sha256(route_screen), SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256
        )
        self.assertEqual(
            sha256(route_raw), SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256
        )
        self.assertEqual(route_raw, canonical_bytes(json.loads(route_raw)))
        self.assertEqual(
            sha256(canonical_bytes(self.anchor["records"])),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(self.anchor["selected_K_history"])),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(self.anchor["records"][69])),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q70_RECORD_SHA256,
        )
        self.assertEqual(
            frozenset(self.anchor), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )

        fresh = SCREEN.fresh_self_module()
        self.assertIsNot(fresh, SCREEN)
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, self_payload)
        first, _ = fresh.load_route_reference(HERE)
        second, _ = fresh.load_route_reference(HERE)
        self.assertIsNot(first, second)

    def test_02_same_cap_configuration_kernel_and_direct_parent(self):
        SCREEN.validate_local_configuration()
        bundle = self.load_static_bundle()
        fresh, parent, configuration, baseline_d, kernel = bundle[:5]
        wrapper_sha, manifest = bundle[5:7]
        self.assertEqual(len(SCREEN.D_CANDIDATES), 35)
        self.assertEqual(
            configuration.MODE_CONFIG[SCREEN.MODE]["candidates"],
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(kernel.RESOURCE_LIMITS, SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS)
        self.assertEqual(wrapper_sha, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(
            sha256(canonical_bytes(manifest)),
            SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256,
        )
        before_m = copy.deepcopy(parent.MODE_CONFIG["magnetization"])
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        self.assertEqual(
            parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 72
        )
        self.assertEqual(parent.MODE_CONFIG["magnetization"], before_m)
        self.assertEqual(
            horizon["semantic_delta"],
            {
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count": {
                    "before": 66,
                    "after": 72,
                }
            },
        )
        helper = parent.load_v2_helper(HERE)
        runtime_kernel, root, _modules, _custody = parent.load_execution_sources(
            HERE,
            helper,
            SCREEN.MODE,
        )
        stages, _trig, _sequence, _transform = parent.build_four_gate_sequence(
            helper,
            root,
            runtime_kernel,
        )
        checkpoint = 0
        derived = {}
        for stage_index, stage in enumerate(stages):
            stage_gates = stage["gates"]
            for batch_start in range(0, len(stage_gates), 4):
                checkpoint += 1
                if checkpoint in (71, 72):
                    batch = stage_gates[batch_start:batch_start + 4]
                    derived[checkpoint] = {
                        "stage_index": stage_index,
                        "stage_group": stage["group"],
                        "batch_in_stage": batch_start // 4,
                        "gate_batch_sha256": helper.gate_batch_sha256(batch),
                    }
        self.assertEqual(derived, SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS)

        config = fresh.configuration_override(baseline_d)
        incremental = config["incremental_route_override_from_k606208_c35_q70"]
        self.assertEqual(incremental["candidate_count"], {"before": 35, "after": 35})
        self.assertEqual(incremental["candidate_ladder_added"], [])
        self.assertEqual(incremental["candidate_ladder_removed"], [])
        self.assertEqual(incremental["policy_cap_changes"], {})
        capability = fresh.kernel_capability_override(wrapper_sha, manifest)
        self.assertEqual(
            capability["incremental_route_changes_from_k606208_c35_q70"], {}
        )

        components = fresh.execution_components(
            list(fresh.EXPECTED_PARENT_EXECUTION_COMPONENTS),
            EXPECTED_SCREEN_SHA256,
            wrapper_sha,
        )
        paths = {item["relative_path"] for item in components}
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, paths)

    def test_03_q71_failure_branch_and_exact_q70_prefix(self):
        result = self.make_raw_result("q71_failure")
        handoff = SCREEN.validate_replay_handoff(result, self.anchor)
        self.assertEqual(handoff["terminal_branch"], "Q71_FAILURE_Q72_NOT_ATTEMPTED")
        self.assertEqual(result["attempted_checkpoint_count"], 71)
        self.assertEqual(result["completed_checkpoint_count"], 70)
        self.assertFalse(result["horizon_checkpoint_attempted"])
        self.assertEqual(result["records"][:70], self.anchor["records"])
        self.assertEqual(
            result["selected_K_history"], self.anchor["selected_K_history"]
        )
        self.assertEqual(
            result["records"][70]["input_expansion_count"], SCREEN.K606208
        )
        self.assertEqual(
            result["records"][70]["input_expansion_sha256"],
            SCREEN.EXPECTED_Q70_RETAINED_EXPANSION_SHA256,
        )
        self.assertEqual(
            result["records"][70]["E_before_ticks"],
            SCREEN.EXPECTED_Q70_E_AFTER_TICKS,
        )

    def test_04_q72_failure_and_q72_success_branches(self):
        failure = self.make_raw_result("q72_failure")
        failure_handoff = SCREEN.validate_replay_handoff(failure, self.anchor)
        self.assertEqual(
            failure_handoff["terminal_branch"], "Q71_SUCCESS_Q72_FAILURE"
        )
        self.assertEqual((len(failure["records"]), len(failure["selected_K_history"])), (72, 71))
        self.assertTrue(failure["horizon_checkpoint_attempted"])
        self.assertFalse(failure["horizon_reached_with_committed_checkpoint"])

        success = self.make_raw_result("q72_success")
        success_handoff = SCREEN.validate_replay_handoff(success, self.anchor)
        self.assertEqual(
            success_handoff["terminal_branch"],
            "Q71_AND_Q72_SUCCESS_HORIZON_REACHED",
        )
        self.assertEqual((len(success["records"]), len(success["selected_K_history"])), (72, 72))
        self.assertIsNone(success["failure_record_sha256"])
        self.assertTrue(success["horizon_reached_with_committed_checkpoint"])

    def test_05_illegal_terminal_paths_fail_closed(self):
        q71_failure = self.make_raw_result("q71_failure")
        q71_failure["records"].append(
            self.make_extended_record(q71_failure["records"][-2], 72, True)
        )
        q71_failure["records_sha256"] = sha256(
            canonical_bytes(q71_failure["records"])
        )
        with self.assertRaisesRegex(RuntimeError, "terminate before q72"):
            SCREEN.validate_replay_handoff(q71_failure, self.anchor)

        q71_success_without_q72 = self.make_raw_result("q72_success")
        q71_success_without_q72["records"].pop()
        q71_success_without_q72["selected_K_history"].pop()
        q71_success_without_q72["records_sha256"] = sha256(
            canonical_bytes(q71_success_without_q72["records"])
        )
        q71_success_without_q72["selected_K_history_sha256"] = sha256(
            canonical_bytes(q71_success_without_q72["selected_K_history"])
        )
        with self.assertRaisesRegex(RuntimeError, "must continue through q72"):
            SCREEN.validate_replay_handoff(q71_success_without_q72, self.anchor)

        bad_history = self.make_raw_result("q72_failure")
        bad_history["selected_K_history"][-1] += 1
        bad_history["selected_K_history_sha256"] = sha256(
            canonical_bytes(bad_history["selected_K_history"])
        )
        with self.assertRaisesRegex(RuntimeError, "exact replay ledger"):
            SCREEN.validate_replay_handoff(bad_history, self.anchor)

    def test_06_closed_raw_record_row_and_counterfactual_schemas(self):
        self.assertEqual(len(SCREEN.EXPECTED_PARENT_RESULT_KEYS), 65)
        self.assertEqual(len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS), 94)
        self.assertEqual(len(SCREEN.Q70_SUCCESS_RECORD_KEYS), 38)
        self.assertEqual(len(SCREEN.Q70_FAILURE_RECORD_KEYS), 32)
        self.assertEqual(len(SCREEN.CANDIDATE_RECORD_KEYS), 7)
        self.assertEqual(len(SCREEN.REMOVED_COUNTERFACTUAL_KEYS), 9)

        cases = []
        raw_extra = self.make_raw_result("q72_success")
        raw_extra["unexpected"] = True
        cases.append((raw_extra, "raw parent top-level"))
        raw_missing = self.make_raw_result("q72_success")
        raw_missing.pop("sequence")
        cases.append((raw_missing, "raw parent top-level"))
        success_extra = self.make_raw_result("q72_success")
        success_extra["records"][70]["unexpected"] = True
        cases.append((success_extra, "q71 record"))
        success_missing = self.make_raw_result("q72_success")
        success_missing["records"][70].pop("selected_drop_ticks")
        cases.append((success_missing, "q71 record"))
        failure_extra = self.make_raw_result("q71_failure")
        failure_extra["records"][70]["unexpected"] = True
        cases.append((failure_extra, "q71 record"))
        failure_missing = self.make_raw_result("q71_failure")
        failure_missing["records"][70].pop("minimum_effective_K_to_meet_prefix")
        cases.append((failure_missing, "q71 record"))
        row_extra = self.make_raw_result("q72_success")
        row_extra["records"][70]["candidate_records"][0]["unexpected"] = True
        cases.append((row_extra, "candidate row 0"))
        counter_missing = self.make_raw_result("q72_success")
        counter_missing["records"][70]["removed_491520_counterfactual"].pop(
            "actual_selected_K"
        )
        cases.append((counter_missing, "removed-491520 counterfactual"))
        for result, label in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(RuntimeError, "exact key-set drift"):
                    SCREEN.validate_replay_handoff(result, self.anchor)

    def test_07_prefix_and_q71_q72_anchor_tampering_is_rejected(self):
        result = self.make_raw_result("q72_success")
        result["records"][0]["E_before_ticks"] = "-1"
        result["records_sha256"] = sha256(canonical_bytes(result["records"]))
        with self.assertRaisesRegex(RuntimeError, "exact q1-70 record prefix"):
            SCREEN.validate_replay_handoff(result, self.anchor)

        result = self.make_raw_result("q72_success")
        result["selected_K_history"][0] += 1
        result["selected_K_history_sha256"] = sha256(
            canonical_bytes(result["selected_K_history"])
        )
        with self.assertRaisesRegex(RuntimeError, "exact q1-70 selected history"):
            SCREEN.validate_replay_handoff(result, self.anchor)

        for checkpoint, field in (
            (70, "input_expansion_count"),
            (70, "input_expansion_sha256"),
            (70, "E_before_ticks"),
            (70, "budget_prefix_cap_ticks"),
            (70, "stage_index"),
            (70, "stage_group"),
            (70, "batch_in_stage"),
            (70, "gate_batch_sha256"),
            (71, "budget_prefix_cap_ticks"),
            (71, "stage_index"),
            (71, "stage_group"),
            (71, "batch_in_stage"),
            (71, "gate_batch_sha256"),
        ):
            result = self.make_raw_result("q72_success")
            result["records"][checkpoint][field] = "tampered"
            result["records_sha256"] = sha256(canonical_bytes(result["records"]))
            with self.subTest(checkpoint=checkpoint + 1, field=field):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(result, self.anchor)

    def test_08_synthetic_relabel_has_exact_authority_and_provenance(self):
        bundle = self.load_static_bundle()
        fresh, parent, configuration, baseline_d, kernel = bundle[:5]
        wrapper_sha, manifest, predecessor, route_reference = bundle[5:]
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)
        result = fresh.validate_and_relabel(
            self.make_raw_result("q72_success"),
            predecessor,
            route_reference,
            baseline_d,
            wrapper_sha,
            manifest,
            horizon,
        )
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS)
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k606208_c35_q72_screen_v1",
        )
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        paths = {
            item["relative_path"]
            for item in result["screen_execution_components"]
        }
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, paths)
        reference = result["route_predecessor_reference"]
        for layer in (reference["screen"], reference["canonical_transcript"]):
            self.assertFalse(layer["executed"] if "executed" in layer else False)
            self.assertFalse(layer["execution_source_layer"])
        canonical = reference["canonical_transcript"]
        self.assertTrue(canonical["post_replay_prefix_validation_input"])
        self.assertFalse(canonical["propagation_input"])
        self.assertFalse(canonical["checkpoint_70_state_loaded"])
        self.assertFalse(canonical["state_resume_input"])
        self.assertEqual(
            result["checkpoint_transform"]["incremental_route_semantic_delta"],
            {
                "candidate_K_values_changed": False,
                "policy_caps_changed": False,
                "kernel_capability_limits_changed": False,
                "horizon_checkpoint_count": {"before": 70, "after": 72},
            },
        )
        for digest_field, value_field in (
            ("screen_execution_components_sha256", "screen_execution_components"),
            ("configuration_reference_sha256", "configuration_reference"),
            ("configuration_override_sha256", "configuration_override"),
            ("kernel_capability_override_sha256", "kernel_capability_override"),
            ("parent_horizon_override_sha256", "parent_horizon_override"),
            ("route_predecessor_reference_sha256", "route_predecessor_reference"),
            ("predecessor_handoff_validation_sha256", "predecessor_handoff_validation"),
            ("checkpoint_transform_sha256", "checkpoint_transform"),
        ):
            self.assertEqual(
                result[digest_field], sha256(canonical_bytes(result[value_field]))
            )

    def test_09_public_fresh_path_resource_identity_and_atomic_output(self):
        sentinel = {"fresh": True}

        class Fresh:
            @staticmethod
            def _run_verified(repo):
                self.assertEqual(repo, HERE)
                return sentinel

        original_fresh = SCREEN.fresh_self_module
        original_private = SCREEN._run_verified
        try:
            SCREEN._run_verified = lambda *_args: self.fail("live module used")
            SCREEN.fresh_self_module = lambda: Fresh()
            self.assertIs(SCREEN.run(HERE), sentinel)
        finally:
            SCREEN.fresh_self_module = original_fresh
            SCREEN._run_verified = original_private

        fresh = SCREEN.fresh_self_module()
        resource_error = RuntimeError("D q72 resource sentinel")

        def fail_parent(_repo):
            raise resource_error

        fresh.load_control_flow_parent = fail_parent
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "D-q72.json"
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

    def test_10_parent_and_final_custody_are_exactly_closed(self):
        bundle = self.load_static_bundle()
        fresh, parent, configuration, baseline_d, kernel = bundle[:5]
        wrapper_sha, manifest, predecessor, route_reference = bundle[5:]
        horizon = fresh.configure_parent_execution(parent, configuration, kernel)

        def relabel(result):
            return fresh.validate_and_relabel(
                result,
                predecessor,
                route_reference,
                baseline_d,
                wrapper_sha,
                manifest,
                horizon,
            )

        valid = relabel(self.make_raw_result("q72_success"))
        self.assertEqual(len(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY), 7)
        self.assertEqual(len(valid["source_custody"]), 10)
        self.assertEqual(
            valid["source_custody"],
            SCREEN.expected_final_source_custody(
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            ),
        )

        custody_cases = []
        missing = self.make_raw_result("q72_success")
        missing["source_custody"].pop(
            "hubbard_l8_adaptive_k_v2_design_probe.py"
        )
        custody_cases.append(("missing", missing, "exact key-set drift"))

        extra = self.make_raw_result("q72_success")
        extra["source_custody"]["unexpected.py"] = "0" * 64
        custody_cases.append(("extra", extra, "exact key-set drift"))

        wrong_hash = self.make_raw_result("q72_success")
        wrong_hash["source_custody"][SCREEN.V2_ARITHMETIC_NAME] = "0" * 64
        custody_cases.append(("hash", wrong_hash, "hash drift"))

        wrong_path = self.make_raw_result("q72_success")
        value = wrong_path["source_custody"].pop(
            "hubbard_l8_observable_interval_step_checker.py"
        )
        wrong_path["source_custody"][
            "hubbard_l8_observable_interval_step_checker_renamed.py"
        ] = value
        custody_cases.append(("path", wrong_path, "exact key-set drift"))

        wrong_schema = self.make_raw_result("q72_success")
        wrong_schema["source_custody"] = list(
            wrong_schema["source_custody"].items()
        )
        custody_cases.append(("schema", wrong_schema, "not an exact dict"))

        for label, result, pattern in custody_cases:
            with self.subTest(custody=label):
                with self.assertRaisesRegex(RuntimeError, pattern):
                    relabel(result)

        component_cases = []
        missing_component = self.make_raw_result("q72_success")
        missing_component["screen_execution_components"].pop()
        component_cases.append(("missing", missing_component))

        extra_component = self.make_raw_result("q72_success")
        extra_component["screen_execution_components"].append({
            "relative_path": "unexpected.py",
            "role": "unexpected",
            "sha256": "0" * 64,
        })
        component_cases.append(("extra", extra_component))

        wrong_component_hash = self.make_raw_result("q72_success")
        wrong_component_hash["screen_execution_components"][0]["sha256"] = (
            "0" * 64
        )
        component_cases.append(("hash", wrong_component_hash))

        wrong_component_path = self.make_raw_result("q72_success")
        wrong_component_path["screen_execution_components"][0][
            "relative_path"
        ] = "renamed_parent.py"
        component_cases.append(("path", wrong_component_path))

        wrong_component_role = self.make_raw_result("q72_success")
        wrong_component_role["screen_execution_components"][0]["role"] = (
            "public_entrypoint"
        )
        component_cases.append(("role", wrong_component_role))

        for label, result in component_cases:
            result["screen_execution_components_sha256"] = sha256(
                canonical_bytes(result["screen_execution_components"])
            )
            with self.subTest(component=label):
                with self.assertRaisesRegex(
                    RuntimeError, "component schema drift"
                ):
                    relabel(result)

    def test_11_counterfactual_adjacency_and_choice_are_fail_closed(self):
        failure = self.make_raw_result("q71_failure")
        q71 = failure["records"][70]
        slack = int(q71["prefix_slack_before_selection_ticks"])
        E_before = int(q71["E_before_ticks"])
        counterfactual = q71["removed_491520_counterfactual"]
        counterfactual.update({
            "drop_ticks": str(slack),
            "E_after_if_selected_ticks": str(E_before + slack),
            "feasible_under_current_prefix_cap": True,
            "would_precede_selected": False,
            "would_be_selected_if_inserted": False,
        })
        failure["records_sha256"] = sha256(canonical_bytes(failure["records"]))
        failure["failure_record_sha256"] = sha256(canonical_bytes(q71))
        with self.assertRaisesRegex(RuntimeError, "counterfactual"):
            SCREEN.validate_replay_handoff(failure, self.anchor)

        q70 = self.anchor["records"][69]
        positive = self.make_extended_record(q70, 71, True)
        slack = int(positive["prefix_slack_before_selection_ticks"])
        E_before = int(positive["E_before_ticks"])
        rows = positive["candidate_records"]
        for index, row in enumerate(rows):
            if index <= 28:
                drop = slack + 29 - index
            else:
                drop = slack - (index - 29)
            row.update({
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(E_before + drop),
                "feasible_under_current_prefix_cap": drop <= slack,
            })
        selected = rows[29]
        positive.update({
            "selected_candidate_index": 29,
            "selected_K": 507_904,
            "selected_effective_retained_count": (
                selected["effective_retained_count"]
            ),
            "selected_dropped_term_count": selected["dropped_term_count"],
            "selected_drop_ticks": selected["drop_ticks"],
            "retained_expansion_count": selected["effective_retained_count"],
            "E_after_ticks": selected["E_after_if_selected_ticks"],
        })
        positive["removed_491520_counterfactual"].update({
            "drop_ticks": str(slack),
            "E_after_if_selected_ticks": str(E_before + slack),
            "feasible_under_current_prefix_cap": True,
            "actual_selected_K": 507_904,
            "would_precede_selected": True,
            "would_be_selected_if_inserted": True,
        })
        self.assertEqual(
            SCREEN.validate_extended_record(positive, q70, 71),
            507_904,
        )
        for field in (
            "would_precede_selected",
            "would_be_selected_if_inserted",
        ):
            tampered = copy.deepcopy(positive)
            tampered["removed_491520_counterfactual"][field] = False
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError, "counterfactual"):
                    SCREEN.validate_extended_record(tampered, q70, 71)

    def test_12_digest_and_cumulative_maxima_tampering_is_rejected(self):
        def rehash(result):
            result["records_sha256"] = sha256(
                canonical_bytes(result["records"])
            )
            final = result["records"][-1]
            if final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
                result["failure_record_sha256"] = sha256(
                    canonical_bytes(final)
                )

        for branch in ("q71_failure", "q72_failure", "q72_success"):
            baseline = self.make_raw_result(branch)
            for record_index in range(70, len(baseline["records"])):
                for field in (
                    "pretruncation_expansion_sha256",
                    "ranked_suffix_sha256",
                ):
                    for bad_value in (7, "not-a-canonical-sha"):
                        result = copy.deepcopy(baseline)
                        result["records"][record_index][field] = bad_value
                        rehash(result)
                        with self.subTest(
                            branch=branch,
                            checkpoint=record_index + 1,
                            field=field,
                            bad_type=type(bad_value).__name__,
                        ):
                            with self.assertRaisesRegex(
                                RuntimeError, "digest schema drift"
                            ):
                                SCREEN.validate_replay_handoff(
                                    result,
                                    self.anchor,
                                )

        for branch in ("q71_failure", "q72_success"):
            for record_field, top_field in (
                (
                    "maximum_expansion_coefficient_tick_bits",
                    "observed_maximum_expansion_coefficient_tick_bits",
                ),
                ("maximum_product_bits", "observed_maximum_product_bits"),
            ):
                result = self.make_raw_result(branch)
                for record in result["records"][70:]:
                    record[record_field] = 0
                result[top_field] = 0
                rehash(result)
                with self.subTest(
                    branch=branch,
                    cumulative_field=record_field,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "cumulative maximum decreased"
                    ):
                        SCREEN.validate_replay_handoff(result, self.anchor)

        for record_field, top_field in (
            (
                "maximum_expansion_coefficient_tick_bits",
                "observed_maximum_expansion_coefficient_tick_bits",
            ),
            ("maximum_product_bits", "observed_maximum_product_bits"),
        ):
            result = self.make_raw_result("q72_failure")
            previous = result["records"][70][record_field]
            result["records"][71][record_field] = previous - 1
            result[top_field] = previous - 1
            rehash(result)
            with self.subTest(q72_failure_cumulative_field=record_field):
                with self.assertRaisesRegex(
                    RuntimeError, "cumulative maximum decreased"
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        for top_field in (
            "observed_maximum_expansion_coefficient_tick_bits",
            "observed_maximum_product_bits",
        ):
            result = self.make_raw_result("q72_success")
            result[top_field] += 1
            with self.subTest(top_field=top_field):
                with self.assertRaisesRegex(
                    RuntimeError, "observed resource ledger drift"
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        for branch, record_index, bad_peak in (
            ("q71_failure", 70, 0),
            ("q72_success", 71, 699_999),
        ):
            result = self.make_raw_result(branch)
            record = result["records"][record_index]
            self.assertLess(
                bad_peak,
                max(
                    record["input_expansion_count"],
                    record["pretruncation_expansion_count"],
                ),
            )
            record["peak_live_terms_this_checkpoint"] = bad_peak
            record["peak_live_terms_cumulative"] = result["records"][
                record_index - 1
            ]["peak_live_terms_cumulative"]
            result["observed_peak_single_expansion_terms"] = result["records"][
                -1
            ]["peak_live_terms_cumulative"]
            rehash(result)
            with self.subTest(branch=branch, bad_peak=bad_peak):
                with self.assertRaisesRegex(
                    RuntimeError, "checkpoint peak below live terms"
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        wrong_peak_top = self.make_raw_result("q72_success")
        wrong_peak_top["observed_peak_single_expansion_terms"] += 1
        with self.assertRaisesRegex(
            RuntimeError, "observed resource ledger drift"
        ):
            SCREEN.validate_replay_handoff(wrong_peak_top, self.anchor)

        for branch, record_index in (
            ("q71_failure", 70),
            ("q72_success", 71),
        ):
            result = self.make_raw_result(branch)
            record = result["records"][record_index]
            record["term_gate_visits_increment"] = 0
            record["term_gate_visits_cumulative"] = result["records"][
                record_index - 1
            ]["term_gate_visits_cumulative"]
            result["observed_term_gate_visits_including_terminal_attempt"] = (
                result["records"][-1]["term_gate_visits_cumulative"]
            )
            rehash(result)
            with self.subTest(branch=branch, zero_gate_visits=True):
                with self.assertRaisesRegex(
                    RuntimeError, "gate visits below first-gate input"
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        for branch, record_index in (
            ("q71_failure", 70),
            ("q72_success", 71),
        ):
            for violation in ("pretruncation", "peak", "visits"):
                result = self.make_raw_result(branch)
                record = result["records"][record_index]
                if violation == "pretruncation":
                    value = min(
                        SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"],
                        SCREEN.POLICY_CAPS_BASE["max_digest_terms"],
                    ) + 1
                    record["pretruncation_expansion_count"] = value
                    record["peak_live_terms_this_checkpoint"] = value
                    record["peak_live_terms_cumulative"] = max(
                        result["records"][record_index - 1][
                            "peak_live_terms_cumulative"
                        ],
                        value,
                    )
                    result["observed_peak_single_expansion_terms"] = result[
                        "records"
                    ][-1]["peak_live_terms_cumulative"]
                elif violation == "peak":
                    value = (
                        SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"]
                        + 1
                    )
                    record["peak_live_terms_this_checkpoint"] = value
                    record["peak_live_terms_cumulative"] = value
                    result["observed_peak_single_expansion_terms"] = result[
                        "records"
                    ][-1]["peak_live_terms_cumulative"]
                else:
                    value = SCREEN.POLICY_CAPS_BASE["max_term_gate_visits"] + 1
                    previous_visits = result["records"][record_index - 1][
                        "term_gate_visits_cumulative"
                    ]
                    record["term_gate_visits_increment"] = value - previous_visits
                    record["term_gate_visits_cumulative"] = value
                    result[
                        "observed_term_gate_visits_including_terminal_attempt"
                    ] = result["records"][-1]["term_gate_visits_cumulative"]
                rehash(result)
                with self.subTest(
                    branch=branch,
                    policy_cap_violation=violation,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "exceed[s]? policy cap"
                    ):
                        SCREEN.validate_replay_handoff(result, self.anchor)

        decimal_cases = []
        integer_rounding = self.make_raw_result("q71_failure")
        integer_rounding["records"][70][
            "rounding_increment_scaled_ticks_squared"
        ] = 1
        decimal_cases.append(("integer-rounding", integer_rounding))

        leading_zero_drop = self.make_raw_result("q71_failure")
        leading_zero_drop["records"][70]["candidate_records"][0][
            "drop_ticks"
        ] = "00"
        decimal_cases.append(("leading-zero-drop", leading_zero_drop))

        signed_interval = self.make_raw_result("q72_success")
        signed_interval["records"][70][
            "minimum_retained_abs_upper_ticks"
        ] = "+1"
        decimal_cases.append(("signed-success-interval", signed_interval))

        integer_counterfactual = self.make_raw_result("q72_failure")
        integer_counterfactual["records"][71][
            "removed_491520_counterfactual"
        ]["E_after_if_selected_ticks"] = 1
        decimal_cases.append(("integer-counterfactual", integer_counterfactual))

        integer_failure_excess = self.make_raw_result("q72_failure")
        integer_failure_excess["records"][71][
            "maximum_candidate_drop_excess_over_slack_ticks"
        ] = 1
        decimal_cases.append(("integer-failure-excess", integer_failure_excess))

        for label, result in decimal_cases:
            rehash(result)
            with self.subTest(decimal_schema=label):
                with self.assertRaisesRegex(
                    RuntimeError, "canonical decimal string"
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        impossible_minimum_K = self.make_raw_result("q71_failure")
        q71 = impossible_minimum_K["records"][70]
        q71["minimum_effective_K_to_meet_prefix"] = (
            q71["pretruncation_expansion_count"] + 1
        )
        q71["required_K_excess_over_policy_maximum"] = (
            q71["minimum_effective_K_to_meet_prefix"] - SCREEN.K606208
        )
        rehash(impossible_minimum_K)
        with self.assertRaisesRegex(RuntimeError, "failure excess-K drift"):
            SCREEN.validate_replay_handoff(impossible_minimum_K, self.anchor)

    def test_13_exact_canonical_q71_failure_ledger(self):
        transcript_name = SCREEN.SELF_NAME.replace(
            "_screen.py", "_transcript.json"
        )
        transcript_path = HERE / transcript_name
        raw = transcript_path.read_bytes()
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size"])
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])

        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(
            frozenset(transcript), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(transcript), 94)

        expected_summary = {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
                "k606208_c35_q72_screen_v1"
            ),
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "screen_horizon_checkpoint_count": 72,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "attempted_checkpoint_count": 71,
            "completed_checkpoint_count": 70,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "failure_checkpoint_included": True,
            "last_committed_cumulative_drop_ticks": EXPECTED_CANONICAL[
                "last_E"
            ],
            "observed_peak_single_expansion_terms": EXPECTED_CANONICAL[
                "peak"
            ],
            "observed_term_gate_visits_including_terminal_attempt": (
                EXPECTED_CANONICAL["visits"]
            ),
            "observed_maximum_expansion_coefficient_tick_bits": (
                EXPECTED_CANONICAL["coefficient_bits"]
            ),
            "observed_maximum_product_bits": EXPECTED_CANONICAL[
                "product_bits"
            ],
            "observed_rounding_cumulative_scaled_ticks_squared": (
                EXPECTED_CANONICAL["rounding"]
            ),
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
        }
        for key, value in expected_summary.items():
            self.assertEqual(transcript[key], value, key)

        self.assertEqual(
            transcript["candidate_K_values"], list(SCREEN.D_CANDIDATES)
        )
        self.assertEqual(
            transcript["candidate_K_values_sha256"],
            EXPECTED_CANONICAL["candidate_sha256"],
        )
        self.assertEqual(
            transcript["candidate_K_values_sha256"],
            sha256(canonical_bytes(transcript["candidate_K_values"])),
        )

        digest_pairs = {
            "screen_execution_components_sha256": (
                "screen_execution_components",
                EXPECTED_CANONICAL["components_sha256"],
            ),
            "configuration_reference_sha256": (
                "configuration_reference",
                EXPECTED_CANONICAL["configuration_reference_sha256"],
            ),
            "configuration_override_sha256": (
                "configuration_override",
                EXPECTED_CANONICAL["configuration_override_sha256"],
            ),
            "kernel_capability_override_sha256": (
                "kernel_capability_override",
                EXPECTED_CANONICAL["kernel_override_sha256"],
            ),
            "parent_horizon_override_sha256": (
                "parent_horizon_override",
                EXPECTED_CANONICAL["parent_horizon_override_sha256"],
            ),
            "route_predecessor_reference_sha256": (
                "route_predecessor_reference",
                EXPECTED_CANONICAL["route_reference_sha256"],
            ),
            "predecessor_handoff_validation_sha256": (
                "predecessor_handoff_validation",
                EXPECTED_CANONICAL["handoff_sha256"],
            ),
            "checkpoint_transform_sha256": (
                "checkpoint_transform",
                EXPECTED_CANONICAL["transform_sha256"],
            ),
        }
        for digest_key, (value_key, expected_digest) in digest_pairs.items():
            self.assertEqual(transcript[digest_key], expected_digest)
            self.assertEqual(
                transcript[digest_key],
                sha256(canonical_bytes(transcript[value_key])),
                digest_key,
            )

        source_hashes = {
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "control_flow_parent_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            "kernel_capability_wrapper_source_sha256": (
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256
            ),
            "v2_arithmetic_source_sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            "v2_helper_source_sha256": (
                "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
            ),
            "v6_configuration_source_sha256": (
                SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
            ),
            "parent_expected_witness_sha256": (
                EXPECTED_CANONICAL["parent_witness_sha256"]
            ),
        }
        for key, value in source_hashes.items():
            self.assertEqual(transcript[key], value, key)
        self.assertEqual(
            transcript["source_custody"],
            SCREEN.expected_final_source_custody(
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            ),
        )

        components = transcript["screen_execution_components"]
        self.assertEqual(len(components), 11)
        component_paths = [item["relative_path"] for item in components]
        self.assertEqual(len(component_paths), len(set(component_paths)))
        self.assertEqual(components[0], {
            "relative_path": SCREEN.SELF_NAME,
            "role": "D_k606208_c35_q72_fresh_same_byte_screen",
            "sha256": EXPECTED_SCREEN_SHA256,
        })
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, component_paths)
        self.assertNotIn(
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, component_paths
        )

        route = transcript["route_predecessor_reference"]
        for item in (route["screen"], route["canonical_transcript"]):
            self.assertIs(item["compiled"], False)
            self.assertIs(item["executed"], False)
            self.assertIs(item["execution_source_layer"], False)
        route_transcript = route["canonical_transcript"]
        self.assertIs(route_transcript["checkpoint_70_state_loaded"], False)
        self.assertIs(route_transcript["propagation_input"], False)
        self.assertIs(route_transcript["state_resume_input"], False)

        records = transcript["records"]
        history = transcript["selected_K_history"]
        self.assertEqual(len(records), 71)
        self.assertEqual(len(history), 70)
        self.assertEqual(records[:70], self.anchor["records"])
        self.assertEqual(history, self.anchor["selected_K_history"])
        self.assertEqual(
            [record["checkpoint_number_one_based"] for record in records],
            list(range(1, 72)),
        )
        self.assertNotIn(
            72,
            [record["checkpoint_number_one_based"] for record in records],
        )
        self.assertEqual(
            sum(len(record["candidate_records"]) for record in records),
            71 * 35,
        )
        self.assertEqual(
            transcript["records_sha256"],
            EXPECTED_CANONICAL["records_sha256"],
        )
        self.assertEqual(
            transcript["records_sha256"], sha256(canonical_bytes(records))
        )
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            EXPECTED_CANONICAL["history_sha256"],
        )
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            sha256(canonical_bytes(history)),
        )

        q70 = records[69]
        q71 = records[70]
        q70_anchors = {
            "E_after_ticks": EXPECTED_CANONICAL["last_E"],
            "retained_expansion_count": 606_208,
            "retained_expansion_sha256": (
                "4cb4888523ed5d1ffb5571573d017c2e44720def1f61a4b3bcaf1c68ac668dc4"
            ),
            "peak_live_terms_cumulative": 718_805,
            "term_gate_visits_cumulative": 87_505_002,
            "maximum_expansion_coefficient_tick_bits": 63,
            "maximum_product_bits": 120,
            "rounding_cumulative_scaled_ticks_squared": (
                "117439184637462075559402711"
            ),
        }
        for key, value in q70_anchors.items():
            self.assertEqual(q70[key], value, key)

        self.assertEqual(frozenset(q71), SCREEN.Q70_FAILURE_RECORD_KEYS)
        q71_anchors = {
            "checkpoint_index_zero_based": 70,
            "checkpoint_number_one_based": 71,
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 14,
            "gate_occurrence_first_zero_based": 280,
            "gate_occurrence_last_zero_based": 283,
            "gate_batch_sha256": (
                "0d8e35335ccbe016a37dbaebad3206f556f6990ebe6dd49774a71088ab178530"
            ),
            "input_expansion_count": 606_208,
            "input_expansion_sha256": q70_anchors[
                "retained_expansion_sha256"
            ],
            "E_before_ticks": EXPECTED_CANONICAL["last_E"],
            "budget_prefix_cap_ticks": "2289007495823880",
            "prefix_slack_before_selection_ticks": "135953610633",
            "pretruncation_expansion_count": 761_190,
            "pretruncation_expansion_sha256": (
                "e216efffffd7eae98f5e2ff93e24de4896cde49d9f4ee0766b88053d97419e99"
            ),
            "ranked_suffix_sha256": (
                "8762214dccff375ae2df119491460bfb4ab328a80920ad582efc0bb0eca2c195"
            ),
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "selected_candidate_index": None,
            "selected_K": None,
            "minimum_effective_K_to_meet_prefix": 614_584,
            "required_K_excess_over_policy_maximum": 8_376,
            "maximum_candidate_drop_excess_over_slack_ticks": "51085377416",
            "peak_live_terms_this_checkpoint": 761_190,
            "peak_live_terms_cumulative": 761_190,
            "term_gate_visits_increment": 2_636_779,
            "term_gate_visits_cumulative": 90_141_781,
            "maximum_expansion_coefficient_tick_bits": 63,
            "maximum_product_bits": 120,
            "rounding_increment_scaled_ticks_squared": (
                "6225617392173923580890072"
            ),
            "rounding_cumulative_scaled_ticks_squared": (
                EXPECTED_CANONICAL["rounding"]
            ),
        }
        for key, value in q71_anchors.items():
            self.assertEqual(q71[key], value, key)
        self.assertEqual(
            sha256(canonical_bytes(q71)),
            EXPECTED_CANONICAL["failure_sha256"],
        )
        self.assertEqual(
            transcript["failure_record_sha256"],
            EXPECTED_CANONICAL["failure_sha256"],
        )

        rows = q71["candidate_records"]
        self.assertEqual(len(rows), 35)
        self.assertEqual(
            sha256(canonical_bytes(rows)),
            EXPECTED_CANONICAL["q71_rows_sha256"],
        )
        self.assertEqual(
            [row["candidate_index"] for row in rows], list(range(35))
        )
        self.assertEqual(
            [row["configured_K"] for row in rows], list(SCREEN.D_CANDIDATES)
        )
        pre_count = q71["pretruncation_expansion_count"]
        E_before = int(q71["E_before_ticks"])
        drops = []
        for row in rows:
            self.assertEqual(frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS)
            self.assertEqual(
                row["effective_retained_count"],
                min(row["configured_K"], pre_count),
            )
            self.assertEqual(
                row["dropped_term_count"],
                pre_count - row["effective_retained_count"],
            )
            drop = int(row["drop_ticks"])
            drops.append(drop)
            self.assertEqual(
                int(row["E_after_if_selected_ticks"]), E_before + drop
            )
            self.assertIs(row["feasible_under_current_prefix_cap"], False)
        self.assertTrue(
            all(left > right for left, right in zip(drops, drops[1:]))
        )

        maximum_row = rows[-1]
        self.assertEqual(maximum_row, {
            "candidate_index": 34,
            "configured_K": 606_208,
            "effective_retained_count": 606_208,
            "dropped_term_count": 154_982,
            "drop_ticks": "187038988049",
            "E_after_if_selected_ticks": "2289058581201296",
            "feasible_under_current_prefix_cap": False,
        })
        self.assertEqual(
            sha256(canonical_bytes(maximum_row)),
            EXPECTED_CANONICAL["q71_max_row_sha256"],
        )

        counterfactual = q71["removed_491520_counterfactual"]
        self.assertEqual(frozenset(counterfactual), SCREEN.REMOVED_COUNTERFACTUAL_KEYS)
        self.assertEqual(counterfactual, {
            "configured_K": 491_520,
            "effective_retained_count": 491_520,
            "dropped_term_count": 269_670,
            "drop_ticks": "3126304160428",
            "E_after_if_selected_ticks": "2291997846373675",
            "feasible_under_current_prefix_cap": False,
            "actual_selected_K": None,
            "would_precede_selected": False,
            "would_be_selected_if_inserted": False,
        })
        self.assertEqual(
            sha256(canonical_bytes(counterfactual)),
            EXPECTED_CANONICAL["q71_counterfactual_sha256"],
        )

        slack = int(q71["prefix_slack_before_selection_ticks"])
        self.assertEqual(
            int(q71["budget_prefix_cap_ticks"]), E_before + slack
        )
        self.assertEqual(
            q71["required_K_excess_over_policy_maximum"],
            q71["minimum_effective_K_to_meet_prefix"] - SCREEN.K606208,
        )
        self.assertEqual(
            int(q71["maximum_candidate_drop_excess_over_slack_ticks"]),
            int(maximum_row["drop_ticks"]) - slack,
        )
        self.assertEqual(
            q71["peak_live_terms_cumulative"],
            max(
                q70["peak_live_terms_cumulative"],
                q71["peak_live_terms_this_checkpoint"],
            ),
        )
        self.assertEqual(
            q71["term_gate_visits_cumulative"],
            q70["term_gate_visits_cumulative"]
            + q71["term_gate_visits_increment"],
        )
        self.assertEqual(
            int(q71["rounding_cumulative_scaled_ticks_squared"]),
            int(q70["rounding_cumulative_scaled_ticks_squared"])
            + int(q71["rounding_increment_scaled_ticks_squared"]),
        )

        parent_view = {
            key: copy.deepcopy(transcript[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        parent_view.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "control_flow_owned_by_screen": True,
        })
        handoff = SCREEN.validate_replay_handoff(parent_view, self.anchor)
        self.assertEqual(handoff, transcript["predecessor_handoff_validation"])
        self.assertEqual(
            handoff["terminal_branch"], "Q71_FAILURE_Q72_NOT_ATTEMPTED"
        )

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_D_K606208_C35_Q72_REPLAY") == "1",
        "set RUN_HUBBARD_L8_D_K606208_C35_Q72_REPLAY=1 for the full replay",
    )
    def test_14_full_replay_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertEqual(result["screen_horizon_checkpoint_count"], 72)
        self.assertIn(
            result["predecessor_handoff_validation"]["terminal_branch"],
            {
                "Q71_FAILURE_Q72_NOT_ATTEMPTED",
                "Q71_SUCCESS_Q72_FAILURE",
                "Q71_AND_Q72_SUCCESS_HORIZON_REACHED",
            },
        )


if __name__ == "__main__":
    unittest.main()
