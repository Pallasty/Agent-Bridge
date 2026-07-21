#!/usr/bin/env python3
"""Static and synthetic tests for the M K557056/C31 q82 screen."""

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
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k557056_c31_q82_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "ba1c221b57fa59655612ad7209b38c83337f6f21b794132f7a9e1600b8d60fed"
)
EXPECTED_CANONICAL = {
    "file_sha256": "1d6cbcddac8a8c596746f24b8c8498f24874e86db5235532d7d269220043cdd4",
    "records_sha256": "cb017a1202e89d5db762296b9b61ad78de132b2a0a589f8d3b21f096609a9aa9",
    "history_sha256": "8c6902944bc0fc1c1c533a4e3e7ca6f65c17f43fef3c6a94f633616b38123e40",
    "components_sha256": "ff6ab21b98eb2f17b7fd72d68450dc4a4dcb68480a7dd34f6120d25eb7f19e40",
    "configuration_reference_sha256": "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138",
    "configuration_override_sha256": "ec25a4c736f761a4b27c667b87c2c50c86ab890817c9a5f6839ffe27d8d65c58",
    "kernel_override_sha256": "bf534a1319b0b7f9d10b37273ce75756d53725e539eb3a727c689592d2300fb3",
    "horizon_override_sha256": "79ed2b8516a4209f7847eaefd581305f31a398424c2481359e024cdd3f52fbc4",
    "route_reference_sha256": "96c463ce660c46a7297aa3a014fcf693ae444760699a710eec665386c4bfc98c",
    "handoff_sha256": "b762d4af4c419b270a0d2b1f7cf12e4d28c79a13bcfb7ba60336528e3d14c3c1",
    "transform_sha256": "7c606a43b6e00dda67555147f29b678846190804af615165f8a55831fe8cdf8e",
    "last_E": "1700039048594959",
    "peak": 643_624,
    "visits": 91_592_879,
    "coefficient_bits": 57,
    "product_bits": 121,
    "rounding": "126557927322403190032220422",
}


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("m_k557056_c31_q82_screen", SCREEN_NAME)


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


def load_predecessor():
    return json.loads((HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes())


def appended_row(record, *, q81=False):
    effective = min(SCREEN.K557056, record["pretruncation_expansion_count"])
    drop = 1 if q81 else 0
    return {
        "candidate_index": 30,
        "configured_K": SCREEN.K557056,
        "effective_retained_count": effective,
        "dropped_term_count": record["pretruncation_expansion_count"] - effective,
        "drop_ticks": str(drop),
        "E_after_if_selected_ticks": str(int(record["E_before_ticks"]) + drop),
        "feasible_under_current_prefix_cap": True,
    }


def synthetic_parent_result():
    predecessor = load_predecessor()
    records = copy.deepcopy(predecessor["records"])
    for record in records[:80]:
        record["candidate_records"].append(appended_row(record))

    q81 = records[80]
    row = appended_row(q81, q81=True)
    q81["candidate_records"].append(row)
    for key in (
        "maximum_candidate_drop_excess_over_slack_ticks",
        "minimum_effective_K_to_meet_prefix",
        "required_K_excess_over_policy_maximum",
    ):
        q81.pop(key, None)
    q81.update({
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 30,
        "selected_K": SCREEN.K557056,
        "selected_effective_retained_count": SCREEN.K557056,
        "selected_dropped_term_count": 40_198,
        "selected_drop_ticks": row["drop_ticks"],
        "selected_dropped_terms_sha256": "1" * 64,
        "maximum_dropped_abs_upper_ticks": "1",
        "minimum_retained_abs_upper_ticks": "1",
        "retained_expansion_count": SCREEN.K557056,
        "retained_expansion_sha256": "2" * 64,
        "E_after_ticks": row["E_after_if_selected_ticks"],
    })

    q82 = copy.deepcopy(predecessor["records"][80])
    q82["checkpoint_index_zero_based"] = 81
    q82["checkpoint_number_one_based"] = 82
    q82["E_before_ticks"] = q81["E_after_ticks"]
    q82["input_expansion_count"] = SCREEN.K557056
    q82["input_expansion_sha256"] = q81["retained_expansion_sha256"]
    q82["candidate_records"].append({
        **appended_row(q82),
        "feasible_under_current_prefix_cap": False,
    })
    records.append(q82)
    history = copy.deepcopy(predecessor["selected_K_history"]) + [SCREEN.K557056]
    components = [
        {
            "relative_path": SCREEN.CONTROL_FLOW_PARENT_NAME,
            "role": "four_gate_screen",
            "sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        },
        {
            "relative_path": SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            "role": "v6_configuration",
            "sha256": SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        },
        {
            "relative_path": SCREEN.V2_ARITHMETIC_NAME,
            "role": "v2_arithmetic",
            "sha256": SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
        },
    ]
    configuration = {"synthetic_parent_configuration": True}
    transform = {"synthetic_parent_transform": True}
    return {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "screen_source_sha256": SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "v2_run_entrypoint_called": False,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "screen_horizon_checkpoint_count": 82,
        "candidate_K_values": list(SCREEN.M_CANDIDATES),
        "candidate_K_values_sha256": SCREEN.EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **SCREEN.POLICY_CAPS_BASE,
            "max_candidate_count": 31,
        },
        "kernel_capability_limits": SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        "records": records,
        "records_sha256": digest(records),
        "selected_K_history": history,
        "selected_K_history_sha256": digest(history),
        "attempted_checkpoint_count": 82,
        "completed_checkpoint_count": 81,
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "screen_execution_components": components,
        "screen_execution_components_sha256": digest(components),
        "configuration_reference": configuration,
        "configuration_reference_sha256": digest(configuration),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": digest(transform),
        "source_custody": {},
    }


class MagnetizationK557056C31Q82ScreenTests(unittest.TestCase):
    def test_01_exact_source_wrapper_and_route_pins(self):
        exact = {
            SCREEN.CONTROL_FLOW_PARENT_NAME: SCREEN.EXPECTED_CONTROL_FLOW_PARENT_SHA256,
            SCREEN.V6_BASELINE_CONFIGURATION_NAME: (
                SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
            ),
            SCREEN.V2_ARITHMETIC_NAME: SCREEN.EXPECTED_V2_ARITHMETIC_SHA256,
            SCREEN.KERNEL_WRAPPER_NAME: SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256,
            SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME: (
                SCREEN.EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256
            ),
        }
        for filename, expected in exact.items():
            self.assertEqual(
                hashlib.sha256((HERE / filename).read_bytes()).hexdigest(), expected
            )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN.ROUTE_PREDECESSOR_TRANSCRIPT_NAME).read_bytes()).hexdigest(),
            SCREEN.EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((HERE / SCREEN_NAME).read_bytes()).hexdigest(),
            EXPECTED_SCREEN_SHA256,
        )
        fresh = SCREEN.fresh_self_module()
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, (HERE / SCREEN_NAME).read_bytes())
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertEqual(wrapper_sha, SCREEN.EXPECTED_KERNEL_WRAPPER_SHA256)
        self.assertEqual(
            digest(manifest), SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256
        )
        self.assertEqual(
            wrapper.capability_manifest_sha256(),
            SCREEN.EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256,
        )

    def test_02_candidate_config_caps_and_horizon_are_exact(self):
        SCREEN.validate_local_configuration()
        self.assertEqual(len(SCREEN.V6_M_CANDIDATES), 29)
        self.assertEqual(len(SCREEN.PREDECESSOR_M_CANDIDATES), 30)
        self.assertEqual(len(SCREEN.M_CANDIDATES), 31)
        self.assertEqual(
            SCREEN.M_CANDIDATES, SCREEN.PREDECESSOR_M_CANDIDATES + (557_056,)
        )
        self.assertEqual(digest(list(SCREEN.M_CANDIDATES)), SCREEN.EXPECTED_CANDIDATE_SHA256)
        changed = SCREEN.changed_mapping_keys(
            SCREEN.EXPECTED_PREDECESSOR_POLICY_CAPS, SCREEN.POLICY_CAPS_BASE
        )
        self.assertEqual(changed, {"max_candidate_K", "max_output_terms_if_successful"})
        self.assertEqual(SCREEN.POLICY_CAPS_BASE["max_candidate_K"], 557_056)
        configuration, baseline_m = SCREEN.load_configured_v6_baseline(HERE)
        self.assertEqual(tuple(baseline_m), SCREEN.V6_M_CANDIDATES)
        self.assertEqual(tuple(configuration.MODE_CONFIG[SCREEN.MODE]["candidates"]), SCREEN.M_CANDIDATES)
        baseline_configuration, _ = SCREEN.load_pinned_module(
            HERE,
            SCREEN.V6_BASELINE_CONFIGURATION_NAME,
            SCREEN.EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            "pristine_v6_for_m_screen_test",
        )
        self.assertEqual(
            configuration.MODE_CONFIG["double_occupancy"],
            baseline_configuration.MODE_CONFIG["double_occupancy"],
        )
        parent = SCREEN.load_control_flow_parent(HERE)
        before = copy.deepcopy(parent.MODE_CONFIG)
        wrapper, _sha, _manifest = SCREEN.load_kernel_wrapper(HERE)
        horizon = SCREEN.configure_parent_execution(parent, configuration, wrapper)
        self.assertEqual(
            horizon["changed_fields"],
            ["MODE_CONFIG.magnetization.horizon_checkpoint_count"],
        )
        self.assertEqual(before[SCREEN.MODE]["horizon_checkpoint_count"], 80)
        self.assertEqual(parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 82)
        self.assertEqual(parent.MODE_CONFIG["double_occupancy"], before["double_occupancy"])

    def test_03_wrapper_capability_and_nonexecution_lineage(self):
        wrapper, wrapper_sha, manifest = SCREEN.load_kernel_wrapper(HERE)
        self.assertEqual(wrapper.RESOURCE_LIMITS, SCREEN.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS)
        self.assertEqual(wrapper.RESOURCE_LIMITS["max_candidate_count"], 32)
        self.assertEqual(wrapper.RESOURCE_LIMITS["max_retained_K"], 557_056)
        self.assertEqual(
            [item["relative_path"] for item in manifest["source_layers"]],
            [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME],
        )
        route = manifest["route_predecessor_reference"]
        self.assertEqual(route["source_sha256"], SCREEN.EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256)
        self.assertFalse(route["compiled"])
        self.assertFalse(route["executed"])
        self.assertFalse(route["execution_source_layer"])
        capability = SCREEN.kernel_capability_override(wrapper_sha, manifest)
        self.assertEqual(capability["execution_source_layers"], [SCREEN.KERNEL_WRAPPER_NAME, SCREEN.V2_ARITHMETIC_NAME])
        self.assertFalse(capability["route_predecessor_is_execution_source"])

    def test_04_private_parent_path_and_exception_identity(self):
        fresh = SCREEN.fresh_self_module()
        sentinel = {"private": True}
        observed = {}

        class Parent:
            def run(self, *_args):
                self.fail("parent public entrypoint used")

            def _run_verified(self, repo, mode):
                observed["repo"] = repo
                observed["mode"] = mode
                return sentinel

        parent = Parent()
        fresh.load_control_flow_parent = lambda _repo: parent
        fresh.load_configured_v6_baseline = lambda _repo: (object(), fresh.V6_M_CANDIDATES)
        fresh.load_kernel_wrapper = lambda _repo: (object(), "w", {})
        fresh.load_route_predecessor_reference = lambda _repo: ({}, {})
        fresh.configure_parent_execution = lambda *_args: {}
        fresh.validate_and_relabel = lambda result, *_args: result
        self.assertIs(fresh._run_verified(HERE), sentinel)
        self.assertEqual(observed, {"repo": HERE.resolve(), "mode": SCREEN.MODE})

        resource_error = RuntimeError("resource identity")

        class FailingParent:
            @staticmethod
            def _run_verified(_repo, _mode):
                raise resource_error

        fresh.load_control_flow_parent = lambda _repo: FailingParent()
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

    def test_05_public_run_always_uses_fresh_self(self):
        sentinel = {"fresh": True}

        class Inner:
            @staticmethod
            def _run_verified(repo):
                self.assertEqual(repo, HERE)
                return sentinel

        original = SCREEN.fresh_self_module
        try:
            SCREEN.fresh_self_module = lambda: Inner()
            self.assertIs(SCREEN.run(HERE), sentinel)
        finally:
            SCREEN.fresh_self_module = original

    def test_06_synthetic_prefix_handoff_and_tamper_checks(self):
        predecessor = load_predecessor()
        result = synthetic_parent_result()
        handoff = SCREEN.validate_replay_handoff(result, predecessor)
        self.assertTrue(handoff["q1_through_q80_common_records_exact"])
        self.assertEqual(handoff["q81_selected_candidate_index"], 30)
        self.assertEqual(handoff["q81_selected_K"], 557_056)
        self.assertEqual(
            handoff["q81_selected_history_prefix_sha256"],
            SCREEN.EXPECTED_Q81_SELECTED_HISTORY_PREFIX_SHA256,
        )
        tamper_cases = {
            "prefix common": lambda item: item["records"][0].__setitem__("stage_index", 99),
            "prefix candidate": lambda item: item["records"][1]["candidate_records"][0].__setitem__("drop_ticks", "9"),
            "q81 appended count": lambda item: item["records"][80]["candidate_records"][30].__setitem__("dropped_term_count", 40_199),
            "q81 selected": lambda item: item["records"][80].__setitem__("selected_K", 540_672),
            "history": lambda item: item["selected_K_history"].__setitem__(80, 540_672),
        }
        for label, mutate in tamper_cases.items():
            with self.subTest(label=label):
                tampered = synthetic_parent_result()
                mutate(tampered)
                with self.assertRaises(RuntimeError):
                    SCREEN.validate_replay_handoff(tampered, predecessor)

    def test_07_synthetic_relabel_provenance_is_layered_and_diagnostic(self):
        fresh = SCREEN.fresh_self_module()
        predecessor, reference = fresh.load_route_predecessor_reference(HERE)
        _configuration, baseline_m = fresh.load_configured_v6_baseline(HERE)
        _wrapper, wrapper_sha, manifest = fresh.load_kernel_wrapper(HERE)
        result = fresh.validate_and_relabel(
            synthetic_parent_result(),
            predecessor,
            reference,
            baseline_m,
            wrapper_sha,
            manifest,
            {"changed_fields": ["MODE_CONFIG.magnetization.horizon_checkpoint_count"]},
        )
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_k557056_c31_q82_screen_v1",
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertTrue(result["control_flow_parent_private_entrypoint_called"])
        self.assertFalse(result["control_flow_owned_by_screen"])
        paths = [item["relative_path"] for item in result["screen_execution_components"]]
        self.assertIn(SCREEN.CONTROL_FLOW_PARENT_NAME, paths)
        self.assertIn(SCREEN.KERNEL_WRAPPER_NAME, paths)
        self.assertNotIn(SCREEN.ROUTE_PREDECESSOR_SCREEN_NAME, paths)
        self.assertNotIn("hubbard_l8_adaptive_k_arithmetic_k540672.py", paths)
        route = result["route_predecessor_reference"]
        self.assertFalse(route["screen"]["compiled"])
        self.assertFalse(route["screen"]["executed"])
        self.assertFalse(route["canonical_transcript"]["propagation_input"])
        self.assertFalse(route["canonical_transcript"]["state_resume_input"])
        for key, value_key in (
            ("screen_execution_components_sha256", "screen_execution_components"),
            ("configuration_reference_sha256", "configuration_reference"),
            ("configuration_override_sha256", "configuration_override"),
            ("kernel_capability_override_sha256", "kernel_capability_override"),
            ("route_predecessor_reference_sha256", "route_predecessor_reference"),
            ("predecessor_handoff_validation_sha256", "predecessor_handoff_validation"),
            ("checkpoint_transform_sha256", "checkpoint_transform"),
        ):
            self.assertEqual(result[key], digest(result[value_key]))
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])

    def test_08_atomic_output_is_bounded_and_failure_preserving(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "transcript.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"[]"))
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                SCREEN.write_atomic_bounded(output, b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1))
            self.assertEqual(output.read_bytes(), b"{}")
            self.assertEqual(list(pathlib.Path(directory).glob("*.tmp")), [])

    def test_09_canonical_transcript_ledger_if_present(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical q82 result requires opt-in replay")
        raw = path.read_bytes()
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_CANONICAL["file_sha256"])
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(transcript["candidate_K_values"], list(SCREEN.M_CANDIDATES))
        self.assertEqual(transcript["candidate_K_values_sha256"], SCREEN.EXPECTED_CANDIDATE_SHA256)
        self.assertEqual(transcript["records_sha256"], digest(transcript["records"]))
        self.assertEqual(transcript["selected_K_history_sha256"], digest(transcript["selected_K_history"]))
        frozen_hashes = {
            "records_sha256": "records_sha256",
            "selected_K_history_sha256": "history_sha256",
            "screen_execution_components_sha256": "components_sha256",
            "configuration_reference_sha256": "configuration_reference_sha256",
            "configuration_override_sha256": "configuration_override_sha256",
            "kernel_capability_override_sha256": "kernel_override_sha256",
            "parent_horizon_override_sha256": "horizon_override_sha256",
            "route_predecessor_reference_sha256": "route_reference_sha256",
            "predecessor_handoff_validation_sha256": "handoff_sha256",
            "checkpoint_transform_sha256": "transform_sha256",
        }
        for transcript_field, expected_field in frozen_hashes.items():
            self.assertEqual(
                transcript[transcript_field],
                EXPECTED_CANONICAL[expected_field],
                transcript_field,
            )
        self.assertIsNone(transcript["failure_record_sha256"])
        self.assertEqual(transcript["attempted_checkpoint_count"], 82)
        self.assertEqual(transcript["completed_checkpoint_count"], 82)
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"],
            EXPECTED_CANONICAL["last_E"],
        )
        self.assertEqual(
            transcript["observed_peak_single_expansion_terms"],
            EXPECTED_CANONICAL["peak"],
        )
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            EXPECTED_CANONICAL["visits"],
        )
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            EXPECTED_CANONICAL["coefficient_bits"],
        )
        self.assertEqual(
            transcript["observed_maximum_product_bits"],
            EXPECTED_CANONICAL["product_bits"],
        )
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            EXPECTED_CANONICAL["rounding"],
        )
        expected_tail = {
            81: (597_254, 557_056, 40_198, "36221002561"),
            82: (641_180, 557_056, 84_124, "233809652747"),
        }
        for checkpoint, expected in expected_tail.items():
            record = transcript["records"][checkpoint - 1]
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint)
            self.assertEqual(
                (
                    record["pretruncation_expansion_count"],
                    record["selected_K"],
                    record["selected_dropped_term_count"],
                    record["selected_drop_ticks"],
                ),
                expected,
            )
            self.assertEqual(record["selected_candidate_index"], 30)
        predecessor = load_predecessor()
        SCREEN.validate_replay_handoff(transcript, predecessor)
        maximum_drop = (1 << 64) // 4000
        E_input = int(transcript["input_cumulative_drop_ticks"])
        denominator = transcript["future_checkpoint_denominator"]
        cumulative = E_input
        history = []
        for q, record in enumerate(transcript["records"], 1):
            cap = E_input + q * (maximum_drop - E_input) // denominator
            self.assertEqual(record["checkpoint_number_one_based"], q)
            self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
            self.assertEqual(int(record["E_before_ticks"]), cumulative)
            rows = record["candidate_records"]
            self.assertEqual([row["configured_K"] for row in rows], list(SCREEN.M_CANDIDATES))
            feasible = []
            drops = []
            for index, row in enumerate(rows):
                drop = int(row["drop_ticks"])
                drops.append(drop)
                self.assertEqual(row["candidate_index"], index)
                self.assertEqual(int(row["E_after_if_selected_ticks"]), cumulative + drop)
                expected = cumulative + drop <= cap
                self.assertIs(row["feasible_under_current_prefix_cap"], expected)
                if expected:
                    feasible.append(index)
            self.assertEqual(drops, sorted(drops, reverse=True))
            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                selected = feasible[0]
                self.assertEqual(record["selected_candidate_index"], selected)
                cumulative += drops[selected]
                self.assertEqual(int(record["E_after_ticks"]), cumulative)
                history.append(SCREEN.M_CANDIDATES[selected])
            else:
                self.assertFalse(feasible)
        self.assertEqual(history, transcript["selected_K_history"])

    def test_10_scope_is_diagnostic_only(self):
        source = (HERE / SCREEN_NAME).read_text()
        for forbidden in (
            "dual_screen_checker",
            "formal_witness",
            "boundary_sidecar",
            "READY_FOR_BENCHMARK",
            "traceback",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("candidate_policy_precommitted_at_probe_time", source)
        self.assertIn("positive_artifact_generated", source)

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_M_K557056_C31_Q82_REPLAY") == "1",
        "expensive deterministic q82 replay is opt-in",
    )
    def test_11_real_replay_is_opt_in(self):
        result = SCREEN.run(HERE)
        self.assertEqual(result["attempted_checkpoint_count"], 82)
        self.assertIn(result["completed_checkpoint_count"], (81, 82))
        self.assertEqual(result["selected_K_history"][80], 557_056)


if __name__ == "__main__":
    unittest.main()
