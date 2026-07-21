#!/usr/bin/env python3
"""Static, synthetic, canonical and opt-in tests for the M C31 q84 screen."""

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
    "k557056_c31_q84_screen.py"
)
EXPECTED_SCREEN_SHA256 = (
    "d778440f6a86adf7d4498d2c3496c0f650c7782379c9f5b25c1e979ad01a136f"
)
EXPECTED_CANONICAL = {
    "file_sha256": "2f866d658570c9cf667088662a98288c14b41144c3ffacdefd862aaf8f185138",
    "records_sha256": "ec428e76d1c6e71f46a90caf0a040260174469c198a974d4c8e0f8e939441d40",
    "history_sha256": "8c6902944bc0fc1c1c533a4e3e7ca6f65c17f43fef3c6a94f633616b38123e40",
    "failure_sha256": "6e715a8d7e1acc489c2e3424a2cafb424e30ab8dfbba19a49d5cc6a1e4089b4c",
    "components_sha256": "a958e9223d84dd00336637e4815a531d8e17ef653495c751f68978a040417a79",
    "configuration_reference_sha256": "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138",
    "configuration_override_sha256": "ec25a4c736f761a4b27c667b87c2c50c86ab890817c9a5f6839ffe27d8d65c58",
    "kernel_override_sha256": "bf534a1319b0b7f9d10b37273ce75756d53725e539eb3a727c689592d2300fb3",
    "parent_horizon_override_sha256": "32110dc50944263e6b6bcc511a7e97b9678322b0ef79c7ff3380fbc3697095ad",
    "route_reference_sha256": "96c463ce660c46a7297aa3a014fcf693ae444760699a710eec665386c4bfc98c",
    "handoff_sha256": "64dd6066bbf0cf309a85ac9854137fffd215d47e5ed63890bed809d62d82fcaa",
    "horizon_extension_sha256": "064fce95da408de2025bdfd14c770ec3cf6265073a6f6664c634c060f20709f3",
    "transform_sha256": "d64a165cbf0cd13f269cb1d15c45bc634dafa4d990705ea95928890136afb103",
    "last_E": "1700039048594959",
    "peak": 652_016,
    "visits": 93_965_211,
    "coefficient_bits": 57,
    "product_bits": 121,
    "rounding": "131187710080178938720344394",
}


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCREEN = load_module("magnetization_k557056_c31_q84_for_tests", SCREEN_NAME)


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


class MagnetizationK557056C31Q84Tests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def synthetic_base_result(self):
        result = json.loads((HERE / SCREEN.BASE_TRANSCRIPT_NAME).read_bytes())
        result["screen_horizon_checkpoint_count"] = SCREEN.EXTENDED_HORIZON
        failure = {
            "checkpoint_number_one_based": 83,
            "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        }
        result["records"].append(failure)
        result["records_sha256"] = sha256(canonical_bytes(result["records"]))
        result["selected_K_history_sha256"] = sha256(
            canonical_bytes(result["selected_K_history"])
        )
        result["attempted_checkpoint_count"] = 83
        result["completed_checkpoint_count"] = 82
        result["screen_terminal_condition"] = (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        )
        result["horizon_checkpoint_attempted"] = False
        result["horizon_reached_with_committed_checkpoint"] = False
        result["failure_checkpoint_included"] = True
        result["failure_record_sha256"] = sha256(canonical_bytes(failure))
        parent_override = SCREEN.expected_q84_parent_horizon_override(result)
        result["parent_horizon_override"] = parent_override
        result["parent_horizon_override_sha256"] = sha256(
            canonical_bytes(parent_override)
        )
        handoff = SCREEN.expected_q84_handoff(result)
        result["predecessor_handoff_validation"] = handoff
        result["predecessor_handoff_validation_sha256"] = sha256(
            canonical_bytes(handoff)
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
        anchor = fresh.load_base_transcript(HERE, base)
        before_horizon = base.EXTENDED_HORIZON
        before_candidates = tuple(base.M_CANDIDATES)
        before_caps = copy.deepcopy(base.POLICY_CAPS_BASE)
        before_limits = copy.deepcopy(
            base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS
        )
        manifest = fresh.install_horizon_adapter(base, anchor)
        base.validate_local_configuration()

        self.assertEqual(before_horizon, 82)
        self.assertEqual(base.EXTENDED_HORIZON, 84)
        self.assertEqual(tuple(base.M_CANDIDATES), before_candidates)
        self.assertEqual(base.POLICY_CAPS_BASE, before_caps)
        self.assertEqual(base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS, before_limits)
        self.assertEqual(manifest["changed_semantic_fields"], ["EXTENDED_HORIZON"])
        self.assertEqual(
            manifest["semantic_delta"],
            {"EXTENDED_HORIZON": {"before": 82, "after": 84}},
        )
        self.assertTrue(manifest["double_occupancy_configuration_unchanged"])
        self.assertTrue(manifest["physical_gate_sequence_unchanged"])
        self.assertTrue(manifest["full_replay_from_checkpoint_one"])
        self.assertFalse(manifest["checkpoint_82_state_loaded_from_transcript"])
        self.assertFalse(
            manifest["returned_parent_mode_config_mutated_by_outer_adapter"]
        )
        self.assertIn(
            "base_q82.validate_replay_handoff",
            manifest["runtime_adapter_functions"],
        )
        self.assertIn(
            "base_q82.load_route_predecessor_reference",
            manifest["runtime_adapter_functions"],
        )

        parent = base.load_control_flow_parent(HERE)
        self.assertEqual(
            parent.MODE_CONFIG[SCREEN.MODE]["horizon_checkpoint_count"], 80
        )
        self.assertEqual(
            parent.MODE_CONFIG["double_occupancy"]["horizon_checkpoint_count"],
            66,
        )
        pristine, _ = fresh.load_base_screen(HERE)
        self.assertEqual(pristine.EXTENDED_HORIZON, 82)

    def test_03_adapter_restores_q84_state_on_provider_errors(self):
        state = {
            "fail_validator": False,
            "fail_loader": False,
            "fail_route": False,
            "fail_handoff": False,
        }
        fake = types.SimpleNamespace(
            EXTENDED_HORIZON=82,
            M_CANDIDATES=tuple(range(1, 32)),
            POLICY_CAPS_BASE={"max_candidate_K": 557_056},
            EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS={
                "max_candidate_count": 32,
                "max_retained_K": 557_056,
            },
        )
        validator_error = RuntimeError("q84 validator sentinel")
        loader_error = RuntimeError("q84 loader sentinel")
        route_error = RuntimeError("q84 route sentinel")
        handoff_error = RuntimeError("q84 handoff sentinel")
        anchor_records = [{"checkpoint_number_one_based": q} for q in range(1, 83)]
        anchor_history = list(range(82))
        base_handoff = {"base_q82_handoff": True}
        anchor = {
            "records": anchor_records,
            "selected_K_history": anchor_history,
            "predecessor_handoff_validation": base_handoff,
            "predecessor_handoff_validation_sha256": sha256(
                canonical_bytes(base_handoff)
            ),
        }

        def original_validator():
            self.assertEqual(fake.EXTENDED_HORIZON, 82)
            if state["fail_validator"]:
                raise validator_error

        def original_loader(_repo):
            self.assertEqual(fake.EXTENDED_HORIZON, 82)
            if state["fail_loader"]:
                raise loader_error
            return types.SimpleNamespace(MODE_CONFIG={
                "magnetization": {"horizon_checkpoint_count": 80},
                "double_occupancy": {"horizon_checkpoint_count": 66},
            })

        def original_handoff(result, _predecessor):
            self.assertEqual(fake.EXTENDED_HORIZON, 82)
            self.assertEqual(result["records"], anchor_records)
            self.assertEqual(result["selected_K_history"], anchor_history)
            if state["fail_handoff"]:
                raise handoff_error
            return base_handoff

        def original_route_loader(_repo):
            self.assertEqual(fake.EXTENDED_HORIZON, 82)
            if state["fail_route"]:
                raise route_error
            return {"route": True}, {"reference": True}

        fake.validate_local_configuration = original_validator
        fake.load_control_flow_parent = original_loader
        fake.load_route_predecessor_reference = original_route_loader
        fake.validate_replay_handoff = original_handoff
        SCREEN.install_horizon_adapter(fake, anchor)
        self.assertEqual(fake.EXTENDED_HORIZON, 84)

        state["fail_validator"] = True
        with self.assertRaises(RuntimeError) as caught:
            fake.validate_local_configuration()
        self.assertIs(caught.exception, validator_error)
        self.assertEqual(fake.EXTENDED_HORIZON, 84)
        state["fail_validator"] = False
        state["fail_loader"] = True
        with self.assertRaises(RuntimeError) as caught:
            fake.load_control_flow_parent(HERE)
        self.assertIs(caught.exception, loader_error)
        self.assertEqual(fake.EXTENDED_HORIZON, 84)
        state["fail_loader"] = False
        state["fail_route"] = True
        with self.assertRaises(RuntimeError) as caught:
            fake.load_route_predecessor_reference(HERE)
        self.assertIs(caught.exception, route_error)
        self.assertEqual(fake.EXTENDED_HORIZON, 84)
        state["fail_route"] = False

        result = {
            "records": anchor_records + [{
                "checkpoint_number_one_based": 83,
                "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
            }],
            "selected_K_history": anchor_history,
            "attempted_checkpoint_count": 83,
            "completed_checkpoint_count": 82,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
        }
        result["records_sha256"] = sha256(canonical_bytes(result["records"]))
        result["selected_K_history_sha256"] = sha256(
            canonical_bytes(result["selected_K_history"])
        )
        result["failure_record_sha256"] = sha256(
            canonical_bytes(result["records"][-1])
        )
        state["fail_handoff"] = True
        with self.assertRaises(RuntimeError) as caught:
            fake.validate_replay_handoff(result, {})
        self.assertIs(caught.exception, handoff_error)
        self.assertEqual(fake.EXTENDED_HORIZON, 84)

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
        resource_error = RuntimeError("M q84 resource sentinel")

        class Base:
            @staticmethod
            def _run_verified(_repo):
                raise resource_error

        fresh.load_base_screen = lambda _repo: (Base(), b"base")
        fresh.load_base_transcript = lambda *_args: {}
        fresh.install_horizon_adapter = lambda *_args: {}
        with self.assertRaises(RuntimeError) as caught:
            fresh._run_verified(HERE)
        self.assertIs(caught.exception, resource_error)

    def test_05_real_q82_private_path_receives_M84_without_replay(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        anchor = fresh.load_base_transcript(HERE, base)
        fresh.install_horizon_adapter(base, anchor)
        adapted_loader = base.load_control_flow_parent
        observed = {}

        def load_sentinel_parent(repo):
            parent = adapted_loader(repo)

            def private_sentinel(inner_repo, mode):
                observed["repo"] = inner_repo
                observed["mode"] = mode
                observed["M_horizon"] = parent.MODE_CONFIG[mode][
                    "horizon_checkpoint_count"
                ]
                observed["D_config"] = copy.deepcopy(
                    parent.MODE_CONFIG["double_occupancy"]
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
                return {"q82_private_parent_result": True}

            parent._run_verified = private_sentinel
            return parent

        base.load_control_flow_parent = load_sentinel_parent
        base.validate_and_relabel = lambda result, *_args: result
        result = base._run_verified(HERE)
        self.assertEqual(result, {"q82_private_parent_result": True})
        self.assertEqual(observed["repo"], HERE.resolve())
        self.assertEqual(observed["mode"], SCREEN.MODE)
        self.assertEqual(observed["M_horizon"], 84)
        self.assertEqual(observed["D_config"]["horizon_checkpoint_count"], 66)
        self.assertEqual(observed["candidates"], base.M_CANDIDATES)
        self.assertEqual(observed["caps"], base.POLICY_CAPS_BASE)
        self.assertEqual(
            observed["kernel_limits"],
            base.EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
        )

    def test_06_q82_anchor_is_non_state_and_prefix_validation_is_exact(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        anchor = fresh.load_base_transcript(HERE, base)
        fresh.install_horizon_adapter(base, anchor)
        result = self.synthetic_base_result()
        fresh.validate_base_result(result, base, anchor)
        predecessor, _route_reference = base.load_route_predecessor_reference(
            HERE
        )
        self.assertEqual(
            base.validate_replay_handoff(result, predecessor),
            fresh.expected_q84_handoff(anchor),
        )

        relabeled = fresh.relabel_outer_result(
            copy.deepcopy(result),
            base,
            anchor,
            fresh.adapter_manifest(base),
        )
        reference = relabeled["base_canonical_reference_artifact"]
        self.assertTrue(reference["loaded_before_replay_as_exact_reference"])
        self.assertTrue(
            reference["used_only_after_replay_for_result_prefix_validation"]
        )
        self.assertTrue(reference["post_replay_prefix_validation_input"])
        for key in (
            "propagation_input",
            "checkpoint_82_state_loaded",
            "state_resume_input",
            "execution_source_layer",
        ):
            self.assertFalse(reference[key], key)

        tampered = copy.deepcopy(result)
        tampered["records"][0]["E_before_ticks"] = "-1"
        tampered["records_sha256"] = sha256(canonical_bytes(tampered["records"]))
        with self.assertRaisesRegex(RuntimeError, "q1-82 record prefix"):
            fresh.validate_base_result(tampered, base, anchor)

        tampered = copy.deepcopy(result)
        tampered["selected_K_history"][0] += 1
        tampered["selected_K_history_sha256"] = sha256(
            canonical_bytes(tampered["selected_K_history"])
        )
        with self.assertRaisesRegex(RuntimeError, "q1-82 history prefix"):
            fresh.validate_base_result(tampered, base, anchor)

    def test_07_synthetic_outer_provenance_hashes_and_authority(self):
        fresh = SCREEN.fresh_self_module()
        base, _payload = fresh.load_base_screen(HERE)
        anchor = fresh.load_base_transcript(HERE, base)
        adapter = fresh.install_horizon_adapter(base, anchor)
        result = fresh.relabel_outer_result(
            self.synthetic_base_result(),
            base,
            anchor,
            adapter,
        )
        self.assertEqual(result["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            result["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k557056_c31_q84_screen_v1",
        )
        self.assertTrue(result["horizon_extension_parent_private_entrypoint_called"])
        self.assertFalse(result["horizon_extension_parent_public_entrypoint_called"])
        self.assertTrue(result["q82_private_entrypoint_owns_full_replay_execution"])
        self.assertTrue(
            result["physical_checkpoint_loop_ownership_preserved_from_q82_result"]
        )
        self.assertEqual(
            result["horizon_extension_override"]["semantic_delta"],
            {"EXTENDED_HORIZON": {"before": 82, "after": 84}},
        )
        self.assertEqual(
            result["parent_horizon_override"]["semantic_delta"],
            {
                "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
                    "before": 80,
                    "after": 84,
                },
            },
        )
        self.assertEqual(
            result["parent_horizon_override"]["parent_mode_config_after"]
            ["double_occupancy"]["horizon_checkpoint_count"],
            66,
        )
        roles = {
            item["relative_path"]: item["role"]
            for item in result["screen_execution_components"]
        }
        self.assertEqual(
            roles[SCREEN.SELF_NAME],
            "M_k557056_c31_q84_fresh_same_byte_horizon_wrapper",
        )
        self.assertEqual(
            roles[SCREEN.BASE_SCREEN_NAME],
            "M_k557056_c31_q82_private_execution_parent_for_q84",
        )
        for field, value in (
            ("screen_execution_components_sha256", result["screen_execution_components"]),
            ("horizon_extension_override_sha256", result["horizon_extension_override"]),
            ("parent_horizon_override_sha256", result["parent_horizon_override"]),
            ("predecessor_handoff_validation_sha256", result["predecessor_handoff_validation"]),
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
            output = pathlib.Path(directory) / "M-q84.json"
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

        self.assertEqual(SCREEN.MODE, "magnetization")
        self.assertEqual(SCREEN.BASE_HORIZON, 82)
        self.assertEqual(SCREEN.EXTENDED_HORIZON, 84)
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
        selected_history = []
        previous = None

        base, _payload = SCREEN.load_base_screen(HERE)
        anchor = SCREEN.load_base_transcript(HERE, base)
        SCREEN.install_horizon_adapter(base, anchor)
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

            rows = record["candidate_records"]
            self.assertEqual(len(rows), 31)
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
            transcript["observed_rounding_cumulative_scaled_ticks_squared"],
            str(rounding),
        )
        predecessor, _reference = base.load_route_predecessor_reference(HERE)
        base.validate_replay_handoff(transcript, predecessor)

    def assert_canonical_when_available(self):
        path = HERE / SCREEN.OUTPUT_NAME
        if not path.exists():
            self.skipTest("canonical M K557056/C31 q84 transcript not generated yet")
        raw = path.read_bytes()
        transcript = json.loads(raw)
        self.assertEqual(sha256(raw), EXPECTED_CANONICAL["file_sha256"])
        base, _payload = SCREEN.load_base_screen(HERE)
        anchor = SCREEN.load_base_transcript(HERE, base)
        SCREEN.install_horizon_adapter(base, anchor)
        self.assertEqual(raw, canonical_bytes(transcript))
        self.assertLessEqual(len(raw), SCREEN.MAX_OUTPUT_BYTES)
        self.assertEqual(transcript["screen_source_sha256"], EXPECTED_SCREEN_SHA256)
        self.assertEqual(
            transcript["transcript_fingerprint"],
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k557056_c31_q84_screen_v1",
        )
        self.assertEqual(
            transcript["status"], "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"
        )
        self.assertEqual(transcript["screen_horizon_checkpoint_count"], 84)
        self.assertEqual(transcript["screen_terminal_condition"],
                         "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE")
        self.assertEqual(transcript["attempted_checkpoint_count"], 83)
        self.assertEqual(transcript["completed_checkpoint_count"], 82)
        self.assertTrue(transcript["failure_checkpoint_included"])
        self.assertFalse(transcript["horizon_reached_with_committed_checkpoint"])
        self.assertEqual(len(transcript["records"]), 83)
        self.assertEqual(len(transcript["selected_K_history"]), 82)
        exact_fields = {
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
        for transcript_field, expected_field in exact_fields.items():
            self.assertEqual(
                transcript[transcript_field],
                EXPECTED_CANONICAL[expected_field],
                transcript_field,
            )
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
        self.assertEqual(transcript["records"][:82], anchor["records"])
        self.assertEqual(
            transcript["selected_K_history"][:82],
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
        reference = transcript["base_canonical_reference_artifact"]
        self.assertEqual(reference["file_sha256"], SCREEN.EXPECTED_BASE_TRANSCRIPT_SHA256)
        self.assertTrue(reference["post_replay_prefix_validation_input"])
        self.assertFalse(reference["propagation_input"])
        self.assertFalse(reference["checkpoint_82_state_loaded"])
        self.assertFalse(reference["state_resume_input"])
        self.assertFalse(reference["execution_source_layer"])
        failure = transcript["records"][-1]
        self.assertEqual(failure["checkpoint_number_one_based"], 83)
        self.assertEqual(failure["gate_occurrence_first_zero_based"], 328)
        self.assertEqual(failure["gate_occurrence_last_zero_based"], 331)
        self.assertEqual(failure["stage_group"], "HU")
        self.assertEqual(failure["stage_index"], 2)
        self.assertEqual(failure["batch_in_stage"], 26)
        self.assertEqual(failure["input_expansion_count"], 557_056)
        self.assertEqual(failure["pretruncation_expansion_count"], 652_016)
        self.assertEqual(failure["prefix_slack_before_selection_ticks"],
                         "133727664071")
        self.assertEqual(failure["minimum_effective_K_to_meet_prefix"], 565_994)
        self.assertEqual(failure["required_K_excess_over_policy_maximum"], 8_938)
        self.assertEqual(
            failure["maximum_candidate_drop_excess_over_slack_ticks"],
            "122768209378",
        )
        final_row = failure["candidate_records"][-1]
        self.assertEqual(final_row["candidate_index"], 30)
        self.assertEqual(final_row["configured_K"], 557_056)
        self.assertEqual(final_row["drop_ticks"], "256495873449")
        self.assertEqual(final_row["dropped_term_count"], 94_960)
        self.assertFalse(final_row["feasible_under_current_prefix_cap"])
        for field in (
            "configuration_reference",
            "configuration_override",
            "kernel_capability_override",
            "route_predecessor_reference",
        ):
            self.assertEqual(transcript[field], anchor[field], field)
        self.assertEqual(
            transcript["parent_horizon_override"],
            SCREEN.expected_q84_parent_horizon_override(anchor),
        )
        self.assertEqual(
            transcript["predecessor_handoff_validation"],
            SCREEN.expected_q84_handoff(anchor),
        )
        self.assertFalse(transcript["candidate_policy_precommitted_at_probe_time"])
        self.assertFalse(transcript["child_boundary_committed"])
        self.assertFalse(transcript["positive_artifact_generated"])
        self.assert_full_canonical_ledger(transcript)

    def test_09_canonical_transcript_full_ledger_when_available(self):
        self.assert_canonical_when_available()

    @unittest.skipUnless(
        os.environ.get("RUN_HUBBARD_L8_MAGNETIZATION_K557056_C31_Q84_REPLAY")
        == "1",
        "expensive deterministic M K557056/C31 q84 replay is opt-in",
    )
    def test_10_real_canonical_replay_is_opt_in(self):
        path = HERE / SCREEN.OUTPUT_NAME
        self.assertTrue(path.exists(), "missing canonical M C31 q84 transcript")
        self.assertEqual(canonical_bytes(SCREEN.run(HERE)), path.read_bytes())


if __name__ == "__main__":
    unittest.main()
