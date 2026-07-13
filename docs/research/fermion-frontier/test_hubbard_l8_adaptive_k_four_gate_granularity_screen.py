#!/usr/bin/env python3
"""Static and synthetic tests for the L8 four-gate granularity screen."""

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


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module(
    "hubbard_l8_adaptive_k_four_gate_granularity_screen",
    "hubbard_l8_adaptive_k_four_gate_granularity_screen.py",
)
V6 = load_module(
    "hubbard_l8_adaptive_k_v6_for_four_gate_tests",
    "hubbard_l8_adaptive_k_v6_design_probe.py",
)


EXPECTED_CANONICAL = {
    "magnetization": {
        "file_sha256": (
            "18629c9a0841e1e3308eda0bc7f3cbc568c8ed2925a6b95d1c3e7b7665b142a0"
        ),
        "candidate_sha256": (
            "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
        ),
        "records_sha256": (
            "2c96c89edd65e47e9fc6ba60d70b52d11d3a0f24b110e32a25ae60a2f2fe5c94"
        ),
        "failure_sha256": (
            "ffa87f177a3d072ddefff2aaa14b7499d537483579ab8c73bfe7153138660e34"
        ),
        "history_sha256": (
            "5812a3b5d996102c3e2393fea0e514466afd01026467b702407c634229f34171"
        ),
        "components_sha256": (
            "5252be8a9819a38bd678167f66e64fbe95301485f2bb894138eeab940c181ee9"
        ),
        "configuration_sha256": (
            "837d33eb2606fd76e99adeed746f8586945730905907682331188158d61f0e40"
        ),
        "transform_sha256": (
            "c2aa225b96c984618d0dd0454dba9cb20f20ae8749f3f2452d8982a399f07336"
        ),
        "completed": 77,
        "attempted": 78,
        "horizon": 80,
        "failure_checkpoint": 78,
        "failure_gates": (308, 311),
        "minimum_K": 529_897,
        "K_excess": 5_609,
        "peak": 643_624,
        "visits": 82_493_877,
        "coefficient_bits": 57,
        "product_bits": 121,
        "rounding": "113613969553110308900100155",
        "last_E": "1699371517687500",
    },
    "double_occupancy": {
        "file_sha256": (
            "2b83f7f349cb0b7fedab4ad8b8058606c239b01d45579722afc490c35f684060"
        ),
        "candidate_sha256": (
            "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
        ),
        "records_sha256": (
            "b1f27ae52362150f5522cccf7aa2056c3197c6048855654836a57c40a0c30bec"
        ),
        "failure_sha256": (
            "6abdfe58f6f31739ad3ec845ec823a930c18ce4db3fdbefcde316d2c5991cef9"
        ),
        "history_sha256": (
            "ecb91ccb56d8138d2acb61f20a44b3fe52ed9cdfcbc615f418595be4e6b7ce24"
        ),
        "components_sha256": (
            "db6b0876d5f254ed2bf1f7a3b91069e402ffb4f4e2e2c3dd06206d17ca6b9eb1"
        ),
        "configuration_sha256": (
            "8d5938c114a0f07c412af54acb551af0de6ce3ff946b8fa065a8bf90bc62e755"
        ),
        "transform_sha256": (
            "c2aa225b96c984618d0dd0454dba9cb20f20ae8749f3f2452d8982a399f07336"
        ),
        "completed": 64,
        "attempted": 65,
        "horizon": 66,
        "failure_checkpoint": 65,
        "failure_gates": (256, 259),
        "minimum_K": 532_869,
        "K_excess": 8_581,
        "peak": 645_011,
        "visits": 75_412_433,
        "coefficient_bits": 63,
        "product_bits": 120,
        "rounding": "97566995223829305135753351",
        "last_E": "2288313355855945",
        "counterfactual_sha256": (
            "cabedc65c77b769a4b27ef335eeadcd472b367d1d17417c3779e5db89a8190d4"
        ),
    },
}

NONCANONICAL_D_SENSITIVITY_CANDIDATES = tuple(
    sorted(
        (
            set(V6.MODE_CONFIG["double_occupancy"]["candidates"])
            - {65_536}
        )
        | {491_520}
    )
)
NONCANONICAL_D_SENSITIVITY_CANDIDATE_SHA256 = (
    "7458c68c9e04bd79e2a41f8eec8406fb571f36e51a42b86d73c2852349bd8cd9"
)


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def walk(value):
    yield value
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from walk(child)
    elif type(value) is list:
        for child in value:
            yield from walk(child)


class FourGateGranularityScreenTests(unittest.TestCase):
    def test_01_exact_source_pins_fresh_self_and_configuration_only_v6(self):
        screen_payload = (HERE / SCREEN.SELF_NAME).read_bytes()
        v2_payload = (HERE / SCREEN.V2_HELPER_NAME).read_bytes()
        v6_payload = (HERE / SCREEN.V6_CONFIGURATION_NAME).read_bytes()
        kernel_payload = (HERE / SCREEN.KERNEL_NAME).read_bytes()
        root_payload = (HERE / SCREEN.ROOT_NAME).read_bytes()
        self.assertEqual(
            hashlib.sha256(screen_payload).hexdigest(),
            "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614",
        )
        for payload, expected in (
            (v2_payload, SCREEN.EXPECTED_V2_HELPER_SHA256),
            (v6_payload, SCREEN.EXPECTED_V6_CONFIGURATION_SHA256),
            (kernel_payload, SCREEN.EXPECTED_KERNEL_SHA256),
            (root_payload, SCREEN.EXPECTED_ROOT_SHA256),
        ):
            self.assertEqual(hashlib.sha256(payload).hexdigest(), expected)

        fresh = SCREEN.fresh_self_module()
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, screen_payload)
        helper = SCREEN.load_v2_helper(HERE)
        configuration = SCREEN.load_v6_configuration(HERE)
        self.assertEqual(helper._VERIFIED_SELF_SOURCE_BYTES, v2_payload)
        self.assertEqual(configuration._VERIFIED_SELF_SOURCE_BYTES, v6_payload)
        self.assertIsNot(configuration, V6)
        self.assertNotIn("v6_configuration.run(", screen_payload.decode("utf-8"))

    def test_02_public_entry_always_uses_fresh_self(self):
        sentinel = {"fresh": True}

        class Inner:
            @staticmethod
            def _run_verified(repo, mode):
                self.assertEqual(repo, HERE)
                self.assertEqual(mode, "magnetization")
                return sentinel

        original_fresh = SCREEN.fresh_self_module
        original_private = SCREEN._run_verified
        try:
            SCREEN._run_verified = lambda *_args: self.fail("live private path used")
            SCREEN.fresh_self_module = lambda: Inner()
            self.assertIs(SCREEN.run(HERE, "magnetization"), sentinel)
        finally:
            SCREEN.fresh_self_module = original_fresh
            SCREEN._run_verified = original_private

    def test_03_v6_candidate_ladders_and_caps_are_exact(self):
        configuration = SCREEN.load_v6_configuration(HERE)
        candidates = {
            mode: configuration.MODE_CONFIG[mode]["candidates"]
            for mode in SCREEN.MODE_CONFIG
        }
        self.assertEqual(len(candidates["magnetization"]), 29)
        self.assertEqual(len(candidates["double_occupancy"]), 32)
        self.assertNotIn(
            SCREEN.REMOVED_D_CANDIDATE_K, candidates["double_occupancy"]
        )
        for mode, ladder in candidates.items():
            self.assertEqual(ladder[-1], 524_288)
            self.assertEqual(
                SCREEN.sha256(SCREEN.canonical_bytes(list(ladder))),
                SCREEN.EXPECTED_V6_CANDIDATE_SHA256[mode],
            )
        self.assertEqual(configuration.POLICY_CAPS_BASE, SCREEN.EXPECTED_V6_CAPS)
        self.assertEqual(
            SCREEN.sha256(SCREEN.canonical_bytes(SCREEN.EXPECTED_V6_CAPS)),
            SCREEN.EXPECTED_V6_CAPS_SHA256,
        )

    def test_04_fixed_geometry_is_9_by_1152_by_288_by_4(self):
        helper = SCREEN.load_v2_helper(HERE)
        kernel, root, _modules, _custody = SCREEN.load_execution_sources(
            HERE, helper, "magnetization"
        )
        stages, _trig, sequence, transform = SCREEN.build_four_gate_sequence(
            helper, root, kernel
        )
        self.assertEqual(sequence["stage_count"], 9)
        self.assertEqual(sequence["gate_count"], 1_152)
        self.assertEqual(sequence["checkpoint_count"], 288)
        self.assertEqual(sequence["gates_per_checkpoint"], 4)
        self.assertEqual(sequence["baseline_checkpoint_count"], 144)
        self.assertEqual(sequence["baseline_gates_per_checkpoint"], 8)
        self.assertEqual(
            sequence["backprop_gate_records_sha256"],
            SCREEN.EXPECTED_BACKPROP_GATE_RECORDS_SHA256,
        )
        self.assertEqual(sum(len(stage["gates"]) for stage in stages), 1_152)
        self.assertTrue(all(len(stage["gates"]) % 4 == 0 for stage in stages))
        self.assertEqual(
            transform["screen_geometry"],
            {
                "stage_count": 9,
                "gate_count": 1_152,
                "gates_per_checkpoint": 4,
                "checkpoints_per_mapped_step": 288,
            },
        )

    def test_05_denominators_and_every_aligned_prefix_cap_are_exact(self):
        helper = SCREEN.load_v2_helper(HERE)
        expected_denominators = {
            "magnetization": 27_936,
            "double_occupancy": 28_224,
        }
        for mode, denominator4 in expected_denominators.items():
            cfg = helper.CONFIG[mode]
            remaining = 100 - cfg["input_step_index"]
            E = cfg["input_cumulative_drop_ticks"]
            B = helper.MAXIMUM_DROP_TICKS
            denominator8 = remaining * 144
            self.assertEqual(denominator4, remaining * 288)
            for q8 in range(145):
                cap8 = E + q8 * (B - E) // denominator8
                cap4 = E + (2 * q8) * (B - E) // denominator4
                self.assertEqual(cap4, cap8, (mode, q8))

    def synthetic_two_checkpoint_result(self):
        fresh = SCREEN.fresh_self_module()
        fresh.MODE_CONFIG = copy.deepcopy(fresh.MODE_CONFIG)
        fresh.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"] = 2
        initial = {("initial", 0): (1, 1)}
        propagated_inputs = []
        retained_outputs = []

        class Counter:
            def __init__(self):
                self.term_gate_visits = 0
                self.maximum_expansion_coefficient_tick_bits = 1
                self.maximum_product_bits = 1
                self.multiplication_rounding_l1_scaled_ticks_squared = 0
                self.window_peak_live_terms = 0
                self.peak_live_terms = 0

            def observe(self, expansion):
                self.window_peak_live_terms = max(
                    self.window_peak_live_terms, len(expansion)
                )
                self.peak_live_terms = max(self.peak_live_terms, len(expansion))

            def observe_interval(self, _interval):
                return None

        class Kernel:
            RESOURCE_LIMITS = {
                "max_candidate_count": 32,
                "max_retained_K": 524_288,
            }
            PropagationCounterV2 = Counter

            @staticmethod
            def root_global_snapshot(_root):
                return {"unchanged": True}

            @staticmethod
            def canonical_sha256(value):
                return hashlib.sha256(canonical_bytes(value)).hexdigest()

            @staticmethod
            def tick_digest(expansion):
                return hashlib.sha256(repr(sorted(expansion.items())).encode()).hexdigest()

            @staticmethod
            def propagate_batch(expansion, batch, _trig, counter):
                propagated_inputs.append(copy.deepcopy(expansion))
                call = len(propagated_inputs)
                output = {
                    (f"pre{call}", 0): (1, 1),
                    (f"junk{call}", 0): (1, 1),
                }
                counter.term_gate_visits += len(batch) * len(expansion)
                counter.window_peak_live_terms = len(output)
                counter.peak_live_terms = max(counter.peak_live_terms, len(output))
                return output

            @staticmethod
            def rank_with_suffix(expansion):
                ranked = list(expansion)
                return ranked, [0] * (len(ranked) + 1)

            @staticmethod
            def evaluate_candidates(
                pre_count, _suffix, candidates, cumulative, prefix_cap
            ):
                records = []
                for index, configured_K in enumerate(candidates):
                    effective = min(configured_K, pre_count)
                    records.append({
                        "candidate_index": index,
                        "configured_K": configured_K,
                        "effective_retained_count": effective,
                        "dropped_term_count": pre_count - effective,
                        "drop_ticks": "0",
                        "E_after_if_selected_ticks": str(cumulative),
                        "feasible_under_current_prefix_cap": (
                            cumulative <= prefix_cap
                        ),
                    })
                return records, 0

            @staticmethod
            def commit_candidate(
                _expansion,
                _ranked,
                _suffix,
                _candidates,
                _cumulative,
                _prefix_cap,
                _selected_index,
            ):
                call = len(retained_outputs) + 1
                retained = {(f"retained{call}", 0): (1, 1)}
                retained_outputs.append(copy.deepcopy(retained))
                return retained, {
                    "effective_retained_count": 1,
                    "dropped_term_count": 1,
                    "dropped_l1_ticks": 0,
                    "dropped_terms_sha256": f"dropped-{call}",
                    "retained_expansion_sha256": Kernel.tick_digest(retained),
                    "minimum_retained_abs_upper_ticks": 1,
                    "maximum_dropped_abs_upper_ticks": 1,
                }

        class Helper:
            CONFIG = {
                "magnetization": {
                    "observable_id": "stub_magnetization",
                    "input_step_index": 3,
                    "child_step_index": 4,
                    "input_cumulative_drop_ticks": 0,
                    "parent_expected_witness_sha256": "stub-parent",
                }
            }
            MAXIMUM_DROP_TICKS = 1_000_000
            KERNEL_COMMIT = "stub-kernel"

            @staticmethod
            def enforce_policy_caps(_kernel, _counter, _count, _caps):
                return None

            @staticmethod
            def gate_batch_sha256(batch):
                return hashlib.sha256(repr(batch).encode()).hexdigest()

            @staticmethod
            def ranked_suffix_sha256(_expansion, ranked, suffix):
                return hashlib.sha256(repr((ranked, suffix)).encode()).hexdigest()

            @staticmethod
            def minimum_effective_k(_suffix, _slack):
                return 0

        class Configuration:
            MODE_CONFIG = {
                "magnetization": {
                    "candidates": tuple(V6.MODE_CONFIG["magnetization"]["candidates"])
                }
            }
            POLICY_CAPS_BASE = dict(V6.POLICY_CAPS_BASE)

        gates = [((index, 0), index) for index in range(8)]
        sequence = {
            "stage_count": 1,
            "gate_count": 8,
            "checkpoint_count": 2,
            "gates_per_checkpoint": 4,
        }
        custody = {
            SCREEN.KERNEL_NAME: SCREEN.EXPECTED_KERNEL_SHA256,
            SCREEN.ROOT_NAME: SCREEN.EXPECTED_ROOT_SHA256,
        }
        boundary = {
            "relative_path": "stub_boundary.b85",
            "encoded_sha256": "b" * 64,
        }
        fresh.load_v2_helper = lambda _repo: Helper()
        fresh.load_v6_configuration = lambda _repo: Configuration()
        fresh.load_execution_sources = lambda *_args: (
            Kernel(), object(), {}, custody
        )
        fresh.load_exact_boundary = lambda *_args: (
            copy.deepcopy(initial), {}, boundary
        )
        fresh.build_four_gate_sequence = lambda *_args: (
            [{"group": "stub", "gates": gates}],
            {},
            sequence,
            {"transform_id": "synthetic-four-gate"},
        )
        result = fresh.run_four_gate(HERE, "magnetization")
        return result, initial, propagated_inputs, retained_outputs, Helper

    def test_06_each_four_gate_batch_commits_into_the_next_input(self):
        result, initial, propagated_inputs, retained_outputs, helper = (
            self.synthetic_two_checkpoint_result()
        )
        self.assertEqual(len(propagated_inputs), 2)
        self.assertEqual(len(retained_outputs), 2)
        self.assertEqual(propagated_inputs[0], initial)
        self.assertEqual(propagated_inputs[1], retained_outputs[0])
        records = result["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(
            records[1]["input_expansion_sha256"],
            hashlib.sha256(
                repr(sorted(retained_outputs[0].items())).encode()
            ).hexdigest(),
        )
        self.assertEqual(result["selected_K_history"], [65_536, 65_536])
        self.assertTrue(result["horizon_reached_with_committed_checkpoint"])
        self.assertEqual(result["screen_terminal_condition"], "DIAGNOSTIC_HORIZON_REACHED")
        for index, record in enumerate(records):
            self.assertEqual(record["checkpoint_index_zero_based"], index)
            self.assertEqual(record["checkpoint_number_one_based"], index + 1)
            self.assertEqual(record["gate_occurrence_first_zero_based"], 4 * index)
            self.assertEqual(record["gate_occurrence_last_zero_based"], 4 * index + 3)
            expected_batch = [((gate, 0), gate) for gate in range(4 * index, 4 * index + 4)]
            self.assertEqual(
                record["gate_batch_sha256"], helper.gate_batch_sha256(expected_batch)
            )

    def test_07_provenance_does_not_masquerade_as_v6_execution_parent(self):
        result, *_rest = self.synthetic_two_checkpoint_result()
        self.assertTrue(result["same_byte_self_execution"])
        self.assertFalse(result["v2_run_entrypoint_called"])
        self.assertFalse(result["v6_execution_invoked"])
        self.assertFalse(result["v6_same_byte_execution_parent"])
        self.assertTrue(result["control_flow_owned_by_screen"])
        reference = result["configuration_reference"]
        self.assertEqual(reference["role"], "candidates_and_caps_reference_only")
        self.assertFalse(reference["v6_execution_invoked"])
        self.assertFalse(reference["v6_same_byte_execution_parent"])
        self.assertEqual(
            result["configuration_reference_sha256"],
            SCREEN.sha256(SCREEN.canonical_bytes(reference)),
        )
        self.assertNotIn("implementation_parent_probe_source_sha256", result)
        roles = [item["role"] for item in result["screen_execution_components"]]
        self.assertIn("v2_helper_provider_not_run_entrypoint", roles)
        self.assertIn("v6_candidates_and_caps_reference_only", roles)

    def test_08_removed_491520_counterfactual_is_exact(self):
        case = self

        class SparseSuffix:
            def __getitem__(self, index):
                case.assertEqual(index, 491_520)
                return 7

        feasible = SCREEN.removed_candidate_counterfactual(
            491_521, SparseSuffix(), 10, 17, 507_904
        )
        self.assertEqual(feasible["configured_K"], 491_520)
        self.assertEqual(feasible["effective_retained_count"], 491_520)
        self.assertEqual(feasible["dropped_term_count"], 1)
        self.assertTrue(feasible["feasible_under_current_prefix_cap"])
        self.assertTrue(feasible["would_precede_selected"])
        self.assertTrue(feasible["would_be_selected_if_inserted"])
        infeasible = SCREEN.removed_candidate_counterfactual(
            491_521, SparseSuffix(), 10, 16, 507_904
        )
        self.assertFalse(infeasible["feasible_under_current_prefix_cap"])
        self.assertFalse(infeasible["would_precede_selected"])
        self.assertFalse(infeasible["would_be_selected_if_inserted"])

    def test_09_resource_exception_object_is_propagated_unchanged(self):
        fresh = SCREEN.fresh_self_module()
        resource_error = RuntimeError("four-gate resource sentinel")

        def fail(_repo, _mode):
            raise resource_error

        fresh.run_four_gate = fail
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE, "double_occupancy")
        self.assertIs(caught.exception, resource_error)

    def test_10_four_mib_atomic_output_is_failure_preserving(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "screen.json"
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

    def test_11_scope_is_diagnostic_only(self):
        result, *_rest = self.synthetic_two_checkpoint_result()
        self.assertEqual(
            result["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
        )
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])
        source = (HERE / SCREEN.SELF_NAME).read_text()
        for forbidden in (
            "READY_FOR_BENCHMARK",
            "formal_witness",
            "boundary_sidecar",
            "dual_screen_checker",
        ):
            self.assertNotIn(forbidden, source)

    def assert_canonical_transcript(self, mode):
        path = HERE / SCREEN.MODE_CONFIG[mode]["output_name"]
        if not path.exists():
            self.skipTest(f"canonical {mode} four-gate transcript not generated yet")
        expected = EXPECTED_CANONICAL[mode]
        raw = path.read_bytes()
        transcript = json.loads(raw)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["file_sha256"])
        self.assertEqual(
            transcript["transcript_fingerprint"],
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1",
        )
        self.assertNotIn("v7", transcript["transcript_fingerprint"])
        self.assertEqual(
            transcript["status"],
            "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        )
        self.assertEqual(
            transcript["screen_terminal_condition"],
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        )
        self.assertTrue(transcript["same_byte_self_execution"])
        self.assertTrue(transcript["v2_helper_compiled_from_verified_bytes"])
        self.assertFalse(transcript["v2_run_entrypoint_called"])
        self.assertTrue(transcript["v6_configuration_compiled_from_verified_bytes"])
        self.assertFalse(transcript["v6_execution_invoked"])
        self.assertFalse(transcript["v6_same_byte_execution_parent"])
        self.assertTrue(transcript["control_flow_owned_by_screen"])
        self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])
        self.assertTrue(
            transcript["runtime_RSS_host_timestamp_and_float_fields_excluded"]
        )
        self.assertEqual(
            transcript["screen_source_sha256"],
            "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614",
        )
        self.assertEqual(
            transcript["candidate_K_values_sha256"],
            expected["candidate_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(canonical_bytes(transcript["candidate_K_values"])).hexdigest(),
            expected["candidate_sha256"],
        )
        for field, value, digest_key in (
            (
                "screen_execution_components_sha256",
                transcript["screen_execution_components"],
                "components_sha256",
            ),
            (
                "configuration_reference_sha256",
                transcript["configuration_reference"],
                "configuration_sha256",
            ),
            (
                "checkpoint_transform_sha256",
                transcript["checkpoint_transform"],
                "transform_sha256",
            ),
        ):
            digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
            self.assertEqual(digest, expected[digest_key])
            self.assertEqual(transcript[field], expected[digest_key])
        roles = [item["role"] for item in transcript["screen_execution_components"]]
        self.assertIn("v2_helper_provider_not_run_entrypoint", roles)
        self.assertIn("v6_candidates_and_caps_reference_only", roles)
        for component in transcript["screen_execution_components"]:
            payload = (HERE / component["relative_path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(), component["sha256"]
            )
        self.assertEqual(
            transcript["configuration_reference"]["role"],
            "candidates_and_caps_reference_only",
        )
        self.assertNotIn("implementation_parent_probe_source_sha256", transcript)
        self.assertEqual(transcript["sequence"]["stage_count"], 9)
        self.assertEqual(transcript["sequence"]["gate_count"], 1_152)
        self.assertEqual(transcript["sequence"]["checkpoint_count"], 288)
        self.assertEqual(transcript["sequence"]["gates_per_checkpoint"], 4)
        self.assertEqual(
            transcript["future_checkpoint_denominator"],
            {"magnetization": 27_936, "double_occupancy": 28_224}[mode],
        )
        self.assertEqual(transcript["screen_horizon_checkpoint_count"], expected["horizon"])
        self.assertEqual(transcript["completed_checkpoint_count"], expected["completed"])
        self.assertEqual(transcript["attempted_checkpoint_count"], expected["attempted"])
        self.assertTrue(transcript["failure_checkpoint_included"])
        self.assertFalse(transcript["horizon_checkpoint_attempted"])
        self.assertFalse(transcript["horizon_reached_with_committed_checkpoint"])

        helper = SCREEN.load_v2_helper(HERE)
        kernel, root, modules, source_custody = SCREEN.load_execution_sources(
            HERE, helper, mode
        )
        stages, _trig, rebuilt_sequence, rebuilt_transform = (
            SCREEN.build_four_gate_sequence(
                helper, root, kernel
            )
        )
        boundary_expansion, _state, boundary_custody = SCREEN.load_exact_boundary(
            HERE,
            helper,
            mode,
            modules,
            kernel,
            root,
        )
        self.assertEqual(transcript["sequence"], rebuilt_sequence)
        self.assertEqual(transcript["checkpoint_transform"], rebuilt_transform)
        self.assertEqual(transcript["input_boundary_custody"], boundary_custody)
        self.assertEqual(
            transcript["source_custody"],
            {
                SCREEN.V2_HELPER_NAME: SCREEN.EXPECTED_V2_HELPER_SHA256,
                SCREEN.V6_CONFIGURATION_NAME: (
                    SCREEN.EXPECTED_V6_CONFIGURATION_SHA256
                ),
                **source_custody,
            },
        )
        self.assertEqual(
            transcript["screen_execution_components"],
            SCREEN.execution_components(
                mode,
                transcript["screen_source_sha256"],
                source_custody,
                boundary_custody,
            ),
        )
        configuration = SCREEN.load_v6_configuration(HERE)
        configured_candidates = list(
            configuration.MODE_CONFIG[mode]["candidates"]
        )
        expected_configuration_reference = {
            "relative_path": SCREEN.V6_CONFIGURATION_NAME,
            "source_sha256": SCREEN.EXPECTED_V6_CONFIGURATION_SHA256,
            "role": "candidates_and_caps_reference_only",
            "fields_adopted": [
                f"MODE_CONFIG.{mode}.candidates",
                "POLICY_CAPS_BASE",
            ],
            "candidate_K_values_sha256": expected["candidate_sha256"],
            "policy_caps_base_sha256": SCREEN.EXPECTED_V6_CAPS_SHA256,
            "v6_execution_invoked": False,
            "v6_same_byte_execution_parent": False,
        }
        self.assertEqual(
            transcript["configuration_reference"],
            expected_configuration_reference,
        )
        expected_caps = dict(configuration.POLICY_CAPS_BASE)
        expected_caps["max_candidate_count"] = len(configured_candidates)
        self.assertEqual(transcript["proposed_policy_caps"], expected_caps)
        gates = [gate for stage in stages for gate in stage["gates"]]
        maximum_drop = int(transcript["maximum_cumulative_drop_ticks"])
        E_input = int(transcript["input_cumulative_drop_ticks"])
        denominator = transcript["future_checkpoint_denominator"]
        candidates = transcript["candidate_K_values"]
        helper_config = helper.CONFIG[mode]
        self.assertEqual(candidates, configured_candidates)
        self.assertEqual(E_input, helper_config["input_cumulative_drop_ticks"])
        self.assertEqual(maximum_drop, helper.MAXIMUM_DROP_TICKS)
        self.assertEqual(
            denominator,
            (100 - helper_config["input_step_index"])
            * SCREEN.CHECKPOINTS_PER_MAPPED_STEP,
        )
        self.assertEqual(
            transcript["input_step_index"], helper_config["input_step_index"]
        )
        self.assertEqual(
            transcript["attempted_child_step_index"],
            helper_config["child_step_index"],
        )
        self.assertEqual(
            transcript["records"][0]["input_expansion_count"],
            len(boundary_expansion),
        )
        self.assertEqual(
            transcript["records"][0]["input_expansion_sha256"],
            kernel.tick_digest(boundary_expansion),
        )
        cumulative = E_input
        selected_history = []
        previous = None
        visits = 0
        rounding = 0
        peak = 0
        coefficient_bits = 0
        product_bits = 0
        statuses = [record["status"] for record in transcript["records"]]
        self.assertEqual(
            statuses,
            ["DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"] * expected["completed"]
            + ["DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"],
        )
        for index, record in enumerate(transcript["records"]):
            checkpoint_number = index + 1
            self.assertEqual(record["checkpoint_index_zero_based"], index)
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint_number)
            self.assertEqual(record["gate_occurrence_first_zero_based"], 4 * index)
            self.assertEqual(record["gate_occurrence_last_zero_based"], 4 * index + 3)
            self.assertEqual(
                record["gate_batch_sha256"],
                helper.gate_batch_sha256(gates[4 * index:4 * index + 4]),
            )
            if previous is not None:
                self.assertEqual(
                    record["input_expansion_count"],
                    previous["retained_expansion_count"],
                )
                self.assertEqual(
                    record["input_expansion_sha256"],
                    previous["retained_expansion_sha256"],
                )
            cap = E_input + checkpoint_number * (maximum_drop - E_input) // denominator
            self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
            self.assertEqual(int(record["E_before_ticks"]), cumulative)
            self.assertEqual(
                int(record["prefix_slack_before_selection_ticks"]), cap - cumulative
            )
            visits += record["term_gate_visits_increment"]
            self.assertEqual(record["term_gate_visits_cumulative"], visits)
            rounding += int(record["rounding_increment_scaled_ticks_squared"])
            self.assertEqual(
                int(record["rounding_cumulative_scaled_ticks_squared"]), rounding
            )
            peak = max(peak, record["peak_live_terms_this_checkpoint"])
            self.assertEqual(record["peak_live_terms_cumulative"], peak)
            self.assertGreaterEqual(
                record["maximum_expansion_coefficient_tick_bits"], coefficient_bits
            )
            self.assertGreaterEqual(record["maximum_product_bits"], product_bits)
            coefficient_bits = record["maximum_expansion_coefficient_tick_bits"]
            product_bits = record["maximum_product_bits"]
            candidate_records = record["candidate_records"]
            self.assertEqual(
                [item["configured_K"] for item in candidate_records], candidates
            )
            drops = []
            feasible_indices = []
            for candidate_index, item in enumerate(candidate_records):
                drop = int(item["drop_ticks"])
                drops.append(drop)
                self.assertEqual(item["candidate_index"], candidate_index)
                self.assertEqual(
                    item["effective_retained_count"],
                    min(item["configured_K"], record["pretruncation_expansion_count"]),
                )
                self.assertEqual(
                    item["dropped_term_count"],
                    record["pretruncation_expansion_count"]
                    - item["effective_retained_count"],
                )
                self.assertEqual(
                    int(item["E_after_if_selected_ticks"]), cumulative + drop
                )
                feasible = cumulative + drop <= cap
                self.assertIs(item["feasible_under_current_prefix_cap"], feasible)
                if feasible:
                    feasible_indices.append(candidate_index)
            self.assertEqual(drops, sorted(drops, reverse=True))
            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                self.assertTrue(feasible_indices)
                selected = feasible_indices[0]
                self.assertEqual(record["selected_candidate_index"], selected)
                self.assertEqual(record["selected_K"], candidates[selected])
                self.assertEqual(int(record["selected_drop_ticks"]), drops[selected])
                selected_row = candidate_records[selected]
                self.assertEqual(
                    record["selected_effective_retained_count"],
                    selected_row["effective_retained_count"],
                )
                self.assertEqual(
                    record["selected_dropped_term_count"],
                    selected_row["dropped_term_count"],
                )
                self.assertEqual(
                    record["retained_expansion_count"],
                    selected_row["effective_retained_count"],
                )
                cumulative += drops[selected]
                self.assertEqual(int(record["E_after_ticks"]), cumulative)
                selected_history.append(candidates[selected])
                previous = record
            else:
                self.assertEqual(
                    record["status"],
                    "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                )
                self.assertFalse(feasible_indices)
                self.assertIsNone(record["selected_candidate_index"])
                self.assertIsNone(record["selected_K"])
                self.assertEqual(
                    int(record["maximum_candidate_drop_excess_over_slack_ticks"]),
                    drops[-1] - (cap - cumulative),
                )
            if mode == "double_occupancy":
                self.assertIn("removed_491520_counterfactual", record)

        records = transcript["records"]
        failure = records[-1]
        self.assertEqual(len(records), expected["attempted"])
        self.assertEqual(len(selected_history), expected["completed"])
        self.assertEqual(
            hashlib.sha256(canonical_bytes(records)).hexdigest(),
            expected["records_sha256"],
        )
        self.assertEqual(transcript["records_sha256"], expected["records_sha256"])
        self.assertEqual(
            hashlib.sha256(canonical_bytes(failure)).hexdigest(),
            expected["failure_sha256"],
        )
        self.assertEqual(
            transcript["failure_record_sha256"], expected["failure_sha256"]
        )
        self.assertEqual(selected_history, transcript["selected_K_history"])
        self.assertEqual(
            hashlib.sha256(canonical_bytes(selected_history)).hexdigest(),
            expected["history_sha256"],
        )
        self.assertEqual(
            transcript["selected_K_history_sha256"], expected["history_sha256"]
        )
        self.assertEqual(str(cumulative), expected["last_E"])
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"], expected["last_E"]
        )
        self.assertEqual(
            failure["checkpoint_number_one_based"], expected["failure_checkpoint"]
        )
        self.assertEqual(
            (
                failure["gate_occurrence_first_zero_based"],
                failure["gate_occurrence_last_zero_based"],
            ),
            expected["failure_gates"],
        )
        self.assertEqual(
            failure["minimum_effective_K_to_meet_prefix"], expected["minimum_K"]
        )
        self.assertEqual(
            failure["required_K_excess_over_policy_maximum"], expected["K_excess"]
        )
        self.assertEqual(
            failure["required_K_excess_over_policy_maximum"],
            max(0, failure["minimum_effective_K_to_meet_prefix"] - candidates[-1]),
        )
        self.assertEqual(
            transcript["observed_peak_single_expansion_terms"], expected["peak"]
        )
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            expected["visits"],
        )
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            expected["coefficient_bits"],
        )
        self.assertEqual(
            transcript["observed_maximum_product_bits"], expected["product_bits"]
        )
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            expected["rounding"],
        )
        self.assertEqual(
            visits,
            transcript["observed_term_gate_visits_including_terminal_attempt"],
        )
        self.assertEqual(peak, transcript["observed_peak_single_expansion_terms"])
        self.assertEqual(
            coefficient_bits,
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
        )
        self.assertEqual(product_bits, transcript["observed_maximum_product_bits"])
        self.assertEqual(
            str(rounding),
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
        )
        self.assertLessEqual(
            transcript["observed_peak_single_expansion_terms"],
            transcript["proposed_policy_caps"]["max_single_expansion_terms"],
        )
        self.assertLessEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            transcript["proposed_policy_caps"]["max_term_gate_visits"],
        )

        if mode == "double_occupancy":
            counterfactuals = [
                record["removed_491520_counterfactual"] for record in records
            ]
            self.assertEqual(
                hashlib.sha256(canonical_bytes(counterfactuals)).hexdigest(),
                expected["counterfactual_sha256"],
            )
            would_select = []
            feasible_checkpoints = []
            for record, counterfactual in zip(records, counterfactuals):
                self.assertEqual(counterfactual["configured_K"], 491_520)
                self.assertEqual(
                    counterfactual["effective_retained_count"],
                    min(491_520, record["pretruncation_expansion_count"]),
                )
                self.assertEqual(
                    counterfactual["dropped_term_count"],
                    record["pretruncation_expansion_count"]
                    - counterfactual["effective_retained_count"],
                )
                cf_after = int(record["E_before_ticks"]) + int(
                    counterfactual["drop_ticks"]
                )
                self.assertEqual(
                    int(counterfactual["E_after_if_selected_ticks"]), cf_after
                )
                feasible = cf_after <= int(record["budget_prefix_cap_ticks"])
                self.assertIs(
                    counterfactual["feasible_under_current_prefix_cap"], feasible
                )
                selected_K = record["selected_K"]
                self.assertEqual(counterfactual["actual_selected_K"], selected_K)
                if feasible:
                    feasible_checkpoints.append(record["checkpoint_number_one_based"])
                would_precede = (
                    selected_K is not None and feasible and 491_520 < selected_K
                )
                self.assertIs(counterfactual["would_precede_selected"], would_precede)
                self.assertIs(
                    counterfactual["would_be_selected_if_inserted"],
                    feasible and (selected_K is None or 491_520 < selected_K),
                )
                drop_by_K = {
                    item["configured_K"]: int(item["drop_ticks"])
                    for item in record["candidate_records"]
                }
                self.assertGreaterEqual(
                    drop_by_K[475_136], int(counterfactual["drop_ticks"])
                )
                self.assertGreaterEqual(
                    int(counterfactual["drop_ticks"]), drop_by_K[507_904]
                )
                if counterfactual["would_be_selected_if_inserted"]:
                    would_select.append(record["checkpoint_number_one_based"])
                    self.assertEqual(selected_K, 507_904)
            self.assertEqual(would_select, [58, 59])
            self.assertEqual(feasible_checkpoints, list(range(1, 60)))

        for item in walk(transcript):
            self.assertIsNot(type(item), float)
            if type(item) is str:
                self.assertFalse(item.startswith("/"))

    def test_12_magnetization_canonical_transcript_when_available(self):
        self.assert_canonical_transcript("magnetization")

    def test_13_double_occupancy_canonical_transcript_when_available(self):
        self.assert_canonical_transcript("double_occupancy")

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_FOUR_GATE_CANONICAL_REPLAY") == "1",
        "expensive deterministic four-gate canonical replays are opt-in",
    )
    def test_14_real_canonical_replays_are_opt_in(self):
        for mode in SCREEN.MODE_CONFIG:
            with self.subTest(mode=mode):
                path = HERE / SCREEN.MODE_CONFIG[mode]["output_name"]
                expected = path.read_bytes()
                self.assertEqual(canonical_bytes(SCREEN.run(HERE, mode)), expected)

    @unittest.skipUnless(
        os.environ.get(
            "RUN_HUBBARD_L8_FOUR_GATE_D_LADDER_SENSITIVITY"
        ) == "1",
        "expensive noncanonical D ladder sensitivity replay is opt-in",
    )
    def test_15_double_occupancy_ladder_sensitivity_is_opt_in(self):
        self.assertEqual(len(NONCANONICAL_D_SENSITIVITY_CANDIDATES), 32)
        self.assertNotIn(65_536, NONCANONICAL_D_SENSITIVITY_CANDIDATES)
        self.assertIn(491_520, NONCANONICAL_D_SENSITIVITY_CANDIDATES)
        self.assertEqual(
            hashlib.sha256(
                canonical_bytes(list(NONCANONICAL_D_SENSITIVITY_CANDIDATES))
            ).hexdigest(),
            NONCANONICAL_D_SENSITIVITY_CANDIDATE_SHA256,
        )

        sensitivity = SCREEN.fresh_self_module()
        configuration = sensitivity.load_v6_configuration(HERE)
        configuration.MODE_CONFIG = copy.deepcopy(configuration.MODE_CONFIG)
        configuration.MODE_CONFIG["double_occupancy"]["candidates"] = (
            NONCANONICAL_D_SENSITIVITY_CANDIDATES
        )
        sensitivity.load_v6_configuration = lambda _repo: configuration

        # Numerical sensitivity only: do not serialize a result whose v6
        # configuration-reference source does not contain this altered ladder.
        result = sensitivity.run_four_gate(HERE, "double_occupancy")
        failure = result["records"][-1]
        self.assertEqual(
            result["candidate_K_values_sha256"],
            NONCANONICAL_D_SENSITIVITY_CANDIDATE_SHA256,
        )
        self.assertEqual(result["completed_checkpoint_count"], 64)
        self.assertEqual(result["attempted_checkpoint_count"], 65)
        self.assertFalse(result["horizon_reached_with_committed_checkpoint"])
        self.assertEqual(failure["checkpoint_number_one_based"], 65)
        self.assertEqual(
            (
                failure["gate_occurrence_first_zero_based"],
                failure["gate_occurrence_last_zero_based"],
            ),
            (256, 259),
        )
        self.assertEqual(failure["minimum_effective_K_to_meet_prefix"], 536_203)
        self.assertEqual(failure["required_K_excess_over_policy_maximum"], 11_915)
        self.assertEqual(result["observed_peak_single_expansion_terms"], 645_044)
        self.assertEqual(
            result["observed_term_gate_visits_including_terminal_attempt"],
            75_255_249,
        )
        self.assertEqual(
            result["observed_maximum_expansion_coefficient_tick_bits"], 63
        )
        self.assertEqual(result["observed_maximum_product_bits"], 120)
        self.assertEqual(
            result["observed_rounding_cumulative_scaled_ticks_squared"],
            "96721781715331738385349508",
        )
        self.assertEqual(
            result["last_committed_cumulative_drop_ticks"],
            "2288346482476575",
        )
        self.assertEqual(
            result["records_sha256"],
            "1baff00ff39f2d15745684c38bcb07dab54e1612ed2a8d947357beccdb9860f8",
        )
        self.assertEqual(
            result["selected_K_history_sha256"],
            "6fa66d189b7680e5e224cb2ff4d50b1482f6ddca5af189e2a4eca99e9579a07d",
        )
        self.assertEqual(result["selected_K_history"][57:59], [491_520, 491_520])


if __name__ == "__main__":
    unittest.main()
