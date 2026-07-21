#!/usr/bin/env python3
"""Static, synthetic, and opt-in tests for the M K606208/C33 q86 screen."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import types
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q86_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "86e5148a51cb70d2aab21d770ad2b21928caf6e2818786542b287be7c8d02d27"
)
EXPECTED_SCREEN_SIZE = 128_605
CANONICAL_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q86_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 785_288,
    "file_sha256": (
        "fc649a90aa42429d7d746f40bdc7dfe109f1dc6921b46beb8c3396cc3012e875"
    ),
    "records_sha256": (
        "fd0063a55e05d4d6233e3aa10a6ec760ad6e8326ed4ac967f36903ad644b1f99"
    ),
    "history_sha256": (
        "0f209e6373265ab01f092c59ac449f75114765bca50d63029b49f2b37c64c383"
    ),
    "components_sha256": (
        "0c8dd197b62a325eb0de5bba399ab7ae3e7fb1397db410f37ffc02ae18765434"
    ),
    "configuration_reference_sha256": (
        "e421d9c9c57e5dc3f7d5aa3500e9e9776f588bfb65df1a03ccd9292df404e5f2"
    ),
    "configuration_override_sha256": (
        "ae5002b1328fa2628d40c9e00424c84547c31d207e12be781af38e0621a37625"
    ),
    "kernel_override_sha256": (
        "da7168a289c0a4cf125fb3ce69deb0f2baf32dcce73955b6355a0fecf401079b"
    ),
    "parent_horizon_override_sha256": (
        "f104f9d58b66f3941a9c44afa30a18fa3fc867c04a6015f5752d8826b6900949"
    ),
    "route_reference_sha256": (
        "e9e275f330be0f0bb2144bbe5f41eefd9b4e109597a334c10a34b26d8178f283"
    ),
    "handoff_sha256": (
        "ad0cd1cfe671f59ddada311dc9185b0e2cc4a0415e15aa0f8f03972c9e892084"
    ),
    "transform_sha256": (
        "67d7f488b942c6b354fcd88b5d78c57abc4d77fdc00ab66d59b24ea1c336bb27"
    ),
    "source_custody_sha256": (
        "4354fa46f80f41f90f870e644c5ee7f5a9322a84395358a2d004fc7598f41c41"
    ),
    "policy_caps_sha256": (
        "f929d275312ad0a548824b5480fc8363cf7a69c3e06a9890e9170adaac09aa46"
    ),
    "kernel_limits_sha256": (
        "217c1638d5224f2d787f2a44b9b1b087b13ba43f70f2c2774cfddc6e960d8f3f"
    ),
    "input_boundary_sha256": (
        "ffea6f3b7f6e9d02ca6328727e9a2fce51d5f0e48efbf013c48e0b09be0a627d"
    ),
    "sequence_sha256": (
        "6856197e9f50ef42036e2097dcb36ae4d48049cd3c8ad93885d0e6dd2ba726a7"
    ),
    "root_globals_sha256": (
        "4a6a1f974f485a636062bec3b50030856728c581a33c155821214a83f12736d6"
    ),
    "arithmetic_commit_sha256": (
        "d20271851f9f11f3c9a23bbf1b4a461ae22f0f84f9011ea177d345cc14b96c2d"
    ),
    "q1_q84_extended_records_sha256": (
        "bcacdcc5155a4ea11ee8cdc65ea3602603dc8ce480b4272629145aaaa071faad"
    ),
    "q1_q84_common_sha256": (
        "381512f502be83d6a673c08917e47a26ad64b3a87636bbfad07366ce52025bed"
    ),
    "q1_q84_first_32_rows_sha256": (
        "1977a6505d828a900baa26099515214e27b18f2fd6f8a6ac354345c0de00170b"
    ),
    "q1_q84_appended_rows_sha256": (
        "8d57d9e7e2d8d7d14256c075c9f6709c1de8b04bcaf2fdb3ffd18b283bdb3dd7"
    ),
    "q85_record_sha256": (
        "fd154242644c5c2fee5074e1a60e9d1f33bafc999144a984b9bdccc9c18b012c"
    ),
    "q85_rows_sha256": (
        "854356d6cbe63323f4e850d2c702f34ecba3d46fb17cc2522bb3e8986bff037b"
    ),
    "q85_appended_row_sha256": (
        "893b9e8573a33818009987af092e4e19f53ae22bc512dc24142340e8652ebd21"
    ),
    "q86_record_sha256": (
        "19f5c0f51d5c38217a0eac9c26891c6578919c5c6f6eae0808d1e41705ee2c56"
    ),
    "q86_rows_sha256": (
        "933d14be34296d782620af7c3879a011b04e4c5975decda4ede894219933c48d"
    ),
    "all_rows_sha256": (
        "d7df6dc107df70c337ec3f493cc72d874f7c1fe030c70354cf7bd7e234f494de"
    ),
    "selected_indices_sha256": (
        "cceb5be296c15bef1afb5286c676d94b5aeb478c22958b1e2042f84cfd618424"
    ),
    "raw_result_sha256": (
        "05e37e50332ed478a21e57bff058e57bc34a155a6cdc0609adee536481b6183f"
    ),
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def value_digest(value) -> str:
    return sha256(canonical_bytes(value))


def load_screen() -> types.ModuleType:
    path = HERE / SCREEN_NAME
    payload = path.read_bytes()
    module = types.ModuleType("M_k606208_c33_q86_screen_for_tests")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


SCREEN = load_screen()


class MagnetizationK606208C33Q86Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.predecessor, cls.route_reference = SCREEN.load_route_reference(HERE)

    @staticmethod
    def digest(label: str) -> str:
        return sha256(label.encode("ascii"))

    def append_row(self, record, old_rows, checkpoint, *, force_failure=False):
        pre_count = record["pretruncation_expansion_count"]
        effective = min(SCREEN.K606208, pre_count)
        if force_failure:
            drop = int(old_rows[-1]["drop_ticks"])
        elif pre_count <= SCREEN.K606208:
            drop = 0
        else:
            drop = max(1, int(old_rows[-1]["drop_ticks"]) - 1)
        E_before = int(record["E_before_ticks"])
        prefix_cap = int(record["budget_prefix_cap_ticks"])
        return {
            "candidate_index": 32,
            "configured_K": SCREEN.K606208,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
            "drop_ticks": str(drop),
            "E_after_if_selected_ticks": str(E_before + drop),
            "feasible_under_current_prefix_cap": (
                E_before + drop <= prefix_cap
            ),
        }

    def prefix_records(self):
        records = []
        for checkpoint, old in enumerate(self.predecessor["records"][:84], 1):
            record = copy.deepcopy(old)
            record["candidate_records"].append(
                self.append_row(
                    record,
                    old["candidate_records"],
                    checkpoint,
                )
            )
            records.append(record)
        return records

    def q85_record(self, success: bool):
        old = self.predecessor["records"][84]
        record = copy.deepcopy(old)
        appended = self.append_row(
            record,
            old["candidate_records"],
            85,
            force_failure=not success,
        )
        if success:
            appended["drop_ticks"] = "1"
            appended["E_after_if_selected_ticks"] = str(
                int(record["E_before_ticks"]) + 1
            )
            appended["feasible_under_current_prefix_cap"] = True
        record["candidate_records"].append(appended)
        if success:
            for key in SCREEN.Q84_FAILURE_ONLY_KEYS:
                record.pop(key)
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 32,
                "selected_K": SCREEN.K606208,
                "selected_effective_retained_count": SCREEN.K606208,
                "selected_dropped_term_count": appended["dropped_term_count"],
                "selected_drop_ticks": appended["drop_ticks"],
                "selected_dropped_terms_sha256": self.digest("q85-dropped"),
                "retained_expansion_count": SCREEN.K606208,
                "retained_expansion_sha256": self.digest("q85-retained"),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "0",
                "E_after_ticks": appended["E_after_if_selected_ticks"],
            })
        else:
            slack = (
                int(record["budget_prefix_cap_ticks"])
                - int(record["E_before_ticks"])
            )
            record.update({
                "minimum_effective_K_to_meet_prefix": SCREEN.K606208 + 1,
                "required_K_excess_over_policy_maximum": 1,
                "maximum_candidate_drop_excess_over_slack_ticks": str(
                    int(appended["drop_ticks"]) - slack
                ),
            })
        return record

    def q86_record(self, q85, success: bool):
        pre_count = 700_000
        E_before = int(q85["E_after_ticks"])
        prefix_cap = int(SCREEN.EXPECTED_Q86_PREFIX_CAP_TICKS)
        slack = prefix_cap - E_before
        rows = []
        for index, configured_K in enumerate(SCREEN.M_CANDIDATES):
            if success and index == 32:
                drop = 1
            else:
                drop = slack + 33 - index
            effective = min(configured_K, pre_count)
            rows.append({
                "candidate_index": index,
                "configured_K": configured_K,
                "effective_retained_count": effective,
                "dropped_term_count": pre_count - effective,
                "drop_ticks": str(drop),
                "E_after_if_selected_ticks": str(E_before + drop),
                "feasible_under_current_prefix_cap": (
                    E_before + drop <= prefix_cap
                ),
            })
        record = {
            "E_before_ticks": str(E_before),
            "batch_in_stage": 29,
            "budget_prefix_cap_ticks": str(prefix_cap),
            "candidate_records": rows,
            "checkpoint_index_zero_based": 85,
            "checkpoint_number_one_based": 86,
            "gate_batch_sha256": SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[86][
                "gate_batch_sha256"
            ],
            "gate_occurrence_first_zero_based": 340,
            "gate_occurrence_last_zero_based": 343,
            "input_expansion_count": q85["retained_expansion_count"],
            "input_expansion_sha256": q85["retained_expansion_sha256"],
            "maximum_expansion_coefficient_tick_bits": q85[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": q85["maximum_product_bits"],
            "peak_live_terms_cumulative": 700_000,
            "peak_live_terms_this_checkpoint": 700_000,
            "prefix_slack_before_selection_ticks": str(slack),
            "pretruncation_expansion_count": pre_count,
            "pretruncation_expansion_sha256": self.digest("q86-pre"),
            "ranked_suffix_sha256": self.digest("q86-ranked"),
            "rounding_cumulative_scaled_ticks_squared": q85[
                "rounding_cumulative_scaled_ticks_squared"
            ],
            "rounding_increment_scaled_ticks_squared": "0",
            "selected_K": None,
            "selected_candidate_index": None,
            "stage_group": "HU",
            "stage_index": 2,
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            "term_gate_visits_cumulative": (
                q85["term_gate_visits_cumulative"] + SCREEN.K606208
            ),
            "term_gate_visits_increment": SCREEN.K606208,
        }
        if success:
            selected = rows[32]
            record.update({
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": 32,
                "selected_K": SCREEN.K606208,
                "selected_effective_retained_count": SCREEN.K606208,
                "selected_dropped_term_count": selected["dropped_term_count"],
                "selected_drop_ticks": selected["drop_ticks"],
                "selected_dropped_terms_sha256": self.digest("q86-dropped"),
                "retained_expansion_count": SCREEN.K606208,
                "retained_expansion_sha256": self.digest("q86-retained"),
                "minimum_retained_abs_upper_ticks": "1",
                "maximum_dropped_abs_upper_ticks": "0",
                "E_after_ticks": selected["E_after_if_selected_ticks"],
            })
        else:
            record.update({
                "minimum_effective_K_to_meet_prefix": 650_000,
                "required_K_excess_over_policy_maximum": (
                    650_000 - SCREEN.K606208
                ),
                "maximum_candidate_drop_excess_over_slack_ticks": "1",
            })
        return record

    def abort_record(self, q85, kind):
        specifications = {
            "final_live_terms": {
                "message": "design policy live-term cap exceeded",
                "type": "RuntimeError",
                "source": "exact_parent_helper",
                "helper": True,
                "schema": "helper_final_live_terms_v1",
                "pre": SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"] + 5,
                "observed": SCREEN.POLICY_CAPS_BASE[
                    "max_single_expansion_terms"
                ] + 5,
                "cap": SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"],
                "complete": True,
                "policy": True,
                "kernel": False,
                "snapshot": True,
                "relation": (
                    "pretruncation_expansion_count>"
                    "policy_max_single_expansion_terms"
                ),
            },
            "transient_live_terms": {
                "message": "design policy transient live-term cap exceeded",
                "type": "RuntimeError",
                "source": "exact_parent_helper",
                "helper": True,
                "schema": "helper_transient_live_terms_v1",
                "pre": 700_000,
                "observed": SCREEN.POLICY_CAPS_BASE[
                    "max_single_expansion_terms"
                ] + 5,
                "cap": SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"],
                "complete": True,
                "policy": True,
                "kernel": False,
                "snapshot": True,
                "relation": (
                    "peak_live_terms_this_checkpoint>"
                    "policy_max_single_expansion_terms>="
                    "pretruncation_expansion_count"
                ),
            },
            "kernel_single_expansion_terms": {
                "message": "v2 single-expansion term cap exceeded",
                "type": "SchemaError",
                "source": "exact_wrapped_v2_kernel",
                "helper": False,
                "schema": (
                    "kernel_observe_count_before_pre_count_assignment_v1"
                ),
                "pre": None,
                "observed": SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS[
                    "max_single_expansion_terms"
                ] + 1,
                "cap": SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS[
                    "max_single_expansion_terms"
                ],
                "complete": False,
                "policy": False,
                "kernel": True,
                "snapshot": False,
                "relation": (
                    "observed_term_count>kernel_max_single_expansion_terms_"
                    "before_pretruncation_assignment"
                ),
            },
        }
        spec = specifications[kind]
        observed = spec["observed"]
        message = spec["message"]
        abort = {
            "schema_version": 1,
            "abort_id": "M_k606208_c33_q86_policy_resource_abort_v1",
            "abort_kind": kind,
            "abort_frame_local_schema_id": spec["schema"],
            "exception_type": spec["type"],
            "exception_message": message,
            "exception_args": [message],
            "exception_source_role": spec["source"],
            "exception_chained_from_exact_parent_helper": spec["helper"],
            "control_flow_parent_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            "helper_source_sha256": SCREEN.EXPECTED_V2_HELPER_SHA256,
            "kernel_source_sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            "checkpoint_index_zero_based": 85,
            "checkpoint_number_one_based": 86,
            "stage_index": 2,
            "stage_group": "HU",
            "batch_in_stage": 29,
            "gate_occurrence_first_zero_based": 340,
            "gate_occurrence_last_zero_based": 343,
            "gate_batch_sha256": SCREEN.EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[86][
                "gate_batch_sha256"
            ],
            "input_expansion_count": q85["retained_expansion_count"],
            "input_expansion_sha256": q85["retained_expansion_sha256"],
            "pretruncation_expansion_count": spec["pre"],
            "observed_term_count": observed,
            "policy_max_single_expansion_terms": SCREEN.POLICY_CAPS_BASE[
                "max_single_expansion_terms"
            ],
            "kernel_max_single_expansion_terms": (
                SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS[
                    "max_single_expansion_terms"
                ]
            ),
            "enforced_term_cap": spec["cap"],
            "observed_excess_terms": observed - spec["cap"],
            "policy_relation": spec["relation"],
            "gate_batch_propagation_started": True,
            "gate_batch_propagation_completed": spec["complete"],
            "policy_cap_check_reached": spec["policy"],
            "kernel_cap_violation_triggered": spec["kernel"],
            "live_expansion_snapshot_available": spec["snapshot"],
            "q86_pretruncation_digest_computed": False,
            "q86_ranking_performed": False,
            "q86_candidate_rows_constructed": False,
            "q86_selection_performed": False,
            "q86_commit_performed": False,
            "q86_checkpoint_record_constructed": False,
            "q86_partial_expansion_committed": False,
            "q85_committed_record_sha256": SCREEN.sha256(
                SCREEN.canonical_bytes(q85)
            ),
            "peak_live_terms_this_checkpoint": observed,
            "peak_live_terms_cumulative": observed,
            "term_gate_visits_increment": SCREEN.K606208,
            "term_gate_visits_cumulative": (
                q85["term_gate_visits_cumulative"] + SCREEN.K606208
            ),
            "rounding_increment_scaled_ticks_squared": "0",
            "rounding_cumulative_scaled_ticks_squared": q85[
                "rounding_cumulative_scaled_ticks_squared"
            ],
            "maximum_expansion_coefficient_tick_bits": q85[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": q85["maximum_product_bits"],
        }
        self.assertEqual(frozenset(abort), SCREEN.RESOURCE_POLICY_ABORT_KEYS)
        return abort

    def raw_result(self, branch, *, abort_kind="final_live_terms"):
        result = {
            key: copy.deepcopy(self.predecessor[key])
            for key in SCREEN.UPSTREAM_PARENT_RESULT_KEYS
        }
        records = self.prefix_records()
        history = list(self.predecessor["selected_K_history"])
        q85_success = branch != "q85_failure"
        q85 = self.q85_record(q85_success)
        records.append(q85)
        if q85_success:
            history.append(SCREEN.K606208)
        abort = None
        if branch == "q86_failure":
            records.append(self.q86_record(q85, False))
        elif branch == "q86_success":
            records.append(self.q86_record(q85, True))
            history.append(SCREEN.K606208)
        elif branch == "q86_abort":
            abort = self.abort_record(q85, abort_kind)
        elif branch != "q85_failure":
            raise AssertionError(branch)

        raw_transform = self.predecessor["checkpoint_transform"][
            "physical_four_gate_control_flow_parent_transform"
        ]
        raw_configuration = {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "source_sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
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
        final = records[-1]
        failed = (
            abort is None
            and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        if branch == "q85_failure":
            summary = (85, 84, False, False, True)
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            last_E = SCREEN.EXPECTED_Q84_E_AFTER_TICKS
        elif branch == "q86_failure":
            summary = (86, 85, True, False, True)
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            last_E = q85["E_after_ticks"]
        elif branch == "q86_success":
            summary = (86, 86, True, True, False)
            terminal = "DIAGNOSTIC_HORIZON_REACHED"
            last_E = final["E_after_ticks"]
        else:
            summary = (86, 85, True, False, False)
            terminal = "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
            last_E = q85["E_after_ticks"]
        resource = abort if abort is not None else final
        components = list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
        result.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_execution_components": components,
            "screen_execution_components_sha256": SCREEN.sha256(
                SCREEN.canonical_bytes(components)
            ),
            "configuration_reference": raw_configuration,
            "configuration_reference_sha256": SCREEN.sha256(
                SCREEN.canonical_bytes(raw_configuration)
            ),
            "checkpoint_transform": copy.deepcopy(raw_transform),
            "checkpoint_transform_sha256": SCREEN.EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256,
            "source_custody": dict(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY),
            "candidate_K_values": list(SCREEN.M_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "kernel_capability_limits": dict(
                SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS
            ),
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": 33,
            },
            "screen_horizon_checkpoint_count": 86,
            "attempted_checkpoint_count": summary[0],
            "completed_checkpoint_count": summary[1],
            "horizon_checkpoint_attempted": summary[2],
            "horizon_reached_with_committed_checkpoint": summary[3],
            "failure_checkpoint_included": summary[4],
            "screen_terminal_condition": terminal,
            "selected_K_history": history,
            "selected_K_history_sha256": SCREEN.sha256(
                SCREEN.canonical_bytes(history)
            ),
            "records": records,
            "records_sha256": SCREEN.sha256(SCREEN.canonical_bytes(records)),
            "failure_record_sha256": (
                SCREEN.sha256(SCREEN.canonical_bytes(final)) if failed else None
            ),
            "last_committed_cumulative_drop_ticks": last_E,
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
            "resource_policy_abort": abort,
            "resource_policy_abort_sha256": (
                SCREEN.sha256(SCREEN.canonical_bytes(abort))
                if abort is not None
                else None
            ),
        })
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return result

    def static_bundle(self):
        parent = SCREEN.load_control_flow_parent(HERE)
        configuration, baseline = SCREEN.load_configured_v6_baseline(HERE)
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        horizon = SCREEN.configure_parent_execution(
            parent,
            configuration,
            wrapper,
        )
        return baseline, wrapper_sha, manifest, horizon

    def load_canonical(self):
        raw = (HERE / CANONICAL_NAME).read_bytes()
        transcript = json.loads(raw)
        self.assertIs(type(transcript), dict)
        self.assertEqual(raw, canonical_bytes(transcript))
        return raw, transcript

    def reverse_canonical_to_raw(self, canonical):
        """Restore the exact 67-key four-gate parent result before relabel."""

        raw = {
            key: copy.deepcopy(canonical[key])
            for key in SCREEN.UPSTREAM_PARENT_RESULT_KEYS
        }
        raw["resource_policy_abort"] = copy.deepcopy(
            canonical["resource_policy_abort"]
        )
        raw["resource_policy_abort_sha256"] = canonical[
            "resource_policy_abort_sha256"
        ]
        raw_configuration = {
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
            self.predecessor["checkpoint_transform"]
            ["physical_four_gate_control_flow_parent_transform"]
        )
        raw.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "control_flow_owned_by_screen": True,
            "screen_execution_components": copy.deepcopy(
                list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
            ),
            "configuration_reference": raw_configuration,
            "checkpoint_transform": raw_transform,
            "source_custody": copy.deepcopy(
                dict(SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY)
            ),
        })
        for value_key, digest_key in (
            (
                "screen_execution_components",
                "screen_execution_components_sha256",
            ),
            ("configuration_reference", "configuration_reference_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
        ):
            raw[digest_key] = value_digest(raw[value_key])
        self.assertEqual(frozenset(raw), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        self.assertEqual(len(raw), 67)
        return raw

    def assert_exact_success_record(
        self,
        record,
        previous,
        checkpoint,
        exact_fields,
        record_sha,
        rows_sha,
        feasible_indices,
    ):
        self.assertEqual(frozenset(record), SCREEN.Q84_SUCCESS_RECORD_KEYS)
        self.assertEqual(len(record), 37)
        self.assertEqual(value_digest(record), record_sha)
        for field, expected in exact_fields.items():
            with self.subTest(checkpoint=checkpoint, field=field):
                self.assertTrue(
                    SCREEN.exact_value_equal(record[field], expected)
                )

        rows = record["candidate_records"]
        self.assertEqual(len(rows), 33)
        self.assertEqual(value_digest(rows), rows_sha)
        E_before = int(record["E_before_ticks"])
        prefix_cap = int(record["budget_prefix_cap_ticks"])
        self.assertEqual(
            int(record["prefix_slack_before_selection_ticks"]),
            prefix_cap - E_before,
        )
        drops = []
        observed_feasible = []
        for index, (configured_K, row) in enumerate(
            zip(SCREEN.M_CANDIDATES, rows)
        ):
            with self.subTest(checkpoint=checkpoint, candidate=index):
                self.assertEqual(
                    frozenset(row), SCREEN.CANDIDATE_RECORD_KEYS
                )
                effective = min(
                    configured_K,
                    record["pretruncation_expansion_count"],
                )
                self.assertEqual(row["candidate_index"], index)
                self.assertEqual(row["configured_K"], configured_K)
                self.assertEqual(row["effective_retained_count"], effective)
                self.assertEqual(
                    row["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                drop = int(row["drop_ticks"])
                drops.append(drop)
                self.assertEqual(
                    int(row["E_after_if_selected_ticks"]),
                    E_before + drop,
                )
                feasible = E_before + drop <= prefix_cap
                self.assertIs(
                    row["feasible_under_current_prefix_cap"], feasible
                )
                if feasible:
                    observed_feasible.append(index)
        self.assertEqual(drops, sorted(drops, reverse=True))
        self.assertEqual(observed_feasible, feasible_indices)
        self.assertEqual(record["selected_candidate_index"], feasible_indices[0])
        selected = rows[feasible_indices[0]]
        self.assertEqual(record["selected_K"], selected["configured_K"])
        self.assertEqual(
            record["selected_effective_retained_count"],
            selected["effective_retained_count"],
        )
        self.assertEqual(
            record["selected_dropped_term_count"],
            selected["dropped_term_count"],
        )
        self.assertEqual(record["selected_drop_ticks"], selected["drop_ticks"])
        self.assertEqual(
            record["E_after_ticks"], selected["E_after_if_selected_ticks"]
        )
        self.assertEqual(
            record["retained_expansion_count"],
            selected["effective_retained_count"],
        )
        self.assertEqual(
            record["input_expansion_count"],
            previous["retained_expansion_count"],
        )
        self.assertEqual(
            record["input_expansion_sha256"],
            previous["retained_expansion_sha256"],
        )
        self.assertEqual(record["E_before_ticks"], previous["E_after_ticks"])
        self.assertEqual(
            record["peak_live_terms_cumulative"],
            max(
                previous["peak_live_terms_cumulative"],
                record["peak_live_terms_this_checkpoint"],
            ),
        )
        self.assertEqual(
            record["term_gate_visits_cumulative"],
            previous["term_gate_visits_cumulative"]
            + record["term_gate_visits_increment"],
        )
        self.assertEqual(
            int(record["rounding_cumulative_scaled_ticks_squared"]),
            int(previous["rounding_cumulative_scaled_ticks_squared"])
            + int(record["rounding_increment_scaled_ticks_squared"]),
        )
        for digest_field in (
            "gate_batch_sha256",
            "input_expansion_sha256",
            "pretruncation_expansion_sha256",
            "ranked_suffix_sha256",
            "selected_dropped_terms_sha256",
            "retained_expansion_sha256",
        ):
            self.assertTrue(SCREEN.is_canonical_sha256(record[digest_field]))

    def test_01_static_pins_append_only_and_closed_schemas(self):
        SCREEN.validate_local_configuration()
        source = (HERE / SCREEN_NAME).read_bytes()
        self.assertEqual(len(source), EXPECTED_SCREEN_SIZE)
        self.assertEqual(sha256(source), EXPECTED_SCREEN_SHA256)
        self.assertEqual(SCREEN._VERIFIED_SELF_SOURCE_BYTES, source)
        self.assertEqual(SCREEN.fresh_self_module()._VERIFIED_SELF_SOURCE_BYTES, source)
        self.assertEqual(len(SCREEN.V6_M_CANDIDATES), 29)
        self.assertEqual(len(SCREEN.PREDECESSOR_M_CANDIDATES), 32)
        self.assertEqual(len(SCREEN.M_CANDIDATES), 33)
        self.assertEqual(
            SCREEN.M_CANDIDATES,
            SCREEN.PREDECESSOR_M_CANDIDATES + (SCREEN.K606208,),
        )
        self.assertEqual(
            SCREEN.sha256(SCREEN.canonical_bytes(list(SCREEN.M_CANDIDATES))),
            "8c0105608be381ce3ecaeb6178d25c0eda50713e54aa22f734b964bbd5464f86",
        )
        self.assertEqual(len(SCREEN.Q84_SUCCESS_RECORD_KEYS), 37)
        self.assertEqual(len(SCREEN.Q84_FAILURE_RECORD_KEYS), 31)
        self.assertEqual(len(SCREEN.CANDIDATE_RECORD_KEYS), 7)
        self.assertEqual(len(SCREEN.RESOURCE_POLICY_ABORT_KEYS), 50)
        source_size = len(source)
        self.assertLessEqual(source_size, SCREEN.MAX_SELF_SOURCE_BYTES)
        self.assertGreaterEqual(SCREEN.MAX_SELF_SOURCE_BYTES - source_size, 2_000)

    def test_02_direct_parent_wrapper_cross_route_and_post_replay_reference(self):
        parent = SCREEN.load_control_flow_parent(HERE)
        self.assertEqual(
            parent._M_K606208_EXACT_RUN_FOUR_GATE.__code__,
            parent.run_four_gate.__code__,
        )
        baseline, wrapper_sha, manifest, horizon = self.static_bundle()
        self.assertEqual(len(baseline), 29)
        self.assertEqual(wrapper_sha, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertFalse(manifest["route_predecessor_reference"]["compiled"])
        self.assertFalse(manifest["cross_route_reference"]["executed"])
        self.assertEqual(
            horizon["semantic_delta"],
            {"MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                "before": 80,
                "after": 86,
            }},
        )
        self.assertEqual(len(self.predecessor["records"]), 85)
        self.assertEqual(len(self.predecessor["selected_K_history"]), 84)
        self.assertFalse(self.route_reference["screen"]["compiled"])
        self.assertTrue(
            self.route_reference["canonical_transcript"][
                "loaded_after_replay_as_exact_reference"
            ]
        )

    def test_03_four_terminal_branches_and_three_abort_kinds(self):
        cases = {
            "q85_failure": "Q85_FAILURE_Q86_NOT_ATTEMPTED",
            "q86_failure": "Q85_SUCCESS_Q86_FAILURE",
            "q86_success": "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
        }
        for branch, expected in cases.items():
            with self.subTest(branch=branch):
                handoff = SCREEN.validate_replay_handoff(
                    self.raw_result(branch),
                    self.predecessor,
                )
                self.assertEqual(handoff["terminal_branch"], expected)
        for kind in (
            "final_live_terms",
            "transient_live_terms",
            "kernel_single_expansion_terms",
        ):
            with self.subTest(abort_kind=kind):
                result = self.raw_result("q86_abort", abort_kind=kind)
                handoff = SCREEN.validate_replay_handoff(
                    result,
                    self.predecessor,
                )
                self.assertEqual(
                    handoff["terminal_branch"],
                    "Q85_SUCCESS_Q86_RESOURCE_ABORT",
                )
                self.assertEqual(handoff["q86_resource_policy_abort_kind"], kind)
                self.assertEqual(len(result["records"]), 85)
                self.assertEqual(len(result["selected_K_history"]), 85)

    def test_04_actual_helper_and_kernel_traceback_schemas(self):
        parent = SCREEN.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        kernel, _wrapper_sha, _manifest = SCREEN.load_kernel_wrapper(HERE)
        caps = {
            **SCREEN.POLICY_CAPS_BASE,
            "max_candidate_count": 33,
        }
        cap = caps["max_single_expansion_terms"]
        for message, term_count, peak, line, local_keys in (
            (
                "design policy live-term cap exceeded",
                cap + 1,
                cap + 1,
                301,
                {"kernel", "counter", "term_count", "caps"},
            ),
            (
                "design policy transient live-term cap exceeded",
                cap,
                cap + 1,
                313,
                {"kernel", "counter", "term_count", "caps", "checks", "key", "observed"},
            ),
        ):
            counter = types.SimpleNamespace(
                term_gate_visits=0,
                maximum_expansion_coefficient_tick_bits=0,
                maximum_product_bits=0,
                window_peak_live_terms=peak,
            )
            with self.subTest(helper_message=message):
                try:
                    helper.enforce_policy_caps(kernel, counter, term_count, caps)
                except RuntimeError as exception:
                    self.assertEqual(exception.args, (message,))
                    item = SCREEN._traceback_items(exception)[-1]
                    self.assertEqual(item.tb_lineno, line)
                    self.assertEqual(set(item.tb_frame.f_locals), local_keys)
                else:
                    self.fail("helper resource abort was not raised")

        counter = kernel.PropagationCounterV2()
        old_cap = kernel.RESOURCE_LIMITS["max_single_expansion_terms"]
        kernel.RESOURCE_LIMITS["max_single_expansion_terms"] = 1
        denominator = kernel.TICK_DENOMINATOR
        try:
            try:
                kernel.propagate_batch(
                    {(0, 1): (denominator, denominator)},
                    [((1, 0), "theta")],
                    {"theta": (
                        (denominator, denominator),
                        (denominator, denominator),
                    )},
                    counter,
                )
            except kernel.SchemaError as exception:
                self.assertEqual(
                    exception.args,
                    ("v2 single-expansion term cap exceeded",),
                )
                items = SCREEN._traceback_items(exception)
                self.assertEqual(
                    [item.tb_frame.f_code.co_name for item in items[-4:]],
                    ["propagate_batch", "propagate_gate", "add_tick_term", "observe_count"],
                )
                self.assertEqual(
                    SCREEN._exact_kernel_overflow_count(kernel, counter, items),
                    2,
                )
            else:
                self.fail("kernel resource abort was not raised")
        finally:
            kernel.RESOURCE_LIMITS["max_single_expansion_terms"] = old_cap

    def test_05_synchronized_tampering_bool_aliases_and_schema_drift_fail(self):
        cases = []
        configuration = self.raw_result("q86_success")
        configuration["configuration_reference"][
            "candidate_K_values_sha256"
        ] = "0" * 64
        configuration["configuration_reference_sha256"] = SCREEN.sha256(
            SCREEN.canonical_bytes(configuration["configuration_reference"])
        )
        cases.append(configuration)

        transform = self.raw_result("q86_success")
        transform["checkpoint_transform"]["transform_id"] = "tampered"
        transform["checkpoint_transform_sha256"] = SCREEN.sha256(
            SCREEN.canonical_bytes(transform["checkpoint_transform"])
        )
        cases.append(transform)

        old_row = self.raw_result("q86_success")
        old_row["records"][0]["candidate_records"][0]["configured_K"] += 1
        old_row["records_sha256"] = SCREEN.sha256(
            SCREEN.canonical_bytes(old_row["records"])
        )
        cases.append(old_row)

        bool_alias = self.raw_result("q86_success")
        bool_alias["attempted_checkpoint_count"] = True
        cases.append(bool_alias)

        top_schema = self.raw_result("q86_success")
        top_schema["unexpected"] = None
        cases.append(top_schema)

        abort_bool = self.raw_result(
            "q86_abort",
            abort_kind="kernel_single_expansion_terms",
        )
        abort_bool["resource_policy_abort"]["kernel_cap_violation_triggered"] = 1
        abort_bool["resource_policy_abort_sha256"] = SCREEN.sha256(
            SCREEN.canonical_bytes(abort_bool["resource_policy_abort"])
        )
        cases.append(abort_bool)

        transient_negative = self.raw_result(
            "q86_abort",
            abort_kind="transient_live_terms",
        )
        transient_negative["resource_policy_abort"][
            "pretruncation_expansion_count"
        ] = -1
        transient_negative["resource_policy_abort_sha256"] = SCREEN.sha256(
            SCREEN.canonical_bytes(transient_negative["resource_policy_abort"])
        )
        cases.append(transient_negative)

        helper_bypasses_kernel = self.raw_result(
            "q86_abort",
            abort_kind="final_live_terms",
        )
        abort = helper_bypasses_kernel["resource_policy_abort"]
        observed = abort["kernel_max_single_expansion_terms"] + 1
        abort["pretruncation_expansion_count"] = observed
        abort["observed_term_count"] = observed
        abort["observed_excess_terms"] = (
            observed - abort["enforced_term_cap"]
        )
        abort["peak_live_terms_this_checkpoint"] = observed
        abort["peak_live_terms_cumulative"] = observed
        helper_bypasses_kernel["observed_peak_single_expansion_terms"] = observed
        helper_bypasses_kernel["resource_policy_abort_sha256"] = SCREEN.sha256(
            SCREEN.canonical_bytes(abort)
        )
        cases.append(helper_bypasses_kernel)

        for index, result in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(result, self.predecessor)

    def test_06_relabel_closes_components_custody_digests_and_cross_route(self):
        baseline, wrapper_sha, manifest, horizon = self.static_bundle()
        result = SCREEN.validate_and_relabel(
            self.raw_result("q86_abort", abort_kind="transient_live_terms"),
            self.predecessor,
            self.route_reference,
            baseline,
            wrapper_sha,
            manifest,
            horizon,
        )
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS)
        self.assertEqual(len(result["screen_execution_components"]), 11)
        self.assertEqual(len(result["source_custody"]), 10)
        component_paths = {
            item["relative_path"] for item in result["screen_execution_components"]
        }
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, component_paths)
        self.assertNotIn(
            "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py",
            component_paths,
        )
        capability = result["kernel_capability_override"]
        self.assertFalse(
            capability["same_K_cross_route_reference_to_D_k606208_c35"][
                "executed"
            ]
        )
        for value_key, digest_key in (
            ("screen_execution_components", "screen_execution_components_sha256"),
            ("configuration_reference", "configuration_reference_sha256"),
            ("configuration_override", "configuration_override_sha256"),
            ("kernel_capability_override", "kernel_capability_override_sha256"),
            ("parent_horizon_override", "parent_horizon_override_sha256"),
            ("route_predecessor_reference", "route_predecessor_reference_sha256"),
            ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
            ("resource_policy_abort", "resource_policy_abort_sha256"),
        ):
            self.assertEqual(
                result[digest_key],
                SCREEN.sha256(SCREEN.canonical_bytes(result[value_key])),
            )

    def test_07_route_load_order_fresh_self_and_atomic_boundary(self):
        fresh = SCREEN.fresh_self_module()
        events = []
        parent = object()
        configuration = object()
        wrapper = object()
        fresh.load_control_flow_parent = lambda _repo: parent
        fresh.load_configured_v6_baseline = lambda _repo: (
            configuration,
            SCREEN.V6_M_CANDIDATES,
        )
        fresh.load_kernel_wrapper = lambda _repo: (wrapper, "w", {"m": 1})
        fresh.configure_parent_execution = lambda *_args: {"h": 1}

        def replay(*_args):
            events.append("replay")
            return {"raw": True}

        def route(_repo):
            self.assertEqual(events, ["replay"])
            events.append("route")
            return {"predecessor": True}, {"reference": True}

        fresh.execute_parent_with_structured_abort = replay
        fresh.load_route_reference = route
        fresh.validate_and_relabel = lambda *_args: {"ordered": list(events)}
        self.assertEqual(fresh._run_verified(HERE), {"ordered": ["replay", "route"]})

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exceeds output byte cap"):
                SCREEN.write_atomic_bounded(
                    output,
                    b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1),
                )

    def test_08_unknown_exception_is_not_structured(self):
        _baseline, _wrapper_sha, _manifest, _horizon = self.static_bundle()
        kernel, _sha, _manifest = SCREEN.load_kernel_wrapper(HERE)

        class Parent:
            @staticmethod
            def _run_verified(_repo, _mode):
                raise RuntimeError("design policy digest cap exceeded")

        with self.assertRaisesRegex(RuntimeError, "digest cap exceeded"):
            SCREEN.execute_parent_with_structured_abort(Parent(), kernel, HERE)

    def test_09_canonical_exact_bytes_top_level_provenance_and_custody(self):
        raw, transcript = self.load_canonical()
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertEqual(
            frozenset(transcript), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS
        )
        self.assertEqual(len(transcript), 96)

        exact_top = {
            "schema_version": 1,
            "transcript_fingerprint": (
                "hubbard_l8_magnetization_adaptive_k_four_gate_"
                "k606208_c33_q86_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
            "observable_id": "staggered_magnetization",
            "input_step_index": 3,
            "attempted_child_step_index": 4,
            "screen_horizon_checkpoint_count": 86,
            "attempted_checkpoint_count": 86,
            "completed_checkpoint_count": 86,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "last_committed_cumulative_drop_ticks": "1700472573422099",
            "future_checkpoint_denominator": 27_936,
            "remaining_mapped_steps_including_attempt": 97,
            "candidate_K_values": list(SCREEN.M_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "control_flow_owned_by_screen": False,
            "control_flow_owned_by_verified_parent": True,
            "control_flow_parent_private_entrypoint_called": True,
            "candidate_policy_precommitted_at_probe_time": False,
            "child_boundary_committed": False,
            "positive_artifact_generated": False,
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
        }
        for field, expected in exact_top.items():
            with self.subTest(top_field=field):
                self.assertTrue(
                    SCREEN.exact_value_equal(transcript[field], expected)
                )

        embedded = {
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
        for value_field, (digest_field, expected) in embedded.items():
            with self.subTest(nested=value_field):
                self.assertEqual(transcript[digest_field], expected)
                self.assertEqual(value_digest(transcript[value_field]), expected)

        unembedded = {
            "source_custody": "source_custody_sha256",
            "proposed_policy_caps": "policy_caps_sha256",
            "kernel_capability_limits": "kernel_limits_sha256",
            "input_boundary_custody": "input_boundary_sha256",
            "sequence": "sequence_sha256",
            "root_globals_before": "root_globals_sha256",
            "root_globals_after": "root_globals_sha256",
            "arithmetic_kernel_commit": "arithmetic_commit_sha256",
        }
        for value_field, expected_field in unembedded.items():
            with self.subTest(unembedded=value_field):
                self.assertEqual(
                    value_digest(transcript[value_field]),
                    EXPECTED_CANONICAL[expected_field],
                )
        self.assertEqual(
            transcript["parent_expected_witness_sha256"],
            "e5a1fec288bbb118fbc56adfa2ee9d21e0e5f4eb49196a7301d70b361c592ff7",
        )
        self.assertTrue(transcript["root_globals_unchanged"])
        self.assertEqual(
            transcript["root_globals_before"], transcript["root_globals_after"]
        )
        self.assertEqual(
            transcript["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 33},
        )
        self.assertEqual(
            transcript["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

        baseline, wrapper_sha, manifest, horizon = self.static_bundle()
        expected_components = SCREEN.execution_components(
            copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)),
            EXPECTED_SCREEN_SHA256,
            wrapper_sha,
        )
        self.assertEqual(len(expected_components), 11)
        self.assertEqual(
            transcript["screen_execution_components"], expected_components
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
        for forbidden in (
            SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME,
            SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "hubbard_l8_adaptive_k_arithmetic_k589824.py",
            "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py",
        ):
            self.assertNotIn(forbidden, component_paths)

        expected_custody = SCREEN.expected_final_source_custody(
            EXPECTED_SCREEN_SHA256,
            wrapper_sha,
        )
        self.assertEqual(len(expected_custody), 10)
        self.assertEqual(transcript["source_custody"], expected_custody)
        for relative_path, expected_sha in expected_custody.items():
            self.assertEqual(
                sha256((HERE / relative_path).read_bytes()), expected_sha
            )

        self.assertEqual(
            transcript["configuration_override"],
            SCREEN.configuration_override(baseline),
        )
        self.assertEqual(
            transcript["kernel_capability_override"],
            SCREEN.kernel_capability_override(wrapper_sha, manifest),
        )
        self.assertEqual(transcript["parent_horizon_override"], horizon)
        self.assertEqual(
            transcript["route_predecessor_reference"], self.route_reference
        )
        config_delta = transcript["configuration_override"][
            "incremental_route_override_from_k589824_c32_q86"
        ]
        self.assertEqual(config_delta["candidate_ladder_added"], [606_208])
        self.assertEqual(config_delta["candidate_ladder_removed"], [])
        self.assertEqual(
            config_delta["candidate_count"], {"before": 32, "after": 33}
        )
        capability = transcript["kernel_capability_override"]
        self.assertFalse(
            capability["same_K_cross_route_reference_to_D_k606208_c35"][
                "executed"
            ]
        )
        route = transcript["route_predecessor_reference"][
            "canonical_transcript"
        ]
        self.assertFalse(route["loaded_before_replay_as_exact_reference"])
        self.assertTrue(route["loaded_after_replay_as_exact_reference"])
        self.assertFalse(route["propagation_input"])
        self.assertFalse(route["state_resume_input"])
        transform = transcript["checkpoint_transform"]
        self.assertFalse(transform["physical_gate_sequence_changed"])
        self.assertFalse(transform["checkpoint_cadence_changed"])
        self.assertFalse(transform["q85_and_q86_outcomes_precommitted"])

    def test_10_canonical_q1_q84_exact_q85_q86_rows_and_resources(self):
        _raw, transcript = self.load_canonical()
        records = transcript["records"]
        history = transcript["selected_K_history"]
        self.assertEqual((len(records), len(history)), (86, 86))
        self.assertEqual(value_digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(value_digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertEqual(history[:84], self.predecessor["selected_K_history"])
        self.assertEqual(history[-2:], [SCREEN.K606208, SCREEN.K589824])

        common_records = []
        first_32_rows = []
        appended_rows = []
        for checkpoint, (record, old) in enumerate(
            zip(records[:84], self.predecessor["records"][:84]),
            1,
        ):
            with self.subTest(prefix_checkpoint=checkpoint):
                self.assertEqual(frozenset(record), SCREEN.Q84_SUCCESS_RECORD_KEYS)
                old_common = {
                    key: value for key, value in old.items()
                    if key != "candidate_records"
                }
                new_common = {
                    key: value for key, value in record.items()
                    if key != "candidate_records"
                }
                self.assertEqual(new_common, old_common)
                self.assertEqual(
                    record["candidate_records"][:32],
                    old["candidate_records"],
                )
                appended = record["candidate_records"][32]
                self.assertEqual(
                    frozenset(appended), SCREEN.CANDIDATE_RECORD_KEYS
                )
                effective = min(
                    SCREEN.K606208,
                    record["pretruncation_expansion_count"],
                )
                self.assertEqual(appended["candidate_index"], 32)
                self.assertEqual(appended["configured_K"], SCREEN.K606208)
                self.assertEqual(appended["effective_retained_count"], effective)
                self.assertEqual(
                    appended["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                self.assertEqual(
                    int(appended["E_after_if_selected_ticks"]),
                    int(record["E_before_ticks"])
                    + int(appended["drop_ticks"]),
                )
                common_records.append(new_common)
                first_32_rows.append(record["candidate_records"][:32])
                appended_rows.append(appended)
        self.assertEqual(
            value_digest(records[:84]),
            EXPECTED_CANONICAL["q1_q84_extended_records_sha256"],
        )
        self.assertEqual(
            value_digest(common_records),
            EXPECTED_CANONICAL["q1_q84_common_sha256"],
        )
        self.assertEqual(
            value_digest(first_32_rows),
            EXPECTED_CANONICAL["q1_q84_first_32_rows_sha256"],
        )
        self.assertEqual(
            value_digest(appended_rows),
            EXPECTED_CANONICAL["q1_q84_appended_rows_sha256"],
        )

        q84, q85, q86 = records[83:86]
        old_q85 = self.predecessor["records"][84]
        excluded = {
            "candidate_records",
            "status",
            "selected_candidate_index",
            "selected_K",
            *SCREEN.Q84_FAILURE_ONLY_KEYS,
            *SCREEN.Q84_SUCCESS_ONLY_KEYS,
        }
        old_shared = {
            key: value for key, value in old_q85.items()
            if key not in excluded
        }
        self.assertEqual(
            {key: q85[key] for key in old_shared}, old_shared
        )
        self.assertEqual(
            q85["candidate_records"][:32], old_q85["candidate_records"]
        )
        self.assertEqual(
            old_q85["minimum_effective_K_to_meet_prefix"], 592_290
        )
        self.assertEqual(SCREEN.K606208 - 592_290, 13_918)

        q85_exact = {
            "E_after_ticks": "1700259415074873",
            "E_before_ticks": "1700230728891281",
            "batch_in_stage": 28,
            "budget_prefix_cap_ticks": "1700381839070373",
            "checkpoint_index_zero_based": 84,
            "checkpoint_number_one_based": 85,
            "gate_batch_sha256": (
                "34a10608b11edb722a301d2fd60689a6b29389d1ba6dc76376cbb124ae32d77c"
            ),
            "gate_occurrence_first_zero_based": 336,
            "gate_occurrence_last_zero_based": 339,
            "input_expansion_count": 589_824,
            "input_expansion_sha256": (
                "35971741409db21c05aaffcda87ef034a5eebe2199f3ba4b03e62c12bbc24eba"
            ),
            "maximum_dropped_abs_upper_ticks": "2102539",
            "maximum_expansion_coefficient_tick_bits": 57,
            "maximum_product_bits": 121,
            "minimum_retained_abs_upper_ticks": "2102674",
            "peak_live_terms_cumulative": 694_130,
            "peak_live_terms_this_checkpoint": 673_356,
            "prefix_slack_before_selection_ticks": "151110179092",
            "pretruncation_expansion_count": 673_356,
            "pretruncation_expansion_sha256": (
                "c7e3390b1e0a4926e5e08fb02bab86a4ecfb2874d54ac773efeeb786e29691fa"
            ),
            "ranked_suffix_sha256": (
                "7596c4738c7f0d7be43ac86c8cdb9d628c9df62d72b47bae797235f0e3b51b8b"
            ),
            "retained_expansion_count": 606_208,
            "retained_expansion_sha256": (
                "4e20b7cca735748be9550750cca1ef4c2cfc6676c228c04ed43d2438da5369d4"
            ),
            "rounding_cumulative_scaled_ticks_squared": (
                "140304369975807495608715337"
            ),
            "rounding_increment_scaled_ticks_squared": (
                "4170212210430962966031320"
            ),
            "selected_K": 606_208,
            "selected_candidate_index": 32,
            "selected_drop_ticks": "28686183592",
            "selected_dropped_term_count": 67_148,
            "selected_dropped_terms_sha256": (
                "c3674861fa58ad3a4a36743adad8ccc7f615650dd8b2a279dffe156dff192f81"
            ),
            "selected_effective_retained_count": 606_208,
            "stage_group": "HU",
            "stage_index": 2,
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "term_gate_visits_cumulative": 98_908_531,
            "term_gate_visits_increment": 2_484_542,
        }
        self.assert_exact_success_record(
            q85,
            q84,
            85,
            q85_exact,
            EXPECTED_CANONICAL["q85_record_sha256"],
            EXPECTED_CANONICAL["q85_rows_sha256"],
            [32],
        )
        self.assertEqual(
            value_digest(q85["candidate_records"][32]),
            EXPECTED_CANONICAL["q85_appended_row_sha256"],
        )

        q86_exact = {
            "E_after_ticks": "1700472573422099",
            "E_before_ticks": "1700259415074873",
            "batch_in_stage": 29,
            "budget_prefix_cap_ticks": "1700486370476045",
            "checkpoint_index_zero_based": 85,
            "checkpoint_number_one_based": 86,
            "gate_batch_sha256": (
                "890f848373b624e1b7ebe230ef5d32d07a6e862c357317657e72c95ddda4d74f"
            ),
            "gate_occurrence_first_zero_based": 340,
            "gate_occurrence_last_zero_based": 343,
            "input_expansion_count": 606_208,
            "input_expansion_sha256": (
                "4e20b7cca735748be9550750cca1ef4c2cfc6676c228c04ed43d2438da5369d4"
            ),
            "maximum_dropped_abs_upper_ticks": "13731080",
            "maximum_expansion_coefficient_tick_bits": 57,
            "maximum_product_bits": 121,
            "minimum_retained_abs_upper_ticks": "13731080",
            "peak_live_terms_cumulative": 694_130,
            "peak_live_terms_this_checkpoint": 654_324,
            "prefix_slack_before_selection_ticks": "226955401172",
            "pretruncation_expansion_count": 654_324,
            "pretruncation_expansion_sha256": (
                "c2c8e95b1a65cd369120bd3cad84635fdf88d6618571687400df3bcee643cdb0"
            ),
            "ranked_suffix_sha256": (
                "4c7af433a01b30bc0775b622262ad87f1d289491e8e939fc33ebe5d25777fdc6"
            ),
            "retained_expansion_count": 589_824,
            "retained_expansion_sha256": (
                "81892d7c339a3094dbe40a531b23ddcfe642804e1c6e8f1da6ca57fa4915a59e"
            ),
            "rounding_cumulative_scaled_ticks_squared": (
                "143055032727790555859115251"
            ),
            "rounding_increment_scaled_ticks_squared": (
                "2750662751983060250399914"
            ),
            "selected_K": 589_824,
            "selected_candidate_index": 31,
            "selected_drop_ticks": "213158347226",
            "selected_dropped_term_count": 64_500,
            "selected_dropped_terms_sha256": (
                "7e3278b5fc8efe8f4099c010f8d430b825d97f566510bc1138b900c0c80d3935"
            ),
            "selected_effective_retained_count": 589_824,
            "stage_group": "HU",
            "stage_index": 2,
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "term_gate_visits_cumulative": 101_424_121,
            "term_gate_visits_increment": 2_515_590,
        }
        self.assert_exact_success_record(
            q86,
            q85,
            86,
            q86_exact,
            EXPECTED_CANONICAL["q86_record_sha256"],
            EXPECTED_CANONICAL["q86_rows_sha256"],
            [31, 32],
        )
        self.assertEqual(q86["selected_candidate_index"], 31)
        self.assertEqual(q86["selected_K"], SCREEN.K589824)
        self.assertTrue(
            q86["candidate_records"][32][
                "feasible_under_current_prefix_cap"
            ]
        )

        all_rows = [record["candidate_records"] for record in records]
        self.assertEqual(sum(map(len, all_rows)), 86 * 33)
        self.assertEqual(
            value_digest(all_rows), EXPECTED_CANONICAL["all_rows_sha256"]
        )
        self.assertEqual(
            value_digest(
                [record["selected_candidate_index"] for record in records]
            ),
            EXPECTED_CANONICAL["selected_indices_sha256"],
        )
        resources = {
            "observed_peak_single_expansion_terms": 694_130,
            "observed_term_gate_visits_including_terminal_attempt": 101_424_121,
            "observed_maximum_expansion_coefficient_tick_bits": 57,
            "observed_maximum_product_bits": 121,
            "observed_rounding_cumulative_scaled_ticks_squared": (
                "143055032727790555859115251"
            ),
        }
        for field, expected in resources.items():
            self.assertEqual(transcript[field], expected)
        self.assertLessEqual(
            transcript["observed_peak_single_expansion_terms"],
            transcript["proposed_policy_caps"]["max_single_expansion_terms"],
        )
        self.assertLessEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            transcript["proposed_policy_caps"]["max_term_gate_visits"],
        )
        handoff = transcript["predecessor_handoff_validation"]
        self.assertEqual(
            handoff["terminal_branch"],
            "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
        )
        self.assertTrue(handoff["q1_through_q84_common_records_exact"])
        self.assertTrue(
            handoff["q1_through_q84_first_32_candidate_rows_exact"]
        )
        self.assertTrue(handoff["q1_through_q84_selected_history_exact"])
        self.assertTrue(handoff["q86_checkpoint_record_constructed"])
        self.assertFalse(handoff["q85_and_q86_outcomes_precommitted"])

    def test_11_canonical_reverses_to_raw67_and_relabels_exact_final96(self):
        expected_bytes, canonical = self.load_canonical()
        raw = self.reverse_canonical_to_raw(canonical)
        self.assertEqual(
            value_digest(raw), EXPECTED_CANONICAL["raw_result_sha256"]
        )
        self.assertEqual(
            SCREEN.validate_replay_handoff(
                copy.deepcopy(raw), self.predecessor
            )["terminal_branch"],
            "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
        )
        baseline, wrapper_sha, manifest, horizon = self.static_bundle()
        relabelled = SCREEN.validate_and_relabel(
            copy.deepcopy(raw),
            self.predecessor,
            self.route_reference,
            baseline,
            wrapper_sha,
            manifest,
            horizon,
        )
        self.assertEqual(relabelled, canonical)
        self.assertEqual(canonical_bytes(relabelled), expected_bytes)
        self.assertEqual(
            value_digest(relabelled), EXPECTED_CANONICAL["file_sha256"]
        )

    @unittest.skipUnless(
        os.environ.get("FERMION_RUN_M606208_C33_Q86_REPLAY") == "1",
        "expensive canonical replay is opt-in",
    )
    def test_99_full_replay_opt_in(self):
        expected = (HERE / CANONICAL_NAME).read_bytes()
        observed = canonical_bytes(SCREEN.run(HERE))
        self.assertEqual(observed, expected)
        self.assertEqual(len(observed), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(sha256(observed), EXPECTED_CANONICAL["file_sha256"])


if __name__ == "__main__":
    unittest.main()
