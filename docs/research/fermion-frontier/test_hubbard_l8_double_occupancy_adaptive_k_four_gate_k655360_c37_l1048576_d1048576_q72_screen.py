#!/usr/bin/env python3
"""Static, synthetic, and canonical tests for the D C37 q72 route."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import pathlib
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q72_screen.py"
)
CURRENT_SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_screen.py"
)
CURRENT_CANONICAL_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_transcript.json"
)
EXPECTED_SCREEN_SHA256 = (
    "1d3366d7c3fdc2a1e4a5c58198cc9be7e561af1f2ff8582e324ed5902c760183"
)
CANONICAL_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q72_transcript.json"
)
EXPECTED_CANONICAL = {
    "file_size_bytes": 751_550,
    "file_sha256": (
        "0517461f8695b21b578190cdd9a5da884f301d43c2f80be8093fbfc20cc006ae"
    ),
    "records_sha256": (
        "dae3378038fbe6b8514782b5f177adeab679b0255a4180a2b1c6dd11f5a6b06a"
    ),
    "history_sha256": (
        "a9f584aa28bc4cfff053d804e743f05c73a966b4e6ef53d43fd38bac2136245a"
    ),
    "q72_sha256": (
        "326b47e8c6f292f3938585676bcda2cf27a4e33fd815dec727b9c9357cb4578c"
    ),
    "q72_rows_sha256": (
        "5c95784865298c8aff971a5245497d8503ebcfd7edefeac13d3f901f47a12550"
    ),
    "all_candidate_rows_sha256": (
        "abcdbc805ed2c0c47bed32a432c7675f2033001f7ae9df387780764effad915a"
    ),
    "components_sha256": (
        "dd583360b9990b416f0e073c4a8ad9f3b289599132ffd66e2312f0a8c27db38b"
    ),
    "custody_sha256": (
        "8f2ec8e2305c27f3c48df1ab36293cefa4e47b96bd30e771ed1f7156aab1f325"
    ),
    "handoff_sha256": (
        "a177ea4b7653f040d5ef815f9c6edd4b58e851fdae8606476252bacee7131a9e"
    ),
}


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


def digest(value) -> str:
    return sha256(canonical_bytes(value))


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("d_k655360_c37_q72_screen_for_tests", SCREEN_NAME)


class DoubleOccupancyK655360C37Q72Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen_raw = (HERE / SCREEN_NAME).read_bytes()
        cls.current_raw = (HERE / CURRENT_CANONICAL_NAME).read_bytes()
        cls.current = json.loads(cls.current_raw)
        cls.canonical_raw = (HERE / CANONICAL_NAME).read_bytes()
        cls.canonical = json.loads(cls.canonical_raw)
        cls.predecessor, cls.route_reference = SCREEN.load_route_reference(
            HERE,
            replay_completed=True,
        )

    def setUp(self):
        self.maxDiff = None

    @staticmethod
    def synthetic_sha(label: str) -> str:
        return sha256(label.encode("ascii"))

    def append_candidate(
        self,
        record,
        checkpoint: int,
        *,
        force_drop: int | None = None,
    ):
        rows = record["candidate_records"]
        self.assertEqual(len(rows), 36)
        self.assertEqual(rows[-1]["configured_K"], SCREEN.K622592)
        pre_count = record["pretruncation_expansion_count"]
        effective = min(SCREEN.K655360, pre_count)
        old_drop = int(rows[-1]["drop_ticks"])
        if force_drop is not None:
            drop = force_drop
        elif pre_count <= SCREEN.K655360:
            drop = 0
        else:
            drop = max(0, old_drop - 1)
        E_after = int(record["E_before_ticks"]) + drop
        row = {
            "candidate_index": 36,
            "configured_K": SCREEN.K655360,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
            "drop_ticks": str(drop),
            "E_after_if_selected_ticks": str(E_after),
            "feasible_under_current_prefix_cap": (
                E_after <= int(record["budget_prefix_cap_ticks"])
            ),
        }
        rows.append(row)
        return row

    def make_raw_success(self):
        predecessor = copy.deepcopy(self.predecessor)
        raw = {
            key: copy.deepcopy(value)
            for key, value in predecessor.items()
            if key not in SCREEN.RELABELLED_ADDED_TOP_LEVEL_KEYS
        }
        records = copy.deepcopy(predecessor["records"])
        for checkpoint, record in enumerate(records[:71], 1):
            self.append_candidate(record, checkpoint)

        q72 = records[71]
        slack = int(q72["prefix_slack_before_selection_ticks"])
        appended = self.append_candidate(q72, 72, force_drop=slack)
        self.assertTrue(appended["feasible_under_current_prefix_cap"])
        for key in SCREEN.Q70_FAILURE_ONLY_KEYS:
            q72.pop(key)
        q72.update({
            "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
            "selected_candidate_index": 36,
            "selected_K": SCREEN.K655360,
            "selected_effective_retained_count": (
                appended["effective_retained_count"]
            ),
            "selected_dropped_term_count": appended["dropped_term_count"],
            "selected_drop_ticks": appended["drop_ticks"],
            "selected_dropped_terms_sha256": self.synthetic_sha(
                "q72-k655360-dropped"
            ),
            "retained_expansion_count": appended[
                "effective_retained_count"
            ],
            "retained_expansion_sha256": self.synthetic_sha(
                "q72-k655360-retained"
            ),
            "minimum_retained_abs_upper_ticks": "1",
            "maximum_dropped_abs_upper_ticks": "1",
            "E_after_ticks": appended["E_after_if_selected_ticks"],
        })
        counterfactual = q72["removed_491520_counterfactual"]
        counterfactual.update({
            "actual_selected_K": SCREEN.K655360,
            "would_precede_selected": False,
            "would_be_selected_if_inserted": False,
        })
        history = copy.deepcopy(predecessor["selected_K_history"])
        history.append(SCREEN.K655360)

        raw_transform = predecessor["checkpoint_transform"][
            "physical_four_gate_control_flow_parent_transform"
        ]
        configuration_reference = {
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
            "policy_caps_base_sha256": (
                SCREEN.EXPECTED_V6_POLICY_CAPS_SHA256
            ),
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
        }
        raw.update({
            "transcript_fingerprint": (
                "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
            ),
            "screen_source_sha256": (
                SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256
            ),
            "control_flow_owned_by_screen": True,
            "screen_execution_components": list(
                SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS
            ),
            "configuration_reference": configuration_reference,
            "checkpoint_transform": copy.deepcopy(raw_transform),
            "source_custody": copy.deepcopy(
                SCREEN.EXPECTED_PARENT_SOURCE_CUSTODY
            ),
            "candidate_K_values": list(SCREEN.D_CANDIDATES),
            "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
            "proposed_policy_caps": {
                **SCREEN.POLICY_CAPS_BASE,
                "max_candidate_count": 37,
            },
            "kernel_capability_limits": copy.deepcopy(
                SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS
            ),
            "attempted_checkpoint_count": 72,
            "completed_checkpoint_count": 72,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "records": records,
            "selected_K_history": history,
            "last_committed_cumulative_drop_ticks": q72["E_after_ticks"],
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
            "observed_peak_single_expansion_terms": q72[
                "peak_live_terms_cumulative"
            ],
            "observed_term_gate_visits_including_terminal_attempt": q72[
                "term_gate_visits_cumulative"
            ],
            "observed_maximum_expansion_coefficient_tick_bits": q72[
                "maximum_expansion_coefficient_tick_bits"
            ],
            "observed_maximum_product_bits": q72[
                "maximum_product_bits"
            ],
            "observed_rounding_cumulative_scaled_ticks_squared": q72[
                "rounding_cumulative_scaled_ticks_squared"
            ],
        })
        for value_key, digest_key in (
            ("screen_execution_components", "screen_execution_components_sha256"),
            ("configuration_reference", "configuration_reference_sha256"),
            ("checkpoint_transform", "checkpoint_transform_sha256"),
            ("records", "records_sha256"),
            ("selected_K_history", "selected_K_history_sha256"),
        ):
            raw[digest_key] = digest(raw[value_key])
        self.assertEqual(
            frozenset(raw),
            SCREEN.EXPECTED_PARENT_RESULT_KEYS,
        )
        return raw

    def test_01_static_ladder_caps_and_source_pin(self):
        self.assertEqual(sha256(self.screen_raw), EXPECTED_SCREEN_SHA256)
        self.assertLessEqual(len(self.screen_raw), SCREEN.MAX_SELF_SOURCE_BYTES)
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.PREDECESSOR_D_CANDIDATES), 36)
        self.assertEqual(len(SCREEN.D_CANDIDATES), 37)
        self.assertEqual(
            SCREEN.D_CANDIDATES,
            SCREEN.PREDECESSOR_D_CANDIDATES + (SCREEN.K655360,),
        )
        self.assertNotIn(SCREEN.K638976, SCREEN.D_CANDIDATES)
        self.assertEqual(
            digest(list(SCREEN.D_CANDIDATES)),
            "66076fbdd8558ff2da161fae605ad594392cff569c3d523abc8524d666ae3dd8",
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_candidate_K"],
            SCREEN.K655360,
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_output_terms_if_successful"],
            SCREEN.K655360,
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_single_expansion_terms"],
            1_048_576,
        )
        self.assertEqual(
            SCREEN.POLICY_CAPS_BASE["max_digest_terms"],
            1_048_576,
        )

    def test_02_direct_root_and_wrapper_authority(self):
        parent = SCREEN.load_control_flow_parent(HERE)
        configuration, baseline_d = SCREEN.load_configured_v6_baseline(HERE)
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertIsInstance(parent, types.ModuleType)
        self.assertIs(parent.run_four_gate.__globals__, parent.__dict__)
        self.assertEqual(tuple(baseline_d), SCREEN.V6_D_CANDIDATES)
        self.assertEqual(
            tuple(configuration.MODE_CONFIG[SCREEN.MODE]["candidates"]),
            SCREEN.D_CANDIDATES,
        )
        self.assertEqual(
            configuration.POLICY_CAPS_BASE,
            SCREEN.POLICY_CAPS_BASE,
        )
        self.assertEqual(
            wrapper_sha,
            "2acf8f8329376ab06ad4c079af633d23bcc6a32fa20af654e5c3dbbb32093d54",
        )
        self.assertEqual(
            wrapper.RESOURCE_LIMITS,
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )
        self.assertEqual(
            manifest["route_predecessor_resource_limits"],
            SCREEN.EXPECTED_ROUTE_KERNEL_LIMITS,
        )
        self.assertFalse(
            manifest["route_predecessor_reference"]["execution_source_layer"]
        )

    def test_03_route_reference_is_guarded_and_post_replay_only(self):
        original = SCREEN.bounded_bytes
        reads = []

        def forbidden_read(*args, **kwargs):
            reads.append((args, kwargs))
            raise AssertionError("pre-replay reference read")

        SCREEN.bounded_bytes = forbidden_read
        try:
            with self.assertRaisesRegex(RuntimeError, "before replay"):
                SCREEN.load_route_reference(HERE, replay_completed=False)
        finally:
            SCREEN.bounded_bytes = original
        self.assertEqual(reads, [])
        reference = self.route_reference
        self.assertFalse(reference["screen"]["compiled"])
        self.assertFalse(reference["screen"]["executed"])
        self.assertFalse(reference["screen"]["private_entrypoint_called"])
        self.assertTrue(
            reference["screen"]["loaded_after_replay_as_exact_reference"]
        )
        canonical = reference["canonical_transcript"]
        self.assertFalse(canonical["state_resume_input"])
        self.assertFalse(canonical["propagation_input"])
        self.assertFalse(canonical["checkpoint_state_loaded"])
        self.assertTrue(canonical["used_only_after_replay_for_result_comparison"])

    def test_04_precanonical_anchors_and_excluded_k638976_evidence(self):
        self.assertEqual(self.current_raw, canonical_bytes(self.current))
        self.assertEqual(len(self.current_raw), 739_189)
        self.assertEqual(
            sha256(self.current_raw),
            "4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd",
        )
        q72 = self.current["records"][71]
        self.assertEqual(q72["minimum_effective_K_to_meet_prefix"], 642_206)
        self.assertEqual(q72["pretruncation_expansion_count"], 799_279)
        self.assertEqual(q72["ranked_suffix_sha256"], (
            "9e9bbc7b188fe28962229358a07b68c5e38c0f9f15921e3505f4e3a27a1fe7a4"
        ))
        self.assertEqual(digest(q72["candidate_records"]), (
            "8ec5b4b4ab3bc981f81cefb8f8ba4e8b86394918242f21cddc18861db369ddd9"
        ))
        evidence = self.route_reference[
            "excluded_candidate_threshold_evidence"
        ]
        self.assertEqual(evidence["configured_K"], SCREEN.K638976)
        self.assertEqual(evidence["shortfall"], 3_230)
        self.assertFalse(evidence["execution_candidate"])
        self.assertFalse(evidence["candidate_row_constructed"])
        self.assertFalse(evidence["exact_drop_ticks_asserted"])
        self.assertNotIn("drop_ticks", evidence)
        delta = self.route_reference["incremental_semantic_delta"]
        self.assertEqual(delta["candidate_ladder_added"], [SCREEN.K655360])
        self.assertEqual(delta["candidate_ladder_removed"], [])

    def test_05_execution_failure_prevents_route_loading(self):
        sentinel = RuntimeError("unknown resource failure")
        calls = []
        saved = {
            name: getattr(SCREEN, name)
            for name in (
                "validate_local_configuration",
                "load_control_flow_parent",
                "load_configured_v6_baseline",
                "load_kernel_wrapper",
                "configure_parent_execution",
                "execute_parent_fail_closed",
                "load_route_reference",
            )
        }
        old_self = SCREEN._VERIFIED_SELF_SOURCE_BYTES
        SCREEN._VERIFIED_SELF_SOURCE_BYTES = b"verified-test-bytes"
        SCREEN.validate_local_configuration = lambda: calls.append("validate")
        SCREEN.load_control_flow_parent = lambda _repo: object()
        SCREEN.load_configured_v6_baseline = (
            lambda _repo: (object(), SCREEN.V6_D_CANDIDATES)
        )
        SCREEN.load_kernel_wrapper = lambda _repo: (
            object(),
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            {},
        )
        SCREEN.configure_parent_execution = (
            lambda *_args: {"synthetic": True}
        )

        def fail_replay(*_args):
            calls.append("replay")
            raise sentinel

        def forbidden_route(*_args, **_kwargs):
            calls.append("route")
            raise AssertionError("route loaded before replay returned")

        SCREEN.execute_parent_fail_closed = fail_replay
        SCREEN.load_route_reference = forbidden_route
        try:
            with self.assertRaises(RuntimeError) as caught:
                SCREEN._run_verified(HERE)
            self.assertIs(caught.exception, sentinel)
        finally:
            for name, value in saved.items():
                setattr(SCREEN, name, value)
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = old_self
        self.assertEqual(calls, ["validate", "replay"])

    def test_06_known_and_unknown_resource_errors_propagate_unchanged(self):
        class Parent:
            def __init__(self, error):
                self.error = error

            def _run_verified(self, _repo, _mode):
                raise self.error

        for error in (
            RuntimeError("design policy live-term cap exceeded"),
            RuntimeError("unrecognized resource ceiling"),
            ValueError("schema-shaped resource failure"),
        ):
            with self.subTest(error=repr(error)):
                with self.assertRaises(type(error)) as caught:
                    SCREEN.execute_parent_fail_closed(Parent(error), HERE)
                self.assertIs(caught.exception, error)

    def test_07_synthetic_first_feasible_success_is_accepted(self):
        raw = self.make_raw_success()
        handoff = SCREEN.validate_replay_handoff(
            raw,
            self.predecessor,
        )
        self.assertEqual(
            handoff["q72_terminal_branch"],
            "Q72_INDEX36_FIRST_FEASIBLE_SUCCESS",
        )
        self.assertTrue(handoff["q1_through_q71_common_records_exact"])
        self.assertTrue(handoff["q72_propagation_and_ranking_exact"])
        self.assertTrue(handoff["q72_appended_candidate_first_feasible"])
        self.assertFalse(handoff["K638976_execution_row_constructed"])

    def test_08_q1_q71_common_or_old_row_tampering_is_rejected(self):
        mutations = (
            lambda raw: raw["records"][0].__setitem__(
                "pretruncation_expansion_count",
                raw["records"][0]["pretruncation_expansion_count"] + 1,
            ),
            lambda raw: raw["records"][70]["candidate_records"][35].__setitem__(
                "drop_ticks",
                str(int(
                    raw["records"][70]["candidate_records"][35]["drop_ticks"]
                ) + 1),
            ),
            lambda raw: raw["selected_K_history"].__setitem__(70, 606_208),
        )
        for mutation in mutations:
            raw = self.make_raw_success()
            mutation(raw)
            raw["records_sha256"] = digest(raw["records"])
            raw["selected_K_history_sha256"] = digest(
                raw["selected_K_history"]
            )
            with self.subTest(mutation=mutation):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(raw, self.predecessor)

    def test_09_q72_propagation_ranking_or_old_rows_are_exact(self):
        mutations = (
            lambda raw: raw["records"][71].__setitem__(
                "pretruncation_expansion_count",
                raw["records"][71]["pretruncation_expansion_count"] + 1,
            ),
            lambda raw: raw["records"][71].__setitem__(
                "ranked_suffix_sha256",
                self.synthetic_sha("tampered-ranking"),
            ),
            lambda raw: raw["records"][71]["candidate_records"][35].__setitem__(
                "drop_ticks",
                "0",
            ),
        )
        for mutation in mutations:
            raw = self.make_raw_success()
            mutation(raw)
            raw["records_sha256"] = digest(raw["records"])
            with self.subTest(mutation=mutation):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(raw, self.predecessor)

    def test_10_failure_branch_and_non_first_feasible_claims_are_rejected(self):
        raw = self.make_raw_success()
        q72 = raw["records"][71]
        appended = q72["candidate_records"][36]
        q72["status"] = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        q72["selected_candidate_index"] = None
        q72["selected_K"] = None
        for key in SCREEN.Q70_SUCCESS_ONLY_KEYS:
            q72.pop(key)
        q72.update({
            "minimum_effective_K_to_meet_prefix": 655_361,
            "required_K_excess_over_policy_maximum": 1,
            "maximum_candidate_drop_excess_over_slack_ticks": "1",
        })
        appended["feasible_under_current_prefix_cap"] = False
        raw["completed_checkpoint_count"] = 71
        raw["horizon_reached_with_committed_checkpoint"] = False
        raw["failure_checkpoint_included"] = True
        raw["screen_terminal_condition"] = (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        raw["selected_K_history"].pop()
        raw["failure_record_sha256"] = digest(q72)
        raw["records_sha256"] = digest(raw["records"])
        raw["selected_K_history_sha256"] = digest(
            raw["selected_K_history"]
        )
        with self.assertRaises(RuntimeError):
            SCREEN.validate_replay_handoff(raw, self.predecessor)

        for field, value in (
            ("candidate_index", 35),
            ("configured_K", SCREEN.K638976),
            ("feasible_under_current_prefix_cap", False),
        ):
            raw = self.make_raw_success()
            raw["records"][71]["candidate_records"][36][field] = value
            raw["records_sha256"] = digest(raw["records"])
            with self.subTest(field=field):
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(raw, self.predecessor)

    def test_11_resource_result_is_rejected_before_artifact(self):
        raw = self.make_raw_success()
        raw["resource_policy_abort"] = {
            "status": "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
        }
        raw["resource_policy_abort_sha256"] = digest(
            raw["resource_policy_abort"]
        )
        with self.assertRaisesRegex(RuntimeError, "fail closed"):
            SCREEN.validate_replay_handoff(raw, self.predecessor)

    def test_12_synthetic_relabel_has_closed_authority(self):
        raw = self.make_raw_success()
        parent = SCREEN.load_control_flow_parent(HERE)
        configuration, baseline_d = SCREEN.load_configured_v6_baseline(HERE)
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        horizon = SCREEN.configure_parent_execution(
            parent,
            configuration,
            wrapper,
        )
        old_self = SCREEN._VERIFIED_SELF_SOURCE_BYTES
        SCREEN._VERIFIED_SELF_SOURCE_BYTES = self.screen_raw
        try:
            result = SCREEN.validate_and_relabel(
                raw,
                self.predecessor,
                self.route_reference,
                baseline_d,
                wrapper_sha,
                manifest,
                horizon,
            )
        finally:
            SCREEN._VERIFIED_SELF_SOURCE_BYTES = old_self
        self.assertEqual(
            frozenset(result),
            SCREEN.EXPECTED_RELABELLED_RESULT_KEYS,
        )
        self.assertEqual(result["candidate_K_values"][-1], SCREEN.K655360)
        paths = {
            item["relative_path"]
            for item in result["screen_execution_components"]
        }
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, paths)
        custody = result["source_custody"]
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, custody)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME, custody)
        delta = result["configuration_override"][
            "incremental_route_override_from_k622592_c36_policy_q72"
        ]
        self.assertEqual(delta["candidate_ladder_added"], [SCREEN.K655360])
        self.assertEqual(delta["candidate_ladder_removed"], [])
        self.assertEqual(
            result["predecessor_handoff_validation"][
                "fresh_replay_checkpoint_range"
            ],
            [1, 72],
        )

    def test_13_static_call_graph_has_no_nested_route_execution(self):
        route_tree = ast.parse(inspect.getsource(SCREEN.load_route_reference))
        route_calls = {
            node.func.id
            for node in ast.walk(route_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertNotIn("compile", route_calls)
        self.assertNotIn("compile_isolated", route_calls)
        self.assertNotIn("exec", route_calls)
        run_source = inspect.getsource(SCREEN._run_verified)
        self.assertLess(
            run_source.index("execute_parent_fail_closed"),
            run_source.index("load_route_reference"),
        )
        self.assertNotIn("CODE_PROVIDER", self.screen_raw.decode("utf-8"))
        self.assertNotIn(
            "ROUTE_PREDECESSOR_SCREEN_NAME)._run_verified",
            self.screen_raw.decode("utf-8"),
        )

    def test_14_canonical_exact_bytes_and_handoff_are_closed(self):
        raw = self.canonical_raw
        canonical = self.canonical
        self.assertEqual(len(raw), EXPECTED_CANONICAL["file_size_bytes"])
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertEqual(raw, canonical_bytes(canonical))
        self.assertEqual(
            frozenset(canonical),
            SCREEN.EXPECTED_RELABELLED_RESULT_KEYS,
        )
        self.assertEqual(len(canonical), 96)

        expected_top = {
            "transcript_fingerprint": (
                "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
                "k655360_c37_l1048576_d1048576_q72_screen_v1"
            ),
            "screen_source_sha256": EXPECTED_SCREEN_SHA256,
            "screen_horizon_checkpoint_count": 72,
            "attempted_checkpoint_count": 72,
            "completed_checkpoint_count": 72,
            "horizon_checkpoint_attempted": True,
            "horizon_reached_with_committed_checkpoint": True,
            "failure_checkpoint_included": False,
            "failure_record_sha256": None,
            "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
            "last_committed_cumulative_drop_ticks": "2289046235933480",
            "resource_policy_abort": None,
            "resource_policy_abort_sha256": None,
        }
        for field, value in expected_top.items():
            self.assertEqual(canonical[field], value, field)
        self.assertEqual(
            canonical["candidate_K_values"],
            list(SCREEN.D_CANDIDATES),
        )
        self.assertEqual(
            canonical["proposed_policy_caps"],
            {**SCREEN.POLICY_CAPS_BASE, "max_candidate_count": 37},
        )
        self.assertEqual(
            canonical["kernel_capability_limits"],
            SCREEN.EXPECTED_WRAPPED_KERNEL_LIMITS,
        )

        records = canonical["records"]
        history = canonical["selected_K_history"]
        self.assertEqual(len(records), 72)
        self.assertEqual(len(history), 72)
        self.assertEqual(canonical["records_sha256"], (
            EXPECTED_CANONICAL["records_sha256"]
        ))
        self.assertEqual(digest(records), EXPECTED_CANONICAL["records_sha256"])
        self.assertEqual(canonical["selected_K_history_sha256"], (
            EXPECTED_CANONICAL["history_sha256"]
        ))
        self.assertEqual(digest(history), EXPECTED_CANONICAL["history_sha256"])
        self.assertEqual(history[:71], self.predecessor["selected_K_history"])
        self.assertEqual(history[71], SCREEN.K655360)

        all_rows = []
        for index, (record, old_record) in enumerate(zip(
            records[:71],
            self.predecessor["records"][:71],
        ), 1):
            with self.subTest(checkpoint=index):
                old_common = {
                    key: value for key, value in old_record.items()
                    if key != "candidate_records"
                }
                new_common = {
                    key: value for key, value in record.items()
                    if key != "candidate_records"
                }
                self.assertEqual(new_common, old_common)
                rows = record["candidate_records"]
                self.assertEqual(len(rows), 37)
                self.assertEqual(rows[:36], old_record["candidate_records"])
                appended = rows[36]
                self.assertEqual(appended["candidate_index"], 36)
                self.assertEqual(appended["configured_K"], SCREEN.K655360)
                self.assertEqual(
                    appended["effective_retained_count"],
                    min(SCREEN.K655360, record["pretruncation_expansion_count"]),
                )
                self.assertEqual(
                    appended["dropped_term_count"],
                    record["pretruncation_expansion_count"]
                    - appended["effective_retained_count"],
                )
                all_rows.extend(rows)

        q72 = records[71]
        old_q72 = self.predecessor["records"][71]
        q72_excluded = {
            "candidate_records",
            "removed_491520_counterfactual",
            "status",
            "selected_candidate_index",
            "selected_K",
            *SCREEN.Q70_FAILURE_ONLY_KEYS,
            *SCREEN.Q70_SUCCESS_ONLY_KEYS,
        }
        old_q72_shared = {
            key: value for key, value in old_q72.items()
            if key not in q72_excluded
        }
        self.assertEqual(
            {key: q72[key] for key in old_q72_shared},
            old_q72_shared,
        )
        rows = q72["candidate_records"]
        all_rows.extend(rows)
        self.assertEqual(len(rows), 37)
        self.assertEqual(rows[:36], old_q72["candidate_records"])
        self.assertEqual(sum(
            len(record["candidate_records"]) for record in records
        ), 2_664)
        self.assertEqual(
            digest(all_rows),
            EXPECTED_CANONICAL["all_candidate_rows_sha256"],
        )
        self.assertEqual(digest(q72), EXPECTED_CANONICAL["q72_sha256"])
        self.assertEqual(digest(rows), EXPECTED_CANONICAL["q72_rows_sha256"])

        selected = rows[36]
        self.assertTrue(all(
            row["feasible_under_current_prefix_cap"] is False
            for row in rows[:36]
        ))
        self.assertTrue(selected["feasible_under_current_prefix_cap"])
        q72_expected = {
            "pretruncation_expansion_count": 799_279,
            "selected_candidate_index": 36,
            "selected_K": SCREEN.K655360,
            "selected_effective_retained_count": SCREEN.K655360,
            "selected_dropped_term_count": 143_919,
            "selected_drop_ticks": "78846106758",
            "E_after_ticks": "2289046235933480",
            "retained_expansion_sha256": (
                "fae098c2e1b746413885371ec4b6c1cfce32f8948c6421a4118aee1707c43cc1"
            ),
            "peak_live_terms_cumulative": 799_279,
            "term_gate_visits_cumulative": 92_869_433,
        }
        for field, value in q72_expected.items():
            self.assertEqual(q72[field], value, field)
        self.assertEqual(selected["candidate_index"], 36)
        self.assertEqual(selected["configured_K"], SCREEN.K655360)
        self.assertEqual(selected["effective_retained_count"], SCREEN.K655360)
        self.assertEqual(selected["dropped_term_count"], 143_919)
        self.assertEqual(selected["drop_ticks"], "78846106758")
        self.assertEqual(
            int(q72["budget_prefix_cap_ticks"])
            - int(q72["E_after_ticks"]),
            43_761_880_334,
        )
        self.assertEqual(
            int(q72["prefix_slack_before_selection_ticks"])
            - int(q72["selected_drop_ticks"]),
            43_761_880_334,
        )

        evidence = {
            "configured_K": SCREEN.K638976,
            "minimum_effective_K_to_meet_prefix": 642_206,
            "shortfall": 3_230,
            "evidence_scope": (
                "fixed_four_gate_q72_predecessor_state_prefix_only"
            ),
            "execution_candidate": False,
            "candidate_row_constructed": False,
            "exact_drop_ticks_asserted": False,
        }
        self.assertNotIn(SCREEN.K638976, canonical["candidate_K_values"])
        self.assertFalse(any(
            row["configured_K"] == SCREEN.K638976 for row in all_rows
        ))
        self.assertNotIn("drop_ticks", evidence)
        self.assertEqual(
            canonical["route_predecessor_reference"]
            ["excluded_candidate_threshold_evidence"],
            evidence,
        )
        self.assertEqual(
            canonical["configuration_override"]
            ["excluded_candidate_threshold_evidence"],
            evidence,
        )

        handoff = canonical["predecessor_handoff_validation"]
        self.assertEqual(
            canonical["predecessor_handoff_validation_sha256"],
            EXPECTED_CANONICAL["handoff_sha256"],
        )
        self.assertEqual(digest(handoff), EXPECTED_CANONICAL["handoff_sha256"])
        self.assertEqual(handoff["fresh_replay_checkpoint_range"], [1, 72])
        self.assertEqual(
            handoff["q72_terminal_branch"],
            "Q72_INDEX36_FIRST_FEASIBLE_SUCCESS",
        )
        for field in (
            "q1_through_q71_common_records_exact",
            "q1_through_q71_first_36_candidate_rows_exact",
            "q1_through_q71_selected_history_exact",
            "q72_propagation_and_ranking_exact",
            "q72_first_36_candidate_rows_exact",
            "q72_appended_candidate_first_feasible",
            "resource_exceptions_fail_closed_without_artifact",
        ):
            self.assertTrue(handoff[field], field)
        self.assertEqual(handoff["excluded_K638976_threshold_evidence"], evidence)
        self.assertFalse(handoff["K638976_execution_row_constructed"])
        self.assertFalse(handoff["K638976_drop_ticks_asserted"])
        self.assertFalse(handoff["route_screen_compiled_or_executed"])
        self.assertFalse(handoff["route_screen_private_entrypoint_called"])
        self.assertFalse(
            handoff["route_canonical_used_as_state_or_resume_input"]
        )

        components = canonical["screen_execution_components"]
        expected_components = SCREEN.execution_components(
            list(SCREEN.EXPECTED_PARENT_EXECUTION_COMPONENTS),
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
            digest(components),
            EXPECTED_CANONICAL["components_sha256"],
        )
        custody = canonical["source_custody"]
        expected_custody = SCREEN.expected_final_source_custody(
            EXPECTED_SCREEN_SHA256,
            SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
        )
        self.assertEqual(custody, expected_custody)
        self.assertEqual(len(custody), 10)
        self.assertEqual(
            digest(custody),
            EXPECTED_CANONICAL["custody_sha256"],
        )
        for component in components:
            self.assertEqual(
                sha256((HERE / component["relative_path"]).read_bytes()),
                component["sha256"],
                component["relative_path"],
            )
        for relative_path, expected_sha in custody.items():
            self.assertEqual(
                sha256((HERE / relative_path).read_bytes()),
                expected_sha,
                relative_path,
            )


if __name__ == "__main__":
    unittest.main()
