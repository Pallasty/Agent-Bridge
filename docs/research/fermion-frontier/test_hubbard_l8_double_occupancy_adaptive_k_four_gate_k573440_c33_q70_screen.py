#!/usr/bin/env python3
"""Static, synthetic, canonical and opt-in tests for the D C33 q70 screen."""

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
    "k573440_c33_q70_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "3e0ae3c21f4d8b2e56a95573ecb238dfe0542ed891ac6bbadceb72b2d03b3045"
)
EXPECTED_CANONICAL = {
    "file_sha256": "38fa337482dbd323d68f36b6debfdc6fff94d4cf8c42e68d6477b45dc02368d6",
    "records_sha256": "80bfb5ee8a9a9ccb069e20a3798de324a83cb619142a6c9bc09cae8a892535e3",
    "history_sha256": "e2d036fab34ed4a6d1b9e09309a2a83c8a9e69afaff2ca9add92505b72557607",
    "failure_sha256": "f0b1c91912a8c6826e91f3d1ea6f5948f7e3ff80109441624e597359469c8dab",
    "components_sha256": "7737ff2a9fb9d13b94ab1a4947e10099442b092f03c3114cd1a6929268b42975",
    "configuration_reference_sha256": "d8ac3bc5a105560dedd41442b14168d3e477e21e0193b96354fd7068d1fd5ab1",
    "configuration_override_sha256": "0adef0f97fecd987da077815194a1a1258d4b832de045b275eaf6f0f40216aa4",
    "kernel_override_sha256": "a3ad822405707e687ac6408ec10dfce559118f073fa7868291dbce25954af1dd",
    "parent_horizon_override_sha256": "170839c613d7686003e4edf31e09fe747a185b2470c4bd162123fd70485b47f6",
    "route_reference_sha256": "6bed98a407a7c05e1ae8883678421e1ede7a18d1998a8eea65ab49458ec10685",
    "handoff_sha256": "bd212a7d175c58e598807de8541accc6df1f39546f2d2521cf96ce44e2bccd26",
    "horizon_extension_sha256": "8ba08ec5f458e80342a9accc1aee1d31bc3fe191c5014bede5ed2dc5d6ee8b11",
    "transform_sha256": "9a8e585df892c8c04435836ffdb411f290ca0e513c9c777bf7a499ac1358e5b0",
    "last_E": "2288712409577855",
    "peak": 688_548,
    "visits": 84_984_299,
    "coefficient_bits": 63,
    "product_bits": 120,
    "rounding": "112331835717923492853131090",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("double_occupancy_k573440_c33_q70_for_tests", SCREEN_NAME)


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


class DoubleOccupancyK573440C33Q70Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def synthetic_base_result(self):
        result = json.loads((HERE / SCREEN.BASE_TRANSCRIPT_NAME).read_bytes())
        result["screen_horizon_checkpoint_count"] = SCREEN.EXTENDED_HORIZON
        failure = {
            "checkpoint_number_one_based": 69,
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        }
        result["records"].append(failure)
        result["records_sha256"] = sha256(canonical_bytes(result["records"]))
        result["selected_K_history_sha256"] = sha256(
            canonical_bytes(result["selected_K_history"])
        )
        result["attempted_checkpoint_count"] = 69
        result["completed_checkpoint_count"] = 68
        result["screen_terminal_condition"] = (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        result["horizon_checkpoint_attempted"] = False
        result["horizon_reached_with_committed_checkpoint"] = False
        result["failure_checkpoint_included"] = True
        result["failure_record_sha256"] = sha256(canonical_bytes(failure))
        parent_override = SCREEN.expected_q70_parent_horizon_override(result)
        result["parent_horizon_override"] = parent_override
        result["parent_horizon_override_sha256"] = sha256(
            canonical_bytes(parent_override)
        )
        return result

    def test_01_exact_source_base_and_canonical_anchor_pins(self):
        self_payload = (HERE / SCREEN.SELF_NAME).read_bytes()
        base_payload = (HERE / SCREEN.BASE_SCREEN_NAME).read_bytes()
        anchor_raw = (HERE / SCREEN.BASE_TRANSCRIPT_NAME).read_bytes()
        self.assertEqual(sha256(self_payload), EXPECTED_SCREEN_SHA256)
        self.assertEqual(sha256(base_payload), SCREEN.EXPECTED_BASE_SCREEN_SHA256)
        self.assertEqual(
            sha256(anchor_raw), SCREEN.EXPECTED_BASE_TRANSCRIPT_SHA256
        )
        self.assertEqual(anchor_raw, canonical_bytes(json.loads(anchor_raw)))

        fresh = SCREEN.fresh_self_module()
        self.assertIsNot(fresh, SCREEN)
        self.assertEqual(fresh._VERIFIED_SELF_SOURCE_BYTES, self_payload)
        first, first_payload = fresh.load_base_screen(HERE)
        second, second_payload = fresh.load_base_screen(HERE)
        self.assertIsNot(first, second)
        self.assertEqual(first_payload, base_payload)
        self.assertEqual(second_payload, base_payload)
        self.assertEqual(first._VERIFIED_SELF_SOURCE_BYTES, base_payload)
        anchor = fresh.load_base_transcript(HERE, first)
        self.assertEqual(
            sha256(canonical_bytes(anchor["records"])),
            SCREEN.EXPECTED_BASE_RECORDS_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(anchor["selected_K_history"])),
            SCREEN.EXPECTED_BASE_HISTORY_SHA256,
        )

    def test_02_adapter_changes_only_extended_horizon(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        before_horizon = base.EXTENDED_HORIZON
        before_candidates = tuple(base.D_CANDIDATES)
        before_caps = copy.deepcopy(base.POLICY_CAPS_BASE)
        before_limits = copy.deepcopy(
            base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        )
        manifest = fresh.install_horizon_adapter(base)
        base.validate_local_configuration()

        self.assertEqual(before_horizon, 68)
        self.assertEqual(base.EXTENDED_HORIZON, 70)
        self.assertEqual(tuple(base.D_CANDIDATES), before_candidates)
        self.assertEqual(base.POLICY_CAPS_BASE, before_caps)
        self.assertEqual(base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS, before_limits)
        self.assertEqual(manifest["changed_semantic_fields"], ["EXTENDED_HORIZON"])
        self.assertEqual(
            manifest["semantic_delta"],
            {"EXTENDED_HORIZON": {"before": 68, "after": 70}},
        )
        self.assertTrue(manifest["magnetization_configuration_unchanged"])
        self.assertTrue(manifest["physical_gate_sequence_unchanged"])
        self.assertTrue(manifest["full_replay_from_checkpoint_one"])
        self.assertFalse(manifest["checkpoint_68_state_loaded_from_transcript"])
        self.assertFalse(
            manifest["returned_parent_mode_config_mutated_by_outer_adapter"]
        )

        parent = base.load_control_flow_parent(HERE)
        self.assertEqual(
            parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 66
        )
        self.assertEqual(
            parent.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 80
        )
        pristine, _ = fresh.load_base_screen(HERE)
        self.assertEqual(pristine.EXTENDED_HORIZON, 68)

    def test_03_adapter_restores_q70_state_on_provider_errors(self):
        state = {"fail_validator": False, "fail_loader": False}
        fake = types.SimpleNamespace(
            EXTENDED_HORIZON=68,
            D_CANDIDATES=tuple(range(1, 34)),
            POLICY_CAPS_BASE={"max_candidate_K": 573_440},
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS={
                "max_candidate_count": 33,
                "max_retained_K": 573_440,
            },
        )
        validator_error = RuntimeError("q70 validator sentinel")
        loader_error = RuntimeError("q70 loader sentinel")

        def original_validator():
            self.assertEqual(fake.EXTENDED_HORIZON, 68)
            if state["fail_validator"]:
                raise validator_error

        def original_loader(_repo):
            self.assertEqual(fake.EXTENDED_HORIZON, 68)
            if state["fail_loader"]:
                raise loader_error
            return types.SimpleNamespace(MODE_CONFIG={
                "magnetization": {"horizon_checkpoint_count": 80},
                "double_occupancy": {"horizon_checkpoint_count": 66},
            })

        fake.validate_local_configuration = original_validator
        fake.load_control_flow_parent = original_loader
        SCREEN.install_horizon_adapter(fake)
        self.assertEqual(fake.EXTENDED_HORIZON, 70)

        state["fail_validator"] = True
        with self.assertRaises(RuntimeError) as caught:
            fake.validate_local_configuration()
        self.assertIs(caught.exception, validator_error)
        self.assertEqual(fake.EXTENDED_HORIZON, 70)
        state["fail_validator"] = False
        state["fail_loader"] = True
        with self.assertRaises(RuntimeError) as caught:
            fake.load_control_flow_parent(HERE)
        self.assertIs(caught.exception, loader_error)
        self.assertEqual(fake.EXTENDED_HORIZON, 70)

    def test_04_public_fresh_path_and_private_exception_identity(self):
        sentinel = {"fresh": True}

        class Inner:
            @staticmethod
            def _run_verified(repo):
                self.assertEqual(repo, HERE)
                return sentinel

        original_fresh = SCREEN.fresh_self_module
        original_private = SCREEN._run_verified
        try:
            SCREEN._run_verified = lambda *_args: self.fail("live outer path used")
            SCREEN.fresh_self_module = lambda: Inner()
            self.assertIs(SCREEN.run(HERE), sentinel)
        finally:
            SCREEN.fresh_self_module = original_fresh
            SCREEN._run_verified = original_private

        fresh = SCREEN.fresh_self_module()
        resource_error = RuntimeError("D q70 resource sentinel")

        class Base:
            @staticmethod
            def _run_verified(_repo):
                raise resource_error

        fresh.load_base_screen = lambda _repo: (Base(), b"base")
        fresh.load_base_transcript = lambda *_args: {}
        fresh.install_horizon_adapter = lambda _base: {}
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

    def test_05_real_q68_private_path_receives_D70_without_replay(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        fresh.install_horizon_adapter(base)
        adapted_loader = base.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = adapted_loader(repo)

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                observed["D_horizon"] = parent.MODE_CONFIG[mode][
                    "horizon_checkpoint_count"
                ]
                observed["M_config"] = copy.deepcopy(
                    parent.MODE_CONFIG["magnetization"]
                )
                configuration = parent.load_v6_configuration(inner_repo)
                observed["candidates"] = configuration.MODE_CONFIG[mode][
                    "candidates"
                ]
                observed["caps"] = copy.deepcopy(configuration.POLICY_CAPS_BASE)
                helper = parent.load_v2_helper(inner_repo)
                kernel, _root, _modules, _custody = parent.load_execution_sources(
                    inner_repo,
                    helper,
                    mode,
                )
                observed["kernel_limits"] = copy.deepcopy(kernel.RESOURCE_LIMITS)
                return {"q68_private_parent_result": True}

            parent._run_verified = private_sentinel
            return parent

        base.load_control_flow_parent = load_sentinel_parent
        base.validate_and_relabel = lambda result, *_args: result
        result = base._run_verified(HERE)
        self.assertEqual(result, {"q68_private_parent_result": True})
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["D_horizon"], 70)
        self.assertEqual(observed["M_config"]["horizon_checkpoint_count"], 80)
        self.assertEqual(observed["candidates"], base.D_CANDIDATES)
        self.assertEqual(observed["caps"], base.POLICY_CAPS_BASE)
        self.assertEqual(
            observed["kernel_limits"],
            base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

    def test_06_q68_anchor_is_non_state_and_prefix_validation_is_exact(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        anchor = fresh.load_base_transcript(HERE, base)
        fresh.install_horizon_adapter(base)
        result = self.synthetic_base_result()
        fresh.validate_base_result(result, base, anchor)

        reference = fresh.relabel_outer_result(
            copy.deepcopy(result),
            base,
            anchor,
            fresh.adapter_manifest(base),
        )["base_canonical_reference_artifact"]
        self.assertTrue(reference["loaded_before_replay_as_exact_reference"])
        self.assertTrue(
            reference["used_only_after_replay_for_result_prefix_validation"]
        )
        self.assertTrue(reference["post_replay_prefix_validation_input"])
        for key in (
            "propagation_input",
            "checkpoint_68_state_loaded",
            "state_resume_input",
            "execution_source_layer",
        ):
            self.assertFalse(reference[key], key)

        tampered = copy.deepcopy(result)
        tampered["records"][0]["E_before_ticks"] = "-1"
        tampered["records_sha256"] = sha256(canonical_bytes(tampered["records"]))
        with self.assertRaisesRegex(RuntimeError, "q1-68 record prefix"):
            fresh.validate_base_result(tampered, base, anchor)

        tampered = copy.deepcopy(result)
        tampered["selected_K_history"][0] += 1
        tampered["selected_K_history_sha256"] = sha256(
            canonical_bytes(tampered["selected_K_history"])
        )
        with self.assertRaisesRegex(RuntimeError, "q1-68 history prefix"):
            fresh.validate_base_result(tampered, base, anchor)

    def test_07_synthetic_outer_provenance_hashes_and_authority(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        anchor = fresh.load_base_transcript(HERE, base)
        adapter = fresh.install_horizon_adapter(base)
        result = fresh.relabel_outer_result(
            self.synthetic_base_result(),
            base,
            anchor,
            adapter,
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q70_screen_v1",
        )
        self.assertTrue(result["horizon_extension_parent_private_entrypoint_called"])
        self.assertFalse(result["horizon_extension_parent_public_entrypoint_called"])
        self.assertTrue(result["q68_private_entrypoint_owns_full_replay_execution"])
        self.assertTrue(
            result["physical_checkpoint_loop_ownership_preserved_from_q68_result"]
        )
        self.assertEqual(
            result["horizon_extension_override"]["semantic_delta"],
            {"EXTENDED_HORIZON": {"before": 68, "after": 70}},
        )
        self.assertEqual(
            result["parent_horizon_override"]["semantic_delta"],
            {
                "MODE_CONFIG.double_occupancy.horizon_checkpoint_count": {
                    "before": 66,
                    "after": 70,
                },
            },
        )
        self.assertEqual(
            result["parent_horizon_override"]["parent_mode_config_after"]
            ["magnetization"]["horizon_checkpoint_count"],
            80,
        )
        roles = {
            item["relative_path"]: item["role"]
            for item in result["screen_execution_components"]
        }
        self.assertEqual(
            roles[SCREEN.SELF_NAME],
            "D_k573440_c33_q70_fresh_same_byte_horizon_wrapper",
        )
        self.assertEqual(
            roles[SCREEN.BASE_SCREEN_NAME],
            "D_k573440_c33_q68_private_execution_parent_for_q70",
        )
        for field, value in (
            ("screen_execution_components_sha256", result["screen_execution_components"]),
            ("horizon_extension_override_sha256", result["horizon_extension_override"]),
            ("parent_horizon_override_sha256", result["parent_horizon_override"]),
            ("checkpoint_transform_sha256", result["checkpoint_transform"]),
        ):
            self.assertEqual(result[field], sha256(canonical_bytes(value)), field)
        self.assertEqual(
            result["source_custody"][SCREEN.SELF_NAME], EXPECTED_SCREEN_SHA256
        )
        self.assertEqual(
            result["source_custody"][SCREEN.BASE_SCREEN_NAME],
            SCREEN.EXPECTED_BASE_SCREEN_SHA256,
        )
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])

    def test_08_four_mib_atomic_output_and_diagnostic_scope(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "D-q70.json"
            SCREEN.write_atomic_bounded(output, b"{}")
            self.assertEqual(output.read_bytes(), b"{}")
            with self.assertRaisesRegex(RuntimeError, "exact bytes"):
                SCREEN.write_atomic_bounded(output, bytearray(b"[]"))
            with self.assertRaisesRegex(RuntimeError, "output byte cap"):
                SCREEN.write_atomic_bounded(
                    output,
                    b"x" * (SCREEN.MAX_OUTPUT_BYTES + 1),
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

        self.assertEqual(SCREEN.MODE, "double_occupancy")
        self.assertEqual(SCREEN.BASE_HORIZON, 68)
        self.assertEqual(SCREEN.EXTENDED_HORIZON, 70)
        source = (HERE / SCREEN.SELF_NAME).read_text()
        for forbidden in (
            "READY_FOR_BENCHMARK",
            "formal_witness",
            "child_boundary_sidecar",
            "positive_certificate",
        ):
            self.assertNotIn(forbidden, source)

    def assert_full_canonical_ledger(self, transcript):
        candidates = transcript["candidate_K_values"]
        records = transcript["records"]
        history = transcript["selected_K_history"]
        E_input = int(transcript["input_cumulative_drop_ticks"])
        maximum_drop = int(transcript["maximum_cumulative_drop_ticks"])
        denominator = transcript["future_checkpoint_denominator"]
        cumulative = E_input
        visits = 0
        rounding = 0
        peak = 0
        coefficient_bits = 0
        product_bits = 0
        selected_history = []
        previous = None

        base, _payload = SCREEN.load_base_screen(HERE)
        SCREEN.install_horizon_adapter(base)
        parent = base.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        kernel, root, _modules, _custody = parent.load_execution_sources(
            HERE,
            helper,
            SCREEN.MODE,
        )
        stages, _trig, sequence, _transform = parent.build_four_gate_sequence(
            helper,
            root,
            kernel,
        )
        gates = [gate for stage in stages for gate in stage["gates"]]
        self.assertEqual(len(gates), sequence["gate_count"])

        for index, record in enumerate(records):
            checkpoint = index + 1
            self.assertEqual(record["checkpoint_index_zero_based"], index)
            self.assertEqual(record["checkpoint_number_one_based"], checkpoint)
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
            cap = E_input + checkpoint * (maximum_drop - E_input) // denominator
            self.assertEqual(int(record["budget_prefix_cap_ticks"]), cap)
            self.assertEqual(int(record["E_before_ticks"]), cumulative)
            slack = cap - cumulative
            self.assertEqual(int(record["prefix_slack_before_selection_ticks"]), slack)

            visits += record["term_gate_visits_increment"]
            self.assertEqual(record["term_gate_visits_cumulative"], visits)
            rounding += int(record["rounding_increment_scaled_ticks_squared"])
            self.assertEqual(
                int(record["rounding_cumulative_scaled_ticks_squared"]),
                rounding,
            )
            peak = max(peak, record["peak_live_terms_this_checkpoint"])
            self.assertEqual(record["peak_live_terms_cumulative"], peak)
            self.assertGreaterEqual(
                record["maximum_expansion_coefficient_tick_bits"], coefficient_bits
            )
            self.assertGreaterEqual(record["maximum_product_bits"], product_bits)
            coefficient_bits = record["maximum_expansion_coefficient_tick_bits"]
            product_bits = record["maximum_product_bits"]

            rows = record["candidate_records"]
            self.assertEqual([row["configured_K"] for row in rows], candidates)
            drops = []
            feasible_indices = []
            for candidate_index, row in enumerate(rows):
                self.assertEqual(row["candidate_index"], candidate_index)
                effective = min(
                    row["configured_K"], record["pretruncation_expansion_count"]
                )
                self.assertEqual(row["effective_retained_count"], effective)
                self.assertEqual(
                    row["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                drop = int(row["drop_ticks"])
                drops.append(drop)
                self.assertEqual(
                    int(row["E_after_if_selected_ticks"]), cumulative + drop
                )
                feasible = cumulative + drop <= cap
                self.assertIs(row["feasible_under_current_prefix_cap"], feasible)
                if feasible:
                    feasible_indices.append(candidate_index)
            self.assertEqual(drops, sorted(drops, reverse=True))

            counterfactual = record["removed_491520_counterfactual"]
            cf_effective = min(491_520, record["pretruncation_expansion_count"])
            self.assertEqual(counterfactual["configured_K"], 491_520)
            self.assertEqual(counterfactual["effective_retained_count"], cf_effective)
            self.assertEqual(
                counterfactual["dropped_term_count"],
                record["pretruncation_expansion_count"] - cf_effective,
            )
            self.assertEqual(
                int(counterfactual["E_after_if_selected_ticks"]),
                cumulative + int(counterfactual["drop_ticks"]),
            )
            self.assertIs(
                counterfactual["feasible_under_current_prefix_cap"],
                cumulative + int(counterfactual["drop_ticks"]) <= cap,
            )

            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                self.assertTrue(feasible_indices)
                selected_index = feasible_indices[0]
                selected_row = rows[selected_index]
                self.assertEqual(record["selected_candidate_index"], selected_index)
                self.assertEqual(record["selected_K"], candidates[selected_index])
                self.assertEqual(
                    int(record["selected_drop_ticks"]), drops[selected_index]
                )
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
                cumulative += drops[selected_index]
                self.assertEqual(int(record["E_after_ticks"]), cumulative)
                selected_history.append(candidates[selected_index])
                previous = record
            else:
                self.assertEqual(
                    record["status"],
                    "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                )
                self.assertFalse(feasible_indices)
                self.assertIsNone(record["selected_candidate_index"])
                self.assertIsNone(record["selected_K"])
                self.assertEqual(index, len(records) - 1)
                self.assertEqual(
                    record["required_K_excess_over_policy_maximum"],
                    max(
                        0,
                        record["minimum_effective_K_to_meet_prefix"]
                        - candidates[-1],
                    ),
                )
                self.assertEqual(
                    int(record["maximum_candidate_drop_excess_over_slack_ticks"]),
                    drops[-1] - slack,
                )
            self.assertEqual(
                counterfactual["actual_selected_K"], record["selected_K"]
            )

        self.assertEqual(selected_history, history)
        self.assertEqual(transcript["attempted_checkpoint_count"], len(records))
        self.assertEqual(transcript["completed_checkpoint_count"], len(history))
        self.assertEqual(
            transcript["last_committed_cumulative_drop_ticks"], str(cumulative)
        )
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"],
            visits,
        )
        self.assertEqual(transcript["observed_peak_single_expansion_terms"], peak)
        self.assertEqual(
            transcript["observed_maximum_expansion_coefficient_tick_bits"],
            coefficient_bits,
        )
        self.assertEqual(transcript["observed_maximum_product_bits"], product_bits)
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            str(rounding),
        )
        self.assertEqual(
            transcript["root_globals_before"], transcript["root_globals_after"]
        )
        self.assertTrue(transcript["root_globals_unchanged"])
        predecessor, _reference = base.load_route_predecessor_reference(HERE)
        base.validate_replay_handoff(transcript, predecessor)

    def assert_canonical_when_available(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical D K573440/C33 q70 transcript not generated yet")
        raw = path.read_bytes()
        transcript = json.loads(raw)
        base, _payload = SCREEN.load_base_screen(HERE)
        anchor = SCREEN.load_base_transcript(HERE, base)
        SCREEN.install_horizon_adapter(base)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            transcript["transcript_fingerprint"],
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k573440_c33_q70_screen_v1",
        )
        self.assertEqual(
            transcript["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
        )
        self.assertEqual(transcript["screen_horizon_checkpoint_count"], 70)
        self.assertGreaterEqual(len(transcript["records"]), 69)
        self.assertLessEqual(len(transcript["records"]), 70)
        self.assertEqual(transcript["records"][:68], anchor["records"])
        self.assertEqual(
            transcript["selected_K_history"][:68],
            anchor["selected_K_history"],
        )
        self.assertEqual(
            transcript["candidate_K_values"], anchor["candidate_K_values"]
        )
        self.assertEqual(
            transcript["proposed_policy_caps"], anchor["proposed_policy_caps"]
        )
        self.assertEqual(
            transcript["kernel_capability_limits"],
            anchor["kernel_capability_limits"],
        )
        for field, value in (
            ("records_sha256", transcript["records"]),
            ("selected_K_history_sha256", transcript["selected_K_history"]),
            ("screen_execution_components_sha256", transcript["screen_execution_components"]),
            ("configuration_reference_sha256", transcript["configuration_reference"]),
            ("configuration_override_sha256", transcript["configuration_override"]),
            ("kernel_capability_override_sha256", transcript["kernel_capability_override"]),
            ("parent_horizon_override_sha256", transcript["parent_horizon_override"]),
            ("route_predecessor_reference_sha256", transcript["route_predecessor_reference"]),
            ("predecessor_handoff_validation_sha256", transcript["predecessor_handoff_validation"]),
            ("horizon_extension_override_sha256", transcript["horizon_extension_override"]),
            ("checkpoint_transform_sha256", transcript["checkpoint_transform"]),
        ):
            self.assertEqual(transcript[field], sha256(canonical_bytes(value)), field)
        frozen_hashes = {
            "records_sha256": "records_sha256",
            "selected_K_history_sha256": "history_sha256",
            "failure_record_sha256": "failure_sha256",
            "screen_execution_components_sha256": "components_sha256",
            "configuration_reference_sha256": "configuration_reference_sha256",
            "configuration_override_sha256": "configuration_override_sha256",
            "kernel_capability_override_sha256": "kernel_override_sha256",
            "parent_horizon_override_sha256": "parent_horizon_override_sha256",
            "route_predecessor_reference_sha256": "route_reference_sha256",
            "predecessor_handoff_validation_sha256": "handoff_sha256",
            "horizon_extension_override_sha256": "horizon_extension_sha256",
            "checkpoint_transform_sha256": "transform_sha256",
        }
        for transcript_field, expected_field in frozen_hashes.items():
            self.assertEqual(
                transcript[transcript_field],
                EXPECTED_CANONICAL[expected_field],
                transcript_field,
            )
        self.assertEqual(transcript["attempted_checkpoint_count"], 69)
        self.assertEqual(transcript["completed_checkpoint_count"], 68)
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
        failure = transcript["records"][-1]
        self.assertEqual(failure["checkpoint_number_one_based"], 69)
        self.assertEqual(failure["pretruncation_expansion_count"], 644_504)
        self.assertEqual(failure["minimum_effective_K_to_meet_prefix"], 579_098)
        self.assertEqual(failure["required_K_excess_over_policy_maximum"], 5_658)
        self.assertEqual(
            int(failure["maximum_candidate_drop_excess_over_slack_ticks"]),
            39_565_157_110,
        )
        reference = transcript["base_canonical_reference_artifact"]
        self.assertEqual(reference["file_sha256"], SCREEN.EXPECTED_BASE_TRANSCRIPT_SHA256)
        self.assertTrue(reference["post_replay_prefix_validation_input"])
        self.assertFalse(reference["propagation_input"])
        self.assertFalse(reference["checkpoint_68_state_loaded"])
        self.assertFalse(reference["state_resume_input"])
        self.assertFalse(reference["execution_source_layer"])
        self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])
        for field in (
            "configuration_reference",
            "configuration_override",
            "kernel_capability_override",
            "route_predecessor_reference",
            "predecessor_handoff_validation",
        ):
            self.assertEqual(transcript[field], anchor[field], field)
        self.assertEqual(
            transcript["parent_horizon_override"],
            SCREEN.expected_q70_parent_horizon_override(anchor),
        )
        self.assert_full_canonical_ledger(transcript)

    def test_09_canonical_transcript_full_ledger_when_available(self):
        self.assert_canonical_when_available()

    @unittest.skipUnless(
        os.environ.get(
            "RUN_HUBBARD_L8_DOUBLE_OCCUPANCY_K573440_C33_Q70_REPLAY"
        ) == "1",
        "expensive deterministic D K573440/C33 q70 replay is opt-in",
    )
    def test_10_real_canonical_replay_is_opt_in(self):
        path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(path.exists(), "missing canonical D C33 q70 transcript")
        self.assertEqual(canonical_bytes(SCREEN.run(HERE)), path.read_bytes())


if __name__ == "__main__":
    unittest.main()
