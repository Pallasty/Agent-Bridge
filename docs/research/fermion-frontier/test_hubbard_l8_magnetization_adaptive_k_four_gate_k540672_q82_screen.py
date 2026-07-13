#!/usr/bin/env python3
"""Static, synthetic and opt-in tests for the M K540672 q82 screen."""

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
    "k540672_q82_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "c06d2be38215266f1d19dc64116041b456e2a597e6aa24aa63b9ffbaeda86b03"
)
EXPECTED_CANONICAL = {
    "file_sha256": (
        "0486a8b19077de9e90f134c7b3c0d43fdf3504a4876d6e0b2c3d01b37b89cb52"
    ),
    "records_sha256": (
        "55e74ae79a1761817f1e80e4922476b5dbc6a01b9125c6e04ad68596e7cf221c"
    ),
    "history_sha256": (
        "43dabd7d34c8de39a91388080dac5e941c162867771fe39fe8a216f7ad00dcc9"
    ),
    "failure_sha256": (
        "00a66d441fa03dde95596dd689576933dd63ee340d2ec2f4c615dadb799f323d"
    ),
    "components_sha256": (
        "f51362ca703af20b2dad48eafef6be56964fb0bca706f6603ddf7ca8c1df26c1"
    ),
    "horizon_override_sha256": (
        "dc17b75530181be7749ec5f3356ff05043904bbca4d36bc25598aa97661fc914"
    ),
    "transform_sha256": (
        "68b6ee4d4647cf4d49bc854f6e5f42b0d029eaf8fba070527f0dac35155566c1"
    ),
    "attempted": 81,
    "completed": 80,
    "last_E": "1699769017939651",
    "peak": 643_624,
    "visits": 89_253_151,
    "coefficient_bits": 57,
    "product_bits": 121,
    "rounding": "122502541637271827355516405",
}


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("magnetization_k540672_q82_for_tests", SCREEN_NAME)


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


class MagnetizationK540672Q82Tests(unittest.TestCase):
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

    def test_02_adapter_changes_only_the_M_horizon(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        before_config = copy.deepcopy(base.MODE_CONFIG)
        before_candidates = tuple(base.M_CANDIDATES)
        before_caps = copy.deepcopy(base.POLICY_CAPS_BASE)
        before_limits = copy.deepcopy(base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS)
        manifest = fresh.install_horizon_adapter(base)
        base.validate_local_configuration()

        after_config = base.MODE_CONFIG
        changed = []
        for mode in before_config:
            for key in before_config[mode]:
                if before_config[mode][key] != after_config[mode][key]:
                    changed.append(f"MODE_CONFIG.{mode}.{key}")
        self.assertEqual(
            changed,
            ["MODE_CONFIG.magnetization.horizon_checkpoint_count"],
        )
        self.assertEqual(
            before_config["magnetization"]["horizon_checkpoint_count"], 80
        )
        self.assertEqual(
            after_config["magnetization"]["horizon_checkpoint_count"], 82
        )
        self.assertEqual(
            after_config["double_occupancy"], before_config["double_occupancy"]
        )
        self.assertEqual(tuple(base.M_CANDIDATES), before_candidates)
        self.assertEqual(base.POLICY_CAPS_BASE, before_caps)
        self.assertEqual(base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS, before_limits)
        self.assertEqual(
            manifest["changed_semantic_fields"],
            ["MODE_CONFIG.magnetization.horizon_checkpoint_count"],
        )
        self.assertTrue(manifest["double_occupancy_configuration_unchanged"])
        self.assertTrue(manifest["full_replay_from_checkpoint_one"])
        self.assertFalse(manifest["checkpoint_80_state_loaded_from_transcript"])

        parent = base.load_control_flow_parent(HERE)
        self.assertEqual(
            parent.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 82
        )
        pristine, _ = fresh.load_base_screen(HERE)
        pristine_parent = pristine.load_control_flow_parent(HERE)
        self.assertEqual(
            pristine_parent.MODE_CONFIG["magnetization"][
                "horizon_checkpoint_count"
            ],
            80,
        )

    def test_03_adapter_restores_effective_state_on_provider_errors(self):
        state = {"fail_validator": False, "fail_loader": False}
        fake = types.SimpleNamespace()
        fake.MODE_CONFIG = {
            "magnetization": {
                "candidates": (1, 2),
                "horizon_checkpoint_count": 80,
                "output_name": "m.json",
            },
            "double_occupancy": {
                "candidates": (3, 4),
                "horizon_checkpoint_count": 66,
                "output_name": "d.json",
            },
        }
        fake.POLICY_CAPS_BASE = {"max_candidate_K": 540_672}
        fake.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
            "max_retained_K": 540_672,
        }

        def original_validator():
            self.assertEqual(
                fake.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 80
            )
            if state["fail_validator"]:
                raise RuntimeError("validator sentinel")

        def original_loader(_repo):
            self.assertEqual(
                fake.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 80
            )
            if state["fail_loader"]:
                raise RuntimeError("loader sentinel")
            return types.SimpleNamespace(MODE_CONFIG=copy.deepcopy(fake.MODE_CONFIG))

        fake.validate_local_configuration = original_validator
        fake.load_control_flow_parent = original_loader
        SCREEN.install_horizon_adapter(fake)
        self.assertEqual(
            fake.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 82
        )

        state["fail_validator"] = True
        with self.assertRaisesRegex(RuntimeError, "validator sentinel"):
            fake.validate_local_configuration()
        self.assertEqual(
            fake.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 82
        )
        state["fail_validator"] = False
        state["fail_loader"] = True
        with self.assertRaisesRegex(RuntimeError, "loader sentinel"):
            fake.load_control_flow_parent(HERE)
        self.assertEqual(
            fake.MODE_CONFIG["magnetization"]["horizon_checkpoint_count"], 82
        )

    def test_04_public_fresh_path_and_resource_exception_identity(self):
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
        resource_error = RuntimeError("q82 resource sentinel")

        class Base:
            @staticmethod
            def _run_verified(_repo, _mode):
                raise resource_error

        fresh.load_base_screen = lambda _repo: (Base(), b"base")
        fresh.load_base_transcript = lambda *_args: {}
        fresh.install_horizon_adapter = lambda _base: {}
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

    def test_05_real_base_private_path_receives_horizon_82_without_replay(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        fresh.install_horizon_adapter(base)
        adapted_loader = base.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = adapted_loader(repo)
            observed["parent_horizon"] = parent.MODE_CONFIG["magnetization"][
                "horizon_checkpoint_count"
            ]

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                return {"private_parent_result": True}

            parent._run_verified = private_sentinel
            return parent

        base.load_control_flow_parent = load_sentinel_parent
        base.validate_and_relabel = lambda result, *_args: result
        result = base._run_verified(HERE, "magnetization")
        self.assertEqual(result, {"private_parent_result": True})
        self.assertEqual(observed["parent_horizon"], 82)
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], "magnetization")

    def synthetic_base_result(self):
        base = json.loads((HERE / SCREEN.BASE_TRANSCRIPT_NAME).read_bytes())
        result = copy.deepcopy(base)
        result["screen_horizon_checkpoint_count"] = 82
        result["horizon_checkpoint_attempted"] = False
        result["horizon_reached_with_committed_checkpoint"] = False
        result["attempted_checkpoint_count"] = 81
        result["completed_checkpoint_count"] = 81
        result["records"].append({"synthetic_checkpoint": 81})
        result["selected_K_history"].append(540_672)
        result["records_sha256"] = sha256(canonical_bytes(result["records"]))
        result["selected_K_history_sha256"] = sha256(
            canonical_bytes(result["selected_K_history"])
        )
        result["failure_record_sha256"] = None
        return result

    def test_06_synthetic_outer_relabel_has_exact_provenance_hashes(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        anchor = fresh.load_base_transcript(HERE, base)
        adapter = fresh.install_horizon_adapter(base)
        result = fresh.relabel_outer_result(
            self.synthetic_base_result(), base, anchor, adapter
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k540672_q82_screen_v1",
        )
        self.assertTrue(result["horizon_extension_parent_private_entrypoint_called"])
        self.assertFalse(result["horizon_extension_parent_public_entrypoint_called"])
        self.assertTrue(result["horizon_extension_orchestration_owned_by_outer_screen"])
        self.assertTrue(
            result["physical_checkpoint_loop_owned_by_verified_four_gate_parent"]
        )
        self.assertEqual(
            result["horizon_extension_override"]["semantic_delta"],
            {
                "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                    "before": 80,
                    "after": 82,
                },
            },
        )
        reference = result["base_canonical_reference_artifact"]
        self.assertTrue(reference["post_replay_prefix_validation_input"])
        self.assertFalse(reference["propagation_input"])
        self.assertFalse(reference["checkpoint_80_state_loaded"])
        self.assertFalse(reference["state_resume_input"])
        roles = {
            item["relative_path"]: item["role"]
            for item in result["screen_execution_components"]
        }
        self.assertEqual(
            roles[SCREEN.SELF_NAME],
            "magnetization_q82_fresh_same_byte_horizon_wrapper",
        )
        self.assertEqual(
            roles[SCREEN.BASE_SCREEN_NAME],
            "k540672_private_execution_parent_for_q82",
        )
        for field, value in (
            (
                "screen_execution_components_sha256",
                result["screen_execution_components"],
            ),
            (
                "horizon_extension_override_sha256",
                result["horizon_extension_override"],
            ),
            ("checkpoint_transform_sha256", result["checkpoint_transform"]),
        ):
            self.assertEqual(result[field], sha256(canonical_bytes(value)))
        self.assertFalse(result["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(result["child_boundary_committed"])
        self.assertFalse(result["positive_artifact_generated"])

    def test_07_four_mib_atomic_output_is_failure_preserving(self):
        self.assertEqual(SCREEN.MAX_OUTPUT_BYTES, 4_194_304)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "q82.json"
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

    def test_08_scope_is_diagnostic_only_and_M_only(self):
        source = (HERE / SCREEN.SELF_NAME).read_text()
        self.assertEqual(SCREEN.MODE, "magnetization")
        self.assertEqual(SCREEN.BASE_HORIZON, 80)
        self.assertEqual(SCREEN.EXTENDED_HORIZON, 82)
        self.assertNotIn("READY_FOR_BENCHMARK", source)
        self.assertNotIn("formal_witness", source)
        self.assertNotIn("child_boundary_sidecar", source)

    def assert_full_canonical_ledger(self, transcript):
        base, _payload = SCREEN.load_base_screen(HERE)
        parent = base.load_control_flow_parent(HERE)
        helper = parent.load_v2_helper(HERE)
        kernel, root, _modules, _custody = parent.load_execution_sources(
            HERE, helper, "magnetization"
        )
        stages, _trig, sequence, _transform = parent.build_four_gate_sequence(
            helper, root, kernel
        )
        gates = [gate for stage in stages for gate in stage["gates"]]
        self.assertEqual(len(gates), sequence["gate_count"])

        candidates = transcript["candidate_K_values"]
        helper_config = helper.CONFIG["magnetization"]
        E_input = helper_config["input_cumulative_drop_ticks"]
        maximum_drop = helper.MAXIMUM_DROP_TICKS
        denominator = transcript["future_checkpoint_denominator"]
        cumulative = E_input
        visits = 0
        rounding = 0
        peak = 0
        coefficient_bits = 0
        product_bits = 0
        selected_history = []
        previous = None

        self.assertEqual(len(transcript["records"]), EXPECTED_CANONICAL["attempted"])
        for index, record in enumerate(transcript["records"]):
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
                self.assertEqual(item["candidate_index"], candidate_index)
                effective = min(
                    item["configured_K"], record["pretruncation_expansion_count"]
                )
                self.assertEqual(item["effective_retained_count"], effective)
                self.assertEqual(
                    item["dropped_term_count"],
                    record["pretruncation_expansion_count"] - effective,
                )
                drop = int(item["drop_ticks"])
                drops.append(drop)
                self.assertEqual(
                    int(item["E_after_if_selected_ticks"]), cumulative + drop
                )
                feasible = cumulative + drop <= cap
                self.assertIs(item["feasible_under_current_prefix_cap"], feasible)
                if feasible:
                    feasible_indices.append(candidate_index)
            self.assertEqual(drops, sorted(drops, reverse=True))

            if record["status"] == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
                selected = feasible_indices[0]
                row = candidate_records[selected]
                self.assertEqual(record["selected_candidate_index"], selected)
                self.assertEqual(record["selected_K"], candidates[selected])
                self.assertEqual(int(record["selected_drop_ticks"]), drops[selected])
                self.assertEqual(
                    record["selected_effective_retained_count"],
                    row["effective_retained_count"],
                )
                self.assertEqual(
                    record["selected_dropped_term_count"], row["dropped_term_count"]
                )
                self.assertEqual(
                    record["retained_expansion_count"], row["effective_retained_count"]
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
                    drops[-1] - slack,
                )
                self.assertEqual(index, len(transcript["records"]) - 1)

        self.assertEqual(selected_history, transcript["selected_K_history"])
        self.assertEqual(len(selected_history), EXPECTED_CANONICAL["completed"])
        self.assertEqual(str(cumulative), EXPECTED_CANONICAL["last_E"])
        self.assertEqual(visits, EXPECTED_CANONICAL["visits"])
        self.assertEqual(peak, EXPECTED_CANONICAL["peak"])
        self.assertEqual(coefficient_bits, EXPECTED_CANONICAL["coefficient_bits"])
        self.assertEqual(product_bits, EXPECTED_CANONICAL["product_bits"])
        self.assertEqual(str(rounding), EXPECTED_CANONICAL["rounding"])
        self.assertEqual(
            transcript["observed_term_gate_visits_including_terminal_attempt"], visits
        )
        self.assertEqual(transcript["observed_peak_single_expansion_terms"], peak)
        self.assertEqual(
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            str(rounding),
        )

    def assert_canonical_when_available(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical M K540672 q82 transcript not generated yet")
        raw = path.read_bytes()
        transcript = json.loads(raw)
        anchor = json.loads((HERE / SCREEN.BASE_TRANSCRIPT_NAME).read_bytes())
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(transcript["screen_horizon_checkpoint_count"], 82)
        self.assertEqual(
            transcript["screen_terminal_condition"],
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        )
        self.assertEqual(
            transcript["attempted_checkpoint_count"], EXPECTED_CANONICAL["attempted"]
        )
        self.assertEqual(
            transcript["completed_checkpoint_count"], EXPECTED_CANONICAL["completed"]
        )
        self.assertEqual(transcript["records"][:80], anchor["records"])
        self.assertEqual(
            transcript["selected_K_history"][:80],
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
            (
                "screen_execution_components_sha256",
                transcript["screen_execution_components"],
            ),
            (
                "horizon_extension_override_sha256",
                transcript["horizon_extension_override"],
            ),
            ("checkpoint_transform_sha256", transcript["checkpoint_transform"]),
        ):
            self.assertEqual(transcript[field], sha256(canonical_bytes(value)))
        self.assertEqual(
            transcript["records_sha256"], EXPECTED_CANONICAL["records_sha256"]
        )
        self.assertEqual(
            transcript["selected_K_history_sha256"],
            EXPECTED_CANONICAL["history_sha256"],
        )
        self.assertEqual(
            transcript["failure_record_sha256"],
            EXPECTED_CANONICAL["failure_sha256"],
        )
        self.assertEqual(
            transcript["screen_execution_components_sha256"],
            EXPECTED_CANONICAL["components_sha256"],
        )
        self.assertEqual(
            transcript["horizon_extension_override_sha256"],
            EXPECTED_CANONICAL["horizon_override_sha256"],
        )
        self.assertEqual(
            transcript["checkpoint_transform_sha256"],
            EXPECTED_CANONICAL["transform_sha256"],
        )
        failure = transcript["records"][-1]
        self.assertEqual(failure["checkpoint_number_one_based"], 81)
        self.assertEqual(
            (
                failure["gate_occurrence_first_zero_based"],
                failure["gate_occurrence_last_zero_based"],
            ),
            (320, 323),
        )
        self.assertEqual(failure["pretruncation_expansion_count"], 597_254)
        self.assertEqual(failure["minimum_effective_K_to_meet_prefix"], 545_129)
        self.assertEqual(failure["required_K_excess_over_policy_maximum"], 4_457)
        self.assertEqual(
            int(failure["maximum_candidate_drop_excess_over_slack_ticks"]),
            61_219_754_503,
        )
        self.assertEqual(
            sha256(canonical_bytes(failure)), EXPECTED_CANONICAL["failure_sha256"]
        )
        self.assert_full_canonical_ledger(transcript)
        self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])

    def test_09_canonical_transcript_when_available(self):
        self.assert_canonical_when_available()

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_MAGNETIZATION_K540672_Q82_REPLAY") == "1",
        "expensive deterministic M q82 replay is opt-in",
    )
    def test_10_real_canonical_replay_is_opt_in(self):
        path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(path.exists(), "missing canonical M q82 transcript")
        self.assertEqual(canonical_bytes(SCREEN.run(HERE)), path.read_bytes())


if __name__ == "__main__":
    unittest.main()
