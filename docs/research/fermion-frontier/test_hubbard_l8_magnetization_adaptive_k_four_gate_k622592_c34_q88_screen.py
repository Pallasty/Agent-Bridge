#!/usr/bin/env python3
"""Static, synthetic, and opt-in tests for M K622592/C34 fixed q88."""

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
    "k622592_c34_q88_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4"
)
EXPECTED_SCREEN_SIZE = 78_218
CANONICAL_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q88_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 821_781,
    "file_sha256": (
        "0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a"
    ),
    "records_sha256": (
        "8832c0fd7c61146f2aa3c5e9a3a827972c459a126c2d371b5a5c41bac700c804"
    ),
    "history_sha256": (
        "58cd214e13f4c122f710aad62ac0e52ead1aed0fa7d8a7e2498ea6013c7f4726"
    ),
    "q1_q87_common_sha256": (
        "2ad0d8a01ca54572f056252373fcf7a9e2dfa38b96aecfc67a26fbe41fc7f353"
    ),
    "q1_q87_old_rows_sha256": (
        "89a45f8e68c6395cf3ee4225cfddb0261aa513bf31f30902e3cb58a268dadb01"
    ),
    "q1_q87_history_sha256": (
        "e340ab1968faabaa070ba04a549ede8c7b27018897521e598ab5fd9714db3bb3"
    ),
    "q87_record_sha256": (
        "58afecf983ecb13b76f4e05584c25a1a663116fac438f0c9ac4b2e6da5feb396"
    ),
    "q87_rows_sha256": (
        "fa981f36125ec2895a67c9d3c12c8e036e2decc642af2c759b5220145d608961"
    ),
    "q87_appended_sha256": (
        "9c3d07987e0bc071294808ed872b31b1daf533e3d6928f8dbd31d4ca55fd41c4"
    ),
    "q88_record_sha256": (
        "aa0c1f25c2957f1f0dbe9d71ad67fa14e217ecbec20e3badbad1cd3d465f9461"
    ),
    "q88_rows_sha256": (
        "bec83189ac3f784e82342aa94d1ef0b257a0b1fba0bd38a82e7ee84a5511c8d9"
    ),
    "q88_old_rows_sha256": (
        "066028a4ed7119b5e584cc1bcdba5bd0d3c1e4a219c343281b42aa24a1ea2a2a"
    ),
    "q88_physical_sha256": (
        "f9ac92d5d2d1734f239cd90688bffd048d21ae8a323764676d3038d51be1f022"
    ),
    "q88_appended_sha256": (
        "4340f4609affb046d045ab655c9483ac6e1f3ba4403016df77ce785e2bffe4f0"
    ),
    "components_sha256": (
        "27c5d848da8c8651fea8935ba58b817264ee1846d5f7d4aa40d4a4e224afae99"
    ),
    "custody_sha256": (
        "14c88e017bc16aeb1406c31aae41e04cabf50dffcce6aa2de9253f6d7323564e"
    ),
    "handoff_sha256": (
        "af84dcc4ceafb293d144f8a4d3a7c426854527c32d46cf5d0d0d75bfd777c915"
    ),
    "configuration_reference_sha256": (
        "e421d9c9c57e5dc3f7d5aa3500e9e9776f588bfb65df1a03ccd9292df404e5f2"
    ),
    "configuration_override_sha256": (
        "836107afb82a7c377c1d5b7e768d6c69fc238292d1c84316fce2dcd96fa41c6a"
    ),
    "kernel_capability_override_sha256": (
        "36e24d5b0f615862042a79093059c1a7a00c7be6e97dae30f69a1d723b08c866"
    ),
    "parent_horizon_override_sha256": (
        "f4b28e1ffdbc72dffdc70af3c796a2808b3a9ed3e024d4f1183b6650fbf0fce3"
    ),
    "route_predecessor_reference_sha256": (
        "c8c392bd124d7bea65c998ef821e5226c83ce256c8350a75d992cf27e29f815f"
    ),
    "checkpoint_transform_sha256": (
        "3c1d764768df6ff87b22ca9738a7f55cc4c991da40a22b72114d09241bdc64b8"
    ),
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("m_k622592_c34_q88_for_tests", SCREEN_NAME)


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


class MagnetizationK622592C34Q88Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.predecessor, self.route_reference = SCREEN.load_route_reference(HERE)

    @staticmethod
    def synthetic_sha(label: str) -> str:
        return hashlib.sha256(f"synthetic-M-C34-{label}".encode("ascii")).hexdigest()

    def appended_row(self, record, *, q88=False):
        pre_count = record["pretruncation_expansion_count"]
        effective = min(SCREEN.K622592, pre_count)
        dropped = pre_count - effective
        E_before = int(record["E_before_ticks"])
        slack = int(record["prefix_slack_before_selection_ticks"])
        drop = slack - 1 if q88 else 0
        return {
            "candidate_index": 33,
            "configured_K": SCREEN.K622592,
            "effective_retained_count": effective,
            "dropped_term_count": dropped,
            "drop_ticks": str(drop),
            "E_after_if_selected_ticks": str(E_before + drop),
            "feasible_under_current_prefix_cap": True,
        }

    def make_raw_success(self):
        raw = {
            key: copy.deepcopy(self.predecessor[key])
            for key in SCREEN.EXPECTED_PARENT_RESULT_KEYS
        }
        records = copy.deepcopy(self.predecessor["records"])
        for record in records[:87]:
            record["candidate_records"].append(self.appended_row(record))
        q88 = records[87]
        appended = self.appended_row(q88, q88=True)
        q88["candidate_records"].append(appended)
        for key in SCREEN.RECORD_FAILURE_ONLY_KEYS:
            q88.pop(key)
        q88.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 33,
            "selected_K": SCREEN.K622592,
            "selected_effective_retained_count": SCREEN.K622592,
            "selected_dropped_term_count": (
                SCREEN.EXPECTED_Q88_PRETRUNCATION_COUNT - SCREEN.K622592
            ),
            "selected_drop_ticks": appended["drop_ticks"],
            "selected_dropped_terms_sha256": self.synthetic_sha("q88-dropped"),
            "retained_expansion_count": SCREEN.K622592,
            "retained_expansion_sha256": self.synthetic_sha("q88-retained"),
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": appended["E_after_if_selected_ticks"],
        })
        self.assertEqual(frozenset(q88), SCREEN.RECORD_SUCCESS_RECORD_KEYS)
        history = copy.deepcopy(self.predecessor["selected_K_history"])
        history.append(SCREEN.K622592)
        raw.update({
            "candidate_K_values": list(SCREEN.M_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": 34,
            },
            "kernel_capability_limits": copy.deepcopy(
                SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS
            ),
            "screen_horizon_checkpoint_count": 88,
            "attempted_checkpoint_count": 88,
            "completed_checkpoint_count": 88,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "selected_K_history": history,
            "selected_K_history_sha256": digest(history),
            "records": records,
            "records_sha256": digest(records),
            "last_committed_cumulative_drop_ticks": q88["E_after_ticks"],
            "observed_peak_single_expansion_terms": q88[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": q88[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": q88[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": q88["maximum_product_bits"],
            "observed_rounding_cumulative_scaled_ticks_squared": q88[
                "rounding_cumulative_scaled_ticks_squared"
            ],
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
            "screen_execution_components": copy.deepcopy(
                list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)
            ),
            "source_custody": copy.deepcopy(
                SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY
            ),
        })
        raw["screen_execution_components_sha256"] = digest(
            raw["screen_execution_components"]
        )
        raw_transform = self.predecessor["checkpoint_transform"][
            "physical_four_gate_control_flow_parent_transform"
        ]
        raw["checkpoint_transform"] = copy.deepcopy(raw_transform)
        raw["checkpoint_transform_sha256"] = digest(raw_transform)
        raw["configuration_reference"] = {"synthetic_parent_reference": True}
        raw["configuration_reference_sha256"] = digest(
            raw["configuration_reference"]
        )
        self.assertEqual(frozenset(raw), SCREEN.EXPECTED_PARENT_RESULT_KEYS)
        return raw

    def static_bundle(self):
        parent = SCREEN.load_control_flow_parent(HERE)
        configuration, baseline_m = SCREEN.load_configured_v6_baseline(HERE)
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        horizon = SCREEN.configure_parent_execution(
            parent, configuration, wrapper
        )
        return parent, baseline_m, wrapper_sha, manifest, horizon

    def test_01_exact_source_ladder_caps_and_closed_schemas(self):
        raw = (HERE / SCREEN_NAME).read_bytes()
        self.assertEqual(len(raw), EXPECTED_SCREEN_SIZE)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SCREEN_SHA256)
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.ROUTE_M_CANDIDATES), 33)
        self.assertEqual(len(SCREEN.M_CANDIDATES), 34)
        self.assertEqual(
            SCREEN.M_CANDIDATES,
            SCREEN.ROUTE_M_CANDIDATES + (SCREEN.K622592,),
        )
        self.assertNotIn(SCREEN.EXPECTED_Q88_MINIMUM_EFFECTIVE_K, SCREEN.M_CANDIDATES)
        self.assertEqual(
            digest(list(SCREEN.M_CANDIDATES)),
            SCREEN.EXPECTED_CANDIDATE_SHA256,
        )
        self.assertEqual(
            {
                "upstream": len(SCREEN.UPSTREAM_PARENT_RESULT_KEYS),
                "raw": len(SCREEN.EXPECTED_PARENT_RESULT_KEYS),
                "final": len(SCREEN.EXPECTED_RELABELLED_RESULT_KEYS),
                "success": len(SCREEN.RECORD_SUCCESS_RECORD_KEYS),
                "failure": len(SCREEN.RECORD_FAILURE_RECORD_KEYS),
                "row": len(SCREEN.CANDIDATE_RECORD_KEYS),
                "abort": len(SCREEN.RESOURCE_POLICY_ABORT_KEYS),
            },
            {
                "upstream": 65, "raw": 67, "final": 96,
                "success": 37, "failure": 31, "row": 7, "abort": 50,
            },
        )
        self.assertLessEqual(len(raw), SCREEN.MAX_SELF_SOURCE_BYTES)

    def test_02_direct_b483_parent_v6_and_wrapper_relationships(self):
        parent, baseline_m, wrapper_sha, manifest, horizon = self.static_bundle()
        self.assertEqual(
            hashlib.sha256(parent._VERIFIED_SELF_SOURCE_BYTES).hexdigest(),
            SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        )
        self.assertEqual(
            SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614",
        )
        self.assertEqual(len(baseline_m), 29)
        self.assertEqual(wrapper_sha, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(
            manifest["route_predecessor_reference"]["relative_path"],
            "hubbard_l8_adaptive_k_arithmetic_k606208_c33.py",
        )
        self.assertEqual(
            manifest["cross_route_reference"]["relative_path"],
            "hubbard_l8_adaptive_k_arithmetic_k622592_c36.py",
        )
        for reference in (
            manifest["route_predecessor_reference"],
            manifest["cross_route_reference"],
        ):
            self.assertFalse(reference["compiled"])
            self.assertFalse(reference["executed"])
            self.assertFalse(reference["execution_source_layer"])
        self.assertEqual(
            horizon["semantic_delta"],
            {
                "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                    "before": 80, "after": 88,
                }
            },
        )
        self.assertTrue(horizon["double_occupancy_configuration_unchanged"])

    def test_03_route_q88_is_exact_and_post_only(self):
        self.assertEqual(len(self.predecessor["records"]), 88)
        self.assertEqual(len(self.predecessor["selected_K_history"]), 87)
        screen_ref = self.route_reference["route_predecessor_screen"]
        canonical_ref = self.route_reference["canonical_transcript"]
        self.assertFalse(screen_ref["compiled"])
        self.assertFalse(screen_ref["executed"])
        self.assertFalse(screen_ref["private_entrypoint_called"])
        self.assertFalse(canonical_ref["loaded_before_replay"])
        self.assertTrue(canonical_ref["loaded_after_full_replay_as_exact_reference"])
        self.assertFalse(canonical_ref["propagation_input"])
        self.assertFalse(canonical_ref["state_resume_input"])
        self.assertEqual(
            self.route_reference["q88_threshold_evidence"],
            SCREEN.Q88_THRESHOLD_EVIDENCE,
        )
        self.assertFalse(
            SCREEN.Q88_THRESHOLD_EVIDENCE["K607993_execution_row_constructed"]
        )

    def test_04_private_run_orders_replay_before_route_read_without_real_run(self):
        saved = {
            name: getattr(SCREEN, name)
            for name in (
                "validate_local_configuration", "load_control_flow_parent",
                "load_configured_v6_baseline", "load_kernel_wrapper",
                "configure_parent_execution", "execute_parent_fail_closed",
                "load_route_reference", "validate_and_relabel",
            )
        }
        old_self = SCREEN._VERIFIED_SELF_SOURCE_BYTES
        calls = []
        sentinel = {"done": True}
        try:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = b"synthetic-self"
            SCREEN.validate_local_configuration = lambda: calls.append("validate")
            SCREEN.load_control_flow_parent = (
                lambda _repo: calls.append("parent") or object()
            )
            SCREEN.load_configured_v6_baseline = (
                lambda _repo: calls.append("configuration") or (object(), ())
            )
            SCREEN.load_kernel_wrapper = (
                lambda _repo: calls.append("wrapper") or (object(), "w", {})
            )
            SCREEN.configure_parent_execution = (
                lambda *_args: calls.append("horizon") or {}
            )
            SCREEN.execute_parent_fail_closed = (
                lambda *_args: calls.append("replay") or {}
            )
            SCREEN.load_route_reference = (
                lambda _repo: calls.append("route_after_replay") or ({}, {})
            )
            SCREEN.validate_and_relabel = (
                lambda *_args: calls.append("relabel") or sentinel
            )
            self.assertIs(SCREEN._run_verified(HERE), sentinel)
        finally:
            for name, value in saved.items():
                setattr(SCREEN, name, value)
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = old_self
        self.assertEqual(
            calls,
            [
                "validate", "parent", "configuration", "wrapper", "horizon",
                "replay", "route_after_replay", "relabel",
            ],
        )

    def test_05_known_and_unknown_resource_errors_propagate_by_identity(self):
        class Parent:
            def __init__(self, error):
                self.error = error

            def _run_verified(self, _repo, _mode):
                raise self.error

        errors = (
            RuntimeError("design policy live-term cap exceeded"),
            RuntimeError("design policy transient live-term cap exceeded"),
            ValueError("unknown resource-shaped error"),
        )
        for error in errors:
            with self.subTest(error=repr(error)):
                with self.assertRaises(type(error)) as caught:
                    SCREEN.execute_parent_fail_closed(Parent(error), HERE)
                self.assertIs(caught.exception, error)

    def test_06_synthetic_index33_first_feasible_success_is_strict(self):
        raw = self.make_raw_success()
        handoff = SCREEN.validate_replay_handoff(raw, self.predecessor)
        self.assertEqual(
            handoff["q88_terminal_branch"],
            "Q88_INDEX33_FIRST_FEASIBLE_SUCCESS",
        )
        self.assertTrue(handoff["q1_through_q87_common_records_exact"])
        self.assertTrue(handoff["q88_propagation_and_ranking_exact"])
        self.assertTrue(handoff["q88_appended_candidate_first_feasible"])
        self.assertFalse(handoff["K607993_execution_row_constructed"])
        self.assertEqual(len(raw["records"]), 88)
        self.assertEqual(len(raw["selected_K_history"]), 88)
        self.assertTrue(
            all(len(record["candidate_records"]) == 34 for record in raw["records"])
        )

    def test_07_failure_non_first_feasible_old_row_and_resource_are_rejected(self):
        cases = []
        failure = self.make_raw_success()
        q88 = failure["records"][87]
        q88["status"] = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        q88["selected_candidate_index"] = None
        q88["selected_K"] = None
        for key in SCREEN.RECORD_SUCCESS_ONLY_KEYS:
            q88.pop(key)
        q88.update({
            "minimum_effective_K_to_meet_prefix": 622_593,
            "required_K_excess_over_policy_maximum": 1,
            "maximum_candidate_drop_excess_over_slack_ticks": "1",
        })
        q88["candidate_records"][33]["feasible_under_current_prefix_cap"] = False
        failure["records_sha256"] = digest(failure["records"])
        cases.append(failure)

        non_first = self.make_raw_success()
        non_first["records"][87]["selected_candidate_index"] = 32
        non_first["records_sha256"] = digest(non_first["records"])
        cases.append(non_first)

        old_row = self.make_raw_success()
        old_row["records"][87]["candidate_records"][32]["drop_ticks"] = "0"
        old_row["records_sha256"] = digest(old_row["records"])
        cases.append(old_row)

        resource = self.make_raw_success()
        resource["resource_policy_abort"] = {"status": "abort"}
        resource["resource_policy_abort_sha256"] = digest(
            resource["resource_policy_abort"]
        )
        cases.append(resource)

        for index, raw in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(raw, self.predecessor)

    def test_08_zero_drop_monotonicity_and_ranking_boundary_forgery_rejected(self):
        zero_drop_forgery = self.make_raw_success()
        q1 = zero_drop_forgery["records"][0]
        appended_q1 = q1["candidate_records"][33]
        self.assertEqual(appended_q1["dropped_term_count"], 0)
        appended_q1["drop_ticks"] = "1"
        appended_q1["E_after_if_selected_ticks"] = str(
            int(q1["E_before_ticks"]) + 1
        )
        zero_drop_forgery["records_sha256"] = digest(
            zero_drop_forgery["records"]
        )

        monotonicity_forgery = self.make_raw_success()
        q87 = monotonicity_forgery["records"][86]
        predecessor_max = q87["candidate_records"][32]
        appended_q87 = q87["candidate_records"][33]
        forged_drop = int(predecessor_max["drop_ticks"]) + 1
        appended_q87["drop_ticks"] = str(forged_drop)
        appended_q87["E_after_if_selected_ticks"] = str(
            int(q87["E_before_ticks"]) + forged_drop
        )
        appended_q87["feasible_under_current_prefix_cap"] = True
        monotonicity_forgery["records_sha256"] = digest(
            monotonicity_forgery["records"]
        )

        ranking_boundary_forgery = self.make_raw_success()
        forged_q88 = ranking_boundary_forgery["records"][87]
        forged_q88["minimum_retained_abs_upper_ticks"] = "0"
        forged_q88["maximum_dropped_abs_upper_ticks"] = "1"
        ranking_boundary_forgery["records_sha256"] = digest(
            ranking_boundary_forgery["records"]
        )

        for label, raw in (
            ("zero_dropped_nonzero_drop", zero_drop_forgery),
            ("appended_monotonicity", monotonicity_forgery),
            ("ranking_boundary", ranking_boundary_forgery),
        ):
            with self.subTest(forgery=label):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(raw, self.predecessor)

    def test_09_synthetic_relabel_closes_components_custody_and_authority(self):
        raw = self.make_raw_success()
        _parent, baseline_m, wrapper_sha, manifest, horizon = self.static_bundle()
        old_self = SCREEN._VERIFIED_SELF_SOURCE_BYTES
        screen_raw = (HERE / SCREEN_NAME).read_bytes()
        SCREEN._VERIFIED_SELF_SOURCE_BYTES = screen_raw
        try:
            result = SCREEN.validate_and_relabel(
                raw,
                self.predecessor,
                self.route_reference,
                baseline_m,
                wrapper_sha,
                manifest,
                horizon,
            )
        finally:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = old_self
        self.assertEqual(frozenset(result), SCREEN.EXPECTED_RELABELLED_RESULT_KEYS)
        self.assertEqual(len(result["screen_execution_components"]), 11)
        self.assertEqual(len(result["source_custody"]), 10)
        paths = {
            item["relative_path"]
            for item in result["screen_execution_components"]
        }
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        self.assertNotIn(
            "hubbard_l8_adaptive_k_arithmetic_k606208_c33.py", paths
        )
        self.assertNotIn(
            "hubbard_l8_adaptive_k_arithmetic_k622592_c36.py", paths
        )
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        self.assertEqual(result["resource_policy_abort"], None)
        self.assertEqual(result["resource_policy_abort_sha256"], None)
        for value_key, digest_key in (
            ("screen_execution_components", "screen_execution_components_sha256"),
            ("configuration_reference", "configuration_reference_sha256"),
            ("configuration_override", "configuration_override_sha256"),
            ("kernel_capability_override", "kernel_capability_override_sha256"),
            ("parent_horizon_override", "parent_horizon_override_sha256"),
            ("route_predecessor_reference", "route_predecessor_reference_sha256"),
            ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
        ):
            self.assertEqual(result[digest_key], digest(result[value_key]))

    def test_10_canonical_exact_bytes_ledgers_rows_and_nested_closure(self):
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
        self.assertEqual((len(records), len(history)), (88, 88))
        self.assertEqual(
            sum(len(record["candidate_records"]) for record in records),
            2_992,
        )
        self.assertTrue(
            all(len(record["candidate_records"]) == 34 for record in records)
        )
        self.assertEqual(digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(
            transcript["records_sha256"], EXPECTED_CANONICAL["records_sha256"]
        )
        self.assertEqual(digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            EXPECTED_CANONICAL["history_sha256"],
        )

        common = lambda record: {
            key: value
            for key, value in record.items()
            if key != "candidate_records"
        }
        q1_q87_common = [common(record) for record in records[:87]]
        predecessor_common = [
            common(record) for record in self.predecessor["records"][:87]
        ]
        old_rows = [
            record["candidate_records"][:33] for record in records[:87]
        ]
        predecessor_rows = [
            record["candidate_records"]
            for record in self.predecessor["records"][:87]
        ]
        self.assertEqual(q1_q87_common, predecessor_common)
        self.assertEqual(old_rows, predecessor_rows)
        self.assertEqual(history[:87], self.predecessor["selected_K_history"])
        self.assertEqual(
            digest(q1_q87_common),
            EXPECTED_CANONICAL["q1_q87_common_sha256"],
        )
        self.assertEqual(
            digest(old_rows), EXPECTED_CANONICAL["q1_q87_old_rows_sha256"]
        )
        self.assertEqual(
            digest(history[:87]),
            EXPECTED_CANONICAL["q1_q87_history_sha256"],
        )

        q87, q88 = records[86], records[87]
        self.assertEqual(digest(q87), EXPECTED_CANONICAL["q87_record_sha256"])
        self.assertEqual(
            digest(q87["candidate_records"]),
            EXPECTED_CANONICAL["q87_rows_sha256"],
        )
        q87_appended = q87["candidate_records"][33]
        self.assertEqual(
            digest(q87_appended), EXPECTED_CANONICAL["q87_appended_sha256"]
        )
        self.assertEqual(q87_appended, {
            "candidate_index": 33,
            "configured_K": 622_592,
            "effective_retained_count": 622_592,
            "dropped_term_count": 23_026,
            "drop_ticks": "3432942770",
            "E_after_if_selected_ticks": "1700476006364869",
            "feasible_under_current_prefix_cap": True,
        })

        self.assertEqual(digest(q88), EXPECTED_CANONICAL["q88_record_sha256"])
        self.assertEqual(
            digest(q88["candidate_records"]),
            EXPECTED_CANONICAL["q88_rows_sha256"],
        )
        self.assertEqual(
            q88["candidate_records"][:33],
            self.predecessor["records"][87]["candidate_records"],
        )
        self.assertEqual(
            digest(q88["candidate_records"][:33]),
            EXPECTED_CANONICAL["q88_old_rows_sha256"],
        )
        physical = {
            key: q88[key] for key in SCREEN.Q88_PHYSICAL_COMMON_KEYS
        }
        predecessor_physical = {
            key: self.predecessor["records"][87][key]
            for key in SCREEN.Q88_PHYSICAL_COMMON_KEYS
        }
        self.assertEqual(physical, predecessor_physical)
        self.assertEqual(
            digest(physical), EXPECTED_CANONICAL["q88_physical_sha256"]
        )
        q88_appended = q88["candidate_records"][33]
        self.assertEqual(
            digest(q88_appended), EXPECTED_CANONICAL["q88_appended_sha256"]
        )
        self.assertEqual(q88_appended, {
            "candidate_index": 33,
            "configured_K": 622_592,
            "effective_retained_count": 622_592,
            "dropped_term_count": 66_650,
            "drop_ticks": "33833242742",
            "E_after_if_selected_ticks": "1700535038508063",
            "feasible_under_current_prefix_cap": True,
        })
        q88_exact = {
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "E_before_ticks": "1700501205265321",
            "budget_prefix_cap_ticks": "1700695433287388",
            "prefix_slack_before_selection_ticks": "194228022067",
            "pretruncation_expansion_count": 689_242,
            "pretruncation_expansion_sha256": (
                "565071e6410de1f107c493346dd41b9b60f0de3727a41d22be42155314da3c40"
            ),
            "ranked_suffix_sha256": (
                "89ca8be11455b2812d6fe9a441bb9d9d182bbde987a8f9155893bbf4ae73ed68"
            ),
            "selected_candidate_index": 33,
            "selected_K": 622_592,
            "selected_effective_retained_count": 622_592,
            "selected_dropped_term_count": 66_650,
            "selected_drop_ticks": "33833242742",
            "selected_dropped_terms_sha256": (
                "3cb779382ecad31b539df1ab9e09d6f36918e6f59febd70838956fd5165eb42d"
            ),
            "retained_expansion_count": 622_592,
            "retained_expansion_sha256": (
                "8afaf7ce7e55c64f6c89e43929bb2df7d3c9229ccbf0193b171519c703829561"
            ),
            "minimum_retained_abs_upper_ticks": "3434232",
            "maximum_dropped_abs_upper_ticks": "3434132",
            "E_after_ticks": "1700535038508063",
        }
        for key, expected in q88_exact.items():
            with self.subTest(q88_field=key):
                self.assertEqual(q88[key], expected)
        self.assertEqual(
            int(q88["prefix_slack_before_selection_ticks"])
            - int(q88["selected_drop_ticks"]),
            160_394_779_325,
        )
        self.assertEqual(
            int(q88["minimum_retained_abs_upper_ticks"])
            - int(q88["maximum_dropped_abs_upper_ticks"]),
            100,
        )

        terminal = {
            "attempted_checkpoint_count": 88,
            "completed_checkpoint_count": 88,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "last_committed_cumulative_drop_ticks": "1700535038508063",
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
        }
        for key, expected in terminal.items():
            self.assertEqual(transcript[key], expected)

        nested = {
            "screen_execution_components": "components_sha256",
            "configuration_reference": "configuration_reference_sha256",
            "configuration_override": "configuration_override_sha256",
            "kernel_capability_override": "kernel_capability_override_sha256",
            "parent_horizon_override": "parent_horizon_override_sha256",
            "route_predecessor_reference": "route_predecessor_reference_sha256",
            "predecessor_handoff_validation": "handoff_sha256",
            "checkpoint_transform": "checkpoint_transform_sha256",
        }
        for value_key, expected_key in nested.items():
            expected = EXPECTED_CANONICAL[expected_key]
            self.assertEqual(digest(transcript[value_key]), expected)
            digest_key = (
                "predecessor_handoff_validation_sha256"
                if value_key == "predecessor_handoff_validation"
                else f"{value_key}_sha256"
            )
            self.assertEqual(transcript[digest_key], expected)

        components = transcript["screen_execution_components"]
        custody = transcript["source_custody"]
        self.assertEqual((len(components), len(custody)), (11, 10))
        self.assertEqual(digest(custody), EXPECTED_CANONICAL["custody_sha256"])
        self.assertEqual(
            components,
            SCREEN.execution_components(
                copy.deepcopy(list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS)),
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            ),
        )
        self.assertEqual(
            custody,
            SCREEN.expected_final_source_custody(
                EXPECTED_SCREEN_SHA256,
                SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            ),
        )
        component_paths = [item["relative_path"] for item in components]
        self.assertEqual(len(component_paths), len(set(component_paths)))
        self.assertNotIn(CANONICAL_NAME, component_paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, component_paths)
        for relative_path, expected_sha in custody.items():
            self.assertEqual(
                hashlib.sha256((HERE / relative_path).read_bytes()).hexdigest(),
                expected_sha,
            )

        handoff = transcript["predecessor_handoff_validation"]
        self.assertEqual(
            handoff["q88_terminal_branch"],
            "Q88_INDEX33_FIRST_FEASIBLE_SUCCESS",
        )
        self.assertTrue(handoff["q1_through_q87_common_records_exact"])
        self.assertTrue(handoff["q1_through_q87_first_33_candidate_rows_exact"])
        self.assertTrue(handoff["q1_through_q87_selected_history_exact"])
        self.assertTrue(handoff["q88_propagation_and_ranking_exact"])
        self.assertTrue(handoff["q88_first_33_candidate_rows_exact"])
        self.assertTrue(handoff["q88_appended_candidate_first_feasible"])
        self.assertFalse(handoff["K607993_execution_row_constructed"])
        self.assertFalse(handoff["K607993_drop_ticks_asserted"])
        self.assertFalse(handoff["q88_outcome_precommitted"])
        self.assertTrue(handoff["resource_exceptions_fail_closed_without_artifact"])

    def test_11_bounded_atomic_output_is_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "result.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"{}"))
            with self.assertRaisesRegex(RuntimeError, "byte cap"):
                SCREEN.write_atomic_bounded(
                    output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1)
                )
    @unittest.skipUnless(
        os.environ.get("FERMION_RUN_M622592_C34_Q88_REPLAY") == "1",
        "expensive deterministic q88 replay is opt-in",
    )
    def test_12_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        raw = canonical_bytes(result)
        canonical = (HERE / CANONICAL_NAME).read_bytes()
        self.assertEqual(raw, canonical)
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(), EXPECTED_CANONICAL["file_sha256"]
        )
        self.assertEqual(
            result["records_sha256"], EXPECTED_CANONICAL["records_sha256"]
        )
        self.assertEqual(
            result["selected_K_history_sha256"],
            EXPECTED_CANONICAL["history_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
