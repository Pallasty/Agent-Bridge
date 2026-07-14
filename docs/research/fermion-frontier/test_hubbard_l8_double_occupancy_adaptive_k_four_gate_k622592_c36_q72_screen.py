#!/usr/bin/env python3
"""Static, synthetic and opt-in tests for the D K622592/C36 q72 screen."""

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
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_q72_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "2e22e1918fbc10cd696d700dbf05e8d99d0c333a1428e9473de6ebbc563488e1"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 726_293,
    "file_sha256": "e7ae9abb11a4cc116778c8c373ff1c93131db9c9d36ba886ff6ef2d7b53bd09f",
    "candidate_sha256": "5ab222cdcd073227d6d5e23f881ce94511dab86c35b6aab53c72de9f403367fc",
    "records_sha256": "6bd9a1a5e6599efd78dda59025281af2d8a030beb02c3f145d9f3e055ed18d22",
    "history_sha256": "18e76e6b8a2eb970bf5930c79901f97d24e9e5cfed865d5a8c8e27bee5bec807",
    "components_sha256": "854cd9786f4d8ec73bf45f8658b54a2e77a1b355482aa00fdd8e41a15faebc6a",
    "configuration_reference_sha256": "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1",
    "configuration_override_sha256": "f47b061f413264fca5c6eb2324356bd3ee2305f175392e22c327c7240bea1cf7",
    "kernel_override_sha256": "6fb7b9a56abe958e63d3c0368e72d5e93ab0251e7b0b8d98db8b75b214b337c8",
    "parent_horizon_override_sha256": "6260d69cff7e23c4f725e81f1db2d2edd057a2a2b73bbf2b5fc99382003db6b7",
    "route_reference_sha256": "57ce1f96021aa384212137de5c0b21d4b546690fd8e167fe27a4564c6a2c8d6d",
    "handoff_sha256": "8326d3506788c81f9ecb34f9462f16e725ffc1fdcafb48cbdf9c636b28704bef",
    "transform_sha256": "b22eb3ad898890066fb79b946f14301be564be08639ae9e6b2543c42c79d177c",
    "abort_sha256": "a88ad538886ad3309b6a54679169a9f74ff66630cda5245b5149ca8070005f27",
    "source_custody_sha256": "03d337349ec97b567256a2d568cb15ec536d2140b6189f32a9829660661ef13f",
    "policy_caps_sha256": "36be6a37beeba572939a3e55a1fa99f85d7d7d3c12fe7a7b8476f551ca656dc5",
    "sequence_sha256": "6856197e9f50ef42036e2097dcb36ae4d48049cd3c8ad93885d0e6dd2ba726a7",
    "arithmetic_commit_sha256": "d20271851f9f11f3c9a23bbf1b4a461ae22f0f84f9011ea177d345cc14b96c2d",
    "input_boundary_sha256": "c18c91885a64bfdb6989d8de8ee29a18fc6445bf8983d14f89ae3b03c50099da",
    "root_globals_sha256": "4a6a1f974f485a636062bec3b50030856728c581a33c155821214a83f12736d6",
    "kernel_limits_sha256": "7229d47fa2b22b137d5b99c8043cf7b267617f17bdc2bd65eac22811e3ab119d",
    "parent_witness_sha256": "b63bcf3b6b8b920630e639215281cd04c065e5226aa430dd417a5515df8ad623",
    "q1_q70_records_sha256": "183d04d9d07288bd381e114fad2d3a675d2311a478eac63eeff6ba6e4819ec21",
    "q1_q70_common_sha256": "503b4602d243a3df0be7333817e42069f0ea61715b9ed135551640e21c5152b1",
    "q1_q70_old_rows_sha256": "c2ca8433d9f29365ccba205142b44c40d64812310664d382f2e272c77bcb6f45",
    "q1_q70_appended_rows_sha256": "a877bca614bb8fd48aa2799d4724bd876eb62c8177fda34eaabeb02b489d89a3",
    "q1_q70_all_rows_sha256": "757547e2acfe4dec8cf756db4e3835320fe76921897a499e389f2b43a33d9e77",
    "q71_record_sha256": "bb5fffe2871aefed25755423d43b0689d48df7e954bb524e3041268a9fc22ad2",
    "q71_rows_sha256": "bf4b73fda44fba672c2893d2a6ed871f705b180383913661aaddc5319feb1d2c",
    "q71_old_rows_sha256": "3685bc6658c10da59d18e38a1502942f9dc6b3c2f33cd67d75aadf655c1dba5f",
    "q71_appended_row_sha256": "80d0b83aec395cb946af52ca7de045260103c908a2fbd7f70b1ea18d381c3f5d",
    "q71_shared_sha256": "8a83b5995a8d6391d7999bbfb59d90178383a5bf3925710a294bd87d1979b7e6",
    "q71_counterfactual_sha256": "0aa6309393526da035bb4bdc706a9732aec7cb18054daedb27e612ba035c25ff",
    "q71_counterfactual_arithmetic_sha256": "58a1a0868d4e903b5c16e12b1abe779bd522332c51843667afb9f49f59dc6fc0",
    "all_rows_sha256": "8c15a15ba84f5aa6d2a9fd63578effc5810595f0ea5bb54c80dee1fa196c0882",
    "selected_indices_sha256": "597aa12b31e6dfc6a3f5c3cbfd16e20d0641323a78ce6da2cbaf8bce0431b44e",
}
def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("double_occupancy_k622592_c36_q72_for_tests", SCREEN_NAME)


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


def digest(value):
    return sha256(canonical_bytes(value))


class DoubleOccupancyK622592C36Q72Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.anchor, self.route_reference = SCREEN.load_route_reference(HERE)

    @staticmethod
    def _record_sha(checkpoint: int, label: str) -> str:
        return sha256(f"synthetic-q{checkpoint}-{label}".encode("ascii"))

    def extend_prefix_record(self, predecessor_record):
        record = copy.deepcopy(predecessor_record)
        rows = record["candidate_records"]
        self.assertEqual(len(rows), 35)
        pre_count = record["pretruncation_expansion_count"]
        effective = min(SCREEN.K622592, pre_count)
        drop = max(0, int(rows[-1]["drop_ticks"]) - 1)
        E_after = int(record["E_before_ticks"]) + drop
        rows.append({
            "candidate_index": 35,
            "configured_K": SCREEN.K622592,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
            "drop_ticks": str(drop),
            "E_after_if_selected_ticks": str(E_after),
            "feasible_under_current_prefix_cap": (
                E_after <= int(record["budget_prefix_cap_ticks"])
            ),
        })
        return record

    def make_q71_record(self, success):
        record = copy.deepcopy(self.anchor["records"][70])
        rows = record["candidate_records"]
        self.assertEqual(len(rows), 35)
        slack = int(record["prefix_slack_before_selection_ticks"])
        drop = slack if success else slack + 1
        pre_count = record["pretruncation_expansion_count"]
        effective = min(SCREEN.K622592, pre_count)
        appended = {
            "candidate_index": 35,
            "configured_K": SCREEN.K622592,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
            "drop_ticks": str(drop),
            "E_after_if_selected_ticks": str(
                int(record["E_before_ticks"]) + drop
            ),
            "feasible_under_current_prefix_cap": success,
        }
        rows.append(appended)
        counterfactual = record["removed_491520_counterfactual"]
        counterfactual["actual_selected_K"] = (
            SCREEN.K622592 if success else None
        )
        counterfactual["would_precede_selected"] = False
        counterfactual["would_be_selected_if_inserted"] = False

        if success:
            for key in SCREEN.Q70_FAILURE_ONLY_KEYS:
                record.pop(key, None)
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 35,
                "selected_K": SCREEN.K622592,
                "selected_effective_retained_count": effective,
                "selected_dropped_term_count": (
                    appended["dropped_term_count"]
                ),
                "selected_drop_ticks": appended["drop_ticks"],
                "selected_dropped_terms_sha256": self._record_sha(
                    71, "dropped"
                ),
                "retained_expansion_count": effective,
                "retained_expansion_sha256": self._record_sha(
                    71, "retained"
                ),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "1",
                "E_after_ticks": appended["E_after_if_selected_ticks"],
            })
        else:
            record.update({
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                "selected_candidate_index": None,
                "selected_K": None,
                "minimum_effective_K_to_meet_prefix": SCREEN.K622592 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

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
                "minimum_effective_K_to_meet_prefix": SCREEN.K622592 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

    def make_raw_result(self, branch):
        result = {
            key: copy.deepcopy(self.anchor[key])
            for key in SCREEN.UPSTREAM_PARENT_RESULT_KEYS
        }
        result["resource_policy_abort"] = None
        result["resource_policy_abort_sha256"] = None
        result.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_horizon_checkpoint_count": SCREEN.EXTENDED_HORIZON,
            "candidate_K_values": list(SCREEN.D_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": len(SCREEN.D_CANDIDATES),
            },
            "kernel_capability_limits": SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        })
        components = copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS))
        result["screen_execution_components"] = components
        result["screen_execution_components_sha256"] = sha256(
            canonical_bytes(components)
        )
        configuration = {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "source_sha256": (
                SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
            ),
            "role": "candidates_and_caps_reference_only",
            "fields_adopted": [
                f"MODE_CONFIG.{SCREEN.MODE}.candidates",
                "POLICY_CAPS_BASE",
            ],
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "policy_caps_base_sha256": SCREEN.EXPECTED_V6_POLICY_CAPS_SHA256,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
        }
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

        records = [
            self.extend_prefix_record(record)
            for record in self.anchor["records"][:70]
        ]
        history = list(self.anchor["selected_K_history"])
        if branch == "q71_failure":
            q71 = self.make_q71_record(False)
            records.append(q71)
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            horizon_attempted = False
            horizon_committed = False
            last_E = SCREEN.EXPECTED_Q70_E_AFTER_TICKS
            attempted = 71
        elif branch in {
            "q72_failure",
            "q72_success",
            "q72_resource_abort",
        }:
            q71 = self.make_q71_record(True)
            records.append(q71)
            history.append(q71["selected_K"])
            horizon_attempted = True
            attempted = 72
            if branch == "q72_resource_abort":
                pre_count = (
                    SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"] + 1
                )
                visit_increment = 4 * q71["retained_expansion_count"]
                abort = {
                    "schema_version": 1,
                    "abort_id": (
                        "D_k622592_c36_q72_live_term_policy_abort_v1"
                    ),
                    "exception_type": "RuntimeError",
                    "exception_message": (
                        "design policy live-term cap exceeded"
                    ),
                    "exception_args": [
                        "design policy live-term cap exceeded"
                    ],
                    "exception_chained_from_exact_parent_helper": True,
                    "control_flow_parent_source_sha256": (
                        SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
                    ),
                    "helper_source_sha256": SCREEN.EXPECTED_V2_HELPER_SHA256,
                    "checkpoint_index_zero_based": 71,
                    "checkpoint_number_one_based": 72,
                    **SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[72],
                    "gate_occurrence_first_zero_based": 284,
                    "gate_occurrence_last_zero_based": 287,
                    "input_expansion_count": q71["retained_expansion_count"],
                    "input_expansion_sha256": q71[
                        "retained_expansion_sha256"
                    ],
                    "pretruncation_expansion_count": pre_count,
                    "max_single_expansion_terms": SCREEN.POLICY_CAPS_BASE[
                        "max_single_expansion_terms"
                    ],
                    "observed_excess_terms": 1,
                    "policy_relation": (
                        "pretruncation_expansion_count>"
                        "max_single_expansion_terms"
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
                    "q71_committed_record_sha256": sha256(
                        canonical_bytes(q71)
                    ),
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
                        int(q71[
                            "rounding_cumulative_scaled_ticks_squared"
                        ]) + 1
                    ),
                    "maximum_expansion_coefficient_tick_bits": q71[
                        "maximum_expansion_coefficient_tick_bits"
                    ],
                    "maximum_product_bits": q71["maximum_product_bits"],
                }
                self.assertEqual(
                    frozenset(abort), SCREEN.RESOURCE_POLICY_ABORT_KEYS
                )
                result["resource_policy_abort"] = abort
                result["resource_policy_abort_sha256"] = sha256(
                    canonical_bytes(abort)
                )
                terminal = "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
                horizon_committed = False
                last_E = q71["E_after_ticks"]
            else:
                q72 = self.make_extended_record(
                    records[-1], 72, branch == "q72_success"
                )
                records.append(q72)
            if branch == "q72_failure":
                terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                horizon_committed = False
                last_E = q71["E_after_ticks"]
            elif branch == "q72_success":
                terminal = "DIAGNOSTIC_HORIZON_REACHED"
                horizon_committed = True
                history.append(q72["selected_K"])
                last_E = q72["E_after_ticks"]
        else:
            raise AssertionError(branch)

        final = records[-1]
        abort = result["resource_policy_abort"]
        failed = (
            abort is None
            and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        resource_source = abort if abort is not None else final
        result.update({
            "records": records,
            "records_sha256": sha256(canonical_bytes(records)),
            "selected_K_history": history,
            "selected_K_history_sha256": sha256(canonical_bytes(history)),
            "attempted_checkpoint_count": attempted,
            "completed_checkpoint_count": len(history),
            "screen_terminal_condition": terminal,
            "horizon_checkpoint_attempted": horizon_attempted,
            "horizon_reached_with_committed_checkpoint": horizon_committed,
            "failure_checkpoint_included": failed,
            "failure_record_sha256": (
                sha256(canonical_bytes(final)) if failed else None
            ),
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
        })
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return result

    def make_synthetic_abort_parent(
        self,
        *,
        checkpoint_number=72,
        omit_rounding_before=False,
        direct_raise=False,
        tamper_helper_source=False,
    ):
        """Build an in-memory exact-frame parent; this performs no replay."""

        expected = self.make_raw_result("q72_resource_abort")
        abort = expected["resource_policy_abort"]
        parent = SCREEN.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        if tamper_helper_source:
            helper._VERIFIED_SELF_SOURCE_BYTES = b"tampered-helper-source"
        sequence_kernel, sequence_root, _modules, _custody = (
            parent.load_execution_sources(HERE, helper, SCREEN.MODE)
        )
        stages, _trig, _sequence, _transform = parent.build_four_gate_sequence(
            helper, sequence_root, sequence_kernel
        )
        checkpoint = 0
        q72_batch = None
        for sequence_stage in stages:
            for batch_start in range(0, len(sequence_stage["gates"]), 4):
                checkpoint += 1
                if checkpoint == 72:
                    q72_batch = sequence_stage["gates"][
                        batch_start:batch_start + 4
                    ]
        self.assertIsNotNone(q72_batch)
        self.assertEqual(
            helper.gate_batch_sha256(q72_batch),
            SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[72][
                "gate_batch_sha256"
            ],
        )

        kernel = types.SimpleNamespace(
            RESOURCE_LIMITS=copy.deepcopy(
                SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS
            ),
            root_global_snapshot=lambda _root: copy.deepcopy(
                expected["root_globals_after"]
            ),
        )
        counter = types.SimpleNamespace(
            window_peak_live_terms=abort[
                "peak_live_terms_this_checkpoint"
            ],
            peak_live_terms=abort["peak_live_terms_cumulative"],
            term_gate_visits=abort["term_gate_visits_cumulative"],
            multiplication_rounding_l1_scaled_ticks_squared=int(
                abort["rounding_cumulative_scaled_ticks_squared"]
            ),
            maximum_expansion_coefficient_tick_bits=abort[
                "maximum_expansion_coefficient_tick_bits"
            ],
            maximum_product_bits=abort["maximum_product_bits"],
        )
        source_custody = copy.deepcopy(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY)
        source_custody.pop(parent.V2_HELPER_NAME)
        source_custody.pop(parent.V6_CONFIGURATION_NAME)
        state = {
            "expected": expected,
            "abort": abort,
            "helper": helper,
            "kernel": kernel,
            "counter": counter,
            "source_custody": source_custody,
            "checkpoint_number": checkpoint_number,
            "omit_rounding_before": omit_rounding_before,
            "direct_raise": direct_raise,
            "q72_batch": q72_batch,
        }

        def fake_run_four_gate(repo, mode):
            del repo
            helper = state["helper"]
            v6_configuration = object()
            kernel = state["kernel"]
            root = {}
            source_custody = state["source_custody"]
            root_before = copy.deepcopy(
                state["expected"]["root_globals_before"]
            )
            boundary_custody = copy.deepcopy(
                state["expected"]["input_boundary_custody"]
            )
            sequence = copy.deepcopy(state["expected"]["sequence"])
            transform = copy.deepcopy(
                state["expected"]["checkpoint_transform"]
            )
            helper_config = {
                "observable_id": state["expected"]["observable_id"],
                "input_step_index": state["expected"]["input_step_index"],
                "child_step_index": state["expected"][
                    "attempted_child_step_index"
                ],
                "parent_expected_witness_sha256": state["expected"][
                    "parent_expected_witness_sha256"
                ],
            }
            candidates = tuple(SCREEN.D_CANDIDATES)
            caps = copy.deepcopy(state["expected"]["proposed_policy_caps"])
            counter = state["counter"]
            E_input = int(state["expected"]["input_cumulative_drop_ticks"])
            cumulative = int(
                state["expected"]["records"][-1]["E_after_ticks"]
            )
            remaining_steps = state["expected"][
                "remaining_mapped_steps_including_attempt"
            ]
            denominator = state["expected"]["future_checkpoint_denominator"]
            horizon = 72
            records = copy.deepcopy(state["expected"]["records"])
            selected_history = list(
                state["expected"]["selected_K_history"]
            )
            failure = None
            horizon_reached = False
            gate_index = 284
            stage_index = 2
            stage = {"group": "HU", "gates": state["q72_batch"]}
            batch_start = 60
            checkpoint_index = 71
            checkpoint_number = state["checkpoint_number"]
            batch = state["q72_batch"]
            input_count = state["abort"]["input_expansion_count"]
            input_sha = state["abort"]["input_expansion_sha256"]
            visits_before = (
                counter.term_gate_visits
                - state["abort"]["term_gate_visits_increment"]
            )
            if not state["omit_rounding_before"]:
                rounding_before = (
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                    - int(state["abort"][
                        "rounding_increment_scaled_ticks_squared"
                    ])
                )
            pre_count = state["abort"]["pretruncation_expansion_count"]
            if state["direct_raise"]:
                raise RuntimeError("design policy live-term cap exceeded")
            helper.enforce_policy_caps(kernel, counter, pre_count, caps)
            raise AssertionError("unreachable")

        def fake_verified(repo, mode):
            return parent.run_four_gate(repo, mode)

        parent.__dict__["copy"] = copy
        parent.__dict__["SCREEN"] = SCREEN
        bound_run_four_gate = types.FunctionType(
            fake_run_four_gate.__code__.replace(co_filename=parent.__file__),
            parent.__dict__,
            fake_run_four_gate.__name__,
            fake_run_four_gate.__defaults__,
            fake_run_four_gate.__closure__,
        )
        parent.run_four_gate = bound_run_four_gate
        parent._D_K622592_EXACT_RUN_FOUR_GATE = bound_run_four_gate
        parent._run_verified = fake_verified
        return parent, expected

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
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(self.anchor["records"][:70])),
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
            sha256(canonical_bytes(self.anchor["records"][70])),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256,
        )
        self.assertEqual(
            frozenset(self.anchor),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS,
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
        self.assertEqual(len(SCREEN.PREDECESSOR_D_CANDIDATES), 35)
        self.assertEqual(len(SCREEN.D_CANDIDATES), 36)
        self.assertEqual(
            SCREEN.D_CANDIDATES,
            SCREEN.PREDECESSOR_D_CANDIDATES + (SCREEN.K622592,),
        )
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
        incremental = config["incremental_route_override_from_k606208_c35_q72"]
        self.assertEqual(incremental["candidate_count"], {"before": 35, "after": 36})
        self.assertEqual(incremental["candidate_ladder_added"], [SCREEN.K622592])
        self.assertEqual(incremental["candidate_ladder_removed"], [])
        self.assertEqual(
            incremental["policy_cap_changes"],
            {
                "max_candidate_K": {
                    "before": SCREEN.K606208,
                    "after": SCREEN.K622592,
                },
                "max_output_terms_if_successful": {
                    "before": SCREEN.K606208,
                    "after": SCREEN.K622592,
                },
            },
        )
        capability = fresh.kernel_capability_override(wrapper_sha, manifest)
        self.assertEqual(
            capability["incremental_route_changes_from_k606208_c35"],
            {
                "max_candidate_count": {"before": 35, "after": 36},
                "max_retained_K": {
                    "before": SCREEN.K606208,
                    "after": SCREEN.K622592,
                },
            },
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
        for old, new in zip(self.anchor["records"][:70], result["records"][:70]):
            self.assertEqual(
                {key: value for key, value in new.items() if key != "candidate_records"},
                {key: value for key, value in old.items() if key != "candidate_records"},
            )
            self.assertEqual(new["candidate_records"][:35], old["candidate_records"])
            self.assertEqual(
                new["candidate_records"][35]["configured_K"],
                SCREEN.K622592,
            )
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

        abort = self.make_raw_result("q72_resource_abort")
        abort_handoff = SCREEN.validate_replay_handoff(abort, self.anchor)
        self.assertEqual(
            abort_handoff["terminal_branch"],
            "Q71_SUCCESS_Q72_LIVE_TERM_POLICY_ABORT",
        )
        self.assertEqual(
            (len(abort["records"]), len(abort["selected_K_history"])),
            (71, 71),
        )
        self.assertEqual(abort["attempted_checkpoint_count"], 72)
        self.assertEqual(abort["completed_checkpoint_count"], 71)
        self.assertFalse(abort["failure_checkpoint_included"])
        self.assertIsNone(abort["failure_record_sha256"])
        self.assertTrue(
            abort_handoff["q72_resource_policy_abort_structured"]
        )
        self.assertFalse(abort_handoff["q72_checkpoint_record_constructed"])

    def test_04b_exact_traceback_abort_capture_is_closed(self):
        parent, expected = self.make_synthetic_abort_parent()
        structured = SCREEN.execute_parent_with_structured_abort(parent, HERE)
        self.assertEqual(structured["records"], expected["records"])
        self.assertEqual(
            structured["selected_K_history"],
            expected["selected_K_history"],
        )
        self.assertEqual(len(structured["records"]), 71)
        self.assertEqual(structured["attempted_checkpoint_count"], 72)
        self.assertEqual(structured["completed_checkpoint_count"], 71)
        self.assertEqual(
            structured["screen_terminal_condition"],
            "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
        )
        abort = structured["resource_policy_abort"]
        self.assertEqual(
            structured["resource_policy_abort_sha256"],
            sha256(canonical_bytes(abort)),
        )
        self.assertGreater(
            abort["pretruncation_expansion_count"],
            abort["max_single_expansion_terms"],
        )
        for unavailable in (
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
            "candidate_records",
            "selected_candidate_index",
            "selected_K",
            "E_after_ticks",
        ):
            self.assertNotIn(unavailable, abort)
        handoff = SCREEN.validate_replay_handoff(structured, self.anchor)
        self.assertEqual(
            handoff["terminal_branch"],
            "Q71_SUCCESS_Q72_LIVE_TERM_POLICY_ABORT",
        )

        cases = (
            ({"checkpoint_number": 71}, "checkpoint boundary drift"),
            ({"omit_rounding_before": True}, "frame local schema drift"),
            ({"direct_raise": True}, "helper traceback identity drift"),
            ({"tamper_helper_source": True}, "helper frame authority drift"),
        )
        for kwargs, pattern in cases:
            parent, _ = self.make_synthetic_abort_parent(**kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(RuntimeError, pattern):
                    SCREEN.execute_parent_with_structured_abort(parent, HERE)

        parent, _ = self.make_synthetic_abort_parent()

        def wrong_run_frame(_repo, _mode):
            raise RuntimeError("design policy live-term cap exceeded")

        parent._run_verified = wrong_run_frame
        with self.assertRaisesRegex(RuntimeError, "parent traceback authority"):
            SCREEN.execute_parent_with_structured_abort(parent, HERE)

        parent, _ = self.make_synthetic_abort_parent()
        parent._VERIFIED_SELF_SOURCE_BYTES = b"tampered-parent-source"
        with self.assertRaisesRegex(RuntimeError, "parent same-byte identity"):
            SCREEN.execute_parent_with_structured_abort(parent, HERE)

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
        self.assertEqual(len(SCREEN.UPSTREAM_PARENT_RESULT_KEYS), 65)
        self.assertEqual(len(SCREEN.EXPECTED_PARENT_RESULT_KEYS), 67)
        self.assertEqual(len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS), 96)
        self.assertEqual(len(SCREEN.RESOURCE_POLICY_ABORT_KEYS), 40)
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
        row_extra["records"][70]["candidate_records"][35]["unexpected"] = True
        cases.append((row_extra, "candidate row 35"))
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
        with self.assertRaisesRegex(RuntimeError, "common record state"):
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

    def test_07b_raw_transform_is_exactly_bound_to_route_authority(self):
        result = self.make_raw_result("q72_success")
        result["checkpoint_transform"]["gates_per_checkpoint"] = 8
        result["checkpoint_transform_sha256"] = sha256(
            canonical_bytes(result["checkpoint_transform"])
        )
        with self.assertRaisesRegex(RuntimeError, "transform authority drift"):
            SCREEN.validate_replay_handoff(result, self.anchor)

        result = self.make_raw_result("q72_success")
        result["checkpoint_transform_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeError, "nested digest drift|digest pin drift"
        ):
            SCREEN.validate_replay_handoff(result, self.anchor)

        predecessor = copy.deepcopy(self.anchor)
        raw = predecessor["checkpoint_transform"][
            "physical_four_gate_control_flow_parent_transform"
        ]
        raw["gates_per_checkpoint"] = 8
        predecessor["checkpoint_transform"][
            "physical_four_gate_control_flow_parent_transform_sha256"
        ] = SCREEN.EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
        with self.assertRaisesRegex(RuntimeError, "route raw transform digest"):
            SCREEN.validate_replay_handoff(
                self.make_raw_result("q72_success"), predecessor
            )

    def test_07c_bool_int_aliases_and_abort_tampering_are_rejected(self):
        scalar_cases = []
        top_integer = self.make_raw_result("q72_success")
        top_integer["schema_version"] = True
        scalar_cases.append(("top-integer", top_integer))
        invariant_boolean = self.make_raw_result("q72_success")
        invariant_boolean["v2_run_entrypoint_called"] = 0
        scalar_cases.append(("invariant-boolean", invariant_boolean))
        terminal_boolean = self.make_raw_result("q72_success")
        terminal_boolean["horizon_checkpoint_attempted"] = 1
        scalar_cases.append(("terminal-boolean", terminal_boolean))
        root_boolean = self.make_raw_result("q72_success")
        root_boolean["root_globals_unchanged"] = 1
        scalar_cases.append(("root-boolean", root_boolean))
        runtime_boolean = self.make_raw_result("q72_success")
        runtime_boolean[
            "runtime_RSS_host_timestamp_and_float_fields_excluded"
        ] = 1
        scalar_cases.append(("runtime-boolean", runtime_boolean))
        helper_compilation_boolean = self.make_raw_result("q72_success")
        helper_compilation_boolean[
            "v2_helper_compiled_from_verified_bytes"
        ] = 1
        scalar_cases.append(("helper-compilation-boolean", helper_compilation_boolean))
        single_ranking_boolean = self.make_raw_result("q72_success")
        single_ranking_boolean[
            "single_propagation_and_single_ranking_per_checkpoint"
        ] = 1
        scalar_cases.append(("single-ranking-boolean", single_ranking_boolean))
        child_step_integer = self.make_raw_result("q72_success")
        child_step_integer["attempted_child_step_index"] = True
        scalar_cases.append(("child-step-integer", child_step_integer))
        checkpoint_integer = self.make_raw_result("q72_success")
        checkpoint_integer["records"][71][
            "checkpoint_index_zero_based"
        ] = True
        scalar_cases.append(("checkpoint-integer", checkpoint_integer))
        row_K = self.make_raw_result("q72_success")
        row_K["records"][71]["candidate_records"][0][
            "configured_K"
        ] = True
        scalar_cases.append(("row-K", row_K))
        row_effective = self.make_raw_result("q72_success")
        row_effective["records"][71]["candidate_records"][0][
            "effective_retained_count"
        ] = True
        scalar_cases.append(("row-effective", row_effective))
        row_drop_count = self.make_raw_result("q72_success")
        row_drop_count["records"][71]["candidate_records"][0][
            "dropped_term_count"
        ] = True
        scalar_cases.append(("row-drop-count", row_drop_count))
        for label, result in scalar_cases:
            result["records_sha256"] = sha256(
                canonical_bytes(result["records"])
            )
            with self.subTest(bool_int_alias=label):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        for label, field, value in (
            ("root-authority", "root_globals_before", {"tampered": True}),
            ("sequence-authority", "sequence", {"tampered": True}),
        ):
            result = self.make_raw_result("q72_success")
            result[field] = value
            with self.subTest(raw_authority=label):
                with self.assertRaisesRegex(
                    RuntimeError, "invariant top-level drift"
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        result = self.make_raw_result("q72_success")
        result["configuration_reference"]["v6_execution_invoked"] = 0
        result["configuration_reference_sha256"] = sha256(
            canonical_bytes(result["configuration_reference"])
        )
        with self.assertRaisesRegex(
            RuntimeError, "configuration-reference authority drift"
        ):
            SCREEN.validate_replay_handoff(result, self.anchor)

        for field, value in (
            ("checkpoint_number_one_based", True),
            ("max_single_expansion_terms", True),
            ("attempted_gate_batch_propagated", 1),
            ("q72_pretruncation_digest_computed", True),
            ("observed_excess_terms", 2),
            ("q71_committed_record_sha256", "0" * 64),
        ):
            result = self.make_raw_result("q72_resource_abort")
            result["resource_policy_abort"][field] = value
            result["resource_policy_abort_sha256"] = sha256(
                canonical_bytes(result["resource_policy_abort"])
            )
            with self.subTest(abort_field=field):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        result = self.make_raw_result("q72_resource_abort")
        result["resource_policy_abort_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "abort digest drift"):
            SCREEN.validate_replay_handoff(result, self.anchor)

        result = self.make_raw_result("q72_resource_abort")
        result["resource_policy_abort"][
            "pretruncation_expansion_sha256"
        ] = "0" * 64
        result["resource_policy_abort_sha256"] = sha256(
            canonical_bytes(result["resource_policy_abort"])
        )
        with self.assertRaisesRegex(RuntimeError, "exact key-set drift"):
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
            "k622592_c36_q72_screen_v1",
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
        self.assertFalse(canonical["loaded_before_replay_as_exact_reference"])
        self.assertTrue(canonical["loaded_after_replay_as_exact_reference"])
        self.assertFalse(canonical["propagation_input"])
        self.assertFalse(canonical["checkpoint_70_state_loaded"])
        self.assertFalse(canonical["state_resume_input"])
        self.assertEqual(
            result["checkpoint_transform"]["incremental_route_semantic_delta"],
            {
                "candidate_K_values_changed": True,
                "policy_caps_changed": True,
                "kernel_capability_limits_changed": True,
                "horizon_checkpoint_count": {"before": 72, "after": 72},
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

        abort_result = fresh.validate_and_relabel(
            self.make_raw_result("q72_resource_abort"),
            predecessor,
            route_reference,
            baseline_d,
            wrapper_sha,
            manifest,
            horizon,
        )
        self.assertEqual(
            frozenset(abort_result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(abort_result["records"]), 71)
        self.assertEqual(
            abort_result["predecessor_handoff_validation"]["terminal_branch"],
            "Q71_SUCCESS_Q72_LIVE_TERM_POLICY_ABORT",
        )
        self.assertIsNone(abort_result["failure_record_sha256"])

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

        events = []
        completed = self.make_raw_result("q72_success")
        upstream = {
            key: copy.deepcopy(completed[key])
            for key in SCREEN.UPSTREAM_PARENT_RESULT_KEYS
        }

        class Parent:
            @staticmethod
            def _run_verified(repo, mode):
                self.assertEqual((repo, mode), (HERE, SCREEN.MODE))
                events.append("replay")
                return copy.deepcopy(upstream)

        fresh = SCREEN.fresh_self_module()
        fresh.load_control_flow_parent = lambda _repo: Parent()
        fresh.load_configured_v6_baseline = lambda _repo: (
            object(),
            SCREEN.V6_D_CANDIDATES,
        )
        fresh.load_kernel_wrapper = lambda _repo: (
            object(),
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            {},
        )
        fresh.configure_parent_execution = lambda *_args: {}

        def load_route_after_replay(_repo):
            events.append("route")
            return {}, {}

        fresh.load_route_reference = load_route_after_replay

        def relabel_after_route(result, *_args):
            self.assertIsNone(result["resource_policy_abort"])
            self.assertIsNone(result["resource_policy_abort_sha256"])
            events.append("relabel")
            return {"ordered": True}

        fresh.validate_and_relabel = relabel_after_route
        self.assertEqual(fresh._run_verified(HERE), {"ordered": True})
        self.assertEqual(events, ["replay", "route", "relabel"])

        fresh = SCREEN.fresh_self_module()
        resource_error = RuntimeError("D q72 resource sentinel")

        def fail_parent(_repo):
            raise resource_error

        fresh.load_control_flow_parent = fail_parent
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

        for unexpected in (
            RuntimeError("unexpected parent failure"),
            RuntimeError(
                "design policy live-term cap exceeded",
                "unexpected second argument",
            ),
            ValueError("unexpected parent value failure"),
        ):
            class UnexpectedParent:
                @staticmethod
                def _run_verified(_repo, _mode):
                    raise unexpected

            with self.subTest(unexpected=type(unexpected).__name__):
                with self.assertRaises(type(unexpected)) as caught:
                    SCREEN.execute_parent_with_structured_abort(
                        UnexpectedParent(), HERE
                    )
                self.assertIs(caught.exception, unexpected)

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
                    RuntimeError, "component (schema|closure) drift"
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
                                RuntimeError,
                                "digest schema drift|shared propagation fields",
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
                        RuntimeError,
                        "cumulative maximum decreased|shared propagation fields",
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
                    RuntimeError,
                    "checkpoint peak below live terms|shared propagation fields",
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
                    RuntimeError,
                    "gate visits below first-gate input|shared propagation fields",
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
                        RuntimeError,
                        "exceed[s]? policy cap|shared propagation fields",
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
                    RuntimeError,
                    "canonical decimal string|shared propagation fields|"
                    "changed predecessor candidate rows",
                ):
                    SCREEN.validate_replay_handoff(result, self.anchor)

        impossible_minimum_K = self.make_raw_result("q71_failure")
        q71 = impossible_minimum_K["records"][70]
        q71["minimum_effective_K_to_meet_prefix"] = (
            q71["pretruncation_expansion_count"] + 1
        )
        q71["required_K_excess_over_policy_maximum"] = (
            q71["minimum_effective_K_to_meet_prefix"] - SCREEN.K622592
        )
        rehash(impossible_minimum_K)
        with self.assertRaisesRegex(RuntimeError, "failure excess-K drift"):
            SCREEN.validate_replay_handoff(impossible_minimum_K, self.anchor)

    def test_13_appended_row_adjacency_is_fail_closed(self):
        def rehash(result):
            result["records_sha256"] = sha256(
                canonical_bytes(result["records"])
            )
            final = result["records"][-1]
            if final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
                result["failure_record_sha256"] = sha256(
                    canonical_bytes(final)
                )

        ranking = self.make_raw_result("q71_failure")
        record = ranking["records"][69]
        predecessor = record["candidate_records"][34]
        appended = record["candidate_records"][35]
        bad_drop = int(predecessor["drop_ticks"]) + 1
        appended["drop_ticks"] = str(bad_drop)
        appended["E_after_if_selected_ticks"] = str(
            int(record["E_before_ticks"]) + bad_drop
        )
        appended["feasible_under_current_prefix_cap"] = (
            int(appended["E_after_if_selected_ticks"])
            <= int(record["budget_prefix_cap_ticks"])
        )
        rehash(ranking)
        with self.assertRaisesRegex(RuntimeError, "appended candidate ranking"):
            SCREEN.validate_replay_handoff(ranking, self.anchor)

        bad_E = self.make_raw_result("q71_failure")
        appended = bad_E["records"][69]["candidate_records"][35]
        appended["E_after_if_selected_ticks"] = str(
            int(appended["E_after_if_selected_ticks"]) + 1
        )
        rehash(bad_E)
        with self.assertRaisesRegex(RuntimeError, "candidate E recurrence"):
            SCREEN.validate_replay_handoff(bad_E, self.anchor)

        bad_count = self.make_raw_result("q71_failure")
        appended = bad_count["records"][69]["candidate_records"][35]
        appended["dropped_term_count"] += 1
        rehash(bad_count)
        with self.assertRaisesRegex(RuntimeError, "appended candidate drift"):
            SCREEN.validate_replay_handoff(bad_count, self.anchor)

        zero_drop = self.make_raw_result("q71_failure")
        record = zero_drop["records"][0]
        appended = record["candidate_records"][35]
        self.assertEqual(appended["dropped_term_count"], 0)
        self.assertEqual(appended["drop_ticks"], "0")
        appended["drop_ticks"] = "1"
        appended["E_after_if_selected_ticks"] = str(
            int(record["E_before_ticks"]) + 1
        )
        appended["feasible_under_current_prefix_cap"] = True
        rehash(zero_drop)
        with self.assertRaisesRegex(RuntimeError, "appended candidate ranking"):
            SCREEN.validate_replay_handoff(zero_drop, self.anchor)


    def test_14_canonical_transcript_exact_q71_and_resource_abort_ledger(self):
        canonical_path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(canonical_path.is_file())
        raw = canonical_path.read_bytes()
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(
            frozenset(transcript), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(transcript), 96)

        exact_top = {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
                "k622592_c36_q72_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "screen_horizon_checkpoint_count": 72,
            "attempted_checkpoint_count": 72,
            "completed_checkpoint_count": 71,
            "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": False,
            "last_committed_cumulative_drop_ticks": "2288967389826722",
            "candidate_K_values": list(SCREEN.D_CANDIDATES),
            "candidate_K_values_sha256": EXPECTED_CANONICAL[
                "candidate_sha256"
            ],
            "resource_policy_abort_sha256": EXPECTED_CANONICAL[
                "abort_sha256"
            ],
            "control_flow_owned_by_screen": False,
            "control_flow_owned_by_verified_parent": True,
            "control_flow_parent_private_entrypoint_called": True,
            "control_flow_parent_runtime_horizon_override_applied": True,
            "v6_runtime_configuration_override_applied": True,
            "diagnostic_candidate_ladder_precommitted_before_replay": True,
            "diagnostic_horizon_precommitted_before_replay": True,
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
        }
        for field, expected in exact_top.items():
            with self.subTest(top_field=field):
                self.assertTrue(
                    SCREEN.exact_value_equal(transcript[field], expected)
                )

        embedded_digests = (
            (
                "candidate_K_values",
                "candidate_K_values_sha256",
                "candidate_sha256",
            ),
            ("records", "records_sha256", "records_sha256"),
            (
                "selected_K_history",
                "selected_K_history_sha256",
                "history_sha256",
            ),
            (
                "screen_execution_components",
                "screen_execution_components_sha256",
                "components_sha256",
            ),
            (
                "configuration_reference",
                "configuration_reference_sha256",
                "configuration_reference_sha256",
            ),
            (
                "configuration_override",
                "configuration_override_sha256",
                "configuration_override_sha256",
            ),
            (
                "kernel_capability_override",
                "kernel_capability_override_sha256",
                "kernel_override_sha256",
            ),
            (
                "parent_horizon_override",
                "parent_horizon_override_sha256",
                "parent_horizon_override_sha256",
            ),
            (
                "route_predecessor_reference",
                "route_predecessor_reference_sha256",
                "route_reference_sha256",
            ),
            (
                "predecessor_handoff_validation",
                "predecessor_handoff_validation_sha256",
                "handoff_sha256",
            ),
            (
                "checkpoint_transform",
                "checkpoint_transform_sha256",
                "transform_sha256",
            ),
            (
                "resource_policy_abort",
                "resource_policy_abort_sha256",
                "abort_sha256",
            ),
        )
        for value_field, digest_field, expected_field in embedded_digests:
            with self.subTest(nested_field=value_field):
                expected = EXPECTED_CANONICAL[expected_field]
                self.assertEqual(transcript[digest_field], expected)
                self.assertEqual(digest(transcript[value_field]), expected)

        unembedded_digests = {
            "source_custody": "source_custody_sha256",
            "proposed_policy_caps": "policy_caps_sha256",
            "sequence": "sequence_sha256",
            "arithmetic_kernel_commit": "arithmetic_commit_sha256",
            "input_boundary_custody": "input_boundary_sha256",
            "root_globals_before": "root_globals_sha256",
            "root_globals_after": "root_globals_sha256",
            "kernel_capability_limits": "kernel_limits_sha256",
        }
        for value_field, expected_field in unembedded_digests.items():
            with self.subTest(unembedded_field=value_field):
                self.assertEqual(
                    digest(transcript[value_field]),
                    EXPECTED_CANONICAL[expected_field],
                )
        self.assertEqual(
            transcript["parent_expected_witness_sha256"],
            EXPECTED_CANONICAL["parent_witness_sha256"],
        )
        self.assertTrue(
            SCREEN.exact_value_equal(
                transcript["root_globals_before"],
                transcript["root_globals_after"],
            )
        )

        records = transcript["records"]
        history = transcript["selected_K_history"]
        self.assertEqual((len(records), len(history)), (71, 71))
        self.assertEqual(digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertTrue(
            SCREEN.exact_value_equal(
                history[:70], self.anchor["selected_K_history"]
            )
        )
        self.assertTrue(
            SCREEN.exact_value_equal(history[-1], SCREEN.K622592)
        )
        self.assertEqual(
            digest(history[:70]), SCREEN.EXPECTED_Q70_SELECTED_HISTORY_SHA256
        )
        self.assertEqual(
            digest(records[:70]),
            EXPECTED_CANONICAL["q1_q70_records_sha256"],
        )

        prefix_common = []
        prefix_old_rows = []
        prefix_appended_rows = []
        prefix_all_rows = []
        for checkpoint_index, (record, anchored) in enumerate(
            zip(records[:70], self.anchor["records"][:70])
        ):
            with self.subTest(prefix_checkpoint=checkpoint_index + 1):
                self.assertEqual(
                    frozenset(record), SCREEN.Q70_SUCCESS_RECORD_KEYS
                )
                common = {
                    key: value
                    for key, value in record.items()
                    if key != "candidate_records"
                }
                anchored_common = {
                    key: value
                    for key, value in anchored.items()
                    if key != "candidate_records"
                }
                self.assertTrue(
                    SCREEN.exact_value_equal(common, anchored_common)
                )
                rows = record["candidate_records"]
                self.assertEqual(len(rows), 36)
                self.assertTrue(
                    SCREEN.exact_value_equal(
                        rows[:35], anchored["candidate_records"]
                    )
                )
                for row in rows:
                    self.assertEqual(
                        frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                    )
                appended = rows[35]
                pre_count = record["pretruncation_expansion_count"]
                effective = min(SCREEN.K622592, pre_count)
                expected_identity = {
                    "candidate_index": 35,
                    "configured_K": SCREEN.K622592,
                    "effective_retained_count": effective,
                    "dropped_term_count": pre_count - effective,
                }
                for field, expected in expected_identity.items():
                    self.assertTrue(
                        SCREEN.exact_value_equal(appended[field], expected)
                    )
                drop = SCREEN.parse_canonical_nonnegative_decimal(
                    appended["drop_ticks"],
                    f"q{checkpoint_index + 1} appended drop",
                )
                E_before = SCREEN.parse_canonical_nonnegative_decimal(
                    record["E_before_ticks"],
                    f"q{checkpoint_index + 1} E-before",
                )
                E_after = SCREEN.parse_canonical_nonnegative_decimal(
                    appended["E_after_if_selected_ticks"],
                    f"q{checkpoint_index + 1} appended E-after",
                )
                prefix_cap = SCREEN.parse_canonical_nonnegative_decimal(
                    record["budget_prefix_cap_ticks"],
                    f"q{checkpoint_index + 1} prefix cap",
                )
                self.assertEqual(E_after, E_before + drop)
                self.assertIs(
                    appended["feasible_under_current_prefix_cap"],
                    E_after <= prefix_cap,
                )
                self.assertIs(
                    appended["dropped_term_count"] == 0,
                    drop == 0,
                )
                predecessor_row = rows[34]
                self.assertLessEqual(
                    drop, int(predecessor_row["drop_ticks"])
                )
                self.assertLessEqual(
                    E_after,
                    int(predecessor_row["E_after_if_selected_ticks"]),
                )
                self.assertGreaterEqual(
                    appended["effective_retained_count"],
                    predecessor_row["effective_retained_count"],
                )
                self.assertLessEqual(
                    appended["dropped_term_count"],
                    predecessor_row["dropped_term_count"],
                )
                prefix_common.append(common)
                prefix_old_rows.append(rows[:35])
                prefix_appended_rows.append(appended)
                prefix_all_rows.append(rows)
        self.assertEqual(sum(map(len, prefix_all_rows)), 2_520)
        self.assertEqual(
            digest(prefix_common), EXPECTED_CANONICAL["q1_q70_common_sha256"]
        )
        self.assertEqual(
            digest(prefix_old_rows),
            EXPECTED_CANONICAL["q1_q70_old_rows_sha256"],
        )
        self.assertEqual(
            digest(prefix_appended_rows),
            EXPECTED_CANONICAL["q1_q70_appended_rows_sha256"],
        )
        self.assertEqual(
            digest(prefix_all_rows),
            EXPECTED_CANONICAL["q1_q70_all_rows_sha256"],
        )

        q70 = records[69]
        q71 = records[70]
        old_q71 = self.anchor["records"][70]
        self.assertEqual(frozenset(q71), SCREEN.Q70_SUCCESS_RECORD_KEYS)
        self.assertEqual(
            digest(q71), EXPECTED_CANONICAL["q71_record_sha256"]
        )
        excluded = {
            "candidate_records",
            "removed_491520_counterfactual",
            "status",
            "selected_candidate_index",
            "selected_K",
            *SCREEN.Q70_FAILURE_ONLY_KEYS,
            *SCREEN.Q70_SUCCESS_ONLY_KEYS,
        }
        q71_shared = {
            key: value for key, value in q71.items() if key not in excluded
        }
        old_q71_shared = {
            key: value
            for key, value in old_q71.items()
            if key not in excluded
        }
        self.assertTrue(
            SCREEN.exact_value_equal(q71_shared, old_q71_shared)
        )
        self.assertEqual(
            digest(q71_shared), EXPECTED_CANONICAL["q71_shared_sha256"]
        )
        q71_rows = q71["candidate_records"]
        self.assertEqual(len(q71_rows), 36)
        self.assertEqual(
            digest(q71_rows), EXPECTED_CANONICAL["q71_rows_sha256"]
        )
        self.assertTrue(
            SCREEN.exact_value_equal(
                q71_rows[:35], old_q71["candidate_records"]
            )
        )
        self.assertEqual(
            digest(q71_rows[:35]),
            EXPECTED_CANONICAL["q71_old_rows_sha256"],
        )
        expected_appended_q71 = {
            "candidate_index": 35,
            "configured_K": SCREEN.K622592,
            "effective_retained_count": SCREEN.K622592,
            "dropped_term_count": 138_598,
            "drop_ticks": "95847613475",
            "E_after_if_selected_ticks": "2288967389826722",
            "feasible_under_current_prefix_cap": True,
        }
        self.assertTrue(
            SCREEN.exact_value_equal(q71_rows[35], expected_appended_q71)
        )
        self.assertEqual(
            digest(q71_rows[35]),
            EXPECTED_CANONICAL["q71_appended_row_sha256"],
        )

        exact_q71 = {
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
            "input_expansion_count": SCREEN.K606208,
            "input_expansion_sha256": (
                SCREEN.EXPECTED_Q70_RETAINED_EXPANSION_SHA256
            ),
            "pretruncation_expansion_count": 761_190,
            "pretruncation_expansion_sha256": (
                "e216efffffd7eae98f5e2ff93e24de4896cde49d9f4ee0766b88053d97419e99"
            ),
            "ranked_suffix_sha256": (
                "8762214dccff375ae2df119491460bfb4ab328a80920ad582efc0bb0eca2c195"
            ),
            "E_before_ticks": SCREEN.EXPECTED_Q70_E_AFTER_TICKS,
            "budget_prefix_cap_ticks": SCREEN.EXPECTED_Q71_PREFIX_CAP_TICKS,
            "prefix_slack_before_selection_ticks": "135953610633",
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 35,
            "selected_K": SCREEN.K622592,
            "selected_effective_retained_count": SCREEN.K622592,
            "selected_dropped_term_count": 138_598,
            "selected_drop_ticks": "95847613475",
            "selected_dropped_terms_sha256": (
                "534e5aca80304a2fe5d94e39eebcbfd8e0ffcf9f4a7ee2a51d19f57c3c0f585e"
            ),
            "retained_expansion_count": SCREEN.K622592,
            "retained_expansion_sha256": (
                "50969113d522dadfedced0960548674551acd1ddf56024bb673ce4ee1272b0f4"
            ),
            "minimum_retained_abs_upper_ticks": "4010748",
            "maximum_dropped_abs_upper_ticks": "4010414",
            "E_after_ticks": "2288967389826722",
            "peak_live_terms_this_checkpoint": 761_190,
            "peak_live_terms_cumulative": 761_190,
            "term_gate_visits_increment": 2_636_779,
            "term_gate_visits_cumulative": 90_141_781,
            "rounding_increment_scaled_ticks_squared": (
                "6225617392173923580890072"
            ),
            "rounding_cumulative_scaled_ticks_squared": (
                "123664802029635999140292783"
            ),
            "maximum_expansion_coefficient_tick_bits": 63,
            "maximum_product_bits": 120,
        }
        for field, expected in exact_q71.items():
            with self.subTest(q71_field=field):
                self.assertTrue(SCREEN.exact_value_equal(q71[field], expected))
        self.assertEqual(
            SCREEN.validate_extended_record(q71, q70, 71), SCREEN.K622592
        )

        E_before = int(q71["E_before_ticks"])
        prefix_cap = int(q71["budget_prefix_cap_ticks"])
        q71_drops = []
        feasible_indices = []
        for candidate_index, (configured_K, row) in enumerate(
            zip(SCREEN.D_CANDIDATES, q71_rows)
        ):
            with self.subTest(q71_candidate=candidate_index):
                self.assertEqual(
                    frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                )
                effective = min(
                    configured_K, q71["pretruncation_expansion_count"]
                )
                expected_identity = {
                    "candidate_index": candidate_index,
                    "configured_K": configured_K,
                    "effective_retained_count": effective,
                    "dropped_term_count": (
                        q71["pretruncation_expansion_count"] - effective
                    ),
                }
                for field, expected in expected_identity.items():
                    self.assertTrue(
                        SCREEN.exact_value_equal(row[field], expected)
                    )
                drop = SCREEN.parse_canonical_nonnegative_decimal(
                    row["drop_ticks"], f"q71 row {candidate_index} drop"
                )
                E_after = SCREEN.parse_canonical_nonnegative_decimal(
                    row["E_after_if_selected_ticks"],
                    f"q71 row {candidate_index} E-after",
                )
                self.assertEqual(E_after, E_before + drop)
                feasible = E_after <= prefix_cap
                self.assertIs(
                    row["feasible_under_current_prefix_cap"], feasible
                )
                self.assertIs(row["dropped_term_count"] == 0, drop == 0)
                if feasible:
                    feasible_indices.append(candidate_index)
                q71_drops.append(drop)
        self.assertEqual(q71_drops, sorted(q71_drops, reverse=True))
        self.assertEqual(feasible_indices, [35])

        counterfactual = q71["removed_491520_counterfactual"]
        expected_counterfactual = {
            "configured_K": 491_520,
            "effective_retained_count": 491_520,
            "dropped_term_count": 269_670,
            "drop_ticks": "3126304160428",
            "E_after_if_selected_ticks": "2291997846373675",
            "feasible_under_current_prefix_cap": False,
            "actual_selected_K": SCREEN.K622592,
            "would_precede_selected": False,
            "would_be_selected_if_inserted": False,
        }
        self.assertEqual(
            frozenset(counterfactual), SCREEN.REMOVED_COUNTERFACTUAL_KEYS
        )
        self.assertTrue(
            SCREEN.exact_value_equal(counterfactual, expected_counterfactual)
        )
        self.assertEqual(
            digest(counterfactual),
            EXPECTED_CANONICAL["q71_counterfactual_sha256"],
        )
        choice_fields = {
            "actual_selected_K",
            "would_precede_selected",
            "would_be_selected_if_inserted",
        }
        counterfactual_arithmetic = {
            key: value
            for key, value in counterfactual.items()
            if key not in choice_fields
        }
        old_counterfactual_arithmetic = {
            key: value
            for key, value in old_q71[
                "removed_491520_counterfactual"
            ].items()
            if key not in choice_fields
        }
        self.assertTrue(
            SCREEN.exact_value_equal(
                counterfactual_arithmetic, old_counterfactual_arithmetic
            )
        )
        self.assertEqual(
            digest(counterfactual_arithmetic),
            EXPECTED_CANONICAL["q71_counterfactual_arithmetic_sha256"],
        )

        abort = transcript["resource_policy_abort"]
        expected_abort = {
            "schema_version": 1,
            "abort_id": "D_k622592_c36_q72_live_term_policy_abort_v1",
            "exception_type": "RuntimeError",
            "exception_message": "design policy live-term cap exceeded",
            "exception_args": ["design policy live-term cap exceeded"],
            "exception_chained_from_exact_parent_helper": True,
            "control_flow_parent_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            "helper_source_sha256": SCREEN.EXPECTED_V2_HELPER_SHA256,
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
            "input_expansion_count": SCREEN.K622592,
            "input_expansion_sha256": exact_q71[
                "retained_expansion_sha256"
            ],
            "pretruncation_expansion_count": 799_279,
            "max_single_expansion_terms": 786_432,
            "observed_excess_terms": 12_847,
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
            "q71_committed_record_sha256": EXPECTED_CANONICAL[
                "q71_record_sha256"
            ],
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
        self.assertEqual(frozenset(abort), SCREEN.RESOURCE_POLICY_ABORT_KEYS)
        self.assertEqual(len(abort), 40)
        self.assertTrue(SCREEN.exact_value_equal(abort, expected_abort))
        self.assertEqual(digest(abort), EXPECTED_CANONICAL["abort_sha256"])
        unavailable_q72_fields = {
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
            "candidate_records",
            "selected_candidate_index",
            "selected_K",
            "selected_drop_ticks",
            "E_after_ticks",
        }
        self.assertTrue(unavailable_q72_fields.isdisjoint(abort))
        for field in (
            "q72_pretruncation_digest_computed",
            "q72_ranking_performed",
            "q72_candidate_rows_constructed",
            "q72_selection_performed",
            "q72_commit_performed",
            "q72_checkpoint_record_constructed",
            "q72_partial_expansion_committed",
        ):
            self.assertIs(abort[field], False)
        self.assertEqual(
            abort["observed_excess_terms"],
            abort["pretruncation_expansion_count"]
            - abort["max_single_expansion_terms"],
        )
        self.assertEqual(
            abort["term_gate_visits_cumulative"],
            q71["term_gate_visits_cumulative"]
            + abort["term_gate_visits_increment"],
        )
        self.assertEqual(
            int(abort["rounding_cumulative_scaled_ticks_squared"]),
            int(q71["rounding_cumulative_scaled_ticks_squared"])
            + int(abort["rounding_increment_scaled_ticks_squared"]),
        )
        self.assertEqual(
            abort["peak_live_terms_cumulative"],
            max(
                q71["peak_live_terms_cumulative"],
                abort["peak_live_terms_this_checkpoint"],
            ),
        )
        self.assertEqual(
            abort["input_expansion_count"], q71["retained_expansion_count"]
        )
        self.assertEqual(
            abort["input_expansion_sha256"],
            q71["retained_expansion_sha256"],
        )
        self.assertEqual(
            abort["q71_committed_record_sha256"], digest(q71)
        )

        observed_resources = {
            "observed_peak_single_expansion_terms": 799_279,
            "observed_term_gate_visits_including_terminal_attempt": 92_869_433,
            "observed_maximum_expansion_coefficient_tick_bits": 63,
            "observed_maximum_product_bits": 120,
            "observed_rounding_cumulative_scaled_ticks_squared": (
                "130329045223088501476863488"
            ),
        }
        for field, expected in observed_resources.items():
            self.assertTrue(
                SCREEN.exact_value_equal(transcript[field], expected)
            )
        self.assertEqual(
            transcript["observed_peak_single_expansion_terms"],
            abort["peak_live_terms_cumulative"],
        )
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            abort["term_gate_visits_cumulative"],
        )

        all_rows = [record["candidate_records"] for record in records]
        self.assertEqual(sum(map(len, all_rows)), 2_556)
        self.assertEqual(
            digest(all_rows), EXPECTED_CANONICAL["all_rows_sha256"]
        )
        self.assertEqual(
            digest([record["selected_candidate_index"] for record in records]),
            EXPECTED_CANONICAL["selected_indices_sha256"],
        )

        expected_components = SCREEN.execution_components(
            copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)),
            EXPECTED_SCREEN_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        )
        self.assertEqual(len(expected_components), 11)
        self.assertTrue(
            SCREEN.exact_value_equal(
                transcript["screen_execution_components"],
                expected_components,
            )
        )
        component_paths = []
        for component in expected_components:
            self.assertEqual(
                frozenset(component), {"relative_path", "role", "sha256"}
            )
            self.assertEqual(
                sha256((HERE / component["relative_path"]).read_bytes()),
                component["sha256"],
            )
            component_paths.append(component["relative_path"])
        self.assertEqual(len(component_paths), len(set(component_paths)))
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, component_paths)
        self.assertNotIn(
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, component_paths
        )

        expected_custody = SCREEN.expected_final_source_custody(
            EXPECTED_SCREEN_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        )
        self.assertEqual(len(expected_custody), 10)
        self.assertTrue(
            SCREEN.exact_value_equal(
                transcript["source_custody"], expected_custody
            )
        )
        for relative_path, expected_sha in expected_custody.items():
            self.assertEqual(
                sha256((HERE / relative_path).read_bytes()), expected_sha
            )

        configuration_reference = transcript["configuration_reference"]
        self.assertEqual(
            sha256(
                (HERE / configuration_reference["relative_path"]).read_bytes()
            ),
            configuration_reference["source_sha256"],
        )
        configuration = transcript["configuration_override"]
        incremental = configuration[
            "incremental_route_override_from_k606208_c35_q72"
        ]
        self.assertEqual(incremental["candidate_ladder_added"], [622_592])
        self.assertEqual(incremental["candidate_ladder_removed"], [])
        self.assertEqual(
            incremental["predecessor_candidate_K_values_sha256"],
            SCREEN.EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        )
        self.assertEqual(
            incremental["predecessor_configuration_override_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256,
        )

        capability = transcript["kernel_capability_override"]
        manifest = capability["capability_manifest"]
        self.assertEqual(
            capability["capability_manifest_sha256"], digest(manifest)
        )
        self.assertEqual(
            manifest["source_layers_sha256"], digest(manifest["source_layers"])
        )
        kernel_route = manifest["route_predecessor_reference"]
        self.assertEqual(
            manifest["route_predecessor_reference_sha256"],
            digest(kernel_route),
        )
        self.assertFalse(kernel_route["compiled"])
        self.assertFalse(kernel_route["executed"])
        self.assertFalse(kernel_route["execution_source_layer"])
        for source_layer in manifest["source_layers"]:
            self.assertEqual(
                sha256((HERE / source_layer["relative_path"]).read_bytes()),
                source_layer["sha256"],
            )

        horizon = transcript["parent_horizon_override"]
        self.assertEqual(
            horizon["parent_mode_config_before_sha256"],
            digest(horizon["parent_mode_config_before"]),
        )
        self.assertEqual(
            horizon["parent_mode_config_after_sha256"],
            digest(horizon["parent_mode_config_after"]),
        )
        self.assertEqual(
            horizon["changed_fields"],
            ["MODE_CONFIG.double_occupancy.horizon_checkpoint_count"],
        )
        self.assertEqual(
            horizon["semantic_delta"][
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count"
            ],
            {"before": 66, "after": 72},
        )
        self.assertEqual(
            sha256((HERE / horizon["parent_relative_path"]).read_bytes()),
            horizon["parent_source_sha256"],
        )

        transform = transcript["checkpoint_transform"]
        physical = transform[
            "physical_four_gate_control_flow_parent_transform"
        ]
        self.assertEqual(
            transform[
                "physical_four_gate_control_flow_parent_transform_sha256"
            ],
            SCREEN.EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256,
        )
        self.assertEqual(
            digest(physical), SCREEN.EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
        )
        self.assertEqual(
            transform["route_predecessor_transform_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        )
        self.assertFalse(transform["physical_gate_sequence_changed"])
        self.assertFalse(transform["checkpoint_cadence_changed"])
        self.assertFalse(transform["q71_and_q72_outcomes_precommitted"])

        route = transcript["route_predecessor_reference"]
        route_screen = route["screen"]
        route_canonical = route["canonical_transcript"]
        for layer in (route_screen, route_canonical):
            self.assertFalse(layer["compiled"])
            self.assertFalse(layer["executed"])
            self.assertFalse(layer["execution_source_layer"])
        self.assertFalse(route_canonical["loaded_before_replay_as_exact_reference"])
        self.assertTrue(route_canonical["loaded_after_replay_as_exact_reference"])
        self.assertTrue(route_canonical["post_replay_prefix_validation_input"])
        self.assertFalse(route_canonical["propagation_input"])
        self.assertFalse(route_canonical["checkpoint_70_state_loaded"])
        self.assertFalse(route_canonical["state_resume_input"])
        self.assertEqual(
            sha256((HERE / route_screen["relative_path"]).read_bytes()),
            route_screen["source_sha256"],
        )
        self.assertEqual(
            sha256((HERE / route_canonical["relative_path"]).read_bytes()),
            route_canonical["file_sha256"],
        )
        self.assertEqual(
            route_canonical["q1_through_q70_records_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        )
        self.assertEqual(
            route_canonical["records_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
        )
        self.assertEqual(
            route_canonical["selected_K_history_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        )
        self.assertEqual(
            route_canonical["q70_record_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q70_RECORD_SHA256,
        )
        self.assertEqual(
            route_canonical["q71_failure_record_sha256"],
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256,
        )

        handoff = transcript["predecessor_handoff_validation"]
        self.assertEqual(
            handoff["terminal_branch"],
            "Q71_SUCCESS_Q72_LIVE_TERM_POLICY_ABORT",
        )
        for field in (
            "q1_through_q70_common_records_exact",
            "q1_through_q70_first_35_candidate_rows_exact",
            "q1_through_q70_selected_history_exact",
            "q71_shared_propagation_fields_exact",
            "q71_first_35_candidate_rows_exact",
            "q72_resource_policy_abort_structured",
        ):
            self.assertIs(handoff[field], True)
        self.assertIs(handoff["q72_checkpoint_record_constructed"], False)
        self.assertIs(handoff["q71_and_q72_outcomes_precommitted"], False)
        self.assertEqual(
            handoff["q72_resource_policy_abort_sha256"],
            EXPECTED_CANONICAL["abort_sha256"],
        )

        raw_result = {
            key: copy.deepcopy(transcript[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        raw_components = copy.deepcopy(
            list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
        )
        raw_configuration_reference = {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "source_sha256": (
                SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
            ),
            "role": "candidates_and_caps_reference_only",
            "fields_adopted": [
                f"MODE_CONFIG.{SCREEN.MODE}.candidates",
                "POLICY_CAPS_BASE",
            ],
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "policy_caps_base_sha256": SCREEN.EXPECTED_V6_POLICY_CAPS_SHA256,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
        }
        raw_transform = copy.deepcopy(
            transcript["checkpoint_transform"][
                "physical_four_gate_control_flow_parent_transform"
            ]
        )
        raw_result.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_execution_components": raw_components,
            "screen_execution_components_sha256": digest(raw_components),
            "configuration_reference": raw_configuration_reference,
            "configuration_reference_sha256": digest(
                raw_configuration_reference
            ),
            "checkpoint_transform": raw_transform,
            "checkpoint_transform_sha256": digest(raw_transform),
            "source_custody": copy.deepcopy(
                SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY
            ),
        })
        raw_handoff = SCREEN.validate_replay_handoff(
            copy.deepcopy(raw_result), self.anchor
        )
        self.assertTrue(
            SCREEN.exact_value_equal(raw_handoff, handoff)
        )

        bundle = self.load_static_bundle()
        fresh, parent, configuration, baseline_d, kernel = bundle[:5]
        wrapper_sha, manifest, predecessor, route_reference = bundle[5:]
        horizon_override = fresh.configure_parent_execution(
            parent, configuration, kernel
        )
        relabelled = fresh.validate_and_relabel(
            copy.deepcopy(raw_result),
            predecessor,
            route_reference,
            baseline_d,
            wrapper_sha,
            manifest,
            horizon_override,
        )
        self.assertTrue(
            SCREEN.exact_value_equal(relabelled, transcript)
        )
        self.assertEqual(
            canonical_bytes(relabelled), raw
        )

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_D_K622592_C36_Q72_REPLAY") == "1",
        "set RUN_HUBBARD_L8_D_K622592_C36_Q72_REPLAY=1 for the full replay",
    )
    def test_15_full_replay_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertEqual(result["screen_horizon_checkpoint_count"], 72)
        self.assertIn(
            result["predecessor_handoff_validation"]["terminal_branch"],
            {
                "Q71_FAILURE_Q72_NOT_ATTEMPTED",
                "Q71_SUCCESS_Q72_FAILURE",
                "Q71_SUCCESS_Q72_LIVE_TERM_POLICY_ABORT",
                "Q71_AND_Q72_SUCCESS_HORIZON_REACHED",
            },
        )
        self.assertEqual(
            canonical_bytes(result),
            (HERE / SCREEN.OUTPUT_NAME).read_bytes(),
        )
        self.assertEqual(digest(result), EXPECTED_CANONICAL["file_sha256"])


if __name__ == "__main__":
    unittest.main()
